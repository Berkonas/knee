"""Reusable widgets: video player with overlays/click capture, matplotlib canvas, badges, worker thread."""

from __future__ import annotations

import traceback
from typing import Callable

import cv2
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import QObject, QPointF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy,
                               QSlider, QVBoxLayout, QWidget)

from ..core.video import FrameReader, VideoError
from .theme import EVIDENCE_COLORS


def page_header(title: str, hint: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 4)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    h = QLabel(hint)
    h.setObjectName("pageHint")
    h.setWordWrap(True)
    lay.addWidget(t)
    lay.addWidget(h)
    return w


def section(title: str) -> QLabel:
    lab = QLabel(title)
    lab.setObjectName("sectionTitle")
    return lab


def error_box(parent, title: str, text: str) -> None:
    QMessageBox.warning(parent, title, text)


def evidence_badge(kind: str) -> QLabel:
    from ..core.metrics import KINDS

    bg, fg = EVIDENCE_COLORS.get(kind, ("#EEE", "#333"))
    lab = QLabel(KINDS.get(kind, kind))
    lab.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:9px; padding:2px 8px; font-size:11px;")
    lab.setToolTip({
        "measured": "Directly measured by an instrument.",
        "video": "Estimated from 2D video pose tracking.",
        "model": "Model-derived estimate using measured forces.",
        "scenario": "Model-derived using an ASSUMED force; use for what-if comparison only.",
        "unavailable": "Cannot be estimated credibly with the available data.",
    }.get(kind, ""))
    return lab


class MplCanvas(FigureCanvasQTAgg):
    """Holds one matplotlib Figure; swap figures with set_figure."""

    def __init__(self, fig=None):
        from matplotlib.figure import Figure

        super().__init__(fig or Figure(figsize=(5, 3)))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(240)

    def set_figure(self, fig) -> None:
        self.figure = fig
        fig.set_canvas(self)
        self.draw_idle()

    def save_dialog(self, parent, default_name: str) -> None:
        path, _ = QFileDialog.getSaveFileName(parent, "Save figure", default_name,
                                              "PNG image (*.png);;SVG vector (*.svg);;PDF (*.pdf)")
        if path:
            self.figure.savefig(path, dpi=300)


