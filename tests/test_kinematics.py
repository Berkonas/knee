import numpy as np
import pytest

from trailbuddy.core import kinematics as km
from trailbuddy.core.events import detect_gait
from trailbuddy.core.synthetic import synthetic_descent


def test_interior_angle_right_angle():
    assert km.interior_angle(np.array([1.0, 0]), np.array([0.0, 0]), np.array([0.0, 1])) == pytest.approx(90)


def test_wrap180():
    assert km.wrap180(190) == pytest.approx(-170)
    assert km.wrap180(-190) == pytest.approx(170)


@pytest.fixture(scope="module")
def synth():
    pose, truth = synthetic_descent(duration=4.0, fps=60)
    kin = km.compute(pose, truth.scale_m_per_px, cutoff_hz=0)  # unfiltered: exact geometry
    return pose, truth, kin


def test_knee_and_hip_angles_match_truth(synth):
    pose, truth, kin = synth
    sl = slice(10, -10)  # ignore filter edge effects
    for side in ("left", "right"):
        err = kin.angles[f"{side}_knee_flexion"][sl] - truth.knee_flexion[side][sl]
        assert np.nanmax(np.abs(err)) < 0.01
        herr = kin.angles[f"{side}_hip_flexion"][sl] - truth.hip_flexion[side][sl]
        assert np.nanmax(np.abs(herr)) < 0.01


def test_filtered_angles_close_to_truth():
    pose, truth = synthetic_descent(duration=4.0, fps=60, noise_px=1.0)
    kin = km.compute(pose, truth.scale_m_per_px, cutoff_hz=6)
    sl = slice(15, -15)
    err = kin.angles["right_knee_flexion"][sl] - truth.knee_flexion["right"][sl]
    assert np.sqrt(np.nanmean(err**2)) < 2.0  # RMS error with 1 px noise and 6 Hz filtering


def test_trunk_elbow_shoulder(synth):
    pose, truth, kin = synth
    sl = slice(10, -10)
    assert np.nanmax(np.abs(kin.angles["trunk_lean"][sl] - truth.trunk_lean[sl])) < 1.0
    assert np.nanmax(np.abs(kin.angles["right_elbow_flexion"][sl] - 70)) < 1.0
    assert np.nanmax(np.abs(kin.angles["right_shoulder_flexion"][sl] - truth.shoulder_flexion[sl])) < 1.5


def test_direction_flip_gives_same_angles():
    pose, truth = synthetic_descent(duration=2.0)
    flipped = pose.xy.copy()
    flipped[..., 0] = pose.width - flipped[..., 0]
    from trailbuddy.core.landmarks import PoseSeries
    p2 = PoseSeries(pose.t, flipped, pose.visibility, pose.fps, pose.width, pose.height)
    k1 = km.compute(pose, truth.scale_m_per_px)
    k2 = km.compute(p2, truth.scale_m_per_px)
    assert k2.direction == -k1.direction
    np.testing.assert_allclose(k1.angles["right_knee_flexion"], k2.angles["right_knee_flexion"], atol=1e-6)


def test_scale_from_height(synth):
    pose, truth, _ = synth
    s = km.scale_from_height(pose, 1.75)
    assert s == pytest.approx(truth.scale_m_per_px, rel=0.02)


def test_scale_from_points():
    assert km.scale_from_points((0, 0), (300, 400), 1.0) == pytest.approx(1 / 500)
    with pytest.raises(ValueError):
        km.scale_from_points((1, 1), (1, 1), 1.0)


def test_low_visibility_points_are_not_used():
    pose, truth = synthetic_descent(duration=2.0)
    pose.visibility[:, 26] = 0.1  # right knee unreliable everywhere
    kin = km.compute(pose, truth.scale_m_per_px)
    assert np.isnan(kin.angles["right_knee_flexion"]).all()


def test_gait_events_match_truth(synth):
    pose, truth, kin = synth
    gait = detect_gait(kin)
    for side in ("left", "right"):
        full = [c for c in truth.contacts[side] if c[0] > 0.05 and c[1] < 3.95]
        det = [c for c in gait.contacts[side] if c.start_s > 0.05 and c.end_s < 3.95]
        assert len(det) == len(full)
        for (a, b), c in zip(full, det):
            assert abs(c.start_s - a) < 0.06
            assert abs(c.end_s - b) < 0.06
    assert gait.cadence_steps_per_min() == pytest.approx(60 / 0.8, rel=0.08)
