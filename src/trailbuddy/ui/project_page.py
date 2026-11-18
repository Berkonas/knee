"""Project page: create/open a study, participants, conditions, trial log."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from ..core.project import EXPERIMENTS, PARTICIPANT_EDIT_FIELDS, SEGMENT_FIELDS, TASKS, CameraVideo, Condition, Participant, Project, Trial, parse_filename
from .widgets import error_box, page_header, section

VIDEO_FILTER = "Videos (*.mp4 *.mov *.MOV *.MP4 *.avi *.m4v *.mkv)"


def table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.horizontalHeader().setMinimumSectionSize(60)
    t.horizontalHeader().setTextElideMode(Qt.TextElideMode.ElideRight)
    return t


def fill(t: QTableWidget, rows):
    t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            t.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))


class ParticipantDialog(QDialog):
    """Participant information. Required for loads: measured mass and height. Everything else is optional."""

    def __init__(self, parent, p: Participant | None = None):
        super().__init__(parent)
        self.setWindowTitle("Participant")
        self.setMinimumWidth(480)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(); f = QFormLayout(body); scroll.setWidget(body)
        outer.addWidget(scroll)
        intro = QLabel("Body mass is required for every force or moment, and height (or a calibrated distance) "
                       "for distances in metres. Nothing is calculated from default values.")
        intro.setWordWrap(True); intro.setObjectName("muted")
        f.addRow(intro)
        self.pid = QLineEdit(p.id if p else "")
        self.pid.setPlaceholderText("P01 (code only, no names)")

        def dsb(lo, hi, dec, suf, val, special=None, tip=""):
            w = QDoubleSpinBox(); w.setRange(lo, hi); w.setDecimals(dec); w.setSuffix(suf)
            if special:
                w.setSpecialValueText(special)
            w.setValue(val); w.setToolTip(tip)
            return w

        def combo(items, cur):
            w = QComboBox()
            for lab, val in items:
                w.addItem(lab, val)
            w.setCurrentIndex(max(0, w.findData(cur)))
            return w

        self.mass = dsb(0, 250, 1, " kg", (p.body_mass_kg or 0) if p else 0, "not entered", "Measured on a scale, with shoes")
        self.height = dsb(0, 2.5, 3, " m", (p.height_m or 0) if p else 0, "not entered", "Standing height, with shoes")
        f.addRow("Participant ID", self.pid)
        f.addRow(section("Required for loads"))
        f.addRow("Body mass *", self.mass)
        f.addRow("Height *", self.height)
        f.addRow(section("Poles"))
        self.pole = dsb(0, 160, 1, " cm", (p.standard_pole_length_cm or 0) if p else 0, "not set",
                        "Standard length: about 90° elbow angle with the tip on level ground")
        f.addRow("Standard pole length", self.pole)
        f.addRow(section("Measured segment lengths (optional)"))
        self.leg = dsb(0, 1.5, 3, " m", (p.leg_length_m or 0) if p else 0, "not measured",
                       "Greater trochanter to the floor")
        f.addRow("Leg length", self.leg)
        self.seg = {}
        segs = p.segments if p else {}
        for key, (label, how) in SEGMENT_FIELDS.items():
            w = dsb(0, 1.0, 3, " m", segs.get(key) or 0, "not measured", how)
            self.seg[key] = w
            f.addRow(label, w)
        f.addRow(section("Other information (optional, voluntary)"))
        self.age = QSpinBox(); self.age.setRange(0, 110); self.age.setSpecialValueText("not given")
        self.age.setValue((p.age_years or 0) if p else 0)
        self.sex = QLineEdit(p.sex if p else ""); self.sex.setPlaceholderText("not given")
        self.sex.setToolTip("Recorded only for reporting. It never replaces this person's measured anatomy.")
        sides = [("not given", ""), ("Left", "left"), ("Right", "right")]
        self.dom = combo(sides, p.dominant_leg if p else "")
        self.lead = combo(sides, p.lead_leg if p else "")
        self.shoe = QLineEdit(p.footwear if p else ""); self.shoe.setPlaceholderText("e.g. trail runners")
        self.load = dsb(0, 60, 1, " kg", (p.carried_load_kg or 0) if p else 0, "none", "Backpack or other carried load")
        f.addRow("Age", self.age)
        f.addRow("Sex / gender", self.sex)
        f.addRow("Dominant leg", self.dom)
        f.addRow("Preferred lead leg", self.lead)
        f.addRow("Footwear", self.shoe)
        f.addRow("Carried load", self.load)
        self.arm = dsb(0, 1.2, 3, " m", (p.arm_length_m or 0) if p else 0, "not measured", "Acromion to wrist")
        f.addRow("Arm length", self.arm)
        f.addRow(section("Baseline tests (optional)"))
        self.scale = QLineEdit(", ".join(f"{x:g}" for x in (p.pole_scale_kg if p else [])))
        self.scale.setPlaceholderText("e.g. 6.5, 7.0, 7.2  (kg on the scale)")
        self.scale.setToolTip("Push one pole onto a scale the way you plant it on the stairs; enter each reading in kg.\n"
                              "Their mean (as % body weight) becomes this participant's scenario pole force.")
        f.addRow("Pole push on scale", self.scale)
        self._mvc = dict(p.mvc) if p else {}
        self._mvc_source = p.mvc_source if p else ""
        mrow = QHBoxLayout()
        self.mvc_label = QLabel(self._mvc_text())
        self.mvc_label.setObjectName("muted")
        self.mvc_label.setWordWrap(True)
        b = QPushButton("Load MVC trial…")
        b.setToolTip("EMG CSV of a maximal voluntary contraction test (time_s + one column per muscle)")
        b.clicked.connect(self._load_mvc)
        mrow.addWidget(self.mvc_label, 1)
        mrow.addWidget(b)
        f.addRow("EMG maxima (MVC)", mrow)
        self.notes = QLineEdit(p.notes if p else "")
        f.addRow("Notes", self.notes)
        if p:
            self.pid.setEnabled(False)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)
        self.resize(500, 680)

    def _mvc_text(self) -> str:
        if not self._mvc:
            return "none loaded"
        return ", ".join(f"{k} {v:.3g}" for k, v in self._mvc.items()) + f"  ({Path(self._mvc_source).name})"

    def _load_mvc(self):
        from ..core.emg import mvc_from_file
        path, _ = QFileDialog.getOpenFileName(self, "MVC trial (EMG CSV)", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            new = mvc_from_file(path)
        except Exception as e:
            error_box(self, "Cannot read MVC file", str(e))
            return
        self._mvc.update(new)  # several MVC files (one per muscle test) accumulate
        self._mvc_source = path
        self.mvc_label.setText(self._mvc_text())

    def _scale_values(self) -> list[float]:
        out = []
        for tok in self.scale.text().replace(";", ",").split(","):
            tok = tok.strip()
            if tok:
                try:
                    out.append(float(tok))
                except ValueError:
                    pass
        return out

    def value(self) -> Participant:
        segs = {k: w.value() for k, w in self.seg.items() if w.value() > 0}
        return Participant(self.pid.text().strip(), self.mass.value() or None, self.height.value() or None,
                           self.leg.value() or None, self.pole.value() or None, segs, self.notes.text(),
                           age_years=self.age.value() or None, sex=self.sex.text().strip(),
                           dominant_leg=self.dom.currentData(), lead_leg=self.lead.currentData(),
                           footwear=self.shoe.text().strip(), carried_load_kg=self.load.value() or None,
                           arm_length_m=self.arm.value() or None, pole_scale_kg=self._scale_values(),
                           mvc=dict(self._mvc), mvc_source=self._mvc_source)


class TrialDialog(QDialog):
    """Create or edit trial metadata."""

    def __init__(self, parent, project: Project, trial: Trial | None = None, video: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Trial details")
        self.project = project
        f = QFormLayout(self)
        self.part = QComboBox()
        self.part.addItems([p.id for p in project.participants])
        self.cond = QComboBox()
        for c in project.conditions:
            self.cond.addItem(f"{c.code} – {c.label}", c.code)
        self.num = QSpinBox(); self.num.setRange(1, 99)
        self.pole = QDoubleSpinBox(); self.pole.setRange(0, 160); self.pole.setSuffix(" cm"); self.pole.setSpecialValueText("auto / none")
        self.cam = QLineEdit(); self.cam.setPlaceholderText("e.g. side view, 3 m, 60 fps, phone at hip height")
        self.notes = QLineEdit()
        self.step_h = QDoubleSpinBox(); self.step_h.setRange(0, 0.5); self.step_h.setDecimals(3); self.step_h.setSuffix(" m"); self.step_h.setValue(0.17)
        self.step_d = QDoubleSpinBox(); self.step_d.setRange(0, 1); self.step_d.setDecimals(3); self.step_d.setSuffix(" m"); self.step_d.setValue(0.28)
        self.n_steps = QSpinBox(); self.n_steps.setRange(0, 40); self.n_steps.setSpecialValueText("not counted")
        self.grade = QDoubleSpinBox(); self.grade.setRange(-45, 45); self.grade.setDecimals(1); self.grade.setSuffix("°")
        self.grade.setToolTip("Ramp or slope angle; negative = downhill")
        self.task = QComboBox()
        for k, lab in TASKS.items():
            self.task.addItem(lab, k)
        self.date = QLineEdit(); self.date.setPlaceholderText("YYYY-MM-DD")
        self.npoles = QComboBox()
        for lab, v in (("from condition", None), ("none", 0), ("one", 1), ("two", 2)):
            self.npoles.addItem(lab, v)
        self.grip = QLineEdit(); self.grip.setPlaceholderText("e.g. strap, hand on top")
        self.surface = QLineEdit(); self.surface.setPlaceholderText("e.g. painted steel stairs")
        self.force = QLineEdit(); self.force.setPlaceholderText("none, or e.g. force plate under step 2")
        if trial:
            self.task.setCurrentIndex(max(0, self.task.findData(trial.task)))
            self.date.setText(trial.date)
            self.npoles.setCurrentIndex(max(0, self.npoles.findData(trial.n_poles)))
            self.grip.setText(trial.grip); self.surface.setText(trial.surface); self.force.setText(trial.force_data)
            self.n_steps.setValue(int(trial.stair.get("n_steps", 0) or 0))
            self.grade.setValue(float(trial.stair.get("slope_deg", 0) or 0))
            self.part.setCurrentText(trial.participant_id); self.part.setEnabled(False)
            self.cond.setCurrentIndex(self.cond.findData(trial.condition_code)); self.cond.setEnabled(False)
            self.num.setValue(trial.trial_number); self.num.setEnabled(False)
            self.pole.setValue(trial.pole_length_cm or 0)
            self.cam.setText(trial.camera_config); self.notes.setText(trial.notes)
            self.step_h.setValue(trial.stair.get("step_height_m", 0.17)); self.step_d.setValue(trial.stair.get("step_depth_m", 0.28))
        elif video:
            parsed = parse_filename(video)
            if parsed:
                pid, code, n = parsed
                if pid in [p.id for p in project.participants]:
                    self.part.setCurrentText(pid)
                i = self.cond.findData(code)
                if i >= 0:
                    self.cond.setCurrentIndex(i)
                self.num.setValue(n)
            f.addRow("Video", QLabel(Path(video).name))
        f.addRow("Participant", self.part)
        f.addRow("Condition", self.cond)
        f.addRow("Trial number", self.num)
        f.addRow("Task", self.task)
        f.addRow("Date", self.date)
        f.addRow(section("Poles"))
        f.addRow("Pole length", self.pole)
        f.addRow("Number of poles", self.npoles)
        f.addRow("Grip", self.grip)
        f.addRow(section("Stairs or slope"))
        f.addRow("Riser (step) height", self.step_h)
        f.addRow("Tread depth", self.step_d)
        f.addRow("Steps descended", self.n_steps)
        f.addRow("Ramp angle", self.grade)
        f.addRow("Surface", self.surface)
        f.addRow(section("Recording"))
        f.addRow("Camera setup", self.cam)
        f.addRow("Force data", self.force)
        f.addRow("Notes / deviations", self.notes)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def apply(self, trial: Trial | None, videos: list[CameraVideo]) -> Trial:
        if trial is None:
            trial = Trial(self.part.currentText(), self.cond.currentData(), self.num.value(), videos)
            if self.pole.value():
                trial.pole_length_cm = self.pole.value()
        else:
            trial.pole_length_cm = self.pole.value() or trial.pole_length_cm
        trial.camera_config = self.cam.text()
        trial.notes = self.notes.text()
        trial.stair.update(step_height_m=self.step_h.value(), step_depth_m=self.step_d.value(),
                           n_steps=self.n_steps.value() or None, slope_deg=self.grade.value() or None)
        trial.task, trial.date = self.task.currentData(), self.date.text().strip()
        trial.n_poles, trial.grip = self.npoles.currentData(), self.grip.text().strip()
        trial.surface, trial.force_data = self.surface.text().strip(), self.force.text().strip()
        return trial

    def apply_existing(self, project: Project, trial: Trial) -> str | None:
        """Apply edits to an existing trial; when its ID changes (task), move the results. Returns an error or None."""
        old_id, old_task = trial.id, trial.task
        self.apply(trial, trial.videos)
        try:
            project.update_trial_id(old_id, trial)
        except (ValueError, OSError) as e:
            trial.task = old_task
            return str(e)
        return None


class CalibrationDialog(QDialog):
    """Pole sensor calibration: scale readings (kg) vs sensor readings -> linear fit, used inverted on trial data."""

    def __init__(self, parent, project: Project):
        super().__init__(parent)
        self.setWindowTitle("Pole force calibration")
        self.project = project
        v = QVBoxLayout(self)
        intro = QLabel("Press each pole onto a scale at several forces and note the sensor reading at each. The fit "
                       "reading = a·F + b is inverted during trials (F = (reading − b)/a) for force-file columns "
                       "pole_left_raw / pole_right_raw.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        v.addWidget(intro)
        self.tables, self.results = {}, {}
        row = QHBoxLayout()
        for side in ("left", "right"):
            col = QVBoxLayout()
            col.addWidget(section(f"{side.capitalize()} pole"))
            t = QTableWidget(8, 2)
            t.setHorizontalHeaderLabels(["Scale (kg)", "Sensor reading"])
            t.verticalHeader().setVisible(False)
            old = project.pole_calibration.get(side, {}).get("points", [])
            for r, (kg, rd) in enumerate(old[:8]):
                t.setItem(r, 0, QTableWidgetItem(f"{kg:g}"))
                t.setItem(r, 1, QTableWidgetItem(f"{rd:g}"))
            col.addWidget(t)
            lab = QLabel(self._describe(project.pole_calibration.get(side)))
            lab.setObjectName("muted")
            lab.setWordWrap(True)
            col.addWidget(lab)
            self.tables[side], self.results[side] = t, lab
            row.addLayout(col)
        v.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        fit = bb.addButton("Fit", QDialogButtonBox.ButtonRole.ActionRole)
        fit.clicked.connect(self.fit)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.resize(620, 460)

    @staticmethod
    def _describe(cal) -> str:
        if not cal:
            return "Not calibrated."
        return (f"reading = {cal['a']:.4g}·F + {cal['b']:.4g}   R² = {cal['r2']:.4f}   "
                f"error ±{cal['rmse_n']:.1f} N   ({cal['n']} points)")

    def _points(self, side):
        t, pts = self.tables[side], []
        for r in range(t.rowCount()):
            a, b = t.item(r, 0), t.item(r, 1)
            try:
                if a and b and a.text().strip() and b.text().strip():
                    pts.append((float(a.text()), float(b.text())))
            except ValueError:
                pass
        return pts

    def fit(self) -> dict:
        from ..core.calibration import fit_calibration
        out = {}
        for side in ("left", "right"):
            pts = self._points(side)
            if not pts:
                self.results[side].setText("Not calibrated.")
                continue
            try:
                cal = fit_calibration([p[0] for p in pts], [p[1] for p in pts]).as_dict()
            except ValueError as e:
                self.results[side].setText(str(e))
                continue
            cal["points"] = pts
            out[side] = cal
            self.results[side].setText(self._describe(cal))
        return out

    def _save(self):
        self.project.pole_calibration = self.fit()
        self.project.save()
        self.accept()


class ProjectPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.setObjectName("page")
        self.state = state
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.addWidget(page_header("Study", "Create or open a study folder, enter participants (codes only), "
                                  "conditions, and log trials. Original videos are linked, never copied or changed."))
        row = QHBoxLayout()
        self.btn_new = QPushButton("New study…")
        self.btn_new.setObjectName("primary")
        self.btn_new.clicked.connect(self.new_project)
        self.btn_open = QPushButton("Open study…")
        self.btn_open.clicked.connect(self.open_project)
        self.btn_demo = QPushButton("Create demo study")
        self.btn_demo.setToolTip("Builds a study of 18 synthetic trials (no real people) so you can explore results and exports.")
        self.btn_demo.clicked.connect(self.make_demo)
        self.btn_delstudy = QPushButton("Delete study…")
        self.btn_delstudy.setToolTip("Moves this study folder (trials, results, caches) to the system trash")
        self.btn_delstudy.clicked.connect(self.delete_study)
        self.btn_cal = QPushButton("Pole force calibration…")
        self.btn_cal.setToolTip("Scale-test calibration for pole force sensors")
        self.btn_cal.clicked.connect(lambda: self.project and CalibrationDialog(self, self.project).exec())
        for b in (self.btn_new, self.btn_open, self.btn_demo, self.btn_cal, self.btn_delstudy):
            row.addWidget(b)
        row.addStretch(1)
        self.info = QLabel("No study open.")
        self.info.setObjectName("muted")
        row.addWidget(self.info)
        lay.addLayout(row)

        self.quality = QLabel("")
        self.quality.setObjectName("warnBanner")
        self.quality.setWordWrap(True)
        self.quality.setTextFormat(Qt.TextFormat.RichText)
        self._quality_open = False
        self._quality_items: list[str] = []
        self.quality.linkActivated.connect(self._toggle_quality)
        self.quality.hide()
        lay.addWidget(self.quality)
        split = QSplitter(Qt.Orientation.Vertical)
        top = QWidget(); tl = QHBoxLayout(top); tl.setContentsMargins(0, 0, 0, 0)
        # participants
        pw = QWidget(); pl = QVBoxLayout(pw); pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(section("Participants"))
        self.ptable = table(["ID", "Mass (kg)", "Height (m)", "Std pole (cm)", "Segment lengths", "Notes"])
        self.ptable.doubleClicked.connect(self.edit_participant)
        pl.addWidget(self.ptable)
        r = QHBoxLayout()
        self.btn_padd = QPushButton("Add participant"); self.btn_padd.clicked.connect(self.add_participant)
        self.btn_pedit = QPushButton("Edit body metrics"); self.btn_pedit.clicked.connect(self.edit_participant)
        self.btn_pdel = QPushButton("Remove"); self.btn_pdel.clicked.connect(self.remove_participant)
        for b in (self.btn_padd, self.btn_pedit, self.btn_pdel):
            r.addWidget(b)
        r.addStretch(1)
        pl.addLayout(r)
        tl.addWidget(pw, 3)
        # conditions
        cw = QWidget(); cl = QVBoxLayout(cw); cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(section("Conditions"))
        self.ctable = table(["Code", "Label", "Poles", "Length offset (cm)"])
        cl.addWidget(self.ctable)
        r = QHBoxLayout()
        self.btn_cadd = QPushButton("Add condition"); self.btn_cadd.clicked.connect(self.add_condition)
        self.btn_cdel = QPushButton("Remove"); self.btn_cdel.clicked.connect(self.remove_condition)
        r.addWidget(self.btn_cadd); r.addWidget(self.btn_cdel); r.addStretch(1)
        cl.addLayout(r)
        tl.addWidget(cw, 2)
        split.addWidget(top)
        # trials
        trw = QWidget(); trl = QVBoxLayout(trw); trl.setContentsMargins(0, 0, 0, 0)
        trl.addWidget(section("Trials"))
        self.ttable = table(["Trial", "Participant", "Condition", "#", "Task", "Views", "Status", "Checks", "Notes"])
        self.ttable.doubleClicked.connect(self.open_selected)
        trl.addWidget(self.ttable)
        r = QHBoxLayout()
        self.btn_tadd = QPushButton("Add one-camera trials…")
        self.btn_tadd.setToolTip("Select one or more videos. Names like P01_C1_T01.mp4 are filled in automatically.")
        self.btn_tadd.clicked.connect(self.add_trials)
        self.btn_tadd2 = QPushButton("Add two-camera trial…")
        self.btn_tadd2.clicked.connect(self.add_two_cam_trial)
        self.btn_tedit = QPushButton("Edit details"); self.btn_tedit.clicked.connect(self.edit_trial)
        self.btn_tdel = QPushButton("Remove"); self.btn_tdel.clicked.connect(self.remove_trial)
        self.btn_topen = QPushButton("Open for analysis"); self.btn_topen.setObjectName("primary")
        self.btn_topen.clicked.connect(self.open_selected)
        for b in (self.btn_tadd, self.btn_tadd2, self.btn_tedit, self.btn_tdel):
            r.addWidget(b)
        r.addStretch(1)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("muted")
        r.addWidget(self.progress_label)
        r.addWidget(self.btn_topen)
        trl.addLayout(r)
        split.addWidget(trw)
        split.setSizes([260, 400])
        lay.addWidget(split, 1)
        state.projectChanged.connect(self.refresh)
        state.trialsChanged.connect(self.refresh)
        self.refresh()

    # ---------------------------------------------------------------------------------------
    @property
    def project(self) -> Project | None:
        return self.state.project

    def refresh(self):
        p = self.project
        has = p is not None
        for b in (self.btn_padd, self.btn_pedit, self.btn_pdel, self.btn_cadd, self.btn_cdel, self.btn_tadd,
                  self.btn_tadd2, self.btn_tedit, self.btn_tdel, self.btn_topen, self.btn_delstudy, self.btn_cal):
            b.setEnabled(has)
        if not has:
            self.info.setText("No study open.")
            for t in (self.ptable, self.ctable, self.ttable):
                t.setRowCount(0)
            self.quality.hide()
            return
        self.info.setText(f"{p.name}  ·  {EXPERIMENTS.get(p.experiment, {}).get('name', p.experiment)}")
        self.info.setToolTip(str(p.root))
        fill(self.ptable, [(q.id, q.body_mass_kg if q.body_mass_kg is not None else "missing",
                            q.height_m if q.height_m is not None else "missing", q.standard_pole_length_cm,
                            f"{len(q.segments)} of {len(SEGMENT_FIELDS)} measured", q.notes)
                           for q in p.participants])
        fill(self.ctable, [(c.code, c.label, "yes" if c.uses_poles else "no",
                            "" if c.pole_offset_cm is None else f"{c.pole_offset_cm:+g}") for c in p.conditions])
        from ..core.quality import study_checks, trial_checks
        fill(self.ttable, [(t.id, t.participant_id, t.condition_code, t.trial_number, TASKS.get(t.task, t.task),
                            " + ".join(v.role for v in t.videos), t.status,
                            "; ".join(m for lev, m in trial_checks(p, t) if lev != "info") or "ok", t.notes)
                           for t in p.trials])
        chk = study_checks(p)
        icon = {"error": "⛔", "warn": "⚠", "info": "ℹ"}
        self._quality_items = [f"{icon[lev]} {m}" for lev, m in chk]
        self._render_quality()
        self.quality.setVisible(bool(chk))
        done = sum(t.status == "analysed" for t in p.trials)
        self.progress_label.setText(f"{done} analysed · {len(p.trials)} logged · {p.planned_trials()} planned")

    def _selected(self, t: QTableWidget):
        r = t.currentRow()
        return None if r < 0 or t.item(r, 0) is None else t.item(r, 0).text()

    def _changed(self):
        self.state.save()
        self.state.trialsChanged.emit()

    # ---- project ---------------------------------------------------------------------------
    def new_project(self):
        d = QFileDialog.getExistingDirectory(self, "Choose an empty folder for the new study")
        if not d:
            return
        if (Path(d) / "project.json").exists():
            error_box(self, "Folder already has a study", "Choose an empty folder, or use Open study.")
            return
        names = [v["name"] for v in EXPERIMENTS.values()]
        choice, ok = QInputDialog.getItem(self, "Experiment template", "Start from (conditions stay editable):",
                                          names, 0, False)
        if not ok:
            return
        key = list(EXPERIMENTS)[names.index(choice)]
        name, ok = QInputDialog.getText(self, "Study name", "Name:", text="TrailBuddy pole study")
        if not ok:
            return
        self.state.set_project(Project.new(d, name or "TrailBuddy study", key))
        self.state.status.emit(f"Created study in {d}")

    def open_project(self):
        d = QFileDialog.getExistingDirectory(self, "Open a study folder (contains project.json)")
        if d:
            self.load_path(d)

    def load_path(self, d: str) -> bool:
        try:
            self.state.set_project(Project.load(d))
            return True
        except Exception as e:
            error_box(self, "Cannot open study", f"{d}\n\n{e}")
            return False

    def make_demo(self):
        d = QFileDialog.getExistingDirectory(self, "Choose an empty folder for the demo study")
        if not d:
            return
        from ..core.demo import build_demo_project
        try:
            p = build_demo_project(Path(d) / "TrailBuddy demo study")
        except Exception as e:
            error_box(self, "Demo failed", str(e))
            return
        self.state.set_project(p)
        self.state.status.emit("Demo study created from synthetic data. Open the Results page.")

    # ---- participants ------------------------------------------------------------------------
    def add_participant(self):
        dlg = ParticipantDialog(self)
        if dlg.exec():
            try:
                self.project.add_participant(dlg.value())
            except ValueError as e:
                error_box(self, "Invalid participant", str(e))
                return
            self._changed()

    def edit_participant(self, *_):
        pid = self._selected(self.ptable)
        if not pid:
            return
        p = self.project.participant(pid)
        dlg = ParticipantDialog(self, p)
        if dlg.exec():
            v = dlg.value()
            try:
                v.validate()
            except ValueError as e:
                error_box(self, "Invalid participant", str(e))
                return
            for k in PARTICIPANT_EDIT_FIELDS:
                setattr(p, k, getattr(v, k))
            self._changed()

    def remove_participant(self):
        pid = self._selected(self.ptable)
        if not pid:
            return
        if any(t.participant_id == pid for t in self.project.trials):
            error_box(self, "Participant has trials", "Remove this participant's trials first.")
            return
        self.project.participants = [p for p in self.project.participants if p.id != pid]
        self._changed()

    # ---- conditions ---------------------------------------------------------------------------
    def add_condition(self):
        dlg = QDialog(self); dlg.setWindowTitle("Condition")
        f = QFormLayout(dlg)
        code = QLineEdit(f"C{len(self.project.conditions)}")
        label = QLineEdit()
        poles = QCheckBox("Participant uses poles"); poles.setChecked(True)
        off = QDoubleSpinBox(); off.setRange(-50, 50); off.setSuffix(" cm")
        f.addRow("Code", code); f.addRow("Label", label); f.addRow("", poles); f.addRow("Length offset", off)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); f.addRow(bb)
        if dlg.exec():
            try:
                self.project.add_condition(Condition(code.text().strip().upper(), label.text().strip() or code.text(),
                                                     poles.isChecked(), off.value() if poles.isChecked() else None))
            except ValueError as e:
                error_box(self, "Invalid condition", str(e))
                return
            self._changed()

    def remove_condition(self):
        code = self._selected(self.ctable)
        if not code:
            return
        if any(t.condition_code == code for t in self.project.trials):
            error_box(self, "Condition in use", "Remove trials of this condition first.")
            return
        self.project.conditions = [c for c in self.project.conditions if c.code != code]
        self._changed()

    # ---- trials -----------------------------------------------------------------------------
    def _need_participants(self) -> bool:
        if not self.project.participants:
            error_box(self, "Add a participant first", "Trials belong to a participant. Add P01 etc. first.")
            return False
        return True

    def add_trials(self):
        if not self._need_participants():
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Select trial videos", "", VIDEO_FILTER)
        for f in files:
            dlg = TrialDialog(self, self.project, video=f)
            if not dlg.exec():
                continue
            try:
                self.project.add_trial(dlg.apply(None, [CameraVideo(f, "side", "Camera A")]))
            except (ValueError, KeyError) as e:
                error_box(self, "Cannot add trial", str(e))
        if files:
            self._changed()

    def add_two_cam_trial(self):
        if not self._need_participants():
            return
        a, _ = QFileDialog.getOpenFileName(self, "Camera A (side view)", "", VIDEO_FILTER)
        if not a:
            return
        b, _ = QFileDialog.getOpenFileName(self, "Camera B (second view)", "", VIDEO_FILTER)
        if not b:
            return
        role, ok = QInputDialog.getItem(self, "Camera B view", "Camera B looks at the participant from:",
                                        ["front", "oblique", "side"], 0, False)
        if not ok:
            return
        dlg = TrialDialog(self, self.project, video=a)
        if dlg.exec():
            try:
                t = self.project.add_trial(dlg.apply(None, [CameraVideo(a, "side", "Camera A"), CameraVideo(b, role, "Camera B")]))
            except (ValueError, KeyError) as e:
                error_box(self, "Cannot add trial", str(e))
                return
            self._changed()
            self.state.openTrial.emit(t.id, "two")

    def edit_trial(self):
        if self.state.refuse_if_busy(self):
            return
        tid = self._selected(self.ttable)
        if not tid:
            return
        t = self.project.trial(tid)
        dlg = TrialDialog(self, self.project, t)
        if dlg.exec():
            err = dlg.apply_existing(self.project, t)
            if err:
                error_box(self, "Cannot change the trial", err)
            self._changed()

    def remove_trial(self):
        if self.state.refuse_if_busy(self):
            return
        tid = self._selected(self.ttable)
        if not tid:
            return
        if QMessageBox.question(self, "Delete trial", f"Delete {tid}?\n\nThe trial and its results move to the "
                                "study's trash and can be restored from the Analyse browser (right-click > Restore "
                                "deleted trials). The original video is not touched.") == QMessageBox.StandardButton.Yes:
            self.project.delete_trials([tid])
            self._changed()

    def _toggle_quality(self, *_):
        self._quality_open = not self._quality_open
        self._render_quality()

    def _render_quality(self):
        n = len(self._quality_items)
        head = f"<b>{n} thing{'s' if n != 1 else ''} to check before comparing conditions</b>"
        link = f' &nbsp;<a href="#">{"Hide" if self._quality_open else "Show"} details</a>'
        body = ("<br>" + "<br>".join(self._quality_items)) if self._quality_open else ""
        self.quality.setText(head + link + body)

    def delete_study(self):
        if self.state.refuse_if_busy(self):
            return
        from PySide6.QtCore import QFile
        p = self.project
        if p is None:
            return
        inside = [v.path for t in p.trials for v in t.videos if Path(v.path).resolve().is_relative_to(p.root.resolve())]
        msg = (f"Move the study folder\n{p.root}\nto the system trash?\n\nThis removes the study file, all trial "
               "results, tracking caches and backups. Original videos outside the folder are not touched; you can "
               "restore the folder from the trash.")
        if inside:
            msg += f"\n\nWarning: {len(inside)} video(s) are stored inside this folder and would move too."
        if QMessageBox.question(self, "Delete study", msg) != QMessageBox.StandardButton.Yes:
            return
        root = str(p.root)
        self.state.set_project(None)
        self.state.settings.remove("last_project")
        ok = QFile.moveToTrash(root)
        if not ok:
            error_box(self, "Could not move to trash", f"The folder was left in place:\n{root}")
        else:
            self.state.status.emit("Study moved to the trash.")

    def open_selected(self, *_):
        tid = self._selected(self.ttable)
        if not tid:
            error_box(self, "Select a trial", "Select a trial in the table first.")
            return
        t = self.project.trial(tid)
        self.state.openTrial.emit(tid, "two" if len(t.videos) > 1 else "single")