class FrameView(QLabel):
    """Displays a BGR frame scaled to fit; emits clicks in source-pixel coordinates."""

    clicked = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 200)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background:#0F1B1A; border-radius:6px; color:#9FB9B4;")
        self.setText("No video loaded")
        self._src_size = (1, 1)
        self._rect = None
        self.click_enabled = False

    def show_frame(self, bgr: np.ndarray) -> None:
        h, w = bgr.shape[:2]
        self._src_size = (w, h)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        pm = QPixmap.fromImage(img).scaled(self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
        self._rect = ((self.width() - pm.width()) / 2, (self.height() - pm.height()) / 2, pm.width(), pm.height())
        self.setPixmap(pm)

    def mousePressEvent(self, ev):
        if not self.click_enabled or self._rect is None:
            return super().mousePressEvent(ev)
        x0, y0, pw, ph = self._rect
        p: QPointF = ev.position()
        if not (x0 <= p.x() <= x0 + pw and y0 <= p.y() <= y0 + ph):
            return
        sx = (p.x() - x0) / pw * self._src_size[0]
        sy = (p.y() - y0) / ph * self._src_size[1]
        self.clicked.emit(sx, sy)


class VideoPlayer(QWidget):
    """Frame-accurate player: play/pause, step, scrub, in/out marks, optional overlay callback."""

    frameChanged = Signal(int)
    loaded = Signal()

    def __init__(self, label: str = ""):
        super().__init__()
        self.reader: FrameReader | None = None
        self.index = 0
        self.mark_in: int | None = None
        self.mark_out: int | None = None
        self.overlay: Callable[[np.ndarray, int], np.ndarray] | None = None
        self.view = FrameView()
        self.title = QLabel(label)
        self.title.setObjectName("muted")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self.seek)
        self.btn_play = QPushButton("Play")
        self.btn_play.setCheckable(True)
        self.btn_play.setToolTip("Play / pause (Space)")
        self.btn_play.toggled.connect(self._toggle)
        self.btn_prev = QPushButton("◀ Frame")
        self.btn_prev.setToolTip("Previous frame")
        self.btn_prev.clicked.connect(lambda: self.seek(self.index - 1))
        self.btn_next = QPushButton("Frame ▶")
        self.btn_next.setToolTip("Next frame")
        self.btn_next.clicked.connect(lambda: self.seek(self.index + 1))
        self.btn_in = QPushButton("Set start")
        self.btn_in.setToolTip("Use the current frame as the start of the analysis interval")
        self.btn_in.clicked.connect(self.set_in)
        self.btn_out = QPushButton("Set end")
        self.btn_out.setToolTip("Use the current frame as the end of the analysis interval")
        self.btn_out.clicked.connect(self.set_out)
        self.pos_label = QLabel("–")
        self.pos_label.setObjectName("muted")
        self.range_label = QLabel("Interval: whole video")
        self.range_label.setObjectName("muted")
        for b in (self.btn_play, self.btn_prev, self.btn_next, self.btn_in, self.btn_out):
            b.setEnabled(False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.seek(self.index + 1, from_timer=True))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        if label:
            lay.addWidget(self.title)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.slider)
        row = QHBoxLayout()
        for b in (self.btn_play, self.btn_prev, self.btn_next):
            row.addWidget(b)
        row.addWidget(self.pos_label)
        row.addStretch(1)
        row.addWidget(self.btn_in)
        row.addWidget(self.btn_out)
        lay.addLayout(row)
        lay.addWidget(self.range_label)

    # ---------------------------------------------------------------------------------------
    def load(self, path: str) -> bool:
        try:
            r = FrameReader(path)
        except VideoError as e:
            error_box(self, "Cannot open video", str(e))
            return False
        if self.reader:
            self.reader.close()
        self.reader = r
        self.mark_in = self.mark_out = None
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, r.info.n_frames - 1))
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.slider.setEnabled(True)
        for b in (self.btn_play, self.btn_prev, self.btn_next, self.btn_in, self.btn_out):
            b.setEnabled(True)
        self.title.setText(f"{r.info.name}  ({r.info.width}×{r.info.height}, {r.info.fps:.2f} fps, "
                           f"{r.info.duration:.2f} s{', audio' if r.info.has_audio else ', no audio'})")
        self.index = -1
        self.seek(0)
        self._update_range()
        self.loaded.emit()
        return True

    @property
    def fps(self) -> float:
        return self.reader.info.fps if self.reader else 30.0

    def time(self) -> float:
        return self.index / self.fps

    def seek(self, i: int, from_timer: bool = False) -> None:
        if not self.reader:
            return
        n = self.reader.info.n_frames
        if i >= n or i < 0:
            if from_timer:
                self.btn_play.setChecked(False)
            i = max(0, min(n - 1, i))
        if i == self.index and not from_timer:
            return
        frame = self.reader.read(i)
        if frame is None:
            return
        self.index = i
        if self.overlay is not None:
            frame = self.overlay(frame.copy(), i)
        self.view.show_frame(frame)
        self.slider.blockSignals(True)
        self.slider.setValue(i)
        self.slider.blockSignals(False)
        self.pos_label.setText(f"Frame {i}  ·  {i / self.fps:.3f} s")
        self.frameChanged.emit(i)

    def refresh(self) -> None:
        i, self.index = self.index, -1
        self.seek(i)

    def _toggle(self, on: bool) -> None:
        self.btn_play.setText("Pause" if on else "Play")
        if on:
            self.timer.start(int(1000 / self.fps))
        else:
            self.timer.stop()

    def set_in(self) -> None:
        self.mark_in = self.index
        if self.mark_out is not None and self.mark_out <= self.mark_in:
            self.mark_out = None
        self._update_range()

    def set_out(self) -> None:
        if self.mark_in is not None and self.index <= self.mark_in:
            error_box(self, "Invalid interval", "The end must be after the start.")
            return
        self.mark_out = self.index
        self._update_range()

    def interval_s(self) -> tuple[float, float] | None:
        if not self.reader:
            return None
        a = (self.mark_in or 0) / self.fps
        b = (self.mark_out if self.mark_out is not None else self.reader.info.n_frames - 1) / self.fps
        return a, b

    def set_interval_s(self, a: float, b: float) -> None:
        self.mark_in, self.mark_out = int(round(a * self.fps)), int(round(b * self.fps))
        self._update_range()

    def _update_range(self) -> None:
        iv = self.interval_s()
        if iv:
            self.range_label.setText(f"Analysis interval: {iv[0]:.2f}–{iv[1]:.2f} s ({iv[1] - iv[0]:.2f} s)")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.reader:
            self.refresh()


class Worker(QObject):
    progress = Signal(float, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            res = self.fn(*self.args, progress=lambda f, m: self.progress.emit(f, m),
                          cancelled=lambda: self._cancel, **self.kwargs)
            self.finished.emit(res)
        except Exception as e:  # surfaced to the user with the reason
            from ..core.pose import Cancelled

            if isinstance(e, Cancelled):
                self.failed.emit("Analysis cancelled.")
            else:
                traceback.print_exc()
                self.failed.emit(f"{type(e).__name__}: {e}")


def start_worker(parent, worker: Worker) -> QThread:
    th = QThread(parent)
    worker.moveToThread(th)
    th.started.connect(worker.run)
    worker.finished.connect(th.quit)
    worker.failed.connect(th.quit)
    th.finished.connect(th.deleteLater)
    th.start()
    return th


def draw_painter_text(img: np.ndarray, text: str, org=(12, 28)) -> np.ndarray:
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 1, cv2.LINE_AA)
    return img


__all__ = ["VideoPlayer", "MplCanvas", "Worker", "start_worker", "evidence_badge", "page_header",
           "section", "error_box", "QPainter"]
