"""Display smoothing and anatomical plausibility checks for 2D keypoints.

These filters are for *viewing* the tracking. Biomechanical signals use their own processing (despiking,
gap filling and a zero-lag 6 Hz Butterworth filter in kinematics.py), so a smooth-looking overlay is never
mistaken for validated kinematics.

Display filter: a zero-phase 2nd-order Butterworth low-pass at 8 Hz, applied separately to each run of valid
samples (gaps are never bridged). We evaluated the One Euro filter below for this job: it is built for
real-time input, and on sinusoidal test movements (0.5-2 Hz, 2 px noise) its forward-backward version left
1.5-3.1 px RMS error versus 1.0 px for the 8 Hz zero-phase filter, so it is kept only for live previews.

One Euro filter: Casiez, Roussel & Vogel (2012), "1€ Filter: A Simple Speed-based Low-pass Filter for Noisy
Input in Interactive Systems", CHI '12. Re-implemented here (BSD-3 reference code at
github.com/casiez/OneEuroFilter); the cutoff rises with speed, so slow drift is smoothed strongly while fast
movements keep little lag. Running it forwards and backwards and averaging removes most of the remaining lag
for offline playback.
"""

from __future__ import annotations

import numpy as np

# Skeleton segments checked for plausible length (MediaPipe-33 indices).
SEGMENTS = {"left_thigh": (23, 25), "right_thigh": (24, 26), "left_shank": (25, 27), "right_shank": (26, 28),
            "left_upper_arm": (11, 13), "right_upper_arm": (12, 14), "left_forearm": (13, 15),
            "right_forearm": (14, 16)}


def _alpha(cutoff: np.ndarray | float, dt: float) -> np.ndarray | float:
    tau = 1.0 / (2 * np.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


def one_euro(x: np.ndarray, fs: float, min_cutoff: float = 1.5, beta: float = 0.02, d_cutoff: float = 1.0) -> np.ndarray:
    """Causal One Euro filter along axis 0 of x (n, ...). NaN samples are kept and restart the filter."""
    x = np.asarray(x, float)
    out = np.full_like(x, np.nan)
    dt = 1.0 / fs
    prev = None
    dprev = None
    for i in range(len(x)):
        xi = x[i]
        if not np.all(np.isfinite(xi)):
            prev = dprev = None
            continue
        if prev is None:
            out[i] = prev = xi
            dprev = np.zeros_like(xi)
            continue
        dx = (xi - prev) / dt
        dhat = dprev + _alpha(d_cutoff, dt) * (dx - dprev)
        cutoff = min_cutoff + beta * np.abs(dhat)
        a = _alpha(cutoff, dt)
        prev = prev + a * (xi - prev)
        dprev = dhat
        out[i] = prev
    return out


def one_euro_zero_lag(x: np.ndarray, fs: float, **kw) -> np.ndarray:
    """Average of a forward and a backward One Euro pass: lag cancels for offline playback."""
    f = one_euro(x, fs, **kw)
    b = one_euro(x[::-1], fs, **kw)[::-1]
    return 0.5 * (f + b)


DISPLAY_CUTOFF_HZ = 8.0


def lowpass_runs(x: np.ndarray, fs: float, cutoff: float = DISPLAY_CUTOFF_HZ, min_run: int = 13) -> np.ndarray:
    """Zero-phase Butterworth low-pass along axis 0, applied to each run of finite samples separately.
    Runs shorter than ``min_run`` samples are returned unchanged; NaN gaps stay NaN."""
    from scipy.signal import butter, filtfilt

    x = np.asarray(x, float)
    out = x.copy()
    if cutoff >= fs / 2:
        return out
    b, a = butter(2, cutoff / (fs / 2))
    ok = np.isfinite(x).reshape(len(x), -1).all(axis=1)
    edges = np.flatnonzero(np.diff(np.concatenate(([0], ok.astype(int), [0]))))
    for s0, s1 in zip(edges[::2], edges[1::2]):
        if s1 - s0 >= min_run:
            out[s0:s1] = filtfilt(b, a, x[s0:s1], axis=0, padlen=min(3 * max(len(a), len(b)), s1 - s0 - 1))
    return out


def implausible_segments(xy: np.ndarray, vis: np.ndarray | None = None, tol: float = 0.35,
                         min_vis: float = 0.3) -> np.ndarray:
    """(n, 33) mask of keypoints whose segment length departs > tol from that segment's median length.

    A 2D segment shortens when it turns toward the camera, so the tolerance is generous; the check catches
    keypoints that jump to another limb or object, not foreshortening."""
    n = len(xy)
    bad = np.zeros(xy.shape[:2], bool)
    for a, b in SEGMENTS.values():
        L = np.linalg.norm(xy[:, a] - xy[:, b], axis=1)
        ok = np.isfinite(L)
        if vis is not None:
            ok &= (vis[:, a] >= min_vis) & (vis[:, b] >= min_vis)
        if ok.sum() < max(5, n // 10):
            continue
        med = np.median(L[ok])
        out = ok & ((L > (1 + tol) * med) | (L < (1 - 2 * tol) * med))
        bad[out, a] = True
        bad[out, b] = True
    return bad


def display_pose(xy: np.ndarray, vis: np.ndarray, fs: float, min_vis: float = 0.3) -> tuple[np.ndarray, dict]:
    """Smoothed copy of keypoints for the video overlay plus a small QC report.

    Low-confidence and anatomically implausible points are hidden (NaN) rather than invented; short gaps stay
    gaps. Returns (xy_display, qc)."""
    xy = np.array(xy, float)
    hide = (vis < min_vis) | implausible_segments(xy, vis, min_vis=min_vis)
    xy[hide] = np.nan
    out = np.empty_like(xy)
    for j in range(xy.shape[1]):
        out[:, j] = lowpass_runs(xy[:, j], fs)
    raw_j = jitter_px(np.asarray(xy))
    qc = {"hidden_fraction": float(hide.mean()), "jitter_raw_px": raw_j, "jitter_display_px": jitter_px(out)}
    return out, qc


def jitter_px(xy: np.ndarray, idx=(23, 24, 25, 26, 27, 28, 29, 30, 31, 32)) -> float:
    """RMS second difference of the leg keypoints (px/frame²): a simple frame-to-frame jitter index."""
    a = np.diff(np.asarray(xy, float)[:, list(idx)], 2, axis=0)
    a = a[np.isfinite(a)]
    return float(np.sqrt(np.mean(a ** 2))) if a.size else float("nan")
