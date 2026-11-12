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
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QScrollArea, QSplitter, QVBoxLayout, QWidget)

from ..core import pole as pole_mod
from ..core.landmarks import PoseSeries
from ..core.pose import draw_skeleton
from ..core.runner import run_trial
from ..core.video import trim
from .analysis_form import AnalysisForm
from .result_view import ResultView
from .widgets import VideoPlayer, Worker, draw_painter_text, error_box, page_header, start_worker


def open_folder(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif os.name == "nt":
        os.startfile(str(path))  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", str(path)])


class PolePanel(QGroupBox):
    """Pole tracking controls for camera A: colour marker or manual clicks."""

    def __init__(self, page):
        super().__init__("Pole tracking (camera A)")
        self.page = page
        self.annotations = pole_mod.ManualAnnotations()
        self.tracks: dict[str, pole_mod.PoleTrack] = {}
        self.detector: pole_mod.ColorMarkerDetector | None = None
        lay = QVBoxLayout(self)
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
        row.addWidget(self.btn_annot); row.addWidget(self.btn_clear); row.addWidget(self.btn_reset)
        lay.addLayout(row)
        self.status = QLabel("No pole data. Pole force needs a scenario or measured data either way.")
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
        self.status.setText("; ".join(msgs) if msgs else "No pole data. Pole force needs a scenario or measured data either way.")

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
    hint = ("Side-view video of a descent. Set the analysis interval, choose a scale, optionally track the poles, "
            "then run the analysis. All angles are 2D projections onto the image plane.")

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
        lay.setContentsMargins(24, 18, 24, 18)
        lay.addWidget(page_header(self.title, self.hint))
        row = QHBoxLayout()
        row.addWidget(QLabel("Trial"))
        self.trial_combo = QComboBox()
        self.trial_combo.setMinimumWidth(220)
        self.trial_combo.currentIndexChanged.connect(self._trial_selected)
        row.addWidget(self.trial_combo)
        self.trial_info = QLabel("")
        self.trial_info.setObjectName("muted")
        row.addWidget(self.trial_info, 1)
        self.btn_body = QPushButton("Body metrics…")
        self.btn_body.setToolTip("Weight, height and segment lengths used by the calculations")
        self.btn_body.clicked.connect(self.edit_body)
        row.addWidget(self.btn_body)
        lay.addLayout(row)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        self.vsplit = QSplitter(Qt.Orientation.Vertical)
        self.player = VideoPlayer()
        self.player.overlay = self._draw_overlay
        self.player.view.clicked.connect(self._clicked)
        self.vsplit.addWidget(self.player)
        self.results = ResultView()
        self.vsplit.addWidget(self.results)
        self.vsplit.setSizes([420, 360])
        ll.addWidget(self.vsplit)
        split.addWidget(left)

        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(8, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget(); il = QVBoxLayout(inner); il.setContentsMargins(0, 0, 6, 0)
        self.form = AnalysisForm()
        self.form.pickScaleToggled.connect(self._pick_scale_toggled)
        il.addWidget(self.form)
        self.poles = PolePanel(self)
        il.addWidget(self.poles)
        self.extra_controls(il)
        il.addStretch(1)
        scroll.setWidget(inner)
        rl.addWidget(scroll, 1)
        self.progress = QProgressBar(); self.progress.setVisible(False)
        self.progress_msg = QLabel(""); self.progress_msg.setObjectName("muted")
        rl.addWidget(self.progress); rl.addWidget(self.progress_msg)
        brow = QHBoxLayout()
        self.btn_run = QPushButton("Run analysis"); self.btn_run.setObjectName("primary")
        self.btn_run.setToolTip("Track pose (cached after the first run) and compute all metrics.")
        self.btn_run.clicked.connect(self.run)
        self.btn_cancel = QPushButton("Cancel"); self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(lambda: self.worker and self.worker.cancel())
        brow.addWidget(self.btn_run); brow.addWidget(self.btn_cancel)
        rl.addLayout(brow)
        brow = QHBoxLayout()
        self.btn_folder = QPushButton("Results folder"); self.btn_folder.clicked.connect(self._open_folder)
        self.btn_clip = QPushButton("Save clip"); self.btn_clip.clicked.connect(self._save_clip)
        self.btn_clip.setToolTip("Writes the analysis interval to a new file; the original is untouched.")
        self.btn_overlay = QPushButton("Save overlay"); self.btn_overlay.clicked.connect(self._save_overlay)
        for b in (self.btn_folder, self.btn_clip, self.btn_overlay):
            brow.addWidget(b)
        rl.addLayout(brow)
        right.setMinimumWidth(430)
        split.addWidget(right)
        split.setSizes([880, 440])
        lay.addWidget(split, 1)
        state.trialsChanged.connect(self.reload_trials)
        self.reload_trials()

    def extra_controls(self, layout):
        pass

    def trial_filter(self, t) -> bool:
        return len(t.videos) == 1

    # ---------------------------------------------------------------------------------------
    def reload_trials(self):
        cur = self.trial.id if self.trial else None
        self.trial_combo.blockSignals(True)
        self.trial_combo.clear()
        p = self.state.project
        if p:
            for t in p.trials:
                if self.trial_filter(t):
                    self.trial_combo.addItem(f"{t.id}  ({t.status})", t.id)
        self.trial_combo.blockSignals(False)
        if self.trial_combo.count() == 0:
            self.trial = None
            self.trial_info.setText("No trials yet. Add them on the Study page." if p else "Open or create a study first.")
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
        for w in (self.btn_run, self.btn_folder, self.btn_clip, self.btn_overlay, self.form, self.poles, self.btn_body):
            w.setEnabled(on)

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
        self._load_existing_result(folder)

    def _show_info(self):
        p = self.state.project
        cond = p.condition(self.trial.condition_code)
        part = p.participant(self.trial.participant_id)
        self.trial_info.setText(f"{cond.label} · pole {self.trial.pole_length_cm or '–'} cm · {part.id}: "
                                f"{part.body_mass_kg:g} kg, {part.height_m:g} m, "
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
                self.results.show_result(load_result(folder), self.trial.id)
                self._load_overlay(folder)
            except Exception as e:  # stale/corrupt results
                self.state.status.emit(f"Could not load previous results: {e}")

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
                        draw_painter_text(img, f"{res.side} knee flexion {ts[col].iloc[j]:.0f} deg (2D)")
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
        self.results.show_result(res, self.trial.id)
        self._load_overlay(self.state.project.trial_dir(self.trial.id))
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
