"""v2 pipeline: dataset pairing, view detection, target selection, pole detection, frontal measures,
visual clap, drift check, despiking, cache round trip."""

import cv2
import numpy as np
import pytest

from trailbuddy.core import dataset, frontal, pole_auto, pose_rtm, sync
from trailbuddy.core.landmarks import N_LANDMARKS, PoseSeries
from trailbuddy.core.signal import despike


def test_envelope_ncc_recovers_known_lag():
    rng = np.random.default_rng(0)
    base = rng.normal(size=3000).cumsum()
    base = (base - base.mean()) / base.std()
    a = base[200:2200]          # A starts 2.0 s into the "room sound"
    b = base[50:2050]           # B starts 0.5 s into it -> events occur 1.5 s later in B... i.e. earlier in A
    r, lag = dataset.envelope_ncc(a, b)
    assert r > 0.99
    assert lag == pytest.approx(-1.5, abs=0.011)


def test_pairing_assignment_and_rejection(monkeypatch, tmp_path):
    rng = np.random.default_rng(1)
    rooms = [rng.normal(size=2500).cumsum() for _ in range(3)]
    env = {"F1": rooms[0][100:1600], "S1": rooms[0][130:1630], "F2": rooms[1][0:1500], "S2": rooms[1][40:1540],
           "F3": rooms[2][0:1500], "S9": rng.normal(size=1500).cumsum()}  # S9 overlaps nothing
    monkeypatch.setattr(dataset, "audio_envelope", lambda p: (env[p] - env[p].mean()) / env[p].std())
    mk = lambda n: dataset.Recording(n, n, 1.0, has_audio=True)  # noqa: E731
    pairs, M = dataset.pair_by_audio([mk("F1"), mk("F2"), mk("F3")], [mk("S1"), mk("S2"), mk("S9")])
    got = {(p.front, p.side) for p in pairs}
    assert ("F1", "S1") in got and ("F2", "S2") in got
    assert not any(p.side == "S9" and p.status == "confident" for p in pairs)
    off = {p.front: p.offset_s for p in pairs}
    assert off["F1"] == pytest.approx(0.30, abs=0.011)


def test_view_from_keypoints():
    k = np.zeros((26, 2))
    k[5], k[6], k[11], k[12] = (100, 100), (160, 100), (105, 200), (155, 200)    # frontal: wide shoulders
    assert dataset.view_from_keypoints(k) > 0.4
    k[5], k[6], k[11], k[12] = (130, 100), (135, 100), (128, 200), (133, 200)    # side-on
    assert dataset.view_from_keypoints(k) < 0.3


def test_target_selection_follows_participant_and_ignores_bystander():
    def person(cx, cy, h):
        k = np.zeros((26, 2))
        k[:, 0] = cx + np.linspace(-0.1, 0.1, 26) * h
        k[:, 1] = cy + np.linspace(-0.5, 0.5, 26) * h
        k[11], k[12] = (cx - 5, cy), (cx + 5, cy)
        return k
    s = np.ones((2, 26))
    kps = np.stack([person(500, 400, 400), person(300, 380, 200)])   # participant (big), bystander (small)
    j = pose_rtm.select_target(kps, s, None, 1920, 1080)
    assert j == 0
    prev = {"hip": np.array([500.0, 400.0]), "h": 400.0}
    kps2 = np.stack([person(320, 380, 200), person(520, 405, 400)])  # order swapped next frame
    assert pose_rtm.select_target(kps2, s, prev, 1920, 1080) == 1
    far = np.stack([person(1500, 400, 400)])                         # implausible jump -> not the target
    assert pose_rtm.select_target(far, np.ones((1, 26)), prev, 1920, 1080) is None


def test_pole_detection_on_rendered_frame():
    img = np.full((1080, 1920, 3), 235, np.uint8)
    cv2.line(img, (1200, 150), (1250, 120), (40, 40, 40), 4)                # handrail-like dark line
    cv2.line(img, (700, 100), (700, 900), (200, 140, 90), 10)               # curtain fold above the hand
    wrist = np.array([1000.0, 400.0])
    tip = wrist + 380 * np.array([np.sin(np.radians(8)), np.cos(np.radians(8))])
    cv2.line(img, tuple(wrist.astype(int)), tuple(tip.astype(int)), (200, 90, 40), 8)   # blue shaft (BGR)
    torso = np.array([[950, 150], [1050, 150], [1050, 350], [950, 350]], float)
    r = pole_auto.detect_in_frame(img, wrist, 600.0, torso, pole_auto.PoleColour())
    assert r is not None
    got_tip, ang, length, conf, method = r
    assert method == "colour"
    assert ang == pytest.approx(8, abs=2)
    # the reported tip includes the dark ferrule below the coloured shaft (fixed fraction, calibrated on real labels)
    expected = wrist + (tip - wrist) * (1 + pole_auto.FERRULE_FRACTION)
    assert np.linalg.norm(got_tip - expected) < 15
    assert conf > 0.5
    # no shaft -> nothing invented
    img2 = np.full((1080, 1920, 3), 235, np.uint8)
    assert pole_auto.detect_in_frame(img2, wrist, 600.0, torso, pole_auto.PoleColour()) is None


