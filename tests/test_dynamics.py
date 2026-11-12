"""Kinetics checked against hand-calculated reference examples."""

import numpy as np
import pytest

from trailbuddy.core import dynamics as dyn
from trailbuddy.core.anthropometry import G, segment_mass
from trailbuddy.core.events import ContactInterval, GaitEvents
from trailbuddy.core.kinematics import Kinematics


def static_kin(points: dict[str, tuple[float, float]], n: int = 50, fs: float = 100.0) -> Kinematics:
    pts = {k: np.tile(np.array(v, float), (n, 1)) for k, v in points.items()}
    return Kinematics(np.arange(n) / fs, fs, pts, {}, "m", 1.0, 1)


LEG = {"right_hip": (0.0, 0.9), "right_knee": (0.1, 0.5), "right_ankle": (0.0, 0.1),
       "right_heel": (-0.05, 0.05), "right_foot_index": (0.15, 0.05)}


def test_quasi_static_knee_hand_calculation():
    # 700 N vertical force at COP x = 0.05 m; knee at x = 0.10 m -> M = 700 * 0.05 = 35 N*m extensor
    kin = static_kin(LEG)
    cop = np.tile([0.05, 0.05], (50, 1))
    m = dyn.quasi_static_knee(kin, "right", np.full(50, 700.0), cop)
    assert m == pytest.approx(np.full(50, 35.0))


def test_quasi_static_requires_scale():
    kin = static_kin(LEG)
    kin.units = "px"
    with pytest.raises(ValueError):
        dyn.quasi_static_knee(kin, "right", np.ones(50), np.zeros((50, 2)))


def test_newton_euler_static_equals_hand_calc():
    """Static posture: knee moment = GRF moment minus foot+shank weight moments about the knee."""
    kin = static_kin(LEG)
    m_body = 70.0
    grf = np.tile([0.0, 700.0], (50, 1))
    cop = np.tile([0.05, 0.05], (50, 1))
    leg = dyn.inverse_dynamics_leg(kin, "right", m_body, grf, cop)
    # Hand calculation about the knee (x_k = 0.10): GRF: 700*(0.10-0.05)=35.
    m_shank = segment_mass("shank", m_body)
    m_foot = segment_mass("foot", m_body)
    x_shank_com = 0.1 + 0.433 * (0.0 - 0.1)    # knee -> ankle
    x_foot_com = -0.05 + 0.4415 * (0.15 - (-0.05))  # heel -> toe (de Leva COM location)
    expected = 35.0 - m_shank * G * (0.1 - x_shank_com) - m_foot * G * (0.1 - x_foot_com)
    mid = slice(5, -5)
    assert leg.knee_extensor[mid] == pytest.approx(np.full(40, expected), abs=1e-6)
    # Ankle: GRF at 0.05 ahead of ankle (x=0) pushes toe up -> plantarflexor demand = 700*0.05 - foot weight
    exp_ankle = 700 * 0.05 - m_foot * G * (x_foot_com - 0.0)
    assert leg.ankle_plantarflexor[mid] == pytest.approx(np.full(40, exp_ankle), abs=1e-6)


def test_newton_euler_matches_quasi_static_for_massless_limit():
    kin = static_kin(LEG)
    grf = np.tile([0.0, 1000.0], (50, 1))
    cop = np.tile([0.02, 0.05], (50, 1))
    leg = dyn.inverse_dynamics_leg(kin, "right", 1e-9, grf, cop)
    qs = dyn.quasi_static_knee(kin, "right", grf[:, 1], cop)
    assert leg.knee_extensor[5:-5] == pytest.approx(qs[5:-5], rel=1e-9)


def test_pendulum_swing_inverse_dynamics():
    """Shank+foot swinging freely (no GRF) about a fixed knee: M_knee = I_knee*alpha + gravity term."""
    fs, n = 1000.0, 2000
    t = np.arange(n) / fs
    th = 0.3 * np.sin(2 * np.pi * 1.0 * t)  # shank angle from vertical-down
    L = 0.4
    knee = np.tile([0.0, 0.5], (n, 1))
    ankle = knee + L * np.stack([np.sin(th), -np.cos(th)], axis=1)
    toe = ankle + np.tile([1e-6, 0.0], (n, 1))  # negligible foot
    pts = {"right_knee": knee, "right_ankle": ankle, "right_foot_index": toe, "right_hip": knee + [0, 0.4],
           "right_heel": ankle}
    kin = Kinematics(t, fs, pts, {}, "m", 1.0, 1)
    mb = 70.0
    leg = dyn.inverse_dynamics_leg(kin, "right", mb, np.zeros((n, 2)), ankle)
    m = segment_mass("shank", mb)
    rc = 0.433 * L
    I_com = m * (0.302 * L) ** 2
    alpha = -0.3 * (2 * np.pi) ** 2 * np.sin(2 * np.pi * t)
    # Moment needed at knee (CCW +) = (I_com + m rc^2) alpha + m g rc sin(th)
    # foot (mass 0.0145*mb at ankle-ish, length ~0) adds m_f*(L^2 alpha + g L sin th)
    mf = segment_mass("foot", mb)
    expected = (I_com + m * rc**2) * alpha + m * G * rc * np.sin(th) + mf * (L**2 * alpha + G * L * np.sin(th))
    mid = slice(50, -50)
    np.testing.assert_allclose(leg.knee_extensor[mid], expected[mid], atol=0.05)


