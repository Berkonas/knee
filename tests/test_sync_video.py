"""Clap synchronization and video I/O with recordings of known timing."""

import numpy as np
import pytest

from trailbuddy.core import sync, video
from trailbuddy.core.synthetic import clap_audio, render_frames, synthetic_descent


@pytest.mark.parametrize("ca,cb", [(1.20, 0.45), (0.50, 2.10), (1.0, 1.0)])
def test_audio_clap_offset_known(ca, cb):
    sr = 16000
    a = clap_audio(4.0, [ca], sr, seed=1)
    b = clap_audio(4.0, [cb], sr, seed=2)
    res = sync.sync_audio(a, b, sr)
    assert res.offset_s == pytest.approx(ca - cb, abs=0.005)
    assert res.confidence is not None and res.confidence >= sync.CONF_MIN
    assert res.note == ""


def test_clap_detection_ignores_low_frequency_footsteps():
    a = clap_audio(5.0, [3.3], 16000)
    det = sync.detect_clap(a, 16000)
    assert det.time_s == pytest.approx(3.3, abs=0.005)


def test_low_confidence_warning_for_pure_noise():
    rng = np.random.default_rng(0)
    noise = (0.05 * rng.normal(size=16000 * 3)).astype(np.float32)
    det = sync.detect_clap(noise, 16000)
    assert not det.is_reliable


def test_search_window_selects_correct_clap():
    a = clap_audio(6.0, [1.0, 4.0], 16000)
    det = sync.detect_clap(a, 16000, search=(3.0, 6.0))
    assert det.time_s == pytest.approx(4.0, abs=0.005)


def test_manual_sync_different_fps():
    r = sync.sync_manual(frame_a=72, fps_a=60.0, frame_b=30, fps_b=30.0)
    assert r.offset_s == pytest.approx(1.2 - 1.0)


def test_common_window_and_errors():
    assert sync.common_window(10.0, 8.0, 1.5) == (1.5, 9.5)
    assert sync.common_window(10.0, 8.0, -1.0) == (0.0, 7.0)
    with pytest.raises(ValueError):
        sync.common_window(2.0, 2.0, 5.0)


def test_resample_between_frame_rates():
    t30 = np.arange(0, 1, 1 / 30)
    t60 = np.arange(0, 1, 1 / 60)
    y = np.sin(t30)
    out = sync.resample_to(t30, y, t60)
    ok = ~np.isnan(out)
    assert np.allclose(out[ok], np.sin(t60[ok]), atol=1e-3)


@pytest.fixture(scope="module")
def synth_videos(tmp_path_factory):
    """Two synthetic recordings of the same motion: 60 fps (clap at 1.0 s) and 30 fps (clap at 0.4 s)."""
    d = tmp_path_factory.mktemp("vids")
    pose60, truth = synthetic_descent(duration=3.0, fps=60, width=640, img_height=480, px_per_m=200)
    pose30, _ = synthetic_descent(duration=3.0, fps=30, width=640, img_height=480, px_per_m=200)
    sr = 16000
    va = video.write_video(render_frames(pose60, truth.pole_tip_px), d / "camA.mp4", 60,
                           clap_audio(3.0, [1.0], sr), sr)
    vb = video.write_video(render_frames(pose30), d / "camB.mp4", 30, clap_audio(3.0, [0.4], sr, seed=5), sr)
    return va, vb, truth


def test_probe_and_audio_roundtrip(synth_videos):
    va, vb, _ = synth_videos
    ia, ib = video.probe(va), video.probe(vb)
    assert ia.fps == pytest.approx(60) and ib.fps == pytest.approx(30)
    assert ia.has_audio and ib.has_audio
    assert ia.width == 640 and ia.height == 480
    assert ia.n_frames == pytest.approx(180, abs=2)


def test_sync_from_encoded_video_files(synth_videos):
    va, vb, _ = synth_videos
    aa, sr = video.extract_audio(va)
    ab, _ = video.extract_audio(vb)
    res = sync.sync_audio(aa, ab, sr)
    # AAC encoder priming can shift each track by a few ms; require < half a 60 fps frame.
    assert res.offset_s == pytest.approx(0.6, abs=0.008)


def test_trim_is_non_destructive(synth_videos, tmp_path):
    va, _, _ = synth_videos
    before = va.read_bytes()
    out = video.trim(va, tmp_path / "clip.mp4", 0.5, 1.5)
    assert va.read_bytes() == before
    info = video.probe(out)
    assert info.duration == pytest.approx(1.0, abs=0.05)
    with pytest.raises(video.VideoError):
        video.trim(va, va, 0, 1)
    with pytest.raises(video.VideoError):
        video.trim(va, tmp_path / "bad.mp4", 1.0, 0.5)


def test_frame_reader_random_access(synth_videos):
    va, _, _ = synth_videos
    r = video.FrameReader(va)
    f10 = r.read(10)
    assert f10 is not None and f10.shape == (480, 640, 3)
    assert r.read(-1) is None and r.read(10_000) is None
    r.close()


def test_invalid_files(tmp_path):
    with pytest.raises(video.VideoError):
        video.probe(tmp_path / "missing.mp4")
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(video.VideoError):
        video.probe(bad)


def test_video_without_audio_reports_clearly(tmp_path):
    pose, _ = synthetic_descent(duration=0.5, fps=30, width=320, img_height=240, px_per_m=100)
    v = video.write_video(render_frames(pose), tmp_path / "silent.mp4", 30)
    assert not video.probe(v).has_audio
    with pytest.raises(video.VideoError, match="manual"):
        video.extract_audio(v)
