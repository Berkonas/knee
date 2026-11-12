"""Synthetic data with known ground truth, for tests and the built-in demo.

``synthetic_descent`` builds a 2D stick figure descending stairs with prescribed joint angles via
forward kinematics, so angle and event algorithms can be checked against exact values.
``render_video`` draws it (plus an optional coloured pole-tip marker) and can embed an audio clap
at a known time for synchronization tests. These are test fixtures, not human recordings, and
MediaPipe is not expected to detect the stick figure.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .landmarks import N_LANDMARKS, PoseSeries, idx


@dataclass
class SyntheticTruth:
    t: np.ndarray
    knee_flexion: dict[str, np.ndarray]
    hip_flexion: dict[str, np.ndarray]
    trunk_lean: np.ndarray
    elbow_flexion: np.ndarray
    shoulder_flexion: np.ndarray
    contacts: dict[str, list[tuple[float, float]]]
    scale_m_per_px: float
    pole_tip_px: np.ndarray


def synthetic_descent(duration: float = 4.0, fps: float = 60.0, height_m: float = 1.75,
                      step_time: float = 0.8, step_height: float = 0.17, step_depth: float = 0.28,
                      px_per_m: float = 400.0, width: int = 1280, img_height: int = 960,
                      noise_px: float = 0.0, seed: int = 0) -> tuple[PoseSeries, SyntheticTruth]:
    """Planar stick figure descending stairs (walking toward +image-x).

    Each foot is planted on a tread for one ``step_time`` (stance) out of a two-step cycle; the
    knee flexes during stance as the body lowers. Joint angles are generated directly, then
    landmarks are placed by forward kinematics with Winter segment lengths.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(0, duration, 1 / fps)
    n = len(t)
    H = height_m
    L_th, L_sh, L_ft = 0.245 * H, 0.246 * H, 0.152 * H
    L_tr, L_ua, L_fa = 0.30 * H, 0.186 * H, 0.146 * H
    cyc = 2 * step_time
    xy = np.full((n, N_LANDMARKS, 2), np.nan)
    truth_k, truth_h, contacts = {}, {}, {"left": [], "right": []}
    phase0 = {"right": 0.0, "left": step_time}
    # body progresses one tread per step
    v = step_depth / step_time
    hip_x = 0.3 + v * t
    hip_y = 1.4 - (step_height / step_time) * t + 0.03 * np.cos(2 * np.pi * t / step_time)
    lean = 8 + 4 * np.sin(2 * np.pi * t / step_time)
    trunk_th = np.radians(90 - lean)
    sh = np.stack([hip_x + L_tr * np.cos(trunk_th), hip_y + L_tr * np.sin(trunk_th)], axis=1)
    hip = np.stack([hip_x, hip_y], axis=1)
    L_leg = L_th + L_sh
    for side in ("right", "left"):
        # Foot plants: one per stance, centred under the hip at mid-stance and 0.85 leg lengths below.
        plants, windows = [], []
        k = -1
        while True:
            a0 = phase0[side] + k * cyc
            if a0 > duration + cyc:
                break
            a1 = a0 + step_time
            tm = 0.5 * (a0 + a1)
            hx = 0.3 + v * tm
            hy = 1.4 - (step_height / step_time) * tm
            plants.append(np.array([hx, hy - 0.85 * L_leg]))
            windows.append((a0, a1))
            if 0 <= a0 and a1 <= duration:
                contacts[side].append((a0, a1))
            elif a0 < 0 < a1:
                contacts[side].append((0.0, a1))
            k += 1
        ankle = np.zeros((n, 2))
        stance_m = np.zeros(n, bool)
        for (a0, a1), pa, pb in zip(windows, plants, plants[1:] + [plants[-1]]):
            m = (t >= a0) & (t < a1)
            ankle[m] = pa
            stance_m |= m
            # swing toward the next plant, lifted along a sine arc
            sw = (t >= a1) & (t < a1 + step_time)
            u = (t[sw] - a1) / step_time
            ankle[sw] = pa + (pb - pa) * u[:, None] + np.stack([0 * u, 0.10 * np.sin(np.pi * u)], axis=1)
        # inverse kinematics: knee anterior to the hip-ankle line
        dvec = ankle - hip
        d = np.minimum(np.linalg.norm(dvec, axis=1), 0.995 * L_leg)
        cos_int = (L_th**2 + L_sh**2 - d**2) / (2 * L_th * L_sh)
        kf = 180 - np.degrees(np.arccos(np.clip(cos_int, -1, 1)))
        # angle at hip between hip->ankle line and thigh
        cos_h = (L_th**2 + d**2 - L_sh**2) / (2 * L_th * d)
        beta = np.arccos(np.clip(cos_h, -1, 1))
        phi = np.arctan2(dvec[:, 1], dvec[:, 0])
        th = phi + beta  # rotate toward +x (anterior knee) for a downward-pointing line
        knee = hip + L_th * np.stack([np.cos(th), np.sin(th)], axis=1)
        ankle = knee + L_sh * np.stack([np.cos(phi + beta - np.radians(kf)), np.sin(phi + beta - np.radians(kf))], axis=1)
        th_thigh = np.arctan2(hip[:, 1] - knee[:, 1], hip[:, 0] - knee[:, 0])
        hf = ((np.degrees(th_thigh) - (90 - lean)) + 180) % 360 - 180
        heel = ankle + np.array([-0.04 * H, -0.04 * H])
        toe = heel + np.array([L_ft, 0.0])
        lab = {"hip": hip, "knee": knee, "ankle": ankle, "heel": heel, "foot_index": toe}
        truth_k[side] = kf
        truth_h[side] = hf
        for nm, arr in lab.items():
            xy[:, idx(side, nm)] = arr
        # arms: shoulder flexion & elbow flexion prescribed (right arm only meaningful)
        sf = np.radians(20 + 10 * np.sin(2 * np.pi * t / cyc))
        ef = np.radians(70.0 + 0 * t)
        down = trunk_th + np.pi  # trunk pointing down
        ua_th = down + sf
        elbow = sh + L_ua * np.stack([np.cos(ua_th), np.sin(ua_th)], axis=1)
        fa_th = ua_th + ef  # forearm rotates forward (CCW) by elbow flexion
        wrist = elbow + L_fa * np.stack([np.cos(fa_th), np.sin(fa_th)], axis=1)
        for nm, arr in (("shoulder", sh), ("elbow", elbow), ("wrist", wrist), ("index", wrist)):
            xy[:, idx(side, nm)] = arr
    xy[:, 0] = sh + np.array([0.03, 0.25])  # nose
    # lab (m) -> image pixels (y down)
    img = np.empty_like(xy)
    img[..., 0] = xy[..., 0] * px_per_m
    img[..., 1] = img_height - xy[..., 1] * px_per_m - 50
    # undefined landmarks: copy nose so arrays are finite
    for i in range(N_LANDMARKS):
        if np.isnan(img[:, i]).all():
            img[:, i] = img[:, 0]
    if noise_px:
        img += rng.normal(0, noise_px, img.shape)
    vis = np.ones((n, N_LANDMARKS))
    # Right pole: tip follows the hand in swing and is planted (stationary) during right stance.
    tip = img[:, idx("right", "wrist")] + np.array([0.15 * px_per_m, 0.95 * px_per_m])
    for a0, a1 in contacts["right"]:
        m = (t >= a0) & (t < a1)
        if m.any():
            tip[m] = tip[np.flatnonzero(m)[0]]
    pose = PoseSeries(t, img, vis, fps, width, img_height, "synthetic")
    truth = SyntheticTruth(t, truth_k, truth_h, lean, np.full(n, 70.0),
                           np.degrees(sf), contacts, 1 / px_per_m, tip)
    return pose, truth


