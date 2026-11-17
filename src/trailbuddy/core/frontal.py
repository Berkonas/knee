"""Front-view (frontal-plane) 2D measures. All are angles or ratios, so they need no metric scale.

Image frame: x right, y down. Angles are 2D projections onto the image plane of the front camera.

  knee FPPA (L/R)        180 deg - angle(hip, knee, ankle); 0 = straight line, + = knee deviates
                         (frontal-plane projection angle, a 2D screening measure; not 3D valgus)
  trunk lateral lean     angle of mid-hip -> mid-shoulder from vertical (+ = toward image right)
  pelvic obliquity       angle of the left-right hip line from horizontal
  pole frontal angle     pole axis (wrist -> tip) from vertical (+ = tip toward image right)
  pole tip spread        |tip_L - tip_R| / shoulder width  (dimensionless)
  step width             |ankle_L - ankle_R| (horizontal) / hip width  (dimensionless)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .kinematics import interior_angle
from .landmarks import PoseSeries, idx
from .metrics import MetricValue
from .pole import PoleTrack
from .signal import condition_xy


def _ang_from_vertical(v: np.ndarray) -> np.ndarray:
    # v in image coords (x right, y down); vertical down = (0, 1)
    return np.degrees(np.arctan2(v[..., 0], v[..., 1]))


def analyse_front(pose: PoseSeries, poles: dict[str, PoleTrack] | None = None, cutoff_hz: float = 6.0,
                  min_visibility: float = 0.5) -> tuple[pd.DataFrame, list[MetricValue], dict]:
    xy = pose.xy.copy()
    xy[pose.visibility < min_visibility] = np.nan
    xy, _ = condition_xy(xy, pose.fps, cutoff_hz, max_gap=max(1, int(0.1 * pose.fps)))
    P = lambda s, n: xy[:, idx(s, n)]  # noqa: E731
    ts = {"time_s": pose.t}
    for s in ("left", "right"):
        ts[f"front_{s}_knee_fppa_deg"] = 180.0 - interior_angle(P(s, "hip"), P(s, "knee"), P(s, "ankle"))
    mid_h = 0.5 * (P("left", "hip") + P("right", "hip"))
    mid_s = 0.5 * (P("left", "shoulder") + P("right", "shoulder"))
    v = mid_s - mid_h  # points up the trunk
    ts["front_trunk_lateral_lean_deg"] = np.degrees(np.arctan2(v[:, 0], -v[:, 1]))
    hv = P("right", "hip") - P("left", "hip")
    ts["front_pelvic_obliquity_deg"] = np.degrees(np.arctan2(hv[:, 1], np.abs(hv[:, 0]) + 1e-9))
    shoulder_w = np.linalg.norm(P("left", "shoulder") - P("right", "shoulder"), axis=1)
    hip_w = np.linalg.norm(hv, axis=1)
    ts["front_step_width_ratio"] = np.abs(P("left", "ankle")[:, 0] - P("right", "ankle")[:, 0]) / hip_w
    tips = {}
    for s, tr in (poles or {}).items():
        if tr is None or tr.coverage() == 0:
            continue
        tip = np.stack([np.interp(pose.t, tr.t, tr.tip[:, c], left=np.nan, right=np.nan) for c in range(2)], axis=1)
        tips[s] = tip
        ts[f"front_pole_{s}_angle_deg"] = _ang_from_vertical(tip - P(s, "wrist"))
    if "left" in tips and "right" in tips:
        ts["front_pole_tip_spread_ratio"] = np.linalg.norm(tips["left"] - tips["right"], axis=1) / shoulder_w
    df = pd.DataFrame(ts)
    M = []

    def mv(key, series, fn, note=""):
        v = series[np.isfinite(series)]
        M.append(MetricValue(key, float(fn(v)) if len(v) else None, "video" if len(v) else "unavailable",
                             note or ("" if len(v) else "Not visible in the front view.")))

    fppa = np.nanmax(np.abs(np.stack([df.front_left_knee_fppa_deg, df.front_right_knee_fppa_deg])), axis=0) \
        if np.isfinite(df[["front_left_knee_fppa_deg", "front_right_knee_fppa_deg"]].to_numpy()).any() else np.full(len(df), np.nan)
    mv("front_knee_fppa_peak", fppa, np.max, "larger of the two knees")
    mv("front_trunk_lateral_lean_rom", df.front_trunk_lateral_lean_deg.to_numpy(), np.ptp)
    mv("front_pelvic_obliquity_rom", df.front_pelvic_obliquity_deg.to_numpy(), np.ptp)
    mv("front_step_width_ratio_mean", df.front_step_width_ratio.to_numpy(), np.mean)
    if "front_pole_tip_spread_ratio" in df:
        mv("front_pole_tip_spread_mean", df.front_pole_tip_spread_ratio.to_numpy(), np.mean)
    else:
        M.append(MetricValue("front_pole_tip_spread_mean", None, "unavailable",
                             "Both poles must be tracked in the front view."))
    quality = {"front_detection_rate": pose.detection_rate(),
               "front_pole_coverage": {s: float(np.isfinite(t[:, 0]).mean()) for s, t in tips.items()}}
    return df, M, quality
