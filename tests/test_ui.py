"""GUI tests (offscreen) for the v2 workspace: browser, synchronised videos, sync tools, analysis,
linked plots, export, import dialog, study and compare pages, appearance switch."""

import numpy as np
import pytest

pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QMessageBox  # noqa: E402

from trailbuddy.core import pipeline, video  # noqa: E402
from trailbuddy.core.demo import build_demo_project  # noqa: E402
from trailbuddy.core.landmarks import PoseSeries  # noqa: E402
from trailbuddy.core.pole import PoleTrack  # noqa: E402
from trailbuddy.core.project import CameraVideo, Participant, Project, Trial  # noqa: E402
from trailbuddy.core.synthetic import clap_audio, render_frames, synthetic_descent  # noqa: E402
from trailbuddy.ui.main_window import MainWindow  # noqa: E402
from trailbuddy.ui.state import AppState  # noqa: E402


@pytest.fixture
def no_dialogs(monkeypatch):
    shown = []
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: shown.append(a[1:3]))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr("trailbuddy.ui.results_page.open_folder", lambda p: None)
    return shown


@pytest.fixture
def win(qtbot, no_dialogs):
    w = MainWindow(AppState())
    qtbot.addWidget(w)
    w.show()
    return w


def make_pair(tmp_path, clap_side=1.0, clap_front=0.4):
    ps, truth = synthetic_descent(duration=3.0, fps=60, width=640, img_height=480, px_per_m=200, seed=1)
    pf, _ = synthetic_descent(duration=3.0, fps=30, width=640, img_height=480, px_per_m=200, seed=2)
    vs = video.write_video(render_frames(ps, truth.pole_tip_px), tmp_path / "side.mp4", 60,
                           clap_audio(3.0, [clap_side], 16000, seed=3), 16000)
    vf = video.write_video(render_frames(pf), tmp_path / "front.mp4", 30, clap_audio(3.0, [clap_front], 16000, seed=4), 16000)
    return vs, vf, ps, pf, truth


@pytest.fixture
def study(tmp_path, monkeypatch):
    vs, vf, ps, pf, truth = make_pair(tmp_path)
    pr = Project.new(tmp_path / "study", "Test study", "exp1")
    pr.add_participant(Participant("P01", 70, 1.75, standard_pole_length_cm=115))
    pr.add_trial(Trial("P01", "C1", 1, [CameraVideo(str(vs), "side", "Side", {"fps": 60, "duration_s": 3}),
                                        CameraVideo(str(vf), "front", "Front", {"fps": 30, "duration_s": 3})]))
    pr.save()

    def fake_process(path, cache, settings=None, progress=None, cancelled=None):
        pose = ps if str(path).endswith("side.mp4") else pf
        pose = PoseSeries(pose.t, pose.xy, pose.visibility, pose.fps, pose.width, pose.height, str(path), {"stride": 1})
        poles = {"right": PoleTrack(pose.t, truth.pole_tip_px if pose.fps == 60 else np.full((pose.n_frames, 2), np.nan))}
        if progress:
            progress(1.0, "done")
        return pose, poles, {}
    monkeypatch.setattr(pipeline, "process_recording", fake_process)
    monkeypatch.setattr(pipeline, "load_cached", lambda cache, v, s: fake_process(v, cache))
    return pr


def test_modes_and_empty_states(win):
    for i in range(4):
        win.mode.set_index(i)
        assert win.stack.currentIndex() == i
    ws = win.pages["workspace"]
    assert ws.browser.tree.topLevelItemCount() == 0
    assert not win.pages["results"].btn_export.isEnabled()


