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
                      abs_threshold: float | None = None, min_duration: float = 0.08,
                      merge_gap: float = 0.1, pos2: np.ndarray | None = None) -> list[ContactInterval]:
    """Detect stationary intervals of a 2D point trajectory.

    Threshold = abs_threshold if given (units/s), otherwise rel_threshold * 95th-percentile speed.
    Intervals touching the clip edges are kept but are partial; callers may drop them.
    """
    if len(t) < 3:
        return []
    dt = float(np.median(np.diff(t)))
    vx, vy = derivative(pos[:, 0], dt), derivative(pos[:, 1], dt)
    speed = np.hypot(vx, vy)
    if pos2 is not None:
        # contact while EITHER point is stationary (heel or toe): in stair descent the forefoot lands first and
        # the heel lifts before the toe, so the toe alone or heel alone would cut stance short
        s2 = np.hypot(derivative(pos2[:, 0], dt), derivative(pos2[:, 1], dt))
        speed = np.fmin(speed, s2)
    if np.all(np.isnan(speed)):
        return []
    thr = abs_threshold if abs_threshold is not None else rel_threshold * np.nanpercentile(speed, 95)
    still = speed < thr  # NaN -> False
    # bridge short interruptions (<= merge_gap) caused by keypoint jitter during a genuine contact
    gap = max(1, int(round(merge_gap / dt)))
    e = np.flatnonzero(np.diff(np.concatenate(([0], still.astype(int), [0]))))
    for b, a in zip(e[1::2][:-1], e[2::2]):
        if a - b <= gap:
            still[b:a] = True
    out: list[ContactInterval] = []
    edges = np.flatnonzero(np.diff(np.concatenate(([0], still.astype(int), [0]))))
    for a, b in zip(edges[::2], edges[1::2]):
        if t[b - 1] - t[a] >= min_duration:
            # end_s marks the end of the last stationary frame (duration = n_frames / fs)
            out.append(ContactInterval(float(t[a]), float(t[b - 1] + dt), int(a), int(b - 1)))
    return out


def foot_point(kin, side: str) -> np.ndarray:
    return 0.5 * (kin.get(side, "heel") + kin.get(side, "foot_index"))


@dataclass
class GaitEvents:
    contacts: dict[str, list[ContactInterval]]  # 'left'/'right' -> stance intervals
    n_frames: int | None = None  # used to exclude contacts truncated by the clip start

    def all_contacts_sorted(self) -> list[tuple[float, str]]:
        ev = [(c.start_s, s) for s, lst in self.contacts.items() for c in lst]
        return sorted(ev)

    def step_times(self) -> np.ndarray:
        """Time between successive foot strikes of alternating feet.

        Contacts already in progress at the first frame are not foot strikes and are excluded.
        """
        ev = sorted((c.start_s, s) for s, lst in self.contacts.items() for c in lst if c.start_i > 0)
        out = [b[0] - a[0] for a, b in zip(ev, ev[1:]) if a[1] != b[1]]
        return np.array(out)

    def stride_times(self, side: str) -> np.ndarray:
        """Time between successive foot strikes of the same foot (robust when the other foot is hidden)."""
        st = [c.start_s for c in self.contacts.get(side, []) if c.start_i > 0]
        return np.diff(st) if len(st) > 1 else np.array([])

    def cadence_steps_per_min(self, side: str | None = None) -> float | None:
        """Steps per minute. With ``side``: 120 / mean stride time of that foot (two steps per stride),
        which does not depend on detecting the other (often occluded) foot."""
        if side is not None:
            sr = self.stride_times(side)
            if len(sr):
                return float(120.0 / np.mean(sr))
        st = self.step_times()
        return float(60.0 / np.mean(st)) if len(st) else None

    def stance_durations(self, side: str, t_start: float, t_end: float) -> np.ndarray:
        """Stance durations excluding intervals truncated by the clip edges."""
        return np.array([c.duration for c in self.contacts.get(side, [])
                         if c.start_i > 0 and (self.n_frames is None or c.end_i < self.n_frames - 1)])


def detect_gait(kin, rel_threshold: float = 0.15, min_duration: float = 0.08) -> GaitEvents:
    contacts = {}
    for s in ("left", "right"):
        contacts[s] = contact_intervals(kin.t, kin.get(s, "heel"), rel_threshold, None, min_duration,
                                        pos2=kin.get(s, "foot_index"))
    return GaitEvents(contacts, len(kin.t))


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


def descent_window(pose, pad_before: float = 0.4, pad_after: float = 0.3, min_drop_legs: float = 0.5):
    """Automatic analysis window: the period in which the participant's hips move down the stairs.

    Hip height (image y of the mid-hip, in leg lengths, 0.5 s median-smoothed) is flat while standing at the top,
    falls step by step during the descent and is flat again at the bottom. The window runs from 5% to 97% of the
    total drop, padded by ``pad_before`` / ``pad_after`` seconds. Returns (t0, t1, drop_legs) or None when no clear
    descent (drop < min_drop_legs leg lengths) is visible.
    Works for side and front views (in both, the hips move down in the image while descending).
    """
    from scipy.ndimage import median_filter

    hy = np.nanmean(pose.xy[:, [23, 24], 1], axis=1)
    leg = np.nanmedian(np.linalg.norm(pose.xy[:, 23] - pose.xy[:, 27], axis=1))
    ok = np.isfinite(hy)
    if ok.sum() < 10 or not np.isfinite(leg) or leg <= 0:
        return None
    t = pose.t
    y = np.interp(t, t[ok], hy[ok]) / leg
    w = max(3, int(round(0.5 * pose.fps)) | 1)
    ys = median_filter(y, size=w, mode="nearest")
    n_edge = max(3, int(0.5 * pose.fps))
    y0, y1 = float(np.median(ys[:n_edge])), float(np.max(ys))
    drop = y1 - y0
    if drop < min_drop_legs:
        return None
    i0 = int(np.argmax(ys > y0 + 0.05 * drop))
    i1 = int(np.argmax(ys > y0 + 0.97 * drop))
    t0 = max(float(t[0]), float(t[i0]) - pad_before)
    t1 = min(float(t[-1]), float(t[i1]) + pad_after)
    return t0, t1, drop
