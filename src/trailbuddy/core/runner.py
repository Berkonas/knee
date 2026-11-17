"""Run a complete trial analysis for one- or two-camera trials (used by the app and the CLI).

Pose results are cached per camera in the trial folder (pose_<cam>.csv + pose_<cam>.json), so
re-running with different biomechanical settings does not repeat pose estimation.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from . import analysis, kinematics as kmod, pose as pose_mod, sync, triangulation as dlt
from .analysis import AnalysisSettings, TrialResult
from .forces import ForceData, load_force_csv
from .landmarks import PoseSeries, idx
from .pole import PoleTrack  # noqa: F401
from .video import probe

Progress = Callable[[float, str], None]


def cached_pose(video: str, out_dir: Path, cam: str, start_s: float, end_s: float, variant: str,
                progress: Progress | None = None, cancelled=None) -> PoseSeries:
    info = probe(video)
    f0 = max(0, int(round(start_s * info.fps)))
    f1 = min(info.n_frames, int(round(end_s * info.fps)) + 1)
    key = {"video": str(Path(video).resolve()), "start_frame": f0, "end_frame": f1, "model": variant,
           "mtime": Path(video).stat().st_mtime}
    meta_p, csv_p = out_dir / f"pose_{cam}.json", out_dir / f"pose_{cam}.csv"
    if meta_p.exists() and csv_p.exists():
        try:
            if json.loads(meta_p.read_text()) == key:
                return PoseSeries.from_dataframe(pd.read_csv(csv_p), info.fps, info.width, info.height, video)
        except (ValueError, KeyError):
            pass
    cb = (lambda f: progress(f, f"Tracking pose ({cam})")) if progress else None
    ps = pose_mod.estimate(video, f0, f1, variant, progress=cb, cancelled=cancelled)
    out_dir.mkdir(parents=True, exist_ok=True)
    ps.to_dataframe().to_csv(csv_p, index=False, float_format="%.3f")
    meta_p.write_text(json.dumps(key))
    return ps


def frontal_projection_angle(ps: PoseSeries, side: str) -> np.ndarray:
    """Knee frontal-plane projection angle (deg) from a frontal camera: 180 - hip-knee-ankle angle."""
    return 180.0 - kmod.interior_angle(ps.point(side, "hip"), ps.point(side, "knee"), ps.point(side, "ankle"))


def load_dlt_csv(path: str | Path):
    """Calibration CSV columns: X_m, Y_m, Z_m, uA, vA, uB, vB (one row per control point)."""
    df = pd.read_csv(path)
    need = ["X_m", "Y_m", "Z_m", "uA", "vA", "uB", "vB"]
    miss = [c for c in need if c not in df]
    if miss:
        raise ValueError(f"Calibration file is missing columns: {', '.join(miss)}")
    X = df[["X_m", "Y_m", "Z_m"]].to_numpy(float)
    La = dlt.calibrate(X, df[["uA", "vA"]].to_numpy(float))
    Lb = dlt.calibrate(X, df[["uB", "vB"]].to_numpy(float))
    err = (dlt.reprojection_error(La, X, df[["uA", "vA"]].to_numpy(float)),
           dlt.reprojection_error(Lb, X, df[["uB", "vB"]].to_numpy(float)))
    return La, Lb, err


def knee_flexion_3d(La, Lb, pa: PoseSeries, pb_on_a: np.ndarray, side: str) -> np.ndarray:
    """3D knee flexion from DLT reconstruction. pb_on_a: camera-B landmarks resampled to A's time."""
    pts = {}
    for nm in ("hip", "knee", "ankle"):
        i = idx(side, nm)
        pts[nm] = dlt.reconstruct([La, Lb], [pa.xy[:, i], pb_on_a[:, i]])
    return 180.0 - kmod.interior_angle(pts["hip"], pts["knee"], pts["ankle"])


