"""MediaPipe Pose landmark indices and a container for pose time series."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# MediaPipe Pose (BlazePose) 33-landmark topology.
LANDMARKS = {
    "nose": 0,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_index": 19, "right_index": 20,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
    "left_heel": 29, "right_heel": 30,
    "left_foot_index": 31, "right_foot_index": 32,
}
N_LANDMARKS = 33

# Skeleton edges drawn in overlays.
SKELETON = [
    (11, 12), (11, 23), (12, 24), (23, 24),
    (11, 13), (13, 15), (12, 14), (14, 16), (15, 19), (16, 20),
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
]


def idx(side: str, name: str) -> int:
    """Index of a sided landmark, e.g. idx('left', 'knee')."""
    return LANDMARKS[f"{side}_{name}"]


@dataclass
class PoseSeries:
    """Pose landmarks over time for one camera.

    xy: (n_frames, 33, 2) pixel coordinates (image convention, y down). NaN = not detected.
    visibility: (n_frames, 33) MediaPipe visibility score in [0, 1] (0 where not detected).
    t: (n_frames,) time in seconds on the source video's clock.
    """

    t: np.ndarray
    xy: np.ndarray
    visibility: np.ndarray
    fps: float
    width: int
    height: int
    source: str = ""
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.t = np.asarray(self.t, dtype=float)
        self.xy = np.asarray(self.xy, dtype=float)
        self.visibility = np.asarray(self.visibility, dtype=float)
        n = len(self.t)
        if self.xy.shape != (n, N_LANDMARKS, 2):
            raise ValueError(f"xy must have shape ({n}, {N_LANDMARKS}, 2), got {self.xy.shape}")
        if self.visibility.shape != (n, N_LANDMARKS):
            raise ValueError("visibility shape does not match xy")

    @property
    def n_frames(self) -> int:
        return len(self.t)

    def point(self, side: str, name: str) -> np.ndarray:
        return self.xy[:, idx(side, name), :]

    def detection_rate(self) -> float:
        """Fraction of frames in which a person was detected."""
        if self.n_frames == 0:
            return 0.0
        return float(np.mean(~np.isnan(self.xy[:, 0, 0])))

    def to_dataframe(self):
        import pandas as pd

        cols = {"time_s": self.t}
        names = {v: k for k, v in LANDMARKS.items()}
        for i in range(N_LANDMARKS):
            nm = names.get(i, f"lm{i}")
            cols[f"{nm}_x_px"] = self.xy[:, i, 0]
            cols[f"{nm}_y_px"] = self.xy[:, i, 1]
            cols[f"{nm}_vis"] = self.visibility[:, i]
        return pd.DataFrame(cols)

    @classmethod
    def from_dataframe(cls, df, fps: float, width: int, height: int, source: str = "") -> "PoseSeries":
        names = {v: k for k, v in LANDMARKS.items()}
        n = len(df)
        xy = np.full((n, N_LANDMARKS, 2), np.nan)
        vis = np.zeros((n, N_LANDMARKS))
        for i in range(N_LANDMARKS):
            nm = names.get(i, f"lm{i}")
            xy[:, i, 0] = df[f"{nm}_x_px"].to_numpy()
            xy[:, i, 1] = df[f"{nm}_y_px"].to_numpy()
            vis[:, i] = df[f"{nm}_vis"].to_numpy()
        return cls(df["time_s"].to_numpy(), xy, vis, fps, width, height, source)
