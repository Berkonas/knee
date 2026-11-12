"""Per-trial result display: metric table with evidence labels, figures, notes."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QPlainTextEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ..core import plots
from ..core.metrics import INFO, KINDS
from .theme import EVIDENCE_COLORS
from .widgets import MplCanvas


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
        h.setStretchLastSection(True)

    def show_metrics(self, metrics):
        self.setRowCount(len(metrics))
        for r, m in enumerate(metrics):
            info = INFO[m.key]
            rng = f"{fmt(m.low)} – {fmt(m.high)}" if m.low is not None and m.high is not None else ""
            vals = [info.label, fmt(m.value), rng, fmt(m.sd), info.unit, KINDS[m.kind], m.note]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
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


class ResultView(QWidget):
    def __init__(self):
        super().__init__()
        self.result = None
        self.tabs = QTabWidget()
        self.table = MetricTable()
        self.tabs.addTab(self.table, "Summary")
        self.canvases = {}
        for key, title in (("kin", "Joint angles"), ("knee", "Knee load"), ("events", "Events"),
                           ("sens", "Sensitivity"), ("cams", "Camera comparison")):
            c = MplCanvas()
            self.canvases[key] = c
            self.tabs.addTab(c, title)
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.tabs.addTab(self.notes, "Methods notes")
        self.btn_save_fig = QPushButton("Save figure…")
        self.btn_save_fig.setToolTip("Save the figure in the current tab as PNG, SVG or PDF")
        self.btn_save_fig.clicked.connect(self._save_fig)
        self.btn_save_fig.setEnabled(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tabs)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.btn_save_fig)
        lay.addLayout(row)
        self.tabs.currentChanged.connect(lambda i: self.btn_save_fig.setEnabled(
            self.result is not None and isinstance(self.tabs.widget(i), MplCanvas)))

    def show_result(self, res, title: str = ""):
        self.result = res
        self.table.show_metrics(res.metrics)
        self.canvases["kin"].set_figure(plots.fig_kinematics(res, f"{title}: joint angles (2D)" if title else ""))
        self.canvases["knee"].set_figure(plots.fig_knee_load(res, f"{title}: knee angle and load" if title else ""))
        self.canvases["events"].set_figure(plots.fig_events(res))
        self.canvases["sens"].set_figure(plots.fig_sensitivity(res))
        self.canvases["cams"].set_figure(self._fig_cams(res))
        q = res.quality
        qtxt = "\n".join(f"  {k}: {v:.3g}" if isinstance(v, float) else f"  {k}: {v}" for k, v in q.items())
        self.notes.setPlainText("Analysis notes\n" + "\n".join(f"• {n}" for n in res.notes) +
                                "\n\nTracking quality\n" + qtxt)
        self.btn_save_fig.setEnabled(isinstance(self.tabs.currentWidget(), MplCanvas))

    def _fig_cams(self, res):
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

    def _save_fig(self):
        w = self.tabs.currentWidget()
        if isinstance(w, MplCanvas):
            w.save_dialog(self, f"{self.tabs.tabText(self.tabs.currentIndex()).lower().replace(' ', '_')}.png")
