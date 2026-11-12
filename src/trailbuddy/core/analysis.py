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
    contact_rel_threshold: float = 0.15
    contact_min_duration_s: float = 0.08
    support_model: str = "static"         # 'static' (m*g) | 'dynamic' (m*(g+a_COM))
    cop_fraction: float = 0.5             # assumed COP position heel(0) -> toe(1)
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
        cols = ["key", "label", "value", "sd", "low", "high", "unit", "evidence", "note"]
        return pd.DataFrame([m.as_row() for m in self.metrics])[cols]


def _peak(y: np.ndarray, mask: np.ndarray | None = None) -> float | None:
    v = y[mask] if mask is not None else y
    v = v[~np.isnan(v)]
    return float(v.max()) if len(v) else None


def analyse(pose: PoseSeries, body_mass: float, height_m: float, settings: AnalysisSettings,
            uses_poles: bool = False, poles: dict[str, PoleTrack] | None = None,
            forces: ForceData | None = None, segments: dict | None = None) -> TrialResult:
    s = settings
    notes: list[str] = []
    poles = poles or {}

    # ---- scale & kinematics -------------------------------------------------------------
    scale = None
    if s.scale_method == "points" and s.scale_m_per_px:
        scale = s.scale_m_per_px
        notes.append("Scale from a measured calibration distance in the scene.")
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

    ts = {"time_s": t}
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
    M.append(MetricValue("cadence", gait.cadence_steps_per_min(), "video"))
    st = gait.step_times()
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
        ts[f"pole_{pside}_tip_source"] = tr.source
        tip_lab = kmod.to_lab(tr.tip, pose.height, kin.direction, scale)
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
    if plant_rows:
        dur = np.array([r["duration_s"] for r in plant_rows])
        angs = np.array([r["angle_at_contact_deg"] for r in plant_rows])
        M.append(MetricValue("pole_contact_time", float(dur.mean()), "video", "awaiting validation",
                             sd=float(dur.std(ddof=1)) if len(dur) > 1 else None))
        M.append(MetricValue("pole_angle_at_contact", float(np.nanmean(angs)), "video", "awaiting validation"))
    elif uses_poles:
        notes.append("Poles used but not tracked: pole timing and angles unavailable. "
                     "Use coloured tip markers or manual annotation.")

    # ---- external forces ------------------------------------------------------------------
    pl = dyn.PoleLoad()
    fdat = forces.resample(t, s.force_offset_s, s.cutoff_hz) if forces is not None else {}
    if uses_poles and s.pole_force_mode == "measured" and any(k in fdat for k in ("pole_left", "pole_right")):
        pl.source = "measured"
        for pside in ("left", "right"):
            if f"pole_{pside}" in fdat:
                pl.axial_n[pside] = np.nan_to_num(fdat[f"pole_{pside}"])
                pl.direction[pside] = pole_dirs.get(pside, np.tile([0.0, 1.0], (n, 1)))
                if pside not in pole_dirs:
                    pl.direction_assumed_vertical = True
    elif uses_poles and s.pole_force_mode == "measured":
        notes.append("Measured pole force selected, but no force file with pole_left_n/pole_right_n columns was given.")
    elif uses_poles and s.pole_force_mode == "scenario":
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
        frac = 100 * pole_vert[stance].mean() / (body_mass * G) if stance.any() else None
        M.append(MetricValue("pole_support_fraction", frac, kind,
                             "" if kind == "measured" else f"{s.pole_pct_bw:g}% BW per planted pole (assumed)"))
    else:
        why = ("No pole columns in the force file." if uses_poles and s.pole_force_mode == "measured" else
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
    measured_grf = "vertical" in fdat
    if scale is None:
        notes.append("Kinetics unavailable without a metric scale.")
    elif measured_grf:
        fv = np.nan_to_num(fdat["vertical"])
        fh = np.nan_to_num(fdat.get("horizontal", np.zeros(n)))
        loaded = fv > 20.0
        if (loaded & ~stance).sum() > 0.2 * max(1, loaded.sum()):
            notes.append(f"Force data show load outside the {side} foot's stance: another foot may be on the plate. "
                         f"Only force during the {side} stance is applied to the {side} leg.")
        fv = np.where(stance, fv, 0.0)
        fh = np.where(stance, fh, 0.0)
        if "cop_x" in fdat and s.plate_origin_x_m is not None:
            foot_y = dyn.cop_on_foot(kin, side, 0.5)[:, 1]
            plate_y = np.nanmedian(foot_y[loaded & stance]) if (loaded & stance).any() else np.nanmedian(foot_y)
            cop = np.stack([s.plate_origin_x_m + fdat["cop_x"], np.full(n, plate_y)], axis=1)
        else:
            cop = dyn.cop_on_foot(kin, side, s.cop_fraction)
            notes.append("COP not measured/located: assumed on the foot (cop_fraction).")
        leg = dyn.inverse_dynamics_leg(kin, side, body_mass, np.stack([fh, fv], axis=1), cop)
        m_knee = leg.knee_extensor
        ts[f"{side}_ankle_plantarflexor_moment_nm"] = leg.ankle_plantarflexor
        ts[f"{side}_hip_extensor_moment_nm"] = leg.hip_extensor
        ts["grf_vertical_n"] = fv
        kinetics_kind = "model"
        notes.append("Knee moment from 2D Newton-Euler inverse dynamics with measured ground reaction force.")
    elif stance.any():
        share = dyn.leg_load_share(t, gait, side)
        support = dyn.total_support_force(kin, body_mass, s.support_model == "dynamic")
        f_foot = np.nan_to_num(share) * np.maximum(support - pole_vert, 0.0)
        cop = dyn.cop_on_foot(kin, side, s.cop_fraction)
        m_knee = dyn.quasi_static_knee(kin, side, f_foot, cop)
        m_knee = np.where(stance, m_knee, np.nan)
        ts[f"{side}_foot_force_scenario_n"] = f_foot
        kinetics_kind = "scenario"
        notes.append("No measured ground reaction force: knee moment from the quasi-static scenario "
                     f"model (support = {'m(g+a_COM)' if s.support_model == 'dynamic' else 'body weight'}, "
                     f"COP at {s.cop_fraction:.2f} of heel-to-toe, inertia neglected).")

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
        mk_pos = np.where(stance, np.nan_to_num(m_knee), 0.0)
        q_nom = dyn.quadriceps_force(mk_pos, s.moment_arm_m)
        q_lo = dyn.quadriceps_force(mk_pos, s.moment_arm_range_m[1])  # longer arm -> lower force
        q_hi = dyn.quadriceps_force(mk_pos, s.moment_arm_range_m[0])
        ts[f"{side}_quad_force_n"] = np.where(stance, q_nom, np.nan)
        power = dyn.joint_power(np.nan_to_num(m_knee), kf, kin.fs)
        ts[f"{side}_knee_power_w"] = np.where(stance, power, np.nan)
        pk = _peak(np.where(stance, m_knee, np.nan))
        M.append(MetricValue("knee_ext_moment_peak", pk / body_mass if pk is not None else None, kinetics_kind))
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
                for copf in sorted({0.25, 0.5, 0.75, round(s.cop_fraction, 3)}):
                    f_foot = np.nan_to_num(share) * np.maximum(support - pole_vert, 0.0)
                    mk = np.where(stance, dyn.quasi_static_knee(kin, side, f_foot, dyn.cop_on_foot(kin, side, copf)), np.nan)
                    if np.isfinite(mk[stance]).mean() < 0.8:
                        continue
                    mk = np.nan_to_num(mk)
                    for r in (s.moment_arm_range_m[0], s.moment_arm_m, s.moment_arm_range_m[1]):
                        sens_rows.append({"support_model": supp, "cop_fraction": copf, "moment_arm_m": r,
                                          "peak_knee_moment_nm_per_kg": float(np.nanmax(mk)) / body_mass,
                                          "peak_quad_force_n": float(dyn.quadriceps_force(mk, r).max()),
                                          "knee_impulse_nms_per_kg": dyn.integrate(np.maximum(mk, 0), t) / body_mass})
            if sens_rows:
                sdf = pd.DataFrame(sens_rows)
                mv = next(m for m in M if m.key == "knee_ext_moment_peak")
                mv.low, mv.high = float(sdf.peak_knee_moment_nm_per_kg.min()), float(sdf.peak_knee_moment_nm_per_kg.max())
                mv.note = "range = sensitivity to support model and COP"
    else:
        reason = ("Needs a metric scale." if scale is None else "Needs detected foot contacts.")
        if "reason_override" in locals():
            reason = reason_override
        for key in ("knee_ext_moment_peak", "quad_force_peak", "quad_force_peak_bw",
                    "knee_ext_impulse_total", "knee_ext_impulse_per_m", "knee_neg_work", "knee_power_absorption_peak"):
            M.append(MetricValue(key, None, "unavailable", reason))

    # ---- upper-limb kinetics ----------------------------------------------------------------
    if pl.source != "none" and scale is not None:
        el_pk, sh_pk = [], []
        for pside, f in pl.axial_n.items():
            f_hand = pl.direction[pside] * f[:, None]
            am = dyn.arm_moments(kin, pside, body_mass, f_hand)
            loaded = f > 0
            ts[f"{pside}_elbow_moment_nm"] = np.where(loaded, am.elbow, np.nan)
            ts[f"{pside}_shoulder_moment_nm"] = np.where(loaded, am.shoulder, np.nan)
            for arr, out_list in ((am.elbow, el_pk), (am.shoulder, sh_pk)):
                v = np.abs(arr[loaded])
                v = v[np.isfinite(v)]
                if v.size:
                    out_list.append(float(v.max()))
        kind = "model" if pl.source == "measured" else "scenario"
        M.append(MetricValue("elbow_moment_peak", max(el_pk) if el_pk else None, kind if el_pk else "unavailable",
                             "absolute value; quasi-static"))
        M.append(MetricValue("shoulder_moment_peak", max(sh_pk) if sh_pk else None, kind if sh_pk else "unavailable",
                             "absolute value; quasi-static"))
    else:
        why = "Needs a pole force (measured or scenario) and a metric scale." if uses_poles else "No poles in this condition."
        M.append(MetricValue("elbow_moment_peak", None, "unavailable", why))
        M.append(MetricValue("shoulder_moment_peak", None, "unavailable", why))

    M.append(MetricValue("tibiofemoral_compression", None, "unavailable",
                         "Requires a musculoskeletal model with co-contraction and measured GRF."))

    # ---- events table ------------------------------------------------------------------------
    for fs_, ivs in gait.contacts.items():
        for c in ivs:
            ev_rows.append({"event": f"{fs_}_foot_contact", "start_s": c.start_s, "end_s": c.end_s,
                            "duration_s": c.duration})
    events = pd.DataFrame(ev_rows, columns=["event", "start_s", "end_s", "duration_s", "angle_at_contact_deg"])
    events = events.sort_values("start_s").reset_index(drop=True)

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
    res.timeseries.to_csv(files["timeseries"], index=False, float_format="%.6g")
    res.summary_table().to_csv(files["summary"], index=False, float_format="%.6g")
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
    for _, r in summ.iterrows():
        g = lambda k: None if pd.isna(r.get(k)) else float(r[k])  # noqa: E731
        kind = next(k for k, v in KINDS.items() if v == r["evidence"])
        metrics.append(MetricValue(r["key"], g("value"), kind, "" if pd.isna(r["note"]) else str(r["note"]),
                                   g("sd"), g("low"), g("high")))
    sens = out / "sensitivity.csv"
    try:
        sdf = pd.read_csv(sens)
    except pd.errors.EmptyDataError:
        sdf = pd.DataFrame()
    return TrialResult(pd.read_csv(out / "timeseries.csv"), metrics, pd.read_csv(out / "events.csv"),
                       sdf, info["quality"], info["side"], info["settings"], info["notes"])