def test_quadriceps_force_and_negative_values():
    q = dyn.quadriceps_force(np.array([-10.0, 0.0, 50.0]), 0.05)
    assert q == pytest.approx([0.0, 0.0, 1000.0])
    with pytest.raises(ValueError):
        dyn.quadriceps_force(np.ones(3), 0.0)


def test_joint_power_eccentric_sign():
    fs = 100.0
    t = np.arange(100) / fs
    flex = 10 + 40 * t            # knee flexing at 40 deg/s
    m = np.full(100, 50.0)        # extensor moment
    p = dyn.joint_power(m, flex, fs)
    assert p[50] == pytest.approx(-50 * np.radians(40))
    w = dyn.integrate(np.minimum(p, 0), t)
    assert w == pytest.approx(-50 * np.radians(40) * t[-1], rel=1e-6)


def test_leg_load_share_single_and_double_support():
    t = np.arange(0, 1.0, 0.01)
    gait = GaitEvents({"right": [ContactInterval(0.0, 0.59, 0, 59)],
                       "left": [ContactInterval(0.4, 0.99, 40, 99)]})
    sh = dyn.leg_load_share(t, gait, "right")
    assert sh[10] == 1.0 and sh[80] == 0.0
    # double support 0.40-0.59: right is trailing -> ramps down 1 -> 0
    ds = sh[40:60]
    assert ds[0] == pytest.approx(1.0) and ds[-1] == pytest.approx(0.0)
    sl = dyn.leg_load_share(t, gait, "left")
    np.testing.assert_allclose(sh + sl, 1.0)


def test_arm_moments_hand_calculation():
    # Upper arm hanging, forearm horizontal forward; pole pushes straight up on the hand with 100 N.
    pts = {"right_shoulder": (0.0, 1.4), "right_elbow": (0.0, 1.1), "right_wrist": (0.3, 1.1)}
    kin = static_kin(pts, n=5)
    f = np.tile([0.0, 100.0], (5, 1))
    am = dyn.arm_moments(kin, "right", 70.0, f, include_segment_weight=False)
    # external moment of an upward force 0.3 m ahead = +30 (CCW) -> internal -30.
    # Internal clockwise on forearm closes... forearm CCW from upper-arm-down? u=(0,0.3) up, f=(0.3,0):
    # cross(u,f) = -0.09 <0 -> CCW rotation of forearm closes the elbow; internal CW (-30) opens it
    # -> extensor demand of +30 N*m (triceps push down on pole).
    assert am.elbow == pytest.approx(np.full(5, 30.0))
    # shoulder: internal -30 (clockwise) = extensor (arm pulled back/down) -> negative flexor
    assert am.shoulder == pytest.approx(np.full(5, -30.0))


def test_pole_direction_vertical_fallback():
    d, assumed = dyn.pole_direction(np.zeros((3, 2)), None, 3)
    assert assumed and np.allclose(d, [[0, 1]] * 3)
    d, assumed = dyn.pole_direction(np.tile([0.0, 1.0], (3, 1)), np.tile([0.0, 0.0], (3, 1)), 3)
    assert not assumed and np.allclose(d, [[0, 1]] * 3)


def test_scenario_pole_load_vertical_total():
    n = 4
    contact = {"right": np.array([True, True, False, False])}
    dirs = {"right": np.tile([0.6, 0.8], (n, 1))}
    pl = dyn.scenario_pole_load(n, 70.0, 10.0, contact, dirs)
    v = pl.vertical_total(n)
    assert v[0] == pytest.approx(0.1 * 70 * G * 0.8)
    assert v[3] == 0.0


def test_total_support_force_static_and_dynamic():
    kin = static_kin({**{f"{s}_{k}": (0.0, 1.0) for s in ("left", "right")
                         for k in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle", "heel", "foot_index")},
                      "mid_shoulder": (0, 1.4), "mid_hip": (0, 1.0), "head": (0, 1.6)})
    assert dyn.total_support_force(kin, 70, False)[0] == pytest.approx(70 * G)
    # stationary body -> dynamic equals static
    assert dyn.total_support_force(kin, 70, True)[10] == pytest.approx(70 * G)
