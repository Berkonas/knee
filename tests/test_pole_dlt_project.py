import numpy as np
import pytest

from trailbuddy.core import pole, triangulation as dlt
from trailbuddy.core.project import Condition, Participant, Project, Trial, parse_filename
from trailbuddy.core.synthetic import render_frames, synthetic_descent


def test_color_marker_tracking_on_rendered_frames():
    p, truth = synthetic_descent(duration=1.0, fps=30, width=640, img_height=480, px_per_m=200)
    frames = list(render_frames(p, truth.pole_tip_px))
    x0, y0 = truth.pole_tip_px[0].astype(int)
    det = pole.ColorMarkerDetector.from_sample(frames[0], x0, y0)
    tr = pole.track(frames, p.t, det)
    assert tr.coverage() == 1.0
    assert np.nanmax(np.linalg.norm(tr.tip - truth.pole_tip_px, axis=1)) < 1.5


def test_color_marker_rejects_grey_pixel():
    img = np.full((50, 50, 3), 128, np.uint8)
    with pytest.raises(ValueError):
        pole.ColorMarkerDetector.from_sample(img, 25, 25)


def test_missing_marker_stays_nan():
    p, truth = synthetic_descent(duration=0.5, fps=30, width=640, img_height=480, px_per_m=200)
    tip = truth.pole_tip_px.copy()
    tip[5:8] = np.nan  # marker occluded
    frames = list(render_frames(p, tip))
    det = pole.ColorMarkerDetector.from_sample(frames[0], *truth.pole_tip_px[0].astype(int))
    tr = pole.track(frames, p.t, det)
    assert np.isnan(tr.tip[5:8]).all()
    assert (tr.source[5:8] == 0).all()


def test_manual_annotation_interpolation_and_flags(tmp_path):
    ann = pole.ManualAnnotations()
    ann.set("right", "tip", 0, 100, 200)
    ann.set("right", "tip", 10, 200, 200)
    ann.set("right", "tip", 50, 300, 200)  # gap 40 > max_gap -> stays NaN
    t = np.arange(60) / 30
    tr = ann.to_track("right", t, max_gap_frames=15)
    assert tr.tip[5, 0] == pytest.approx(150)
    assert tr.source[0] == 2 and tr.source[5] == 3
    assert np.isnan(tr.tip[30]).all() and tr.source[30] == 0
    ann.save(tmp_path / "a.json")
    assert pole.ManualAnnotations.load(tmp_path / "a.json").points["right"]["tip"][10] == (200, 200)


def test_pole_contact_detection():
    t = np.arange(0, 2, 1 / 60)
    x = np.where(t < 0.5, 300 * t, np.where(t < 1.0, 150, 150 + 300 * (t - 1.0)))
    tr = pole.PoleTrack(t, np.stack([x, np.full_like(x, 400)], axis=1))
    ivs = pole.pole_contacts(tr)
    assert len(ivs) == 1 and ivs[0].start_s == pytest.approx(0.5, abs=0.04) and ivs[0].end_s == pytest.approx(1.0, abs=0.04)
    sparse = pole.PoleTrack(t, np.full((len(t), 2), np.nan))
    assert pole.pole_contacts(sparse) is None


def _camera(R_deg, tvec, f=800, c=(320, 240)):
    a = np.radians(R_deg)
    R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    def proj(X):
        Xc = (R @ X.T).T + tvec
        return np.stack([f * Xc[:, 0] / Xc[:, 2] + c[0], f * Xc[:, 1] / Xc[:, 2] + c[1]], axis=1)
    return proj


def test_dlt_calibration_and_reconstruction():
    rng = np.random.default_rng(0)
    ctrl = rng.uniform(-0.5, 0.5, (10, 3)) + [0, 0, 0]
    cams = [_camera(0, np.array([0, 0, 4.0])), _camera(60, np.array([0, 0, 4.0]))]
    Ls = [dlt.calibrate(ctrl, c(ctrl)) for c in cams]
    for L, c in zip(Ls, cams):
        assert dlt.reprojection_error(L, ctrl, c(ctrl)) < 1e-6
    test = rng.uniform(-0.4, 0.4, (5, 3))
    rec = dlt.reconstruct(Ls, [c(test) for c in cams])
    assert np.allclose(rec, test, atol=1e-6)


def test_dlt_rejects_too_few_points():
    with pytest.raises(ValueError):
        dlt.calibrate(np.zeros((4, 3)), np.zeros((4, 2)))


def test_project_roundtrip(tmp_path):
    pr = Project.new(tmp_path / "study", "Pilot", "exp2")
    assert [c.code for c in pr.conditions] == ["C0", "C1", "C2", "C3"]
    pr.add_participant(Participant("P01", 70, 1.75, standard_pole_length_cm=115))
    t = pr.add_trial(Trial("P01", "C2", 1))
    assert t.id == "P01_C2_T01" and t.pole_length_cm == 110
    assert pr.planned_trials() == 12
    pr.add_condition(Condition("C4", "Custom", True, 10))
    pr.save()
    pr2 = Project.load(tmp_path / "study")
    assert pr2.trial("P01_C2_T01").pole_length_cm == 110
    assert pr2.condition("C4").pole_offset_cm == 10


def test_project_validation(tmp_path):
    pr = Project.new(tmp_path, "x")
    with pytest.raises(ValueError):
        pr.add_participant(Participant("Jane Doe", 70, 1.7))
    with pytest.raises(ValueError):
        pr.add_participant(Participant("P01", 5, 1.7))
    pr.add_participant(Participant("P01", 70, 1.7))
    with pytest.raises(ValueError):
        pr.add_participant(Participant("P01", 70, 1.7))
    with pytest.raises(KeyError):
        pr.add_trial(Trial("P09", "C0", 1))


def test_parse_filename():
    assert parse_filename("P01_C1_T03.mp4") == ("P01", "C1", 3)
    assert parse_filename("p02_c0_t1_side.MOV") == ("P02", "C0", 1)
    assert parse_filename("holiday.mp4") is None
