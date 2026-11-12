"""Video metadata, frame access, audio extraction and non-destructive trimming.

ffmpeg is provided by the ``imageio-ffmpeg`` package, so users do not need to install it.
Source recordings are never modified: trimming always writes a new file.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class VideoError(RuntimeError):
    """Raised for unreadable or unsupported video files."""


def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    kwargs = {}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):  # Windows: no console flash
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, capture_output=True, **kwargs)


@dataclass
class VideoInfo:
    path: str
    fps: float
    n_frames: int
    width: int
    height: int
    duration: float
    has_audio: bool
    rotation: int = 0

    @property
    def name(self) -> str:
        return Path(self.path).name


def probe(path: str | Path) -> VideoInfo:
    """Read basic metadata. Raises VideoError with a readable message on failure."""
    path = str(path)
    if not Path(path).is_file():
        raise VideoError(f"File not found: {path}")
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise VideoError(f"Could not open video (unsupported format or corrupt file): {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    ok, _ = cap.read()
    cap.release()
    if not ok or fps <= 0 or w <= 0:
        raise VideoError(f"Video has no readable frames: {path}")
    # ffmpeg banner tells us whether there is an audio stream.
    res = _run([ffmpeg_exe(), "-hide_banner", "-i", path])
    text = res.stderr.decode(errors="replace")
    has_audio = bool(re.search(r"Stream #\S+.*Audio:", text))
    return VideoInfo(path, float(fps), n, w, h, n / fps if fps else 0.0, has_audio)


class FrameReader:
    """Random-access frame reader with a tiny cache for scrubbing."""

    def __init__(self, path: str | Path):
        self.info = probe(path)
        self._cap = cv2.VideoCapture(str(path))
        self._next = 0
        self._cache: dict[int, np.ndarray] = {}

    def read(self, index: int) -> np.ndarray | None:
        """Return frame ``index`` as BGR uint8, or None if out of range."""
        if index < 0 or index >= max(self.info.n_frames, 1):
            return None
        if index in self._cache:
            return self._cache[index]
        if index != self._next:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self._cap.read()
        self._next = index + 1
        if not ok:
            return None
        if len(self._cache) > 32:
            self._cache.pop(next(iter(self._cache)))
        self._cache[index] = frame
        return frame

    def iter_range(self, start: int, stop: int):
        """Yield (index, frame) sequentially; much faster than random access."""
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        for i in range(start, stop):
            ok, frame = self._cap.read()
            if not ok:
                break
            yield i, frame
        self._next = -1

    def close(self) -> None:
        self._cap.release()


def extract_audio(path: str | Path, sample_rate: int = 16000) -> tuple[np.ndarray, int]:
    """Decode the audio track as mono float32 in [-1, 1].

    Raises VideoError if the file has no audio stream.
    """
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn",
           "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-acodec", "pcm_s16le", "-"]
    res = _run(cmd)
    if res.returncode != 0 or len(res.stdout) == 0:
        raise VideoError(f"No usable audio track in {Path(path).name}. Use manual clap-frame sync.")
    audio = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio, sample_rate


def trim(src: str | Path, dst: str | Path, start_s: float, end_s: float, reencode: bool = True) -> Path:
    """Write ``src[start_s:end_s]`` to a new file ``dst``. Never overwrites ``src``."""
    src, dst = Path(src), Path(dst)
    if src.resolve() == dst.resolve():
        raise VideoError("Refusing to overwrite the original recording.")
    if end_s <= start_s:
        raise VideoError("End time must be after start time.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start_s:.4f}",
           "-i", str(src), "-t", f"{end_s - start_s:.4f}"]
    if reencode:  # frame-accurate cut
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac"]
    else:
        cmd += ["-c", "copy"]
    cmd.append(str(dst))
    res = _run(cmd)
    if res.returncode != 0:
        raise VideoError("ffmpeg trim failed: " + res.stderr.decode(errors="replace")[-400:])
    return dst


def write_video(frames, dst: str | Path, fps: float, audio: np.ndarray | None = None,
                sample_rate: int = 16000) -> Path:
    """Encode BGR frames (iterable of HxWx3 uint8) to H.264 MP4, optionally with mono audio."""
    import tempfile

    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    frames = iter(frames)
    first = next(frames)
    h, w = first.shape[:2]
    with tempfile.TemporaryDirectory() as td:
        cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-"]
        if audio is not None:
            wav = Path(td) / "a.raw"
            (np.clip(audio, -1, 1) * 32767).astype(np.int16).tofile(wav)
            cmd += ["-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-i", str(wav)]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        if audio is not None:
            cmd += ["-c:a", "aac", "-shortest"]
        cmd.append(str(dst))
        kwargs = {}
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        try:
            proc.stdin.write(np.ascontiguousarray(first).tobytes())
            for f in frames:
                proc.stdin.write(np.ascontiguousarray(f).tobytes())
            proc.stdin.close()
        except BrokenPipeError:
            pass
        err = proc.stderr.read().decode(errors="replace")
        if proc.wait() != 0:
            raise VideoError("ffmpeg encode failed: " + err[-400:])
    return dst
