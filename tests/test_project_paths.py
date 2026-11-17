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
