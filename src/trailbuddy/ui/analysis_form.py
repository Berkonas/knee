"""Analysis settings, split into the setup steps (scale, stairs, forces, advanced).

Each step is a plain widget (no group boxes) so it can be placed in the step accordion.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

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


def hint(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("muted")
    lab.setWordWrap(True)
    return lab


def form(parent: QWidget) -> QFormLayout:
    f = QFormLayout(parent)
    f.setContentsMargins(0, 0, 0, 0)
    f.setHorizontalSpacing(10)
    f.setVerticalSpacing(8)
    f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return f


class AnalysisForm(QObject):
    """Holds all settings widgets; exposes four section widgets for the accordion."""

    pickScaleToggled = Signal(bool)
    forceFileChanged = Signal(str)
    changed = Signal()

    def __init__(self):
        super().__init__()
        # ---- scale & side ---------------------------------------------------------------------
        self.scale_box = QWidget()
        v = QVBoxLayout(self.scale_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(hint("Metres per pixel are needed for speed and every force or moment. Best: click two points "
                         "on something you measured in the plane of motion, such as a stair riser."))
        fw = QWidget()
        f = form(fw)
        self.scale_method = QComboBox()
        self.scale_method.addItem("Measured distance in the scene (best)", "points")
        self.scale_method.addItem("Participant body metrics (approximate)", "height")
        self.scale_method.addItem("None (angles and timing only)", "none")
        self.scale_method.setCurrentIndex(1)
        f.addRow("Method", self.scale_method)
        row = QHBoxLayout()
        self.btn_pick_scale = QPushButton("Pick 2 points")
        self.btn_pick_scale.setCheckable(True)
        self.btn_pick_scale.setToolTip("Then click the two ends of the measured distance on the video.")
        self.btn_pick_scale.toggled.connect(self.pickScaleToggled)
        self.scale_dist = dspin(0.01, 10, 0.17, 0.01, 3, " m", "Real distance between the two points")
        self.scale_dist.setMinimumWidth(96)
        row.addWidget(self.btn_pick_scale, 1)
        row.addWidget(self.scale_dist)
        f.addRow("Distance", row)
        self.scale_label = QLabel("No points picked")
        self.scale_label.setObjectName("muted")
        f.addRow("", self.scale_label)
        self.scale_points: list[tuple[float, float]] = []
        self.side = QComboBox()
        for lab, val in (("Automatic (side facing the camera)", "auto"), ("Left leg and arm", "left"),
                         ("Right leg and arm", "right")):
            self.side.addItem(lab, val)
        f.addRow("Analysed side", self.side)
        v.addWidget(fw)

        # ---- stairs ---------------------------------------------------------------------------
        self.stairs_box = QWidget()
        v = QVBoxLayout(self.stairs_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(hint("Used to express knee demand per metre descended. Leave steps at 0 if unknown."))
        fw = QWidget()
        f = form(fw)
        self.step_h = dspin(0, 0.5, 0.17, 0.005, 3, " m", "Riser height")
        self.n_steps = QSpinBox()
        self.n_steps.setRange(0, 50)
        self.n_steps.setToolTip("Number of steps descended within the analysis interval")
        f.addRow("Step height", self.step_h)
        f.addRow("Steps in clip", self.n_steps)
        v.addWidget(fw)

        # ---- forces ---------------------------------------------------------------------------
        self.forces_box = QWidget()
        v = QVBoxLayout(self.forces_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(hint("Video shows movement, not force. Without a force plate the app uses body weight; pole "
                         "force must be assumed (scenario) or measured with a load cell."))
        fw = QWidget()
        f = form(fw)
        self.pole_mode = QComboBox()
        self.pole_mode.addItem("Not modelled", "none")
        self.pole_mode.addItem("Scenario: assumed pole force", "scenario")
        self.pole_mode.addItem("Measured (load-cell CSV)", "measured")
        f.addRow("Pole force", self.pole_mode)
        self.pole_pct = dspin(0, 50, 10, 1, 1, " % BW", "Axial force per planted pole, % of body weight")
        f.addRow("Assumed force", self.pole_pct)
        row = QHBoxLayout()
        self.btn_force = QPushButton("Import force CSV…")
        self.btn_force.setToolTip("Force plate, instrumented step or pole load cell (see docs/data-formats.md)")
        self.btn_force.clicked.connect(self._pick_force)
        self.btn_force_clear = QPushButton("Clear")
        self.btn_force_clear.clicked.connect(lambda: self.set_force_file(""))
        row.addWidget(self.btn_force, 1)
        row.addWidget(self.btn_force_clear)
        f.addRow("Force data", row)
        self.force_label = QLabel("None: video-only analysis")
        self.force_label.setObjectName("muted")
        self.force_label.setWordWrap(True)
        f.addRow("", self.force_label)
        v.addWidget(fw)

        # ---- advanced -------------------------------------------------------------------------
        self.adv_box = QWidget()
        v = QVBoxLayout(self.adv_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(hint("Defaults follow the methods document. Every trial also reports a sensitivity range."))
        fw = QWidget()
        f = form(fw)
        self.model = QComboBox()
        for lab, val in (("Full (recommended)", "full"), ("Heavy (slower, most accurate)", "heavy"),
                         ("Lite (fastest)", "lite")):
            self.model.addItem(lab, val)
        f.addRow("Pose model", self.model)
        self.cutoff = dspin(1, 30, 6, 0.5, 1, " Hz", "Low-pass cut-off for landmark trajectories (Winter: ~6 Hz)")
        f.addRow("Filter cut-off", self.cutoff)
        self.support = QComboBox()
        self.support.addItem("Body weight (quasi-static)", "static")
        self.support.addItem("Weight + COM acceleration", "dynamic")
        f.addRow("Support force", self.support)
        self.cop = dspin(0, 1, 0.5, 0.05, 2, "", "Assumed centre of pressure: 0 = heel, 1 = toes")
        f.addRow("Centre of pressure", self.cop)
        self.moment_arm = dspin(2, 8, 100 * MOMENT_ARM_NOMINAL_M, 0.1, 1, " cm",
                                "Patellar tendon moment arm (literature 4-6 cm)")
        f.addRow("Knee moment arm", self.moment_arm)
        self.force_offset = dspin(-600, 600, 0, 0.001, 3, " s", "t_video = t_force + offset")
        f.addRow("Force time offset", self.force_offset)
        v.addWidget(fw)

        self.force_file = ""
        self.pole_mode.currentIndexChanged.connect(self._sync_enabled)
        self.scale_method.currentIndexChanged.connect(self._sync_enabled)
        for w in (self.scale_method, self.side, self.pole_mode, self.support, self.model):
            w.currentIndexChanged.connect(lambda *_: self.changed.emit())
        for w in (self.scale_dist, self.step_h, self.pole_pct, self.cutoff, self.cop, self.moment_arm):
            w.valueChanged.connect(lambda *_: self.changed.emit())
        self.n_steps.valueChanged.connect(lambda *_: self.changed.emit())
        self._sync_enabled()

    def setEnabled(self, on: bool):
        for w in (self.scale_box, self.stairs_box, self.forces_box, self.adv_box):
            w.setEnabled(on)

    def _sync_enabled(self):
        self.pole_pct.setEnabled(self.pole_mode.currentData() == "scenario")
        pts = self.scale_method.currentData() == "points"
        self.btn_pick_scale.setEnabled(pts)
        self.scale_dist.setEnabled(pts)

    def _pick_force(self):
        p, _ = QFileDialog.getOpenFileName(None, "Import force data", "", "CSV files (*.csv)")
        if p:
            from ..core.forces import load_force_csv
            try:
                fd = load_force_csv(p)
            except Exception as e:
                from .widgets import error_box
                error_box(None, "Cannot read force file", str(e))
                return
            self.set_force_file(p, ", ".join(fd.channels))

    def set_force_file(self, path: str, channels: str = ""):
        from pathlib import Path
        self.force_file = path
        self.force_label.setText(f"{Path(path).name} ({channels})" if path else "None: video-only analysis")
        self.forceFileChanged.emit(path)
        self.changed.emit()

    def add_scale_point(self, x: float, y: float) -> bool:
        self.scale_points.append((x, y))
        if len(self.scale_points) > 2:
            self.scale_points = self.scale_points[-1:]
        if len(self.scale_points) == 2:
            s = self.scale_m_per_px()
            self.scale_label.setText(f"{1 / s:.0f} px per metre ({1000 * s:.2f} mm per px)")
            self.btn_pick_scale.setChecked(False)
            self.changed.emit()
            return True
        self.scale_label.setText("Point 1 set; click point 2")
        return False

    def scale_m_per_px(self) -> float | None:
        if len(self.scale_points) == 2:
            from ..core.kinematics import scale_from_points
            return scale_from_points(*self.scale_points, self.scale_dist.value())
        return None

    # ---- summaries for the step headers -------------------------------------------------------
    def scale_summary(self) -> tuple[str, bool]:
        m = self.scale_method.currentData()
        side = self.side.currentText().split(" (")[0]
        if m == "points":
            s = self.scale_m_per_px()
            return (f"{1 / s:.0f} px/m from 2 points · {side}" if s else "Pick 2 points on the video", bool(s))
        if m == "height":
            return (f"From body metrics (approximate) · {side}", True)
        return ("No scale: angles and timing only", True)

    def stairs_summary(self) -> tuple[str, bool]:
        n = self.n_steps.value()
        return (f"{n} × {100 * self.step_h.value():.1f} cm = {n * self.step_h.value():.2f} m" if n
                else "Steps not counted (optional)", bool(n))

    def forces_summary(self) -> tuple[str, bool]:
        mode = self.pole_mode.currentData()
        txt = {"none": "Body weight only; pole force not modelled",
               "scenario": f"Scenario: {self.pole_pct.value():g}% BW per planted pole",
               "measured": "Measured pole force from CSV"}[mode]
        if self.force_file:
            txt += " · force data loaded"
        return txt, True

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
            self.scale_label.setText(f"{1 / self.scale_m_per_px():.0f} px per metre (saved)")
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
