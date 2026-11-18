"""Trial analysis pipeline: pose -> kinematics -> events -> kinetics -> metrics.

The function ``analyse`` is pure (no file or GUI side effects) so it can be unit tested with
synthetic landmark data. ``save_result`` writes the standard set of output files.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import dynamics as dyn
from . import kinematics as kmod
from .anthropometry import G
from .events import detect_gait, stance_mask
from .forces import ForceData
from .landmarks import PoseSeries
from .metrics import KINDS, MetricValue
from .pole import PoleTrack, pole_contacts

# Patellar tendon moment arm: in vivo ~4.8-5.9 cm (Tsaopoulos et al., 2009); cadaver peak 4-6 cm
# (Krevolin et al., 2004). Nominal 5 cm with a 4-6 cm sensitivity range.
MOMENT_ARM_NOMINAL_M = 0.05
MOMENT_ARM_RANGE_M = (0.04, 0.06)


@dataclass
class AnalysisSettings:
    side: str = "auto"                    # 'auto' | 'left' | 'right'
    cutoff_hz: float = 6.0
    min_visibility: float = 0.5
    max_gap_s: float = 0.1
    scale_method: str = "height"          # 'height' | 'points' | 'none'
    scale_m_per_px: float | None = None   # used when scale_method == 'points'
    contact_rel_threshold: float = 0.2
    contact_min_duration_s: float = 0.12
    support_model: str = "static"         # 'static' (m*g) | 'dynamic' (m*(g+a_COM))
    cop_fraction: float = 0.5             # assumed COP position heel(0) -> toe(1)
    grf_direction: str = "com"            # 'com' (COP -> whole-body COM) | 'vertical' (alternative assumption)
    # Mode A 'video': kinematics only, no forces or moments.  Mode B 'scenario': assumption-based loads.
    # Mode C 'measured': loads from imported force data (force plate, insoles, pole load cells).
    load_mode: str = "video"
    use_scale_pole_force: bool = True        # scenario pole force from the participant's scale test when entered
    scale_reading_is_both_poles: bool = False  # True if the scale test pressed both poles at once
    moment_arm_m: float = MOMENT_ARM_NOMINAL_M
    moment_arm_range_m: tuple[float, float] = MOMENT_ARM_RANGE_M
    pole_force_mode: str = "none"         # 'none' | 'scenario' | 'measured'
    pole_pct_bw: float = 10.0             # scenario: axial force per planted pole, % BW
    force_offset_s: float = 0.0           # t_video = t_force + offset
    plate_origin_x_m: float | None = None  # lab-frame x of the plate COP origin
    descent_height_m: float | None = None  # vertical height descended in the window


@dataclass
class TrialResult:
    timeseries: pd.DataFrame
    metrics: list[MetricValue]
    events: pd.DataFrame
    sensitivity: pd.DataFrame
    quality: dict
    side: str
    settings: dict
    notes: list[str] = field(default_factory=list)

    def metric(self, key: str) -> MetricValue | None:
        return next((m for m in self.metrics if m.key == key), None)

    def summary_table(self) -> pd.DataFrame:
        cols = ["key", "label", "value", "sd", "low", "high", "unit", "evidence", "view", "note"]
        return pd.DataFrame([m.as_row() for m in self.metrics])[cols]


def _peak(y: np.ndarray, mask: np.ndarray | None = None) -> float | None:
    v = y[mask] if mask is not None else y
    v = v[~np.isnan(v)]
    return float(v.max()) if len(v) else None


LOAD_MODES = {"video": "A · Video-only kinematics", "scenario": "B · Assumption-based scenario",
              "measured": "C · Measured forces"}


def analyse(pose: PoseSeries, body_mass: float | None, height_m: float | None, settings: AnalysisSettings,
            uses_poles: bool = False, poles: dict[str, PoleTrack] | None = None,
            forces: ForceData | None = None, segments: dict | None = None, emg=None) -> TrialResult:
    s = settings
    notes: list[str] = []
    poles = poles or {}

    # ---- scale & kinematics -------------------------------------------------------------
    scale = None
    if s.scale_method == "points" and s.scale_m_per_px:
        scale = s.scale_m_per_px
        notes.append("Scale from a measured calibration distance in the scene.")
    elif s.scale_method == "height" and height_m is None:
        notes.append("No scale: the participant's height is not entered, so distances stay in pixels.")
    elif s.scale_method == "height":
        seg = segments or {}
        scale = kmod.scale_from_height(pose, height_m, thigh_m=seg.get("thigh_m"), shank_m=seg.get("shank_m"))
        if seg.get("thigh_m") and seg.get("shank_m"):
            notes.append("Scale from the participant's measured thigh + shank length (approximate: depends on "
                         "how well hip/knee/ankle landmarks match the tape-measure landmarks).")
        else:
            notes.append("Scale estimated from body height and Winter leg-segment proportions "
                         "(approximate, +-5-10%). Measured segment lengths or a distance in the scene is better.")
    else:
        notes.append("No scale: distances in pixels; speed and all kinetics are unavailable.")
    kin = kmod.compute(pose, scale, s.cutoff_hz, s.max_gap_s, s.min_visibility)
    side = kmod.best_side(kin) if s.side == "auto" else s.side
    t = kin.t
    n = len(t)
    gait = detect_gait(kin, s.contact_rel_threshold, s.contact_min_duration_s)
    stance = stance_mask(t, gait.contacts.get(side, []))
    quality: dict = {}
    if not stance.any():
        notes.append(f"No stance phase detected for the {side} foot; kinetics need foot contacts.")

    if body_mass is None:
        kin_block = "Needs this participant's measured body mass (Body metrics…)."
    elif scale is None:
        kin_block = "Needs a metric scale (participant height, segment lengths or a calibrated distance)."
    elif s.load_mode == "video":
        kin_block = "Video-only mode (A): forces and moments are not estimated. Choose mode B (scenario) or C (measured)."
    elif s.load_mode == "measured" and forces is None:
        kin_block = "Measured-force mode (C) needs an imported force file."
    else:
        kin_block = None
    quality["load_mode"] = s.load_mode
    notes.append(f"Load analysis mode: {LOAD_MODES.get(s.load_mode, s.load_mode)}.")

    stride = int(pose.meta.get("stride", 1) or 1)
    ts = {"time_s": t, "frame_index": np.round(t * pose.fps * stride).astype(int)}  # source-video frame number
    for k, v in kin.angles.items():
        ts[f"{k}_deg"] = v
    ts[f"{side}_stance"] = stance.astype(int)
    other_side = "left" if side == "right" else "right"
    ts[f"{other_side}_stance"] = stance_mask(t, gait.contacts.get(other_side, [])).astype(int)
    # Raw segment-endpoint trajectories (lab frame, analysed side) for stick figures and re-analysis.
    unit = kin.units
    for nm in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle", "heel", "foot_index"):
        xy = kin.get(side, nm)
        ts[f"{side}_{nm}_x_{unit}"] = xy[:, 0]
        ts[f"{side}_{nm}_y_{unit}"] = xy[:, 1]
    for nm in ("mid_hip", "mid_shoulder"):
        ts[f"{nm}_x_{unit}"] = kin.pts[nm][:, 0]
        ts[f"{nm}_y_{unit}"] = kin.pts[nm][:, 1]

    # Segment orientation from vertical (deg; + = distal end ahead of proximal in the travel direction)
    def seg_from_vertical(prox, dist):
        v = kin.get(side, dist) - kin.get(side, prox)
        return np.degrees(np.arctan2(v[:, 0], -v[:, 1]))
    ts[f"{side}_thigh_orientation_deg"] = seg_from_vertical("hip", "knee")
    ts[f"{side}_shank_orientation_deg"] = seg_from_vertical("knee", "ankle")
    ts[f"{side}_upper_arm_orientation_deg"] = seg_from_vertical("shoulder", "elbow")
    ts[f"{side}_forearm_orientation_deg"] = seg_from_vertical("elbow", "wrist")
    for j in ("knee_flexion", "hip_flexion", "ankle_dorsiflexion", "elbow_flexion", "shoulder_flexion"):
        ts[f"{side}_{j}_velocity_dps"] = np.gradient(kin.angles[f"{side}_{j}"], 1.0 / kin.fs)

    M: list[MetricValue] = []
    a = kin.angles
    kf = a[f"{side}_knee_flexion"]
    M.append(MetricValue("knee_flexion_peak", _peak(kf, stance if stance.any() else None), "video",
                         f"{side} leg"))
    M.append(MetricValue("knee_flexion_rom", float(np.nanmax(kf) - np.nanmin(kf)) if np.isfinite(kf).any() else None,
                         "video", f"{side} leg"))
    kf_vel = -np.gradient(np.radians(kf), 1.0 / kin.fs)  # extension velocity, rad/s
    if stance.any() and np.isfinite(kf[stance]).any():
        first = [c.start_i for c in gait.contacts.get(side, []) if c.start_i > 0]
        M.append(MetricValue("knee_flexion_at_contact",
                             float(np.nanmean(kf[first])) if first else None, "video",
                             f"{side} leg, mean of {len(first)} contacts" if first else "No foot strike in window."))
        M.append(MetricValue("knee_flexion_velocity_peak", float(np.degrees(np.nanmax(-kf_vel[stance]))), "video",
                             "fastest knee flexion while loaded (controlled lowering)"))
    else:
        M.append(MetricValue("knee_flexion_at_contact", None, "unavailable", "Needs foot contacts."))
        M.append(MetricValue("knee_flexion_velocity_peak", None, "unavailable", "Needs foot contacts."))
    M.append(MetricValue("hip_flexion_peak", _peak(a[f"{side}_hip_flexion"], stance if stance.any() else None),
                         "video", f"{side} leg"))
    M.append(MetricValue("ankle_dorsiflexion_peak", _peak(a[f"{side}_ankle_dorsiflexion"], stance if stance.any() else None),
                         "video", f"{side} leg"))
    M.append(MetricValue("trunk_lean_mean", float(np.nanmean(a["trunk_lean"])), "video"))
    M.append(MetricValue("shoulder_flexion_peak", _peak(a[f"{side}_shoulder_flexion"]), "video", f"{side} arm"))
    M.append(MetricValue("elbow_flexion_mean", float(np.nanmean(a[f"{side}_elbow_flexion"])), "video", f"{side} arm"))
    M.append(MetricValue("speed", kmod.walking_speed(kin), "video" if scale else "unavailable",
                         "" if scale else "Needs a scale."))
    M.append(MetricValue("cadence", gait.cadence_steps_per_min(side), "video", f"from {side} foot strides"))
    sr = gait.stride_times(side)
    st = sr / 2.0 if len(sr) else gait.step_times()
    M.append(MetricValue("step_time_mean", float(st.mean()) if len(st) else None, "video",
                         sd=float(st.std(ddof=1)) if len(st) > 1 else None))
    M.append(MetricValue("step_time_cv", float(100 * st.std(ddof=1) / st.mean()) if len(st) > 2 else None,
                         "video" if len(st) > 2 else "unavailable", "" if len(st) > 2 else "Needs at least 3 steps."))
    sd_ = gait.stance_durations(side, t[0], t[-1])
    M.append(MetricValue("stance_time_mean", float(sd_.mean()) if len(sd_) else None, "video",
                         "" if len(sd_) else "No complete stance in window.",
                         sd=float(sd_.std(ddof=1)) if len(sd_) > 1 else None))

    # ---- poles ----------------------------------------------------------------------------
    hand_px = {sd: pose.point(sd, "wrist") for sd in ("left", "right")}
    pole_dirs, pole_contact, ev_rows = {}, {}, []
    for pside, tr in poles.items():
        if tr is None or tr.coverage() == 0:
            continue
        ang = tr.angle_from_vertical_deg(hand_px[pside]) * kin.direction
        ts[f"pole_{pside}_angle_deg"] = ang
        ts[f"pole_{pside}_tracking_conf"] = tr.confidence
        # pole relative to the forearm (deg between the forearm direction and the pole axis)
        fa = kin.get(pside, "wrist") - kin.get(pside, "elbow")
        fa_ang = np.degrees(np.arctan2(fa[:, 0], fa[:, 1]))  # lab frame: y up -> from 'down'... use image-equivalent
        ts[f"pole_{pside}_minus_forearm_deg"] = np.abs(((ang - (-np.degrees(np.arctan2(fa[:, 0], -fa[:, 1]))) + 180) % 360) - 180)
        del fa_ang
        ts[f"pole_{pside}_tip_source"] = tr.source
        tip_lab = kmod.to_lab(tr.tip, pose.height, kin.direction, scale)
        if scale:
            ts[f"pole_{pside}_tip_x_m"], ts[f"pole_{pside}_tip_y_m"] = tip_lab[:, 0], tip_lab[:, 1]
        hand_lab = dyn.grip_point(kin, pside)
        d, assumed = dyn.pole_direction(hand_lab, tip_lab, n)
        if assumed:
            notes.append(f"{pside} pole tip missing in most frames: pole direction not used (would be assumed vertical).")
        else:
            pole_dirs[pside] = d
        ivs = pole_contacts(tr, s.contact_rel_threshold, s.contact_min_duration_s)
        if ivs is None:
            notes.append(f"{pside} pole tracking covers <50% of frames; pole contacts not estimated.")
            continue
        if not ivs:
            notes.append(f"No {pside} pole-tip contacts detected (tip never stationary).")
        pole_contact[pside] = stance_mask(t, ivs)
        ts[f"pole_{pside}_contact"] = pole_contact[pside].astype(int)
        for c in ivs:
            ev_rows.append({"event": f"pole_{pside}_contact", "start_s": c.start_s, "end_s": c.end_s,
                            "duration_s": c.duration, "angle_at_contact_deg": float(ang[c.start_i])})
    plant_rows = [r for r in ev_rows if r["event"].startswith("pole")]
    # coordination: pole plant relative to the nearest foot strike of the analysed leg (s; + = pole after foot)
    strikes = np.array([c.start_s for c in gait.contacts.get(side, []) if c.start_i > 0])
    leads = []
    for r in plant_rows:
        if len(strikes):
            d = r["start_s"] - strikes
            leads.append(float(d[np.argmin(np.abs(d))]))
    if plant_rows:
        dur = np.array([r["duration_s"] for r in plant_rows])
        angs = np.array([r["angle_at_contact_deg"] for r in plant_rows])
        M.append(MetricValue("pole_contact_time", float(dur.mean()), "video", "awaiting validation",
                             sd=float(dur.std(ddof=1)) if len(dur) > 1 else None))
        M.append(MetricValue("pole_angle_at_contact", float(np.nanmean(angs)), "video", "awaiting validation"))
        M.append(MetricValue("pole_plant_timing", float(np.mean(leads)) if leads else None,
                             "video" if leads else "unavailable",
                             "+ = pole plants after the foot lands" if leads else "Needs foot strikes and pole plants."))
    else:
        if uses_poles:
            notes.append("Poles used but not tracked: pole timing and angles unavailable. "
                         "Correct the pole manually or adjust the pole colour range.")
        for key in ("pole_contact_time", "pole_angle_at_contact", "pole_plant_timing"):
            M.append(MetricValue(key, None, "unavailable",
                                 "Pole not tracked in the side view." if uses_poles else "No poles in this condition."))

    # ---- external forces ------------------------------------------------------------------
    pl = dyn.PoleLoad()
    fdat = forces.resample(t, s.force_offset_s, s.cutoff_hz) if forces is not None else {}
    pole_mode = s.pole_force_mode if kin_block is None else "none"
    if s.load_mode == "scenario" and pole_mode == "measured":
        pole_mode = "none"
    if s.load_mode == "measured" and pole_mode == "scenario":
        pole_mode = "none"
        notes.append("Measured-force mode: scenario pole force ignored (only measured pole forces are used).")
    if uses_poles and pole_mode == "measured" and any(k in fdat for k in ("pole_left", "pole_right")):
        pl.source = "measured"
        for pside in ("left", "right"):
            if f"pole_{pside}" in fdat:
                pl.axial_n[pside] = np.nan_to_num(fdat[f"pole_{pside}"])
                pl.direction[pside] = pole_dirs.get(pside, np.tile([0.0, 1.0], (n, 1)))
                if pside not in pole_dirs:
                    pl.direction_assumed_vertical = True
    elif uses_poles and pole_mode == "measured":
        notes.append("Measured pole force selected, but no force file with pole_left_n/pole_right_n columns was given.")
    elif uses_poles and pole_mode == "scenario":
        contact = dict(pole_contact)
        if not contact:
            contact = {side: stance}  # assume the same-side pole is planted during stance
            notes.append("Pole contact timing assumed equal to the analysed foot's stance "
                         "(no pole tracking).")
        pl = dyn.scenario_pole_load(n, body_mass, s.pole_pct_bw, contact, pole_dirs)
    if pl.direction_assumed_vertical:
        notes.append("Pole direction unknown for some frames; assumed vertical.")
    pole_vert = pl.vertical_total(n)
    if pl.source != "none":
        ts["pole_vertical_total_n"] = pole_vert
        kind = "measured" if pl.source == "measured" else "scenario"
        if kind == "measured" and (set(pl.axial_n) - set(pole_dirs)):
            kind = "model"  # measured axial force, but a pole direction assumed vertical -> not a pure measurement
        frac = 100 * pole_vert[stance].mean() / (body_mass * G) if stance.any() else None
        M.append(MetricValue("pole_support_fraction", frac, kind,
                             "" if pl.source == "measured" and kind == "measured" else
                             ("measured axial force; pole direction assumed vertical for an untracked pole"
                              if pl.source == "measured" else f"{s.pole_pct_bw:g}% BW per planted pole (assumed)")))
    else:
        why = (kin_block if uses_poles and kin_block else
               "No pole columns in the force file." if uses_poles and pole_mode == "measured" else
               "Pole force cannot be measured from video. Enter a scenario or import load-cell data."
               if uses_poles else "No poles in this condition.")
        M.append(MetricValue("pole_support_fraction", None, "unavailable", why))

    other = "left" if side == "right" else "right"
    if stance.any() and not gait.contacts.get(other):
        notes.append(f"No contacts detected for the {other} foot (often hidden in a side view): double support "
                     f"cannot be identified, so the {side} leg is assumed to carry all leg support throughout its "
                     "stance. Knee loads are an upper bound (typically ~10-20% higher impulse).")
        quality["double_support_unknown"] = True

    # ---- lower-limb kinetics ----------------------------------------------------------------
    kinetics_kind = None
    m_knee = None
    fbd = None
    measured_grf = "vertical" in fdat and s.load_mode == "measured"
    if kin_block is not None:
        notes.append(f"Joint loads not calculated: {kin_block}")
    elif s.load_mode == "measured" and not measured_grf:
        notes.append("Measured-force mode: the force file has no vertical ground reaction force (fz_n), so the "
                     "knee moment is unavailable. It is not replaced by a scenario estimate.")
    elif measured_grf:
        fv = np.nan_to_num(fdat["vertical"])
        fh = np.nan_to_num(fdat.get("horizontal", np.zeros(n)))
        loaded = fv > 20.0
        if (loaded & ~stance).sum() > 0.2 * max(1, loaded.sum()):
            notes.append(f"Force data show load outside the {side} foot's stance: another foot may be on the plate. "
                         f"Only force during the {side} stance is applied to the {side} leg.")
        # the plate's own contact decides when force acts; the video stance (widened by 3 frames, since video foot
        # strike can lag the plate by a frame or two) only decides which leg receives it
        from scipy.ndimage import binary_dilation
        apply = loaded & binary_dilation(stance, iterations=3)
        fv = np.where(apply, fv, 0.0)
        fh = np.where(apply, fh, 0.0)
        if "horizontal" not in fdat:
            notes.append("Force file has no horizontal force (fx_n): the ground reaction force is assumed vertical "
                         "in the inverse dynamics.")
        if "cop_x" in fdat and s.plate_origin_x_m is not None:
            foot_y = dyn.cop_on_foot(kin, side, 0.5)[:, 1]
            plate_y = np.nanmedian(foot_y[loaded & stance]) if (loaded & stance).any() else np.nanmedian(foot_y)
            cop = np.stack([s.plate_origin_x_m + fdat["cop_x"], np.full(n, plate_y)], axis=1)
        else:
            cop = dyn.cop_on_foot(kin, side, s.cop_fraction)
            notes.append("COP not measured/located: assumed on the foot (cop_fraction).")
        leg = dyn.inverse_dynamics_leg(kin, side, body_mass, np.stack([fh, fv], axis=1), cop)
        m_knee = leg.knee_extensor
        fbd = {"cop": cop, "grf": np.stack([fh, fv], axis=1)}
        ts[f"{side}_ankle_plantarflexor_moment_nm"] = leg.ankle_plantarflexor
        ts[f"{side}_hip_extensor_moment_nm"] = leg.hip_extensor
        ts["grf_vertical_n"] = fv
        kinetics_kind = "model"
        notes.append("Knee moment from 2D Newton-Euler inverse dynamics with measured ground reaction force.")
    elif stance.any() and s.load_mode == "scenario":
        share = dyn.leg_load_share(t, gait, side)
        support = dyn.total_support_force(kin, body_mass, s.support_model == "dynamic")
        f_foot = np.nan_to_num(share) * np.maximum(support - pole_vert, 0.0)
        cop = dyn.cop_on_foot(kin, side, s.cop_fraction)
        com = dyn.whole_body_com(kin) if s.grf_direction == "com" else None
        m_knee = dyn.quasi_static_knee(kin, side, f_foot, cop, com)
        fbd = {"cop": cop, "grf": dyn.grf_toward_com(f_foot, cop, com) if com is not None
               else np.stack([np.zeros(n), f_foot], axis=1), "com": com}
        m_knee = np.where(stance, m_knee, np.nan)
        ts[f"{side}_foot_force_scenario_n"] = f_foot
        kinetics_kind = "scenario"
        notes.append("No measured ground reaction force: knee moment from the quasi-static scenario "
                     f"model (support = {'m(g+a_COM)' if s.support_model == 'dynamic' else 'body weight'}, "
                     f"COP at {s.cop_fraction:.2f} of heel-to-toe, force directed "
                     f"{'from the COP toward the whole-body COM' if s.grf_direction == 'com' else 'vertically (alternative assumption)'}, "
                     "segment inertia neglected).")

    sens_rows = []
    if m_knee is not None and stance.any():
        valid = np.isfinite(m_knee[stance]).mean()
        if valid < 0.8:
            notes.append(f"Knee moment could be computed in only {100 * valid:.0f}% of stance frames "
                         "(missing landmarks); kinetics reported as unavailable.")
            m_knee = None
            reason_override = "Too many stance frames with missing landmarks."
    if m_knee is not None:
        ts[f"{side}_knee_extensor_moment_nm"] = m_knee
        # free-body-diagram inputs (lab frame, m and N): where and how the foot force acts
        if fbd is not None:
            cop_, grf_ = fbd["cop"], np.where(stance[:, None], fbd["grf"], np.nan)
            ts[f"{side}_cop_x_m"], ts[f"{side}_cop_y_m"] = cop_[:, 0], cop_[:, 1]
            ts[f"{side}_grf_x_n"], ts[f"{side}_grf_y_n"] = grf_[:, 0], grf_[:, 1]
            if fbd.get("com") is not None:
                ts["com_x_m"], ts["com_y_m"] = fbd["com"][:, 0], fbd["com"][:, 1]
        mk_pos = np.where(stance, np.nan_to_num(m_knee), 0.0)
        q_nom = dyn.quadriceps_force(mk_pos, s.moment_arm_m)
        q_lo = dyn.quadriceps_force(mk_pos, s.moment_arm_range_m[1])  # longer arm -> lower force
        q_hi = dyn.quadriceps_force(mk_pos, s.moment_arm_range_m[0])
        ts[f"{side}_quad_force_n"] = np.where(stance, q_nom, np.nan)
        power = dyn.joint_power(np.nan_to_num(m_knee), kf, kin.fs)
        ts[f"{side}_knee_power_w"] = np.where(stance, power, np.nan)
        pk = _peak(np.where(stance, m_knee, np.nan))
        M.append(MetricValue("knee_ext_moment_peak", pk / body_mass if pk is not None else None, kinetics_kind))
        M.append(MetricValue("knee_ext_moment_peak_nm", pk, kinetics_kind))
        M.append(MetricValue("quad_force_peak", float(q_nom.max()), kinetics_kind,
                             f"moment arm {100 * s.moment_arm_m:.1f} cm (range {100 * s.moment_arm_range_m[0]:.0f}-"
                             f"{100 * s.moment_arm_range_m[1]:.0f} cm)", low=float(q_lo.max()), high=float(q_hi.max())))
        M.append(MetricValue("quad_force_peak_bw", float(q_nom.max()) / (body_mass * G), kinetics_kind,
                             low=float(q_lo.max()) / (body_mass * G), high=float(q_hi.max()) / (body_mass * G)))
        imp = dyn.integrate(np.maximum(mk_pos, 0), t) / body_mass
        from scipy.integrate import cumulative_trapezoid
        ts[f"{side}_knee_ext_impulse_cum_nms_per_kg"] = cumulative_trapezoid(np.maximum(mk_pos, 0), t, initial=0) / body_mass
        n_st = max(1, len([c for c in gait.contacts.get(side, [])]))
        M.append(MetricValue("knee_ext_impulse_per_step", imp / n_st, kinetics_kind,
                             f"{n_st} stance phase(s) of the {side} leg"))
        M.append(MetricValue("knee_ext_impulse_total", imp, kinetics_kind, "mechanical demand, not fatigue"))
        if s.descent_height_m:
            M.append(MetricValue("knee_ext_impulse_per_m", imp / s.descent_height_m, kinetics_kind))
        else:
            M.append(MetricValue("knee_ext_impulse_per_m", None, "unavailable", "Enter the height descended."))
        negw = dyn.integrate(np.minimum(np.nan_to_num(power), 0), t, stance) / body_mass
        M.append(MetricValue("knee_neg_work", negw, kinetics_kind))
        pw = np.where(stance, power, np.nan)
        M.append(MetricValue("knee_power_absorption_peak",
                             float(-np.nanmin(pw)) / body_mass if np.isfinite(pw).any() and np.nanmin(pw) < 0 else None,
                             kinetics_kind, "magnitude of the most negative knee power"))

        # Sensitivity of the scenario model to its assumptions.
        if kinetics_kind == "scenario":
            share = dyn.leg_load_share(t, gait, side)
            for supp in ("static", "dynamic"):
                try:
                    support = dyn.total_support_force(kin, body_mass, supp == "dynamic")
                except ValueError:
                    continue
                if np.isfinite(support[stance]).mean() < 0.8:
                    notes.append(f"Sensitivity rows for the {supp} support model skipped (COM not computable).")
                    continue
                com_all = dyn.whole_body_com(kin)
                pole_scales = (0.5, 1.0, 1.5) if pl.source == "scenario" else (1.0,)
                for gdir, copf, ps in [(g, c, k) for g in ("com", "vertical")
                                       for c in sorted({0.25, 0.5, 0.75, round(s.cop_fraction, 3)}) for k in pole_scales]:
                    f_foot = np.nan_to_num(share) * np.maximum(support - ps * pole_vert, 0.0)
                    mk = np.where(stance, dyn.quasi_static_knee(kin, side, f_foot, dyn.cop_on_foot(kin, side, copf),
                                                                com_all if gdir == "com" else None), np.nan)
                    if np.isfinite(mk[stance]).mean() < 0.8:
                        continue
                    pk_s = _peak(mk)  # stance-only peak, same definition as the nominal value
                    mk = np.nan_to_num(mk)
                    for r in (s.moment_arm_range_m[0], s.moment_arm_m, s.moment_arm_range_m[1]):
                        sens_rows.append({"support_model": supp, "grf_direction": gdir, "cop_fraction": copf,
                                          "pole_force_pct_bw": ps * s.pole_pct_bw if pl.source == "scenario" else None,
                                          "moment_arm_m": r,
                                          "peak_knee_moment_nm_per_kg": pk_s / body_mass,
                                          "peak_quad_force_n": float(dyn.quadriceps_force(mk, r).max()),
                                          "knee_impulse_nms_per_kg": dyn.integrate(np.maximum(mk, 0), t) / body_mass})
            if sens_rows:
                sdf = pd.DataFrame(sens_rows)
                mv = next(m for m in M if m.key == "knee_ext_moment_peak")
                mv.low, mv.high = float(sdf.peak_knee_moment_nm_per_kg.min()), float(sdf.peak_knee_moment_nm_per_kg.max())
                mv.note = ("range = sensitivity to support model, force direction, COP"
                           + (" and pole force (±50 %)" if pl.source == "scenario" else ""))
                mn = next(m for m in M if m.key == "knee_ext_moment_peak_nm")
                mn.low, mn.high, mn.note = mv.low * body_mass, mv.high * body_mass, mv.note
    else:
        reason = kin_block or ("Measured-force mode needs a vertical ground reaction force."
                               if s.load_mode == "measured" else "Needs detected foot contacts.")
        if "reason_override" in locals():
            reason = reason_override
        for key in ("knee_ext_moment_peak", "knee_ext_moment_peak_nm", "quad_force_peak", "quad_force_peak_bw",
                    "knee_ext_impulse_total", "knee_ext_impulse_per_step", "knee_ext_impulse_per_m", "knee_neg_work", "knee_power_absorption_peak"):
            M.append(MetricValue(key, None, "unavailable", reason))

    # ---- upper-limb kinetics ----------------------------------------------------------------
    if pl.source != "none" and kin_block is None:
        el_pk, sh_pk = [], []
        rng = {"el": {0.5: [], 1.5: []}, "sh": {0.5: [], 1.5: []}}
        f_min = max(10.0, 0.02 * body_mass * G)  # below this the pole is not loaded (load-cell noise, swing)
        for pside, f in pl.axial_n.items():
            f_hand = pl.direction[pside] * f[:, None]
            am = dyn.arm_moments(kin, pside, body_mass, f_hand)
            if pl.source == "scenario":  # same ±50 % pole-force range as the knee sensitivity
                for k in (0.5, 1.5):
                    ak = dyn.arm_moments(kin, pside, body_mass, f_hand * k)
                    for arr, key in ((ak.elbow, "el"), (ak.shoulder, "sh")):
                        v = np.abs(arr[f > f_min])
                        v = v[np.isfinite(v)]
                        if v.size:
                            rng[key][k].append(float(v.max()))
            loaded = f > f_min
            grip = dyn.grip_point(kin, pside)
            ts[f"pole_{pside}_force_x_n"] = np.where(loaded, f_hand[:, 0], np.nan)
            ts[f"pole_{pside}_force_y_n"] = np.where(loaded, f_hand[:, 1], np.nan)
            ts[f"{pside}_grip_x_m"], ts[f"{pside}_grip_y_m"] = grip[:, 0], grip[:, 1]
            for nm in ("shoulder", "elbow", "wrist"):
                xy_ = kin.get(pside, nm)
                ts.setdefault(f"{pside}_{nm}_x_m", xy_[:, 0])
                ts.setdefault(f"{pside}_{nm}_y_m", xy_[:, 1])
            ts[f"{pside}_elbow_moment_nm"] = np.where(loaded, am.elbow, np.nan)
            ts[f"{pside}_shoulder_moment_nm"] = np.where(loaded, am.shoulder, np.nan)
            for arr, out_list in ((am.elbow, el_pk), (am.shoulder, sh_pk)):
                v = np.abs(arr[loaded])
                v = v[np.isfinite(v)]
                if v.size:
                    out_list.append(float(v.max()))
        kind = "model" if pl.source == "measured" else "scenario"
        for key, pk_list, rk in (("elbow_moment_peak", el_pk, "el"), ("shoulder_moment_peak", sh_pk, "sh")):
            val = max(pk_list) if pk_list else None
            # peak across poles at each pole-force scale (not mixing one pole's low with the other's high)
            lo = max(rng[rk][0.5]) if rng[rk][0.5] else None
            hi = max(rng[rk][1.5]) if rng[rk][1.5] else None
            note = "absolute value; quasi-static" + ("; range = pole force ±50 %" if lo is not None else "")
            k_ = kind if pk_list else "unavailable"
            M.append(MetricValue(key, val, k_, note, low=lo, high=hi))
            M.append(MetricValue(f"{key}_per_kg", val / body_mass if val is not None else None, k_, note,
                                 low=lo / body_mass if lo is not None else None,
                                 high=hi / body_mass if hi is not None else None))
    else:
        why = ((kin_block or "Needs a pole force: a scenario pole force (mode B) or a measured one (mode C).")
               if uses_poles else "No poles in this condition.")
        for key in ("elbow_moment_peak", "elbow_moment_peak_per_kg", "shoulder_moment_peak", "shoulder_moment_peak_per_kg"):
            M.append(MetricValue(key, None, "unavailable", why))

    M.append(MetricValue("tibiofemoral_compression", None, "unavailable",
                         "Requires a musculoskeletal model with co-contraction and measured GRF."))

    # ---- events table ------------------------------------------------------------------------
    for fs_, ivs in gait.contacts.items():
        for c in ivs:
            ev_rows.append({"event": f"{fs_}_foot_contact", "start_s": c.start_s, "end_s": c.end_s,
                            "duration_s": c.duration})
    # ---- EMG (%MVC) ------------------------------------------------------------------------------
    if emg is not None:
        from . import emg as emgmod
        from .metrics import ensure_emg_info
        ed, mvc, off = emg
        pct = emgmod.percent_mvc(ed, mvc, t, off)
        for ch, y in pct.items():
            ensure_emg_info(ch)
            ts[f"emg_{ch}_pct_mvc"] = y
            st_vals = y[stance & np.isfinite(y)]
            M.append(MetricValue(f"emg_{ch}_peak", float(np.nanmax(y)) if np.isfinite(y).any() else None,
                                 "measured" if np.isfinite(y).any() else "unavailable", "whole analysis window"))
            M.append(MetricValue(f"emg_{ch}_stance_mean", float(st_vals.mean()) if st_vals.size else None,
                                 "measured" if st_vals.size else "unavailable", f"{side} foot stance"))
        missing = sorted(set(ed.channels) - set(pct))
        if missing:
            notes.append(f"EMG channels without an MVC value (not normalised): {', '.join(missing)}.")

    from .technique import analyse_technique, foot_event_rows, support_phases
    ev_rows += foot_event_rows(gait.contacts, float(t[0]), float(t[-1]))
    events = pd.DataFrame(ev_rows, columns=["event", "start_s", "end_s", "duration_s", "angle_at_contact_deg"])
    events = events.sort_values("start_s").reset_index(drop=True)
    tq = analyse_technique(events, {k: float(v.coverage()) for k, v in poles.items() if v is not None}, uses_poles)
    tq.support_phases = support_phases(t, stance_mask(t, gait.contacts.get("left", [])),
                                       stance_mask(t, gait.contacts.get("right", [])))
    quality["technique"] = tq.as_dict()
    tk = "video" if tq.n_plants else "unavailable"
    why = "" if tq.n_plants else ("No poles in this condition." if not uses_poles else "No pole plants detected.")
    M.append(MetricValue("pole_simultaneous_fraction", tq.simultaneous_fraction, tk, why or tq.pattern))
    M.append(MetricValue("pole_plant_timing_sd", tq.plant_timing_sd_s, tk if tq.plant_timing_sd_s is not None else
                         "unavailable", why or "consistency of plant timing across plants"))
    M.append(MetricValue("steps_without_pole", tq.steps_without_pole_pct, tk if tq.steps_without_pole_pct is not None
                         else "unavailable", why))

    quality = {**kin.quality, **quality}
    seg = segments or {}
    if scale and seg.get("thigh_m") and seg.get("shank_m"):
        th = np.nanmedian(np.linalg.norm(kin.get(side, "hip") - kin.get(side, "knee"), axis=1))
        sh = np.nanmedian(np.linalg.norm(kin.get(side, "knee") - kin.get(side, "ankle"), axis=1))
        quality["thigh_shank_ratio_video"] = float(th / sh)
        quality["thigh_shank_ratio_measured"] = float(seg["thigh_m"] / seg["shank_m"])
    quality["scale_m_per_px"] = scale
    quality["analysed_side"] = side
    quality["n_frames"] = n
    quality["fps"] = kin.fs
    return TrialResult(pd.DataFrame(ts), M, events, pd.DataFrame(sens_rows), quality, side,
                       asdict(settings), notes)


def save_result(res: TrialResult, out_dir: str | Path, meta: dict | None = None) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "timeseries": out / "timeseries.csv",
        "summary": out / "summary.csv",
        "events": out / "events.csv",
        "sensitivity": out / "sensitivity.csv",
        "info": out / "analysis.json",
    }
    res.timeseries.to_csv(files["timeseries"], index=False, float_format="%.9g")
    res.summary_table().to_csv(files["summary"], index=False, float_format="%.9g")
    res.events.to_csv(files["events"], index=False, float_format="%.6g")
    res.sensitivity.to_csv(files["sensitivity"], index=False, float_format="%.6g")
    files["info"].write_text(json.dumps({"meta": meta or {}, "side": res.side, "quality": res.quality,
                                         "settings": res.settings, "notes": res.notes}, indent=2, default=str))
    return files


def load_result(out_dir: str | Path) -> TrialResult:
    out = Path(out_dir)
    info = json.loads((out / "analysis.json").read_text())
    summ = pd.read_csv(out / "summary.csv")
    metrics = []
    from .metrics import ensure_info_for_key
    for k in summ["key"]:
        ensure_info_for_key(str(k))
    for _, r in summ.iterrows():
        g = lambda k: None if pd.isna(r.get(k)) else float(r[k])  # noqa: E731
        kind = next(k for k, v in KINDS.items() if v == r["evidence"])
        metrics.append(MetricValue(r["key"], g("value"), kind, "" if pd.isna(r["note"]) else str(r["note"]),
                                   g("sd"), g("low"), g("high"), str(r.get("view", "side")) if "view" in r else "side"))
    sens = out / "sensitivity.csv"
    try:
        sdf = pd.read_csv(sens)
    except pd.errors.EmptyDataError:
        sdf = pd.DataFrame()
    return TrialResult(pd.read_csv(out / "timeseries.csv"), metrics, pd.read_csv(out / "events.csv"),
                       sdf, info["quality"], info["side"], info["settings"], info["notes"])
