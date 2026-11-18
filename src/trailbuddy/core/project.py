"""Study organisation: participants, conditions, trials, stored as one JSON file per project.

Original videos are referenced by path and never copied or modified. Results for each trial are
written to <project>/trials/<trial_id>/. Participant names are not stored - use codes (P01...).
"""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 2
_SAVE_LOCK = threading.RLock()

TASKS = {"stair_descent": "Stair descent", "downhill_walk": "Downhill ramp", "level_walk": "Flat ground",
         "stair_ascent": "Stair ascent", "step_down": "Single step-down", "uphill_walk": "Uphill walking"}
# Short code added to trial IDs so the same condition and number can exist on several terrains.
# Stair descent has none, which keeps the IDs of existing studies unchanged.
TASK_CODES = {"stair_descent": "", "downhill_walk": "RAMP", "level_walk": "FLAT", "stair_ascent": "UP",
              "step_down": "STEP", "uphill_walk": "UPHILL"}


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
    "full": {"name": "TrailBuddy full design - 4 pole conditions x 3 terrains", "task": "all", "reps": 3,
             "tasks": ["level_walk", "downhill_walk", "stair_descent"],
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

PARTICIPANT_EDIT_FIELDS = ("body_mass_kg", "height_m", "leg_length_m", "standard_pole_length_cm", "segments", "notes",
                           "age_years", "sex", "dominant_leg", "lead_leg", "footwear", "carried_load_kg")

PID_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")


@dataclass
class Participant:
    """A participant. Body mass and height are None until measured values are entered: nothing that
    depends on them (scale from height, any force or moment) is calculated from a default."""

    id: str
    body_mass_kg: float | None = None   # required for every body-weight-dependent quantity
    height_m: float | None = None       # used for the video scale when no scene calibration exists
    leg_length_m: float | None = None
    standard_pole_length_cm: float | None = None
    segments: dict = field(default_factory=dict)  # measured segment lengths, keys in SEGMENT_FIELDS (m)
    notes: str = ""
    age_years: int | None = None        # optional, voluntary
    sex: str = ""                       # optional, voluntary; never used to replace measured anatomy
    dominant_leg: str = ""              # 'left' | 'right' | ''
    lead_leg: str = ""                  # preferred leading leg on descent
    footwear: str = ""
    carried_load_kg: float | None = None

    @property
    def metrics_entered(self) -> bool:
        return self.body_mass_kg is not None and self.height_m is not None

    def missing(self) -> list[str]:
        return [lab for lab, v in (("body mass", self.body_mass_kg), ("height", self.height_m)) if v is None]

    def validate(self) -> None:
        if not PID_RE.match(self.id):
            raise ValueError("Participant ID must be a short code like P01 (letters, digits, - or _).")
        if self.body_mass_kg is not None and not (20 <= self.body_mass_kg <= 250):
            raise ValueError("Body mass must be between 20 and 250 kg.")
        if self.height_m is not None and not (1.0 <= self.height_m <= 2.5):
            raise ValueError("Height must be between 1.0 and 2.5 m.")
        if self.carried_load_kg is not None and not (0 <= self.carried_load_kg <= 60):
            raise ValueError("Carried load must be between 0 and 60 kg.")
        for k, v in self.segments.items():
            if k in SEGMENT_FIELDS and v is not None and self.height_m and not (0.03 <= v <= 0.4 * self.height_m):
                raise ValueError(f"{SEGMENT_FIELDS[k][0]} of {v} m is not plausible for a height of {self.height_m} m.")


@dataclass
class CameraVideo:
    path: str
    role: str = "side"  # 'side' (sagittal) | 'front' | 'oblique'
    label: str = "Camera A"
    meta: dict = field(default_factory=dict)  # resolution, fps, duration, device, creation time


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
    date: str = ""                                  # ISO date of the recording
    task: str = "stair_descent"                     # key of TASKS
    n_poles: int | None = None                      # 0, 1 or 2 (None = from the condition)
    grip: str = ""                                  # e.g. strap, no strap, top of handle
    surface: str = ""
    force_data: str = ""                            # description of force data available, if any
    segments: list[dict] = field(default_factory=list)  # candidate movement segments {start_s, end_s, label, source}

    @property
    def id(self) -> str:
        code = TASK_CODES.get(self.task, "")
        return f"{self.participant_id}_{self.condition_code}{'_' + code if code else ''}_T{self.trial_number:02d}"


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

    # ---- safe deletion (recoverable) ----------------------------------------------------
    def trash_dir(self) -> Path:
        assert self.root is not None
        return self.root / ".trash"

    def delete_trials(self, tids: list[str]) -> list[Path]:
        """Move trials to <study>/.trash: their study entry and derived results. Source videos are never touched."""
        import shutil
        import time

        out = []
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for tid in tids:
            t = self.trial(tid)
            dest = self.trash_dir() / f"{stamp}_{tid}"
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "trial.json").write_text(json.dumps(asdict(t), indent=2))
            src = self.root / "trials" / tid
            if src.exists():
                shutil.move(str(src), str(dest / "results"))
            self.remove_trial(tid)
            out.append(dest)
        self.save()
        return out

    def deleted_trials(self) -> list[tuple[Path, str]]:
        d = self.trash_dir()
        if not d.exists():
            return []
        return sorted(((p, p.name.split("_", 1)[-1]) for p in d.iterdir() if (p / "trial.json").exists()),
                      reverse=True)

    def restore_trial(self, trash_entry: Path) -> Trial:
        import shutil

        t = _trial_from_dict(json.loads((trash_entry / "trial.json").read_text()), self.root)
        if any(q.id == t.id for q in self.trials):
            raise ValueError(f"A trial {t.id} already exists; rename or delete it first.")
        self.participant(t.participant_id)  # KeyError if the participant was removed meanwhile
        self.condition(t.condition_code)
        target = self.root / "trials" / t.id
        if (trash_entry / "results").exists() and target.exists():
            raise ValueError(f"A results folder for {t.id} already exists ({target}); move it away first.")
        self.trials.append(t)
        if (trash_entry / "results").exists():
            shutil.move(str(trash_entry / "results"), str(self.root / "trials" / t.id))
        shutil.rmtree(trash_entry)
        self.save()
        return t

    def rename_trial(self, tid: str, condition_code: str | None = None, trial_number: int | None = None) -> Trial:
        """Reassign a trial's condition and/or number; its results folder follows the new ID."""
        t = self.trial(tid)
        new = Trial(**{**asdict(t), "videos": t.videos,
                       "condition_code": condition_code or t.condition_code,
                       "trial_number": trial_number or t.trial_number})
        cond = self.condition(new.condition_code)
        if new.id != tid and any(q.id == new.id for q in self.trials):
            raise ValueError(f"Trial {new.id} already exists.")
        old_dir, new_dir = self.root / "trials" / tid, self.root / "trials" / new.id
        if new.id != tid and new_dir.exists():
            raise ValueError(f"A results folder {new_dir.name} already exists; move it away first.")
        if new.id != tid and old_dir.exists():
            old_dir.rename(new_dir)  # move first: if this fails, nothing has changed
        if new.condition_code != t.condition_code:
            t.status = "new"  # results were computed for the old condition (poles, pole length): re-analyse
            std = self.participant(t.participant_id).standard_pole_length_cm
            t.pole_length_cm = std + (cond.pole_offset_cm or 0.0) if (std is not None and cond.uses_poles) else None
        t.condition_code, t.trial_number = new.condition_code, new.trial_number
        self.save()
        return t

    def duplicate_trial(self, tid: str) -> Trial:
        t = self.trial(tid)
        d = asdict(t)
        d.update(trial_number=self.next_trial_number(t.participant_id, t.condition_code, t.task), status="new",
                 notes=(t.notes + " (copy)").strip())
        new = _trial_from_dict(d, self.root)
        self.trials.append(new)
        self.save()
        return new

    def clear_cache(self, tids: list[str] | None = None) -> int:
        """Delete generated tracking caches (all, or those of the given trials' videos). Returns files removed."""
        assert self.root is not None
        cache = self.root / "cache"
        if not cache.exists():
            return 0
        stems = None if tids is None else {Path(v.path).stem for tid in tids for v in self.trial(tid).videos}
        n = 0
        for f in cache.iterdir():
            if f.is_file() and (stems is None or any(f.name.startswith(st + ".") for st in stems)):
                f.unlink()
                n += 1
        return n

    def next_trial_number(self, pid: str, code: str, task: str | None = None) -> int:
        nums = [t.trial_number for t in self.trials if t.participant_id == pid and t.condition_code == code
                and (task is None or t.task == task)]
        return max(nums, default=0) + 1

    def planned_trials(self) -> int:
        exp = EXPERIMENTS.get(self.experiment, {})
        n_tasks = len(exp.get("tasks", [None]))
        return len(self.participants) * len([c for c in self.conditions if c.code != "UNSET"]) * exp.get("reps", 3) * n_tasks

    def update_trial_id(self, old_id: str, t: Trial) -> None:
        """Call after changing a trial's task, condition or number: moves its results folder to the new ID and
        refuses an ID that another trial already has (the change is undone)."""
        if t.id == old_id:
            return
        if sum(q.id == t.id for q in self.trials) > 1:
            raise ValueError(f"Trial {t.id} already exists.")
        old_dir, new_dir = self.root / "trials" / old_id, self.root / "trials" / t.id
        if new_dir.exists():
            raise ValueError(f"A results folder {new_dir.name} already exists; move it away first.")
        if old_dir.exists():
            old_dir.rename(new_dir)

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
             "trials": [self._trial_dict(t) for t in self.trials]}
        return d

    def _trial_dict(self, t: Trial) -> dict:
        """Video paths are stored relative to the study folder when they are near it (e.g. ../../Videos/x.mov), so
        a study folder moved together with its videos still opens and no home-folder path is written."""
        d = asdict(t)
        for v in d["videos"]:
            try:
                rel = os.path.relpath(v["path"], self.root)
            except ValueError:  # different drive on Windows
                continue
            if rel.count("..") <= 3 and not os.path.isabs(rel):
                v["path"] = Path(rel).as_posix()
        return d

    def save(self) -> Path:
        assert self.root is not None
        path = self.root / "project.json"
        with _SAVE_LOCK:  # analysis threads and the UI thread may both save
            return self._save_locked(path)

    def _save_locked(self, path: Path) -> Path:
        import os
        import tempfile
        import time

        if path.exists():  # keep the last 20 versions of the study file
            bdir = self.root / "backups"
            bdir.mkdir(exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
            dest, k = bdir / f"project-{stamp}.json", 1
            while dest.exists():  # several saves in the same millisecond: never overwrite a backup
                dest, k = bdir / f"project-{stamp}-{k}.json", k + 1
            dest.write_bytes(path.read_bytes())
            for old in sorted(bdir.glob("project-*.json"))[:-20]:
                old.unlink()
        fd, tmp = tempfile.mkstemp(prefix="project.", suffix=".json.tmp", dir=self.root)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(self.to_dict(), indent=2))
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, root: str | Path) -> "Project":
        root = Path(root)
        path = root / "project.json" if root.is_dir() else root
        d = json.loads(path.read_text())
        trials = [_trial_from_dict(t, path.parent) for t in d.get("trials", [])]
        return cls(name=d["name"], experiment=d.get("experiment", "exp1"),
                   conditions=[Condition(**_known(Condition, c)) for c in d.get("conditions", [])],
                   participants=[_participant_from_dict(p) for p in d.get("participants", [])],
                   trials=trials, root=path.parent)


