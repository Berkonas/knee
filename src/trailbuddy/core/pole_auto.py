"""Markerless trekking-pole detection anchored at the hands.

Physical constraints used (from our recordings): each pole is a straight, thin shaft held in one hand,
so its axis passes through the wrist and extends downward to the tip. The shafts are a saturated colour
(blue/violet aluminium) unlike the stairs (black), walls (white) and clothing worn in our sessions.

Per frame and per hand:
 1. Region of interest around and below the wrist, sized by the person's height in pixels (H).
 2. Evidence: pole-coloured pixels (HSV gate) outside the (slightly dilated) torso polygon; if no
    colour evidence, Canny edges (lower confidence).
 3. Straight segments are found with the probabilistic Hough transform (OpenCV HoughLinesP).
 4. Geometric gating: the segment's line must pass within 0.07 H of the wrist, must start at the hand
    and not continue above it (rejects handrails and vertical curtain folds), and must point downward
    within +-40 deg of vertical and within 30 deg of the previous frame's angle.
 5. Tip = lower end of the longest gated segment; collinear pieces add support (occlusion by the legs).
    Confidence = supporting segment length / shaft length x closeness of the line to the wrist.
    Frames below the confidence threshold or with implausible length stay empty (NaN) - never guessed.
Manual correction (clicking the tip) overrides automatic values frame by frame (see pole.ManualAnnotations).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from .landmarks import PoseSeries, idx
from .pole import PoleTrack
from .video import FrameReader


@dataclass
class PoleColour:
    hue_low: int = 95       # OpenCV hue 0-179; 95-150 covers blue to violet
    hue_high: int = 150
    sat_min: int = 45
    val_min: int = 55       # excludes dark navy clothing (V ~ 40) while keeping the lit shaft


def evidence_mask(frame: np.ndarray, colour: PoleColour) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (colour.hue_low, colour.sat_min, colour.val_min), (colour.hue_high, 255, 255))


MAX_ANGLE = 40.0  # deg from vertical; poles in descent stay well inside this, handrails (45-60 deg) do not


def _segments(m: np.ndarray, body_h: float):
    lines = cv2.HoughLinesP(m, 1, np.pi / 180, threshold=max(15, int(0.05 * body_h)),
                            minLineLength=max(15, int(0.12 * body_h)), maxLineGap=max(5, int(0.06 * body_h)))
    return [] if lines is None else [tuple(float(v) for v in ln.reshape(-1)[:4]) for ln in lines]


def detect_in_frame(frame: np.ndarray, wrist: np.ndarray, body_h: float, exclude_poly: np.ndarray | None,
                    colour: PoleColour, prev_angle: float | None = None, mask: np.ndarray | None = None):
    """Return (tip_xy, angle_deg_from_down, length_px, confidence, method) or None.

    angle: 0 = pointing straight down, + = tip toward +image-x.
    A candidate shaft must (i) be a straight segment, (ii) lie on a line passing within 0.07 H of the wrist,
    (iii) start near the hand and not continue above it (rejects handrails and curtain folds), and
    (iv) point downward within +-40 deg of vertical (and within 30 deg of the previous frame's angle).
    """
    if not np.isfinite(wrist).all() or body_h < 20:
        return None
    h, w = frame.shape[:2]
    x0, x1 = int(max(0, wrist[0] - 0.7 * body_h)), int(min(w, wrist[0] + 0.7 * body_h))
    y0, y1 = int(max(0, wrist[1] - 0.25 * body_h)), int(min(h, wrist[1] + 1.05 * body_h))
    if x1 - x0 < 10 or y1 - y0 < 10:
        return None
    base = mask if mask is not None else evidence_mask(frame, colour)
    best = None
    for method in ("colour", "edges"):
        if method == "colour":
            m = base[y0:y1, x0:x1].copy()
        else:
            if best is not None:
                break
            m = cv2.Canny(cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY), 60, 160)
        if exclude_poly is not None:
            c = exclude_poly.mean(axis=0)
            cv2.fillConvexPoly(m, (c + 1.12 * (exclude_poly - c) - [x0, y0]).astype(np.int32), 0)
        wl = wrist - [x0, y0]
        cands = []
        for x_a, y_a, x_b, y_b in _segments(m, body_h):
            p_a, p_b = np.array([x_a, y_a]), np.array([x_b, y_b])
            if p_a[1] > p_b[1]:
                p_a, p_b = p_b, p_a          # p_a = upper end
            v = p_b - p_a
            L = np.linalg.norm(v)
            if L < 1:
                continue
            u = v / L
            ang = float(np.degrees(np.arctan2(u[0], u[1])))
            if abs(ang) > MAX_ANGLE:
                continue
            if prev_angle is not None and np.isfinite(prev_angle) and abs(ang - prev_angle) > 30:
                continue
            # distance from wrist to the segment's line, and position of the wrist along the line
            rel = wl - p_a
            perp = abs(rel[0] * u[1] - rel[1] * u[0])
            t_w = rel @ u                       # where the wrist projects (0 = upper end)
            if perp > 0.07 * body_h:
                continue
            if t_w < -0.35 * body_h:            # segment starts far below the hand
                continue
            if t_w > 0.12 * body_h:             # segment continues well above the hand -> rail/fold
                continue
            tip_r = float((p_b - wl) @ u)       # tip distance from the wrist along the axis
            cands.append((tip_r, ang, u, L, perp))
        if not cands:
            continue
        # merge collinear candidates (occluded shaft) - take the longest reach among similar angles
        cands.sort(key=lambda c: -c[0])
        tip_r, ang, u, L, perp = cands[0]
        support = sum(c[3] for c in cands if abs(c[1] - ang) < 4)
        if tip_r < 0.25 * body_h or tip_r > 1.0 * body_h:
            continue
        conf = float(np.clip(support / tip_r, 0, 1) * np.clip(1 - perp / (0.07 * body_h), 0.2, 1))
        if method == "edges":
            conf *= 0.6
        best = (wrist + u * tip_r, ang, tip_r, conf, method)
    return best


def track_poles(video: str, pose: PoseSeries, frame0: int = 0, colour: PoleColour | None = None,
                min_conf: float = 0.25, progress: Callable[[float], None] | None = None,
                cancelled: Callable[[], bool] | None = None) -> dict[str, PoleTrack]:
    """Track both poles through the frames covered by ``pose`` (same frame indices/time base)."""
    from .pose import Cancelled

    colour = colour or PoleColour()
    reader = FrameReader(video)
    n = pose.n_frames
    stride = int(pose.meta.get("stride", 1))
    out = {s: {"tip": np.full((n, 2), np.nan), "conf": np.zeros(n), "src": np.zeros(n, int)} for s in ("left", "right")}
    prev_ang = {"left": None, "right": None}
    end = frame0 + n * stride
    k = 0
    for i, frame in reader.iter_range(frame0, end):
        if (i - frame0) % stride:
            continue
        if k >= n:
            break
        if cancelled and cancelled():
            reader.close()
            raise Cancelled()
        xy = pose.xy[k]
        ok = np.isfinite(xy[[11, 12, 23, 24, 27, 28]]).all(axis=1)
        if ok.sum() >= 4:
            top = np.nanmin(xy[[0, 11, 12], 1])
            bottom = np.nanmax(xy[[27, 28, 29, 30, 31, 32], 1])
            body_h = float(bottom - top) * 1.1
            torso = xy[[11, 12, 24, 23]]
            excl = torso if np.isfinite(torso).all() else None
            mask = evidence_mask(frame, colour)
            for side in ("left", "right"):
                wr = xy[idx(side, "wrist")]
                res = detect_in_frame(frame, wr, body_h, excl, colour, prev_ang[side], mask)
                if res is not None and res[3] >= min_conf:
                    tip, ang, _, conf, method = res
                    out[side]["tip"][k] = tip
                    out[side]["conf"][k] = conf
                    out[side]["src"][k] = 1
                    prev_ang[side] = ang
                else:
                    prev_ang[side] = None if res is None else prev_ang[side]
        k += 1
        if progress and k % 10 == 0:
            progress(k / n)
    reader.close()
    tracks = {}
    for side, d in out.items():
        tip = d["tip"].copy()
        # outlier rejection: tip jumps larger than 0.25 body heights between frames are removed
        tracks[side] = PoleTrack(pose.t.copy(), tip, None, d["conf"], d["src"], method="auto_wrist_ray")
    if progress:
        progress(1.0)
    return tracks
