"""Study organisation: participants, conditions, trials, stored as one JSON file per project.

Original videos are referenced by path and never copied or modified. Results for each trial are
written to <project>/trials/<trial_id>/. Participant names are not stored - use codes (P01...).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass
class Condition:
    code: str
    label: str
    uses_poles: bool
    pole_offset_cm: float | None = None  # relative to the participant's standard length


EXPERIMENTS: dict[str, dict] = {
    "exp1": {"name": "Experiment 1 - simple comparison", "task": "stair descent", "reps": 3,
             "conditions": [Condition("C0", "No poles", False), Condition("C1", "Standard poles", True, 0.0)]},
    "exp2": {"name": "Experiment 2 - pole length", "task": "stair descent", "reps": 3,
             "conditions": [Condition("C0", "No poles", False), Condition("C1", "Standard poles", True, 0.0),
                            Condition("C2", "Standard - 5 cm", True, -5.0), Condition("C3", "Standard + 5 cm", True, 5.0)]},
    "exp3": {"name": "Experiment 3 - controlled step-down", "task": "single step-down", "reps": 3,
             "conditions": [Condition("C0", "No poles", False), Condition("C1", "Standard poles", True, 0.0),
                            Condition("C3", "Standard + 5 cm", True, 5.0)]},
}

# Optional tape-measure body metrics (metres). Landmark definitions are shown in the app.
SEGMENT_FIELDS = {
    "thigh_m": ("Thigh length", "Greater trochanter (bony point at the side of the hip) to the knee joint line"),
    "shank_m": ("Shank length", "Knee joint line to the outer ankle bone (lateral malleolus)"),
    "foot_m": ("Foot length", "Back of the heel to the tip of the longest toe"),
    "upper_arm_m": ("Upper-arm length", "Top of the shoulder (acromion) to the outer elbow (lateral epicondyle)"),
    "forearm_m": ("Forearm length", "Outer elbow to the wrist bone on the little-finger side (ulnar styloid)"),
}

PID_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")


@dataclass
class Participant:
    id: str
    body_mass_kg: float
    height_m: float
    leg_length_m: float | None = None
    standard_pole_length_cm: float | None = None
    segments: dict = field(default_factory=dict)  # measured segment lengths, keys in SEGMENT_FIELDS (m)
    notes: str = ""

    def validate(self) -> None:
        if not PID_RE.match(self.id):
            raise ValueError("Participant ID must be a short code like P01 (letters, digits, - or _).")
        if not (20 <= self.body_mass_kg <= 250):
            raise ValueError("Body mass must be between 20 and 250 kg.")
        if not (1.0 <= self.height_m <= 2.5):
            raise ValueError("Height must be between 1.0 and 2.5 m.")
        for k, v in self.segments.items():
            if k in SEGMENT_FIELDS and v is not None and not (0.03 <= v <= 0.4 * self.height_m):
                raise ValueError(f"{SEGMENT_FIELDS[k][0]} of {v} m is not plausible for a height of {self.height_m} m.")


@dataclass
class CameraVideo:
    path: str
    role: str = "side"  # 'side' (sagittal) | 'front' | 'oblique'
    label: str = "Camera A"


@dataclass
class Trial:
    participant_id: str
    condition_code: str
    trial_number: int
    videos: list[CameraVideo] = field(default_factory=list)
    pole_length_cm: float | None = None
    stair: dict = field(default_factory=dict)       # step_height_m, step_depth_m, n_steps, slope_deg
    camera_config: str = ""
    sync: dict = field(default_factory=dict)        # offset_s, method, confidence
    interval: list[float] | None = None             # [start_s, end_s] in camera A clock
    settings: dict = field(default_factory=dict)    # analysis settings snapshot
    notes: str = ""
    status: str = "new"                             # new | analysed | error

    @property
    def id(self) -> str:
        return f"{self.participant_id}_{self.condition_code}_T{self.trial_number:02d}"


@dataclass
class Project:
    name: str
    experiment: str = "exp1"
    conditions: list[Condition] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)
    trials: list[Trial] = field(default_factory=list)
    root: Path | None = None

    @classmethod
    def new(cls, root: str | Path, name: str, experiment: str = "exp1") -> "Project":
        conds = [Condition(**asdict(c)) for c in EXPERIMENTS[experiment]["conditions"]]
        p = cls(name=name, experiment=experiment, conditions=conds, root=Path(root))
        p.root.mkdir(parents=True, exist_ok=True)
        p.save()
        return p

    # ---- lookup -------------------------------------------------------------------------
    def participant(self, pid: str) -> Participant:
        for p in self.participants:
            if p.id == pid:
                return p
        raise KeyError(f"Unknown participant {pid}")

    def condition(self, code: str) -> Condition:
        for c in self.conditions:
            if c.code == code:
                return c
        raise KeyError(f"Unknown condition {code}")

    def trial(self, tid: str) -> Trial:
        for t in self.trials:
            if t.id == tid:
                return t
        raise KeyError(f"Unknown trial {tid}")

    # ---- mutation -----------------------------------------------------------------------
    def add_participant(self, p: Participant) -> None:
        p.validate()
        if any(q.id == p.id for q in self.participants):
            raise ValueError(f"Participant {p.id} already exists.")
        self.participants.append(p)

    def add_condition(self, c: Condition) -> None:
        if any(q.code == c.code for q in self.conditions):
            raise ValueError(f"Condition {c.code} already exists.")
        self.conditions.append(c)

    def add_trial(self, t: Trial) -> Trial:
        self.participant(t.participant_id)
        cond = self.condition(t.condition_code)
        if any(q.id == t.id for q in self.trials):
            raise ValueError(f"Trial {t.id} already exists.")
        if t.pole_length_cm is None and cond.uses_poles:
            std = self.participant(t.participant_id).standard_pole_length_cm
            if std is not None:
                t.pole_length_cm = std + (cond.pole_offset_cm or 0.0)
        self.trials.append(t)
        return t

    def remove_trial(self, tid: str) -> None:
        self.trials = [t for t in self.trials if t.id != tid]

    def next_trial_number(self, pid: str, code: str) -> int:
        nums = [t.trial_number for t in self.trials if t.participant_id == pid and t.condition_code == code]
        return max(nums, default=0) + 1

    def planned_trials(self) -> int:
        reps = EXPERIMENTS.get(self.experiment, {}).get("reps", 3)
        return len(self.participants) * len(self.conditions) * reps

    def trial_dir(self, tid: str) -> Path:
        assert self.root is not None
        d = self.root / "trials" / tid
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---- persistence --------------------------------------------------------------------
    def to_dict(self) -> dict:
        d = {"schema": SCHEMA_VERSION, "name": self.name, "experiment": self.experiment,
             "conditions": [asdict(c) for c in self.conditions],
             "participants": [asdict(p) for p in self.participants],
             "trials": [asdict(t) for t in self.trials]}
        return d

    def save(self) -> Path:
        assert self.root is not None
        path = self.root / "project.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2))
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, root: str | Path) -> "Project":
        root = Path(root)
        path = root / "project.json" if root.is_dir() else root
        d = json.loads(path.read_text())
        trials = []
        for t in d.get("trials", []):
            t = dict(t)
            t["videos"] = [CameraVideo(**v) for v in t.get("videos", [])]
            trials.append(Trial(**t))
        return cls(name=d["name"], experiment=d.get("experiment", "exp1"),
                   conditions=[Condition(**c) for c in d.get("conditions", [])],
                   participants=[Participant(**p) for p in d.get("participants", [])],
                   trials=trials, root=path.parent)


def parse_filename(name: str) -> tuple[str, str, int] | None:
    """Parse protocol file names like 'P01_C1_T01.mp4' -> ('P01', 'C1', 1)."""
    m = re.match(r"^(P\d+)_(C\d+)_T(\d+)", Path(name).stem, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).upper(), m.group(2).upper(), int(m.group(3))