def _known(cls, d: dict) -> dict:
    """Keep only fields the dataclass knows (studies written by newer versions still open)."""
    names = set(cls.__dataclass_fields__)
    return {k: v for k, v in d.items() if k in names}


def _participant_from_dict(d: dict) -> Participant:
    d = dict(d)
    if d.pop("metrics_entered", True) is False:  # schema 1: placeholder mass/height were stored as numbers
        d["body_mass_kg"] = d["height_m"] = None
    return Participant(**_known(Participant, d))


def _trial_from_dict(d: dict, root: Path) -> Trial:
    d = dict(d)
    d["videos"] = [CameraVideo(**_known(CameraVideo, {**v, "path": resolve_video_path(v["path"], root)}))
                   for v in d.get("videos", [])]
    return Trial(**_known(Trial, d))


def resolve_video_path(stored: str, project_root: Path) -> str:
    """Absolute path for a stored video path. Relative paths are looked up next to the study folder and then in
    each of its parent folders, so a study opens the same way from a packaged app (whose working folder is not
    the repository) as from a source checkout."""
    p = Path(stored)
    if p.is_absolute():
        return str(p)
    for base in (project_root, *project_root.parents):
        if (base / p).exists():
            return str((base / p).resolve())
    if p.exists():  # relative to the current folder (old behaviour)
        return str(p.resolve())
    return stored


def parse_filename(name: str) -> tuple[str, str, int] | None:
    """Parse protocol file names like 'P01_C1_T01.mp4' -> ('P01', 'C1', 1)."""
    m = re.match(r"^(P\d+)_(C\d+)_T(\d+)", Path(name).stem, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).upper(), m.group(2).upper(), int(m.group(3))
