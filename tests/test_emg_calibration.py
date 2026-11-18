"""EMG %MVC processing and pole-force calibration (scale test -> inverse model)."""

import numpy as np
import pandas as pd
import pytest

from trailbuddy.core import analysis, emg
from trailbuddy.core.analysis import AnalysisSettings
from trailbuddy.core.anthropometry import G
from trailbuddy.core.calibration import fit_calibration, scale_pct_bw
from trailbuddy.core.forces import load_force_csv
from trailbuddy.core.synthetic import synthetic_descent


def burst(t, amp, rng):
    return amp * rng.normal(0, 1, t.size) * (np.sin(2 * np.pi * 1.0 * t) > 0)


def test_percent_mvc_scales_with_activation(tmp_path):
    fs, rng = 1000.0, np.random.default_rng(0)
    t = np.arange(0, 4, 1 / fs)
    pd.DataFrame({"time_s": t, "vastus_lateralis": rng.normal(0, 1.0, t.size)}).to_csv(tmp_path / "mvc.csv", index=False)
    pd.DataFrame({"time_s": t, "vastus_lateralis": burst(t, 0.5, rng)}).to_csv(tmp_path / "trial.csv", index=False)
    mvc = emg.mvc_from_file(tmp_path / "mvc.csv")
    d = emg.load_emg_csv(tmp_path / "trial.csv")
    pct = emg.percent_mvc(d, mvc, np.arange(0, 4, 1 / 60))["vastus_lateralis"]
    assert 35 < np.nanmax(pct) < 70  # half the MVC amplitude during bursts
    assert np.nanmin(pct) < 10


def test_calibration_inverse_recovers_force_and_reports_fit(tmp_path):
    kg = np.array([0, 5, 10, 15, 20])
    reading = 0.8 * kg * G + 120 + np.array([0.5, -0.3, 0.2, -0.4, 0.1])
    cal = fit_calibration(kg, reading)
    assert cal.r2 > 0.999 and cal.rmse_n < 1.0
    assert cal.to_force(0.8 * 100 + 120) == pytest.approx(100, abs=1)
    t = np.linspace(0, 1, 50)
    pd.DataFrame({"time_s": t, "pole_left_raw": 0.8 * 150 + 120}).to_csv(tmp_path / "f.csv", index=False)
    fd = load_force_csv(tmp_path / "f.csv", {"left": cal.as_dict()})
    assert fd.channels["pole_left"] == pytest.approx(np.full(50, 150), abs=1)
    with pytest.raises(ValueError):
        load_force_csv(tmp_path / "f.csv")
    with pytest.raises(ValueError):
        fit_calibration([1, 1, 1], [2, 3, 4])


def test_scale_pole_force_percent_body_weight():
    assert scale_pct_bw([7.0, 7.0], 70.0) == pytest.approx(10.0)
    assert scale_pct_bw([], 70.0) is None and scale_pct_bw([7.0], None) is None


def test_emg_metrics_in_analysis_are_labelled_measured(tmp_path):
    pose, truth = synthetic_descent(duration=3.0, fps=60, seed=2)
    fs, rng = 1000.0, np.random.default_rng(1)
    te = np.arange(0, 3, 1 / fs)
    d = emg.EmgData(te, fs, {"triceps": burst(te, 1.0, rng)})
    res = analysis.analyse(pose, 70.0, 1.75, AnalysisSettings(side="right"), emg=(d, {"triceps": 2.0}, 0.0))
    m = res.metric("emg_triceps_peak")
    assert m.kind == "measured" and m.value > 0 and "emg_triceps_pct_mvc" in res.timeseries
    analysis.save_result(res, tmp_path)
    assert analysis.load_result(tmp_path).metric("emg_triceps_stance_mean") is not None
