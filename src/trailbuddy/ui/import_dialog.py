"""Import a folder of recordings: automatic organisation with a review table the user can correct."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                               QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..core import importer
from .widgets import Worker, error_box, start_worker


class ImportDialog(QDialog):
    COLS = ["File", "Duration", "Res / fps", "Device", "View", "Participant", "Paired with", "Match", "Status"]

    def __init__(self, parent, state, folder: str | None = None):
        super().__init__(parent)
        self.state = state
        self.plan = None
        self.setWindowTitle("Import recordings")
        self.resize(1080, 640)
        lay = QVBoxLayout(self)
        intro = QLabel("The app reads each recording's metadata, detects the camera view from the person's posture, "
                       "groups recordings by participant (clothing colour), and pairs front and side recordings "
                       "by matching their sound. Check the table and correct anything before importing. "
                       "Original files are never modified or moved.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        lay.addWidget(intro)
        row = QHBoxLayout()
        self.folder = QLabel(folder or "No folder chosen")
        self.btn_folder = QPushButton("Choose folder…")
        self.btn_folder.clicked.connect(self._choose)
        row.addWidget(self.btn_folder)
        row.addWidget(self.folder, 1)
        row.addWidget(QLabel("Participants"))
        self.n_part = QSpinBox()
        self.n_part.setRange(1, 12)
        self.n_part.setValue(3)
        row.addWidget(self.n_part)
        self.btn_scan = QPushButton("Analyse folder")
        self.btn_scan.setObjectName("primary")
        self.btn_scan.clicked.connect(self._scan)
        row.addWidget(self.btn_scan)
        lay.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.msg = QLabel("")
        self.msg.setObjectName("muted")
        lay.addWidget(self.progress)
        lay.addWidget(self.msg)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        lay.addWidget(self.table, 1)
        self.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.btn_apply = self.bb.addButton("Create trials", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_apply.setEnabled(False)
        self.bb.accepted.connect(self._apply)
        self.bb.rejected.connect(self.reject)
        lay.addWidget(self.bb)
        self._folder = folder

    def _choose(self):
        d = QFileDialog.getExistingDirectory(self, "Folder with recordings")
        if d:
            self._folder = d
            self.folder.setText(d)

    def _scan(self):
        if not self._folder:
            self._choose()
            if not self._folder:
                return
        self.btn_scan.setEnabled(False)
        self.progress.setVisible(True)
        self.worker = Worker(lambda progress, cancelled: importer.organise(self._folder, self.n_part.value(),
                                                                           progress, cancelled))
        self.worker.progress.connect(self._on_progress)   # bound methods: queued to the UI thread
        self.worker.finished.connect(self._show)
        self.worker.failed.connect(self._on_failed)
        self.thread = start_worker(self, self.worker)

    def _on_progress(self, f: float, m: str):
        self.progress.setValue(int(100 * f))
        self.msg.setText(m)

    def _on_failed(self, m: str):
        error_box(self, "Import failed", m)
        self.btn_scan.setEnabled(True)
        self.progress.setVisible(False)

    def _show(self, plan):
        self.plan = plan
        self.progress.setVisible(False)
        self.btn_scan.setEnabled(True)
        recs = plan["recordings"]
        pairs = {**{p.front: p for p in plan["pairs"]}, **{p.side: p for p in plan["pairs"]}}
        self.table.setRowCount(len(recs))
        parts = sorted({g for g in plan["groups"].values() if g}) or ["P01"]
        self._combos = {}
        for r_i, r in enumerate(recs):
            p = pairs.get(r.name)
            partner = "" if p is None else (p.side if p.front == r.name else p.front)
            vals = [r.name, f"{r.duration_s:.1f} s", f"{r.width}×{r.height} @ {r.fps:.0f}" + (" HDR" if r.hdr else ""),
                    r.device, None, None, partner, "" if p is None else f"{p.score:.2f}",
                    r.issue if not r.usable else ("Needs review" if (p and p.status == "review") else
                                                  ("Paired" if p else "No partner found"))]
            for c, v in enumerate(vals):
                if v is not None:
                    self.table.setItem(r_i, c, QTableWidgetItem(v))
            view = QComboBox()
            view.addItems(["front", "side", "unknown"])
            view.setCurrentText(r.view)
            part = QComboBox()
            part.addItems(parts + ["(skip)"])
            part.setCurrentText(plan["groups"].get(r.name, "(skip)") if r.usable else "(skip)")
            for w in (view, part):
                w.setEnabled(r.usable)
            self.table.setCellWidget(r_i, 4, view)
            self.table.setCellWidget(r_i, 5, part)
            self._combos[r.name] = (view, part)
        n_pairs = len(plan["pairs"])
        n_conf = sum(p.status == "confident" for p in plan["pairs"])
        self.msg.setText(f"{len(recs)} recordings · {sum(r.usable for r in recs)} usable · {n_pairs} front/side pairs "
                         f"({n_conf} confident). Unpaired recordings become single-view trials.")
        self.btn_apply.setEnabled(True)

    def _apply(self):
        if self.plan is None:
            return
        for r in self.plan["recordings"]:
            view, part = self._combos[r.name]
            r.view = view.currentText()
            g = part.currentText()
            if g == "(skip)":
                r.usable = False
            else:
                self.plan["groups"][r.name] = g
        # drop pairs whose members were re-labelled to different participants or views
        keep = []
        recs = {r.name: r for r in self.plan["recordings"]}
        for p in self.plan["pairs"]:
            f, s = recs[p.front], recs[p.side]
            if f.usable and s.usable and f.view == "front" and s.view == "side" and \
                    self.plan["groups"].get(f.name) == self.plan["groups"].get(s.name):
                keep.append(p)
        self.plan["pairs"] = keep
        if self.state.project is None:
            error_box(self, "No study open", "Create or open a study first.")
            return
        created = importer.apply_plan(self.state.project, self.plan)
        self.state.save()
        self.state.trialsChanged.emit()
        self.state.status.emit(f"Imported {len(created)} trials from {Path(self._folder).name}")
        self.accept()


__all__ = ["ImportDialog", "Qt"]
