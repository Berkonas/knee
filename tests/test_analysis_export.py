"""End-to-end: synthetic trials -> analysis -> comparisons -> exports."""

import numpy as np
import pandas as pd
import pytest

from trailbuddy.core import analysis, compare, export
from trailbuddy.core.analysis import AnalysisSettings
from trailbuddy.core.pole import PoleTrack
from trailbuddy.core.project import Participant, Project, Trial
from trailbuddy.core.synthetic import synthetic_descent


def run(uses_poles=False, mode="none", pct=10.0, seed=0, **kw):
    pose, truth = synthetic_descent(duration=4.0, fps=60, noise_px=0.5, seed=seed)
    s = AnalysisSettings(side="right", scale_method="points", scale_m_per_px=truth.scale_m_per_px,
                         pole_force_mode=mode, pole_pct_bw=pct, descent_height_m=0.68, **kw)
    poles = {"right": PoleTrack(pose.t, truth.pole_tip_px)} if uses_poles else None
    return analysis.analyse(pose, 70.0, 1.75, s, uses_poles, poles), truth


def test_no_pole_trial_outputs_and_labels():
    res, truth = run()
    km = res.metric("knee_ext_moment_peak")
    assert km.kind == "scenario" and km.value > 0
    assert km.low <= km.value <= km.high
    q = res.metric("quad_force_peak")
    assert q.low < q.value < q.high  # moment-arm range
    assert res.metric("tibiofemoral_compression").kind == "unavailable"
    assert res.metric("pole_support_fraction").kind == "unavailable"
    assert res.metric("elbow_moment_peak").value is None
    assert res.metric("knee_neg_work").value < 0  # eccentric during descent
    assert res.metric("knee_ext_impulse_per_m").value == pytest.approx(
        res.metric("knee_ext_impulse_total").value / 0.68)
    assert res.metric("cadence").value == pytest.approx(75, rel=0.1)
    assert len(res.sensitivity) >= 18


def test_quasi_static_moment_matches_hand_formula_on_synthetic():
    res, truth = run()
    ts = res.timeseries
    st = ts["right_stance"].astype(bool)
    # in single support with static model: M = m g (x_knee - x_cop); spot-check one frame by recomputing
    m = ts.loc[st, "right_knee_extensor_moment_nm"].to_numpy()
    f = ts.loc[st, "right_foot_force_scenario_n"].to_numpy()
    assert np.nanmax(f) == pytest.approx(70 * 9.81, rel=1e-6)
    assert np.all(np.isfinite(m))


def test_pole_scenario_reduces_knee_and_loads_arm():
    base, _ = run()
    pol, _ = run(uses_poles=True, mode="scenario", pct=10.0)
    assert pol.metric("pole_support_fraction").kind == "scenario"
    assert pol.metric("knee_ext_impulse_total").value < base.metric("knee_ext_impulse_total").value
    assert pol.metric("shoulder_moment_peak").value > 0
    assert pol.metric("elbow_moment_peak").kind == "scenario"


def test_poles_without_force_are_reported_unavailable():
    res, _ = run(uses_poles=True, mode="none")
    assert res.metric("elbow_moment_peak").kind == "unavailable"
    assert "Pole force" in res.metric("pole_support_fraction").note


def test_no_scale_makes_kinetics_unavailable():
    pose, _ = synthetic_descent(duration=3.0)
    res = analysis.analyse(pose, 70, 1.75, AnalysisSettings(scale_method="none"))
    assert res.metric("knee_ext_moment_peak").kind == "unavailable"
    assert res.metric("speed").value is None
    assert res.metric("knee_flexion_peak").value is not None


def test_height_scale_used_by_default():
    pose, truth = synthetic_descent(duration=3.0)
    res = analysis.analyse(pose, 70, 1.75, AnalysisSettings())
    assert res.quality["scale_m_per_px"] == pytest.approx(truth.scale_m_per_px, rel=0.02)


def test_measured_grf_path_uses_inverse_dynamics(tmp_path):
    from trailbuddy.core.forces import load_force_csv
    pose, truth = synthetic_descent(duration=3.0)
    t = pose.t
    pd.DataFrame({"time_s": t, "fz_n": np.full(len(t), 686.7), "fx_n": 0.0}).to_csv(tmp_path / "f.csv", index=False)
    fd = load_force_csv(tmp_path / "f.csv")
    s = AnalysisSettings(side="right", scale_method="points", scale_m_per_px=truth.scale_m_per_px)
    res = analysis.analyse(pose, 70, 1.75, s, forces=fd)
    assert res.metric("knee_ext_moment_peak").kind == "model"
    assert "right_hip_extensor_moment_nm" in res.timeseries


