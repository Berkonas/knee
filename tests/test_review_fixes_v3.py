"""Regression tests for the version-3 specialist review findings."""

import json

import numpy as np
import pandas as pd
import pytest

from trailbuddy.core import analysis, compare
from trailbuddy.core.analysis import AnalysisSettings
from trailbuddy.core.pipeline import exact_times
from trailbuddy.core.pole import PoleTrack
from trailbuddy.core.project import CameraVideo, Participant, Project, Trial
from trailbuddy.core.synthetic import synthetic_descent


def study(tmp_path):
    pr = Project.new(tmp_path / "s", "s", "exp2")
    pr.add_participant(Participant("P01", 70, 1.75, standard_pole_length_cm=120))
    pr.add_trial(Trial("P01", "C0", 1))
    pr.add_trial(Trial("P01", "C1", 1))
    pr.save()
    (pr.trial_dir("P01_C0_T01") / "summary.csv").write_text("x")
    return pr


def test_cached_times_snap_to_frames():
    fps = 59.96
    t = np.round(np.arange(500) / fps, 2)
    snapped = exact_times(t, fps)
    assert np.allclose(np.diff(snapped), 1 / fps)


def test_rename_onto_existing_folder_changes_nothing(tmp_path):
    pr = study(tmp_path)
    (pr.root / "trials" / "P01_C2_T01").mkdir()
    with pytest.raises(ValueError):
        pr.rename_trial("P01_C0_T01", "C2")
    assert pr.trial("P01_C0_T01").condition_code == "C0"
    assert (pr.root / "trials" / "P01_C0_T01" / "summary.csv").exists()


def test_rename_condition_marks_results_stale_and_sets_pole_length(tmp_path):
    pr = study(tmp_path)
    pr.trial("P01_C0_T01").status = "analysed"
    t = pr.rename_trial("P01_C0_T01", "C3")
    assert t.status == "new" and t.pole_length_cm == 125.0


def test_restore_refuses_existing_results_folder(tmp_path):
    pr = study(tmp_path)
    pr.delete_trials(["P01_C0_T01"])
    (pr.root / "trials" / "P01_C0_T01").mkdir(parents=True)
    with pytest.raises(ValueError):
        pr.restore_trial(pr.deleted_trials()[0][0])
    assert "P01_C0_T01" not in [t.id for t in pr.trials]


def test_clear_cache_matches_dotted_stems(tmp_path):
    pr = study(tmp_path)
    pr.trial("P01_C1_T01").videos.append(CameraVideo("/x/IMG.trim.mov"))
    (pr.root / "cache").mkdir()
    (pr.root / "cache" / "IMG.trim.acc.pose.csv").write_text("x")
    assert pr.clear_cache(["P01_C1_T01"]) == 1


def test_paths_saved_relative_to_study(tmp_path):
    pr = study(tmp_path)
    v = tmp_path / "Videos" / "a.mov"
    v.parent.mkdir()
    v.write_bytes(b"x")
    pr.trial("P01_C1_T01").videos.append(CameraVideo(str(v)))
    pr.save()
    stored = json.loads((pr.root / "project.json").read_text())["trials"][1]["videos"][0]["path"]
    assert stored == "../Videos/a.mov"
    assert Project.load(pr.root).trial("P01_C1_T01").videos[0].path == str(v.resolve())


def test_backups_not_overwritten_within_a_second(tmp_path):
    pr = study(tmp_path)
    n0 = len(list((pr.root / "backups").glob("*.json")))
    for _ in range(3):
        pr.save()
    assert len(list((pr.root / "backups").glob("*.json"))) >= n0 + 2


def test_terrains_are_never_pooled_in_comparisons():
    rows = [{"participant": "P01", "task": task, "condition": c, "metric": "knee_ext_moment_peak", "value": v,
             "trial_id": f"{task}{c}{k}"}
            for task, base in (("stair_descent", 1.5), ("level_walk", 0.5))
            for c, f in (("C0", 1.0), ("C1", 0.8)) for k, v in enumerate((base * f - 0.01, base * f + 0.01))]
    w = compare.within_participant(pd.DataFrame(rows), "knee_ext_moment_peak", "C0").set_index("task")
    assert w.loc["stair_descent", "pct_diff"] == pytest.approx(-20) and w.loc["level_walk", "pct_diff"] == pytest.approx(-20)


def test_arm_range_is_per_pole_force_scale_and_blocked_metrics_listed():
    pose, truth = synthetic_descent(duration=4.0, fps=60, noise_px=0.5, seed=1)
    s = AnalysisSettings(load_mode="scenario", side="right", scale_method="points",
                         scale_m_per_px=truth.scale_m_per_px, pole_force_mode="scenario", pole_pct_bw=10)
    res = analysis.analyse(pose, 70.0, 1.75, s, True, {"right": PoleTrack(pose.t, truth.pole_tip_px)})
    m = res.metric("shoulder_moment_peak")
    assert m.low < m.value < m.high
    blocked = analysis.analyse(pose, None, 1.75, s, True, {"right": PoleTrack(pose.t, truth.pole_tip_px)})
    assert blocked.metric("knee_ext_impulse_per_step").kind == "unavailable"
    sens = res.sensitivity
    nominal = res.metric("knee_ext_moment_peak")
    assert sens.peak_knee_moment_nm_per_kg.min() <= nominal.value <= sens.peak_knee_moment_nm_per_kg.max()
