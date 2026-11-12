"""Signal conditioning: gap filling, zero-lag Butterworth filtering, differentiation."""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt


def fill_gaps(y: np.ndarray, max_gap: int) -> tuple[np.ndarray, np.ndarray]:
    """Linearly interpolate NaN gaps no longer than ``max_gap`` samples.

    Returns (filled, was_interpolated). Longer gaps and leading/trailing NaNs stay NaN,
    so the software never invents coordinates across long tracking dropouts.
    """
    y = np.asarray(y, dtype=float).copy()
    interp = np.zeros(len(y), dtype=bool)
    nan = np.isnan(y)
    if not nan.any() or nan.all():
        return y, interp
    i = 0
    n = len(y)
    while i < n:
        if nan[i]:
            j = i
            while j < n and nan[j]:
                j += 1
            if i > 0 and j < n and (j - i) <= max_gap:
                y[i:j] = np.interp(np.arange(i, j), [i - 1, j], [y[i - 1], y[j]])
                interp[i:j] = True
            i = j
        else:
            i += 1
    return y, interp


def lowpass(y: np.ndarray, fs: float, cutoff: float, order: int = 2) -> np.ndarray:
    """Zero-lag (forward-backward) Butterworth low-pass filter.

    A 2nd-order filter applied forward and backward gives an effective 4th-order,
    zero-phase response (Winter, 2009). NaN segments are filtered piecewise; valid runs too
    short to filter (<= 3*filter order samples) are set to NaN rather than left unfiltered,
    because they would otherwise be differentiated raw.
    """
    y = np.asarray(y, dtype=float)
    out = y.copy()
    if cutoff <= 0 or cutoff >= fs / 2:
        return out
    b, a = butter(order, cutoff / (fs / 2))
    padlen = 3 * max(len(a), len(b))
    valid = ~np.isnan(y)
    # Find contiguous valid runs.
    edges = np.flatnonzero(np.diff(np.concatenate(([0], valid.astype(int), [0]))))
    for start, stop in zip(edges[::2], edges[1::2]):
        seg = y[start:stop]
        if len(seg) > padlen:
            out[start:stop] = filtfilt(b, a, seg)
        else:
            out[start:stop] = np.nan
    return out


def derivative(y: np.ndarray, dt: float) -> np.ndarray:
    """Central-difference derivative (NaN-propagating)."""
    y = np.asarray(y, dtype=float)
    if len(y) < 2:
        return np.full_like(y, np.nan)
    return np.gradient(y, dt)


def condition_xy(xy: np.ndarray, fs: float, cutoff: float, max_gap: int):
    """Gap-fill and filter an (n, k, 2) coordinate array. Returns (xy_filtered, interp_mask)."""
    out = np.full_like(xy, np.nan, dtype=float)
    mask = np.zeros(xy.shape[:2], dtype=bool)
    for k in range(xy.shape[1]):
        for c in range(2):
            filled, interp = fill_gaps(xy[:, k, c], max_gap)
            out[:, k, c] = lowpass(filled, fs, cutoff)
            mask[:, k] |= interp
    return out, mask
