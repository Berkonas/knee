"""Project-level exports: CSV, Excel workbook, figures and a plain-language summary."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import compare, plots
from .metrics import INFO

KEY_METRICS = ["quad_force_peak", "knee_ext_moment_peak", "knee_flexion_peak", "knee_ext_impulse_total",
               "knee_neg_work", "shoulder_moment_peak", "elbow_moment_peak", "shoulder_flexion_peak",
               "trunk_lean_mean", "speed", "cadence"]

LIMITATIONS = [
    "Pilot study with n = 3 team members; results describe these participants under these conditions only.",
    "Joint angles are 2D projections from video; out-of-plane motion and camera angle introduce error.",
    "Without a force plate, knee moments come from a quasi-static scenario model with assumed foot force "
    "and centre of pressure; dynamic (impact) force peaks are not captured.",
    "Quadriceps force = net knee moment / assumed patellar tendon moment arm; co-contraction is ignored.",
    "Pole force cannot be measured from ordinary video; arm moments use measured or assumed pole force.",
    "Mechanical-demand metrics (angular impulse, negative work) are not measures of fatigue, pain or injury risk.",
    "Stairs in a lab are not an uneven trail; no backpack load was tested.",
]


def export_project(project, out_dir: str | Path, baseline: str = "C0",
                   fig_formats=("png", "svg", "pdf")) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    long = compare.collect(project)
    if long.empty:
        raise ValueError("No analysed trials to export yet.")
    files: dict[str, Path] = {}
    files["long_csv"] = out / "all_metrics_long.csv"
    long.to_csv(files["long_csv"], index=False, float_format="%.6g")
    wide = long.pivot_table(index=["trial_id", "participant", "condition", "trial"], columns="metric",
                            values="value").reset_index()
    files["wide_csv"] = out / "trials_by_metric.csv"
    wide.to_csv(files["wide_csv"], index=False, float_format="%.6g")

    within = pd.concat([compare.within_participant(long, m, baseline).assign(metric=m) for m in KEY_METRICS],
                       ignore_index=True)
    group = pd.concat([compare.group_summary(long, m, baseline) for m in KEY_METRICS], ignore_index=True)
    pp = pd.concat([compare.per_participant(long, m).assign(metric=m) for m in KEY_METRICS], ignore_index=True)
    files["within_csv"] = out / "within_participant_changes.csv"
    within.to_csv(files["within_csv"], index=False, float_format="%.6g")

    meta = pd.DataFrame([{**{"trial_id": t.id, "participant": t.participant_id, "condition": t.condition_code,
                             "trial": t.trial_number, "pole_length_cm": t.pole_length_cm,
                             "camera_config": t.camera_config, "notes": t.notes, "status": t.status},
                          **{f"stair_{k}": v for k, v in t.stair.items()}} for t in project.trials])
    parts = pd.DataFrame([{"participant": p.id, "body_mass_kg": p.body_mass_kg, "height_m": p.height_m,
                           "leg_length_m": p.leg_length_m, "standard_pole_length_cm": p.standard_pole_length_cm}
                          for p in project.participants])
    defs = pd.DataFrame([{"metric": k, "label": i.label, "unit": i.unit, "what": i.what, "why": i.why,
                          "can_conclude": i.conclude, "cannot_conclude": i.not_conclude} for k, i in INFO.items()])
    files["xlsx"] = out / "trailbuddy_results.xlsx"
    with pd.ExcelWriter(files["xlsx"], engine="openpyxl") as xw:
        wide.to_excel(xw, sheet_name="Trials x metrics", index=False)
        pp.to_excel(xw, sheet_name="Participant means", index=False)
        within.to_excel(xw, sheet_name="Within-participant", index=False)
        group.to_excel(xw, sheet_name="Group (descriptive)", index=False)
        meta.to_excel(xw, sheet_name="Trial log", index=False)
        parts.to_excel(xw, sheet_name="Participants", index=False)
        defs.to_excel(xw, sheet_name="Metric definitions", index=False)
        long.to_excel(xw, sheet_name="All values (long)", index=False)

    figdir = out / "figures"
    conds = [c.code for c in project.conditions]
    for m in ("quad_force_peak", "knee_ext_moment_peak", "knee_flexion_peak", "knee_ext_impulse_total",
              "shoulder_moment_peak", "elbow_moment_peak", "shoulder_flexion_peak"):
        if (long.metric == m).any() and long[long.metric == m].value.notna().any():
            plots.save(plots.fig_condition_comparison(long, m, conds), figdir / f"conditions_{m}", fig_formats)
            w = compare.within_participant(long, m, baseline)
            if not w.empty:
                plots.save(plots.fig_paired_change(w, m), figdir / f"paired_change_{m}", fig_formats)
    plots.save(plots.fig_tradeoff(long), figdir / "tradeoff_knee_vs_shoulder", fig_formats)

    # Stance-normalised knee curves by condition
    results = compare.load_all_results(project)
    for col_suffix, ylabel, name in [("knee_flexion_deg", "Knee flexion (deg)", "knee_angle"),
                                     ("knee_extensor_moment_nm", "Knee extensor moment (N·m)", "knee_moment")]:
        by = {}
        for tid, res in results.items():
            code = project.trial(tid).condition_code
            c = compare.stance_curves(res, f"{res.side}_{col_suffix}")
            if len(c):
                by.setdefault(code, []).append(c)
        if by:
            by = {k: np.vstack(v) for k, v in sorted(by.items())}
            plots.save(plots.fig_stance_normalised(by, ylabel, f"{ylabel.split(' (')[0]} over stance, by condition"),
                       figdir / f"stance_normalised_{name}", fig_formats)

    files["summary_md"] = out / "analysis_summary.md"
    files["summary_md"].write_text(summary_markdown(project, long, group, baseline))
    return files


def summary_markdown(project, long: pd.DataFrame, group: pd.DataFrame, baseline: str) -> str:
    n_tr = long.trial_id.nunique()
    lines = [f"# {project.name}: analysis summary", "",
             f"Analysed trials: {n_tr} of {len(project.trials)} logged ({project.planned_trials()} planned). "
             f"Participants: {', '.join(p.id for p in project.participants)}. Baseline condition: {baseline}.", "",
             "Evidence labels: *Measured*, *Video estimate (2D)*, *Model estimate*, *Scenario (assumed force)*, "
             "*Unavailable*. Group values are descriptive (no significance testing with n = 3).", ""]
    for m in KEY_METRICS:
        info = INFO[m]
        g = group[group.metric == m] if not group.empty else group
        lines += [f"## {info.label} ({info.unit})", "",
                  f"- **What we measured:** {info.what}",
                  f"- **Why it matters:** {info.why}",
                  f"- **What we can conclude:** {info.conclude}",
                  f"- **What we cannot conclude:** {info.not_conclude}"]
        ev = long[long.metric == m].evidence.dropna().unique()
        if len(ev):
            lines.append(f"- **Evidence type:** {', '.join(ev)}")
        if g is not None and len(g):
            for r in g.itertuples():
                lines.append(f"- **{r.condition} vs {baseline}:** mean change {r.mean_pct_diff:+.1f}% "
                             f"(range {r.min_pct_diff:+.1f}% to {r.max_pct_diff:+.1f}%), lower in "
                             f"{r.n_reduced} of {r.n_participants} participants.")
        else:
            lines.append("- No within-participant comparison available yet.")
        lines.append("")
    lines += ["## Limitations", ""] + [f"- {x}" for x in LIMITATIONS] + [""]
    return "\n".join(lines)
