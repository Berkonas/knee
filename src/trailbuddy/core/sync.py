"""Clap-based synchronization of two recordings.

Automatic method
----------------
1. Decode each audio track (mono, 16 kHz).
2. High-pass filter (> 1 kHz) to emphasise the broadband, impulsive clap over speech and
   footsteps, then compute a short-window (2.5 ms hop) RMS energy envelope.
3. Onset strength = positive first difference of the log-energy envelope.
4. The clap is the strongest onset in the search window. Confidence = peak / 99th percentile of
   the rest of the envelope, so the user is warned when the clap does not stand out.
5. The offset is refined by cross-correlating the two envelopes within +-0.25 s of the coarse
   estimate, giving sub-frame resolution (envelope hop 2.5 ms).

Convention: ``offset_s = clap_time_A - clap_time_B``. A moment at time t_B in video B
occurs at t_A = t_B + offset_s in video A.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfiltfilt

HOP_S = 0.0025
CONF_MIN = 3.0  # empirically: pure noise ~1-2, clear clap >> 5


@dataclass
class ClapDetection:
    time_s: float
    confidence: float  # clap peak / 99th percentile of the rest of the envelope
    envelope: np.ndarray
    hop_s: float = HOP_S

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= CONF_MIN


@dataclass
class SyncResult:
    offset_s: float
    method: str  # "audio" or "manual"
    clap_a_s: float
    clap_b_s: float
    confidence: float | None = None
    note: str = ""

    def b_to_a(self, t_b):
        return np.asarray(t_b) + self.offset_s

    def a_to_b(self, t_a):
        return np.asarray(t_a) - self.offset_s


def onset_envelope(audio: np.ndarray, sr: int, hop_s: float = HOP_S) -> np.ndarray:
    if len(audio) < sr * 0.05:
        raise ValueError("Audio is too short for clap detection.")
    sos = butter(4, 1000 / (sr / 2), btype="highpass", output="sos")
    x = sosfiltfilt(sos, audio.astype(float))
    hop = max(1, int(round(hop_s * sr)))
    win = hop * 2
    n = (len(x) - win) // hop + 1
    frames = np.lib.stride_tricks.sliding_window_view(x, win)[::hop][:n]
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    loge = 20 * np.log10(rms + 1e-9)
    onset = np.maximum(np.diff(loge, prepend=loge[0]), 0)
    return onset * rms / (rms.max() + 1e-12)  # weight by loudness: clap is loud AND sudden


def detect_clap(audio: np.ndarray, sr: int, search: tuple[float, float] | None = None) -> ClapDetection:
    env = onset_envelope(audio, sr)
    lo, hi = 0, len(env)
    if search is not None:
        lo = max(0, int(search[0] / HOP_S))
        hi = min(len(env), int(search[1] / HOP_S))
        if hi - lo < 4:
            raise ValueError("Clap search window is empty.")
    seg = env[lo:hi]
    k = int(np.argmax(seg))
    # Confidence: clap peak relative to the 99th percentile of the envelope away from the peak
    # (a clap must stand out from everything else in the search window).
    guard = int(0.2 / HOP_S)
    rest = np.concatenate([seg[: max(0, k - guard)], seg[k + guard:]])
    ref = float(np.percentile(rest, 99)) if len(rest) > 10 else 0.0
    conf = float(seg[k] / (ref + 1e-9)) if ref > 0 else float("inf")
    conf = min(conf, 1000.0)
    return ClapDetection(time_s=(lo + k) * HOP_S, confidence=conf, envelope=env)


def refine_offset(env_a: np.ndarray, env_b: np.ndarray, coarse_offset: float,
                  window_s: float = 0.25) -> float:
    """Cross-correlate envelopes near the coarse offset; returns refined offset (s)."""
    lag_max = int(window_s / HOP_S)
    c = int(round(coarse_offset / HOP_S))
    # shift B by coarse offset, then search small residual lag
    best, best_lag = -np.inf, 0
    a = (env_a - env_a.mean()) / (env_a.std() + 1e-12)
    b = (env_b - env_b.mean()) / (env_b.std() + 1e-12)
    for lag in range(c - lag_max, c + lag_max + 1):
        if lag >= 0:
            aa, bb = a[lag:], b[: len(a) - lag]
        else:
            aa, bb = a[: len(b) + lag], b[-lag:]
        m = min(len(aa), len(bb))
        if m < 10:
            continue
        v = float(np.dot(aa[:m], bb[:m]) / m)
        if v > best:
            best, best_lag = v, lag
    return best_lag * HOP_S


def sync_audio(audio_a: np.ndarray, audio_b: np.ndarray, sr: int,
               search_a: tuple[float, float] | None = None,
               search_b: tuple[float, float] | None = None) -> SyncResult:
    da = detect_clap(audio_a, sr, search_a)
    db = detect_clap(audio_b, sr, search_b)
    coarse = da.time_s - db.time_s
    refined = refine_offset(da.envelope, db.envelope, coarse)
    conf = min(da.confidence, db.confidence)
    note = "" if conf >= CONF_MIN else ("Clap is not clearly louder than background noise in at least one "
                                 "recording. Check alignment visually or use manual clap frames.")
    if abs(refined - coarse) > 0.05:
        note += " Envelope cross-correlation disagrees with clap peaks by >50 ms; verify manually."
    return SyncResult(refined, "audio", da.time_s, db.time_s, conf, note.strip())


def sync_manual(frame_a: int, fps_a: float, frame_b: int, fps_b: float) -> SyncResult:
    """Offset from user-identified clap frames (hands first touching) in each video."""
    ta, tb = frame_a / fps_a, frame_b / fps_b
    return SyncResult(ta - tb, "manual", ta, tb, None,
                      f"Manual sync; resolution limited to ~1 frame ({1000 / min(fps_a, fps_b):.0f} ms).")


def common_window(dur_a: float, dur_b: float, offset_s: float) -> tuple[float, float]:
    """Overlapping interval of both recordings, in video A's clock."""
    start = max(0.0, offset_s)
    end = min(dur_a, dur_b + offset_s)
    if end <= start:
        raise ValueError("The two recordings do not overlap after synchronization.")
    return start, end


def resample_to(t_src: np.ndarray, y_src: np.ndarray, t_dst: np.ndarray, max_gap_s: float = 0.1) -> np.ndarray:
    """Linear resampling onto another time base (handles different frame rates).

    NaN outside the source range and wherever the bracketing valid source samples are more than
    ``max_gap_s`` apart, so tracking dropouts are never bridged with invented values.
    """
    y_src = np.asarray(y_src, float)
    out = np.full(t_dst.shape + y_src.shape[1:], np.nan)
    flat_src = y_src.reshape(len(t_src), -1)
    flat_out = out.reshape(len(t_dst), -1)
    for j in range(flat_src.shape[1]):
        v = flat_src[:, j]
        ok = ~np.isnan(v)
        if ok.sum() >= 2:
            ts = t_src[ok]
            y = np.interp(t_dst, ts, v[ok], left=np.nan, right=np.nan)
            k = np.clip(np.searchsorted(ts, t_dst), 1, len(ts) - 1)
            gap = ts[k] - ts[k - 1]
            y[gap > max_gap_s + 1e-9] = np.nan
            flat_out[:, j] = y
    return flat_out.reshape(out.shape)
