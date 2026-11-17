"""Display filters: noise reduction without lag, gap handling, plausibility checks."""

import numpy as np

from trailbuddy.core import filters


def test_display_lowpass_reduces_noise_without_lag_or_attenuation():
    fs, t = 60.0, np.arange(0, 4, 1 / 60)
    for f in (0.5, 2.0):
        true = 100 * np.sin(2 * np.pi * f * t)
        noisy = true + np.random.default_rng(0).normal(0, 2.0, t.size)
        out = filters.lowpass_runs(noisy[:, None], fs)[:, 0]
        assert np.sqrt(np.mean((out - true) ** 2)) < 0.6 * 2.0
        lag = np.argmax(np.correlate(out - out.mean(), true - true.mean(), "full")) - (t.size - 1)
        assert lag == 0


def test_one_euro_smooths_slow_movement():
    t = np.arange(0, 4, 1 / 60)
    noisy = 10 * t + np.random.default_rng(0).normal(0, 2.0, t.size)
    out = filters.one_euro(noisy[:, None], 60.0)[:, 0]
    assert np.std(np.diff(out)) < 0.5 * np.std(np.diff(noisy))


def test_gaps_stay_gaps():
    x = np.arange(20.0)[:, None]
    x[8:11] = np.nan
    for out in (filters.one_euro_zero_lag(x, 60.0), filters.lowpass_runs(x, 60.0, min_run=5)):
        assert np.isnan(out[8:11]).all() and np.isfinite(out[:8]).all()


def test_implausible_segment_points_are_flagged():
    n = 50
    xy = np.zeros((n, 33, 2))
    xy[:, 23] = [0, 0]
    xy[:, 25] = [0, 40]   # thigh length 40
    xy[10, 25] = [0, 120]  # knee jumps to another object
    bad = filters.implausible_segments(xy)
    assert bad[10, 25] and not bad[5, 25]


def test_display_pose_reports_jitter_drop():
    rng = np.random.default_rng(1)
    t = np.arange(0, 3, 1 / 60)
    xy = np.zeros((t.size, 33, 2))
    for j in range(33):
        xy[:, j, 0] = 50 * np.sin(2 * np.pi * t + j) + 200
        xy[:, j, 1] = 30 * np.cos(2 * np.pi * t + j) + 200
    xy += rng.normal(0, 1.5, xy.shape)
    out, qc = filters.display_pose(xy, np.ones((t.size, 33)), 60.0)
    assert qc["jitter_display_px"] < 0.5 * qc["jitter_raw_px"]
