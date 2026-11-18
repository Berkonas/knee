"""Non-destructive movement segmentation: candidate analysis intervals inside a recording.

Segments are timestamps stored with the trial; the video files are never cut. A segment is a period of
whole-body movement (mid-hip speed above a threshold, short pauses bridged), labelled by what the hips do:
'descent' when they drop by at least half a leg length, 'ascent' when they rise, otherwise 'level movement'.
Periods without tracking inside a segment are reported, never removed, so timing stays continuous.
"""

from __future__ import annotations

import numpy as np

MOVE_LEGS_PER_S = 0.25   # mid-hip speed (leg lengths per second) that counts as moving
BRIDGE_S = 0.6           # pauses shorter than this stay inside one segment
MIN_SEGMENT_S = 1.0
PAD_S = 0.3


def candidate_segments(pose, min_drop_legs: float = 0.5) -> list[dict]:
    from scipy.ndimage import median_filter

    t = pose.t
    import warnings

    with warnings.catch_warnings():  # frames with no hip keypoints give NaN (expected)
        warnings.simplefilter("ignore", RuntimeWarning)
        hip = np.nanmean(pose.xy[:, [23, 24]], axis=1)
    from .landmarks import leg_length_px
    leg = leg_length_px(pose.xy)
    ok = np.isfinite(hip).all(axis=1)
    if ok.sum() < 10 or not np.isfinite(leg) or leg <= 0:
        return []
    w = max(3, int(round(0.25 * pose.fps)) | 1)
    hx = median_filter(np.interp(t, t[ok], hip[ok, 0]), size=w, mode="nearest") / leg
    hy = median_filter(np.interp(t, t[ok], hip[ok, 1]), size=w, mode="nearest") / leg
    sp = np.hypot(np.gradient(hx, t), np.gradient(hy, t))
    sp = median_filter(sp, size=w, mode="nearest")
    # inside long tracking gaps the interpolated hip is invented: no movement can be claimed there
    edges_g = np.flatnonzero(np.diff(np.concatenate(([0], (~ok).astype(int), [0]))))
    for a, b in zip(edges_g[::2], edges_g[1::2]):
        if t[min(b, len(t) - 1)] - t[a] > BRIDGE_S:
            sp[a:b] = 0.0
    moving = sp > MOVE_LEGS_PER_S
    # bridge short pauses
    edges = np.flatnonzero(np.diff(np.concatenate(([0], moving.astype(int), [0]))))
    runs = [[t[a], t[b - 1]] for a, b in zip(edges[::2], edges[1::2])]
    merged: list[list[float]] = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < BRIDGE_S:
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    out = []
    for a, b in merged:
        if b - a < MIN_SEGMENT_S:
            continue
        a, b = max(float(t[0]), a - PAD_S), min(float(t[-1]), b + PAD_S)
        m = (t >= a) & (t <= b)
        drop = float(hy[m][-1] - hy[m][0])  # image y grows downward: + = hips went down
        label = "descent" if drop >= min_drop_legs else ("ascent" if drop <= -min_drop_legs else "level movement")
        out.append({"start_s": round(float(a), 3), "end_s": round(float(b), 3), "label": label, "hip_drop_legs": round(drop, 2),
                    "tracked_fraction": round(float(ok[m].mean()), 3), "source": "auto"})
    return out


def best_segment(segs: list[dict]) -> dict | None:
    """The descent with the largest hip drop (then the longest), else the longest segment."""
    if not segs:
        return None
    desc = [s for s in segs if s["label"] == "descent"]
    pool = desc or segs
    return max(pool, key=lambda s: (s["hip_drop_legs"] if desc else 0, s["end_s"] - s["start_s"]))
