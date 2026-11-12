"""Within-participant comparisons and descriptive group summaries.

Design rules (pilot study, n = 3):
  * Repeated trials are averaged WITHIN each participant first; participants are the unit.
  * Differences are reported per participant (absolute and percent vs. the baseline condition).
  * Group values are descriptive (mean of participant means, min-max). No p-values.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import TrialResult, load_result
from .events import normalize_cycle


def collect(project) -> pd.DataFrame:
    """Long table: one row per analysed trial x metric."""
    rows = []
    for tr in project.trials:
        d = project.root / "trials" / tr.id
        if not (d / "summary.csv").exists():
            continue
        s = pd.read_csv(d / "summary.csv")
        cond = project.condition(tr.condition_code)
        for _, r in s.iterrows():
            rows.append({"trial_id": tr.id, "participant": tr.participant_id, "condition": tr.condition_code,
                         "condition_label": cond.label, "trial": tr.trial_number,
                         "pole_length_cm": tr.pole_length_cm, "metric": r["key"], "label": r["label"],
                         "unit": r["unit"], "evidence": r["evidence"], "value": r["value"]})
    return pd.DataFrame(rows, columns=["trial_id", "participant", "condition", "condition_label", "trial",
                                       "pole_length_cm", "metric", "label", "unit", "evidence", "value"])


def per_participant(long: pd.DataFrame, metric: str) -> pd.DataFrame:
    d = long[(long.metric == metric)].dropna(subset=["value"])
    if d.empty:
        return pd.DataFrame(columns=["participant", "condition", "mean", "sd", "n", "cv_pct"])
    g = d.groupby(["participant", "condition"])["value"]
    out = g.agg(["mean", "std", "count"]).reset_index().rename(columns={"std": "sd", "count": "n"})
    out["cv_pct"] = 100 * out["sd"] / out["mean"].abs()
    return out


def within_participant(long: pd.DataFrame, metric: str, baseline: str = "C0") -> pd.DataFrame:
    """Per participant: each condition vs the baseline condition."""
    pp = per_participant(long, metric)
    rows = []
    for pid, g in pp.groupby("participant"):
        base = g[g.condition == baseline]
        if base.empty:
            continue
        b = float(base["mean"].iloc[0])
        for _, r in g.iterrows():
            if r.condition == baseline:
                continue
            diff = r["mean"] - b
            rows.append({"participant": pid, "condition": r.condition, "baseline": baseline,
                         "baseline_mean": b, "condition_mean": r["mean"], "abs_diff": diff,
                         "pct_diff": 100 * diff / abs(b) if b != 0 else np.nan,
                         "n_baseline": int(base["n"].iloc[0]), "n_condition": int(r["n"]),
                         "sd_condition": r["sd"]})
    return pd.DataFrame(rows)


def group_summary(long: pd.DataFrame, metric: str, baseline: str = "C0") -> pd.DataFrame:
    w = within_participant(long, metric, baseline)
    if w.empty:
        return pd.DataFrame()
    g = w.groupby("condition")
    out = pd.DataFrame({
        "n_participants": g.size(),
        "mean_pct_diff": g["pct_diff"].mean(),
        "min_pct_diff": g["pct_diff"].min(),
        "max_pct_diff": g["pct_diff"].max(),
        "n_reduced": g["abs_diff"].apply(lambda x: int((x < 0).sum())),
    }).reset_index()
    out["metric"] = metric
    out["note"] = "Descriptive only (pilot, n=3). No significance testing."
    return out


def stance_curves(res: TrialResult, column: str, n: int = 101) -> np.ndarray:
    """Stance-normalised (0-100 %) curves of ``column`` for each complete stance of the analysed foot."""
    ev = res.events
    side = res.side
    ts = res.timeseries
    if column not in ts:
        return np.empty((0, n))
    t = ts["time_s"].to_numpy()
    y = ts[column].to_numpy(float)
    stances = ev[(ev.event == f"{side}_foot_contact") & (ev.start_s > t[0] + 1e-6) & (ev.end_s < t[-1] - 1e-6)]
    curves = [normalize_cycle(t, y, r.start_s, r.end_s, n) for r in stances.itertuples()]
    return np.array(curves) if curves else np.empty((0, n))


def load_all_results(project) -> dict[str, TrialResult]:
    out = {}
    for tr in project.trials:
        d = Path(project.root) / "trials" / tr.id
        if (d / "analysis.json").exists():
            try:
                out[tr.id] = load_result(d)
            except Exception:  # corrupted output: skip, the UI reports status
                continue
    return out