def _front_pose(n=60, fps=30.0):
    xy = np.full((n, N_LANDMARKS, 2), np.nan)
    for i, (x, y) in {11: (400, 200), 12: (500, 200), 23: (420, 400), 24: (480, 400), 25: (410, 550),
                      26: (480, 550), 27: (420, 700), 28: (480, 700), 15: (380, 380), 16: (520, 380), 0: (450, 120)}.items():
        xy[:, i] = (x, y)
    xy[:, 25, 0] = 380  # left knee displaced medially/laterally -> nonzero FPPA
    return PoseSeries(np.arange(n) / fps, xy, np.ones((n, N_LANDMARKS)), fps, 900, 800)


def test_frontal_measures_geometry():
    df, metrics, q = frontal.analyse_front(_front_pose(), None, cutoff_hz=0)
    from trailbuddy.core.kinematics import interior_angle
    exp = 180 - interior_angle(np.array([420, 400.]), np.array([380, 550.]), np.array([420, 700.]))
    assert df.front_left_knee_fppa_deg.iloc[10] == pytest.approx(exp, abs=1e-6)
    assert df.front_right_knee_fppa_deg.iloc[10] == pytest.approx(0, abs=1e-6)
    assert df.front_trunk_lateral_lean_deg.iloc[10] == pytest.approx(0, abs=1e-6)
    assert df.front_step_width_ratio.iloc[10] == pytest.approx(60 / 60)
    m = {x.key: x for x in metrics}
    assert m["front_pole_tip_spread_mean"].kind == "unavailable"


def test_visual_clap():
    p = _front_pose(n=150, fps=30)
    d = np.concatenate([np.linspace(140, 2, 40), np.linspace(2, 140, 40), np.full(70, 140)])
    p.xy[:, 15, 0] = 450 - d / 2
    p.xy[:, 16, 0] = 450 + d / 2
    t, conf = sync.visual_clap(p, (0, 5))
    assert t == pytest.approx(39 / 30, abs=1 / 30)
    assert conf > 0.5


def test_despike_removes_isolated_jump_keeps_motion():
    t = np.linspace(0, 2, 120)
    y = 300 + 80 * np.sin(2 * np.pi * t)
    y2 = y.copy()
    y2[50] += 120
    out, mask = despike(y2, floor=20)
    assert mask[50] and mask.sum() == 1
    assert np.isnan(out[50]) and np.allclose(out[~mask], y[~mask])


def test_drift_check_zero_for_shifted_copy():
    rng = np.random.default_rng(2)
    base = rng.normal(size=4000).cumsum()
    a, b = base[300:3300], base[100:3100]     # pure shift of 2.0 s, no drift
    r, lag = dataset.envelope_ncc(a, b)
    d = sync.estimate_drift(a, b, 0.01, lag)
    assert d["drift_ms_per_min"] == pytest.approx(0, abs=1)


def test_kinetics_blocked_without_body_metrics():
    from trailbuddy.core import analysis
    from trailbuddy.core.analysis import AnalysisSettings
    from trailbuddy.core.runner import block_unsupported_kinetics
    from trailbuddy.core.synthetic import synthetic_descent
    p, tr = synthetic_descent(duration=3.0)
    res = analysis.analyse(p, 70, 1.75, AnalysisSettings(load_mode="scenario", side="right"))
    assert res.metric("knee_ext_moment_peak").value is not None
    block_unsupported_kinetics(res)
    for k in ("knee_ext_moment_peak", "quad_force_peak", "knee_neg_work", "speed"):
        assert res.metric(k).kind == "unavailable" and res.metric(k).value is None
    assert res.metric("knee_flexion_peak").value is not None          # kinematics unaffected
    assert not any("moment" in c or "force" in c for c in res.timeseries.columns)


def test_moment_scales_linearly_with_body_mass():
    """Physical consistency: quasi-static knee moment and quad force scale with mass; angles do not."""
    from trailbuddy.core import analysis
    from trailbuddy.core.analysis import AnalysisSettings
    from trailbuddy.core.synthetic import synthetic_descent
    p, tr = synthetic_descent(duration=3.0)
    s = AnalysisSettings(load_mode="scenario", side="right", scale_method="points", scale_m_per_px=tr.scale_m_per_px)
    a = analysis.analyse(p, 60, 1.75, s)
    b = analysis.analyse(p, 90, 1.75, s)
    assert b.metric("quad_force_peak").value == pytest.approx(a.metric("quad_force_peak").value * 1.5, rel=1e-6)
    assert b.metric("knee_ext_moment_peak").value == pytest.approx(a.metric("knee_ext_moment_peak").value, rel=1e-6)
    assert b.metric("knee_flexion_peak").value == pytest.approx(a.metric("knee_flexion_peak").value)
    # halving the calibrated scale (metres per pixel) halves the moment arm and so the moment
    s2 = AnalysisSettings(load_mode="scenario", side="right", scale_method="points", scale_m_per_px=tr.scale_m_per_px / 2)
    c = analysis.analyse(p, 60, 1.75, s2)
    assert c.metric("knee_ext_moment_peak").value == pytest.approx(a.metric("knee_ext_moment_peak").value / 2, rel=1e-6)
