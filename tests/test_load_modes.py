"""Load-analysis modes A/B/C, missing body metrics, and consistency of the pole force between knee and arms."""

import numpy as np
import pytest

from trailbuddy.core import analysis
from trailbuddy.core import dynamics as dyn
from trailbuddy.core.analysis import AnalysisSettings
from trailbuddy.core.anthropometry import G
from trailbuddy.core.pole import PoleTrack
from trailbuddy.core.synthetic import synthetic_descent

LOADS = ("knee_ext_moment_peak", "knee_ext_moment_peak_nm", "quad_force_peak", "elbow_moment_peak",
         "shoulder_moment_peak", "pole_support_fraction")


def run(mass=70.0, height=1.75, poles=True, **kw):
    pose, truth = synthetic_descent(duration=4.0, fps=60, noise_px=0.5, seed=1)
    kw.setdefault("pole_pct_bw", 10.0)
    s = AnalysisSettings(side="right", scale_method="points", scale_m_per_px=truth.scale_m_per_px,
                         pole_force_mode="scenario" if poles else "none", **kw)
    pt = {"right": PoleTrack(pose.t, truth.pole_tip_px)} if poles else None
    return analysis.analyse(pose, mass, height, s, poles, pt)


def test_mode_a_video_only_reports_no_loads_but_keeps_kinematics():
    res = run(load_mode="video")
    for k in LOADS:
        m = res.metric(k)
        assert m.kind == "unavailable" and m.value is None and "Video-only" in m.note
    assert res.metric("knee_flexion_peak").value > 30
    assert not any("moment" in c or "force_n" in c for c in res.timeseries.columns)


def test_missing_mass_blocks_loads_in_scenario_mode():
    res = run(mass=None, load_mode="scenario")
    assert all(res.metric(k).kind == "unavailable" for k in LOADS)
    assert "body mass" in res.metric("knee_ext_moment_peak").note


def test_missing_height_gives_no_metric_scale():
    pose, _ = synthetic_descent(duration=2.0, fps=60, seed=2)
    res = analysis.analyse(pose, 70.0, None, AnalysisSettings(load_mode="scenario", side="right"))
    assert res.quality["scale_m_per_px"] is None
    assert res.metric("speed").kind == "unavailable"


def test_mode_c_without_force_file_is_unavailable_not_scenario():
    res = run(load_mode="measured")
    assert res.metric("knee_ext_moment_peak").kind == "unavailable"
    assert res.metric("pole_support_fraction").kind == "unavailable"


def test_scenario_pole_force_reduces_knee_and_loads_arms_consistently():
    no = run(poles=False, load_mode="scenario")
    lo = run(load_mode="scenario", pole_pct_bw=5.0)
    hi = run(load_mode="scenario", pole_pct_bw=20.0)
    k0, k1, k2 = (r.metric("knee_ext_moment_peak").value for r in (no, lo, hi))
    assert k0 > k1 > k2  # more pole support -> less leg support -> smaller knee moment
    s1, s2 = (r.metric("shoulder_moment_peak").value for r in (lo, hi))
    assert s2 > s1  # ... and more shoulder demand
    m = hi.metric("shoulder_moment_peak")
    assert m.low < m.value < m.high and m.kind == "scenario"
    assert hi.metric("knee_ext_moment_peak_nm").value == pytest.approx(k2 * 70.0)
    assert set(hi.sensitivity["pole_force_pct_bw"].dropna()) == {10.0, 20.0, 30.0}


def test_pole_vertical_component_is_force_times_cos_theta():
    n, th = 5, np.radians(30)
    d = np.tile([np.sin(th), np.cos(th)], (n, 1))  # 30 degrees from vertical
    pl = dyn.scenario_pole_load(n, 70.0, 10.0, {"left": np.ones(n, bool)}, {"left": d})
    assert pl.vertical_total(n) == pytest.approx(np.full(n, 0.10 * 70.0 * G * np.cos(th)))
