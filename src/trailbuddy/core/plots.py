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


# =============================================================================================
# Second-generation figures: timeline, stick strip, multi-metric comparisons
# =============================================================================================

def _intervals(mask: np.ndarray, t: np.ndarray):
    m = np.asarray(mask).astype(bool)
    edges = np.flatnonzero(np.diff(np.concatenate(([0], m.astype(int), [0]))))
    return [(t[a], t[b - 1]) for a, b in zip(edges[::2], edges[1::2])]


def fig_timeline(res, title: str = "", playhead: float | None = None) -> Figure:
    """Movement timeline on one time axis: joint angles, contacts, knee load, cumulative demand."""
    ts, s = res.timeseries, res.side
    t = ts["time_s"].to_numpy()
    has_load = f"{s}_knee_extensor_moment_nm" in ts
    rows = 4 if has_load else 2
    ratios = [3, 1.1, 2.4, 1.8][:rows] if has_load else [3, 1.1]
    fig, axs = _fig(7.2, 1.55 * sum(ratios), rows, 1, sharex=True, gridspec_kw={"height_ratios": ratios})
    a1, a2 = axs[0], axs[1]
    for col, lab, c in [(f"{s}_knee_flexion_deg", "Knee flexion", PALETTE[0]),
                        (f"{s}_hip_flexion_deg", "Hip flexion", PALETTE[1]),
                        (f"{s}_ankle_dorsiflexion_deg", "Ankle dorsiflexion", PALETTE[2]),
                        ("trunk_lean_deg", "Trunk lean", PALETTE[3])]:
        if col in ts:
            a1.plot(t, ts[col], color=c, label=lab, lw=1.8 if "knee" in col else 1.2)
    a1.set_ylabel("Angle (deg, 2D)")
    a1.legend(loc="upper left", ncols=4, frameon=False, fontsize=7.5)
    # contact lanes
    lanes = [(f"{s}_stance", f"{s.capitalize()} foot", "#4D4D4D")]
    other = "left" if s == "right" else "right"
    if f"{other}_stance" in ts:
        lanes.append((f"{other}_stance", f"{other.capitalize()} foot", "#9A9A9A"))
    for p_ in ("left", "right"):
        if f"pole_{p_}_contact" in ts:
            lanes.append((f"pole_{p_}_contact", f"{p_.capitalize()} pole", "#D55E00"))
    for i, (col, _lab, c) in enumerate(lanes):
        for a, b in _intervals(ts[col].to_numpy(), t):
            a2.broken_barh([(a, max(b - a, 1e-3))], (i - 0.32, 0.64), color=c)
    a2.set_yticks(range(len(lanes)), [lab for _, lab, _ in lanes])
    a2.set_ylim(-0.6, len(lanes) - 0.4)
    a2.invert_yaxis()
    a2.grid(False)
    a2.set_title("Ground contacts (bars = in contact)", loc="left", fontsize=8.5)
    for ax in axs[:1]:
        _shade_stance(ax, ts, s)
    if has_load:
        a3, a4 = axs[2], axs[3]
        bw_scale = None
        m = ts[f"{s}_knee_extensor_moment_nm"]
        a3.plot(t, m, color=PALETTE[1], label="Knee extensor moment")
        a3.axhline(0, color="k", lw=0.6)
        a3.set_ylabel("N·m")
        q = res.metric("quad_force_peak")
        kind = res.metric("knee_ext_moment_peak").kind if res.metric("knee_ext_moment_peak") else ""
        a3.set_title(f"Knee extensor moment [{kind}]", loc="left", fontsize=8.5)
        _shade_stance(a3, ts, s)
        cum = ts.get(f"{s}_knee_ext_impulse_cum_nms_per_kg")
        if cum is not None:
            a4.plot(t, cum, color=PALETTE[0])
            a4.fill_between(t, 0, cum, color=PALETTE[0], alpha=0.12)
            a4.set_ylabel("N·m·s/kg")
            a4.set_title("Cumulative knee extensor demand (mechanical, not fatigue)", loc="left", fontsize=8.5)
        del bw_scale, q
    axs[-1].set_xlabel("Time (s)")
    if playhead is not None:
        for ax in axs:
            ax.axvline(playhead, color="#B3261E", lw=1)
    fig.suptitle(title or f"Movement timeline, {s} side", fontsize=10, x=0.01, ha="left")
    return fig


