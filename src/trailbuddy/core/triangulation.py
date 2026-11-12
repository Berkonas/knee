"""Direct Linear Transformation (Abdel-Aziz & Karara, 1971) for two-camera 3D reconstruction.

Use only with a proper calibration: >= 6 non-coplanar control points with known 3D coordinates
(e.g. a measured frame or marked stair corners) visible in both cameras. Reconstruction accuracy
must be checked (``reprojection_error`` and a held-out known distance) before 3D angles are
reported. The app labels DLT output as "3D (calibrated, unvalidated)" until such checks pass.
"""

from __future__ import annotations

import numpy as np


def calibrate(world_xyz: np.ndarray, image_uv: np.ndarray) -> np.ndarray:
    """Solve the 11 DLT parameters for one camera. Returns L (11,)."""
    X = np.asarray(world_xyz, float)
    uv = np.asarray(image_uv, float)
    if len(X) < 6 or len(X) != len(uv):
        raise ValueError("DLT calibration needs at least 6 matching control points.")
    A, b = [], []
    for (x, y, z), (u, v) in zip(X, uv):
        A.append([x, y, z, 1, 0, 0, 0, 0, -u * x, -u * y, -u * z]); b.append(u)
        A.append([0, 0, 0, 0, x, y, z, 1, -v * x, -v * y, -v * z]); b.append(v)
    A = np.array(A); b = np.array(b)
    if np.linalg.matrix_rank(A) < 11:
        raise ValueError("Control points are degenerate (coplanar or collinear).")
    L, *_ = np.linalg.lstsq(A, b, rcond=None)
    return L


def project(L: np.ndarray, xyz: np.ndarray) -> np.ndarray:
    xyz = np.atleast_2d(xyz)
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    den = L[8] * x + L[9] * y + L[10] * z + 1
    u = (L[0] * x + L[1] * y + L[2] * z + L[3]) / den
    v = (L[4] * x + L[5] * y + L[6] * z + L[7]) / den
    return np.stack([u, v], axis=1)


def reconstruct(Ls: list[np.ndarray], uvs: list[np.ndarray]) -> np.ndarray:
    """Least-squares 3D point(s) from >= 2 calibrated views. uvs: list of (n,2); NaN-safe."""
    n = len(uvs[0])
    out = np.full((n, 3), np.nan)
    for i in range(n):
        A, b = [], []
        for L, uv in zip(Ls, uvs):
            u, v = uv[i]
            if np.isnan(u) or np.isnan(v):
                continue
            A.append([L[0] - u * L[8], L[1] - u * L[9], L[2] - u * L[10]]); b.append(u - L[3])
            A.append([L[4] - v * L[8], L[5] - v * L[9], L[6] - v * L[10]]); b.append(v - L[7])
        if len(A) >= 4:
            out[i], *_ = np.linalg.lstsq(np.array(A), np.array(b), rcond=None)
    return out


def reprojection_error(L: np.ndarray, world_xyz: np.ndarray, image_uv: np.ndarray) -> float:
    """RMS reprojection error in pixels."""
    d = project(L, world_xyz) - np.asarray(image_uv, float)
    return float(np.sqrt(np.mean(np.sum(d**2, axis=1))))
