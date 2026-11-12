"""Study results: every metric compared across conditions within each participant."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QSplitter,
                               QStackedWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import compare, export, plots
from ..core.metrics import INFO
from .components import Segmented
from .project_page import table
from .result_view import fmt
from .single_page import open_folder
from .widgets import MplCanvas, error_box

METRIC_CHOICES = ["quad_force_peak", "knee_ext_moment_peak", "knee_ext_impulse_per_step", "knee_ext_impulse_total",
                  "knee_neg_work", "knee_power_absorption_peak", "knee_flexion_peak", "knee_flexion_at_contact",
                  "knee_flexion_velocity_peak", "hip_flexion_peak", "ankle_dorsiflexion_peak", "trunk_lean_mean",
                  "shoulder_flexion_peak", "elbow_flexion_mean", "shoulder_moment_peak", "elbow_moment_peak",
                  "pole_support_fraction", "pole_angle_at_contact", "speed", "cadence", "stance_time_mean",
                  "step_time_cv"]

VIEWS = ["Overview", "By condition", "Pole length", "Repetitions", "Trade-off", "Stance curves"]


class ResultsPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.setObjectName("page")
        self.state = state
        self.long = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 14)
        lay.setSpacing(10)
        head = QHBoxLayout()
        t = QLabel("Results")
        t.setObjectName("pageTitle")
        head.addWidget(t)
        head.addSpacing(16)
        self.view = Segmented(VIEWS)
        self.view.changed.connect(self._view_changed)
        head.addWidget(self.view)
        head.addStretch(1)
        self.btn_export = QPushButton("Export all results…")
        self.btn_export.setObjectName("primary")
        self.btn_export.setToolTip("Raw data, CSV and Excel tables, PNG/SVG/PDF figures and a plain-language summary")
        self.btn_export.clicked.connect(self.export)
        head.addWidget(self.btn_export)
        lay.addLayout(head)
        sub = QLabel("Trials are averaged within each participant, then each condition is compared with the baseline. "
                     "A change is highlighted when it is larger than that person's trial-to-trial noise. n = 3: "
                     "descriptive only, no significance tests.")
        sub.setObjectName("pageHint")
        sub.setWordWrap(True)
        lay.addWidget(sub)
        row = QHBoxLayout()
        self.metric_label = QLabel("Metric")
        row.addWidget(self.metric_label)
        self.metric = QComboBox()
        for k in METRIC_CHOICES:
            self.metric.addItem(f"{INFO[k].label} ({INFO[k].unit})", k)
        row.addWidget(self.metric)
        row.addWidget(QLabel("Baseline"))
        self.baseline = QComboBox()
        row.addWidget(self.baseline)
        row.addStretch(1)
        self.btn_savefig = QPushButton("Save figure…")
        self.btn_savefig.clicked.connect(lambda: self.canvas.save_dialog(self, f"{VIEWS[self.view.index()].lower()}.png"))
        row.addWidget(self.btn_savefig)
        lay.addLayout(row)
        self.explain = QLabel("")
        self.explain.setWordWrap(True)
        self.explain.setObjectName("muted")
        lay.addWidget(self.explain)
        split = QSplitter(Qt.Orientation.Vertical)
        split.setOpaqueResize(False)
        self.canvas = MplCanvas()
        split.addWidget(self.canvas)
        self.tables = QStackedWidget()
        self.t_changes = table(["Metric", "Participant", "Condition", "Baseline", "Condition mean", "Change",
                                "% change", "Noise (±)", "Larger than noise?"])
        self.tables.addWidget(self.t_changes)
        split.addWidget(self.tables)
        split.setSizes([480, 240])
        lay.addWidget(split, 1)
        self.metric.currentIndexChanged.connect(self.update_views)
        self.baseline.currentIndexChanged.connect(self.update_views)
        state.resultsChanged.connect(self.refresh)
        state.projectChanged.connect(self.refresh)
        self.refresh()

    # ---------------------------------------------------------------------------------------
    def refresh(self):
        p = self.state.project
        cur = self.baseline.currentData()
        self.baseline.blockSignals(True)
        self.baseline.clear()
        if p:
            for c in p.conditions:
                self.baseline.addItem(f"{c.code} – {c.label}", c.code)
            i = self.baseline.findData(cur)
            self.baseline.setCurrentIndex(max(0, i))
        self.baseline.blockSignals(False)
        self.long = compare.collect(p) if p else None
        has = self.long is not None and not self.long.empty
        self.btn_export.setEnabled(has)
        self.btn_savefig.setEnabled(has)
        self.update_views()

    def _view_changed(self, i):
        uses_metric = VIEWS[i] in ("By condition", "Pole length", "Repetitions")
        self.metric.setEnabled(uses_metric)
        self.metric_label.setEnabled(uses_metric)
        self.update_views()

    def update_views(self, *_):
        m = self.metric.currentData()
        info = INFO[m]
        view = VIEWS[self.view.index()]
        if view in ("By condition", "Pole length", "Repetitions"):
            self.explain.setText(f"{info.what} Why it matters: {info.why} Cannot conclude: {info.not_conclude}")
        else:
            self.explain.setText({
                "Overview": "Every metric at once: how far each condition moved each participant from baseline.",
                "Trade-off": "Does knee unloading come with more shoulder demand? Each point is a participant's "
                             "mean in one condition.",
                "Stance curves": "Knee extensor moment over the stance phase (0 % = foot lands, 100 % = foot "
                                 "leaves), mean ± SD of all stances per condition.",
            }[view])
        p = self.state.project
        if self.long is None or self.long.empty:
            fig, ax = plots._fig()
            ax.text(0.5, 0.5, "No analysed trials yet.\nAnalyse trials, or create the demo study on the Study page.",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            self.canvas.set_figure(fig)
            self.t_changes.setRowCount(0)
            return
        base = self.baseline.currentData() or "C0"
        conds = [c.code for c in p.conditions]
        ch = compare.change_table(self.long, base, list(dict.fromkeys(compare.OVERVIEW_METRICS + [m])))
        if view == "Overview":
            fig = plots.fig_metric_overview(ch[ch.metric.isin(compare.OVERVIEW_METRICS)].dropna(subset=["pct_diff"]))
        elif view == "By condition":
            fig = plots.fig_condition_comparison(self.long, m, conds)
        elif view == "Pole length":
            fig = plots.fig_dose_response(self.long, m, {c.code: (c.pole_offset_cm if c.uses_poles else None)
                                                         for c in p.conditions})
        elif view == "Repetitions":
            fig = plots.fig_repetition(self.long, m)
        elif view == "Trade-off":
            fig = plots.fig_tradeoff(self.long)
        else:
            fig = self._curves(p)
        self.canvas.set_figure(fig)
        rows = ch[ch.metric.isin(compare.OVERVIEW_METRICS)] if view == "Overview" else ch[ch.metric == m]
        self._fill_changes(rows)

    def _fill_changes(self, ch):
        t = self.t_changes
        t.setRowCount(len(ch))
        for r, row in enumerate(ch.itertuples()):
            vals = [row.label, row.participant, row.condition, fmt(row.baseline_mean), fmt(row.condition_mean),
                    fmt(row.abs_diff), "–" if not np.isfinite(row.pct_diff) else f"{row.pct_diff:+.1f}%",
                    fmt(row.noise_95), "Yes" if row.clear else ("No" if np.isfinite(row.noise_95) else "Needs ≥2 trials")]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if c == 8 and row.clear:
                    it.setForeground(QColor("#1F6F66"))
                t.setItem(r, c, it)

    def _curves(self, p):
        results = compare.load_all_results(p)
        by = {}
        for tid, res in results.items():
            c = compare.stance_curves(res, f"{res.side}_knee_extensor_moment_nm")
            if len(c):
                mass = p.participant(p.trial(tid).participant_id).body_mass_kg
                by.setdefault(p.trial(tid).condition_code, []).append(c / mass)
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
