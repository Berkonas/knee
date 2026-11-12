"""Shared analysis settings form (scale, side, model, stairs, forces, poles)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QToolButton, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from ..core.analysis import MOMENT_ARM_NOMINAL_M, AnalysisSettings


def dspin(lo, hi, val, step=0.01, dec=2, suffix="", tip=""):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(step)
    s.setValue(val)
    if suffix:
        s.setSuffix(suffix)
    s.setToolTip(tip)
    return s


class AnalysisForm(QWidget):
    pickScaleToggled = Signal(bool)
    forceFileChanged = Signal(str)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        g = QGroupBox("Scale and side")
        f = QFormLayout(g)
        self.scale_method = QComboBox()
        self.scale_method.addItem("Measured distance in the scene (best)", "points")
        self.scale_method.addItem("Participant height (approximate)", "height")
        self.scale_method.addItem("None (angles and timing only)", "none")
        self.scale_method.setCurrentIndex(1)
        self.scale_method.setToolTip("Metres-per-pixel is needed for speed and every force/moment estimate.")
        f.addRow("Scale", self.scale_method)
        row = QHBoxLayout()
        self.btn_pick_scale = QPushButton("Pick 2 points")
        self.btn_pick_scale.setCheckable(True)
        self.btn_pick_scale.setToolTip("Click two points on the video whose real distance you measured "
                                       "(e.g. top and bottom of a stair riser, or ends of a metre stick).")
        self.btn_pick_scale.toggled.connect(self.pickScaleToggled)
        self.scale_dist = dspin(0.01, 10, 0.17, 0.01, 3, " m", "Real distance between the two points")
        self.scale_dist.setMinimumWidth(90)
        row.addWidget(self.btn_pick_scale, 1)
        row.addWidget(self.scale_dist)
        f.addRow("Calibration", row)
        self.scale_label = QLabel("No points picked")
        self.scale_label.setObjectName("muted")
        f.addRow("", self.scale_label)
        self.scale_points: list[tuple[float, float]] = []
        self.side_row_holder = f
        self.side = QComboBox()
        for lab, v in (("Automatic (side facing camera)", "auto"), ("Left leg/arm", "left"), ("Right leg/arm", "right")):
            self.side.addItem(lab, v)
        f.addRow("Analysed side", self.side)
        self.model = QComboBox()
        for lab, v in (("Full (recommended)", "full"), ("Heavy (slower, most accurate)", "heavy"), ("Lite (fast)", "lite")):
            self.model.addItem(lab, v)
        self.model.setToolTip("MediaPipe Pose Landmarker model size.")
        self.cutoff = dspin(1, 30, 6, 0.5, 1, " Hz", "Low-pass cut-off for landmark trajectories (Winter: ~6 Hz for walking).")
        lay.addWidget(g)

        g = QGroupBox("Stairs")
        f = QFormLayout(g)
        self.step_h = dspin(0, 0.5, 0.17, 0.005, 3, " m", "Riser height")
        self.n_steps = QSpinBox()
        self.n_steps.setRange(0, 50)
        self.n_steps.setValue(0)
        self.n_steps.setToolTip("Number of steps descended within the analysis interval (0 = unknown).")
        f.addRow("Step height", self.step_h)
        f.addRow("Steps in interval", self.n_steps)
        lay.addWidget(g)

        g = QGroupBox("External forces")
        fp = QFormLayout(g)
        lay.addWidget(g)
        self.btn_adv = QToolButton()
        self.btn_adv.setText("Show advanced settings")
        self.btn_adv.setCheckable(True)
        self.btn_adv.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_adv.setArrowType(Qt.ArrowType.RightArrow)
        self.btn_adv.setStyleSheet("QToolButton { border: none; color: #1F6F66; padding: 6px 0; }")
        lay.addWidget(self.btn_adv)
        self.adv = QGroupBox("Advanced")
        f = QFormLayout(self.adv)
        f.addRow("Pose model", self.model)
        f.addRow("Filter cut-off", self.cutoff)
        self.support = QComboBox()
        self.support.addItem("Body weight (quasi-static)", "static")
        self.support.addItem("Body weight + COM acceleration (dynamic)", "dynamic")
        self.support.setToolTip("Total support force used when no force plate data are imported.")
        f.addRow("Support force", self.support)
        self.cop = dspin(0, 1, 0.5, 0.05, 2, "", "Assumed centre of pressure along the foot: 0 = heel, 1 = toes.")
        f.addRow("Centre of pressure", self.cop)
        self.moment_arm = dspin(2, 8, 100 * MOMENT_ARM_NOMINAL_M, 0.1, 1, " cm",
                                "Patellar tendon moment arm (literature ~4–6 cm). Range 4–6 cm is always reported.")
        f.addRow("Knee extensor moment arm", self.moment_arm)
        self.pole_mode = QComboBox()
        self.pole_mode.addItem("Not modelled", "none")
        self.pole_mode.addItem("Scenario: assumed pole force", "scenario")
        self.pole_mode.addItem("Measured (load-cell CSV)", "measured")
        self.pole_mode.setToolTip("Pole force cannot be seen in video. Choose an explicit assumption or import data.")
        fp.addRow("Pole force", self.pole_mode)
        self.pole_pct = dspin(0, 50, 10, 1, 1, " % BW", "Axial force per planted pole as % of body weight (scenario).")
        fp.addRow("Assumed force", self.pole_pct)
        row = QHBoxLayout()
        self.btn_force = QPushButton("Import force CSV…")
        self.btn_force.setToolTip("Force plate / instrumented step / pole load cell. See docs/data-formats.md.")
        self.btn_force.clicked.connect(self._pick_force)
        self.btn_force_clear = QPushButton("Clear")
        self.btn_force_clear.clicked.connect(lambda: self.set_force_file(""))
        row.addWidget(self.btn_force)
        row.addWidget(self.btn_force_clear)
        fp.addRow("Force data", row)
        self.force_label = QLabel("None (video-only)")
        self.force_label.setObjectName("muted")
        self.force_label.setWordWrap(True)
        fp.addRow("", self.force_label)
        self.force_offset = dspin(-600, 600, 0, 0.001, 3, " s", "t_video = t_force + offset")
        f.addRow("Force time offset", self.force_offset)
        lay.addWidget(self.adv)
        self.adv.setVisible(False)
        self.btn_adv.toggled.connect(self._toggle_adv)
        self.force_file = ""
        self.pole_mode.currentIndexChanged.connect(self._sync_enabled)
        self.scale_method.currentIndexChanged.connect(self._sync_enabled)
        self._sync_enabled()

    def _toggle_adv(self, on):
        self.adv.setVisible(on)
        self.btn_adv.setText("Hide advanced settings" if on else "Show advanced settings")
        self.btn_adv.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)

    def _sync_enabled(self):
        self.pole_pct.setEnabled(self.pole_mode.currentData() == "scenario")
        pts = self.scale_method.currentData() == "points"
        self.btn_pick_scale.setEnabled(pts)
        self.scale_dist.setEnabled(pts)

    def _pick_force(self):
        p, _ = QFileDialog.getOpenFileName(self, "Import force data", "", "CSV files (*.csv)")
        if p:
            from ..core.forces import load_force_csv
            try:
                fd = load_force_csv(p)
            except Exception as e:
                from .widgets import error_box
                error_box(self, "Cannot read force file", str(e))
                return
            self.set_force_file(p, ", ".join(fd.channels))

    def set_force_file(self, path: str, channels: str = ""):
        self.force_file = path
        self.force_label.setText(f"{path}\nChannels: {channels}" if path else "None (video-only)")
        self.forceFileChanged.emit(path)

    def add_scale_point(self, x: float, y: float) -> bool:
        self.scale_points.append((x, y))
        if len(self.scale_points) > 2:
            self.scale_points = self.scale_points[-1:]
        if len(self.scale_points) == 2:
            from ..core.kinematics import scale_from_points
            s = scale_from_points(*self.scale_points, self.scale_dist.value())
            self.scale_label.setText(f"{1 / s:.1f} px per metre ({1000 * s:.2f} mm/px)")
            self.btn_pick_scale.setChecked(False)
            return True
        self.scale_label.setText("Point 1 set; click point 2")
        return False

    def scale_m_per_px(self) -> float | None:
        if len(self.scale_points) == 2:
            from ..core.kinematics import scale_from_points
            return scale_from_points(*self.scale_points, self.scale_dist.value())
        return None

    def settings(self) -> AnalysisSettings:
        method = self.scale_method.currentData()
        sp = self.scale_m_per_px() if method == "points" else None
        if method == "points" and sp is None:
            raise ValueError("Pick two calibration points on the video, or choose another scale method.")
        n = self.n_steps.value()
        return AnalysisSettings(
            side=self.side.currentData(), cutoff_hz=self.cutoff.value(), scale_method=method,
            scale_m_per_px=sp, support_model=self.support.currentData(), cop_fraction=self.cop.value(),
            moment_arm_m=self.moment_arm.value() / 100, pole_force_mode=self.pole_mode.currentData(),
            pole_pct_bw=self.pole_pct.value(), force_offset_s=self.force_offset.value(),
            descent_height_m=self.step_h.value() * n if n else None)

    def stair(self) -> dict:
        return {"step_height_m": self.step_h.value(), "n_steps": self.n_steps.value()}

    def load_from(self, trial) -> None:
        s = trial.settings or {}
        def setc(combo, val):
            i = combo.findData(val)
            if i >= 0:
                combo.setCurrentIndex(i)
        setc(self.scale_method, s.get("scale_method", "height"))
        setc(self.side, s.get("side", "auto"))
        setc(self.support, s.get("support_model", "static"))
        setc(self.pole_mode, s.get("pole_force_mode", "none"))
        setc(self.model, s.get("pose_model", "full"))
        self.cutoff.setValue(s.get("cutoff_hz", 6.0))
        self.cop.setValue(s.get("cop_fraction", 0.5))
        self.moment_arm.setValue(100 * s.get("moment_arm_m", MOMENT_ARM_NOMINAL_M))
        self.pole_pct.setValue(s.get("pole_pct_bw", 10.0))
        self.force_offset.setValue(s.get("force_offset_s", 0.0))
        self.scale_points = [tuple(p) for p in s.get("scale_points", [])]
        if "scale_distance_m" in s:
            self.scale_dist.setValue(s["scale_distance_m"])
        if len(self.scale_points) == 2:
            self.scale_label.setText(f"{1 / self.scale_m_per_px():.1f} px per metre (saved)")
        else:
            self.scale_label.setText("No points picked")
        self.set_force_file(s.get("force_csv", ""))
        self.step_h.setValue(trial.stair.get("step_height_m", 0.17))
        self.n_steps.setValue(int(trial.stair.get("n_steps", 0)))

    def store_into(self, trial) -> None:
        trial.settings["scale_points"] = self.scale_points
        trial.settings["scale_distance_m"] = self.scale_dist.value()
        trial.settings["force_csv"] = self.force_file
        trial.settings["pose_model"] = self.model.currentData()
        trial.stair.update(self.stair())


__all__ = ["AnalysisForm", "QCheckBox"]
