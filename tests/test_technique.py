"""Pole-technique classification on constructed event tables."""

import pandas as pd

from trailbuddy.core.technique import analyse_technique


def ev(rows):
    return pd.DataFrame(rows, columns=["event", "start_s", "end_s", "duration_s"])


def strikes(times, sides):
    return [{"event": f"{s}_foot_strike", "start_s": t, "end_s": t, "duration_s": 0} for t, s in zip(times, sides)]


def plants(times, side):
    return [{"event": f"pole_{side}_contact", "start_s": t, "end_s": t + 0.4, "duration_s": 0.4} for t in times]


def test_alternating_planting_with_foot_strikes():
    st = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    e = ev(strikes(st, ["right", "left"] * 3) + plants([0.52, 1.52, 2.52], "left") + plants([1.02, 2.02, 3.02], "right"))
    tq = analyse_technique(e, {"left": 0.9, "right": 0.9}, True)
    assert tq.pattern == "alternating planting" and tq.lead_leg == "right"
    assert tq.timing_class_counts["with foot strike"] == 6 and tq.steps_without_pole_pct == 0
    assert tq.confidence > 0.8


def test_simultaneous_planting_and_missed_steps():
    st = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    e = ev(strikes(st, ["left", "right"] * 3) + plants([0.3, 1.3], "left") + plants([0.32, 1.33], "right"))
    tq = analyse_technique(e, {"left": 0.8, "right": 0.8}, True)
    assert tq.pattern.startswith("simultaneous")
    assert tq.timing_class_counts["early (before foot)"] == 4
    assert tq.steps_without_pole_pct == 50.0  # 2.0, 2.5 and 3.0 s have no plant nearby


def test_no_poles_and_no_plants():
    assert analyse_technique(ev(strikes([1.0], ["left"])), {}, False).pattern == "no poles (condition)"
    tq = analyse_technique(ev(strikes([1.0], ["left"])), {"left": 0.1}, True)
    assert tq.pattern == "no pole plants detected" and tq.confidence == 0
