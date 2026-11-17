"""Interactive biomechanics plots (pyqtgraph) linked to the video: the red cursor follows playback;
clicking or dragging in a plot moves the video to that instant. Stance phases and pole plants are
drawn as event markers."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from .theme import tok

PEN = ["#1F77B4", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]

GROUPS = {
    "Joint angles": [("{s}_knee_flexion_deg", "Knee flexion"), ("{s}_hip_flexion_deg", "Hip flexion"),
                     ("{s}_ankle_dorsiflexion_deg", "Ankle dorsiflexion"), ("trunk_lean_deg", "Trunk lean")],
    "Arms": [("{s}_elbow_flexion_deg", "Elbow flexion"), ("{s}_shoulder_flexion_deg", "Shoulder flexion"),
             ("{s}_forearm_orientation_deg", "Forearm from vertical")],
    "Poles": [("pole_left_angle_deg", "Left pole (side view)"), ("pole_right_angle_deg", "Right pole (side view)"),
              ("front_pole_left_angle_deg", "Left pole (front view)"), ("front_pole_right_angle_deg", "Right pole (front view)")],
    "Velocity": [("{s}_knee_flexion_velocity_dps", "Knee"), ("{s}_hip_flexion_velocity_dps", "Hip"),
                 ("{s}_ankle_dorsiflexion_velocity_dps", "Ankle")],
    "Front view": [("front_left_knee_fppa_deg", "Left knee FPPA"), ("front_right_knee_fppa_deg", "Right knee FPPA"),
                   ("front_trunk_lateral_lean_deg", "Trunk lateral lean"), ("front_pelvic_obliquity_deg", "Pelvic tilt")],
    "Knee load": [("{s}_knee_extensor_moment_nm", "Knee extensor moment (N·m)"),
                  ("{s}_knee_ext_impulse_cum_nms_per_kg", "Cumulative impulse (N·m·s/kg)")],
}
UNITS = {"Joint angles": "deg (2D)", "Arms": "deg (2D)", "Poles": "deg from vertical", "Velocity": "deg/s",
         "Front view": "deg (2D, front)", "Knee load": "model estimate"}


class DataPlots(QWidget):
    seek = Signal(float)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        head = QHBoxLayout()
        self.group = QComboBox()       # a menu scales to any window width (segmented buttons got squashed)
        self.group.addItems(list(GROUPS))
        self.group.setToolTip("Which measurements to plot")
        self.group.currentIndexChanged.connect(lambda _: self.redraw())
        head.addWidget(self.group)
        head.addStretch(1)
        self.readout = QLabel("")
        self.readout.setObjectName("muted")
        self.readout.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # elide, never squeeze
        head.addWidget(self.readout)
        self.btn_png = QPushButton("Save PNG…")
        self.btn_png.setToolTip("Export this plot at publication resolution")
        self.btn_png.clicked.connect(self._save)
        head.addWidget(self.btn_png)
        lay.addLayout(head)
        self.pw = pg.PlotWidget()
        self.pw.setMenuEnabled(False)
        self.pw.showGrid(x=True, y=True, alpha=0.15)
        self.pw.setLabel("bottom", "Time", units="s")
        self.legend = self.pw.addLegend(offset=(-10, 6), labelTextSize="9pt", brush=pg.mkBrush(255, 255, 255, 200))
        lay.addWidget(self.pw, 1)
        self.cursor = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen("#B3261E", width=1.5))
        self.cursor.sigPositionChanged.connect(lambda ln: self._cursor_moved(ln.value()))
        self.pw.scene().sigMouseClicked.connect(self._clicked)
        self.res = None
        self._internal = False

    def set_result(self, res):
        self.res = res
        self.redraw()

    def redraw(self):
        self.pw.clear()
        self.legend.clear()
        self.pw.addItem(self.cursor)
        self.pw.getViewBox().setBackgroundColor(tok("surface"))
        from PySide6.QtGui import QColor
        c = QColor(tok("surface"))
        c.setAlpha(215)
        self.legend.setBrush(pg.mkBrush(c))
        self.legend.setLabelTextColor(tok("ink"))
        if self.res is None:
            self.readout.setText("Run the analysis to see time series here.")
            return
        ts, s = self.res.timeseries, self.res.side
        t = ts["time_s"].to_numpy()
        name = list(GROUPS)[self.group.currentIndex()]
        # events: stance of the analysed foot (shaded) and pole plants (thin bars at the bottom)
        st = ts.get(f"{s}_stance")
        if st is not None:
            m = st.to_numpy().astype(bool)
            edges = np.flatnonzero(np.diff(np.concatenate(([0], m.astype(int), [0]))))
            for a, b in zip(edges[::2], edges[1::2]):
                r = pg.LinearRegionItem((t[a], t[b - 1]), movable=False, brush=pg.mkBrush(31, 111, 102, 28),
                                        pen=pg.mkPen(None))
                r.setZValue(-10)
                self.pw.addItem(r)
        n = 0
        for i, (col, label) in enumerate(GROUPS[name]):
            c = col.format(s=s)
            if c in ts and np.isfinite(ts[c].to_numpy(dtype=float)).any():
                self.pw.plot(t, ts[c].to_numpy(dtype=float), pen=pg.mkPen(PEN[i % len(PEN)], width=2), name=label,
                             connect="finite")
                n += 1
        self.pw.setLabel("left", UNITS[name])
        self.readout.setText("" if n else f"No {name.lower()} data for this trial.")
        self.pw.enableAutoRange()

    def set_time(self, t: float):
        self._internal = True
        self.cursor.setValue(t)
        self._internal = False
        if self.res is not None:
            ts = self.res.timeseries
            k = int(np.argmin(np.abs(ts["time_s"].to_numpy() - t)))
            s = self.res.side
            parts = []
            for c, lab in ((f"{s}_knee_flexion_deg", "knee"), (f"{s}_hip_flexion_deg", "hip"),
                           (f"{s}_elbow_flexion_deg", "elbow")):
                if c in ts and np.isfinite(ts[c].iloc[k]):
                    parts.append(f"{lab} {ts[c].iloc[k]:.0f}°")
            self.readout.setText(f"t = {t:.3f} s   " + "  ".join(parts))

    def _cursor_moved(self, v):
        if not self._internal:
            self.seek.emit(float(v))

    def _clicked(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        vb = self.pw.getViewBox()
        if self.pw.sceneBoundingRect().contains(ev.scenePos()):
            x = vb.mapSceneToView(ev.scenePos()).x()
            self.seek.emit(float(x))

    def _save(self):
        from PySide6.QtWidgets import QFileDialog
        import pyqtgraph.exporters as ex
        p, _ = QFileDialog.getSaveFileName(self, "Save plot", "plot.png", "PNG image (*.png)")
        if p:
            e = ex.ImageExporter(self.pw.plotItem)
            e.parameters()["width"] = 2400
            e.export(p)