def fig_stick_strip(res, n_frames: int = 7, title: str = "") -> Figure:
    """Sagittal stick figures (trunk, analysed leg and arm) through the clearest stance, plus knee angle."""
    ts, s = res.timeseries, res.side
    unit = "m" if f"{s}_knee_x_m" in ts else "px"
    need = [f"{s}_{n}_x_{unit}" for n in ("hip", "knee", "ankle", "heel", "foot_index", "shoulder", "elbow", "wrist")]
    fig, ax = _fig(7.2, 2.8)
    if not all(c in ts for c in need):
        ax.text(0.5, 0.5, "Segment trajectories not available (re-run the analysis)", ha="center",
                va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return fig
    t = ts["time_s"].to_numpy()
    st = _intervals(ts[f"{s}_stance"].to_numpy(), t)
    full = [iv for iv in st if iv[0] > t[0] and iv[1] < t[-1]] or st
    a, b = max(full, key=lambda iv: iv[1] - iv[0]) if full else (t[0], t[-1])
    idxs = [int(np.argmin(np.abs(t - x))) for x in np.linspace(a, b, n_frames)]
    P = lambda nm, i: (ts[f"{s}_{nm}_x_{unit}"].iloc[i], ts[f"{s}_{nm}_y_{unit}"].iloc[i])  # noqa: E731
    span = (ts[f"{s}_hip_y_{unit}"] - ts[f"{s}_ankle_y_{unit}"]).abs().median()
    gap = 0.9 * float(span) if np.isfinite(span) and span > 0 else 1.0
    import matplotlib.cm as cm
    cmap = cm.get_cmap("viridis") if hasattr(cm, "get_cmap") else __import__("matplotlib").colormaps["viridis"]
    for k, i in enumerate(idxs):
        x0 = P("hip", i)[0]
        def X(nm):
            x, y = P(nm, i)
            return x - x0 + k * gap, y
        c = cmap(k / max(1, n_frames - 1))
        chains = [("shoulder", "hip"), ("hip", "knee"), ("knee", "ankle"), ("ankle", "heel"),
                  ("heel", "foot_index"), ("ankle", "foot_index"), ("shoulder", "elbow"), ("elbow", "wrist")]
        for u, v in chains:
            (x1, y1), (x2, y2) = X(u), X(v)
            ax.plot([x1, x2], [y1, y2], color=c, lw=2.4 if u in ("hip", "knee") else 1.4, solid_capstyle="round")
        kx, ky = X("knee")
        kfv = ts[f"{s}_knee_flexion_deg"].iloc[i]
        ax.annotate(f"{kfv:.0f}°", (kx, ky), xytext=(6, 0), textcoords="offset points", fontsize=7, color=c)
        ax.text(X("hip")[0], ax.get_ylim()[0], f"{100 * (t[i] - a) / max(b - a, 1e-9):.0f}%", fontsize=7,
                ha="center", va="bottom", color="#5E6E6B")
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xticks([])
    ax.set_ylabel(f"Height ({unit})")
    ax.grid(False)
    ax.set_title(title or f"Leg configuration through stance ({s} leg, % of stance; knee flexion labelled)")
    return fig


CAP = 50.0  # % change shown on the overview axis; larger values are drawn as arrows at the edge


def fig_metric_overview(changes: pd.DataFrame, title: str = "") -> Figure:
    """Forest-style overview: % change vs baseline for many metrics; dots = participants, bar = mean.

    changes: rows with columns metric, label, condition, participant, pct_diff, clear (bool).
    """
    conds = sorted(changes.condition.unique()) if len(changes) else []
    metrics = list(dict.fromkeys(changes.label)) if len(changes) else []
    fig, axs = _fig(3.0 + 2.6 * max(1, len(conds)), 0.34 * max(4, len(metrics)) + 1.3, 1, max(1, len(conds)),
                    sharey=True, squeeze=False)
    axs = axs[0]
    if not len(changes):
        axs[0].text(0.5, 0.5, "Needs a baseline condition and at least one comparison condition",
                    ha="center", va="center", transform=axs[0].transAxes)
        axs[0].set_axis_off()
        return fig
    y = {m: i for i, m in enumerate(metrics)}
    for ax, c in zip(axs, conds):
        d = changes[changes.condition == c]
        for lab, g in d.groupby("label"):
            yy = y[lab]
            mean = g.pct_diff.mean()
            ax.plot([0, mean], [yy, yy], color=cond_color(c), lw=5, alpha=0.35, solid_capstyle="butt")
            for r in g.itertuples():
                x = float(np.clip(r.pct_diff, -CAP, CAP))
                ax.scatter(x, yy, s=28, zorder=3, edgecolor="white", lw=0.6,
                           marker="o" if abs(r.pct_diff) <= CAP else (">" if r.pct_diff > 0 else "<"),
                           color=cond_color(c) if r.clear else "#B5B5B5")
        ax.axvline(0, color="k", lw=0.8)
        ax.set_title(f"{c} vs baseline", fontsize=9)
        ax.set_xlabel("Change from baseline (%)")
        lim = min(CAP, np.nanmax(np.abs(d.pct_diff))) if len(d) else 10
        ax.set_xlim(-1.15 * max(lim, 5), 1.15 * max(lim, 5))
    axs[0].set_yticks(range(len(metrics)), metrics)
    axs[0].invert_yaxis()
    fig.suptitle(title or "Change from baseline, every metric. Dot = participant (coloured: larger than their "
                 "trial-to-trial noise; grey: within noise). Bar = mean.", fontsize=8.5, x=0.01, ha="left")
    return fig


def fig_dose_response(long: pd.DataFrame, metric: str, offsets: dict[str, float | None]) -> Figure:
    """Metric vs pole length offset (no poles shown separately), one line per participant."""
    info = INFO.get(metric)
    fig, ax = _fig(5.0, 3.3)
    d = long[(long.metric == metric)].dropna(subset=["value"])
    if d.empty:
        ax.text(0.5, 0.5, "No values yet", ha="center", va="center", transform=ax.transAxes)
        return fig
    x_none = min([v for v in offsets.values() if v is not None], default=0) - 7.5
    for j, (pid, g) in enumerate(d.groupby("participant")):
        pts = []
        for code, gg in g.groupby("condition"):
            off = offsets.get(code)
            x = x_none if off is None else off
            ax.scatter(np.full(len(gg), x) + 0.25 * (j - 1), gg.value, s=10, color="#B5B5B5", zorder=2)
            pts.append((x, gg.value.mean()))
        pts.sort()
        poles = [(x, v) for x, v in pts if x != x_none]
        nop = [(x, v) for x, v in pts if x == x_none]
        col = PALETTE[j % len(PALETTE)]
        if poles:
            ax.plot(*zip(*poles), marker="o", color=col, label=pid)
        if nop:
            ax.plot(*zip(*nop), marker="s", color=col, ls="none")
    ticks = sorted({x_none} | {v for v in offsets.values() if v is not None})
    ax.set_xticks(ticks, ["no poles" if x == x_none else f"{x:+g} cm" for x in ticks])
    ax.axvline(x_none + 3.75, color="#C9D3D1", lw=1)
    ax.set_xlabel("Pole length relative to standard")
    ax.set_ylabel(f"{info.label} ({info.unit})" if info else metric)
    ax.set_title("Pole-length response (participant means; grey = trials)")
    ax.legend(frameon=False)
    return fig


def fig_repetition(long: pd.DataFrame, metric: str) -> Figure:
    """Metric across repetitions (trial 1 -> 3) within each participant x condition: within-session drift."""
    info = INFO.get(metric)
    fig, ax = _fig(5.0, 3.2)
    d = long[(long.metric == metric)].dropna(subset=["value"])
    if d.empty:
        ax.text(0.5, 0.5, "No values yet", ha="center", va="center", transform=ax.transAxes)
        return fig
    styles = ["-", "--", ":", "-."]
    for j, (pid, g) in enumerate(d.groupby("participant")):
        for i, (code, gg) in enumerate(g.groupby("condition")):
            gg = gg.sort_values("trial")
            ax.plot(gg.trial, gg.value, marker="o", color=cond_color(code, i), ls=styles[j % 4],
                    label=f"{pid} {code}", ms=4)
    ax.set_xlabel("Repetition (trial number)")
    ax.set_ylabel(f"{info.label} ({info.unit})" if info else metric)
    ax.set_xticks(sorted(d.trial.unique()))
    ax.set_title("Change across repetitions (drift can reflect fatigue, learning or pacing)")
    ax.legend(frameon=False, ncols=2, fontsize=7)
    return fig
