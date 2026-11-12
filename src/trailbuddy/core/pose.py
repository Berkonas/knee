"""Human pose estimation with MediaPipe Pose Landmarker (BlazePose GHUM, 33 landmarks).

Model files (Apache-2.0) are downloaded once from Google's model storage on first use.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .landmarks import N_LANDMARKS, PoseSeries
from .paths import models_dir
from .video import FrameReader

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_{v}/float16/latest/pose_landmarker_{v}.task")
MODEL_VARIANTS = ("lite", "full", "heavy")


class Cancelled(Exception):
    pass


def model_path(variant: str = "full", download: bool = True) -> Path:
    if variant not in MODEL_VARIANTS:
        raise ValueError(f"Unknown model variant {variant!r}")
    path = models_dir() / f"pose_landmarker_{variant}.task"
    if not path.exists():
        if not download:
            raise FileNotFoundError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        try:
            urllib.request.urlretrieve(MODEL_URL.format(v=variant), tmp)
        except OSError as e:
            raise RuntimeError(
                "Could not download the pose model (internet needed once). "
                f"Download {MODEL_URL.format(v=variant)} manually into {path.parent}.") from e
        tmp.replace(path)
    return path


def estimate(video: str | Path, start_frame: int = 0, end_frame: int | None = None,
             variant: str = "full", min_confidence: float = 0.5,
             progress: Callable[[float], None] | None = None,
             cancelled: Callable[[], bool] | None = None) -> PoseSeries:
    """Run pose estimation on frames [start_frame, end_frame). Undetected frames are NaN."""
    from mediapipe import Image, ImageFormat
    from mediapipe.tasks.python import BaseOptions, vision

    reader = FrameReader(video)
    info = reader.info
    end = info.n_frames if end_frame is None else min(end_frame, info.n_frames)
    if end - start_frame < 2:
        raise ValueError("Analysis interval must contain at least 2 frames.")
    opts = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path(variant))),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=min_confidence,
        min_pose_presence_confidence=min_confidence,
        min_tracking_confidence=min_confidence,
    )
    n = end - start_frame
    xy = np.full((n, N_LANDMARKS, 2), np.nan)
    vis = np.zeros((n, N_LANDMARKS))
    t = (np.arange(start_frame, end) / info.fps)
    with vision.PoseLandmarker.create_from_options(opts) as lm:
        for k, (i, frame) in enumerate(reader.iter_range(start_frame, end)):
            if cancelled and cancelled():
                reader.close()
                raise Cancelled()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = lm.detect_for_video(Image(image_format=ImageFormat.SRGB, data=rgb), int(round(1000 * i / info.fps)))
            if res.pose_landmarks:
                pts = res.pose_landmarks[0]
                xy[k, :, 0] = [p.x * info.width for p in pts]
                xy[k, :, 1] = [p.y * info.height for p in pts]
                vis[k] = [p.visibility if p.visibility is not None else 1.0 for p in pts]
            if progress and k % 5 == 0:
                progress(k / n)
    reader.close()
    if progress:
        progress(1.0)
    return PoseSeries(t, xy, vis, info.fps, info.width, info.height, str(video),
                      {"model": f"mediapipe_pose_landmarker_{variant}", "start_frame": start_frame})


def draw_skeleton(frame: np.ndarray, xy: np.ndarray, vis: np.ndarray, min_vis: float = 0.5,
                  color=(80, 220, 170), low_color=(60, 60, 230)) -> np.ndarray:
    """Draw the skeleton on a BGR frame (in place). Low-confidence points are drawn red."""
    from .landmarks import SKELETON

    out = frame
    for a, b in SKELETON:
        if np.isnan(xy[a]).any() or np.isnan(xy[b]).any():
            continue
        c = color if min(vis[a], vis[b]) >= min_vis else low_color
        cv2.line(out, tuple(int(v) for v in xy[a]), tuple(int(v) for v in xy[b]), c, 2, cv2.LINE_AA)
    for i in range(11, N_LANDMARKS):
        if not np.isnan(xy[i]).any():
            c = color if vis[i] >= min_vis else low_color
            cv2.circle(out, tuple(int(v) for v in xy[i]), 4, c, -1, cv2.LINE_AA)
    return out
