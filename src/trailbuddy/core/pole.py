"""Trekking-pole tracking.

Supported methods (all produce the same ``PoleTrack``):

* ``ColorMarkerDetector`` - automatic tracking of a brightly coloured marker (tape) on the pole
  tip and, optionally, a second marker near the grip. Recommended for data collection.
* Manual annotation - the user clicks the tip (and optionally top) on key frames; values are
  linearly interpolated only across short gaps and flagged as interpolated.
* ``PoleDetector`` protocol - plug-in point for a future learned detector (e.g. a YOLO keypoint
  model trained on our own pole videos).

Frames where the pole cannot be found are left as NaN with source 'missing' - coordinates are
never invented. Pole *force* cannot be measured from video; see dynamics.PoleLoad.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from .events import contact_intervals
from .signal import fill_gaps

SOURCE_CODES = {"missing": 0, "auto": 1, "manual": 2, "interp": 3}


@dataclass
class PoleTrack:
    """Tracked pole points in image pixels for one pole ('left' or 'right' hand)."""

    t: np.ndarray
    tip: np.ndarray                    # (n,2) px, NaN if unknown
    top: np.ndarray | None = None      # (n,2) px, optional second marker near the grip
    confidence: np.ndarray | None = None
    source: np.ndarray | None = None   # int codes, see SOURCE_CODES
    method: str = "manual"

    def __post_init__(self):
        n = len(self.t)
        if self.confidence is None:
            self.confidence = np.where(np.isnan(self.tip[:, 0]), 0.0, 1.0)
        if self.source is None:
            self.source = np.where(np.isnan(self.tip[:, 0]), 0, 2)
        assert self.tip.shape == (n, 2)

    def coverage(self) -> float:
        return float(np.mean(~np.isnan(self.tip[:, 0]))) if len(self.t) else 0.0

    def angle_from_vertical_deg(self, hand_px: np.ndarray | None = None) -> np.ndarray:
        """Pole inclination from vertical in the image (deg, + = tip ahead of hand in +image-x)."""
        upper = self.top if self.top is not None else hand_px
        if upper is None:
            return np.full(len(self.t), np.nan)
        v = self.tip - upper  # image coords, y down
        return np.degrees(np.arctan2(v[:, 0], v[:, 1]))

    def length_px(self, hand_px: np.ndarray | None = None) -> np.ndarray:
        upper = self.top if self.top is not None else hand_px
        if upper is None:
            return np.full(len(self.t), np.nan)
        return np.linalg.norm(self.tip - upper, axis=1)


class PoleDetector(Protocol):
    def detect(self, frame_bgr: np.ndarray, prev: tuple[float, float] | None) -> tuple[float, float, float] | None:
        """Return (x, y, confidence) for one marker, or None if not found."""


@dataclass
class ColorMarkerDetector:
    """HSV threshold + largest-blob centroid, searched near the previous position."""

    hsv_low: tuple[int, int, int]
    hsv_high: tuple[int, int, int]
    search_radius: int = 120
    min_area: int = 12

    @staticmethod
    def from_sample(frame_bgr: np.ndarray, x: int, y: int, tol_h: int = 12, min_s: int = 80,
                    min_v: int = 60) -> "ColorMarkerDetector":
        """Build a detector from the colour of a clicked pixel (5x5 median)."""
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        patch = hsv[max(0, y - 2):y + 3, max(0, x - 2):x + 3].reshape(-1, 3)
        h, s, v = np.median(patch, axis=0).astype(int)
        if s < min_s:
            raise ValueError("Selected pixel is not saturated enough to be a coloured marker. "
                             "Use bright tape (e.g. fluorescent orange/green) on the pole tip.")
        return ColorMarkerDetector((max(0, h - tol_h), min_s, min_v), (min(179, h + tol_h), 255, 255))

    def detect(self, frame_bgr, prev=None):
        h, w = frame_bgr.shape[:2]
        x0, y0, x1, y1 = 0, 0, w, h
        if prev is not None and np.all(np.isfinite(prev)):
            px, py = int(prev[0]), int(prev[1])
            r = self.search_radius
            x0, y0, x1, y1 = max(0, px - r), max(0, py - r), min(w, px + r), min(h, py + r)
        roi = frame_bgr[y0:y1, x0:x1]
        if roi.size == 0:
            return None
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(self.hsv_low), np.array(self.hsv_high))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, labels, stats, cents = cv2.connectedComponentsWithStats(mask)
        if n <= 1:
            return None
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        area = stats[k, cv2.CC_STAT_AREA]
        if area < self.min_area:
            return None
        second = np.sort(stats[1:, cv2.CC_STAT_AREA])[-2] if n > 2 else 0
        conf = float(min(1.0, area / (area + second + 1e-9)))  # ambiguity lowers confidence
        cx, cy = cents[k]
        return float(cx + x0), float(cy + y0), conf


def track(frames, t: np.ndarray, tip_det: PoleDetector, top_det: PoleDetector | None = None,
          min_conf: float = 0.6, start_tip=None, start_top=None) -> PoleTrack:
    """Run detectors over an iterable of BGR frames aligned with ``t``."""
    n = len(t)
    tip = np.full((n, 2), np.nan)
    top = np.full((n, 2), np.nan) if top_det else None
    conf = np.zeros(n)
    prev_tip, prev_top = start_tip, start_top
    for i, frame in enumerate(frames):
        if i >= n:
            break
        r = tip_det.detect(frame, prev_tip)
        if r and r[2] >= min_conf:
            tip[i] = r[:2]
            conf[i] = r[2]
            prev_tip = r[:2]
        if top_det is not None:
            r2 = top_det.detect(frame, prev_top)
            if r2 and r2[2] >= min_conf:
                top[i] = r2[:2]
                prev_top = r2[:2]
    source = np.where(np.isnan(tip[:, 0]), 0, 1)
    return PoleTrack(t, tip, top, conf, source, method="color_marker")


@dataclass
class ManualAnnotations:
    """User-clicked pole points: {pole: {'tip'|'top': {frame_index: (x, y)}}}."""

    points: dict = field(default_factory=dict)

    def set(self, pole: str, part: str, frame: int, x: float, y: float) -> None:
        self.points.setdefault(pole, {}).setdefault(part, {})[int(frame)] = (float(x), float(y))

    def remove(self, pole: str, part: str, frame: int) -> None:
        self.points.get(pole, {}).get(part, {}).pop(int(frame), None)

    def to_track(self, pole: str, t: np.ndarray, frame0: int = 0, max_gap_frames: int = 15) -> PoleTrack:
        n = len(t)
        def series(part):
            arr = np.full((n, 2), np.nan)
            for f, (x, y) in self.points.get(pole, {}).get(part, {}).items():
                if 0 <= f - frame0 < n:
                    arr[f - frame0] = (x, y)
            return arr
        tip_raw, top_raw = series("tip"), series("top")
        tip = np.stack([fill_gaps(tip_raw[:, c], max_gap_frames)[0] for c in range(2)], axis=1)
        src = np.where(~np.isnan(tip_raw[:, 0]), 2, np.where(~np.isnan(tip[:, 0]), 3, 0))
        top = None
        if not np.all(np.isnan(top_raw)):
            top = np.stack([fill_gaps(top_raw[:, c], max_gap_frames)[0] for c in range(2)], axis=1)
        conf = np.where(src == 2, 1.0, np.where(src == 3, 0.5, 0.0))
        return PoleTrack(t, tip, top, conf, src, method="manual")

    def save(self, path: Path) -> None:
        data = {p: {part: {str(k): v for k, v in d.items()} for part, d in parts.items()}
                for p, parts in self.points.items()}
        Path(path).write_text(json.dumps(data, indent=1))

    @classmethod
    def load(cls, path: Path) -> "ManualAnnotations":
        raw = json.loads(Path(path).read_text())
        return cls({p: {part: {int(k): tuple(v) for k, v in d.items()} for part, d in parts.items()}
                    for p, parts in raw.items()})


def pole_contacts(track: PoleTrack, rel_threshold: float = 0.15, min_duration: float = 0.08,
                  min_coverage: float = 0.5):
    """Estimated pole-ground contact intervals (tip stationary). None if tracking is too sparse."""
    if track.coverage() < min_coverage:
        return None
    filled = np.stack([fill_gaps(track.tip[:, c], 5)[0] for c in range(2)], axis=1)
    return contact_intervals(track.t, filled, rel_threshold, None, min_duration)
