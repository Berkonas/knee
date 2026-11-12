"""Per-trial result display: metric table with evidence labels, figures, notes."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from ..core import plots
from ..core.metrics import INFO, KINDS
from .theme import EVIDENCE_COLORS


def fmt(v, digits=3):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "–"
    a = abs(v)
    if a >= 100:
        return f"{v:.0f}"
    if a >= 10:
        return f"{v:.1f}"
    return f"{v:.{digits - 1}f}"


class MetricTable(QTableWidget):
    COLS = ["Metric", "Value", "Range (sensitivity)", "SD", "Unit", "Evidence", "Note"]

    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrap(False)
        self.setColumnWidth(0, 260)

    def show_metrics(self, metrics):
        self.setRowCount(len(metrics))
        for r, m in enumerate(metrics):
            info = INFO[m.key]
            rng = f"{fmt(m.low)} – {fmt(m.high)}" if m.low is not None and m.high is not None else ""
            vals = [info.label, fmt(m.value), rng, fmt(m.sd), info.unit, KINDS[m.kind], m.note]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 6 and v:
                    it.setToolTip(v)
                if c == 0:
                    it.setToolTip(f"<b>{info.label}</b><br><b>What:</b> {info.what}<br><b>Why:</b> {info.why}"
                                  f"<br><b>Can conclude:</b> {info.conclude}<br><b>Cannot conclude:</b> {info.not_conclude}")
                if c in (1, 2, 3):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 5:
                    from PySide6.QtGui import QColor
                    bg, fg = EVIDENCE_COLORS[m.kind]
                    it.setBackground(QColor(bg))
                    it.setForeground(QColor(fg))
                self.setItem(r, c, it)


def camera_figure(res):
    if True:  # noqa: SIM108
        ts = res.timeseries
        fig, ax = plots._fig(6.5, 3.2)
        s = res.side
        if f"camB_{s}_knee_flexion_deg" not in ts:
            ax.text(0.5, 0.5, "Two-camera trials only", ha="center", va="center", transform=ax.transAxes)
            return fig
        ax.plot(ts.time_s, ts[f"{s}_knee_flexion_deg"], label="Camera A (2D)", color=plots.PALETTE[0])
        ax.plot(ts.time_s, ts[f"camB_{s}_knee_flexion_deg"], label="Camera B (2D projection)", color=plots.PALETTE[1])
        if f"camB_{s}_knee_fppa_deg" in ts:
            ax.plot(ts.time_s, ts[f"camB_{s}_knee_fppa_deg"], label="Camera B frontal-plane projection angle",
                    color=plots.PALETTE[2], ls="--")
        if f"{s}_knee_flexion_3d_deg" in ts:
            ax.plot(ts.time_s, ts[f"{s}_knee_flexion_3d_deg"], label="3D (calibrated, unvalidated)", color="k")
        ax.set_xlabel("Time (s, camera A clock)")
        ax.set_ylabel("Angle (deg)")
        ax.set_title(f"Knee angle by camera, {s} side")
        ax.legend(frameon=False)
        return fig

