"""Two-camera workflow: side-by-side preview, clap synchronization, common window, analysis."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QPushButton)

from ..core import sync
from ..core.video import VideoError, extract_audio, trim
from .single_page import SinglePage
from .widgets import VideoPlayer, error_box


class TwoPage(SinglePage):
    title = "Two cameras"
    hint = ("Load a trial recorded from two viewpoints. Synchronise them with the clap (automatic from audio, or by "
            "marking the clap frame in each video), check the alignment, then analyse. Camera A is the side view "
            "used for sagittal angles and kinetics. 3D requires a DLT calibration and is reported as unvalidated.")

    def __init__(self, state):
        self.clap_a = None
        self.clap_b = None
        super().__init__(state)
        self.player_b = VideoPlayer("Camera B")
        self.player_b.btn_in.setVisible(False)
        self.player_b.btn_out.setVisible(False)
        self.player_b.range_label.setVisible(False)
        # Side-by-side preview: A (side view) left, B right; results below.
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QSplitter
        self.hsplit = QSplitter(Qt.Orientation.Horizontal)
        self.hsplit.addWidget(self.player)
        self.hsplit.addWidget(self.player_b)
        self.vsplit.insertWidget(0, self.hsplit)
        self.vsplit.setSizes([400, 380])
        self.player.frameChanged.connect(self._follow_a)
        if self.trial is not None:
            self._trial_selected()

    def trial_filter(self, t) -> bool:
        return len(t.videos) > 1

    def extra_controls(self, layout):
        g = QGroupBox("Synchronisation")
        f = QFormLayout(g)
        self.btn_auto = QPushButton("Detect clap from audio")
        self.btn_auto.setToolTip("Finds the sharpest loud transient in each audio track and aligns them.")
        self.btn_auto.clicked.connect(self.auto_sync)
        self.search_end = QDoubleSpinBox(); self.search_end.setRange(0, 600); self.search_end.setSuffix(" s")
        self.search_end.setSpecialValueText("whole recording"); self.search_end.setValue(0)
        self.search_end.setToolTip("Only search the first N seconds (useful if there are other loud sounds).")
        f.addRow(self.btn_auto)
        f.addRow("Search first", self.search_end)
        row = QHBoxLayout()
        self.btn_clap_a = QPushButton("Clap frame A = current")
        self.btn_clap_a.clicked.connect(lambda: self._mark_clap("a"))
        self.btn_clap_b = QPushButton("Clap frame B = current")
        self.btn_clap_b.clicked.connect(lambda: self._mark_clap("b"))
        row.addWidget(self.btn_clap_a); row.addWidget(self.btn_clap_b)
        f.addRow(row)
        self.btn_manual = QPushButton("Apply manual sync")
        self.btn_manual.setToolTip("Use the frames where the hands first touch in each video.")
        self.btn_manual.clicked.connect(self.manual_sync)
        f.addRow(self.btn_manual)
        self.offset = QDoubleSpinBox(); self.offset.setRange(-600, 600); self.offset.setDecimals(4)
        self.offset.setSingleStep(0.001); self.offset.setSuffix(" s")
        self.offset.setToolTip("t_A = t_B + offset. Fine-tune with the arrows while watching both views.")
        self.offset.valueChanged.connect(self._offset_edited)
        f.addRow("Offset (B → A)", self.offset)
        self.link = QCheckBox("Link playback (B follows A)"); self.link.setChecked(True)
        f.addRow(self.link)
        self.sync_label = QLabel("Not synchronised.")
        self.sync_label.setWordWrap(True); self.sync_label.setObjectName("muted")
        f.addRow(self.sync_label)
        row = QHBoxLayout()
        self.btn_window = QPushButton("Use common window")
        self.btn_window.setToolTip("Set the analysis interval to the time both cameras recorded.")
        self.btn_window.clicked.connect(self.use_common_window)
        self.btn_aligned = QPushButton("Save aligned clips")
        self.btn_aligned.setToolTip("Writes both videos trimmed to the analysis interval (originals untouched).")
        self.btn_aligned.clicked.connect(self.save_aligned)
        row.addWidget(self.btn_window); row.addWidget(self.btn_aligned)
        f.addRow(row)
        layout.addWidget(g)
        g = QGroupBox("3D (optional)")
        f = QFormLayout(g)
        self.btn_dlt = QPushButton("Load DLT calibration…")
        self.btn_dlt.setToolTip("CSV with X_m,Y_m,Z_m,uA,vA,uB,vB for >= 6 non-coplanar control points.")
        self.btn_dlt.clicked.connect(self.load_dlt)
        self.dlt_label = QLabel("No calibration: 2D per-view analysis only.")
        self.dlt_label.setObjectName("muted"); self.dlt_label.setWordWrap(True)
        f.addRow(self.btn_dlt); f.addRow(self.dlt_label)
        layout.addWidget(g)

    # ---------------------------------------------------------------------------------------
    def load_videos(self):
        if not hasattr(self, "player_b"):
            return
        super().load_videos()
        vb = self.trial.videos[1].path
        if not Path(vb).exists():
            error_box(self, "Video not found", vb)
            return
        self.player_b.load(vb)
        self.player_b.title.setText(self.player_b.title.text().replace("Camera B", f"Camera B ({self.trial.videos[1].role})", 1))
        self.offset.blockSignals(True)
        self.offset.setValue(float(self.trial.sync.get("offset_s", 0.0)))
        self.offset.blockSignals(False)
        self._show_sync()
        cal = self.trial.settings.get("dlt_csv")
        self.dlt_label.setText(f"Calibration: {Path(cal).name}" if cal else "No calibration: 2D per-view analysis only.")

    def _follow_a(self, i):
        if self.link.isChecked() and self.player_b.reader:
            tb = i / self.player.fps - self.offset.value()
            self.player_b.seek(int(round(tb * self.player_b.fps)))

    def _mark_clap(self, which):
        if which == "a":
            self.clap_a = self.player.index
        else:
            self.clap_b = self.player_b.index
        self.sync_label.setText(f"Clap frames: A = {self.clap_a if self.clap_a is not None else '–'}, "
                                f"B = {self.clap_b if self.clap_b is not None else '–'}. Turn off 'Link playback' "
                                "to scrub B on its own.")

    def manual_sync(self):
        if self.clap_a is None or self.clap_b is None:
            error_box(self, "Mark both clap frames", "Set the clap frame in camera A and camera B first.")
            return
        r = sync.sync_manual(self.clap_a, self.player.fps, self.clap_b, self.player_b.fps)
        self._apply(r)

    def auto_sync(self):
        try:
            aa, sr = extract_audio(self.trial.videos[0].path)
            ab, _ = extract_audio(self.trial.videos[1].path)
            win = (0.0, self.search_end.value()) if self.search_end.value() > 0 else None
            r = sync.sync_audio(aa, ab, sr, win, win)
        except (VideoError, ValueError) as e:
            error_box(self, "Automatic sync failed", f"{e}\n\nUse manual clap frames instead.")
            return
        self._apply(r)

    def _apply(self, r: sync.SyncResult):
        self.trial.sync = {"offset_s": r.offset_s, "method": r.method, "clap_a_s": r.clap_a_s,
                           "clap_b_s": r.clap_b_s, "confidence": r.confidence, "note": r.note}
        self.offset.blockSignals(True)
        self.offset.setValue(r.offset_s)
        self.offset.blockSignals(False)
        self.state.save()
        self._show_sync()
        self.player.seek(int(round(r.clap_a_s * self.player.fps)))
        self._follow_a(self.player.index)

    def _offset_edited(self, v):
        if not self.trial:
            return
        if self.trial.sync.get("offset_s") != v:
            self.trial.sync["offset_s"] = v
            self.trial.sync["method"] = (self.trial.sync.get("method", "manual").split("+")[0]) + "+adjusted"
            self.state.save()
        self._show_sync()
        self._follow_a(self.player.index)

    def _show_sync(self):
        s = self.trial.sync if self.trial else {}
        if "offset_s" not in s:
            self.sync_label.setText("Not synchronised. Detect the clap or mark clap frames.")
            return
        conf = s.get("confidence")
        txt = f"Offset {s['offset_s']:+.4f} s ({s.get('method')})"
        if conf is not None:
            txt += f", clap clarity {conf:.0f}× background"
        if s.get("note"):
            txt += f". ⚠ {s['note']}"
        try:
            a, b = sync.common_window(self.player.reader.info.duration, self.player_b.reader.info.duration, s["offset_s"])
            txt += f"\nCommon window (camera A clock): {a:.2f}–{b:.2f} s"
        except (ValueError, AttributeError):
            txt += "\n⚠ Recordings do not overlap with this offset."
        self.sync_label.setText(txt)

    def use_common_window(self):
        try:
            a, b = sync.common_window(self.player.reader.info.duration, self.player_b.reader.info.duration,
                                      self.offset.value())
        except ValueError as e:
            error_box(self, "No overlap", str(e))
            return
        self.player.set_interval_s(a, b - 1.0 / self.player.fps)

    def save_aligned(self):
        if "offset_s" not in self.trial.sync:
            error_box(self, "Synchronise first", "Detect the clap or apply manual sync first.")
            return
        a, b = self.player.interval_s()
        off = self.trial.sync["offset_s"]
        out = self.state.project.trial_dir(self.trial.id) / "aligned"
        try:
            trim(self.trial.videos[0].path, out / f"{self.trial.id}_A_aligned.mp4", a, b)
            trim(self.trial.videos[1].path, out / f"{self.trial.id}_B_aligned.mp4", max(0, a - off), b - off)
        except Exception as e:
            error_box(self, "Export failed", str(e))
            return
        self.state.status.emit(f"Aligned clips saved to {out}")

    def load_dlt(self):
        p, _ = QFileDialog.getOpenFileName(self, "DLT calibration", "", "CSV files (*.csv)")
        if not p:
            return
        from ..core.runner import load_dlt_csv
        try:
            _, _, err = load_dlt_csv(p)
        except Exception as e:
            error_box(self, "Invalid calibration", str(e))
            return
        self.trial.settings["dlt_csv"] = p
        self.state.save()
        self.dlt_label.setText(f"{Path(p).name}: reprojection error A {err[0]:.1f} px, B {err[1]:.1f} px. "
                               "3D output remains labelled unvalidated.")

    def prepare_trial(self) -> bool:
        if "offset_s" not in self.trial.sync:
            error_box(self, "Synchronise first", "Detect the clap or apply manual clap frames before analysing.")
            return False
        return super().prepare_trial()