def run_trial(project, trial, settings: AnalysisSettings, poles: dict[str, PoleTrack] | None = None,
              variant: str = "full", progress: Progress | None = None, cancelled=None) -> TrialResult:
    if not trial.videos:
        raise ValueError("This trial has no video.")
    part = project.participant(trial.participant_id)
    cond = project.condition(trial.condition_code)
    out = project.trial_dir(trial.id)
    va = trial.videos[0].path
    ia = probe(va)
    start, end = trial.interval or [0.0, ia.duration]
    two = len(trial.videos) > 1
    def sub(lo, hi):
        if progress is None:
            return None
        return lambda f, msg: progress(lo + (hi - lo) * f, msg)
    pa = cached_pose(va, out, "A", start, end, variant, sub(0, 0.5 if two else 0.9), cancelled)
    if pa.detection_rate() < 0.2:
        raise ValueError(f"A person was detected in only {100 * pa.detection_rate():.0f}% of frames. Check that the "
                         "whole body is visible and well lit, shorten the interval to the descent, or try the "
                         "'Heavy' pose model.")

    forces: ForceData | None = None
    fpath = trial.settings.get("force_csv")
    if fpath:
        forces = load_force_csv(fpath)
    if trial.stair.get("step_height_m") and trial.stair.get("n_steps") and settings.descent_height_m is None:
        settings.descent_height_m = float(trial.stair["step_height_m"]) * int(trial.stair["n_steps"])

    res = analysis.analyse(pa, part.body_mass_kg, part.height_m, settings, cond.uses_poles, poles, forces,
                           part.segments)

    if two:
        vb = trial.videos[1].path
        ib = probe(vb)
        off = float(trial.sync.get("offset_s", 0.0))
        b0, b1 = max(0.0, start - off), min(ib.duration, end - off)
        if b1 - b0 < 0.2:
            res.notes.append("Camera B does not overlap the analysis window after sync; skipped.")
        else:
            pb = cached_pose(vb, out, "B", b0, b1, variant, sub(0.5, 0.9), cancelled)
            ta = res.timeseries["time_s"].to_numpy()
            xy_b = sync.resample_to(pb.t + off, pb.xy, ta)
            vis_b = sync.resample_to(pb.t + off, pb.visibility, ta)
            pb_a = PoseSeries(ta, xy_b, np.nan_to_num(vis_b), ia.fps, ib.width, ib.height, vb)
            role_b = trial.videos[1].role
            kb = kmod.compute(pb_a, None, settings.cutoff_hz, settings.max_gap_s, settings.min_visibility)
            for s in ("left", "right"):
                res.timeseries[f"camB_{s}_knee_flexion_deg"] = kb.angles[f"{s}_knee_flexion"]
                if role_b == "front":
                    res.timeseries[f"camB_{s}_knee_fppa_deg"] = frontal_projection_angle(pb_a, s)
            res.quality["camB_detection_rate"] = pb.detection_rate()
            res.notes.append(f"Camera B ({role_b}) synchronised with offset {off:+.3f} s "
                             f"({trial.sync.get('method', 'unknown')}); its 2D angles are projections "
                             "onto a different image plane and are not interchangeable with camera A.")
            cal = trial.settings.get("dlt_csv")
            if cal:
                La, Lb, err = load_dlt_csv(cal)
                for s in ("left", "right"):
                    res.timeseries[f"{s}_knee_flexion_3d_deg"] = knee_flexion_3d(La, Lb, pa, xy_b, s)
                res.quality["dlt_reprojection_px"] = list(err)
                res.notes.append("3D knee flexion from DLT reconstruction: calibrated but NOT validated "
                                 f"(reprojection error A {err[0]:.1f} px, B {err[1]:.1f} px).")
    if progress:
        progress(0.95, "Saving results")
    analysis.save_result(res, out, {"trial": trial.id, "participant": part.id, "condition": cond.code,
                                    "videos": [asdict(v) for v in trial.videos], "sync": trial.sync,
                                    "interval": [start, end], "pose_model": variant})
    trial.settings.update({k: v for k, v in asdict(settings).items()})
    trial.interval = [start, end]
    trial.status = "analysed"
    project.save()
    if progress:
        progress(1.0, "Done")
    return res


# =============================================================================================
# v2: paired front/side trials using the per-recording cache (core.pipeline)
# =============================================================================================

def video_by_role(trial, role: str):
    for v in trial.videos:
        if v.role == role:
            return v
    return None


