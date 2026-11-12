"""2D sagittal-plane kinematics from pose landmarks.

Coordinate frame ("lab frame"):
  * x = horizontal, positive in the participant's direction of travel
  * y = vertical, positive up
  * units = metres when a scale is known, otherwise pixels (flagged in the output).

Segment angles are measured counter-clockwise from +x (Winter, 2009 convention), using the
vector from the distal to the proximal end. Joint angles (degrees):

  knee flexion     = theta_thigh - theta_shank            (0 = straight, + = flexed)
  hip flexion      = theta_thigh - theta_trunk            (0 = thigh in line with trunk)
  ankle dorsiflex. = 90 - (theta_shank - theta_foot)      (0 = shank perpendicular to foot)
  trunk lean       = 90 - theta_trunk                     (+ = leaning forward)
  shoulder flexion = angle(upper arm) - angle(trunk, pointing down)   (+ = arm forward)
  elbow flexion    = 180 - interior angle(shoulder, elbow, wrist)

All values are 2D projections onto the image plane. They equal true sagittal angles only when
the camera's optical axis is perpendicular to the plane of motion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .landmarks import PoseSeries, idx
from .signal import condition_xy, derivative

SIDES = ("left", "right")

# Winter (2009) segment lengths as a fraction of body height.
THIGH_FRAC = 0.245
SHANK_FRAC = 0.246


def wrap180(a: np.ndarray) -> np.ndarray:
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


def seg_angle(distal: np.ndarray, proximal: np.ndarray) -> np.ndarray:
    v = proximal - distal
    return np.degrees(np.arctan2(v[..., 1], v[..., 0]))


def interior_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Angle ABC (at b) in degrees."""
    u, v = a - b, c - b
    cos = np.sum(u * v, axis=-1) / (np.linalg.norm(u, axis=-1) * np.linalg.norm(v, axis=-1))
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


@dataclass
class Kinematics:
    t: np.ndarray
    fs: float
    pts: dict[str, np.ndarray]          # name -> (n, 2) lab-frame positions (filtered)
    angles: dict[str, np.ndarray]       # e.g. 'right_knee_flexion' -> (n,) degrees
    units: str                          # 'm' or 'px'
    scale_m_per_px: float | None
    direction: int                      # +1 if walking toward +image-x, -1 otherwise
    quality: dict[str, float] = field(default_factory=dict)  # mean visibility, % interpolated
    interpolated: np.ndarray | None = None

    def get(self, side: str, name: str) -> np.ndarray:
        return self.pts[f"{side}_{name}"]

    def velocity(self, key: str) -> np.ndarray:
        p = self.pts[key]
        dt = 1.0 / self.fs
        return np.stack([derivative(p[:, 0], dt), derivative(p[:, 1], dt)], axis=1)


POINT_NAMES = ["shoulder", "elbow", "wrist", "index", "hip", "knee", "ankle", "heel", "foot_index"]


def walking_direction(pose: PoseSeries) -> int:
    """+1 if the hips move toward larger image x over the clip, else -1."""
    hips = np.nanmean(pose.xy[:, [idx("left", "hip"), idx("right", "hip")], 0], axis=1)
    ok = ~np.isnan(hips)
    if ok.sum() < 2:
        return 1
    return 1 if hips[ok][-1] >= hips[ok][0] else -1


def scale_from_height(pose: PoseSeries, height_m: float, side: str | None = None,
                      thigh_m: float | None = None, shank_m: float | None = None) -> float:
    """Approximate metres-per-pixel from thigh+shank pixel length.

    Real length = measured thigh + shank (tape measure) when both are given, otherwise
    height x Winter fractions (0.245 + 0.246). Uses the median over frames, so it tolerates some
    tracking noise. Less accurate than a calibration distance measured in the scene.
    """
    vals = []
    for s in (SIDES if side is None else (side,)):
        hip, knee, ank = pose.point(s, "hip"), pose.point(s, "knee"), pose.point(s, "ankle")
        lpx = np.linalg.norm(hip - knee, axis=1) + np.linalg.norm(knee - ank, axis=1)
        ids = [idx(s, n) for n in ("hip", "knee", "ankle")]
        lpx = np.where(pose.visibility[:, ids].min(axis=1) >= 0.5, lpx, np.nan)  # visibility gate
        vals.append(lpx)
    lpx = np.nanmedian(np.concatenate(vals))
    if not np.isfinite(lpx) or lpx <= 0:
        raise ValueError("Cannot estimate scale: legs not detected.")
    real = (thigh_m + shank_m) if (thigh_m and shank_m) else height_m * (THIGH_FRAC + SHANK_FRAC)
    return real / lpx


