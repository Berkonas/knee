"""Biomechanics workspace: knee and upper-limb loads of the selected trial, the assumptions behind them,
and a free-body diagram that shows where each force acts.

Changing an assumption re-runs only the biomechanics on the cached tracking (no pose estimation).
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QSlider, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.analysis import LOAD_MODES, AnalysisSettings, load_result
from ..core.anthropometry import G
from ..core.metrics import INFO, SHORT_KINDS
from .result_view import fmt
from .theme import EVIDENCE_COLORS, tok
from .widgets import Worker, error_box, start_worker

LOAD_KEYS = ["knee_ext_moment_peak", "knee_ext_moment_peak_nm", "quad_force_peak", "quad_force_peak_bw",
             "knee_power_absorption_peak", "knee_neg_work", "knee_ext_impulse_total", "elbow_moment_peak",
             "elbow_moment_peak_per_kg", "shoulder_moment_peak", "shoulder_moment_peak_per_kg", "pole_support_fraction",
             "tibiofemoral_compression"]


class FreeBodyView(QWidget):
    """Sagittal free-body diagram at one frame: segments, foot force at the COP, the knee moment arm (the
    perpendicular distance from the knee to the force line), and the pole force with the shoulder lever arm."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 300)
        self.frame: dict = {}

    def set_frame(self, fr: dict):
        self.frame = fr
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(tok("surface")))
        fr = self.frame
        ink, muted = QColor(tok("ink")), QColor(tok("muted"))
        if not fr or "knee" not in fr:
            p.setPen(muted)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       fr.get("message", "Select an analysed trial.") if fr else "Select an analysed trial.")
            return
        pts = [v for k, v in fr.items() if isinstance(v, np.ndarray) and v.shape == (2,) and np.isfinite(v).all()
               and not k.endswith("_f")]
        arr = np.array(pts)
        lo, hi = arr.min(0), arr.max(0)
        span = max(hi[0] - lo[0], hi[1] - lo[1], 0.5) * 1.35
        c = (lo + hi) / 2
        W, H = self.width(), self.height() - 46
        sc = min(W, H) / span

        def X(v):
            return QPointF(W / 2 + (v[0] - c[0]) * sc, 12 + H / 2 - (v[1] - c[1]) * sc)

        def ok(*ks):
            return all(k in fr and np.isfinite(fr[k]).all() for k in ks)

        seg = QPen(ink, 3)
        p.setPen(seg)
        for a, b in (("hip", "knee"), ("knee", "ankle"), ("heel", "toe"), ("ankle", "heel"), ("shoulder", "hip"),
                     ("shoulder", "elbow"), ("elbow", "wrist")):
            if ok(a, b):
                p.drawLine(X(fr[a]), X(fr[b]))
        p.setBrush(ink)
        for k in ("hip", "knee", "ankle", "shoulder", "elbow"):
            if ok(k):
                p.drawEllipse(X(fr[k]), 4, 4)
        bw = fr.get("bw_n") or 700.0
        n_per_m = bw / 0.55  # one body weight is drawn 0.55 m long

        def arrow(at, f, col, label):
            if not (np.isfinite(at).all() and np.isfinite(f).all()) or np.hypot(*f) < 1:
                return
            tip = at + f / n_per_m
            p.setPen(QPen(col, 3))
            p.drawLine(X(at), X(tip))
            d = (tip - at) / max(np.hypot(*(tip - at)), 1e-9)
            nrm = np.array([-d[1], d[0]])
            head = QPainterPath(X(tip))
            head.lineTo(X(tip - 0.05 * d + 0.025 * nrm))
            head.lineTo(X(tip - 0.05 * d - 0.025 * nrm))
            head.closeSubpath()
            p.fillPath(head, col)
            p.setPen(col)
            p.drawText(X(tip) + QPointF(6, -4), label)

        foot_col, pole_col = QColor(tok("accent")), QColor("#C77700")
        if ok("cop", "grf_f"):
            p.setBrush(foot_col)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(X(fr["cop"]), 5, 5)
            arrow(fr["cop"], fr["grf_f"], foot_col, f"F foot {np.hypot(*fr['grf_f']):.0f} N")
            if ok("knee"):  # perpendicular from the knee to the force line
                u = fr["grf_f"] / np.hypot(*fr["grf_f"])
                foot = fr["cop"] + np.dot(fr["knee"] - fr["cop"], u) * u
                pen = QPen(foot_col, 1.5, Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.drawLine(X(fr["cop"]), X(fr["cop"] + u * max(np.dot(fr["knee"] - fr["cop"], u) * 1.15, 0.3)))
                p.drawLine(X(fr["knee"]), X(foot))
                d = np.hypot(*(fr["knee"] - foot))
                p.drawText(X((fr["knee"] + foot) / 2) + QPointF(6, 14), f"d = {100 * d:.1f} cm")
        if ok("com"):
            p.setPen(QPen(muted, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(X(fr["com"]), 6, 6)
            p.drawText(X(fr["com"]) + QPointF(9, 4), "COM")
        if ok("grip", "pole_f"):
            if ok("tip"):
                p.setPen(QPen(pole_col, 2))
                p.drawLine(X(fr["grip"]), X(fr["tip"]))
            arrow(fr["grip"], fr["pole_f"], pole_col, f"F pole {np.hypot(*fr['pole_f']):.0f} N")
            if ok("shoulder"):
                p.setPen(QPen(pole_col, 1.5, Qt.PenStyle.DashLine))
                p.drawLine(X(fr["shoulder"]), X(fr["grip"]))
        # caption
        p.setPen(ink)
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        p.drawText(12, self.height() - 26, fr.get("caption1", ""))
        p.setPen(muted)
        p.setFont(self.font())
        p.drawText(12, self.height() - 8, fr.get("caption2", ""))


class BiomechanicsPage(QWidget):
    seekRequested = Signal(float)

    def __init__(self, state):
        super().__init__()
        self.setObjectName("page")
        self.state = state
        self.res = None
        self.trial = None
        self.thread = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(10)
        self.title = QLabel("Biomechanics")
        self.title.setObjectName("pageTitle")
        self.sub = QLabel("Select a trial in Analyse.")
        self.sub.setObjectName("muted")
        self.sub.setWordWrap(True)
        lay.addWidget(self.title)
        lay.addWidget(self.sub)
        self.warn = QLabel("")
        self.warn.setObjectName("warnBanner")
        self.warn.setWordWrap(True)
        self.warn.hide()
        lay.addWidget(self.warn)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.fbd = FreeBodyView()
        lv.addWidget(self.fbd, 3)
        row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(self._frame_changed)
        self.btn_peak = QPushButton("Peak knee moment")
        self.btn_peak.clicked.connect(self._go_peak)
        self.btn_video = QPushButton("Show in video")
        self.btn_video.clicked.connect(lambda: self.seekRequested.emit(self._t()))
        row.addWidget(self.slider, 1)
        row.addWidget(self.btn_peak)
        row.addWidget(self.btn_video)
        lv.addLayout(row)
        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(180)
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setLabel("left", "Moment (N·m)")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.scene().sigMouseClicked.connect(self._plot_clicked)
        self.cursor = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#D9534F"))
        self.plot.addItem(self.cursor)
        self.plot_legend = QLabel("")
        self.plot_legend.setObjectName("muted")
        lv.addWidget(self.plot_legend)
        lv.addWidget(self.plot, 2)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)
        cap = QLabel("Loads")
        cap.setObjectName("cardTitle")
        rv.addWidget(cap)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Quantity", "Value", "Range", "Type"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        from PySide6.QtWidgets import QHeaderView
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setWordWrap(False)
        rv.addWidget(self.table, 2)
        cap2 = QLabel("Assumptions")
        cap2.setObjectName("cardTitle")
        rv.addWidget(cap2)
        box = QFrame()
        f = QFormLayout(box)
        self.mode = QComboBox()
        for k, lab in LOAD_MODES.items():
            self.mode.addItem(lab, k)
        self.pole_pct = QDoubleSpinBox(); self.pole_pct.setRange(0, 50); self.pole_pct.setSuffix(" % BW per pole")
        self.cop = QDoubleSpinBox(); self.cop.setRange(0, 1); self.cop.setSingleStep(0.05)
        self.cop.setToolTip("Centre of pressure along the foot: 0 = heel, 1 = toes")
        self.gdir = QComboBox()
        self.gdir.addItem("Toward body centre of mass", "com")
        self.gdir.addItem("Vertical (upper bound)", "vertical")
        self.arm = QDoubleSpinBox(); self.arm.setRange(2, 8); self.arm.setSuffix(" cm"); self.arm.setDecimals(1)
        f.addRow("Mode", self.mode)
        f.addRow("Pole force", self.pole_pct)
        f.addRow("Centre of pressure", self.cop)
        f.addRow("Foot force direction", self.gdir)
        f.addRow("Knee extensor moment arm", self.arm)
        rv.addWidget(box)
        self.btn_apply = QPushButton("Recalculate loads")
        self.btn_apply.setObjectName("primary")
        self.btn_apply.setToolTip("Re-runs the biomechanics on the saved tracking. No pose estimation is repeated.")
        self.btn_apply.clicked.connect(self.recalculate)
        rv.addWidget(self.btn_apply)
        self.eq = QLabel("")
        self.eq.setWordWrap(True)
        self.eq.setObjectName("muted")
        self.eq.setTextFormat(Qt.TextFormat.RichText)
        rv.addWidget(self.eq, 1)
        right.setMinimumWidth(420)
        for w in (self.mode, self.gdir):
            w.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        lay.addWidget(split, 1)
        state.resultsChanged.connect(self.refresh)
        state.trialSelected.connect(self.show_trial)

    # ---- data -------------------------------------------------------------------------------
    def show_trial(self, tid: str):
        p = self.state.project
        if p is None:
            return
        try:
            self.trial = p.trial(tid)
        except KeyError:
            self.trial = None
        self.refresh()

    def refresh(self):
        p, t = self.state.project, self.trial
        self.res = None
        if p is None or t is None or t not in p.trials:
            self.sub.setText("Select a trial in Analyse.")
            self.fbd.set_frame({})
            self.table.setRowCount(0)
            return
        folder = p.root / "trials" / t.id
        if (folder / "analysis.json").exists():
            try:
                self.res = load_result(folder)
            except Exception:
                self.res = None
        part = p.participant(t.participant_id)
        s = {**AnalysisSettings().__dict__, **(t.settings or {})}
        self.mode.setCurrentIndex(max(0, self.mode.findData(s.get("load_mode", "video"))))
        self.pole_pct.setValue(float(s.get("pole_pct_bw", 10.0)))
        self.cop.setValue(float(s.get("cop_fraction", 0.5)))
        self.gdir.setCurrentIndex(max(0, self.gdir.findData(s.get("grf_direction", "com"))))
        self.arm.setValue(100 * float(s.get("moment_arm_m", 0.05)))
        self.title.setText(f"{t.id} · biomechanics")
        self.sub.setText(f"{p.condition(t.condition_code).label} · mode {LOAD_MODES.get(s.get('load_mode', 'video'))}")
        missing = []
        if part.body_mass_kg is None:
            missing.append("body mass")
        if part.height_m is None and s.get("scale_method") == "height":
            missing.append("height (or a calibrated distance)")
        msg = []
        if missing:
            msg.append(f"Enter {' and '.join(missing)} for {part.id} (right-click the participant > Participant information).")
        if s.get("load_mode", "video") == "video":
            msg.append("Mode A (video only): no forces or moments are estimated. Choose mode B to see assumption-based "
                       "loads, or C with imported force data.")
        if self.res is None:
            msg.append("This trial has not been analysed yet.")
        self.warn.setText("  ".join(msg))
        self.warn.setVisible(bool(msg))
        self._fill_table()
        self._fill_plot()
        self._fill_equations(part)

    def _fill_table(self):
        self.table.setRowCount(0)
        if self.res is None:
            return
        rows = [m for k in LOAD_KEYS if (m := self.res.metric(k)) is not None]
        self.table.setRowCount(len(rows))
        for r, m in enumerate(rows):
            info = INFO[m.key]
            rng = f"{fmt(m.low)}–{fmt(m.high)}" if m.low is not None and m.high is not None else ""
            items = [info.label, "–" if m.value is None else f"{fmt(m.value)} {info.unit}", rng, SHORT_KINDS[m.kind]]
            for c, txt in enumerate(items):
                it = QTableWidgetItem(txt)
                tip = f"{info.what}\nNot: {info.not_conclude}" + (f"\n\n{m.note}" if m.note else "")
                it.setToolTip(tip)
                if c == 3:
                    bg, fg = EVIDENCE_COLORS[m.kind]
                    dark = self.table.palette().base().color().lightness() < 128
                    it.setForeground(QColor(bg if dark else fg))
                self.table.setItem(r, c, it)
        self.table.resizeRowsToContents()

    def _fill_plot(self):
        self.plot.clear()
        self.plot.addItem(self.cursor)
        self.plot.setBackground(tok("bg"))
        self.plot.getViewBox().setBackgroundColor(tok("surface"))
        for ax in ("left", "bottom"):
            self.plot.getAxis(ax).setTextPen(tok("muted"))
            self.plot.getAxis(ax).setPen(tok("line_strong"))
        ts = self.res.timeseries if self.res is not None else None
        self.slider.blockSignals(True)
        if ts is None or len(ts) == 0:
            self.slider.setRange(0, 0)
            self.slider.blockSignals(False)
            self.fbd.set_frame({"message": "Not analysed yet."})
            self.plot_legend.setText("")
            return
        t = ts["time_s"].to_numpy()
        side = self.res.side
        series = [(f"{side}_knee_extensor_moment_nm", "Knee extensor moment", tok("accent")),
                  ("left_shoulder_moment_nm", "Left shoulder moment", "#C77700"),
                  ("right_shoulder_moment_nm", "Right shoulder moment", "#E0A23B"),
                  ("left_elbow_moment_nm", "Left elbow moment", "#8E6CC7"),
                  ("right_elbow_moment_nm", "Right elbow moment", "#B79BE6")]
        shown = []
        for col, lab, colr in series:
            if col in ts:
                self.plot.plot(t, ts[col].to_numpy(), pen=pg.mkPen(colr, width=2), connect="finite")
                shown.append(f'<span style="color:{colr}">━</span> {lab}')
        st = ts.get(f"{side}_stance")
        if st is not None:
            on = st.to_numpy().astype(bool)
            edges = np.flatnonzero(np.diff(np.concatenate(([0], on.astype(int), [0]))))
            for a, b in zip(edges[::2], edges[1::2]):
                reg = pg.LinearRegionItem((t[a], t[b - 1]), movable=False, brush=pg.mkBrush(120, 170, 160, 35),
                                          pen=pg.mkPen(None))
                self.plot.addItem(reg)
        self.plot_legend.setText("   ".join(shown + ["▮ stance"]) if shown else
                                 "No load time series for this trial (see the message above).")
        self.slider.setRange(0, len(t) - 1)
        self.slider.blockSignals(False)
        self._go_peak()

    def _fill_equations(self, part):
        s = self.trial.settings or {}
        mass = part.body_mass_kg
        self.eq.setText(
            "<b>Knee</b>: M<sub>knee</sub> = (x<sub>knee</sub> − x<sub>COP</sub>)·F<sub>y</sub> + "
            "(y<sub>COP</sub> − y<sub>knee</sub>)·F<sub>x</sub> = |F|·d<br>"
            "F<sub>foot,y</sub> = share × (m·g − Σ F<sub>pole</sub>·cos θ<sub>pole</sub>)"
            + (f", m·g = {mass * G:.0f} N" if mass else "") + "<br>"
            "<b>Quadriceps-equivalent force</b>: F<sub>quad</sub> = M<sub>knee</sub> / r "
            f"(r = {100 * float(s.get('moment_arm_m', 0.05)):.1f} cm, range 4–6 cm). Not tendon or joint contact force.<br>"
            "<b>Shoulder</b>: M<sub>shoulder</sub> = (r<sub>grip</sub> − r<sub>shoulder</sub>) × F<sub>pole</sub> + "
            "arm weight terms; elbow likewise.<br>The same pole force enters the knee and arm models.")

    # ---- frame display ------------------------------------------------------------------------
    def _t(self) -> float:
        if self.res is None or not len(self.res.timeseries):
            return 0.0
        return float(self.res.timeseries["time_s"].iloc[self.slider.value()])

    def _go_peak(self):
        if self.res is None:
            return
        col = f"{self.res.side}_knee_extensor_moment_nm"
        ts = self.res.timeseries
        if col in ts and np.isfinite(ts[col]).any():
            self.slider.setValue(int(np.nanargmax(ts[col].to_numpy())))
        else:
            self._frame_changed(self.slider.value())

    def _plot_clicked(self, ev):
        if self.res is None:
            return
        x = self.plot.plotItem.vb.mapSceneToView(ev.scenePos()).x()
        t = self.res.timeseries["time_s"].to_numpy()
        self.slider.setValue(int(np.argmin(np.abs(t - x))))

    def _frame_changed(self, i: int):
        if self.res is None or not len(self.res.timeseries):
            return
        ts = self.res.timeseries
        row = ts.iloc[i]
        side = self.res.side
        self.cursor.setValue(float(row["time_s"]))
        u = "m" if f"{side}_knee_x_m" in ts else None
        if u is None:
            self.fbd.set_frame({"message": "No metric scale for this trial, so the free-body diagram cannot be drawn."})
            return

        def P(name, s=side):
            k = f"{s}_{name}_x_m"
            return np.array([row.get(k, np.nan), row.get(f"{s}_{name}_y_m", np.nan)], float)

        fr = {"hip": P("hip"), "knee": P("knee"), "ankle": P("ankle"), "heel": P("heel"), "toe": P("foot_index"),
              "shoulder": P("shoulder"), "elbow": P("elbow"), "wrist": P("wrist")}
        part = self.state.project.participant(self.trial.participant_id)
        fr["bw_n"] = part.body_mass_kg * G if part.body_mass_kg else None
        if f"{side}_cop_x_m" in ts:
            fr["cop"] = np.array([row[f"{side}_cop_x_m"], row[f"{side}_cop_y_m"]], float)
            fr["grf_f"] = np.array([row[f"{side}_grf_x_n"], row[f"{side}_grf_y_n"]], float)
        if "com_x_m" in ts:
            fr["com"] = np.array([row["com_x_m"], row["com_y_m"]], float)
        for ps in (side, "left" if side == "right" else "right"):
            if f"pole_{ps}_force_x_n" in ts and np.isfinite(row[f"pole_{ps}_force_x_n"]):
                fr["grip"] = P("grip", ps)
                fr["pole_f"] = np.array([row[f"pole_{ps}_force_x_n"], row[f"pole_{ps}_force_y_n"]], float)
                if f"pole_{ps}_tip_x_m" in ts:
                    fr["tip"] = np.array([row[f"pole_{ps}_tip_x_m"], row[f"pole_{ps}_tip_y_m"]], float)
                if ps != side:  # draw that arm instead
                    for nm in ("shoulder", "elbow", "wrist"):
                        fr[nm] = P(nm, ps)
                break
        mk = row.get(f"{side}_knee_extensor_moment_nm", np.nan)
        sh = [row.get(f"{s}_shoulder_moment_nm", np.nan) for s in ("left", "right")]
        sh = [v for v in sh if np.isfinite(v)]
        fr["caption1"] = (f"t = {row['time_s']:.2f} s   M knee = {mk:.0f} N·m" if np.isfinite(mk) else
                          f"t = {row['time_s']:.2f} s   no foot force at this frame (swing or mode A)")
        if sh:
            fr["caption1"] += f"   M shoulder = {max(sh, key=abs):.1f} N·m"
        kind = self.res.metric("knee_ext_moment_peak")
        fr["caption2"] = ("Scenario estimate from stated assumptions" if kind and kind.kind == "scenario" else
                          "Inverse dynamics with measured force" if kind and kind.kind == "model" else
                          "Kinematics only: forces are not shown")
        self.fbd.set_frame(fr)

    # ---- recalculation --------------------------------------------------------------------------
    def recalculate(self):
        if self.trial is None or self.state.project is None:
            return
        from ..core.runner import run_pair

        t = self.trial
        st = dict(t.settings or {})
        known = AnalysisSettings.__dataclass_fields__
        base = {k: v for k, v in st.items() if k in known}
        if isinstance(base.get("moment_arm_range_m"), list):
            base["moment_arm_range_m"] = tuple(base["moment_arm_range_m"])
        base.update(load_mode=self.mode.currentData(), pole_pct_bw=self.pole_pct.value(), cop_fraction=self.cop.value(),
                    grf_direction=self.gdir.currentData(), moment_arm_m=self.arm.value() / 100)
        if base["load_mode"] == "scenario" and base.get("pole_force_mode", "none") == "none" and \
                self.state.project.condition(t.condition_code).uses_poles:
            base["pole_force_mode"] = "scenario"
        settings = AnalysisSettings(**base)
        proc = None  # default tracking settings: the cached tracking is reused
        self.btn_apply.setEnabled(False)
        self.btn_apply.setText("Recalculating…")
        self.worker = Worker(lambda progress, cancelled: run_pair(self.state.project, t, settings, proc, progress,
                                                                    cancelled))
        self.worker.finished.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.thread = start_worker(self, self.worker)

    def _done(self, _res):
        self.btn_apply.setEnabled(True)
        self.btn_apply.setText("Recalculate loads")
        self.state.save()
        self.state.resultsChanged.emit()

    def _failed(self, msg):
        self.btn_apply.setEnabled(True)
        self.btn_apply.setText("Recalculate loads")
        error_box(self, "Recalculation failed", msg)


__all__ = ["BiomechanicsPage", "FreeBodyView", "QSizePolicy"]
