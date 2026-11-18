"""Movement segmentation on synthetic hip trajectories."""

import numpy as np

from trailbuddy.core.landmarks import N_LANDMARKS, PoseSeries
from trailbuddy.core.segmentation import best_segment, candidate_segments


def pose_from_hip(t, hx, hy, leg=200.0):
    xy = np.full((len(t), N_LANDMARKS, 2), np.nan)
    for j in (23, 24):
        xy[:, j, 0], xy[:, j, 1] = hx, hy
    for j in (25, 26):
        xy[:, j, 0], xy[:, j, 1] = hx, hy + leg / 2
    for j in (27, 28):
        xy[:, j, 0], xy[:, j, 1] = hx, hy + leg
    return PoseSeries(t, xy, np.ones((len(t), N_LANDMARKS)), 60.0, 1920, 1080, "synthetic", {})


def test_two_descents_separated_by_standing_are_two_segments():
    t = np.arange(0, 16, 1 / 60)
    hy = np.piecewise(t, [t < 2, (t >= 2) & (t < 5), (t >= 5) & (t < 9), (t >= 9) & (t < 12), t >= 12],
                      [300, lambda x: 300 + 100 * (x - 2), 600, lambda x: 600 + 100 * (x - 9), 900])
    hx = 500 + 40 * np.clip(t - 2, 0, None) * ((t < 5) | ((t > 9) & (t < 12)))
    segs = candidate_segments(pose_from_hip(t, hx, hy))
    assert [s["label"] for s in segs] == ["descent", "descent"]
    assert abs(segs[0]["start_s"] - 1.7) < 0.3 and abs(segs[0]["end_s"] - 5.3) < 0.3
    assert abs(segs[1]["start_s"] - 8.7) < 0.3


def test_standing_still_gives_no_segment_and_level_walk_is_labelled():
    t = np.arange(0, 6, 1 / 60)
    assert candidate_segments(pose_from_hip(t, np.full_like(t, 500), np.full_like(t, 300))) == []
    segs = candidate_segments(pose_from_hip(t, 500 + 150 * t, np.full_like(t, 300)))
    assert segs[0]["label"] == "level movement"
    assert best_segment(segs) == segs[0]


def test_leg_length_ignores_knee_bend():
    from trailbuddy.core.landmarks import leg_length_px
    t = np.arange(0, 2, 1 / 60)
    xy = np.full((t.size, N_LANDMARKS, 2), np.nan)
    bend = np.radians(60) * (np.sin(2 * np.pi * t) > 0)  # knee bent 60 deg half the time
    for hipj, kneej, ankj in ((23, 25, 27), (24, 26, 28)):
        xy[:, hipj] = [0, 0]
        xy[:, kneej] = [0, 100]
        xy[:, ankj] = np.stack([100 * np.sin(bend), 100 + 100 * np.cos(bend)], axis=1)
    assert leg_length_px(xy) == np.float64(200.0)
