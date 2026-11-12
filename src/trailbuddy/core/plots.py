"""Publication-style figures (matplotlib). Each function returns a Figure; nothing is shown."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .metrics import INFO

# Okabe-Ito colour-blind-safe palette.
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]
COND_COLORS = {"C0": "#4D4D4D", "C1": "#0072B2", "C2": "#009E73", "C3": "#D55E00"}

STYLE = {
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25,
    "grid.linewidth": 0.6, "lines.linewidth": 1.6, "figure.dpi": 100, "savefig.dpi": 300,
    "font.family": "sans-serif", "svg.fonttype": "none", "pdf.fonttype": 42,
}


def cond_color(code: str, i: int = 0) -> str:
    return COND_COLORS.get(code, PALETTE[i % len(PALETTE)])


def _fig(w=6.5, h=3.2, nrows=1, ncols=1, **kw):
    import matplotlib

    matplotlib.rcParams.update(STYLE)
    fig = Figure(figsize=(w, h), layout="constrained")
    axs = fig.subplots(nrows, ncols, **kw)
    return fig, axs


def _shade_stance(ax, ts: pd.DataFrame, side: str):
    col = f"{side}_stance"
    if col not in ts:
        return
    t = ts["time_s"].to_numpy()
    m = ts[col].to_numpy().astype(bool)
    edges = np.flatnonzero(np.diff(np.concatenate(([0], m.astype(int), [0]))))
    for a, b in zip(edges[::2], edges[1::2]):
        ax.axvspan(t[a], t[b - 1], color="#0072B2", alpha=0.07, lw=0)


def fig_kinematics(res, title: str = "") -> Figure:
    """Knee, hip, ankle (top) and trunk, shoulder, elbow (bottom) vs time; stance shaded."""
    ts, s = res.timeseries, res.side
    fig, (a1, a2) = _fig(6.5, 4.6, 2, 1, sharex=True)
    for col, lab, c in [(f"{s}_knee_flexion_deg", "Knee flexion", PALETTE[0]),
                        (f"{s}_hip_flexion_deg", "Hip flexion", PALETTE[1]),
                        (f"{s}_ankle_dorsiflexion_deg", "Ankle dorsiflexion", PALETTE[2])]:
        a1.plot(ts.time_s, ts[col], color=c, label=lab)
    for col, lab, c in [("trunk_lean_deg", "Trunk forward lean", PALETTE[3]),
                        (f"{s}_shoulder_flexion_deg", "Shoulder flexion", PALETTE[4]),
                        (f"{s}_elbow_flexion_deg", "Elbow flexion", PALETTE[5])]:
        a2.plot(ts.time_s, ts[col], color=c, label=lab)
    for ax in (a1, a2):
        _shade_stance(ax, ts, s)
        ax.set_ylabel("Angle (deg, 2D)")
        ax.legend(loc="upper right", ncols=3, frameon=False)
    a2.set_xlabel("Time (s)")
    a1.set_title(title or f"Joint angles, {s} side (2D video estimate; shaded = stance)")
    return fig


def fig_knee_load(res, title: str = "") -> Figure:
    ts, s = res.timeseries, res.side
    fig, (a1, a2) = _fig(6.5, 4.6, 2, 1, sharex=True)
    a1.plot(ts.time_s, ts[f"{s}_knee_flexion_deg"], color=PALETTE[0])
    a1.set_ylabel("Knee flexion (deg)")
    col = f"{s}_knee_extensor_moment_nm"
    if col in ts:
        a2.plot(ts.time_s, ts[col], color=PALETTE[1], label="Knee extensor moment (N·m)")
        q = ts.get(f"{s}_quad_force_n")
        if q is not None:
            ax2 = a2.twinx()
            ax2.plot(ts.time_s, q, color=PALETTE[2], ls="--", label="Quadriceps force (N)")
            ax2.set_ylabel("Quadriceps force (N)", color=PALETTE[2])
            ax2.spines["right"].set_visible(True)
            ax2.grid(False)
        a2.set_ylabel("Moment (N·m)")
        mv = res.metric("knee_ext_moment_peak")
        kind = mv.kind if mv else ""
        a2.set_title(f"Knee extensor demand [{kind}]", loc="left")
    else:
        a2.text(0.5, 0.5, "Knee moment unavailable (needs scale and foot contacts)",
                ha="center", va="center", transform=a2.transAxes)
    for ax in (a1, a2):
        _shade_stance(ax, ts, s)
    a2.set_xlabel("Time (s)")
    a1.set_title(title or f"Knee angle and estimated load, {s} leg")
    return fig


def fig_events(res, title: str = "") -> Figure:
    ev = res.events
    fig, ax = _fig(6.5, 2.2)
    rows = sorted(ev.event.unique()) if len(ev) else []
    for i, e in enumerate(rows):
        for r in ev[ev.event == e].itertuples():
            ax.broken_barh([(r.start_s, r.duration_s)], (i - 0.35, 0.7),
                           color=PALETTE[0] if "foot" in e else PALETTE[1])
    ax.set_yticks(range(len(rows)), [r.replace("_", " ") for r in rows])
    ax.set_xlabel("Time (s)")
    ax.set_title(title or "Detected contacts (estimates; verify against video)")
    if not rows:
        ax.text(0.5, 0.5, "No contacts detected", ha="center", va="center", transform=ax.transAxes)
    return fig


def fig_stance_normalised(curves_by_cond: dict[str, np.ndarray], ylabel: str, title: str) -> Figure:
    fig, ax = _fig(5.0, 3.2)
    x = np.linspace(0, 100, 101)
    for i, (code, c) in enumerate(curves_by_cond.items()):
        if len(c) == 0:
            continue
        m, sd = np.nanmean(c, axis=0), np.nanstd(c, axis=0)
        col = cond_color(code, i)
        ax.plot(x, m, color=col, label=f"{code} (n={len(c)} stances)")
        ax.fill_between(x, m - sd, m + sd, color=col, alpha=0.15, lw=0)
    ax.set_xlabel("Stance (%)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(frameon=False)
    return fig


def fig_condition_comparison(long: pd.DataFrame, metric: str, conditions: list[str]) -> Figure:
    """Trials (small dots) and participant means (large markers, joined across conditions)."""
    info = INFO.get(metric)
    d = long[(long.metric == metric)].dropna(subset=["value"])
    fig, ax = _fig(5.0, 3.4)
    markers = ["o", "s", "^", "D", "v", "P"]
    xs = {c: i for i, c in enumerate(conditions)}
    for j, (pid, g) in enumerate(d.groupby("participant")):
        means = []
        for c in conditions:
            v = g[g.condition == c]["value"].to_numpy()
            if len(v):
                ax.scatter(np.full(len(v), xs[c]) + 0.12 * (j - 1), v, s=12, color="#999999", zorder=2)
                means.append((xs[c] + 0.12 * (j - 1), v.mean()))
        if means:
            mx, my = zip(*means)
            ax.plot(mx, my, marker=markers[j % len(markers)], color=PALETTE[j % len(PALETTE)], label=pid,
                    ms=7, zorder=3)
    ax.set_xticks(range(len(conditions)), conditions)
    unit = info.unit if info else ""
    ax.set_ylabel(f"{info.label if info else metric} ({unit})")
    ax.set_title("Participant means (markers) and individual trials (grey)")
    if len(d):
        ax.legend(frameon=False, title="Participant")
    else:
        ax.text(0.5, 0.5, "No values for this metric yet", ha="center", va="center", transform=ax.transAxes)
    return fig


def fig_paired_change(within: pd.DataFrame, metric: str) -> Figure:
    info = INFO.get(metric)
    fig, ax = _fig(5.0, 3.0)
    if within.empty:
        ax.text(0.5, 0.5, "Needs baseline and comparison trials", ha="center", va="center", transform=ax.transAxes)
        return fig
    conds = sorted(within.condition.unique())
    for j, (pid, g) in enumerate(within.groupby("participant")):
        x = [conds.index(c) for c in g.condition]
        ax.scatter(np.array(x) + 0.1 * (j - 1), g.pct_diff, color=PALETTE[j % len(PALETTE)], label=pid, s=40, zorder=3)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(range(len(conds)), [f"{c} vs {within.baseline.iloc[0]}" for c in conds])
    ax.set_ylabel("Change vs baseline (%)")
    ax.set_title(f"{info.label if info else metric}: within-participant change")
    ax.legend(frameon=False)
    return fig


def fig_tradeoff(long: pd.DataFrame, knee_metric: str = "quad_force_peak",
                 arm_metric: str = "shoulder_moment_peak") -> Figure:
    """Knee demand vs arm demand, participant x condition means."""
    fig, ax = _fig(5.0, 3.6)
    k = long[long.metric == knee_metric].groupby(["participant", "condition"])["value"].mean()
    a = long[long.metric == arm_metric].groupby(["participant", "condition"])["value"].mean()
    j = pd.concat([k.rename("knee"), a.rename("arm")], axis=1).reset_index()
    j["arm"] = j["arm"].fillna(0.0)  # no poles -> no pole-induced arm moment
    j = j.dropna(subset=["knee"])
    for i, (code, g) in enumerate(j.groupby("condition")):
        ax.scatter(g.arm, g.knee, color=cond_color(code, i), label=code, s=40)
        for r in g.itertuples():
            ax.annotate(r.participant, (r.arm, r.knee), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ki, ai = INFO[knee_metric], INFO[arm_metric]
    ax.set_xlabel(f"{ai.label} ({ai.unit})")
    ax.set_ylabel(f"{ki.label} ({ki.unit})")
    ax.set_title("Trade-off: knee unloading vs upper-limb demand")
    if len(j):
        ax.legend(frameon=False, title="Condition")
    return fig


def fig_sensitivity(res) -> Figure:
    fig, ax = _fig(5.0, 3.0)
    s = res.sensitivity
    if s is None or len(s) == 0:
        ax.text(0.5, 0.5, "Sensitivity analysis applies to the scenario model only",
                ha="center", va="center", transform=ax.transAxes)
        return fig
    for i, (supp, g) in enumerate(s.groupby("support_model")):
        for k, (r, gg) in enumerate(g.groupby("moment_arm_m")):
            ax.plot(gg.cop_fraction, gg.peak_quad_force_n, marker="o", color=PALETTE[i * 3 + k],
                    label=f"{supp}, r = {100 * r:.0f} cm")
    ax.set_xlabel("Assumed COP position (0 = heel, 1 = toe)")
    ax.set_ylabel("Peak quadriceps force (N)")
    ax.set_title("Sensitivity of the quadriceps force estimate to assumptions")
    ax.legend(frameon=False, fontsize=7)
    return fig


def save(fig: Figure, path_stem, formats=("png", "svg", "pdf")) -> list:
    from pathlib import Path

    out = []
    for f in formats:
        p = Path(f"{path_stem}.{f}")
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p)
        out.append(p)
    return out
