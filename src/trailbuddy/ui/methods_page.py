"""Methods: a compact reference. Evidence labels, analysis modes, the core equations, and a searchable
metric list; the full derivations live in RESEARCH_PIPELINE.md and docs/calculation-audit.md."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QLineEdit, QSplitter, QTableWidget, QTableWidgetItem,
                               QTextBrowser, QVBoxLayout, QWidget)

from ..core.metrics import INFO, KINDS
from .theme import EVIDENCE_COLORS
from .widgets import page_header

SUMMARY = """
<p><b>Evidence labels.</b> {badges}</p>
<p><b>Analysis modes.</b> <b>A</b> video-only kinematics: angles, timing, pole geometry, no forces.
<b>B</b> scenario: loads from stated assumptions (body weight, support share, COP, pole force).
<b>C</b> measured: loads from imported force-plate, insole or pole load-cell data.</p>
<table cellspacing="0" cellpadding="4">
<tr><td><b>Support</b></td><td>F<sub>feet</sub> + Σ F<sub>pole</sub>·cos θ<sub>pole</sub> ≈ m·g (static) or m·(g + a<sub>COM</sub>)</td></tr>
<tr><td><b>Knee moment</b></td><td>M<sub>knee</sub> = (x<sub>knee</sub> − x<sub>COP</sub>)·F<sub>y</sub> + (y<sub>COP</sub> − y<sub>knee</sub>)·F<sub>x</sub>;
force from the COP toward the body COM (vertical force is an alternative assumption; the sensitivity range covers both)</td></tr>
<tr><td><b>Quadriceps</b></td><td>F<sub>quad</sub> ≈ M<sub>knee</sub> / r, r = 5 cm (4–6 cm). Net-moment equivalent, not tendon or contact force</td></tr>
<tr><td><b>Shoulder, elbow</b></td><td>M = (r<sub>grip</sub> − r<sub>joint</sub>) × F<sub>pole</sub> + arm-segment weight terms</td></tr>
<tr><td><b>Power, work</b></td><td>P = M<sub>knee</sub>·ω<sub>ext</sub>; negative work = ∫ min(P, 0) dt; impulse = ∫ max(M, 0) dt</td></tr>
<tr><td><b>Measured force</b></td><td>2D Newton–Euler: F<sub>p</sub> = m a − m g − F<sub>d</sub>; M<sub>p</sub> = Iα − M<sub>d</sub> − r<sub>p</sub>×F<sub>p</sub> − r<sub>d</sub>×F<sub>d</sub></td></tr>
</table>
<p><b>Never estimated from video:</b> tibiofemoral compression, shoulder contact force, fatigue, pain or injury risk.</p>
<p style="color:#7A8582">Full equations, assumptions and references: RESEARCH_PIPELINE.md and docs/calculation-audit.md
in the project folder.</p>
"""


class MethodsPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.addWidget(page_header("Methods", "How each number is produced, and what it can and cannot support."))
        split = QSplitter(Qt.Orientation.Vertical)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        badges = " ".join(f'<span style="background:{EVIDENCE_COLORS[k][0]}; color:{EVIDENCE_COLORS[k][1]};">'
                          f'&nbsp;{v}&nbsp;</span>' for k, v in KINDS.items())
        tb.setHtml(SUMMARY.format(badges=badges))
        split.addWidget(tb)
        ref = QWidget()
        rv = QVBoxLayout(ref)
        rv.setContentsMargins(0, 8, 0, 0)
        row = QHBoxLayout()
        cap = QLabel("Metric reference")
        cap.setObjectName("cardTitle")
        row.addWidget(cap)
        row.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search metrics")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(280)
        self.search.textChanged.connect(self._filter)
        row.addWidget(self.search)
        rv.addLayout(row)
        self.table = QTableWidget(len(INFO), 3)
        self.table.setHorizontalHeaderLabels(["Metric", "Unit", "What it is"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for r, i in enumerate(INFO.values()):
            for c, txt in enumerate((i.label, i.unit, i.what)):
                it = QTableWidgetItem(txt)
                it.setToolTip(f"<b>{i.label}</b><br>{i.what}<br><b>Why:</b> {i.why}<br><b>Can conclude:</b> {i.conclude}"
                              f"<br><b>Cannot conclude:</b> {i.not_conclude}")
                self.table.setItem(r, c, it)
        rv.addWidget(self.table, 1)
        split.addWidget(ref)
        split.setSizes([330, 420])
        lay.addWidget(split, 1)

    def _filter(self, text: str):
        q = text.lower().strip()
        for r in range(self.table.rowCount()):
            hit = not q or any(q in (self.table.item(r, c).text().lower()) for c in range(3))
            self.table.setRowHidden(r, not hit)
