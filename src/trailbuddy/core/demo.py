"""Demo study built from SYNTHETIC stick-figure data (no real participants).

Purpose: let users explore the Results page and exports before real recordings exist. The
numbers are artefacts of the synthetic motion and the pole-force scenario, not findings.
"""

from __future__ import annotations

from pathlib import Path

from . import analysis
from .analysis import AnalysisSettings
from .pole import PoleTrack
from .project import Participant, Project, Trial
from .synthetic import synthetic_descent

DEMO_PEOPLE = [("P01", 68.0, 1.72), ("P02", 81.0, 1.83), ("P03", 59.0, 1.65)]


def build_demo_project(root: str | Path) -> Project:
    pr = Project.new(root, "Demo (synthetic data - not real results)", "exp1")
    seed = 0
    for pid, mass, h in DEMO_PEOPLE:
        pr.add_participant(Participant(pid, mass, h, standard_pole_length_cm=round(0.68 * h * 100),
                                       notes="synthetic"))
    for pid, mass, h in DEMO_PEOPLE:
        for code in ("C0", "C1"):
            uses = code == "C1"
            for k in (1, 2, 3):
                tr = pr.add_trial(Trial(pid, code, k, notes="synthetic demo trial",
                                        stair={"step_height_m": 0.17, "n_steps": 4}))
                lean_bias = 0.0
                pose, truth = synthetic_descent(duration=4.0, fps=60, height_m=h, noise_px=0.8, seed=seed,
                                                step_time=0.8 + 0.02 * (seed % 3) + (0.04 if uses else 0.0))
                seed += 1
                s = AnalysisSettings(side="right", scale_method="points", scale_m_per_px=truth.scale_m_per_px,
                                     pole_force_mode="scenario" if uses else "none", pole_pct_bw=10.0,
                                     descent_height_m=0.68 + lean_bias)
                poles = {"right": PoleTrack(pose.t, truth.pole_tip_px)} if uses else None
                res = analysis.analyse(pose, mass, h, s, uses, poles)
                res.notes.insert(0, "SYNTHETIC DEMO DATA - not a human recording.")
                analysis.save_result(res, pr.trial_dir(tr.id), {"trial": tr.id, "synthetic": True})
                tr.status = "analysed"
    pr.save()
    return pr
