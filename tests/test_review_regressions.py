"""Regression tests for issues found in the independent biomechanics review."""

import numpy as np
import pandas as pd
import pytest

from trailbuddy.core import analysis, dynamics as dyn, sync
from trailbuddy.core.analysis import AnalysisSettings
from trailbuddy.core.events import ContactInterval, GaitEvents
from trailbuddy.core.kinematics import Kinematics
from trailbuddy.core.landmarks import idx
from trailbuddy.core.synthetic import synthetic_descent


def far_side_hidden(seed=0):
    pose, truth = synthetic_descent(duration=4.0, fps=60, seed=seed)
    for nm in ("shoulder", "elbow", "wrist", "index", "hip", "knee", "ankle", "heel", "foot_index"):
        pose.visibility[:, idx("left", nm)] = 0.3
    return pose, truth


def test_dynamic_support_with_hidden_far_side_is_not_zero():
    pose, truth = far_side_hidden()
    s = AnalysisSettings(side="right", scale_method="points", scale_m_per_px=truth.scale_m_per_px,
                         support_model="dynamic")
    res = analysis.analyse(pose, 70, 1.75, s)
    pk = res.metric("knee_ext_moment_peak")
    assert pk.value is not None and pk.value > 0.5
    assert res.metric("knee_ext_impulse_total").value > 0
    assert pk.low > 0.5  # dynamic sensitivity rows no longer collapse to zero


def test_hidden_contralateral_foot_is_flagged():
    pose, truth = far_side_hidden()
    s = AnalysisSettings(side="right", scale_method="points", scale_m_per_px=truth.scale_m_per_px)
    res = analysis.analyse(pose, 70, 1.75, s)
    assert res.quality.get("double_support_unknown") is True
    assert any("upper bound" in n for n in res.notes)


def test_resample_does_not_bridge_long_gaps():
    t = np.arange(0, 3, 1 / 30)
    y = np.sin(t)
    y[30:60] = np.nan  # 1 s dropout
    out = sync.resample_to(t, y, np.arange(0, 3, 1 / 60))
    t60 = np.arange(0, 3, 1 / 60)
    assert np.isnan(out[(t60 > 1.05) & (t60 < 1.95)]).all()
    assert np.isfinite(out[(t60 > 0.1) & (t60 < 0.9)]).all()


def test_step_times_exclude_contact_truncated_at_clip_start():
    g = GaitEvents({"right": [ContactInterval(0.0, 0.4, 0, 24), ContactInterval(1.3, 1.9, 78, 114)],
                    "left": [ContactInterval(0.5, 1.1, 30, 66)]}, n_frames=200)
    assert g.step_times() == pytest.approx([0.8])


def test_grip_point_used_for_arm_lever():
    n = 3
    pts = {"right_shoulder": np.tile([0.0, 1.4], (n, 1)), "right_elbow": np.tile([0.0, 1.1], (n, 1)),
           "right_wrist": np.tile([0.25, 1.1], (n, 1)), "right_index": np.tile([0.41, 1.1], (n, 1))}
    kin = Kinematics(np.arange(n) / 60, 60, pts, {}, "m", 1.0, 1)
    am = dyn.arm_moments(kin, "right", 70, np.tile([0.0, 100.0], (n, 1)), include_segment_weight=False)
    assert am.elbow[0] == pytest.approx(100 * 0.33)  # lever to grip (wrist + half of wrist->index)


def test_force_channels_are_filtered_before_resampling(tmp_path):
    from trailbuddy.core.forces import load_force_csv
    t = np.arange(0, 2, 0.001)
    fz = 700 + 300 * np.sin(2 * np.pi * 80 * t)  # 80 Hz content far above the 6 Hz cut-off
    pd.DataFrame({"time_s": t, "fz_n": fz}).to_csv(tmp_path / "f.csv", index=False)
    fd = load_force_csv(tmp_path / "f.csv")
    out = fd.resample(np.arange(0.2, 1.8, 1 / 60), 0.0, cutoff_hz=6.0)["vertical"]
    assert np.max(np.abs(out - 700)) < 15


def test_fy_column_is_not_taken_as_vertical(tmp_path):
    from trailbuddy.core.forces import load_force_csv
    pd.DataFrame({"time_s": [0, 1], "fy_n": [1, 2]}).to_csv(tmp_path / "f.csv", index=False)
    with pytest.raises(ValueError):
        load_force_csv(tmp_path / "f.csv")


def test_force_plate_only_applied_during_analysed_stance(tmp_path):
    from trailbuddy.core.forces import load_force_csv
    pose, truth = synthetic_descent(duration=3.0)
    pd.DataFrame({"time_s": pose.t, "fz_n": 686.7}).to_csv(tmp_path / "f.csv", index=False)
    s = AnalysisSettings(side="right", scale_method="points", scale_m_per_px=truth.scale_m_per_px)
    res = analysis.analyse(pose, 70, 1.75, s, forces=load_force_csv(tmp_path / "f.csv"))
    ts = res.timeseries
    assert (ts.loc[ts.right_stance == 0, "grf_vertical_n"] == 0).all()
    assert any("another foot" in n for n in res.notes)
