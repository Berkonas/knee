"""Kinetic models. Every output here is MODEL-DERIVED and depends on stated assumptions.

Two lower-limb models are provided:

1. ``inverse_dynamics_leg`` - full 2D Newton-Euler inverse dynamics (foot -> shank -> thigh),
   used when a measured ground reaction force (force plate / instrumented step) is supplied.

2. ``quasi_static_knee`` - a quasi-static model for video-only trials: the foot's ground reaction
   force is assumed vertical, with magnitude from a stated support scenario, acting at an assumed
   centre of pressure (COP) on the foot. Segment inertia and weight below the knee are neglected:

       M_knee,ext = F_v * (x_knee - x_COP)

   This captures how posture (knee position relative to the foot) and pole unloading change knee
   extensor demand, but it ignores dynamic force peaks (impact) and horizontal forces.

Sign conventions (lab frame x forward, y up, counter-clockwise positive):
  * internal knee moment on the shank at the knee: + = EXTENSOR
  * internal hip moment on the thigh at the hip:   + = FLEXOR  (reported as extensor = -M)
  * internal ankle moment on the foot at ankle:    + = DORSIFLEXOR (reported as plantarflexor = -M)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .anthropometry import G, WINTER, segment_mass
from .events import ContactInterval, GaitEvents
from .signal import derivative


def cross2(r: np.ndarray, f: np.ndarray) -> np.ndarray:
    return r[..., 0] * f[..., 1] - r[..., 1] * f[..., 0]


def _acc(p: np.ndarray, dt: float) -> np.ndarray:
    v = np.stack([derivative(p[:, 0], dt), derivative(p[:, 1], dt)], axis=1)
    return np.stack([derivative(v[:, 0], dt), derivative(v[:, 1], dt)], axis=1)


def _ang_acc(prox: np.ndarray, dist: np.ndarray, dt: float) -> np.ndarray:
    v = prox - dist
    th = np.unwrap(np.arctan2(v[:, 1], v[:, 0]))
    return derivative(derivative(th, dt), dt)


# --------------------------------------------------------------------------------------------
# Whole-body centre of mass and total external force (Newton's 2nd law on the whole body)
# --------------------------------------------------------------------------------------------

def whole_body_com(kin) -> np.ndarray:
    """Whole-body COM (n, 2) from Winter segment masses and COM locations (lab frame)."""
    P = kin.pts
    parts = []

    def along(prox, dist, frac):
        return prox + frac * (dist - prox)

    trunk = along(P["mid_shoulder"], P["mid_hip"], 1 - WINTER["trunk"].com_frac)
    parts.append((WINTER["trunk"].mass_frac, trunk))
    head = P.get("head", P["mid_shoulder"])
    parts.append((WINTER["head_neck"].mass_frac, head))
    for s in ("left", "right"):
        g = lambda n: P[f"{s}_{n}"]  # noqa: E731
        parts += [
            (WINTER["upper_arm"].mass_frac, along(g("shoulder"), g("elbow"), WINTER["upper_arm"].com_frac)),
            (WINTER["forearm_hand"].mass_frac, along(g("elbow"), g("wrist"), WINTER["forearm_hand"].com_frac)),
            (WINTER["thigh"].mass_frac, along(g("hip"), g("knee"), WINTER["thigh"].com_frac)),
            (WINTER["shank"].mass_frac, along(g("knee"), g("ankle"), WINTER["shank"].com_frac)),
            (WINTER["foot"].mass_frac, along(g("ankle"), g("foot_index"), WINTER["foot"].com_frac)),
        ]
    w = sum(m for m, _ in parts)
    return sum(m * p for m, p in parts) / w


def total_support_force(kin, body_mass: float, dynamic: bool) -> np.ndarray:
    """Total vertical external support force (N) = feet + poles.

    static : m*g (quasi-static assumption)
    dynamic: m*(g + a_COM,y) with a_COM from twice-differentiated, low-pass filtered video COM.
             Sensitive to filtering and scale; treat as an estimate.
    """
    n = len(kin.t)
    if not dynamic:
        return np.full(n, body_mass * G)
    if kin.units != "m":
        raise ValueError("Dynamic support force requires a metric scale.")
    a = _acc(whole_body_com(kin), 1.0 / kin.fs)
    return body_mass * (G + a[:, 1])


# --------------------------------------------------------------------------------------------
# Support scenarios for video-only trials
# --------------------------------------------------------------------------------------------

def leg_load_share(t: np.ndarray, gait: GaitEvents, side: str) -> np.ndarray:
    """Fraction of leg-borne support carried by ``side`` (0..1, NaN where unknown).

    Single support -> 1 (stance leg) / 0 (swing leg). Double support -> linear transfer from the
    trailing leg to the leading leg over the overlap. No foot detected in contact -> NaN.
    """
    other = "left" if side == "right" else "right"
    def mask(ivs: list[ContactInterval]):
        m = np.zeros(len(t), bool)
        for c in ivs:
            m[c.start_i:c.end_i + 1] = True
        return m
    me, ot = mask(gait.contacts.get(side, [])), mask(gait.contacts.get(other, []))
    share = np.where(me & ~ot, 1.0, np.where(ot & ~me, 0.0, np.nan))
    both = me & ot
    if both.any():
        edges = np.flatnonzero(np.diff(np.concatenate(([0], both.astype(int), [0]))))
        for a, b in zip(edges[::2], edges[1::2]):
            # leading leg = the one whose current contact began more recently
            def start_of(ivs):
                st = [c.start_i for c in ivs if c.start_i <= a <= c.end_i]
                return st[0] if st else -1
            mine, theirs = start_of(gait.contacts[side]), start_of(gait.contacts[other])
            ramp = np.linspace(0, 1, b - a) if b - a > 1 else np.array([0.5])
            share[a:b] = ramp if mine > theirs else 1 - ramp
    return share


@dataclass
class PoleLoad:
    """Pole forces acting on the participant, per pole: axial force (N) and hand/tip geometry."""

    axial_n: dict[str, np.ndarray] = field(default_factory=dict)       # 'left'/'right' -> (n,)
    direction: dict[str, np.ndarray] = field(default_factory=dict)     # unit vector tip->hand (n,2)
    source: str = "none"   # 'none' | 'measured' | 'scenario'
    direction_assumed_vertical: bool = False

    def vertical_total(self, n: int) -> np.ndarray:
        tot = np.zeros(n)
        for k, f in self.axial_n.items():
            d = self.direction.get(k)
            uy = d[:, 1] if d is not None else np.ones(n)
            tot += np.nan_to_num(f) * np.nan_to_num(uy, nan=1.0)
        return tot


def pole_direction(hand: np.ndarray, tip: np.ndarray | None, n: int) -> tuple[np.ndarray, bool]:
    """Unit vector from pole tip to hand; vertical if tip is unknown (flagged)."""
    if tip is None or np.all(np.isnan(tip)):
        return np.tile([0.0, 1.0], (n, 1)), True
    v = hand - tip
    nrm = np.linalg.norm(v, axis=1, keepdims=True)
    d = v / np.where(nrm > 0, nrm, np.nan)
    assumed = np.isnan(d[:, 0])
    d[assumed] = [0.0, 1.0]
    return d, bool(assumed.mean() > 0.5)


def scenario_pole_load(n: int, body_mass: float, pct_bw_per_pole: float,
                       contact: dict[str, np.ndarray], directions: dict[str, np.ndarray]) -> PoleLoad:
    """Each pole in contact carries an axial force of pct_bw_per_pole % of body weight."""
    pl = PoleLoad(source="scenario")
    for k, m in contact.items():
        pl.axial_n[k] = np.where(m, pct_bw_per_pole / 100.0 * body_mass * G, 0.0)
        pl.direction[k] = directions.get(k, np.tile([0.0, 1.0], (n, 1)))
    pl.direction_assumed_vertical = any(k not in directions for k in contact)
    return pl


# --------------------------------------------------------------------------------------------
# Lower limb
# --------------------------------------------------------------------------------------------

def cop_on_foot(kin, side: str, frac_heel_to_toe: float) -> np.ndarray:
    heel, toe = kin.get(side, "heel"), kin.get(side, "foot_index")
    return heel + frac_heel_to_toe * (toe - heel)


def quasi_static_knee(kin, side: str, f_vertical: np.ndarray, cop: np.ndarray) -> np.ndarray:
    """Internal knee extensor moment (N*m), + = extensor, from a vertical foot force at COP."""
    if kin.units != "m":
        raise ValueError("Knee moment requires a metric scale (calibrate distance or enter height).")
    return f_vertical * (kin.get(side, "knee")[:, 0] - cop[:, 0])


@dataclass
class LegDynamics:
    ankle_plantarflexor: np.ndarray
    knee_extensor: np.ndarray
    hip_extensor: np.ndarray
    knee_force: np.ndarray  # (n,2) joint reaction force on shank at knee (N)


def inverse_dynamics_leg(kin, side: str, body_mass: float, grf: np.ndarray, cop: np.ndarray) -> LegDynamics:
    """2D Newton-Euler inverse dynamics, bottom-up (Winter, 2009, ch. 5).

    grf: (n,2) ground reaction force on the foot in lab frame (N); zero outside stance.
    cop: (n,2) centre of pressure (m).
    For each segment:  F_p = m*a - m*g - F_d ;  M_p = I*alpha - M_d - r_p x F_p - r_d x F_d
    where r are vectors from the segment COM to the proximal/distal joint.
    """
    if kin.units != "m":
        raise ValueError("Inverse dynamics requires a metric scale.")
    dt = 1.0 / kin.fs
    g = np.array([0.0, -G])
    ankle, knee, hip = kin.get(side, "ankle"), kin.get(side, "knee"), kin.get(side, "hip")
    toe = kin.get(side, "foot_index")

    def segment(name, prox, dist, F_d, M_d, r_d_point):
        p = WINTER[name]
        m = segment_mass(name, body_mass)
        L = np.nanmedian(np.linalg.norm(dist - prox, axis=1))
        I = m * (p.rgyr_frac * L) ** 2
        com = prox + p.com_frac * (dist - prox)
        a = _acc(com, dt)
        alpha = _ang_acc(prox, dist, dt)
        F_p = m * a - m * g - F_d
        r_p = prox - com
        r_d = r_d_point - com
        M_p = I * alpha - M_d - cross2(r_p, F_p) - cross2(r_d, F_d)
        return F_p, M_p

    grf = np.nan_to_num(grf)
    F_a, M_a = segment("foot", ankle, toe, grf, np.zeros(len(grf)), np.where(np.isnan(cop), ankle, cop))
    F_k, M_k = segment("shank", knee, ankle, -F_a, -M_a, ankle)
    F_h, M_h = segment("thigh", hip, knee, -F_k, -M_k, knee)
    return LegDynamics(-M_a, M_k, -M_h, F_k)


# --------------------------------------------------------------------------------------------
# Derived knee quantities
# --------------------------------------------------------------------------------------------

def quadriceps_force(m_knee_ext: np.ndarray, moment_arm_m: float) -> np.ndarray:
    """Net-moment-equivalent quadriceps (patellar tendon) force, N.

    F_quad = max(M_ext, 0) / r. Assumes the quadriceps alone balance the net extensor moment
    (no antagonist co-contraction), so it is a lower-bound-type estimate of true muscle force.
    """
    if moment_arm_m <= 0:
        raise ValueError("Moment arm must be positive.")
    return np.maximum(m_knee_ext, 0.0) / moment_arm_m


def joint_power(moment: np.ndarray, flexion_deg: np.ndarray, fs: float) -> np.ndarray:
    """Joint power (W) = M_ext * omega_ext, with omega_ext = -d(flexion)/dt (rad/s).

    Negative power while the knee flexes under an extensor moment = eccentric (energy absorption).
    """
    omega_ext = -derivative(np.radians(flexion_deg), 1.0 / fs)
    return moment * omega_ext


def integrate(y: np.ndarray, t: np.ndarray, mask: np.ndarray | None = None) -> float:
    y = np.nan_to_num(np.asarray(y, float))
    if mask is not None:
        y = np.where(mask, y, 0.0)
    return float(np.trapezoid(y, t)) if hasattr(np, "trapezoid") else float(np.trapz(y, t))


# --------------------------------------------------------------------------------------------
# Upper limb (quasi-static)
# --------------------------------------------------------------------------------------------

@dataclass
class ArmMoments:
    elbow: np.ndarray       # internal moment magnitude with sign: + = extensor
    shoulder: np.ndarray    # internal moment, + = flexor (arm-forward direction)


def arm_moments(kin, side: str, body_mass: float, f_hand: np.ndarray,
                include_segment_weight: bool = True) -> ArmMoments:
    """Quasi-static elbow and shoulder moments from the pole force acting at the hand.

    f_hand: (n,2) force exerted BY the pole ON the hand (N). Internal moment = -(sum of external
    moments about the joint). Inertia neglected (slow arm motion during planting).
    """
    if kin.units != "m":
        raise ValueError("Arm moments require a metric scale.")
    sh, el, wr = kin.get(side, "shoulder"), kin.get(side, "elbow"), kin.get(side, "wrist")
    hand = wr
    f_hand = np.nan_to_num(f_hand)
    m_el_ext = cross2(hand - el, f_hand)
    m_sh_ext = cross2(hand - sh, f_hand)
    if include_segment_weight:
        w_fh = np.array([0.0, -segment_mass("forearm_hand", body_mass) * G])
        w_ua = np.array([0.0, -segment_mass("upper_arm", body_mass) * G])
        com_fh = el + WINTER["forearm_hand"].com_frac * (wr - el)
        com_ua = sh + WINTER["upper_arm"].com_frac * (el - sh)
        m_el_ext = m_el_ext + cross2(com_fh - el, np.broadcast_to(w_fh, com_fh.shape))
        m_sh_ext = (m_sh_ext + cross2(com_fh - sh, np.broadcast_to(w_fh, com_fh.shape))
                    + cross2(com_ua - sh, np.broadcast_to(w_ua, com_ua.shape)))
    m_el_int = -m_el_ext
    m_sh_int = -m_sh_ext
    # Elbow: + = extensor if the internal moment tends to open the elbow angle.
    u, f = sh - el, wr - el
    open_sign = np.sign(cross2(u, f))
    return ArmMoments(elbow=m_el_int * open_sign, shoulder=m_sh_int)
