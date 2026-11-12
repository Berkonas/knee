"""Results across trials: condition comparisons, paired changes, trade-off, exports."""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QSplitter, QTabWidget,
                               QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from ..core import compare, export, plots
from ..core.metrics import INFO
from .project_page import fill, table
from .single_page import open_folder
from .widgets import MplCanvas, error_box, page_header

METRIC_CHOICES = ["quad_force_peak", "knee_ext_moment_peak", "knee_ext_impulse_total", "knee_neg_work",
                  "knee_flexion_peak", "shoulder_moment_peak", "elbow_moment_peak", "shoulder_flexion_peak",
                  "elbow_flexion_mean", "trunk_lean_mean", "speed", "cadence", "stance_time_mean",
                  "pole_support_fraction", "pole_angle_at_contact"]


class ResultsPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.setObjectName("page")
        self.state = state
        self.long = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.addWidget(page_header("Results", "Compare conditions within each participant. Trials are averaged per "
                                  "participant first; group values are descriptive only (n = 3, no significance tests)."))
        row = QHBoxLayout()
        row.addWidget(QLabel("Metric"))
        self.metric = QComboBox()
        for k in METRIC_CHOICES:
            self.metric.addItem(f"{INFO[k].label} ({INFO[k].unit})", k)
        row.addWidget(self.metric)
        row.addWidget(QLabel("Baseline"))
        self.baseline = QComboBox()
        row.addWidget(self.baseline)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        row.addWidget(self.btn_refresh)
        row.addStretch(1)
        self.btn_export = QPushButton("Export all results…")
        self.btn_export.setObjectName("primary")
        self.btn_export.setToolTip("CSV tables, Excel workbook, PNG/SVG/PDF figures and a plain-language summary.")
        self.btn_export.clicked.connect(self.export)
        row.addWidget(self.btn_export)
        lay.addLayout(row)
        self.explain = QLabel("")
        self.explain.setWordWrap(True)
        self.explain.setObjectName("muted")
        lay.addWidget(self.explain)
        split = QSplitter(Qt.Orientation.Vertical)
        self.tabs = QTabWidget()
        self.c_cond, self.c_pair, self.c_trade, self.c_curve = MplCanvas(), MplCanvas(), MplCanvas(), MplCanvas()
        self.tabs.addTab(self.c_cond, "By condition")
        self.tabs.addTab(self.c_pair, "Paired change")
        self.tabs.addTab(self.c_trade, "Knee vs arm trade-off")
        self.tabs.addTab(self.c_curve, "Stance curves")
        split.addWidget(self.tabs)
        bottom = QTabWidget()
        self.t_within = table(["Participant", "Condition", "Baseline mean", "Condition mean", "Difference", "% change", "n"])
        self.t_group = table(["Condition", "Participants", "Mean % change", "Min %", "Max %", "Lower in"])
        bottom.addTab(self.t_within, "Within-participant")
        bottom.addTab(self.t_group, "Group (descriptive)")
        split.addWidget(bottom)
        split.setSizes([420, 220])
        lay.addWidget(split, 1)
        brow = QHBoxLayout()
        brow.addStretch(1)
        self.btn_savefig = QPushButton("Save figure…")
        self.btn_savefig.clicked.connect(lambda: self.tabs.currentWidget().save_dialog(self, f"{self.metric.currentData()}.png"))
        brow.addWidget(self.btn_savefig)
        lay.addLayout(brow)
        self.metric.currentIndexChanged.connect(self.update_views)
        self.baseline.currentIndexChanged.connect(self.update_views)
        state.resultsChanged.connect(self.refresh)
        state.projectChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        p = self.state.project
        self.baseline.blockSignals(True)
        self.baseline.clear()
        if p:
            for c in p.conditions:
                self.baseline.addItem(f"{c.code} – {c.label}", c.code)
        self.baseline.blockSignals(False)
        self.long = compare.collect(p) if p else None
        has = self.long is not None and not self.long.empty
        self.btn_export.setEnabled(has)
        self.btn_savefig.setEnabled(has)
        self.update_views()

    def update_views(self, *_):
        m = self.metric.currentData()
        info = INFO[m]
        self.explain.setText(f"{info.what} Why it matters: {info.why} Cannot conclude: {info.not_conclude}")
        p = self.state.project
        if self.long is None or self.long.empty:
            for c in (self.c_cond, self.c_pair, self.c_trade, self.c_curve):
                fig, ax = plots._fig()
                ax.text(0.5, 0.5, "No analysed trials yet. Analyse trials, or create the demo study.",
                        ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
                c.set_figure(fig)
            fill(self.t_within, []); fill(self.t_group, [])
            return
        base = self.baseline.currentData() or "C0"
        conds = [c.code for c in p.conditions]
        self.c_cond.set_figure(plots.fig_condition_comparison(self.long, m, conds))
        w = compare.within_participant(self.long, m, base)
        self.c_pair.set_figure(plots.fig_paired_change(w, m))
        self.c_trade.set_figure(plots.fig_tradeoff(self.long))
        self.c_curve.set_figure(self._curves(p))
        from .result_view import fmt as f
        fill(self.t_within, [(r.participant, r.condition, f(r.baseline_mean), f(r.condition_mean), f(r.abs_diff),
                              f"{r.pct_diff:+.1f}%", f"{r.n_baseline} / {r.n_condition}") for r in w.itertuples()])
        g = compare.group_summary(self.long, m, base)
        fill(self.t_group, [(r.condition, r.n_participants, f"{r.mean_pct_diff:+.1f}%", f"{r.min_pct_diff:+.1f}%",
                             f"{r.max_pct_diff:+.1f}%", f"{r.n_reduced} of {r.n_participants}") for r in g.itertuples()])

    def _curves(self, p):
        results = compare.load_all_results(p)
        by = {}
        for tid, res in results.items():
            c = compare.stance_curves(res, f"{res.side}_knee_extensor_moment_nm")
            if len(c):
                by.setdefault(p.trial(tid).condition_code, []).append(c / p.participant(p.trial(tid).participant_id).body_mass_kg)
        by = {k: np.vstack(v) for k, v in sorted(by.items())}
        return plots.fig_stance_normalised(by, "Knee extensor moment (N·m/kg)",
                                           "Knee extensor moment over stance (mean ± SD of stances)")

    def export(self):
        d = QFileDialog.getExistingDirectory(self, "Export to folder")
        if not d:
            return
        try:
            files = export.export_project(self.state.project, d, self.baseline.currentData() or "C0")
        except Exception as e:
            error_box(self, "Export failed", str(e))
            return
        self.state.status.emit(f"Exported {len(files)} tables and figures to {d}")
        open_folder(files["summary_md"].parent)
