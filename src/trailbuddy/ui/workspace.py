"""Analysis workspace: experiment browser | synchronised videos + linked plots | inspector."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSpinBox,
                               QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import pipeline, sync
from ..core.analysis import load_result
from ..core.metrics import CATEGORIES, INFO, SHORT_KINDS
from ..core.runner import run_pair, video_by_role
from .analysis_form import AnalysisForm, hint
from .browser import ExperimentBrowser
from .components import Segmented
from .data_plots import DataPlots
from .result_view import fmt
from .sync_video import SyncVideoPanel
from .theme import EVIDENCE_COLORS
from .widgets import Worker, error_box, start_worker

PROC_DEFAULT = {"backend": "rtmpose", "mode": "balanced", "stride": 1}


def _fit(table: QTableWidget) -> None:
    """First column takes the remaining width (long names elide with …), the others fit their content."""
    h = table.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setWordWrap(False)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.verticalHeader().setDefaultSectionSize(26)


def card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("card")
    v = QVBoxLayout(f)
    v.setContentsMargins(12, 10, 12, 12)
    v.setSpacing(8)
    if title:
        t = QLabel(title)
        t.setObjectName("cardTitle")
        v.addWidget(t)
    return f, v


class Inspector(QWidget):
    """Right panel: measures at the cursor and summary, sync, trial details, settings."""

    def __init__(self, ws):
        super().__init__()
        self.ws = ws
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 10, 10, 10)
        lay.setSpacing(8)
        self.tabs = Segmented(["Measures", "Sync", "Trial", "Settings"])
        lay.addWidget(self.tabs)
        self.stack = QStackedWidget()
        self.tabs.changed.connect(self.stack.setCurrentIndex)
        lay.addWidget(self.stack, 1)
        self.stack.addWidget(self._measures())
        self.stack.addWidget(self._sync())
        self.stack.addWidget(self._trial())
        self.stack.addWidget(self._settings())
        # run bar
        run, rv = card()
        self.msg = QLabel("Select a trial in the browser.")
        self.msg.setObjectName("muted")
        self.msg.setWordWrap(True)
        rv.addWidget(self.msg)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        rv.addWidget(self.progress)
        row = QHBoxLayout()
        self.btn_run = QPushButton("Analyse trial")
        self.btn_run.setObjectName("primary")
        self.btn_run.setToolTip("Track body and poles in both views (cached), then compute all measures (⌘R)")
        self.btn_run.setShortcut("Ctrl+R")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        row.addWidget(self.btn_run, 1)
        row.addWidget(self.btn_cancel)
        rv.addLayout(row)
        row = QHBoxLayout()
        self.btn_all = QPushButton("Analyse all trials")
        self.btn_export = QPushButton("Export trial…")
        row.addWidget(self.btn_all)
        row.addWidget(self.btn_export)
        rv.addLayout(row)
        lay.addWidget(run)

    def _scroll(self, w: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(w)
        return sa

    # ---- measures ---------------------------------------------------------------------------
    def _measures(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 4, 0)
        c, cv = card("At the cursor")
        self.live = QTableWidget(0, 3)
        self.live.setHorizontalHeaderLabels(["Measure", "Value", "View"])
        self.live.verticalHeader().setVisible(False)
        _fit(self.live)
        self.live.setMinimumHeight(250)
        self.live.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        cv.addWidget(self.live)
        v.addWidget(c)
        c, cv = card("Trial summary")
        self.summary = QTableWidget(0, 3)
        self.summary.setHorizontalHeaderLabels(["Metric", "Value", "Type"])
        self.summary.verticalHeader().setVisible(False)
        _fit(self.summary)
        self.summary.setMinimumHeight(320)
        self.summary.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        cv.addWidget(self.summary)
        self.quality = QLabel("")
        self.quality.setObjectName("muted")
        self.quality.setWordWrap(True)
        cv.addWidget(self.quality)
        self.btn_report = QPushButton("Open full report")
        cv.addWidget(self.btn_report)
        v.addWidget(c)
        v.addStretch(1)
        return self._scroll(w)

    # ---- sync -------------------------------------------------------------------------------
    def _sync(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 4, 0)
        c, cv = card("Clap synchronisation")
        cv.addWidget(hint("Offset = side time − front time for the same instant. Check the clap frame: both "
                          "views must show the hands meeting."))
        self.sync_info = QLabel("–")
        self.sync_info.setWordWrap(True)
        cv.addWidget(self.sync_info)
        row = QHBoxLayout()
        self.btn_audio = QPushButton("Audio clap")
        self.btn_audio.setToolTip("Clap peak + envelope cross-correlation of the two sound tracks")
        self.btn_visual = QPushButton("Visual clap")
        self.btn_visual.setToolTip("Moment the wrists meet, from tracked poses (needs analysed recordings)")
        row.addWidget(self.btn_audio)
        row.addWidget(self.btn_visual)
        cv.addLayout(row)
        f = QFormLayout()
        self.offset = QDoubleSpinBox()
        self.offset.setRange(-60, 60)
        self.offset.setDecimals(5)
        self.offset.setSingleStep(1 / 60)
        self.offset.setSuffix(" s")
        f.addRow("Offset", self.offset)
        cv.addLayout(f)
        row = QHBoxLayout()
        self.btn_m1 = QPushButton("− 1 frame")
        self.btn_p1 = QPushButton("+ 1 frame")
        row.addWidget(self.btn_m1)
        row.addWidget(self.btn_p1)
        cv.addLayout(row)
        self.drift = QLabel("")
        self.drift.setObjectName("muted")
        self.drift.setWordWrap(True)
        cv.addWidget(self.drift)
        v.addWidget(c)
        c, cv = card("Pairing")
        self.pair_info = QLabel("–")
        self.pair_info.setWordWrap(True)
        cv.addWidget(self.pair_info)
        self.btn_pair = QPushButton("Change paired recording…")
        cv.addWidget(self.btn_pair)
        v.addWidget(c)
        v.addStretch(1)
        return self._scroll(w)

    # ---- trial ------------------------------------------------------------------------------
    def _trial(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 4, 0)
        c, cv = card("Trial")
        f = QFormLayout()
        self.t_part = QLabel("–")
        self.t_cond = QComboBox()
        self.t_num = QSpinBox()
        self.t_num.setRange(1, 99)
        self.t_pole = QDoubleSpinBox()
        self.t_pole.setRange(0, 160)
        self.t_pole.setSuffix(" cm")
        self.t_pole.setSpecialValueText("not set")
        self.t_notes = QLineEdit()
        f.addRow("Participant", self.t_part)
        f.addRow("Condition", self.t_cond)
        f.addRow("Trial number", self.t_num)
        f.addRow("Pole length", self.t_pole)
        f.addRow("Notes", self.t_notes)
        cv.addLayout(f)
        self.btn_body = QPushButton("Body metrics…")
        cv.addWidget(self.btn_body)
        v.addWidget(c)
        c, cv = card("Analysis interval (side-camera clock)")
        f = QFormLayout()
        self.iv_a = QDoubleSpinBox()
        self.iv_b = QDoubleSpinBox()
        for s in (self.iv_a, self.iv_b):
            s.setRange(0, 3600)
            s.setDecimals(3)
            s.setSuffix(" s")
        f.addRow("Start", self.iv_a)
        f.addRow("End", self.iv_b)
        cv.addLayout(f)
        row = QHBoxLayout()
        self.btn_in = QPushButton("Start = cursor  (I)")
        self.btn_out = QPushButton("End = cursor  (O)")
        self.btn_in.setShortcut("I")
        self.btn_out.setShortcut("O")
        row.addWidget(self.btn_in)
        row.addWidget(self.btn_out)
        cv.addLayout(row)
        self.btn_common = QPushButton("Use the whole common window")
        cv.addWidget(self.btn_common)
        v.addWidget(c)
        c, cv = card("Stairs")
        cv.addWidget(self.ws.form.stairs_box)
        v.addWidget(c)
        v.addStretch(1)
        return self._scroll(w)

    # ---- settings ---------------------------------------------------------------------------
    def _settings(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 4, 0)
        c, cv = card("Tracking")
        f = QFormLayout()
        self.p_backend = QComboBox()
        self.p_backend.addItem("RTMPose + YOLOX (recommended)", "rtmpose")
        self.p_backend.addItem("MediaPipe Pose", "mediapipe")
        self.p_mode = QComboBox()
        for lab, val in (("Balanced", "balanced"), ("Accurate (slower)", "performance"), ("Fast", "lightweight")):
            self.p_mode.addItem(lab, val)
        self.p_stride = QComboBox()
        self.p_stride.addItem("Every frame", 1)
        self.p_stride.addItem("Every 2nd frame (2× faster)", 2)
        f.addRow("Body model", self.p_backend)
        f.addRow("Model size", self.p_mode)
        f.addRow("Frames", self.p_stride)
        cv.addLayout(f)
        cv.addWidget(hint("Results are cached per recording and settings, so changing biomechanics settings below "
                          "does not re-run tracking."))
        v.addWidget(c)
        c, cv = card("Scale and side")
        cv.addWidget(self.ws.form.scale_box)
        v.addWidget(c)
        c, cv = card("External forces")
        cv.addWidget(self.ws.form.forces_box)
        v.addWidget(c)
        c, cv = card("Biomechanics model")
        cv.addWidget(self.ws.form.adv_box)
        v.addWidget(c)
        v.addStretch(1)
        return self._scroll(w)


class WorkspacePage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.setObjectName("workspace")
        self.state = state
        self.trial = None
        self.res = None
        self.worker = None
        self.form = AnalysisForm()
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.hsplit = QSplitter(Qt.Orientation.Horizontal)
        self.hsplit.setChildrenCollapsible(True)
        self.browser = ExperimentBrowser(state)
        self.browser.setMinimumWidth(190)
        self.hsplit.addWidget(self.browser)
        center = QWidget()
        center.setObjectName("workspaceCenter")
        center.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.browser.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        cl = QVBoxLayout(center)
        cl.setContentsMargins(6, 10, 6, 10)
        cl.setSpacing(6)
        self.header = QLabel("Select a trial")
        self.header.setObjectName("pageTitle")
        self.subheader = QLabel("")
        self.subheader.setObjectName("pageHint")
        cl.addWidget(self.header)
        cl.addWidget(self.subheader)
        self.vsplit = QSplitter(Qt.Orientation.Vertical)
        self.vsplit.setChildrenCollapsible(False)
        self.video = SyncVideoPanel()
        self.video.labels_fn = self._labels
        self.vsplit.addWidget(self.video)
        pc, pl = card()
        self.plots = DataPlots()
        pl.addWidget(self.plots)
        self.vsplit.addWidget(pc)
        self.vsplit.setSizes([560, 300])
        cl.addWidget(self.vsplit, 1)
        self.hsplit.addWidget(center)
        self.inspector = Inspector(self)
        self.inspector.setObjectName("inspector")
        self.inspector.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.inspector.setMinimumWidth(300)
        self.hsplit.addWidget(self.inspector)
        self.hsplit.setSizes([240, 860, 400])
        self.hsplit.setStretchFactor(1, 1)
        outer.addWidget(self.hsplit)
        # wiring
        self.browser.trialSelected.connect(self.open_trial)
        self.video.timeChanged.connect(self._time_changed)
        self.video.canvasClicked.connect(self._canvas_clicked)
        self.plots.seek.connect(lambda t: self.video.seek(t, force=True))
        ins = self.inspector
        ins.btn_run.clicked.connect(self.run)
        ins.btn_cancel.clicked.connect(lambda: self.worker and self.worker.cancel())
        ins.btn_all.clicked.connect(self.run_all)
        ins.btn_export.clicked.connect(self.export_trial)
        ins.btn_report.clicked.connect(self.open_report)
        ins.btn_audio.clicked.connect(self.sync_audio)
        ins.btn_visual.clicked.connect(self.sync_visual)
        ins.offset.valueChanged.connect(self._offset_changed)
        ins.btn_m1.clicked.connect(lambda: ins.offset.setValue(ins.offset.value() - 1 / self.video.fps()))
        ins.btn_p1.clicked.connect(lambda: ins.offset.setValue(ins.offset.value() + 1 / self.video.fps()))
        ins.btn_in.clicked.connect(lambda: ins.iv_a.setValue(self.video.t))
        ins.btn_out.clicked.connect(lambda: ins.iv_b.setValue(self.video.t))
        ins.btn_common.clicked.connect(self._common_window)
        ins.btn_body.clicked.connect(self.edit_body)
        ins.btn_pair.clicked.connect(self.edit_pairing)
        self.browser.editPairing.connect(lambda tid: (self.open_trial(tid), self.edit_pairing()))
        self.browser.editBody.connect(self._edit_body_pid)
        for wdg in (ins.t_cond,):
            wdg.currentIndexChanged.connect(self._trial_meta_changed)
        ins.t_num.valueChanged.connect(self._trial_meta_changed)
        ins.t_pole.valueChanged.connect(self._trial_meta_changed)
        ins.t_notes.editingFinished.connect(self._trial_meta_changed)
        ins.iv_a.valueChanged.connect(self._interval_changed)
        ins.iv_b.valueChanged.connect(self._interval_changed)
        state.projectChanged.connect(self._project_changed)
        self._loading = False

    # ------------------------------------------------------------------------------------
    @property
    def project(self):
        return self.state.project

    def proc(self) -> dict:
        ins = self.inspector
        return {"backend": ins.p_backend.currentData(), "mode": ins.p_mode.currentData(),
                "stride": ins.p_stride.currentData()}

    def _project_changed(self):
        self.trial = None
        self.res = None
        self.video.load(None, None, 0)
        self.plots.set_result(None)
        self.header.setText("Select a trial" if self.project else "Open or create a study")
        self.subheader.setText("Import recordings with the button in the browser." if self.project else "")
        ins = self.inspector
        ins.t_cond.blockSignals(True)
        ins.t_cond.clear()
        if self.project:
            for c in self.project.conditions:
                ins.t_cond.addItem(f"{c.code} – {c.label}", c.code)
        ins.t_cond.blockSignals(False)

    def open_trial(self, tid: str):
        if self.project is None or (self.trial and self.trial.id == tid and self.video.sources):
            return
        self._loading = True
        t = self.project.trial(tid)
        self.trial = t
        p = self.project.participant(t.participant_id)
        c = self.project.condition(t.condition_code)
        side, front = video_by_role(t, "side"), video_by_role(t, "front")
        self.header.setText(f"{p.id} · Trial {t.trial_number} · {c.label}")
        views = " + ".join(v for v, x in (("side", side), ("front", front)) if x)
        self.subheader.setText(f"{views} view{'s' if side and front else ''} · {t.id}"
                               + ("" if p.metrics_entered else " · body metrics are placeholders"))
        errs = self.video.load(side.path if side else None, front.path if front else None,
                               float(t.sync.get("offset_s", 0.0)))
        if errs:
            error_box(self, "Cannot open video", "\n".join(errs))
        self._attach_cached()
        ins = self.inspector
        ins.t_part.setText(f"{p.id} ({p.body_mass_kg:g} kg, {p.height_m:g} m)")
        ins.t_cond.setCurrentIndex(max(0, ins.t_cond.findData(t.condition_code)))
        ins.t_num.setValue(t.trial_number)
        ins.t_pole.setValue(t.pole_length_cm or 0)
        ins.t_notes.setText(t.notes)
        ins.offset.blockSignals(True)
        ins.offset.setValue(float(t.sync.get("offset_s", 0.0)))
        ins.offset.blockSignals(False)
        ins.offset.setEnabled(bool(side and front))
        self._show_sync()
        a, b = t.interval or [0.0, self.video.t_max]
        ins.iv_a.setValue(a)
        ins.iv_b.setValue(b)
        self.form.load_from(t)
        folder = self.project.root / "trials" / t.id
        self.res = None
        if (folder / "analysis.json").exists():
            try:
                self.res = load_result(folder)
            except Exception as e:  # stale results
                self.state.status.emit(f"Previous results could not be read: {e}")
        self._show_result()
        ins.msg.setText("Results loaded." if self.res else "Not analysed yet. Press Analyse trial.")
        self._loading = False

    def _attach_cached(self):
        for _role, src in self.video.sources.items():
            hit = pipeline.load_cached(self.project.root / "cache", src.info.path, {**PROC_DEFAULT, **self.proc()})
            if hit:
                src.pose, src.poles = hit[0], hit[1]
        self.video.seek(self.video.t, force=True)

    def _labels(self, xy):
        """Raw per-frame 2D knee and elbow angles (unfiltered) drawn next to the joints."""
        from ..core.kinematics import interior_angle
        out = []
        for side, (h, k, a) in (("L", (23, 25, 27)), ("R", (24, 26, 28))):
            if np.isfinite(xy[[h, k, a]]).all():
                ang = 180 - float(interior_angle(xy[h], xy[k], xy[a]))
                out.append((xy[k], f"{side} knee {ang:.0f}°", side))
        return out

    def _show_result(self):
        ins = self.inspector
        self.plots.set_result(self.res)
        ins.summary.clearSpans()
        ins.summary.setRowCount(0)
        ins.quality.setText("")
        if self.res is None:
            return
        rows = []
        present = {m.key: m for m in self.res.metrics}
        for cat, keys in CATEGORIES.items():
            ms = [present[k] for k in keys if k in present]
            if ms:
                rows.append(cat)
                rows.extend(ms)
        ins.summary.setRowCount(len(rows))
        from PySide6.QtGui import QColor, QFont
        for r, m in enumerate(rows):
            if isinstance(m, str):           # category header row
                it = QTableWidgetItem(m)
                f = QFont(it.font())
                f.setBold(True)
                it.setFont(f)
                ins.summary.setItem(r, 0, it)
                ins.summary.setSpan(r, 0, 1, 3)
                continue
            info = INFO[m.key]
            val = "–" if m.value is None else f"{fmt(m.value)} {info.unit}"
            items = [info.label, val, SHORT_KINDS[m.kind]]
            for c_i, txt in enumerate(items):
                it = QTableWidgetItem(txt)
                if c_i == 0:
                    it.setToolTip(f"{info.what}\n\nWhy: {info.why}\nCannot conclude: {info.not_conclude}"
                                  + (f"\n\nNote: {m.note}" if m.note else "") + f"\nView: {m.view}")
                if c_i == 2:
                    bg, fg = EVIDENCE_COLORS[m.kind]
                    it.setBackground(QColor(bg))
                    it.setForeground(QColor(fg))
                ins.summary.setItem(r, c_i, it)
        q = self.res.quality
        parts = [f"Side: person in {100 * q.get('detection_rate', 0):.0f}% of frames, "
                 f"{q.get('pct_outliers_removed', 0):.1f}% spikes removed, "
                 f"{q.get('pct_interpolated', 0):.1f}% gap-filled"]
        if "front_detection_rate" in q:
            parts.append(f"Front: person in {100 * q['front_detection_rate']:.0f}% of frames")
        if self.res.notes:
            parts.append("Notes: " + " ".join(self.res.notes[:3]))
        ins.quality.setText("\n".join(parts))
        self._time_changed(self.video.t)

    def _time_changed(self, t: float):
        self.plots.set_time(t)
        ins = self.inspector
        if self.res is None:
            ins.live.setRowCount(0)
            return
        ts, s = self.res.timeseries, self.res.side
        k = int(np.argmin(np.abs(ts["time_s"].to_numpy() - t)))
        inside = abs(ts["time_s"].iloc[k] - t) < 0.05
        rows = [("Knee flexion", f"{s}_knee_flexion_deg", "°", "side"), ("Hip flexion", f"{s}_hip_flexion_deg", "°", "side"),
                ("Ankle dorsiflexion", f"{s}_ankle_dorsiflexion_deg", "°", "side"),
                ("Trunk lean", "trunk_lean_deg", "°", "side"), ("Elbow flexion", f"{s}_elbow_flexion_deg", "°", "side"),
                ("Shoulder flexion", f"{s}_shoulder_flexion_deg", "°", "side"),
                ("Knee flexion velocity", f"{s}_knee_flexion_velocity_dps", "°/s", "side"),
                ("Left pole angle", "pole_left_angle_deg", "°", "side"), ("Right pole angle", "pole_right_angle_deg", "°", "side"),
                ("Left pole confidence", "pole_left_tracking_conf", "", "side"),
                ("Right pole confidence", "pole_right_tracking_conf", "", "side"),
                ("Knee FPPA left", "front_left_knee_fppa_deg", "°", "front"),
                ("Knee FPPA right", "front_right_knee_fppa_deg", "°", "front"),
                ("Trunk lateral lean", "front_trunk_lateral_lean_deg", "°", "front"),
                ("Knee extensor moment", f"{s}_knee_extensor_moment_nm", "N·m", "model")]
        vals = []
        for lab, col, unit, view in rows:
            if col in ts:
                v = ts[col].iloc[k] if inside else np.nan
                vals.append((lab, "–" if not np.isfinite(v) else (f"{v:.2f}" if unit == "" else f"{v:.0f} {unit}"), view))
        ins.live.setRowCount(len(vals))
        for r, (a, b, c) in enumerate(vals):
            for j, txt in enumerate((a, b, c)):
                ins.live.setItem(r, j, QTableWidgetItem(txt))

    def _canvas_clicked(self, role, x, y):
        pass

    # ---- trial meta ---------------------------------------------------------------------------
    def _trial_meta_changed(self, *_):
        if self._loading or not self.trial:
            return
        ins = self.inspector
        t = self.trial
        new_code = ins.t_cond.currentData()
        if new_code and new_code != t.condition_code:
            t.condition_code = new_code
        t.trial_number = ins.t_num.value()
        t.pole_length_cm = ins.t_pole.value() or None
        t.notes = ins.t_notes.text()
        self.state.save()
        self.state.trialsChanged.emit()

    def _interval_changed(self):
        if self._loading or not self.trial:
            return
        a, b = self.inspector.iv_a.value(), self.inspector.iv_b.value()
        if b > a:
            self.trial.interval = [a, b]
            self.state.save()
            self.inspector.msg.setText(f"Interval {a:.2f}–{b:.2f} s. Re-analyse to apply it.")
        else:
            self.inspector.msg.setText("The end of the interval must be after the start; interval not changed.")

    def _common_window(self):
        v = self.video
        if len(v.sources) == 2:
            fs, ff = v.sources["side"].info.duration, v.sources["front"].info.duration
            try:
                a, b = sync.common_window(fs, ff, v.offset)
            except ValueError as e:
                error_box(self, "No overlap", str(e))
                return
        else:
            a, b = 0.0, v.t_max
        self.inspector.iv_a.setValue(a)
        self.inspector.iv_b.setValue(b)

    # ---- sync -------------------------------------------------------------------------------
    def _show_sync(self):
        t = self.trial
        ins = self.inspector
        s = t.sync if t else {}
        if not t or len(t.videos) < 2:
            ins.sync_info.setText("Single-view trial: no synchronisation needed.")
            ins.pair_info.setText("No paired recording. Use 'Change paired recording…' to add one.")
            return
        ins.sync_info.setText(f"Offset {s.get('offset_s', 0):+.4f} s · method: {s.get('method', 'not set')}"
                              + (f" · clap clarity {s['confidence']:.0f}×" if s.get("confidence") else ""))
        if s.get("pair_score") is not None:
            ins.pair_info.setText(f"Paired by audio match {s['pair_score']:.2f} "
                                  f"(margin {s.get('pair_margin', 0):+.2f}, {s.get('pair_status')}).")
        else:
            ins.pair_info.setText("Pairing set manually.")
        if s.get("drift_ms_per_min") is not None:
            ins.drift.setText(f"Clock drift check: {s['drift_ms_per_min']:+.0f} ms/min "
                              f"({'below one frame over this trial, no correction applied' if abs(s['drift_ms_per_min']) * self.video.t_max / 60 < 1000 / self.video.fps() else 'larger than one frame: check sync at the end of the trial'}).")
        else:
            ins.drift.setText("")

    def _offset_changed(self, v):
        if self._loading or not self.trial:
            return
        self.trial.sync["offset_s"] = float(v)
        if not str(self.trial.sync.get("method", "")).endswith("adjusted"):
            self.trial.sync["method"] = f"{self.trial.sync.get('method', 'manual')}+adjusted"
        self.video.set_offset(float(v))
        self.state.save()
        self._show_sync()

    def _apply_offset(self, off: float, method: str, extra: dict | None = None):
        self.trial.sync.update({"offset_s": float(off), "method": method, **(extra or {})})
        self._loading = True
        self.inspector.offset.setValue(off)
        self._loading = False
        self.video.set_offset(off)
        self.state.save()
        self._show_sync()

    def sync_audio(self):
        from ..core import dataset
        t = self.trial
        side, front = video_by_role(t, "side"), video_by_role(t, "front")
        if not (side and front):
            return
        try:
            es, ef = dataset.audio_envelope(side.path), dataset.audio_envelope(front.path)
            r, lag = dataset.envelope_ncc(es, ef)
            from ..core.video import extract_audio
            a_s, sr = extract_audio(side.path)
            a_f, _ = extract_audio(front.path)
            clap = sync.sync_audio(a_s, a_f, sr, (0, 5), (0, 5))
            drift = sync.estimate_drift(es, ef, dataset.ENV_HOP_S, lag)
        except Exception as e:
            error_box(self, "Audio sync failed", f"{e}\n\nUse the visual clap or adjust the offset by hand.")
            return
        # Decision: the clap peak gives sub-frame precision; the whole-recording envelope correlation is the
        # robust cross-check. Use the clap when it is clear and agrees (or the envelope is inconclusive).
        clap_ok = clap.confidence is not None and clap.confidence >= sync.CONF_MIN
        if clap_ok and (r < 0.3 or abs(clap.offset_s - lag) < 0.05):
            use, method = clap.offset_s, "audio clap"
        elif r >= 0.3:
            use, method = lag, "audio envelope"
        else:
            use, method = clap.offset_s, "audio clap (low confidence: check visually)"
        self._apply_offset(use, method, {"confidence": clap.confidence, "envelope_r": r,
                                         "drift_ms_per_min": drift.get("drift_ms_per_min")})
        self.video.seek(clap.clap_a_s, force=True)

    def sync_visual(self):
        srcs = self.video.sources
        if len(srcs) < 2 or not all(s.pose is not None for s in srcs.values()):
            error_box(self, "Analyse first", "The visual clap needs tracked poses in both views. Run the analysis "
                      "(tracking is cached), then try again.")
            return
        ts, cs = sync.visual_clap(srcs["side"].pose)
        tf, cf = sync.visual_clap(srcs["front"].pose)
        if ts is None or tf is None:
            error_box(self, "No clap found", "The hands were not seen meeting in the first 5 s of both views.")
            return
        self._apply_offset(ts - tf, "visual clap", {"confidence": None, "visual_conf": min(cs, cf)})
        self.video.seek(ts, force=True)

    # ---- run --------------------------------------------------------------------------------
    def _busy(self, on: bool):
        ins = self.inspector
        ins.btn_run.setEnabled(not on)
        ins.btn_all.setEnabled(not on)
        ins.btn_cancel.setEnabled(on)
        ins.progress.setVisible(on)

    def run(self):
        if not self.trial:
            error_box(self, "Select a trial", "Choose a trial in the experiment browser first.")
            return
        try:
            settings = self.form.settings()
        except ValueError as e:
            error_box(self, "Check settings", str(e))
            return
        self.form.store_into(self.trial)
        trial, proc = self.trial, self.proc()
        self.worker = Worker(lambda progress, cancelled: run_pair(self.project, trial, settings, proc, progress, cancelled))
        self.worker.progress.connect(self._on_progress)  # bound method -> queued to the UI thread
        self.worker.finished.connect(self._done)
        self.worker.failed.connect(self._failed)
        self._busy(True)
        self.thread = start_worker(self, self.worker)

    def _on_progress(self, f: float, m: str):
        self.inspector.progress.setValue(int(100 * f))
        self.inspector.msg.setText(m)

    def _done(self, res):
        self._busy(False)
        self.inspector.msg.setText("Analysis complete. Results saved with the trial.")
        self.res = res
        self._attach_cached()
        self._show_result()
        self.state.trialsChanged.emit()
        self.state.resultsChanged.emit()

    def _failed(self, msg):
        self._busy(False)
        self.inspector.msg.setText(msg)
        if "cancelled" not in msg.lower():
            error_box(self, "Analysis failed", msg)

    def run_all(self):
        if self.project is None or not self.project.trials:
            return
        try:
            settings = self.form.settings()
        except ValueError as e:
            error_box(self, "Check settings", str(e))
            return
        proc = self.proc()
        trials = list(self.project.trials)

        def job(progress, cancelled):
            import copy
            done, failed = 0, []
            for i, t in enumerate(trials):
                if cancelled():
                    break
                try:
                    run_pair(self.project, t, copy.deepcopy(settings), proc,
                             lambda f, m, i=i: progress((i + f) / len(trials), f"{t.id}: {m}"), cancelled)
                    done += 1
                except Exception as e:  # keep going; report at the end
                    failed.append(f"{t.id}: {e}")
            return done, failed

        self.worker = Worker(job)
        self.worker.progress.connect(self._on_progress)  # bound method -> queued to the UI thread
        self.worker.finished.connect(self._all_done)
        self.worker.failed.connect(self._failed)
        self._busy(True)
        self.thread = start_worker(self, self.worker)

    def _all_done(self, out):
        done, failed = out
        self._busy(False)
        self.inspector.msg.setText(f"Analysed {done} trial(s)." + (f" {len(failed)} failed." if failed else ""))
        if failed:
            QMessageBox.warning(self, "Some trials failed", "\n".join(failed[:12]))
        self.state.trialsChanged.emit()
        self.state.resultsChanged.emit()
        if self.trial:
            tid = self.trial.id
            self.trial = None
            self.open_trial(tid)

    # ---- dialogs ------------------------------------------------------------------------------
    def edit_body(self):
        if self.trial:
            self._edit_body_pid(self.trial.participant_id)

    def _edit_body_pid(self, pid):
        from .project_page import ParticipantDialog
        part = self.project.participant(pid)
        dlg = ParticipantDialog(self, part)
        if dlg.exec():
            v = dlg.value()
            try:
                v.validate()
            except ValueError as e:
                error_box(self, "Check body metrics", str(e))
                return
            for k in ("body_mass_kg", "height_m", "leg_length_m", "standard_pole_length_cm", "segments", "notes"):
                setattr(part, k, getattr(v, k))
            part.metrics_entered = True
            self.state.save()
            self.state.trialsChanged.emit()
            self.state.status.emit("Body metrics saved. Re-analyse to use them.")

    def edit_pairing(self):
        from .pairing_dialog import PairingDialog
        if not self.trial:
            return
        dlg = PairingDialog(self, self.project, self.trial)
        if dlg.exec():
            self.state.save()
            self.state.trialsChanged.emit()
            tid = self.trial.id
            self.trial = None
            self.open_trial(tid)

    def open_report(self):
        if self.res is None:
            error_box(self, "No results", "Analyse the trial first.")
            return
        from PySide6.QtWidgets import QDialog
        from .report_view import ReportView
        d = QDialog(self)
        d.setWindowTitle(f"Report · {self.trial.id}")
        d.resize(1100, 820)
        lay = QVBoxLayout(d)
        rv = ReportView()
        lay.addWidget(rv)
        c = self.project.condition(self.trial.condition_code)
        rv.show_result(self.res, f"{self.trial.id}: {c.label}")
        d.exec()

    def export_trial(self):
        if self.res is None or not self.trial:
            error_box(self, "No results", "Analyse the trial first.")
            return
        d = QFileDialog.getExistingDirectory(self, "Export trial to folder")
        if not d:
            return
        from ..core.export import export_trial
        try:
            files = export_trial(self.project, self.trial, self.res, d, self.proc())
        except Exception as e:
            error_box(self, "Export failed", str(e))
            return
        self.state.status.emit(f"Exported {len(files)} files to {d}")


__all__ = ["WorkspacePage", "json", "Path"]
