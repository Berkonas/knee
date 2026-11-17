"""Gait events and trekking-pole technique from detected foot and pole-tip contacts.

Everything here is derived from video contact detection (foot or pole tip stationary), so each label comes
with a confidence and can be overridden by the user. Pole *support* (how much force a pole carries) cannot
be inferred from these timings or from pole orientation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SYNC_WINDOW_S = 0.15      # two pole plants within this window count as simultaneous
TIMING_BAND_S = 0.10      # |plant - foot strike| <= this counts as "with the foot"
STEP_POLE_WINDOW_S = 0.35  # a foot strike with no pole plant within this window counts as a step without a pole


@dataclass
class Technique:
    pattern: str = "not assessed"   # alternating | simultaneous | single pole | mixed | no poles detected
    confidence: float = 0.0
    lead_leg: str = ""
    n_plants: int = 0
    simultaneous_fraction: float | None = None
    timing_class_counts: dict = field(default_factory=dict)   # early / with foot / late
    plant_timing_mean_s: float | None = None
    plant_timing_sd_s: float | None = None
    steps_without_pole_pct: float | None = None
    support_phases: dict = field(default_factory=dict)       # single / double support time (s)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _intervals(events, prefix: str) -> list[tuple[float, float]]:
    if events is None or len(events) == 0:
        return []
    ev = events[events["event"] == prefix]
    return [(float(a), float(b)) for a, b in zip(ev["start_s"], ev["end_s"])]


def foot_event_rows(contacts: dict, t0: float, t1: float) -> list[dict]:
    """Foot strike / toe-off rows. A contact that starts at the first frame (or ends at the last) was already
    under way, so it gives no strike (toe-off) event."""
    rows = []
    for side, ivs in contacts.items():
        for c in ivs:
            if c.start_s > t0 + 1e-6:
                rows.append({"event": f"{side}_foot_strike", "start_s": c.start_s, "end_s": c.start_s, "duration_s": 0.0})
            if c.end_s < t1 - 1e-6:
                rows.append({"event": f"{side}_toe_off", "start_s": c.end_s, "end_s": c.end_s, "duration_s": 0.0})
    return rows


def support_phases(t: np.ndarray, left: np.ndarray, right: np.ndarray) -> dict:
    """Time (s) in double support, single support (each side) and flight/unknown, from stance masks."""
    dt = np.median(np.diff(t)) if len(t) > 1 else 0.0
    return {"double_support_s": float((left & right).sum() * dt), "left_single_s": float((left & ~right).sum() * dt),
            "right_single_s": float((right & ~left).sum() * dt), "no_contact_s": float((~left & ~right).sum() * dt)}


def analyse_technique(events, pole_coverage: dict[str, float], uses_poles: bool) -> Technique:
    tq = Technique()
    strikes = sorted([(float(s), e.split("_")[0]) for e, s in zip(events["event"], events["start_s"])
                      if e.endswith("_foot_strike")]) if len(events) else []
    if strikes:
        tq.lead_leg = strikes[0][1]
    plants = sorted([(a, side) for side in ("left", "right") for a, _ in _intervals(events, f"pole_{side}_contact")])
    tq.n_plants = len(plants)
    cov = [v for v in pole_coverage.values() if v is not None]
    if not uses_poles:
        tq.pattern = "no poles (condition)"
        return tq
    if not plants:
        tq.pattern = "no pole plants detected"
        tq.notes.append("No stationary pole tip was found; technique cannot be assessed from this video.")
        return tq
    sides = {s for _, s in plants}
    simult = 0
    for i, (a, s) in enumerate(plants):
        if any(b != s and abs(x - a) <= SYNC_WINDOW_S for j, (x, b) in enumerate(plants) if j != i):
            simult += 1
    tq.simultaneous_fraction = 100.0 * simult / len(plants)
    if len(sides) == 1:
        tq.pattern = "single pole"
    elif tq.simultaneous_fraction >= 70:
        tq.pattern = "simultaneous (double-pole) planting"
    elif tq.simultaneous_fraction <= 30:
        tq.pattern = "alternating planting"
    else:
        tq.pattern = "mixed"
    st = np.array([s for s, _ in strikes])
    if len(st):
        d = np.array([a - st[np.argmin(np.abs(st - a))] for a, _ in plants])
        tq.plant_timing_mean_s = float(d.mean())
        tq.plant_timing_sd_s = float(d.std(ddof=1)) if len(d) > 1 else None
        tq.timing_class_counts = {"early (before foot)": int((d < -TIMING_BAND_S).sum()),
                                  "with foot strike": int((np.abs(d) <= TIMING_BAND_S).sum()),
                                  "late (after foot)": int((d > TIMING_BAND_S).sum())}
        pa = np.array([a for a, _ in plants])
        missed = sum(1 for s in st if not (np.abs(pa - s) <= STEP_POLE_WINDOW_S).any())
        tq.steps_without_pole_pct = 100.0 * missed / len(st)
    # confidence: enough plants and good pole tracking in both hands
    tq.confidence = float(min(1.0, len(plants) / 6) * (np.mean(cov) if cov else 0.0))
    if len(sides) == 1 and len(pole_coverage) == 2 and min(pole_coverage.values()) < 0.3:
        tq.notes.append("One pole is poorly tracked (often hidden behind the body in a side view): "
                        "'single pole' may really be two poles.")
    tq.notes.append("Pole dragging cannot be told apart from planting in 2D video and is not assessed.")
    return tq
