"""Surface EMG: import, standard processing, and normalisation to a maximal voluntary contraction (%MVC).

Processing (SENIAM-style, as in e.g. pyemgpipeline and the Visual3D EMG notes):
  1. remove the DC offset;
  2. band-pass 20-450 Hz (4th-order zero-lag Butterworth; upper edge limited to 0.45 x sampling rate);
  3. full-wave rectification;
  4. linear envelope: moving RMS over 50 ms, then a 6 Hz zero-lag low-pass.
MVC value for a channel = the largest 0.5 s moving average of that channel's envelope in its MVC trial.
%MVC = 100 x envelope / MVC value. Sampling below 500 Hz skips the band-pass (and is flagged): such data are
already envelopes from the recording system.

CSV format: a ``time_s`` column, then one column per muscle (any name, e.g. vastus_lateralis, triceps,
anterior_deltoid), in the units of the recording system. The EMG clock is aligned to the video with an offset
(t_video = t_emg + offset), like force data.

EMG shows how hard a muscle works relative to its maximum; it is not a force and cannot be converted to one
without a calibrated musculoskeletal model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class EmgData:
    t: np.ndarray
    fs: float
    channels: dict[str, np.ndarray] = field(default_factory=dict)
    source: str = ""


def load_emg_csv(path: str | Path) -> EmgData:
    df = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in df.columns}
    if "time_s" not in cols:
        raise ValueError("EMG file must have a 'time_s' column.")
    t = df[cols["time_s"]].to_numpy(float)
    if len(t) < 10 or np.any(np.diff(t) <= 0):
        raise ValueError("EMG time_s must be strictly increasing with at least 10 samples.")
    ch = {k.strip().lower().replace(" ", "_"): df[c].to_numpy(float) for k, c in cols.items() if k != "time_s"}
    if not ch:
        raise ValueError("No EMG channels found (one column per muscle after time_s).")
    return EmgData(t, 1.0 / float(np.median(np.diff(t))), ch, str(path))


def envelope(x: np.ndarray, fs: float, rms_window_s: float = 0.05, lp_hz: float = 6.0) -> np.ndarray:
    from scipy.signal import butter, filtfilt

    x = np.asarray(x, float) - np.nanmean(x)
    if fs >= 500:
        hi = min(450.0, 0.45 * fs)
        b, a = butter(4, [20.0 / (fs / 2), hi / (fs / 2)], btype="band")
        x = filtfilt(b, a, x)
    x = np.abs(x)
    w = max(1, int(round(rms_window_s * fs)))
    rms = np.sqrt(np.convolve(x ** 2, np.ones(w) / w, mode="same"))
    if lp_hz < fs / 2:
        b, a = butter(2, lp_hz / (fs / 2))
        rms = filtfilt(b, a, rms)
    return np.maximum(rms, 0.0)


def mvc_value(x: np.ndarray, fs: float, window_s: float = 0.5) -> float:
    """Largest 0.5 s moving average of the envelope in an MVC trial."""
    env = envelope(x, fs)
    w = max(1, int(round(window_s * fs)))
    if len(env) < w:
        return float(np.max(env))
    return float(np.max(np.convolve(env, np.ones(w) / w, mode="valid")))


def mvc_from_file(path: str | Path) -> dict[str, float]:
    d = load_emg_csv(path)
    return {k: mvc_value(v, d.fs) for k, v in d.channels.items()}


def percent_mvc(d: EmgData, mvc: dict[str, float], t_video: np.ndarray, offset_s: float = 0.0) -> dict[str, np.ndarray]:
    """%MVC envelope of each channel that has an MVC value, resampled onto the video clock."""
    out = {}
    for k, v in d.channels.items():
        if k in mvc and mvc[k] > 0:
            env = 100.0 * envelope(v, d.fs) / mvc[k]
            out[k] = np.interp(t_video, d.t + offset_s, env, left=np.nan, right=np.nan)
    return out
