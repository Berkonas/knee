"""Study-level data-quality checks shown on the Study dashboard and in exports.

'Analysed' only means the pipeline ran. These checks say whether the inputs and tracking behind a trial
support the numbers it reports.
"""

from __future__ import annotations

import json
from pathlib import Path


def trial_checks(project, t) -> list[tuple[str, str]]:
    """(level, message) for one trial; level is 'error', 'warn' or 'info'."""
    out = []
    cond = next((c for c in project.conditions if c.code == t.condition_code), None)
    if t.condition_code.upper() == "UNSET" or cond is None:
        out.append(("warn", "condition not assigned"))
    roles = {v.role for v in t.videos}
    if len(t.videos) < 2:
        out.append(("info", f"single view ({', '.join(sorted(roles)) or 'none'})"))
    if t.sync.get("pair_status") == "review":
        out.append(("warn", "front/side pairing needs review"))
    if not all(Path(v.path).exists() for v in t.videos):
        out.append(("error", "video file not found"))
    info = Path(project.root) / "trials" / t.id / "analysis.json"
    if t.status != "analysed" or not info.exists():
        out.append(("info", "not analysed"))
        return out
    q = json.loads(info.read_text()).get("quality", {})
    det = q.get("detection_rate")
    if det is not None and det < 0.9:
        out.append(("warn", f"person tracked in only {100 * det:.0f}% of frames"))
    if q.get("kinetics_blocked"):
        out.append(("info", "loads blocked: body metrics missing"))
    tech = q.get("technique") or {}
    if cond is not None and cond.uses_poles and tech.get("n_plants", 0) == 0:
        out.append(("warn", "poles expected but no pole plants detected"))
    return out


def study_checks(project) -> list[tuple[str, str]]:
    out = []
    for p in project.participants:
        if p.missing():
            out.append(("warn", f"{p.id}: {' and '.join(p.missing())} not entered (loads unavailable)"))
    unset = [t.id for t in project.trials if t.condition_code.upper() == "UNSET"]
    if unset:
        out.append(("warn", f"{len(unset)} of {len(project.trials)} trials have no condition assigned"))
    review = [t.id for t in project.trials if t.sync.get("pair_status") == "review"]
    if review:
        out.append(("warn", f"pairing to review: {', '.join(review)}"))
    single = [t.id for t in project.trials if len(t.videos) < 2]
    if single:
        out.append(("info", f"{len(single)} single-view trial(s): {', '.join(single)}"))
    missing = [t.id for t in project.trials if not all(Path(v.path).exists() for v in t.videos)]
    if missing:
        out.append(("error", f"videos not found for {', '.join(missing)}"))
    return out
