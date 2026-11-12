"""GUI tests (offscreen): every main control is exercised on synthetic data."""

import numpy as np
import pytest

pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QMessageBox  # noqa: E402

from trailbuddy.core import video  # noqa: E402
from trailbuddy.core.demo import build_demo_project  # noqa: E402
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
    monkeypatch.setattr("trailbuddy.ui.single_page.open_folder", lambda p: None)
    monkeypatch.setattr("trailbuddy.ui.results_page.open_folder", lambda p: None)
    return shown


@pytest.fixture
def win(qtbot, no_dialogs):
    st = AppState()
    w = MainWindow(st)
    qtbot.addWidget(w)
    w.show()
    return w


def test_navigation_and_empty_states(win):
    for i in range(5):
        win.nav.setCurrentRow(i)
        assert win.stack.currentIndex() == i
    assert not win.pages["results"].btn_export.isEnabled()
    assert not win.pages["single"].btn_run.isEnabled()
    assert not win.pages["project"].btn_padd.isEnabled()


def test_demo_project_results_and_export(win, tmp_path, monkeypatch):
    win.state.set_project(build_demo_project(tmp_path / "demo"))
    rp = win.pages["results"]
    assert rp.btn_export.isEnabled()
    assert rp.t_within.rowCount() == 3
    for i in range(rp.metric.count()):
        rp.metric.setCurrentIndex(i)  # every metric renders without error
    rp.metric.setCurrentIndex(rp.metric.findData("knee_ext_impulse_total"))
    assert rp.t_group.rowCount() == 1
    monkeypatch.setattr("trailbuddy.ui.results_page.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path / "exp"))
    (tmp_path / "exp").mkdir()
    rp.export()
    assert (tmp_path / "exp" / "trailbuddy_results.xlsx").exists()
    assert (tmp_path / "exp" / "analysis_summary.md").exists()
    pp = win.pages["project"]
    assert pp.ttable.rowCount() == 18 and pp.ptable.rowCount() == 3


def test_project_page_participant_and_condition_validation(win, tmp_path, no_dialogs):
    pr = Project.new(tmp_path / "s", "t")
    win.state.set_project(pr)
    pp = win.pages["project"]
    pr.add_participant(Participant("P01", 70, 1.75))
    win.state.trialsChanged.emit()
    assert pp.ptable.rowCount() == 1
    pp.ptable.selectRow(0)
    pr.trials.append(Trial("P01", "C0", 1))
    pp.remove_participant()  # blocked: has trials
    assert len(pr.participants) == 1 and no_dialogs


def _make_video(path, fps, clap_t, seed=0, marker=True):
    pose, truth = synthetic_descent(duration=3.0, fps=fps, width=640, img_height=480, px_per_m=200, seed=seed)
    return video.write_video(render_frames(pose, truth.pole_tip_px if marker else None), path, fps,
                             clap_audio(3.0, [clap_t], 16000, seed=seed + 3), 16000), truth


def test_single_camera_controls(win, tmp_path, qtbot, no_dialogs):
    v, truth = _make_video(tmp_path / "P01_C1_T01.mp4", 30, 0.5)
    pr = Project.new(tmp_path / "s", "t")
    pr.add_participant(Participant("P01", 70, 1.75, standard_pole_length_cm=115))
    pr.add_trial(Trial("P01", "C1", 1, [CameraVideo(str(v))]))
    pr.save()
    win.state.set_project(pr)
    win.state.openTrial.emit("P01_C1_T01", "single")
    sp = win.pages["single"]
    assert sp.trial.id == "P01_C1_T01" and sp.player.reader is not None
    p = sp.player
    p.btn_next.click(); assert p.index == 1
    p.btn_prev.click(); assert p.index == 0
    p.seek(10); p.btn_in.click(); p.seek(60); p.btn_out.click()
    assert p.interval_s() == pytest.approx((10 / 30, 60 / 30))
    p.btn_play.setChecked(True); qtbot.wait(150); p.btn_play.setChecked(False)
    assert p.index > 60
    # scale by two clicked points
    sp.form.scale_method.setCurrentIndex(sp.form.scale_method.findData("points"))
    sp.form.btn_pick_scale.setChecked(True)
    sp.form.scale_dist.setValue(1.0)
    sp._clicked(100, 100); sp._clicked(300, 100)
    assert sp.form.scale_m_per_px() == pytest.approx(1 / 200)
    assert not sp.form.btn_pick_scale.isChecked()
    # pole: pick marker colour on the rendered tip, then track
    p.seek(10)
    sp.poles.btn_pick.setChecked(True)
    tx, ty = truth.pole_tip_px[10]
    sp._clicked(tx, ty)
    assert sp.poles.btn_track.isEnabled()
    sp.poles.btn_track.click()
    assert sp.poles.tracks["right"].coverage() > 0.95
    # manual annotation
    sp.poles.pole.setCurrentIndex(1)  # left pole
    sp.poles.btn_annot.setChecked(True)
    sp._clicked(50, 60)
    assert sp.poles.annotations.points["left"]["tip"][p.index] == (50, 60)
    sp.poles.btn_clear.click()
    assert p.index not in sp.poles.annotations.points["left"]["tip"]
    # trimmed clip (non-destructive)
    sp.btn_clip.click()
    clips = list(pr.trial_dir("P01_C1_T01").glob("*_clip_*.mp4"))
    assert len(clips) == 1
    # overlay requires analysis first -> friendly message
    sp._save_overlay()
    assert any("Run the analysis first" in str(m) for m in no_dialogs)


def test_single_camera_run_reports_no_person(win, tmp_path, qtbot, no_dialogs, monkeypatch):
    """The stick figure is not a person: pose finds nothing and the user gets a clear error."""
    v, _ = _make_video(tmp_path / "P01_C0_T01.mp4", 30, 0.5, marker=False)
    pr = Project.new(tmp_path / "s", "t")
    pr.add_participant(Participant("P01", 70, 1.75))
    pr.add_trial(Trial("P01", "C0", 1, [CameraVideo(str(v))]))
    win.state.set_project(pr)
    win.state.openTrial.emit("P01_C0_T01", "single")
    sp = win.pages["single"]
    from trailbuddy.core import pose as pose_mod
    from trailbuddy.core.landmarks import N_LANDMARKS, PoseSeries

    def fake_estimate(video_path, f0, f1, variant, progress=None, cancelled=None):
        n = f1 - f0
        return PoseSeries(np.arange(f0, f1) / 30, np.full((n, N_LANDMARKS, 2), np.nan), np.zeros((n, N_LANDMARKS)),
                          30, 640, 480, str(video_path))
    monkeypatch.setattr(pose_mod, "estimate", fake_estimate)
    sp.btn_run.click()
    qtbot.waitUntil(lambda: sp.btn_run.isEnabled(), timeout=20000)
    assert any("legs not detected" in str(m) or "Analysis failed" in str(m) for m in no_dialogs)


def test_single_camera_full_run_with_injected_pose(win, tmp_path, qtbot, no_dialogs, monkeypatch):
    """Full GUI run using synthetic landmarks in place of MediaPipe (which cannot see a stick figure)."""
    v, truth = _make_video(tmp_path / "P01_C1_T01.mp4", 30, 0.5)
    pr = Project.new(tmp_path / "s", "t")
    pr.add_participant(Participant("P01", 70, 1.75))
    pr.add_trial(Trial("P01", "C1", 1, [CameraVideo(str(v))]))
    win.state.set_project(pr)
    win.state.openTrial.emit("P01_C1_T01", "single")
    sp = win.pages["single"]
    from trailbuddy.core import pose as pose_mod
    full, _ = synthetic_descent(duration=3.0, fps=30, width=640, img_height=480, px_per_m=200)

    def fake_estimate(video_path, f0, f1, variant, progress=None, cancelled=None):
        from trailbuddy.core.landmarks import PoseSeries
        progress and progress(1.0)
        return PoseSeries(full.t[f0:f1], full.xy[f0:f1], full.visibility[f0:f1], 30, 640, 480, str(video_path))
    monkeypatch.setattr(pose_mod, "estimate", fake_estimate)
    sp.form.pole_mode.setCurrentIndex(sp.form.pole_mode.findData("scenario"))
    sp.btn_run.click()
    qtbot.waitUntil(lambda: sp.btn_run.isEnabled(), timeout=30000)
    res = sp.results.result
    assert res is not None, no_dialogs
    assert res.metric("quad_force_peak").value > 0
    assert sp.results.table.rowCount() == len(res.metrics)
    assert pr.trial("P01_C1_T01").status == "analysed"
    assert (pr.trial_dir("P01_C1_T01") / "timeseries.csv").exists()
    for i in range(sp.results.tabs.count()):
        sp.results.tabs.setCurrentIndex(i)
    monkeypatch.setattr("trailbuddy.ui.single_page.QFileDialog.getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "ov.mp4"), ""))
    sp._save_overlay()
    assert (tmp_path / "ov.mp4").exists()


def test_two_camera_sync_controls(win, tmp_path, qtbot, no_dialogs):
    va, _ = _make_video(tmp_path / "A.mp4", 60, 1.0, seed=1)
    vb, _ = _make_video(tmp_path / "B.mp4", 30, 0.4, seed=2)
    pr = Project.new(tmp_path / "s", "t")
    pr.add_participant(Participant("P01", 70, 1.75))
    pr.add_trial(Trial("P01", "C0", 1, [CameraVideo(str(va)), CameraVideo(str(vb), "front", "Camera B")]))
    win.state.set_project(pr)
    win.state.openTrial.emit("P01_C0_T01", "two")
    tp = win.pages["two"]
    assert tp.player_b.reader is not None
    tp.btn_run.click()  # not yet synced -> friendly error, no crash
    assert any("Synchronise first" in str(m) for m in no_dialogs)
    tp.btn_auto.click()
    assert tp.trial.sync["offset_s"] == pytest.approx(0.6, abs=0.01)
    assert "Offset" in tp.sync_label.text()
    # linked playback: B follows A by the offset
    tp.player.seek(90)  # 1.5 s in A -> 0.9 s in B -> frame 27 at 30 fps
    assert tp.player_b.index == pytest.approx(27, abs=1)
    # manual sync from clap frames
    tp.player.seek(60); tp.btn_clap_a.click()
    tp.link.setChecked(False); tp.player_b.seek(12); tp.btn_clap_b.click()
    tp.btn_manual.click()
    assert tp.trial.sync["method"] == "manual" and tp.trial.sync["offset_s"] == pytest.approx(0.6)
    tp.offset.setValue(0.61)
    assert tp.trial.sync["method"].endswith("+adjusted")
    tp.btn_window.click()
    a, b = tp.player.interval_s()
    assert a == pytest.approx(0.61, abs=0.02) and b <= 3.0
    tp.btn_aligned.click()
    out = pr.trial_dir("P01_C0_T01") / "aligned"
    assert (out / "P01_C0_T01_A_aligned.mp4").exists() and (out / "P01_C0_T01_B_aligned.mp4").exists()
    # original files untouched
    assert video.probe(va).fps == pytest.approx(60)


def test_two_camera_run_with_injected_pose(win, tmp_path, qtbot, no_dialogs, monkeypatch):
    va, _ = _make_video(tmp_path / "A.mp4", 60, 1.0, seed=1)
    vb, _ = _make_video(tmp_path / "B.mp4", 30, 0.4, seed=2)
    pr = Project.new(tmp_path / "s", "t")
    pr.add_participant(Participant("P01", 70, 1.75))
    pr.add_trial(Trial("P01", "C0", 1, [CameraVideo(str(va)), CameraVideo(str(vb), "front", "Camera B")],
                       sync={"offset_s": 0.6, "method": "audio"}))
    win.state.set_project(pr)
    win.state.openTrial.emit("P01_C0_T01", "two")
    tp = win.pages["two"]
    from trailbuddy.core import pose as pose_mod
    from trailbuddy.core.landmarks import PoseSeries
    s60, _ = synthetic_descent(duration=3.0, fps=60, width=640, img_height=480, px_per_m=200)
    s30, _ = synthetic_descent(duration=3.0, fps=30, width=640, img_height=480, px_per_m=200)

    def fake(video_path, f0, f1, variant, progress=None, cancelled=None):
        s = s60 if str(video_path).endswith("A.mp4") else s30
        f1 = min(f1, s.n_frames)
        return PoseSeries(s.t[f0:f1], s.xy[f0:f1], s.visibility[f0:f1], s.fps, 640, 480, str(video_path))
    monkeypatch.setattr(pose_mod, "estimate", fake)
    tp.btn_window.click()
    tp.btn_run.click()
    qtbot.waitUntil(lambda: tp.btn_run.isEnabled(), timeout=30000)
    res = tp.results.result
    assert res is not None, no_dialogs
    assert "camB_right_knee_fppa_deg" in res.timeseries
