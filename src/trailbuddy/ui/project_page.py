"""Project page: create/open a study, participants, conditions, trial log."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from ..core.project import EXPERIMENTS, CameraVideo, Condition, Participant, Project, Trial, parse_filename
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
    return t


def fill(t: QTableWidget, rows):
    t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            t.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))


class ParticipantDialog(QDialog):
    def __init__(self, parent, p: Participant | None = None):
        super().__init__(parent)
        self.setWindowTitle("Participant")
        f = QFormLayout(self)
        self.pid = QLineEdit(p.id if p else "")
        self.pid.setPlaceholderText("P01 (code only, no names)")
        self.mass = QDoubleSpinBox(); self.mass.setRange(20, 250); self.mass.setSuffix(" kg"); self.mass.setValue(p.body_mass_kg if p else 70)
        self.height = QDoubleSpinBox(); self.height.setRange(1, 2.5); self.height.setDecimals(3); self.height.setSuffix(" m"); self.height.setValue(p.height_m if p else 1.75)
        self.leg = QDoubleSpinBox(); self.leg.setRange(0, 1.5); self.leg.setDecimals(3); self.leg.setSuffix(" m"); self.leg.setSpecialValueText("not measured"); self.leg.setValue(p.leg_length_m or 0 if p else 0)
        self.pole = QDoubleSpinBox(); self.pole.setRange(0, 160); self.pole.setDecimals(1); self.pole.setSuffix(" cm"); self.pole.setSpecialValueText("not set"); self.pole.setValue(p.standard_pole_length_cm or 0 if p else 0)
        self.pole.setToolTip("Standard length: ~90° elbow angle with the tip on level ground.")
        self.notes = QLineEdit(p.notes if p else "")
        f.addRow("Participant ID", self.pid)
        f.addRow("Body mass", self.mass)
        f.addRow("Height", self.height)
        f.addRow("Leg length", self.leg)
        f.addRow("Standard pole length", self.pole)
        f.addRow("Notes", self.notes)
        if p:
            self.pid.setEnabled(False)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def value(self) -> Participant:
        return Participant(self.pid.text().strip(), self.mass.value(), self.height.value(),
                           self.leg.value() or None, self.pole.value() or None, {}, self.notes.text())


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
        if trial:
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
        f.addRow("Pole length", self.pole)
        f.addRow("Step height", self.step_h)
        f.addRow("Step depth", self.step_d)
        f.addRow("Camera setup", self.cam)
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
        trial.stair.update(step_height_m=self.step_h.value(), step_depth_m=self.step_d.value())
        return trial


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
        for b in (self.btn_new, self.btn_open, self.btn_demo):
            row.addWidget(b)
        row.addStretch(1)
        self.info = QLabel("No study open.")
        self.info.setObjectName("muted")
        row.addWidget(self.info)
        lay.addLayout(row)

        split = QSplitter(Qt.Orientation.Vertical)
        top = QWidget(); tl = QHBoxLayout(top); tl.setContentsMargins(0, 0, 0, 0)
        # participants
        pw = QWidget(); pl = QVBoxLayout(pw); pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(section("Participants"))
        self.ptable = table(["ID", "Mass (kg)", "Height (m)", "Leg (m)", "Std pole (cm)", "Notes"])
        self.ptable.doubleClicked.connect(self.edit_participant)
        pl.addWidget(self.ptable)
        r = QHBoxLayout()
        self.btn_padd = QPushButton("Add participant"); self.btn_padd.clicked.connect(self.add_participant)
        self.btn_pedit = QPushButton("Edit"); self.btn_pedit.clicked.connect(self.edit_participant)
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
        self.ttable = table(["Trial", "Participant", "Condition", "#", "Pole (cm)", "Cameras", "Status", "Notes"])
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
                  self.btn_tadd2, self.btn_tedit, self.btn_tdel, self.btn_topen):
            b.setEnabled(has)
        if not has:
            self.info.setText("No study open.")
            for t in (self.ptable, self.ctable, self.ttable):
                t.setRowCount(0)
            return
        self.info.setText(f"{p.name}  ·  {EXPERIMENTS.get(p.experiment, {}).get('name', p.experiment)}  ·  {p.root}")
        fill(self.ptable, [(q.id, q.body_mass_kg, q.height_m, q.leg_length_m, q.standard_pole_length_cm, q.notes)
                           for q in p.participants])
        fill(self.ctable, [(c.code, c.label, "yes" if c.uses_poles else "no",
                            "" if c.pole_offset_cm is None else f"{c.pole_offset_cm:+g}") for c in p.conditions])
        fill(self.ttable, [(t.id, t.participant_id, t.condition_code, t.trial_number, t.pole_length_cm,
                            len(t.videos), t.status, t.notes) for t in p.trials])
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
            p.body_mass_kg, p.height_m, p.leg_length_m = v.body_mass_kg, v.height_m, v.leg_length_m
            p.standard_pole_length_cm, p.notes = v.standard_pole_length_cm, v.notes
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
        tid = self._selected(self.ttable)
        if not tid:
            return
        t = self.project.trial(tid)
        dlg = TrialDialog(self, self.project, t)
        if dlg.exec():
            dlg.apply(t, t.videos)
            self._changed()

    def remove_trial(self):
        tid = self._selected(self.ttable)
        if not tid:
            return
        if QMessageBox.question(self, "Remove trial", f"Remove {tid} from the study log?\n"
                                "The original video and any result files on disk are kept.") \
                == QMessageBox.StandardButton.Yes:
            self.project.remove_trial(tid)
            self._changed()

    def open_selected(self, *_):
        tid = self._selected(self.ttable)
        if not tid:
            error_box(self, "Select a trial", "Select a trial in the table first.")
            return
        t = self.project.trial(tid)
        self.state.openTrial.emit(tid, "two" if len(t.videos) > 1 else "single")
