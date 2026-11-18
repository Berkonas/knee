"""Pole-force calibration against a scale.

1. Sensor calibration: press a pole onto a scale at several forces and note the sensor reading at each. Fit
   reading = a·F + b by least squares, with F = scale reading (kg) × g. During trials, the inverse model
   F = (reading − b) / a converts raw sensor readings to newtons. Columns pole_left_raw / pole_right_raw in a force
   CSV are converted this way.

2. Scale-based scenario (no sensor): each participant pushes a pole onto a scale the way they would plant it
   during descent, and the readings are entered in kg. The mean, as a percentage of body weight, becomes that
   participant's scenario pole force. It stays a *scenario*: it shows typical effort, not the force in each trial.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .anthropometry import G


@dataclass
class PoleCalibration:
    a: float          # sensor units per newton
    b: float          # sensor reading at zero force
    r2: float
    rmse_n: float     # residual error of the inverse model, newtons
    n: int

    def to_force(self, reading):
        return (np.asarray(reading, float) - self.b) / self.a

    def as_dict(self) -> dict:
        return asdict(self)


def fit_calibration(scale_kg, readings) -> PoleCalibration:
    f = np.asarray(scale_kg, float) * G
    r = np.asarray(readings, float)
    ok = np.isfinite(f) & np.isfinite(r)
    f, r = f[ok], r[ok]
    if len(f) < 3 or np.ptp(f) <= 0:
        raise ValueError("Need at least 3 calibration points at different forces.")
    a, b = np.polyfit(f, r, 1)
    if abs(a) < 1e-12:
        raise ValueError("The sensor reading does not change with force; check the sensor.")
    pred = a * f + b
    ss = float(np.sum((r - r.mean()) ** 2))
    r2 = 1 - float(np.sum((r - pred) ** 2)) / ss if ss > 0 else 0.0
    rmse_n = float(np.sqrt(np.mean(((r - b) / a - f) ** 2)))
    return PoleCalibration(float(a), float(b), r2, rmse_n, int(len(f)))


def scale_pct_bw(readings_kg, body_mass_kg: float | None) -> float | None:
    """Mean scale reading while pushing a pole, as % body weight (None without body mass or readings)."""
    v = [x for x in (readings_kg or []) if x is not None and x > 0]
    if not v or not body_mass_kg:
        return None
    return 100.0 * float(np.mean(v)) / body_mass_kg
