"""Methods page: how each number is produced and what it can and cannot support."""

from __future__ import annotations

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from ..core.metrics import INFO, KINDS
from .theme import EVIDENCE_COLORS
from .widgets import page_header

INTRO = """
<h3>Evidence labels</h3>
<p>Every number in the app and in exports carries one of these labels:</p>
<p>{badges}</p>
<h3>Models in plain words</h3>
<ul>
<li><b>Joint angles</b> come from MediaPipe Pose landmarks, filtered with a 6&nbsp;Hz zero-lag Butterworth filter.
They are 2D projections onto the image plane: accurate only when the camera faces the side of the motion.</li>
<li><b>Foot and pole contacts</b> are found where the foot (or pole tip) stops moving. Check them on the video.</li>
<li><b>Knee extensor moment without a force plate</b> uses a quasi-static model: the foot carries body weight
(minus any pole support), acting straight up through an assumed point on the foot.
M<sub>knee</sub> = F<sub>foot</sub> × horizontal distance from that point to the knee. Impact peaks and horizontal
forces are not captured, so these are <i>scenario</i> estimates for comparing conditions.</li>
<li><b>With a force plate</b>, 2D Newton–Euler inverse dynamics (foot → shank → thigh) with Winter (2009)
segment parameters gives ankle, knee and hip moments.</li>
<li><b>Quadriceps force</b> = knee extensor moment ÷ patellar tendon moment arm (nominal 5&nbsp;cm, range 4–6&nbsp;cm
from in vivo and cadaver studies). Co-contraction is ignored.</li>
<li><b>Arm moments</b> treat the pole as pushing along its own axis on the hand. Pole force must be measured or
assumed; it cannot be read from ordinary video.</li>
<li><b>Mechanical demand</b>: knee extensor angular impulse (moment × time) and negative knee work. These describe
mechanical loading. They are not fatigue, pain or injury risk.</li>
</ul>
<p>Full equations, assumptions and references: <code>docs/methods.md</code> in the project repository.</p>
<h3>Metric reference</h3>
"""


class MethodsPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.addWidget(page_header("Methods", "What each number means, how it is calculated, and its limits."))
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        badges = " ".join(f'<span style="background:{EVIDENCE_COLORS[k][0]}; color:{EVIDENCE_COLORS[k][1]};">'
                          f'&nbsp;{v}&nbsp;</span>' for k, v in KINDS.items())
        html = INTRO.format(badges=badges)
        for i in INFO.values():
            html += (f"<h4>{i.label} <span style='color:#5E6E6B'>({i.unit})</span></h4>"
                     f"<p><b>What we measure:</b> {i.what}<br><b>Why it matters:</b> {i.why}<br>"
                     f"<b>What we can conclude:</b> {i.conclude}<br><b>What we cannot conclude:</b> {i.not_conclude}</p>")
        tb.setHtml(html)
        lay.addWidget(tb, 1)