def clap_audio(duration: float, clap_times: list[float], sr: int = 16000, noise: float = 0.01,
               seed: int = 1) -> np.ndarray:
    """Background noise plus sharp broadband clap transients (exp. decay ~8 ms) at given times."""
    rng = np.random.default_rng(seed)
    a = noise * rng.normal(size=int(duration * sr)).astype(np.float32)
    for ct in clap_times:
        i0 = int(ct * sr)
        k = np.arange(int(0.05 * sr))
        burst = rng.normal(size=len(k)) * np.exp(-k / (0.008 * sr)) * 0.8
        a[i0:i0 + len(k)] += burst[: max(0, len(a) - i0)].astype(np.float32)
    # some low-frequency 'footstep' thumps that should not be mistaken for the clap
    for ft in np.arange(0.7, duration, 0.9):
        i0 = int(ft * sr)
        k = np.arange(int(0.06 * sr))
        a[i0:i0 + len(k)] += (0.3 * np.sin(2 * np.pi * 60 * k / sr) * np.exp(-k / (0.02 * sr)))[: max(0, len(a) - i0)]
    return np.clip(a, -1, 1)


def render_frames(pose: PoseSeries, marker_px: np.ndarray | None = None,
                  marker_bgr=(0, 140, 255), offset_frames: int = 0):
    """Yield BGR frames showing the stick figure (and a coloured pole-tip marker)."""
    from .landmarks import SKELETON

    for i in range(pose.n_frames):
        img = np.full((pose.height, pose.width, 3), 235, np.uint8)
        cv2.putText(img, f"frame {i + offset_frames}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (40, 40, 40), 2)
        p = pose.xy[i]
        for a, b in SKELETON:
            if np.isfinite(p[[a, b]]).all():
                cv2.line(img, tuple(p[a].astype(int)), tuple(p[b].astype(int)), (60, 60, 60), 6)
        if marker_px is not None and np.isfinite(marker_px[i]).all():
            cv2.line(img, tuple(p[16].astype(int)), tuple(marker_px[i].astype(int)), (90, 90, 90), 3)
            cv2.circle(img, tuple(marker_px[i].astype(int)), 9, marker_bgr, -1)
        yield img
