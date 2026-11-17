"""Whole-body pose with RTMPose (Halpe-26 keypoints incl. heels and toes) + YOLOX person detection,
via rtmlib (Apache-2.0, ONNX Runtime). Chosen over MediaPipe after testing on our side-view recordings:
MediaPipe misplaced hips/knees on loose light trousers, while RTMPose localised knees, heels and toes.

Target tracking: every frame may contain several people (bystanders walk behind the stairs). The
participant is initialised as the largest, most confident person in the first frames, then followed by
choosing, in each frame, the detection whose hip centre and size are closest to the previous ones.
Frames where the target is not found are left empty (NaN) - never filled with another person.

Output is a PoseSeries in the MediaPipe 33-landmark layout so the rest of the pipeline is unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np

from .landmarks import N_LANDMARKS, PoseSeries
from .paths import models_dir
from .video import FrameReader

# Halpe26 index -> MediaPipe-33 index
HALPE_TO_MP = {0: 0, 5: 11, 6: 12, 7: 13, 8: 14, 9: 15, 10: 16, 11: 23, 12: 24, 13: 25, 14: 26, 15: 27, 16: 28,
               24: 29, 25: 30, 20: 31, 21: 32}
MODELS = {
    "balanced": ("https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_m_8xb8-300e_humanart-c2c7a14a.zip",
                 "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-m_simcc-body7_pt-body7-halpe26_700e-256x192-4d3e73dd_20230605.zip",
                 (192, 256)),
    "performance": ("https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_x_8xb8-300e_humanart-a39d44ed.zip",
                    "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-x_simcc-body7_pt-body7-halpe26_700e-384x288-7fb6e239_20230606.zip",
                    (288, 384)),
    "lightweight": ("https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_tiny_8xb8-300e_humanart-6f3252f9.zip",
                    "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-s_simcc-body7_pt-body7-halpe26_700e-256x192-7f134165_20230605.zip",
                    (192, 256)),
}
DET_SIZE = {"balanced": (640, 640), "performance": (640, 640), "lightweight": (416, 416)}


def _fetch(url: str) -> str:
    """Download and unzip an ONNX model into models/rtmpose (once). Returns the .onnx path."""
    import io
    import urllib.request
    import zipfile

    dest = models_dir() / "rtmpose"
    dest.mkdir(parents=True, exist_ok=True)
    stem = Path(url).stem
    cached = list(dest.glob(f"{stem}*.onnx"))
    if cached:
        return str(cached[0])
    try:
        data = urllib.request.urlopen(url, timeout=120).read()
    except OSError as e:
        raise RuntimeError(f"Could not download the pose model ({url}). Internet is needed once.") from e
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        onnx = [n for n in z.namelist() if n.endswith(".onnx")][0]
        out = dest / f"{stem}.onnx"
        out.write_bytes(z.read(onnx))
    return str(out)


def best_device() -> str:
    try:
        import onnxruntime as ort
    except ImportError:
        return "cpu"
    prov = ort.get_available_providers()
    if "CUDAExecutionProvider" in prov:
        return "cuda"
    return "cpu"  # CoreML is available on Macs but was slower/unstable for these models in testing


_CACHE: dict = {}


def detector(mode: str = "balanced", device: str | None = None):
    """Callable frame -> (keypoints (P,26,2), scores (P,26)). Cached per (mode, device)."""
    from rtmlib import BodyWithFeet

    device = device or best_device()
    key = (mode, device)
    if key not in _CACHE:
        det_url, pose_url, pose_size = MODELS[mode]
        try:
            _CACHE[key] = BodyWithFeet(det=_fetch(det_url), det_input_size=DET_SIZE[mode], pose=_fetch(pose_url),
                                       pose_input_size=pose_size, backend="onnxruntime", device=device)
        except Exception:
            if device != "cpu":  # reliable CPU fallback
                return detector(mode, "cpu")
            raise
    return _CACHE[key]


def _bbox(k):
    return np.array([k[:, 0].min(), k[:, 1].min(), k[:, 0].max(), k[:, 1].max()])


def select_target(kps: np.ndarray, scores: np.ndarray, prev: dict | None, img_w: int, img_h: int):
    """Pick the participant among detections. Returns index or None."""
    if len(kps) == 0:
        return None
    cand = []
    for i, (k, s) in enumerate(zip(kps, scores)):
        good = s > 0.3
        if good.sum() < 8:
            continue
        b = _bbox(k[good])
        h = b[3] - b[1]
        hip = np.nanmean(k[[11, 12]], axis=0)
        if prev is None:
            cand.append((h * float(np.mean(s)), i))
        else:
            d = np.linalg.norm(hip - prev["hip"]) / max(prev["h"], 1)
            dh = abs(h - prev["h"]) / max(prev["h"], 1)
            if d < 0.6 and dh < 0.5:  # plausible frame-to-frame motion of the same person
                cand.append((-(d + dh), i))
    if not cand:
        return None
    return max(cand)[1]


def estimate(video: str | Path, start_frame: int = 0, end_frame: int | None = None, mode: str = "balanced",
             stride: int = 1, progress: Callable[[float], None] | None = None,
             cancelled: Callable[[], bool] | None = None, device: str | None = None) -> PoseSeries:
    """Track the participant's 2D keypoints in frames [start_frame, end_frame) (every ``stride``-th frame)."""
    from .pose import Cancelled

    det = detector(mode, device)
    reader = FrameReader(video)
    info = reader.info
    end = info.n_frames if end_frame is None else min(end_frame, info.n_frames)
    if end - start_frame < 2:
        raise ValueError("Analysis interval must contain at least 2 frames.")
    idx = np.arange(start_frame, end, stride)
    n = len(idx)
    xy = np.full((n, N_LANDMARKS, 2), np.nan)
    vis = np.zeros((n, N_LANDMARKS))
    nper = np.zeros(n, int)
    prev = None
    lost = 0
    k_out = 0
    for i, frame in reader.iter_range(start_frame, end):
        if (i - start_frame) % stride:
            continue
        if cancelled and cancelled():
            reader.close()
            raise Cancelled()
        kps, sc = det(frame)
        nper[k_out] = len(kps)
        j = select_target(kps, sc, prev if lost < 15 else None, info.width, info.height)
        if j is not None:
            k, s = kps[j], sc[j]
            for h_i, m_i in HALPE_TO_MP.items():
                xy[k_out, m_i] = k[h_i]
                vis[k_out, m_i] = s[h_i]
            good = s > 0.3
            b = _bbox(k[good]) if good.sum() >= 2 else _bbox(k)
            prev = {"hip": np.nanmean(k[[11, 12]], axis=0), "h": b[3] - b[1]}
            lost = 0
        else:
            lost += 1
        k_out += 1
        if progress and k_out % 5 == 0:
            progress(k_out / n)
    reader.close()
    if progress:
        progress(1.0)
    t = idx[:k_out] / info.fps
    ps = PoseSeries(t, xy[:k_out], vis[:k_out], info.fps / stride, info.width, info.height, str(video),
                    {"model": f"rtmpose_halpe26_{mode}", "start_frame": start_frame, "stride": stride,
                     "people_per_frame_max": int(nper[:k_out].max()) if k_out else 0})
    return ps
