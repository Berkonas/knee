"""Per-trial report: metric cards (with reference bands), movement timeline, stick figures, tables."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from ..core import plots, reference
from ..core.metrics import CATEGORIES, INFO, KINDS, SHORT_KINDS
from .components import MetricCard
from .result_view import MetricTable, fmt
from .widgets import MplCanvas


def card_for(m) -> MetricCard:
    info = INFO[m.key]
    ref = reference.RANGES.get(m.key)
    status = reference.classify(m.key, m.value) if m.kind != "unavailable" else None
    band = (m.value, ref.low, ref.high, m.low, m.high) if (ref and m.value is not None) else None
    ref_text = (f"Typical {fmt(ref.low)}–{fmt(ref.high)} {info.unit}: {ref.context} ({ref.source})" if ref else "")
    range_text = (f"Model range {fmt(m.low)}–{fmt(m.high)} (sensitivity to assumptions)"
                  if m.low is not None and m.high is not None else "")
    sd = f" ± {fmt(m.sd)}" if m.sd is not None else ""
    value = "Unavailable" if m.kind == "unavailable" or m.value is None else f"{fmt(m.value)}{sd}"
    tip = (f"<b>{info.label}</b> · {KINDS[m.kind]}<br><b>What:</b> {info.what}<br><b>Why it matters:</b> {info.why}<br>"
           f"<b>Can conclude:</b> {info.conclude}<br><b>Cannot conclude:</b> {info.not_conclude}")
    note = m.note if m.kind == "unavailable" or m.key in ("quad_force_peak", "tibiofemoral_compression") else ""
    return MetricCard(info.label, value, info.unit, m.kind, SHORT_KINDS[m.kind], note, band, status, ref_text, tip,
                      range_text)


class FigureBlock(QWidget):
    def __init__(self, title: str, height: int):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        t = QLabel(title)
        t.setObjectName("groupTitle")
        row.addWidget(t)
        row.addStretch(1)
        self.btn = QPushButton("Save figure…")
        row.addWidget(self.btn)
        lay.addLayout(row)
        self.canvas = MplCanvas()
        self.canvas.setFixedHeight(height)
        lay.addWidget(self.canvas)
        self.btn.clicked.connect(lambda: self.canvas.save_dialog(self, title.lower().replace(" ", "_") + ".png"))


class ReportView(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setObjectName("reportScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result = None
        inner = QWidget()
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(4, 4, 12, 16)
        self.lay.setSpacing(6)
        self.title = QLabel("No results yet")
        self.title.setObjectName("reportTitle")
        self.chips = QHBoxLayout()
        self.lay.addWidget(self.title)
        self.lay.addLayout(self.chips)
        self.empty = QLabel("Set up the trial on the left and click Run analysis. The report shows every metric "
                            "against published reference ranges, a movement timeline and the leg's motion.")
        self.empty.setObjectName("muted")
        self.empty.setWordWrap(True)
        self.lay.addWidget(self.empty)
        self.cards_host = QWidget()
        self.cards_lay = QVBoxLayout(self.cards_host)
        self.cards_lay.setContentsMargins(0, 0, 0, 0)
        self.lay.addWidget(self.cards_host)
        self.figs = {
            "timeline": FigureBlock("Movement timeline", 640),
            "stick": FigureBlock("Leg motion through stance", 300),
            "curves": FigureBlock("Stance-normalised knee curves", 300),
            "sens": FigureBlock("Sensitivity to model assumptions", 300),
            "cams": FigureBlock("Camera comparison", 300),
        }
        for f in self.figs.values():
            self.lay.addWidget(f)
            f.setVisible(False)
        t = QLabel("All numbers")
        t.setObjectName("groupTitle")
        self.lay.addWidget(t)
        self.table = MetricTable()
        self.table.setMinimumHeight(360)
        self.lay.addWidget(self.table)
        t = QLabel("Analysis notes and tracking quality")
        t.setObjectName("groupTitle")
        self.lay.addWidget(t)
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(180)
        self.lay.addWidget(self.notes)
        self.lay.addStretch(1)
        self.setWidget(inner)
        self._cards = []
        self._grids = []
        self._reflow = QTimer(self)
        self._reflow.setSingleShot(True)
        self._reflow.setInterval(60)
        self._reflow.timeout.connect(self._layout_cards)

    # ---------------------------------------------------------------------------------------
    def show_result(self, res, title: str = "", subtitle: str = ""):
        self.result = res
        self.empty.setVisible(False)
        self.title.setText(title or "Trial report")
        while self.chips.count():
            w = self.chips.takeAt(0).widget()
            if w:
                w.deleteLater()
        q = res.quality
        chips = [f"{res.side.capitalize()} side analysed", subtitle,
                 f"Person detected in {100 * q.get('detection_rate', 0):.0f}% of frames",
                 f"{q.get('pct_interpolated', 0):.1f}% of points interpolated"]
        for c in chips:
            if c:
                lab = QLabel(c)
                lab.setObjectName("chip")
                self.chips.addWidget(lab)
        if q.get("double_support_unknown"):
            lab = QLabel("Double support not visible: knee loads are an upper bound")
            lab.setObjectName("chipWarn")
            self.chips.addWidget(lab)
        self.chips.addStretch(1)
        # cards grouped by category
        for g in self._grids:
            g.deleteLater()
        self._grids, self._cards = [], []
        while self.cards_lay.count():
            it = self.cards_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        present = {m.key: m for m in res.metrics}
        for cat, keys in CATEGORIES.items():
            ms = [present[k] for k in keys if k in present]
            if not ms:
                continue
            t = QLabel(cat)
            t.setObjectName("groupTitle")
            self.cards_lay.addWidget(t)
            host = QWidget()
            grid = QGridLayout(host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(10)
            cards = [card_for(m) for m in ms]
            self._cards.append((grid, cards))
            self._grids.append(host)
            self.cards_lay.addWidget(host)
        self._layout_cards()
        # figures
        self.figs["timeline"].canvas.set_figure(plots.fig_timeline(res, title))
        self.figs["stick"].canvas.set_figure(plots.fig_stick_strip(res))
        self.figs["curves"].canvas.set_figure(self._curves(res))
        self.figs["sens"].canvas.set_figure(plots.fig_sensitivity(res))
        has_b = any(c.startswith("camB_") for c in res.timeseries.columns)
        if has_b:
            from .result_view import camera_figure
            self.figs["cams"].canvas.set_figure(camera_figure(res))
        for k, f in self.figs.items():
            f.setVisible(k != "cams" or has_b)
        self.table.show_metrics(res.metrics)
        qtxt = "\n".join(f"  {k}: {v:.3g}" if isinstance(v, float) else f"  {k}: {v}" for k, v in q.items())
        self.notes.setPlainText("Notes\n" + "\n".join(f"• {n}" for n in res.notes) + "\n\nTracking quality\n" + qtxt)

    def _curves(self, res):
        from ..core.compare import stance_curves
        s = res.side
        fig, axs = plots._fig(7.2, 2.9, 1, 2)
        x = np.linspace(0, 100, 101)
        for ax, col, lab, c in ((axs[0], f"{s}_knee_flexion_deg", "Knee flexion (deg)", plots.PALETTE[0]),
                                (axs[1], f"{s}_knee_extensor_moment_nm", "Knee extensor moment (N·m)", plots.PALETTE[1])):
            cur = stance_curves(res, col)
            if len(cur):
                for k in cur:
                    ax.plot(x, k, color=c, alpha=0.25, lw=0.8)
                ax.plot(x, np.nanmean(cur, axis=0), color=c, lw=2, label=f"mean of {len(cur)} stances")
                ax.legend(frameon=False)
            else:
                ax.text(0.5, 0.5, "No complete stance", ha="center", va="center", transform=ax.transAxes)
            ax.set_xlabel("Stance (%)")
            ax.set_ylabel(lab)
        return fig

    def _layout_cards(self):
        cols = max(1, min(4, (self.viewport().width() - 20) // 250))
        for grid, cards in self._cards:
            for i, c in enumerate(cards):
                grid.addWidget(c, i // cols, i % cols)
            for k in range(4):
                grid.setColumnStretch(k, 1 if k < cols else 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reflow.start()


__all__ = ["ReportView", "QSizePolicy"]