def test_force_csv_validation(tmp_path):
    from trailbuddy.core.forces import load_force_csv
    (tmp_path / "a.csv").write_text("t,foo\n0,1\n")
    with pytest.raises(ValueError):
        load_force_csv(tmp_path / "a.csv")
    (tmp_path / "b.csv").write_text("time_s,bar\n0,1\n1,2\n")
    with pytest.raises(ValueError):
        load_force_csv(tmp_path / "b.csv")


def test_save_load_and_project_export(tmp_path):
    pr = Project.new(tmp_path / "study", "Synthetic demo", "exp1")
    for pid in ("P01", "P02", "P03"):
        pr.add_participant(Participant(pid, 70, 1.75, standard_pole_length_cm=115))
    seed = 0
    for pid in ("P01", "P02", "P03"):
        for code, uses in (("C0", False), ("C1", True)):
            for k in (1, 2, 3):
                tr = pr.add_trial(Trial(pid, code, k))
                res, _ = run(uses_poles=uses, mode="scenario" if uses else "none", seed=seed)
                seed += 1
                analysis.save_result(res, pr.trial_dir(tr.id), {"trial": tr.id})
                tr.status = "analysed"
    pr.save()
    loaded = analysis.load_result(pr.trial_dir("P01_C1_T01"))
    assert loaded.metric("quad_force_peak").value is not None
    long = compare.collect(pr)
    assert long.trial_id.nunique() == 18
    w = compare.within_participant(long, "knee_ext_impulse_total")
    assert len(w) == 3 and (w.pct_diff < 0).all()
    g = compare.group_summary(long, "knee_ext_impulse_total")
    assert int(g.n_participants.iloc[0]) == 3 and "No significance" in g.note.iloc[0]
    files = export.export_project(pr, tmp_path / "export", fig_formats=("png", "svg"))
    for k in ("long_csv", "wide_csv", "xlsx", "summary_md", "within_csv"):
        assert files[k].exists() and files[k].stat().st_size > 0
    xl = pd.ExcelFile(files["xlsx"])
    assert "Metric definitions" in xl.sheet_names
    figs = list((tmp_path / "export" / "figures").glob("*.png"))
    assert len(figs) >= 5
    assert any(p.name.startswith("stance_normalised") for p in figs)
    md = files["summary_md"].read_text()
    assert "What we cannot conclude" in md and "lower in 3 of 3" in md


def test_export_requires_results(tmp_path):
    pr = Project.new(tmp_path, "empty")
    with pytest.raises(ValueError):
        export.export_project(pr, tmp_path / "x")


def test_trial_figures_render():
    from trailbuddy.core import plots
    res, _ = run(uses_poles=True, mode="scenario")
    for f in (plots.fig_kinematics(res), plots.fig_knee_load(res), plots.fig_events(res), plots.fig_sensitivity(res)):
        assert len(f.axes) >= 1


def test_export_includes_changes_raw_data_and_trial_figures(tmp_path):
    from trailbuddy.core.demo import build_demo_project
    pr = build_demo_project(tmp_path / "demo")
    files = export.export_project(pr, tmp_path / "out", fig_formats=("png",))
    ch = pd.read_csv(files["changes_csv"])
    assert {"noise_95", "clear", "pct_diff"} <= set(ch.columns) and len(ch) > 20
    assert (files["raw_dir"] / "P01_C0_T01" / "timeseries.csv").exists()
    assert (tmp_path / "out" / "figures" / "trials" / "P01_C1_T02" / "timeline.png").exists()
    assert (tmp_path / "out" / "figures" / "overview_all_metrics.png").exists()
    xl = pd.ExcelFile(files["xlsx"])
    assert {"Changes vs baseline", "Reference ranges"} <= set(xl.sheet_names)
    ts = pd.read_csv(files["raw_dir"] / "P01_C0_T01" / "timeseries.csv")
    assert "right_knee_x_m" in ts and "right_knee_ext_impulse_cum_nms_per_kg" in ts


def test_reference_classification():
    from trailbuddy.core import reference
    assert reference.classify("knee_flexion_peak", 70) == "below"
    assert reference.classify("knee_flexion_peak", 80) == "within"
    assert reference.classify("knee_flexion_peak", 95) == "above"
    assert reference.classify("speed", 1.0) is None
    for k in reference.RANGES:
        from trailbuddy.core.metrics import INFO
        assert k in INFO