def run_pair(project, trial, settings: AnalysisSettings, proc: dict | None = None,
             progress: Progress | None = None, cancelled=None) -> TrialResult:
    """Analyse a trial with a side view (sagittal kinetics/kinematics) and/or a front view (frontal measures).

    Sync convention: trial.sync['offset_s'] = t_side - t_front for the same instant.
    The analysis interval trial.interval is expressed on the side-camera clock (front clock if no side view).
    """
    from . import frontal, pipeline
    from .pole import ManualAnnotations

    proc = proc or {}
    cache = Path(project.root) / "cache"
    side_v, front_v = video_by_role(trial, "side"), video_by_role(trial, "front")
    if side_v is None and front_v is None:
        raise ValueError("This trial has no side or front recording.")
    part = project.participant(trial.participant_id)
    cond = project.condition(trial.condition_code)
    out = project.trial_dir(trial.id)
    off = float(trial.sync.get("offset_s", 0.0))

    def sub(lo, hi):
        return (lambda f, m: progress(lo + (hi - lo) * f, m)) if progress else None

    side_data = pipeline.process_recording(side_v.path, cache, proc, sub(0, 0.45), cancelled) if side_v else None
    front_data = pipeline.process_recording(front_v.path, cache, proc, sub(0.45, 0.9), cancelled) if front_v else None
    if progress:
        progress(0.92, "Computing biomechanics")
    ref = side_data or front_data
    pose_full = ref[0]
    from .events import descent_window
    if trial.interval:
        t0, t1 = trial.interval
    else:
        # default: the automatically detected descent (hip height falling), limited to the common window
        win = descent_window(pose_full)
        t0, t1 = (win[0], win[1]) if win else (float(pose_full.t[0]), float(pose_full.t[-1]))
        trial.settings["interval_method"] = "auto: hip descent" if win else "whole recording (no clear descent)"
        if side_data and front_data:
            f_t = front_data[0].t + off  # front clock -> side clock
            t0, t1 = max(t0, float(f_t[0])), min(t1, float(f_t[-1]))
    forces = load_force_csv(trial.settings["force_csv"]) if trial.settings.get("force_csv") else None
    if trial.stair.get("step_height_m") and trial.stair.get("n_steps") and settings.descent_height_m is None:
        settings.descent_height_m = float(trial.stair["step_height_m"]) * int(trial.stair["n_steps"])
    if side_data:
        pose_s = pipeline.slice_pose(side_data[0], t0, t1)
        poles_s = {k: pipeline.slice_track(v, t0, t1) for k, v in side_data[1].items()}
        man = out / "poles_manual.json"
        if man.exists():
            ann = ManualAnnotations.load(man)
            f0 = int(round(pose_s.t[0] * side_data[0].fps * pose_s.meta.get("stride", 1)))
            for s_ in ("left", "right"):
                if ann.points.get(s_, {}).get("tip"):
                    m_tr = ann.to_track(s_, pose_s.t, f0)
                    a = poles_s.get(s_)
                    if a is not None:  # manual points override automatic ones frame by frame
                        tip = np.where(np.isfinite(m_tr.tip), m_tr.tip, a.tip)
                        src = np.where(np.isfinite(m_tr.tip[:, 0]), m_tr.source, a.source)
                        conf = np.where(np.isfinite(m_tr.tip[:, 0]), m_tr.confidence, a.confidence)
                        poles_s[s_] = PoleTrack(pose_s.t, tip, None, conf, src, "auto+manual")
                    else:
                        poles_s[s_] = m_tr
        detected = pipeline.pole_present(poles_s)
        trial.settings["poles_detected"] = bool(detected)
        if cond.code == "UNSET" and not detected:
            res_note_cond = "No poles were detected in the side view: this looks like a no-poles trial."
        elif cond.code == "UNSET":
            res_note_cond = "Poles detected: assign the condition (standard / shorter / longer) on the Trial tab."
        else:
            res_note_cond = ""
        uses = (cond.uses_poles and cond.code != "UNSET") or detected
        res = analysis.analyse(pose_s, part.body_mass_kg, part.height_m, settings, uses, poles_s, forces,
                               part.segments)
        if detected and not cond.uses_poles:
            res.notes.append("Poles were detected although the condition says 'no poles': check the condition.")
        if res_note_cond:
            res.notes.insert(0, res_note_cond)
    else:
        pose_f0 = pipeline.slice_pose(front_data[0], t0, t1)
        res = analysis.analyse(pose_f0, part.body_mass_kg, part.height_m,
                               AnalysisSettings(scale_method="none", side=settings.side), cond.uses_poles, None)
        from .metrics import MetricValue
        res.metrics = [MetricValue(m.key, None, "unavailable", "Needs a side-view recording (sagittal measure).")
                       for m in res.metrics]
        keep = ["time_s"]
        res.timeseries = res.timeseries[keep]
        res.notes.append("Front view only: sagittal angles, timing and kinetics need the side view and are not "
                         "reported. Front-view (frontal-plane) measures are below.")
    if front_data:
        fa, fb = (t0 - off, t1 - off) if side_data else (t0, t1)
        pose_f = pipeline.slice_pose(front_data[0], fa, fb)
        poles_f = {k: pipeline.slice_track(v, fa, fb) for k, v in front_data[1].items()}
        fdf, fm, fq = frontal.analyse_front(pose_f, poles_f, settings.cutoff_hz, settings.min_visibility)
        for m in fm:
            m.view = "front"
        ts = res.timeseries
        tt = ts["time_s"].to_numpy()
        f_time = fdf["time_s"].to_numpy() + (off if side_data else 0.0)
        for c in fdf.columns:
            if c != "time_s":
                ts[c] = sync.resample_to(f_time, fdf[c].to_numpy(), tt)
        res.metrics.extend(fm)
        res.quality.update(fq)
    if not front_data:
        for k in ("front_knee_fppa_peak", "front_trunk_lateral_lean_rom", "front_pelvic_obliquity_rom",
                  "front_step_width_ratio_mean", "front_pole_tip_spread_mean"):
            from .metrics import MetricValue
            res.metrics.append(MetricValue(k, None, "unavailable", "No front-view recording for this trial.", view="front"))
    if not part.metrics_entered:
        res.notes.insert(0, "Body mass/height are placeholder values: enter real body metrics before using any "
                         "force or moment.")
    res.quality["sync_offset_s"] = off if (side_data and front_data) else None
    res.quality["processing"] = {"pose": (proc or {}).get("backend", "rtmpose"), "mode": (proc or {}).get("mode", "balanced"),
                                 "stride": (proc or {}).get("stride", 1)}
    analysis.save_result(res, out, {"trial": trial.id, "participant": part.id, "condition": cond.code,
                                    "videos": [asdict(v) for v in trial.videos], "sync": trial.sync,
                                    "interval": [t0, t1], "processing": proc})
    trial.interval = [t0, t1]
    trial.status = "analysed"
    project.save()
    if progress:
        progress(1.0, "Done")
    return res
