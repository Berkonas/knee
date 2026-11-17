"""Studies must find their videos whatever the app's working folder is (packaged apps start in /)."""

import json
from pathlib import Path

from trailbuddy.core.project import Project, resolve_video_path


def test_relative_video_path_resolves_from_study_parents(tmp_path, monkeypatch):
    (tmp_path / "Videos").mkdir()
    (tmp_path / "Videos" / "a.mov").write_bytes(b"x")
    study = tmp_path / "studies" / "s"
    pr = Project.new(study, "s")
    pr.save()
    d = json.loads((study / "project.json").read_text())
    d["trials"] = [{"participant_id": "P01", "condition_code": "C0", "trial_number": 1,
                    "videos": [{"path": "Videos/a.mov", "role": "side"}]}]
    (study / "project.json").write_text(json.dumps(d))
    monkeypatch.chdir("/")
    loaded = Project.load(study)
    assert Path(loaded.trials[0].videos[0].path) == (tmp_path / "Videos" / "a.mov").resolve()


def test_absolute_and_missing_paths_are_kept(tmp_path):
    assert resolve_video_path("/x/y.mov", tmp_path) == "/x/y.mov"
    assert resolve_video_path("nowhere/z.mov", tmp_path) == "nowhere/z.mov"


def _study(tmp_path):
    from trailbuddy.core.project import Participant, Trial
    pr = Project.new(tmp_path / "s", "s", "exp2")
    pr.add_participant(Participant("P01", 70, 1.75))
    for k in (1, 2):
        pr.add_trial(Trial("P01", "C1", k))
    pr.save()
    (pr.trial_dir("P01_C1_T01") / "summary.csv").write_text("x")
    return pr


def test_schema1_placeholder_metrics_become_missing(tmp_path):
    pr = _study(tmp_path)
    d = json.loads((pr.root / "project.json").read_text())
    d["participants"][0].update(body_mass_kg=70.0, height_m=1.7, metrics_entered=False)
    d["participants"][0]["future_field"] = 1  # written by a newer version: ignored
    (pr.root / "project.json").write_text(json.dumps(d))
    p = Project.load(pr.root).participant("P01")
    assert p.body_mass_kg is None and p.height_m is None and not p.metrics_entered
    assert p.missing() == ["body mass", "height"]


def test_delete_restore_trials_keeps_results_and_never_touches_videos(tmp_path):
    pr = _study(tmp_path)
    video = tmp_path / "v.mov"
    video.write_bytes(b"v")
    from trailbuddy.core.project import CameraVideo
    pr.trial("P01_C1_T01").videos.append(CameraVideo(str(video)))
    pr.delete_trials(["P01_C1_T01", "P01_C1_T02"])
    assert pr.trials == [] and video.exists()
    assert not (pr.root / "trials" / "P01_C1_T01").exists()
    entries = pr.deleted_trials()
    assert {tid for _, tid in entries} == {"P01_C1_T01", "P01_C1_T02"}
    t1 = next(e for e, tid in entries if tid == "P01_C1_T01")
    pr.restore_trial(t1)
    assert (pr.root / "trials" / "P01_C1_T01" / "summary.csv").exists()
    assert Project.load(pr.root).trial("P01_C1_T01").videos[0].path == str(video)


def test_rename_duplicate_and_backups(tmp_path):
    pr = _study(tmp_path)
    pr.rename_trial("P01_C1_T01", condition_code="C2")
    assert (pr.root / "trials" / "P01_C2_T01" / "summary.csv").exists()
    import pytest
    with pytest.raises(KeyError):
        pr.rename_trial("P01_C2_T01", condition_code="C9")
    dup = pr.duplicate_trial("P01_C1_T02")
    assert dup.id == "P01_C1_T03" and dup.status == "new"
    assert len(list((pr.root / "backups").glob("project-*.json"))) >= 1


def test_clear_cache_only_for_selected_trials(tmp_path):
    from trailbuddy.core.project import CameraVideo
    pr = _study(tmp_path)
    pr.trial("P01_C1_T01").videos.append(CameraVideo("/x/A.mov"))
    pr.trial("P01_C1_T02").videos.append(CameraVideo("/x/B.mov"))
    c = pr.root / "cache"
    c.mkdir()
    for n in ("A.bal.pose.csv", "A.bal.json", "B.bal.pose.csv"):
        (c / n).write_text("x")
    assert pr.clear_cache(["P01_C1_T01"]) == 2 and (c / "B.bal.pose.csv").exists()
    assert pr.clear_cache() == 1