def test_workspace_open_sync_analyse_export(win, study, qtbot, tmp_path, no_dialogs, monkeypatch):
    win.state.set_project(study)
    ws = win.pages["workspace"]
    assert ws.browser.tree.topLevelItemCount() == 1
    ws.browser.select_trial("P01_C1_T01")
    assert ws.trial.id == "P01_C1_T01" and set(ws.video.sources) == {"side", "front"}
    # synchronised mapping: front time = side time - offset
    ws._apply_offset(0.6, "test")
    ws.video.seek(1.5, force=True)
    assert ws.video.view_time("front") == pytest.approx(0.9)
    assert ws.video.sources["front"].last_index == 27   # 0.9 s at 30 fps
    # frame-level manual nudge
    ws.inspector.btn_p1.click()
    assert ws.trial.sync["offset_s"] == pytest.approx(0.6 + 1 / 60, abs=1e-4)
    # audio clap sync recovers the known offset (side clap 1.0 s, front clap 0.4 s -> +0.6 s)
    ws.sync_audio()
    assert ws.trial.sync["offset_s"] == pytest.approx(0.6, abs=0.01)
    # playback controls
    ws.video.step(1)
    t1 = ws.video.t
    ws.video.step(-10)
    assert ws.video.t == pytest.approx(max(0, t1 - 10 / 60))
    ws.video.speed_box.setCurrentIndex(4)
    ws.video.toggle_play(); qtbot.wait(120); ws.video.stop()
    # interval from the cursor
    ws.video.seek(0.7, force=True); ws.inspector.btn_in.click()
    ws.video.seek(2.4, force=True); ws.inspector.btn_out.click()
    assert ws.trial.interval == pytest.approx([0.7, 2.4], abs=1e-6)
    # analysis (tracking patched with synthetic landmarks)
    ws.form.pole_mode.setCurrentIndex(ws.form.pole_mode.findData("scenario"))
    ws.run()
    qtbot.waitUntil(lambda: ws.inspector.btn_run.isEnabled(), timeout=60000)
    assert ws.res is not None, no_dialogs
    assert ws.inspector.summary.rowCount() > 20
    assert any(m.view == "front" and m.value is not None for m in ws.res.metrics)
    assert "front_left_knee_fppa_deg" in ws.res.timeseries
    # linked plots: clicking a plot time moves the video; moving the video moves the plot cursor
    ws.plots.seek.emit(1.2)
    assert ws.video.t == pytest.approx(1.2)
    assert ws.plots.cursor.value() == pytest.approx(1.2)
    assert ws.inspector.live.rowCount() > 5
    for i in range(ws.plots.group.count()):
        ws.plots.group.setCurrentIndex(i)
    # visual clap needs poses in both views (patched cache provides them)
    ws.sync_visual()
    # exports (annotated video skipped: no real cache)
    monkeypatch.setattr("trailbuddy.ui.workspace.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path / "exp"))
    ws.export_trial()
    out = tmp_path / "exp" / "P01" / "P01_C1_T01"
    for f in ("timeseries.csv", "summary.csv", "events.csv", "processing_settings.json", "timeline.png"):
        assert (out / f).exists(), f
    assert (out / "P01_C1_T01_annotated.mp4").exists()


def test_import_dialog_with_patched_detector(win, tmp_path, no_dialogs, monkeypatch, qtbot):
    from trailbuddy.core import dataset, importer
    from trailbuddy.core.dataset import PairSuggestion, Recording
    folder = tmp_path / "rec"
    folder.mkdir()
    vs, vf, *_ = make_pair(folder)
    pr = Project.new(tmp_path / "s2", "Import test")
    win.state.set_project(pr)

    def fake_organise(path, n, progress=None, cancelled=None):
        recs = [dataset.read_metadata(vs), dataset.read_metadata(vf)]
        recs[0].view, recs[1].view = "side", "front"
        pairs = [PairSuggestion(recs[1].name, recs[0].name, 0.9, 0.3, -0.6, "confident")]
        return {"recordings": recs, "pairs": pairs, "groups": {recs[0].name: "P01", recs[1].name: "P01"}}
    monkeypatch.setattr(importer, "organise", fake_organise)
    from trailbuddy.ui.import_dialog import ImportDialog
    dlg = ImportDialog(win, win.state, str(folder))
    dlg._scan()
    qtbot.waitUntil(lambda: dlg.btn_apply.isEnabled(), timeout=20000)
    assert dlg.table.rowCount() == 2
    dlg._apply()
    assert len(pr.trials) == 1 and len(pr.trials[0].videos) == 2
    assert pr.trials[0].sync["offset_s"] == pytest.approx(0.6)
    assert not pr.participant("P01").metrics_entered
    del Recording


def test_compare_page_and_appearance(win, tmp_path):
    win.state.set_project(build_demo_project(tmp_path / "demo"))
    rp = win.pages["results"]
    assert rp.btn_export.isEnabled()
    for v in range(len(rp.view.buttons)):
        rp.view.set_index(v)
    win.set_appearance("dark")
    from trailbuddy.ui import theme
    assert theme.mode() == "dark"
    win.set_appearance("light")
    assert theme.mode() == "light"


def test_study_page_validation(win, tmp_path, no_dialogs):
    pr = Project.new(tmp_path / "s", "t")
    win.state.set_project(pr)
    pp = win.pages["project"]
    pr.add_participant(Participant("P01", 70, 1.75))
    win.state.trialsChanged.emit()
    assert pp.ptable.rowCount() == 1
    pp.ptable.selectRow(0)
    pr.trials.append(Trial("P01", "C0", 1))
    pp.remove_participant()
    assert len(pr.participants) == 1 and no_dialogs