def scale_from_points(p1: tuple[float, float], p2: tuple[float, float], distance_m: float) -> float:
    d = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
    if d <= 0 or distance_m <= 0:
        raise ValueError("Calibration points must be distinct and the distance positive.")
    return distance_m / d


def to_lab(xy_px: np.ndarray, height_px: int, direction: int, scale: float | None) -> np.ndarray:
    """Image pixels (y down) -> lab frame (x forward, y up)."""
    out = np.empty_like(xy_px, dtype=float)
    out[..., 0] = xy_px[..., 0] * direction
    out[..., 1] = height_px - xy_px[..., 1]
    if scale:
        out *= scale
    return out


def compute(pose: PoseSeries, scale_m_per_px: float | None = None, cutoff_hz: float = 6.0,
            max_gap_s: float = 0.1, min_visibility: float = 0.5, direction: int | None = None) -> Kinematics:
    """Filter landmarks and compute 2D joint angles for both sides."""
    if pose.n_frames < 5:
        raise ValueError("Need at least 5 frames to compute kinematics.")
    fs = pose.fps
    direction = walking_direction(pose) if direction is None else direction
    xy = pose.xy.copy()
    xy[pose.visibility < min_visibility] = np.nan  # discard low-confidence landmarks
    raw_mask = np.isnan(xy[..., 0])
    filt, interp = condition_xy(xy, fs, cutoff_hz, max_gap=max(1, int(round(max_gap_s * fs))))
    lab = to_lab(filt, pose.height, direction, scale_m_per_px)

    pts: dict[str, np.ndarray] = {}
    for s in SIDES:
        for nm in POINT_NAMES:
            pts[f"{s}_{nm}"] = lab[:, idx(s, nm), :]
    pts["head"] = lab[:, 0, :]  # nose landmark
    # Midpoints use whichever side is available (the far side is often occluded in a side view).
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pts["mid_hip"] = np.nanmean(np.stack([pts["left_hip"], pts["right_hip"]]), axis=0)
        pts["mid_shoulder"] = np.nanmean(np.stack([pts["left_shoulder"], pts["right_shoulder"]]), axis=0)

    ang: dict[str, np.ndarray] = {}
    for s in SIDES:
        g = lambda n: pts[f"{s}_{n}"]  # noqa: E731
        th_trunk = seg_angle(g("hip"), g("shoulder"))
        th_thigh = seg_angle(g("knee"), g("hip"))
        th_shank = seg_angle(g("ankle"), g("knee"))
        th_foot = seg_angle(g("heel"), g("foot_index"))
        th_uarm = seg_angle(g("shoulder"), g("elbow"))  # shoulder->elbow, pointing down
        th_trunk_down = seg_angle(g("shoulder"), g("hip"))
        ang[f"{s}_knee_flexion"] = wrap180(th_thigh - th_shank)
        ang[f"{s}_hip_flexion"] = wrap180(th_thigh - th_trunk)
        ang[f"{s}_ankle_dorsiflexion"] = wrap180(90.0 - wrap180(th_shank - th_foot))
        ang[f"{s}_shoulder_flexion"] = wrap180(th_uarm - th_trunk_down)
        ang[f"{s}_elbow_flexion"] = 180.0 - interior_angle(g("shoulder"), g("elbow"), g("wrist"))
    ang["trunk_lean"] = wrap180(90.0 - seg_angle(pts["mid_hip"], pts["mid_shoulder"]))

    quality = {"detection_rate": pose.detection_rate()}
    for s in SIDES:
        ids = [idx(s, n) for n in ("hip", "knee", "ankle", "shoulder", "elbow", "wrist")]
        quality[f"{s}_mean_visibility"] = float(np.nanmean(pose.visibility[:, ids]))
    quality["pct_interpolated"] = float(100 * interp.mean())
    quality["pct_missing_after_fill"] = float(100 * np.isnan(filt[..., 0]).mean())
    quality["pct_low_confidence_raw"] = float(100 * raw_mask.mean())

    return Kinematics(pose.t.copy(), fs, pts, ang, "m" if scale_m_per_px else "px",
                      scale_m_per_px, direction, quality, interp)


def best_side(kin: Kinematics) -> str:
    """Side facing the camera (higher mean visibility)."""
    lv = kin.quality.get("left_mean_visibility", 0)
    rv = kin.quality.get("right_mean_visibility", 0)
    return "left" if lv >= rv else "right"


def walking_speed(kin: Kinematics) -> float | None:
    """Mean horizontal speed of the mid-hip (m/s) over valid frames; None without scale."""
    if kin.units != "m":
        return None
    x = kin.pts["mid_hip"][:, 0]
    ok = ~np.isnan(x)
    if ok.sum() < 2:
        return None
    t = kin.t[ok]
    return float(abs(x[ok][-1] - x[ok][0]) / (t[-1] - t[0]))
