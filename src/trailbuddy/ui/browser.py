"""Experiment browser: participants -> trials -> paired recordings, with status, search and filter."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

STATUS_GLYPH = {"analysed": "●", "new": "○", "error": "✕"}


def trial_title(project, t) -> str:
    c = project.condition(t.condition_code)
    label = "condition ?" if c.code == "UNSET" else c.label
    return f"Trial {t.trial_number} · {label}"


class ExperimentBrowser(QWidget):
    trialSelected = Signal(str)
    importRequested = Signal()
    editPairing = Signal(str)
    editBody = Signal(str)

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.setObjectName("browserPanel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 6, 10)
        lay.setSpacing(8)
        head = QHBoxLayout()
        t = QLabel("Experiment")
        t.setObjectName("cardTitle")
        head.addWidget(t)
        head.addStretch(1)
        self.count = QLabel("")
        self.count.setObjectName("muted")
        head.addWidget(self.count)
        lay.addLayout(head)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search participant, trial or file")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        lay.addWidget(self.search)
        self.filter = QComboBox()
        for lab, v in (("All trials", "all"), ("Not analysed", "new"), ("Analysed", "analysed"),
                       ("Needs review", "review")):
            self.filter.addItem(lab, v)
        self.filter.currentIndexChanged.connect(self.refresh)
        lay.addWidget(self.filter)
        self.tree = QTreeWidget()
        self.tree.setObjectName("browser")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setUniformRowHeights(True)
        self.tree.itemSelectionChanged.connect(self._selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.tree, 1)
        self.btn_import = QPushButton("Import recordings…")
        self.btn_import.setToolTip("Scan a folder: detects camera views, participants and front/side pairs")
        self.btn_import.clicked.connect(self.importRequested)
        lay.addWidget(self.btn_import)
        self.legend = QLabel("● analysed  ○ to do  ⚠ check pairing")
        self.legend.setObjectName("muted")
        lay.addWidget(self.legend)
        state.projectChanged.connect(self.refresh)
        state.trialsChanged.connect(self.refresh)
        self.refresh()

    def _match(self, t, text: str, flt: str) -> bool:
        review = "review" in (t.sync.get("pair_status", "") or "") or "review" in t.notes.lower() or \
                 len(t.videos) < 2
        if flt == "new" and t.status == "analysed":
            return False
        if flt == "analysed" and t.status != "analysed":
            return False
        if flt == "review" and not review:
            return False
        if not text:
            return True
        hay = " ".join([t.id, t.participant_id, t.condition_code, t.notes] + [Path(v.path).name for v in t.videos])
        return text.lower() in hay.lower()

    def refresh(self):
        p = self.state.project
        sel = self.current_trial()
        self.tree.blockSignals(True)
        self.tree.clear()
        if p is None:
            self.count.setText("")
            self.tree.blockSignals(False)
            return
        text, flt = self.search.text().strip(), self.filter.currentData()
        n = 0
        for part in p.participants:
            trials = [t for t in p.trials if t.participant_id == part.id and self._match(t, text, flt)]
            if not trials and (text or flt != "all"):
                continue
            pi = QTreeWidgetItem([f"{part.id}  ·  {len(trials)} trials" + ("" if part.metrics_entered else "  ·  !")])
            pi.setToolTip(0, f"{part.body_mass_kg:g} kg, {part.height_m:g} m" + ("" if part.metrics_entered else
                             "\nBody metrics are placeholders: right-click > Body metrics…"))
            pi.setData(0, Qt.ItemDataRole.UserRole, ("participant", part.id))
            f = pi.font(0)
            f.setBold(True)
            pi.setFont(0, f)
            self.tree.addTopLevelItem(pi)
            for t in sorted(trials, key=lambda x: (x.condition_code, x.trial_number)):
                review = (t.sync.get("pair_status") == "review") or len(t.videos) < 2
                glyph = "⚠" if review and t.status != "analysed" else STATUS_GLYPH.get(t.status, "○")
                ti = QTreeWidgetItem([f"{glyph}  {trial_title(p, t)}"])
                ti.setData(0, Qt.ItemDataRole.UserRole, ("trial", t.id))
                tip = [t.id]
                if t.sync.get("pair_score") is not None:
                    tip.append(f"Pair match {t.sync['pair_score']:.2f} ({t.sync.get('pair_status')})")
                if t.notes:
                    tip.append(t.notes)
                ti.setToolTip(0, "\n".join(tip))
                pi.addChild(ti)
                for v in t.videos:
                    m = v.meta or {}
                    info = f"{m.get('duration_s', 0):.1f} s · {m.get('fps', 0):.0f} fps" if m else ""
                    vi = QTreeWidgetItem([f"{v.role.capitalize():5}  {Path(v.path).name}   {info}"])
                    vi.setData(0, Qt.ItemDataRole.UserRole, ("video", t.id))
                    vi.setToolTip(0, f"{v.path}\n{m.get('width', '?')}×{m.get('height', '?')}, {m.get('device', '')}"
                                     f"{', HDR' if m.get('hdr') else ''}")
                    vi.setForeground(0, self.palette().placeholderText())
                    ti.addChild(vi)
                n += 1
            pi.setExpanded(True)
        self.count.setText(f"{n} trials")
        self.tree.blockSignals(False)
        if sel:
            self.select_trial(sel)

    def current_trial(self) -> str | None:
        it = self.tree.currentItem()
        if it is None:
            return None
        kind, val = it.data(0, Qt.ItemDataRole.UserRole) or (None, None)
        return val if kind in ("trial", "video") else None

    def select_trial(self, tid: str):
        for i in range(self.tree.topLevelItemCount()):
            pi = self.tree.topLevelItem(i)
            for j in range(pi.childCount()):
                ti = pi.child(j)
                if ti.data(0, Qt.ItemDataRole.UserRole) == ("trial", tid):
                    self.tree.setCurrentItem(ti)
                    return

    def _selected(self):
        tid = self.current_trial()
        if tid:
            self.trialSelected.emit(tid)

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        if it is None:
            return
        kind, val = it.data(0, Qt.ItemDataRole.UserRole)
        m = QMenu(self)
        if kind in ("trial", "video"):
            m.addAction("Edit pairing and sync…", lambda: self.editPairing.emit(val))
        if kind == "participant":
            m.addAction("Body metrics…", lambda: self.editBody.emit(val))
        m.exec(self.tree.viewport().mapToGlobal(pos))
