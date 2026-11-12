"""Import externally measured forces (force plate, instrumented step, pole load cell).

CSV format (header row required, comma-separated):
  time_s, then any of:
    fz_n | fy_n | vertical_n  -> vertical ground reaction force (N, + up)
    fx_n | ap_n               -> horizontal force along the walking direction (N, + forward)
    cop_x_m                   -> COP along the walking direction (m) in the plate frame
    pole_left_n, pole_right_n -> pole axial forces (N, compression +)
The force recording's clock is aligned to the video with a user-entered offset
(t_video = t_force + offset_s), e.g. from a shared clap/impact event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ALIASES = {
    "vertical": ["fz_n", "fy_n", "vertical_n", "fz", "fy"],
    "horizontal": ["fx_n", "ap_n", "fx"],
    "cop_x": ["cop_x_m", "copx", "cop_x"],
    "pole_left": ["pole_left_n", "pole_l_n"],
    "pole_right": ["pole_right_n", "pole_r_n"],
}


@dataclass
class ForceData:
    t: np.ndarray
    channels: dict[str, np.ndarray] = field(default_factory=dict)
    source: str = ""

    def resample(self, t_video: np.ndarray, offset_s: float = 0.0) -> dict[str, np.ndarray]:
        tt = self.t + offset_s
        return {k: np.interp(t_video, tt, v, left=np.nan, right=np.nan) for k, v in self.channels.items()}


def load_force_csv(path: str | Path) -> ForceData:
    df = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in df.columns}
    if "time_s" not in cols:
        raise ValueError("Force file must have a 'time_s' column.")
    t = df[cols["time_s"]].to_numpy(float)
    if np.any(np.diff(t) <= 0):
        raise ValueError("Force file time_s must be strictly increasing.")
    ch = {}
    for key, names in ALIASES.items():
        for nm in names:
            if nm in cols:
                ch[key] = df[cols[nm]].to_numpy(float)
                break
    if not ch:
        raise ValueError("No recognised force columns. Expected e.g. fz_n, fx_n, cop_x_m, pole_left_n.")
    return ForceData(t, ch, str(path))
