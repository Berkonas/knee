"""Build (or update) a study from a folder of recordings: views, participants, pairs, trials."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from . import dataset
from .project import CameraVideo, Condition, Participant, Project, Trial


def organise(folder: str | Path, n_participants: int = 3, progress=None, cancelled=None) -> dict:
    """Scan, classify views, group participants and pair recordings. Returns a plan dict (no project changes)."""
    from . import pose_rtm

    recs = dataset.scan_folder(folder)
    det = pose_rtm.detector()
    dataset.classify_and_describe(recs, det, (lambda f, m: progress(0.4 * f, m)) if progress else None)
    groups = dataset.group_participants(recs, [], n_participants)
    front = [r for r in recs if r.usable and r.view == "front"]
    side = [r for r in recs if r.usable and r.view == "side"]
    # pass 1: unconstrained audio pairing; side files inherit the participant of a confident front partner
    pairs, _ = dataset.pair_by_audio(front, side, (lambda f, m: progress(0.4 + 0.6 * f, m)) if progress else None)
    for p in pairs:
        if p.status == "confident" and p.front in groups:
            groups[p.side] = groups[p.front]
    # pass 2: forbid pairs across *known* different participants (unlabelled side files stay unconstrained)
    pairs, _ = dataset.pair_by_audio(front, side, None, groups=groups)
    for p in pairs:
        if p.front in groups:
            groups.setdefault(p.side, groups[p.front])
    # unpaired recordings: nearest labelled recording of the SAME camera view by clothing colour
    import numpy as np
    for view in ("front", "side"):
        same = [r for r in recs if r.usable and r.view == view and len(r.appearance) >= 3]
        ref = [(np.array(r.appearance), groups[r.name]) for r in same if r.name in groups]
        for r in same:
            if r.name not in groups and ref:
                d = [np.linalg.norm(np.array(r.appearance) - a) for a, _ in ref]
                groups[r.name] = ref[int(np.argmin(d))][1]
    for r in recs:
        r.participant = groups.get(r.name, "")
    return {"recordings": recs, "pairs": pairs, "groups": groups}


def _cluster_side(side, k):  # kept for experimentation: side-view colours are unreliable (HDR, backlight)
    import numpy as np
    from scipy.cluster.vq import kmeans2

    ok = [r for r in side if len(r.appearance) == 3]
    if len(ok) < k:
        return {}
    X = np.array([r.appearance for r in ok])
    Xn = (X - X.mean(0)) / (X.std(0) + 1e-6)
    best = None
    for seed in range(10):
        c, lab = kmeans2(Xn, k, seed=seed, minit="++")
        inertia = sum(np.sum((Xn[lab == j] - c[j]) ** 2) for j in range(k))
        if best is None or inertia < best[0]:
            best = (inertia, lab)
    return {r.name: f"S{lab}" for r, lab in zip(ok, best[1])}


def apply_plan(project: Project, plan: dict, default_condition: str | None = None) -> list[Trial]:
    """Create participants (placeholder body metrics) and one trial per pair/unpaired recording."""
    recs = {r.name: r for r in plan["recordings"]}
    groups = plan["groups"]
    for pid in sorted(set(groups.values())):
        if pid and not any(p.id == pid for p in project.participants):
            project.participants.append(Participant(pid, notes="Body mass and height not yet entered"))
    if not project.conditions:
        project.conditions = [Condition("C0", "No poles", False), Condition("C1", "Standard poles", True, 0.0)]
    cond = default_condition or ("C1" if any(c.code == "C1" for c in project.conditions) else project.conditions[0].code)
    if not any(c.code == "UNSET" for c in project.conditions):
        project.conditions.append(Condition("UNSET", "Condition not yet assigned", True, None))
    used = {v.path for t in project.trials for v in t.videos}
    created = []

    def cam(r, role):
        meta = {k: getattr(r, k) for k in ("width", "height", "fps", "duration_s", "n_frames", "device", "codec",
                                            "hdr", "has_audio", "creation_time")}
        return CameraVideo(r.path, role, "Side" if role == "side" else "Front", meta)

    items = []
    paired = set()
    for p in plan["pairs"]:
        items.append((recs[p.front], recs[p.side], p))
        paired |= {p.front, p.side}
    for r in plan["recordings"]:
        if r.usable and r.name not in paired and r.view in ("front", "side"):
            items.append((r if r.view == "front" else None, r if r.view == "side" else None, None))
    items.sort(key=lambda it: (groups.get((it[0] or it[1]).name, "P99"), (it[0] or it[1]).name))
    for f, s, p in items:
        if (f and f.path in used) or (s and s.path in used):
            continue
        pid = groups.get((f or s).name) or "P99"
        if not any(q.id == pid for q in project.participants):
            project.participants.append(Participant(pid, notes="Body mass and height not yet entered"))
        vids = ([cam(s, "side")] if s else []) + ([cam(f, "front")] if f else [])
        t = Trial(pid, "UNSET", project.next_trial_number(pid, "UNSET"), vids)
        t.sync = ({"offset_s": -p.offset_s, "method": "audio-envelope", "pair_score": p.score,
                   "pair_margin": p.margin, "pair_status": p.status} if p else {})
        t.notes = "" if (f and s) else "Single view only: no matching recording found"
        if p and p.status == "review":
            t.notes = "Pairing needs review (weak audio match)"
        project.trials.append(t)
        created.append(t)
    del cond
    project.save()
    return created


def plan_summary(plan: dict) -> list[dict]:
    return [r.to_dict() | {"pair": next((asdict(p) for p in plan["pairs"] if r.name in (p.front, p.side)), None)}
            for r in plan["recordings"]]
