"""Single-camera workflow: preview, interval, scale, pole tracking, analysis, results."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from ..core import pole as pole_mod
from ..core.landmarks import PoseSeries
from ..core.pose import draw_skeleton
from ..core.runner import run_trial
from ..core.video import trim
from .analysis_form import AnalysisForm, hint
from .components import Accordion, Segmented, StepCard, TimelineStrip
from .report_view import ReportView
from .widgets import VideoPlayer, Worker, draw_painter_text, error_box, start_worker


def open_folder(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif os.name == "nt":
        os.startfile(str(path))  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", str(path)])


class PolePanel(QWidget):
    """Pole tracking controls for camera A: colour marker or manual clicks."""

    changed = Signal()

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.annotations = pole_mod.ManualAnnotations()
        self.tracks: dict[str, pole_mod.PoleTrack] = {}
        self.detector: pole_mod.ColorMarkerDetector | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(hint("Optional. Bright tape on each pole tip makes tracking automatic; you can also click "
                           "the tip by hand. Frames where the pole is not found stay empty."))
        row = QHBoxLayout()
        self.pole = QComboBox(); self.pole.addItem("Right-hand pole", "right"); self.pole.addItem("Left-hand pole", "left")
        self.part = QComboBox(); self.part.addItem("Tip", "tip"); self.part.addItem("Grip marker", "top")
        row.addWidget(self.pole); row.addWidget(self.part)
        lay.addLayout(row)
        row = QHBoxLayout()
        self.btn_pick = QPushButton("Pick marker colour"); self.btn_pick.setCheckable(True)
        self.btn_pick.setToolTip("Click the coloured tape on the pole tip in the current frame.")
        self.btn_track = QPushButton("Track marker"); self.btn_track.setEnabled(False)
        self.btn_track.setToolTip("Track the picked colour through the analysis interval.")
        self.btn_track.clicked.connect(self.track_marker)
        row.addWidget(self.btn_pick); row.addWidget(self.btn_track)
        lay.addLayout(row)
        row = QHBoxLayout()
        self.btn_annot = QPushButton("Click to annotate"); self.btn_annot.setCheckable(True)
        self.btn_annot.setToolTip("Manual mode: each click stores the selected point at the current frame. "
                                  "Gaps up to 0.25 s are interpolated (flagged); longer gaps stay empty.")
        self.btn_clear = QPushButton("Clear this frame")
        self.btn_clear.clicked.connect(self.clear_frame)
        self.btn_reset = QPushButton("Clear pole")
        self.btn_reset.clicked.connect(self.clear_pole)
        row.addWidget(self.btn_annot); row.addWidget(self.btn_clear)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.btn_reset)
        lay.addLayout(row)
        self.status = QLabel("No pole data yet.")
        self.status.setObjectName("muted"); self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.btn_pick.toggled.connect(lambda on: on and self.btn_annot.setChecked(False))
        self.btn_annot.toggled.connect(lambda on: on and self.btn_pick.setChecked(False))

    def reset(self):
        self.annotations = pole_mod.ManualAnnotations()
        self.tracks = {}
        self.detector = None
        self.btn_track.setEnabled(False)
        self._update()

    def load(self, folder: Path):
        self.reset()
        f = folder / "poles_manual.json"
        if f.exists():
            self.annotations = pole_mod.ManualAnnotations.load(f)
        for side in ("left", "right"):
            p = folder / f"pole_{side}_marker.csv"
            if p.exists():
                df = pd.read_csv(p)
                self.tracks[side] = pole_mod.PoleTrack(df.time_s.to_numpy(), df[["tip_x", "tip_y"]].to_numpy(),
                                                       None, df.confidence.to_numpy(), df.source.to_numpy(), "color_marker")
        self._update()

    def save(self, folder: Path):
        if self.annotations.points:
            self.annotations.save(folder / "poles_manual.json")
        for side, tr in self.tracks.items():
            pd.DataFrame({"time_s": tr.t, "tip_x": tr.tip[:, 0], "tip_y": tr.tip[:, 1],
                          "confidence": tr.confidence, "source": tr.source}).to_csv(folder / f"pole_{side}_marker.csv", index=False)

    def handle_click(self, x, y) -> bool:
        player = self.page.player
        if self.btn_pick.isChecked():
            frame = player.reader.read(player.index)
            try:
                self.detector = pole_mod.ColorMarkerDetector.from_sample(frame, int(x), int(y))
            except ValueError as e:
                error_box(self, "Not a marker", str(e))
                return True
            self.seed = (x, y)
            self.btn_pick.setChecked(False)
            self.btn_track.setEnabled(True)
            self.status.setText(f"Marker colour picked (hue {self.detector.hsv_low[0]}–{self.detector.hsv_high[0]}). "
                                "Now click Track marker.")
            return True
        if self.btn_annot.isChecked():
            self.annotations.set(self.pole.currentData(), self.part.currentData(), player.index, x, y)
            self._update()
            player.refresh()
            return True
        return False

    def clear_frame(self):
        self.annotations.remove(self.pole.currentData(), self.part.currentData(), self.page.player.index)
        self._update(); self.page.player.refresh()

    def clear_pole(self):
        side = self.pole.currentData()
        self.annotations.points.pop(side, None)
        self.tracks.pop(side, None)
        self._update(); self.page.player.refresh()

    def track_marker(self):
        player = self.page.player
        a, b = player.interval_s()
        f0, f1 = int(round(a * player.fps)), int(round(b * player.fps)) + 1
        frames = (fr for _, fr in player.reader.iter_range(f0, f1))
        t = np.arange(f0, f1) / player.fps
        prev = self.seed if abs(player.index - f0) < 2 else None
        tr = pole_mod.track(frames, t, self.detector, start_tip=prev)
        player.reader._next = -1
        self.tracks[self.pole.currentData()] = tr
        self._update()
        player.refresh()

    def _update(self):
        msgs = []
        for side in ("right", "left"):
            n = len(self.annotations.points.get(side, {}).get("tip", {}))
            if n:
                msgs.append(f"{side} pole: {n} manual tip points")
            if side in self.tracks:
                msgs.append(f"{side} pole: marker tracked in {100 * self.tracks[side].coverage():.0f}% of frames")
        self.status.setText("; ".join(msgs) if msgs else "No pole data yet.")
        self.changed.emit()

    def summary(self) -> tuple[str, bool]:
        msgs = []
        for side in ("right", "left"):
            if side in self.tracks:
                msgs.append(f"{side} pole tracked ({100 * self.tracks[side].coverage():.0f}%)")
            elif self.annotations.points.get(side, {}).get("tip"):
                msgs.append(f"{side} pole: {len(self.annotations.points[side]['tip'])} clicks")
        return ("; ".join(msgs) if msgs else "Not tracked (optional)"), bool(msgs)

    def tracks_for(self, t: np.ndarray, frame0: int) -> dict:
        out = {}
        for side in ("left", "right"):
            if side in self.tracks:
                tr = self.tracks[side]
                tip = np.stack([np.interp(t, tr.t, tr.tip[:, c], left=np.nan, right=np.nan) for c in range(2)], axis=1)
                out[side] = pole_mod.PoleTrack(t, tip, None, None, np.where(np.isnan(tip[:, 0]), 0, 1), "color_marker")
            elif self.annotations.points.get(side, {}).get("tip"):
                fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 30
                out[side] = self.annotations.to_track(side, t, frame0, max_gap_frames=int(0.25 * fps))
        return out

    def draw(self, img, index):
        for side, col in (("right", (0, 140, 255)), ("left", (255, 120, 0))):
            pts = self.annotations.points.get(side, {})
            for part in ("tip", "top"):
                p = pts.get(part, {}).get(index)
                if p:
                    cv2.drawMarker(img, (int(p[0]), int(p[1])), col, cv2.MARKER_CROSS, 22, 2)
            tr = self.tracks.get(side)
            if tr is not None:
                k = int(np.argmin(np.abs(tr.t - index / self.page.player.fps)))
                if abs(tr.t[k] - index / self.page.player.fps) < 1e-3 and np.isfinite(tr.tip[k]).all():
                    cv2.circle(img, tuple(tr.tip[k].astype(int)), 12, col, 2)
        return img


class SinglePage(QWidget):
    title = "One camera"
    hint = "Side-view video of a descent. Work through the steps on the right, then run the analysis."
    two_camera = False

    def __init__(self, state):
        super().__init__()
        self.setObjectName("page")
        self.state = state
        self.trial = None
        self.pose_overlay: PoseSeries | None = None
        self.overlay_frame0 = 0
        self.thread = None
        self.worker = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 14)
        lay.setSpacing(10)
        # header: title, trial picker, view switch, body metrics
        head = QHBoxLayout()
        t = QLabel(self.title)
        t.setObjectName("pageTitle")
        head.addWidget(t)
        head.addSpacing(16)
        self.trial_combo = QComboBox()
        self.trial_combo.setMinimumWidth(230)
        self.trial_combo.setToolTip("Trials are added on the Study page")
        self.trial_combo.currentIndexChanged.connect(self._trial_selected)
        head.addWidget(self.trial_combo)
        self.btn_body = QPushButton("Body metrics…")
        self.btn_body.setToolTip("Weight, height and segment lengths used by the calculations")
        self.btn_body.clicked.connect(self.edit_body)
        head.addWidget(self.btn_body)
        head.addStretch(1)
        self.view = Segmented(["Video and setup", "Report"])
        self.view.changed.connect(self._switch_view)
        head.addWidget(self.view)
        lay.addLayout(head)
        self.trial_info = QLabel("")
        self.trial_info.setObjectName("pageHint")
        lay.addWidget(self.trial_info)

        self.stack = QStackedWidget()
        # ---- page 0: video + steps ---------------------------------------------------------
        work = QSplitter(Qt.Orientation.Horizontal)
        work.setOpaqueResize(False)
        work.setChildrenCollapsible(False)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        self.video_area = QSplitter(Qt.Orientation.Horizontal)
        self.video_area.setOpaqueResize(False)
        self.player = VideoPlayer("Camera A")
        self.player.overlay = self._draw_overlay
        self.player.view.clicked.connect(self._clicked)
        self.player.frameChanged.connect(self._frame_changed)
        self.video_area.addWidget(self.player)
        ll.addWidget(self.video_area, 1)
        self.timeline = TimelineStrip()
        self.timeline.seek.connect(lambda ts: self.player.seek(int(round(ts * self.player.fps))))
        ll.addWidget(self.timeline)
        work.addWidget(left)

        right = QWidget()
        right.setMinimumWidth(400)
        right.setMaximumWidth(520)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.form = AnalysisForm()
        self.form.pickScaleToggled.connect(self._pick_scale_toggled)
        self.form.changed.connect(self._update_steps)
        self.poles = PolePanel(self)
        self.poles.changed.connect(self._update_steps)
        self.acc = Accordion()
        n = 1
        self.step_clip = self.acc.add(StepCard(n, "Choose the descent", self._clip_body(),
                                               "Set start and end on the video")); n += 1
        self.extra_steps(n)
        n += len(self.acc.steps) - 1
        self.step_scale = self.acc.add(StepCard(n, "Scale and side", self.form.scale_box)); n += 1
        self.step_stairs = self.acc.add(StepCard(n, "Stairs", self.form.stairs_box)); n += 1
        self.step_poles = self.acc.add(StepCard(n, "Pole tracking", self.poles)); n += 1
        self.step_forces = self.acc.add(StepCard(n, "Forces", self.form.forces_box)); n += 1
        self.step_adv = self.acc.add(StepCard(n, "Advanced (optional)", self.form.adv_box,
                                              "Model settings: defaults are fine"))
        self.acc.finish()
        scroll.setWidget(self.acc)
        rl.addWidget(scroll, 1)
        run = QFrame()
        run.setObjectName("card")
        rv = QVBoxLayout(run)
        rv.setContentsMargins(12, 10, 12, 10)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress_msg = QLabel("Ready when the steps above are set.")
        self.progress_msg.setObjectName("muted")
        self.progress_msg.setWordWrap(True)
        rv.addWidget(self.progress_msg)
        rv.addWidget(self.progress)
        brow = QHBoxLayout()
        self.btn_run = QPushButton("Run analysis")
        self.btn_run.setObjectName("primary")
        self.btn_run.setMinimumHeight(34)
        self.btn_run.setToolTip("Track the body (cached after the first run) and compute every metric")
        self.btn_run.clicked.connect(self.run)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(lambda: self.worker and self.worker.cancel())
        brow.addWidget(self.btn_run, 1)
        brow.addWidget(self.btn_cancel)
        rv.addLayout(brow)
        brow = QHBoxLayout()
        self.btn_folder = QPushButton("Results folder")
        self.btn_folder.clicked.connect(self._open_folder)
        self.btn_clip = QPushButton("Save clip")
        self.btn_clip.setToolTip("Writes the chosen interval to a new file; the original is untouched")
        self.btn_clip.clicked.connect(self._save_clip)
        self.btn_overlay = QPushButton("Save overlay video")
        self.btn_overlay.clicked.connect(self._save_overlay)
        for b in (self.btn_folder, self.btn_clip, self.btn_overlay):
            brow.addWidget(b)
        rv.addLayout(brow)
        rl.addWidget(run)
        work.addWidget(right)
        work.setStretchFactor(0, 1)
        work.setSizes([900, 440])
        self.stack.addWidget(work)
        # ---- page 1: report -----------------------------------------------------------------
        self.results = ReportView()
        self.stack.addWidget(self.results)
        lay.addWidget(self.stack, 1)
        self.player.loaded.connect(self._update_steps)
        self.player.rangeChanged.connect(self._update_steps)
        state.trialsChanged.connect(self.reload_trials)
        self.reload_trials()

    # hooks for the two-camera page
    def extra_steps(self, n: int):
        pass

    def trial_filter(self, t) -> bool:
        return len(t.videos) == 1

    def _clip_body(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(hint("Play or drag the slider to the first step of the descent and press Set start, then to "
                         "the last step and press Set end. Include whole steps."))
        row = QHBoxLayout()
        b = QPushButton("Use whole video")
        b.clicked.connect(lambda: self.player.reader and self.player.set_interval_s(
            0, (self.player.reader.info.n_frames - 1) / self.player.fps))
        row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        return w

    def _update_steps(self, *_):
        iv = self.player.interval_s() if self.player.reader else None
        if iv:
            self.step_clip.set_status(f"{iv[0]:.2f}–{iv[1]:.2f} s ({iv[1] - iv[0]:.2f} s)",
                                      self.player.mark_in is not None or self.player.mark_out is not None)
        self.step_scale.set_status(*self.form.scale_summary())
        self.step_stairs.set_status(*self.form.stairs_summary())
        self.step_poles.set_status(*self.poles.summary())
        self.step_forces.set_status(*self.form.forces_summary())

    def _switch_view(self, i: int):
        self.stack.setCurrentIndex(i)

    def _frame_changed(self, i: int):
        self.timeline.set_playhead(i / self.player.fps)

    # ---------------------------------------------------------------------------------------
    def reload_trials(self):
        cur = self.trial.id if self.trial else None
        self.trial_combo.blockSignals(True)
        self.trial_combo.clear()
        p = self.state.project
        if p:
            for t in p.trials:
                if self.trial_filter(t):
                    self.trial_combo.addItem(f"{t.id}  ·  {t.status}", t.id)
        self.trial_combo.blockSignals(False)
        if self.trial_combo.count() == 0:
            self.trial = None
            self.trial_info.setText("No trials of this kind yet. Add them on the Study page." if p
                                    else "Open or create a study on the Study page first.")
            self._set_enabled(False)
            return
        i = self.trial_combo.findData(cur) if cur else 0
        self.trial_combo.setCurrentIndex(max(0, i))
        if self.trial is None or self.trial.id != self.trial_combo.currentData():
            self._trial_selected()

    def select_trial(self, tid: str):
        i = self.trial_combo.findData(tid)
        if i >= 0:
            self.trial_combo.setCurrentIndex(i)

    def _set_enabled(self, on: bool):
        for w in (self.btn_run, self.btn_folder, self.btn_clip, self.btn_overlay, self.poles, self.btn_body, self.acc):
            w.setEnabled(on)
        self.form.setEnabled(on)

    def _trial_selected(self, *_):
        tid = self.trial_combo.currentData()
        p = self.state.project
        if not tid or not p:
            return
        self.trial = p.trial(tid)
        self._show_info()
        self._set_enabled(True)
        self.form.load_from(self.trial)
        folder = p.trial_dir(self.trial.id)
        self.poles.load(folder)
        self.load_videos()
        if self.trial.interval:
            self.player.set_interval_s(*self.trial.interval)
        self.pose_overlay = None
        self.timeline.clear()
        self.results.result = None
        self._load_existing_result(folder)
        self._update_steps()

    def _show_info(self):
        p = self.state.project
        cond = p.condition(self.trial.condition_code)
        part = p.participant(self.trial.participant_id)
        pole = f"pole {self.trial.pole_length_cm:g} cm" if self.trial.pole_length_cm else (
            "poles" if cond.uses_poles else "no poles")
        self.trial_info.setText(f"{part.id} · {cond.code} {cond.label} · {pole} · trial {self.trial.trial_number}"
                                f"   |   {part.body_mass_kg:g} kg, {part.height_m:g} m, "
                                f"{len(part.segments)} segment lengths measured")

    def edit_body(self):
        from .project_page import ParticipantDialog
        if not self.trial:
            return
        part = self.state.project.participant(self.trial.participant_id)
        dlg = ParticipantDialog(self, part)
        if dlg.exec():
            v = dlg.value()
            try:
                v.validate()
            except ValueError as e:
                error_box(self, "Check body metrics", str(e))
                return
            part.body_mass_kg, part.height_m, part.leg_length_m = v.body_mass_kg, v.height_m, v.leg_length_m
            part.standard_pole_length_cm, part.segments, part.notes = v.standard_pole_length_cm, v.segments, v.notes
            self.state.save()
            self.state.trialsChanged.emit()
            self._show_info()
            self.state.status.emit("Body metrics saved. Run the analysis again to use them.")

    def load_videos(self):
        v = self.trial.videos[0].path
        if not Path(v).exists():
            error_box(self, "Video not found", f"{v}\n\nThe file was moved or renamed. Re-add the trial.")
            return
        self.player.load(v)

    def _load_existing_result(self, folder: Path):
        from ..core.analysis import load_result
        if (folder / "analysis.json").exists():
            try:
                self._show_result(load_result(folder))
                self._load_overlay(folder)
            except Exception as e:  # stale/corrupt results
                self.state.status.emit(f"Could not load previous results: {e}")

    def _show_result(self, res):
        p = self.state.project
        cond = p.condition(self.trial.condition_code)
        self.results.show_result(res, f"{self.trial.id}: {cond.label}",
                                 f"{p.participant(self.trial.participant_id).body_mass_kg:g} kg")
        ts = res.timeseries
        s = res.side
        lanes = [(f"{s[0].upper()} foot", ts[f"{s}_stance"].to_numpy(), "#4D4D4D")]
        o = "left" if s == "right" else "right"
        if f"{o}_stance" in ts:
            lanes.append((f"{o[0].upper()} foot", ts[f"{o}_stance"].to_numpy(), "#A8A8A8"))
        for pside in ("left", "right"):
            if f"pole_{pside}_contact" in ts:
                lanes.append((f"{pside[0].upper()} pole", ts[f"pole_{pside}_contact"].to_numpy(), "#D55E00"))
        self.timeline.set_data(ts.time_s.to_numpy(), ts[f"{s}_knee_flexion_deg"].to_numpy(), lanes,
                               f"{s.capitalize()} knee flexion (deg) · click to jump the video")

    def _load_overlay(self, folder: Path):
        f = folder / "pose_A.csv"
        if f.exists() and self.player.reader:
            info = self.player.reader.info
            self.pose_overlay = PoseSeries.from_dataframe(pd.read_csv(f), info.fps, info.width, info.height)
            self.overlay_frame0 = int(round(self.pose_overlay.t[0] * info.fps))
            self.player.refresh()

    def _draw_overlay(self, img, i):
        if self.pose_overlay is not None:
            k = i - self.overlay_frame0
            if 0 <= k < self.pose_overlay.n_frames:
                draw_skeleton(img, self.pose_overlay.xy[k], self.pose_overlay.visibility[k])
                res = self.results.result
                if res is not None:
                    col = f"{res.side}_knee_flexion_deg"
                    ts = res.timeseries
                    j = int(np.argmin(np.abs(ts.time_s.to_numpy() - i / self.player.fps)))
                    if col in ts and np.isfinite(ts[col].iloc[j]):
                        draw_painter_text(img, f"{res.side} knee flexion {ts[col].iloc[j]:.0f} deg (2D)",
                                          scale=img.shape[0] / 720)
        for p in self.form.scale_points:
            cv2.drawMarker(img, (int(p[0]), int(p[1])), (40, 200, 255), cv2.MARKER_TILTED_CROSS, 18, 2)
        return self.poles.draw(img, i)

    def _pick_scale_toggled(self, on):
        if on:
            self.form.scale_points = []
            self.poles.btn_pick.setChecked(False)
            self.poles.btn_annot.setChecked(False)
        self._update_click_mode()

    def _update_click_mode(self):
        self.player.view.click_enabled = True
        self.player.view.setCursor(Qt.CursorShape.CrossCursor)

    def _clicked(self, x, y):
        if self.form.btn_pick_scale.isChecked():
            self.form.add_scale_point(x, y)
            self.player.refresh()
            return
        self.poles.handle_click(x, y)

    # ---------------------------------------------------------------------------------------
    def prepare_trial(self) -> bool:
        iv = self.player.interval_s()
        if iv is None:
            error_box(self, "No video", "Load a trial with a video first.")
            return False
        self.trial.interval = list(iv)
        return True

    def run(self):
        if not self.trial or not self.prepare_trial():
            return
        try:
            settings = self.form.settings()
        except ValueError as e:
            error_box(self, "Check settings", str(e))
            return
        folder = self.state.project.trial_dir(self.trial.id)
        self.form.store_into(self.trial)
        self.poles.save(folder)
        variant = self.form.model.currentData()
        self.worker = Worker(self._run_job, settings, variant)
        self.worker.progress.connect(self._progress)
        self.worker.finished.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.btn_run.setEnabled(False); self.btn_cancel.setEnabled(True)
        self.progress.setVisible(True); self.progress.setValue(0)
        self.thread = start_worker(self, self.worker)

    def _run_job(self, settings, variant, progress, cancelled):
        info = self.player.reader.info
        a, b = self.trial.interval
        f0, f1 = int(round(a * info.fps)), min(info.n_frames, int(round(b * info.fps)) + 1)
        t = np.arange(f0, f1) / info.fps
        poles = self.poles.tracks_for(t, f0) or None
        return run_trial(self.state.project, self.trial, settings, poles, variant, progress, cancelled)

    def _progress(self, f, msg):
        self.progress.setValue(int(100 * f))
        self.progress_msg.setText(msg)

    def _done(self, res):
        self.btn_run.setEnabled(True); self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        self.progress_msg.setText("Analysis complete. Results saved in the trial folder.")
        self._show_result(res)
        self._load_overlay(self.state.project.trial_dir(self.trial.id))
        self.view.set_index(1)
        self.state.trialsChanged.emit()
        self.state.resultsChanged.emit()
        self.state.status.emit(f"{self.trial.id} analysed")

    def _failed(self, msg):
        self.btn_run.setEnabled(True); self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        self.progress_msg.setText(msg)
        if "cancelled" not in msg:
            error_box(self, "Analysis failed", msg)

    def _open_folder(self):
        if self.trial:
            open_folder(self.state.project.trial_dir(self.trial.id))

    def _save_clip(self):
        if not self.trial or not self.player.reader:
            return
        a, b = self.player.interval_s()
        out = self.state.project.trial_dir(self.trial.id) / f"{self.trial.id}_clip_{a:.2f}-{b:.2f}s.mp4"
        try:
            trim(self.player.reader.info.path, out, a, b)
        except Exception as e:
            error_box(self, "Trim failed", str(e))
            return
        self.state.status.emit(f"Saved {out.name}")

    def _save_overlay(self):
        if self.pose_overlay is None:
            error_box(self, "Run the analysis first", "The overlay needs pose results for this trial.")
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save overlay video",
                                             str(self.state.project.trial_dir(self.trial.id) / f"{self.trial.id}_overlay.mp4"),
                                             "MP4 video (*.mp4)")
        if not out:
            return
        from ..core.video import write_video
        r = self.player.reader
        f0 = self.overlay_frame0
        frames = (self._draw_overlay(fr.copy(), i) for i, fr in r.iter_range(f0, f0 + self.pose_overlay.n_frames))
        try:
            write_video(frames, out, r.info.fps)
        except Exception as e:
            error_box(self, "Export failed", str(e))
            return
        self.state.status.emit(f"Saved {Path(out).name}")
