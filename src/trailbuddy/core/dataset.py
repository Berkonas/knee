"""Experiment dataset manager: scan a folder of recordings, read metadata, classify camera view,
pair front/side recordings of the same trial, and group recordings by participant.

Design notes (from auditing the CREATE-lab session of 2026-11-16):
* Phone file names (IMG_5602.mov ...) carry no trial information.
* Container creation times can contradict the true recording order (edited / re-exported clips),
  so they are used only as a weak tie-breaker, never as the pairing criterion.
* Two cameras record the same room sound, so the *audio* of a true front/side pair is strongly
  correlated at one time lag (the sync offset). Pairing therefore uses normalised cross-correlation of
  log-energy audio envelopes plus a global one-to-one assignment (Hungarian algorithm).
* Every automatic decision carries a confidence and can be corrected by the user.
Location metadata (GPS) present in some phone files is deliberately never read or stored.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .video import VideoError, _run, extract_audio, ffmpeg_exe

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".avi", ".mkv"}
MIN_USABLE_S = 1.0


@dataclass
class Recording:
    path: str
    name: str
    size_mb: float
    duration_s: float = 0.0
    fps: float = 0.0
    n_frames: int = 0
    width: int = 0
    height: int = 0
    codec: str = ""
    hdr: bool = False
    has_audio: bool = False
    audio_rate: int = 0
    creation_time: str = ""
    device: str = ""
    rotation: int = 0
    usable: bool = True
    issue: str = ""
    view: str = "unknown"          # 'front' | 'side' | 'unknown'
    view_confidence: float = 0.0
    participant: str = ""          # suggested group label (e.g. 'P01')
    appearance: list = field(default_factory=list)  # torso colour feature used for grouping

    def to_dict(self):
        return asdict(self)


def read_metadata(path: str | Path) -> Recording:
    """Container/stream metadata via the bundled ffmpeg. Never raises for broken files: sets usable=False."""
    path = Path(path)
    rec = Recording(str(path), path.name, round(path.stat().st_size / 1e6, 2))
    res = _run([ffmpeg_exe(), "-hide_banner", "-i", str(path)])
    t = res.stderr.decode(errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", t)
    if not m:
        rec.usable, rec.issue = False, "Unreadable or unsupported file"
        return rec
    rec.duration_s = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    v = re.search(r"Stream #\S+.*Video: (\w+)[^\n]*?, (\w+)(?:\([^)]*\))?, (\d+)x(\d+)[^\n]*?, ([\d.]+) fps", t)
    if v:
        rec.codec, pix = v.group(1), v.group(2)
        rec.width, rec.height, rec.fps = int(v.group(3)), int(v.group(4)), float(v.group(5))
        line = re.search(r"Stream #\S+.*Video:[^\n]*", t).group(0)
        rec.hdr = ("10le" in pix) or ("bt2020" in line) or ("arib-std-b67" in line) or ("smpte2084" in line)
    a = re.search(r"Stream #\S+.*Audio: \w+[^\n]*?, (\d+) Hz", t)
    if a:
        rec.has_audio, rec.audio_rate = True, int(a.group(1))
    c = re.search(r"creation_time\s*:\s*(\S+)", t)
    rec.creation_time = c.group(1) if c else ""
    d = re.search(r"com\.apple\.quicktime\.model\s*:\s*(.+)", t) or re.search(r"\bmodel\s*:\s*(.+)", t)
    rec.device = d.group(1).strip() if d else ""
    r = re.search(r"rotate\s*:\s*(-?\d+)", t) or re.search(r"rotation of (-?[\d.]+) degrees", t)
    rec.rotation = int(float(r.group(1))) if r else 0
    rec.n_frames = int(round(rec.duration_s * rec.fps)) if rec.fps else 0
    if rec.duration_s < MIN_USABLE_S:
        rec.usable, rec.issue = False, f"Too short ({rec.duration_s:.2f} s): likely an aborted recording"
    elif not v:
        rec.usable, rec.issue = False, "No video stream"
    return rec


def scan_folder(folder: str | Path) -> list[Recording]:
    folder = Path(folder).resolve()  # recordings are stored with absolute paths
    if not folder.is_dir():
        raise VideoError(f"Not a folder: {folder}")
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and not p.name.startswith("."))
    return [read_metadata(p) for p in files]


# ---------------------------------------------------------------------------------------------
# Audio-envelope pairing
# ---------------------------------------------------------------------------------------------
ENV_HOP_S = 0.01


def audio_envelope(path: str | Path, sr: int = 16000) -> np.ndarray:
    """Log RMS energy (10 ms hop) of the high-passed (>300 Hz) mono track, median-centred."""
    from scipy.signal import butter, sosfiltfilt

    a, sr = extract_audio(path, sr)
    x = sosfiltfilt(butter(4, 300 / (sr / 2), "highpass", output="sos"), a.astype(float))
    h = int(ENV_HOP_S * sr)
    n = len(x) // h
    if n < 10:
        raise VideoError("Audio too short")
    e = np.log10(np.sqrt((x[: n * h].reshape(n, h) ** 2).mean(1)) + 1e-6)
    return e - np.median(e)


def envelope_ncc(a: np.ndarray, b: np.ndarray, max_lag_s: float = 20.0, min_overlap_s: float = 3.0):
    """Best Pearson correlation over lags (normalised on the overlap only).

    Returns (r, lag_s) with a[i] aligned to b[i - lag]; lag_s > 0 means the event happens later in a.
    """
    from scipy.signal import fftconvolve

    n, m = len(a), len(b)
    min_overlap_s = min(min_overlap_s, 0.5 * min(n, m) * ENV_HOP_S)
    num = fftconvolve(a, b[::-1], mode="full")
    lags = np.arange(len(num)) - (m - 1)
    i0 = np.maximum(0, lags)
    i1 = np.minimum(n, m + lags)
    L = i1 - i0
    ok = (L >= int(min_overlap_s / ENV_HOP_S)) & (np.abs(lags) <= int(max_lag_s / ENV_HOP_S))
    if not ok.any():
        return 0.0, 0.0
    ca, cb = np.concatenate(([0], np.cumsum(a))), np.concatenate(([0], np.cumsum(b)))
    ca2, cb2 = np.concatenate(([0], np.cumsum(a * a))), np.concatenate(([0], np.cumsum(b * b)))
    j0, j1 = i0 - lags, i1 - lags
    Ls = np.maximum(L, 1)
    sa, sb = ca[i1] - ca[i0], cb[j1] - cb[j0]
    va = ca2[i1] - ca2[i0] - sa * sa / Ls
    vb = cb2[j1] - cb2[j0] - sb * sb / Ls
    r = (num - sa * sb / Ls) / np.sqrt(np.maximum(va * vb, 1e-12))
    r[~ok] = -1
    k = int(np.argmax(r))
    return float(r[k]), float(lags[k] * ENV_HOP_S)


@dataclass
class PairSuggestion:
    front: str            # file name
    side: str
    score: float          # audio envelope correlation (0..1)
    margin: float         # score minus the best competing score for either file
    offset_s: float       # t_front = t_side + offset_s (audio-derived)
    status: str           # 'confident' | 'review' | 'manual'

    def to_dict(self):
        return asdict(self)


def pair_by_audio(front: list[Recording], side: list[Recording], progress=None, groups: dict | None = None,
                  min_accept: float = 0.6, min_score: float = 0.7, min_margin: float = 0.08
                  ) -> tuple[list[PairSuggestion], np.ndarray]:
    """One-to-one front/side assignment maximising audio-envelope correlation (Hungarian algorithm).

    groups: optional {file: participant label}; pairs across different participants are not allowed.
    Pairs scoring below ``min_accept`` are not proposed (the recordings stay unpaired: they very likely do
    not overlap in time). A pair is 'confident' when score >= min_score and it beats every competing
    candidate by min_margin, or when score >= min_score and both files belong to the same participant group;
    otherwise it is proposed for 'review'.
    """
    from scipy.optimize import linear_sum_assignment

    envs = {}
    allrec = [r for r in front + side if r.usable and r.has_audio]
    for i, r in enumerate(allrec):
        try:
            envs[r.name] = audio_envelope(r.path)
        except VideoError:
            pass
        if progress:
            progress(0.6 * (i + 1) / max(1, len(allrec)), f"Reading audio {r.name}")
    F = [r for r in front if r.name in envs]
    S = [r for r in side if r.name in envs]
    M = np.zeros((len(F), len(S)))
    LAG = np.zeros_like(M)
    for i, f in enumerate(F):
        for j, s in enumerate(S):
            if groups and groups.get(f.name) and groups.get(s.name) and groups[f.name] != groups[s.name]:
                M[i, j], LAG[i, j] = -1.0, 0.0
                continue
            M[i, j], LAG[i, j] = envelope_ncc(envs[f.name], envs[s.name])
        if progress:
            progress(0.6 + 0.4 * (i + 1) / max(1, len(F)), "Comparing recordings")
    out = []
    if M.size:
        rows, cols = linear_sum_assignment(-M)
        for i, j in zip(rows, cols):
            if M[i, j] < min_accept:
                continue
            others = np.concatenate([np.delete(M[i], j), np.delete(M[:, j], i)])
            others = others[others > -1]
            margin = float(M[i, j] - (others.max() if others.size else 0.0))
            same_group = bool(groups and groups.get(F[i].name) and groups.get(F[i].name) == groups.get(S[j].name))
            confident = M[i, j] >= min_score and (margin >= min_margin or same_group)
            status = "confident" if confident else "review"
            out.append(PairSuggestion(F[i].name, S[j].name, round(float(M[i, j]), 3), round(margin, 3),
                                      round(float(LAG[i, j]), 3), status))
    return out, M


# ---------------------------------------------------------------------------------------------
# View classification and participant grouping (pose-based; needs a pose callable)
# ---------------------------------------------------------------------------------------------

def sample_frames(path: str | Path, times_s: list[float]):
    import cv2

    cap = cv2.VideoCapture(str(path))
    out = []
    for t in times_s:
        cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * t)
        ok, fr = cap.read()
        if ok:
            out.append(fr)
    cap.release()
    return out


def view_from_keypoints(kps: np.ndarray) -> float:
    """Shoulder width / torso height in the image: ~0.6-0.8 facing the camera, ~0-0.25 side-on.

    kps: (26, 2) Halpe26 keypoints of the target person.
    """
    sh = np.linalg.norm(kps[5] - kps[6])
    hip_c, sh_c = (kps[11] + kps[12]) / 2, (kps[5] + kps[6]) / 2
    torso = np.linalg.norm(hip_c - sh_c)
    return float(sh / torso) if torso > 1 else np.nan


def torso_colour(frame, kps: np.ndarray) -> np.ndarray:
    """Clothing appearance: median Lab colour of the torso (shoulder-hip quadrilateral) and of the thighs
    (thick hip->knee strokes). Six numbers; used to group recordings of the same participant."""
    import cv2

    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    out = []
    mask = np.zeros(frame.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, kps[[5, 6, 12, 11]].astype(np.int32), 255)
    px = lab[mask > 0]
    out.append(np.median(px, axis=0) if len(px) > 20 else np.full(3, np.nan))
    mask[:] = 0
    width = max(4, int(0.25 * np.linalg.norm(kps[11] - kps[13])))
    for a, b in ((11, 13), (12, 14)):
        cv2.line(mask, tuple(kps[a].astype(int)), tuple(kps[b].astype(int)), 255, width)
    px = lab[mask > 0]
    out.append(np.median(px, axis=0) if len(px) > 20 else np.full(3, np.nan))
    return np.concatenate(out)


def classify_and_describe(recs: list[Recording], detector, progress=None) -> None:
    """Fill view, view_confidence and appearance for usable recordings using a person detector.

    detector(frame) -> (kps (P,26,2), scores (P,26)); the largest confident person is used.
    The view of each *device* is then taken by majority vote, because each phone stayed in one place.
    """
    use = [r for r in recs if r.usable]
    for i, r in enumerate(use):
        ratios, cols = [], []
        for fr in sample_frames(r.path, [0.35 * r.duration_s, 0.5 * r.duration_s, 0.7 * r.duration_s]):
            kps, sc = detector(fr)
            if len(kps) == 0:
                continue
            area = [np.ptp(k[:, 0]) * np.ptp(k[:, 1]) * float(np.mean(s)) for k, s in zip(kps, sc)]
            k = kps[int(np.argmax(area))]
            ratios.append(view_from_keypoints(k))
            cols.append(torso_colour(fr, k))
        if ratios:
            q = float(np.nanmedian(ratios))
            r.view = "front" if q > 0.4 else ("side" if q < 0.3 else "unknown")
            r.view_confidence = float(min(1.0, abs(q - 0.35) / 0.25))
            r.appearance = [float(x) for x in np.nanmedian(np.array(cols), axis=0)]
        if progress:
            progress((i + 1) / max(1, len(use)), f"Checking camera view of {r.name}")
    # device-level majority vote
    by_dev: dict[str, list[Recording]] = {}
    for r in use:
        by_dev.setdefault(r.device or "?", []).append(r)
    for dev, rs in by_dev.items():
        votes = [r.view for r in rs if r.view != "unknown"]
        if dev != "?" and votes:
            maj = max(set(votes), key=votes.count)
            if votes.count(maj) / len(votes) >= 0.7:
                for r in rs:
                    if r.view != maj:
                        r.view, r.view_confidence = maj, 0.5


def group_participants(recs: list[Recording], pairs: list[PairSuggestion], k: int = 3) -> dict[str, str]:
    """Suggest participant labels by clustering front-view clothing colour into k groups.

    Front views give the most consistent colour (same lighting, frontal torso). Side recordings inherit
    the label of their paired front recording. Labels are ordered by first appearance (file order).
    Returns {file name: 'P01'...}; the user can change any label.
    """
    from scipy.cluster.vq import kmeans2

    front = [r for r in recs if r.usable and r.view == "front" and len(r.appearance) >= 3 and np.isfinite(r.appearance).all()]
    labels: dict[str, str] = {}
    if len(front) >= k:
        X = np.array([r.appearance for r in front])
        Xn = (X - X.mean(0)) / (X.std(0) + 1e-6)
        best = None
        for seed in range(10):
            cent, lab = kmeans2(Xn, k, seed=seed, minit="++")
            inertia = sum(np.sum((Xn[lab == c] - cent[c]) ** 2) for c in range(k))
            if best is None or inertia < best[0]:
                best = (inertia, lab)
        lab = best[1]
        order = []
        for c in lab:
            if c not in order:
                order.append(c)
        for r, c in zip(front, lab):
            labels[r.name] = f"P{order.index(c) + 1:02d}"
    for p in pairs:
        if p.front in labels:
            labels[p.side] = labels[p.front]
    return labels


__all__ = ["Recording", "PairSuggestion", "scan_folder", "read_metadata", "pair_by_audio", "envelope_ncc",
           "classify_and_describe", "group_participants", "subprocess"]
