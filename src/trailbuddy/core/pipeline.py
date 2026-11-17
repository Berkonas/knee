"""Per-recording processing with an on-disk cache.

Each usable recording is processed once over its whole length:
  pose  -> <cache>/<stem>.<model>.pose.csv  (+ .json with settings and source fingerprint)
  poles -> <cache>/<stem>.<model>.poles.csv
Trial analyses then slice these caches by time, so changing an analysis interval, sync offset or
biomechanical setting never re-runs inference. A cache entry is invalidated automatically when the
video file (size, modification time) or the processing settings change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .landmarks import PoseSeries
from .pole import PoleTrack
from .video import probe

PIPELINE_VERSION = 2
POLE_VERSION = 5   # bump when the pole detector changes: poles are recomputed, cached poses are reused


def _key(video: str, settings: dict) -> dict:
    p = Path(video)
    st = p.stat()
    return {"file": p.name, "size": st.st_size, "mtime": int(st.st_mtime), "version": PIPELINE_VERSION, **settings}


def _paths(cache: Path, video: str, tag: str):
    stem = Path(video).stem
    return cache / f"{stem}.{tag}.pose.csv", cache / f"{stem}.{tag}.poles.csv", cache / f"{stem}.{tag}.json"


def _tag(settings: dict) -> str:
    return f"{settings.get('backend', 'rtmpose')}-{settings.get('mode', 'balanced')}-s{settings.get('stride', 1)}"


def _read_pose(cache: Path, video: str, settings: dict):
    pose_p, _, meta_p = _paths(cache, video, _tag(settings))
    if not (pose_p.exists() and meta_p.exists()):
        return None, None
    meta = json.loads(meta_p.read_text())
    if meta.get("key") != _key(video, settings):
        return None, None
    info = probe(video)
    pose = PoseSeries.from_dataframe(pd.read_csv(pose_p), meta["fps"], info.width, info.height, video)
    pose.meta.update(meta.get("pose_meta", {}))
    return pose, meta


def _read_poles(cache: Path, video: str, settings: dict, meta: dict):
    _, poles_p, _ = _paths(cache, video, _tag(settings))
    if not poles_p.exists() or meta.get("pole_version") != POLE_VERSION:
        return None
    df = pd.read_csv(poles_p)
    poles = {}
    for s in ("left", "right"):
        if f"{s}_tip_x" in df:
            poles[s] = PoleTrack(df.time_s.to_numpy(), df[[f"{s}_tip_x", f"{s}_tip_y"]].to_numpy(), None,
                                 df[f"{s}_conf"].to_numpy(), df[f"{s}_src"].to_numpy().astype(int), "auto_wrist_segment")
    return poles


def load_cached(cache: str | Path, video: str, settings: dict):
    """(pose, poles, meta) when both are cached and current, else None."""
    try:
        pose, meta = _read_pose(Path(cache), video, settings)
        if pose is None:
            return None
        poles = _read_poles(Path(cache), video, settings, meta)
        if poles is None:
            return None
        return pose, poles, meta
    except Exception:
        return None


def process_recording(video: str, cache: str | Path, settings: dict | None = None,
                      progress: Callable[[float, str], None] | None = None, cancelled=None):
    """Pose + pole tracking over the full recording (cached; poses and poles are cached separately)."""
    from . import pole_auto, pose_rtm

    settings = {"backend": "rtmpose", "mode": "balanced", "stride": 1, **(settings or {})}
    cache = Path(cache)
    hit = load_cached(cache, video, settings)
    if hit is not None:
        if progress:
            progress(1.0, "Loaded from cache")
        return hit
    cache.mkdir(parents=True, exist_ok=True)
    name = Path(video).name

    def p(lo, hi, msg):
        return (lambda f: progress(lo + (hi - lo) * f, msg)) if progress else None

    try:
        pose, meta = _read_pose(cache, video, settings)
    except Exception:
        pose, meta = None, None
    if pose is None:
        if settings["backend"] == "mediapipe":
            from . import pose as mp_pose
            pose = mp_pose.estimate(video, 0, None, "full", progress=p(0, 0.8, f"Tracking body in {name}"),
                                    cancelled=cancelled)
            pose.meta["stride"] = 1
        else:
            pose = pose_rtm.estimate(video, 0, None, settings["mode"], settings["stride"],
                                     progress=p(0, 0.8, f"Tracking body in {name}"), cancelled=cancelled)
        meta = {"key": _key(video, settings), "fps": pose.fps, "pose_meta": pose.meta,
                "detection_rate": pose.detection_rate()}
        pose_p, _, _ = _paths(cache, video, _tag(settings))
        pose.to_dataframe().to_csv(pose_p, index=False, float_format="%.2f")
    poles = pole_auto.track_poles(video, pose, 0, progress=p(0.8, 1.0, f"Tracking poles in {name}"),
                                  cancelled=cancelled)
    _, poles_p, meta_p = _paths(cache, video, _tag(settings))
    cols = {"time_s": pose.t}
    for s, tr in poles.items():
        cols[f"{s}_tip_x"], cols[f"{s}_tip_y"] = tr.tip[:, 0], tr.tip[:, 1]
        cols[f"{s}_conf"], cols[f"{s}_src"] = tr.confidence, tr.source
    pd.DataFrame(cols).to_csv(poles_p, index=False, float_format="%.3f")
    meta.update({"pole_version": POLE_VERSION, "pole_coverage": {s: tr.coverage() for s, tr in poles.items()}})
    meta_p.write_text(json.dumps(meta, indent=1, default=str))
    return pose, poles, meta


def slice_pose(pose: PoseSeries, t0: float, t1: float) -> PoseSeries:
    m = (pose.t >= t0 - 1e-9) & (pose.t <= t1 + 1e-9)
    return PoseSeries(pose.t[m], pose.xy[m], pose.visibility[m], pose.fps, pose.width, pose.height, pose.source,
                      dict(pose.meta))


def slice_track(tr: PoleTrack, t0: float, t1: float) -> PoleTrack:
    m = (tr.t >= t0 - 1e-9) & (tr.t <= t1 + 1e-9)
    return PoleTrack(tr.t[m], tr.tip[m], None if tr.top is None else tr.top[m], tr.confidence[m], tr.source[m],
                     tr.method)


def pole_present(poles: dict[str, PoleTrack], min_coverage: float = 0.3) -> bool:
    return any(tr.coverage() >= min_coverage for tr in poles.values())


__all__ = ["process_recording", "load_cached", "slice_pose", "slice_track", "pole_present", "np"]
