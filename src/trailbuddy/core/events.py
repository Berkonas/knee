"""Gait and pole contact events from kinematics (velocity-threshold method).

A foot (or pole tip) is considered in contact while its speed stays below a threshold for at
least ``min_duration`` seconds. On stairs the foot is stationary on each tread while loaded, so
this works for level walking and descent alike (cf. the foot-velocity algorithm of O'Connor et
al., 2007, and coordinate-based methods of Zeni et al., 2008). Events are *estimates* and should be
spot-checked against the video.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .signal import derivative


@dataclass
class ContactInterval:
    start_s: float
    end_s: float
    start_i: int
    end_i: int

    @property
    def duration(self) -> float:
        return self.end_s - self.start_s


def contact_intervals(t: np.ndarray, pos: np.ndarray, rel_threshold: float = 0.15,
                      abs_threshold: float | None = None, min_duration: float = 0.08) -> list[ContactInterval]:
    """Detect stationary intervals of a 2D point trajectory.

    Threshold = abs_threshold if given (units/s), otherwise rel_threshold * 95th-percentile speed.
    Intervals touching the clip edges are kept but are partial; callers may drop them.
    """
    if len(t) < 3:
        return []
    dt = float(np.median(np.diff(t)))
    vx, vy = derivative(pos[:, 0], dt), derivative(pos[:, 1], dt)
    speed = np.hypot(vx, vy)
    if np.all(np.isnan(speed)):
        return []
    thr = abs_threshold if abs_threshold is not None else rel_threshold * np.nanpercentile(speed, 95)
    still = speed < thr  # NaN -> False
    out: list[ContactInterval] = []
    edges = np.flatnonzero(np.diff(np.concatenate(([0], still.astype(int), [0]))))
    for a, b in zip(edges[::2], edges[1::2]):
        if t[b - 1] - t[a] >= min_duration:
            out.append(ContactInterval(float(t[a]), float(t[b - 1]), int(a), int(b - 1)))
    return out


def foot_point(kin, side: str) -> np.ndarray:
    return 0.5 * (kin.get(side, "heel") + kin.get(side, "foot_index"))


@dataclass
class GaitEvents:
    contacts: dict[str, list[ContactInterval]]  # 'left'/'right' -> stance intervals

    def all_contacts_sorted(self) -> list[tuple[float, str]]:
        ev = [(c.start_s, s) for s, lst in self.contacts.items() for c in lst]
        return sorted(ev)

    def step_times(self) -> np.ndarray:
        """Time between successive foot contacts of alternating feet."""
        ev = self.all_contacts_sorted()
        out = [b[0] - a[0] for a, b in zip(ev, ev[1:]) if a[1] != b[1]]
        return np.array(out)

    def cadence_steps_per_min(self) -> float | None:
        st = self.step_times()
        return float(60.0 / np.mean(st)) if len(st) else None

    def stance_durations(self, side: str, t_start: float, t_end: float) -> np.ndarray:
        """Stance durations excluding intervals truncated by the clip edges."""
        return np.array([c.duration for c in self.contacts.get(side, [])
                         if c.start_s > t_start + 1e-9 and c.end_s < t_end - 1e-9])


def detect_gait(kin, rel_threshold: float = 0.15, min_duration: float = 0.08) -> GaitEvents:
    contacts = {}
    for s in ("left", "right"):
        contacts[s] = contact_intervals(kin.t, foot_point(kin, s), rel_threshold, None, min_duration)
    return GaitEvents(contacts)


def stance_mask(t: np.ndarray, intervals: list[ContactInterval]) -> np.ndarray:
    m = np.zeros(len(t), dtype=bool)
    for c in intervals:
        m[c.start_i: c.end_i + 1] = True
    return m


def normalize_cycle(t: np.ndarray, y: np.ndarray, start: float, end: float, n: int = 101) -> np.ndarray:
    """Resample y between two events onto 0..100 % (n points)."""
    pct = np.linspace(0, 1, n)
    tt = start + pct * (end - start)
    ok = ~np.isnan(y)
    if ok.sum() < 2:
        return np.full(n, np.nan)
    return np.interp(tt, t[ok], y[ok], left=np.nan, right=np.nan)
