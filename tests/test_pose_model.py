"""MediaPipe integration smoke test (downloads the model once; skipped when offline)."""

import numpy as np
import pytest

from trailbuddy.core import pose, video
from trailbuddy.core.synthetic import render_frames, synthetic_descent


@pytest.fixture(scope="module")
def model():
    try:
        return pose.model_path("lite")
    except RuntimeError:
        pytest.skip("pose model not downloadable (offline)")


def test_estimate_runs_and_leaves_undetected_frames_nan(model, tmp_path):
    p, _ = synthetic_descent(duration=0.5, fps=30, width=320, img_height=240, px_per_m=100)
    v = video.write_video(render_frames(p), tmp_path / "v.mp4", 30)
    calls = []
    ps = pose.estimate(v, 0, 10, "lite", progress=calls.append)
    assert ps.n_frames == 10 and ps.xy.shape == (10, 33, 2)
    assert calls[-1] == 1.0
    # no human in a stick-figure video: frames are NaN, never invented
    undetected = np.isnan(ps.xy[:, 0, 0])
    assert np.all(ps.visibility[undetected] == 0)


def test_estimate_cancel(model, tmp_path):
    p, _ = synthetic_descent(duration=0.5, fps=30, width=320, img_height=240, px_per_m=100)
    v = video.write_video(render_frames(p), tmp_path / "v.mp4", 30)
    with pytest.raises(pose.Cancelled):
        pose.estimate(v, 0, 10, "lite", cancelled=lambda: True)


def test_bad_interval(model, tmp_path):
    p, _ = synthetic_descent(duration=0.5, fps=30, width=320, img_height=240, px_per_m=100)
    v = video.write_video(render_frames(p), tmp_path / "v.mp4", 30)
    with pytest.raises(ValueError):
        pose.estimate(v, 5, 6, "lite")
