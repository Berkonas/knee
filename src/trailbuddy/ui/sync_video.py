"""Synchronised front + side video panel with one master clock, overlays and transport controls.

Master clock: seconds on the side camera's timeline (front camera if no side view).
Each view maps the master time to its own frame:  side frame = round(t * fps_side)
                                                  front frame = round((t - offset) * fps_front)
where offset = t_side - t_front for the same instant (from clap sync). Frames are fetched sequentially
during playback (fast path) and by seeking otherwise; display uses real-time pacing (frames are skipped
rather than slowing playback), so both views always show the same instant.
"""

from __future__ import annotations

import time

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QSizePolicy, QSlider, QSplitter,
                               QToolButton, QVBoxLayout, QWidget)

from ..core.landmarks import SKELETON
from ..core.video import FrameReader, VideoError
from .theme import tok

SIDE_COL = QColor("#59D0BE")
LOW_COL = QColor("#F08A7E")
POLE_COL = QColor("#FFB347")
FOOT_COL = {"left": QColor("#59D0BE"), "right": QColor("#FFB347")}
FLASH_S = 0.25   # a foot strike flashes for this long (idea from jeremyipark/vision-demos, re-implemented)


class VideoCanvas(QWidget):
    """Paints one video frame (aspect-correct) plus vector overlays in source-pixel coordinates."""

    clicked = Signal(float, float)

    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.img: QImage | None = None
        self.src_size = (1, 1)
        self.overlay = None   # dict with 'xy','vis','poles','trail','labels'
        self.message = "No recording"
        self.show = {"skeleton": True, "poles": True, "trails": False, "labels": False, "contacts": True}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(240, 160)

    def set_frame(self, bgr: np.ndarray | None):
        if bgr is None:
            self.img = None
            self.update()
            return
        h, w = bgr.shape[:2]
        self.src_size = (w, h)
        # downscale once to the widget size (cheap) and convert
        scale = min(self.width() / w, self.height() / h, 1.0) * self.devicePixelRatioF()
        if scale < 0.98:
            bgr = cv2.resize(bgr, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        self.img = QImage(rgb.data, rgb.shape[1], rgb.shape[0], 3 * rgb.shape[1], QImage.Format.Format_RGB888).copy()
        self.update()

    def _rect(self) -> QRectF:
        w, h = self.src_size
        s = min(self.width() / w, self.height() / h)
        return QRectF((self.width() - w * s) / 2, (self.height() - h * s) / 2, w * s, h * s)

    def mousePressEvent(self, e):
        r = self._rect()
        p = e.position()
        if r.contains(p):
            self.clicked.emit((p.x() - r.x()) / r.width() * self.src_size[0], (p.y() - r.y()) / r.height() * self.src_size[1])

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(tok("video_bg")))
        if self.img is None:
            p.setPen(QColor("#8FA09C"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)
            p.end()
            return
        r = self._rect()
        p.drawImage(r, self.img)
        sx = r.width() / self.src_size[0]
        X = lambda pt: QPointF(r.x() + pt[0] * sx, r.y() + pt[1] * sx)  # noqa: E731
        ov = self.overlay or {}
        xy, vis = ov.get("xy"), ov.get("vis")
        lw = max(1.5, 2.2 * sx * 1.6)
        if self.show["trails"] and ov.get("trail") is not None:
            for path, col in ov["trail"]:  # comet: thin and transparent at the tail, full at the head
                pts = [X(q) for q in path if np.isfinite(q).all()]
                n = max(1, len(pts) - 1)
                for i, (a, b) in enumerate(zip(pts, pts[1:])):
                    f = (i + 1) / n
                    c = QColor(col)
                    c.setAlphaF(min(1.0, 0.05 + 0.9 * f ** 1.4))
                    p.setPen(QPen(c, lw * (0.25 + 1.0 * f), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    p.drawLine(a, b)
        if self.show["skeleton"] and xy is not None:
            for a, b in SKELETON:
                if np.isfinite(xy[[a, b]]).all():
                    good = min(vis[a], vis[b]) >= 0.5
                    p.setPen(QPen(SIDE_COL if good else LOW_COL, lw, Qt.PenStyle.SolidLine if good else Qt.PenStyle.DashLine,
                                  Qt.PenCapStyle.RoundCap))
                    p.drawLine(X(xy[a]), X(xy[b]))
            p.setPen(Qt.PenStyle.NoPen)
            for i in list(range(11, 17)) + list(range(23, 33)):
                if np.isfinite(xy[i]).all():
                    p.setBrush(SIDE_COL if vis[i] >= 0.5 else LOW_COL)
                    p.drawEllipse(X(xy[i]), lw * 1.3, lw * 1.3)
        if self.show["contacts"] and ov.get("contacts"):
            p.setBrush(Qt.BrushStyle.NoBrush)
            for pt, side, age in ov["contacts"]:
                if not np.isfinite(pt).all():
                    continue
                col = QColor(FOOT_COL.get(side, SIDE_COL))
                p.setPen(QPen(col, lw * 1.1))
                p.drawEllipse(X(pt), lw * 4.0, lw * 2.4)  # planted foot
                if age < FLASH_S:  # foot strike: expanding, fading ring
                    f = age / FLASH_S
                    c = QColor(col)
                    c.setAlphaF(0.9 * (1 - f))
                    p.setPen(QPen(c, lw * 1.6))
                    p.drawEllipse(X(pt), lw * (4.5 + 6 * f), lw * (3 + 4 * f))
        if self.show["poles"] and ov.get("poles"):
            for hand, tip, conf in ov["poles"]:
                if np.isfinite(hand).all() and np.isfinite(tip).all():
                    col = QColor(POLE_COL)
                    col.setAlphaF(0.45 + 0.55 * float(np.clip(conf, 0, 1)))
                    p.setPen(QPen(col, lw * 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    p.drawLine(X(hand), X(tip))
                    p.setBrush(col)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(X(tip), lw * 2, lw * 2)
        if self.show["labels"] and ov.get("labels"):
            f = QFont(self.font())
            f.setPointSizeF(max(9.0, 11 * min(1.0, r.width() / 900)))
            f.setBold(True)
            p.setFont(f)
            for lab in ov["labels"]:
                pt, text = lab[0], lab[1]
                if np.isfinite(pt).all():
                    br = p.fontMetrics().boundingRect(text)
                    # left-leg label to the left of the joint, right-leg label to the right: never overlap
                    dx = -(br.width() + 14) if (len(lab) > 2 and lab[2] == "L") else 10
                    q = X(pt) + QPointF(dx, -6 if (len(lab) > 2 and lab[2] == "L") else 14)
                    box = QRectF(q.x() - 4, q.y() - br.height() + 2, br.width() + 8, br.height() + 2)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(0, 0, 0, 150))
                    p.drawRoundedRect(box, 4, 4)
                    p.setPen(QColor("white"))
                    p.drawText(q, text)
        p.end()


class ViewSource:
    """One camera: reader + time mapping + cached pose/pole data for overlays."""

    def __init__(self, path: str, role: str):
        self.reader = FrameReader(path)
        self.info = self.reader.info
        self.role = role
        self.pose = None
        self.display_xy = None   # smoothed keypoints for the overlay only (core.filters.display_pose)
        self.display_qc = {}
        self.smooth = True
        self.poles = {}
        self.contacts: dict[str, list[tuple[float, float]]] = {}  # side -> stance intervals on this view's clock
        self.last_index = -1

    def set_tracking(self, pose, poles):
        from ..core.filters import display_pose
        self.pose, self.poles = pose, poles
        self.display_xy, self.display_qc = (display_pose(pose.xy, pose.visibility, pose.fps)
                                            if pose is not None else (None, {}))

    def frame_at(self, t_view: float):
        i = int(round(t_view * self.info.fps))
        if i < 0 or i >= self.info.n_frames:
            return None, i
        if i != self.last_index:  # sequential reads are fast; FrameReader seeks only when needed
            fr = self.reader.read(i)
            self.last_index = i
            return fr, i
        return None, i

    def overlay_at(self, t_view: float, labels_fn=None) -> dict | None:
        if self.pose is None:
            return None
        k = int(np.argmin(np.abs(self.pose.t - t_view)))
        if abs(self.pose.t[k] - t_view) > 1.5 / max(self.pose.fps, 1):
            return None
        src_xy = self.display_xy if (self.smooth and self.display_xy is not None) else self.pose.xy
        xy, vis = src_xy[k], self.pose.visibility[k]
        poles = []
        for side, tr in self.poles.items():
            j = int(np.argmin(np.abs(tr.t - t_view)))
            if abs(tr.t[j] - t_view) < 1.5 / max(self.pose.fps, 1) and np.isfinite(tr.tip[j]).all():
                hand = self.pose.xy[k, 15 if side == "left" else 16]  # raw wrist: the display filter may hide it
                poles.append((hand, tr.tip[j], float(tr.confidence[j])))
        lo = max(0, k - int(self.pose.fps * 0.6))
        trail = [(src_xy[lo:k + 1, 25], QColor(89, 208, 190, 150)), (src_xy[lo:k + 1, 26], QColor(255, 179, 71, 150)),
                 (src_xy[lo:k + 1, 29], QColor(89, 208, 190, 110)), (src_xy[lo:k + 1, 30], QColor(255, 179, 71, 110))]
        labels = labels_fn(xy) if labels_fn else []
        contacts = []
        for side, ivs in self.contacts.items():
            for a, b in ivs:
                if a <= t_view <= b:
                    h, toe = (29, 31) if side == "left" else (30, 32)
                    contacts.append(((src_xy[k, h] + src_xy[k, toe]) / 2, side, t_view - a))
                    break
        return {"xy": xy, "vis": vis, "poles": poles, "trail": trail, "labels": labels, "contacts": contacts}

    def close(self):
        self.reader.close()


class SyncVideoPanel(QWidget):
    timeChanged = Signal(float)
    canvasClicked = Signal(str, float, float)   # role, x, y

    def __init__(self):
        super().__init__()
        self.sources: dict[str, ViewSource] = {}
        self.offset = 0.0            # t_side - t_front
        self.t = 0.0
        self.t_max = 0.0
        self.speed = 1.0
        self.labels_fn = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.canvas = {"side": VideoCanvas("Side view"), "front": VideoCanvas("Front view")}
        for role, c in self.canvas.items():
            fr = QFrame()
            fr.setObjectName("videoCard")
            fl = QVBoxLayout(fr)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.setSpacing(0)
            cap = QLabel(f"  {c.title}")
            cap.setObjectName("videoCaption")
            cap.setFixedHeight(22)
            fl.addWidget(cap)
            fl.addWidget(c)
            c.clicked.connect(lambda x, y, role=role: self.canvasClicked.emit(role, x, y))
            self.split.addWidget(fr)
        lay.addWidget(self.split, 1)
        # transport
        bar = QHBoxLayout()
        bar.setSpacing(4)

        def tb(text, tip, fn, check=False):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setAccessibleName(tip.split(" (")[0])  # screen readers announce the action, not the glyph
            b.setCheckable(check)
            b.clicked.connect(fn)
            bar.addWidget(b)
            return b
        self.btn_back10 = tb("⏮", "Back 10 frames (Shift+←)", lambda: self.step(-10))
        self.btn_back = tb("◀", "Previous frame (←)", lambda: self.step(-1))
        self.btn_play = tb("▶", "Play / pause (Space)", self.toggle_play, True)
        self.btn_fwd = tb("▶︎|", "Next frame (→)", lambda: self.step(1))
        self.btn_fwd10 = tb("⏭", "Forward 10 frames (Shift+→)", lambda: self.step(10))
        self.speed_box = QComboBox()
        for s in (0.1, 0.25, 0.5, 1.0, 2.0):
            self.speed_box.addItem(f"{s:g}×", s)
        self.speed_box.setCurrentIndex(3)
        self.speed_box.setToolTip("Playback speed")
        self.speed_box.currentIndexChanged.connect(lambda: setattr(self, "speed", self.speed_box.currentData()))
        bar.addWidget(self.speed_box)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.valueChanged.connect(lambda v: self.seek(v / 1000 * self.t_max, from_slider=True))
        bar.addWidget(self.slider, 1)
        self.time_label = QLabel("–")
        self.time_label.setObjectName("muted")
        self.time_label.setMinimumWidth(130)
        self.slider.setMinimumWidth(140)
        bar.addWidget(self.time_label)
        lay.addLayout(bar)
        tog = QHBoxLayout()
        tog.setSpacing(12)
        self.toggles = {}
        for key, lab in (("skeleton", "Skeleton"), ("poles", "Poles"), ("contacts", "Foot contacts"),
                         ("trails", "Trajectories"), ("labels", "Angle labels"), ("smooth", "Smoothed display")):
            cb = QCheckBox(lab)
            cb.setChecked(key in ("skeleton", "poles", "smooth", "contacts"))   # nothing but tracking lines on the video by default
            if key == "smooth":
                cb.setToolTip("Overlay only: 8 Hz zero-lag filter, implausible points hidden. Off = raw tracking. "
                              "Measurements always use their own processing.")
            cb.toggled.connect(lambda on, key=key: self._toggle(key, on))
            tog.addWidget(cb)
            self.toggles[key] = cb
        tog.addStretch(1)
        self.sync_label = QLabel("")
        self.sync_label.setObjectName("muted")
        tog.addWidget(self.sync_label)
        lay.addLayout(tog)
        self.timer = QTimer(self)
        self.timer.setInterval(15)
        self.timer.timeout.connect(self._tick)
        self._play_t0 = None

    # ------------------------------------------------------------------------------------
    def load(self, side: str | None, front: str | None, offset: float):
        self.stop()
        for s in self.sources.values():
            s.close()
        self.sources = {}
        errors = []
        for role, path in (("side", side), ("front", front)):
            if path:
                try:
                    self.sources[role] = ViewSource(path, role)
                except VideoError as e:
                    errors.append(str(e))
            self.canvas[role].parentWidget().setVisible(bool(path))
            self.canvas[role].message = "No recording for this view"
            self.canvas[role].set_frame(None)
        self.offset = offset
        master = self.sources.get("side") or self.sources.get("front")
        self.t_max = master.info.duration if master else 0.0
        self.t = 0.0
        self.seek(0.0)
        return errors

    def master_role(self):
        return "side" if "side" in self.sources else "front"

    def set_contacts(self, intervals: dict[str, list[tuple[float, float]]]):
        """Foot stance intervals on the master (side) clock; each view gets them on its own clock."""
        self._contacts_master = intervals
        for role, src in self.sources.items():
            shift = -self.offset if (role == "front" and "side" in self.sources) else 0.0
            src.contacts = {s: [(a + shift, b + shift) for a, b in ivs] for s, ivs in intervals.items()}
        self.seek(self.t, force=True)

    def view_time(self, role: str, t: float | None = None) -> float:
        t = self.t if t is None else t
        if role == "front" and "side" in self.sources:
            return t - self.offset
        return t

    def master_time_from_view(self, role: str, tv: float) -> float:
        return tv + self.offset if (role == "front" and "side" in self.sources) else tv

    def set_offset(self, off: float):
        self.offset = off
        if getattr(self, "_contacts_master", None):
            self.set_contacts(self._contacts_master)  # front-view contact times follow the new offset
        else:
            self.seek(self.t, force=True)

    def fps(self) -> float:
        m = self.sources.get(self.master_role())
        return m.info.fps if m else 30.0

    def _toggle(self, key, on):
        if key == "smooth":
            for src in self.sources.values():
                src.smooth = on
            self.seek(self.t, force=True)
            return
        for c in self.canvas.values():
            c.show[key] = on
            c.update()

    def seek(self, t: float, from_slider: bool = False, force: bool = False):
        t = float(np.clip(t, 0, max(self.t_max, 0)))
        if not force and abs(t - self.t) < 1e-6 and not from_slider and self.t != 0:
            return
        self.t = t
        for role, src in self.sources.items():
            tv = self.view_time(role)
            fr, i = src.frame_at(tv)
            c = self.canvas[role]
            if fr is not None:
                c.set_frame(fr)
            elif i < 0 or i >= src.info.n_frames:
                c.set_frame(None)
                c.message = "Outside this recording (sync offset)"
            c.overlay = src.overlay_at(tv, self.labels_fn)
            c.update()
        if not from_slider and self.t_max > 0:
            self.slider.blockSignals(True)
            self.slider.setValue(int(1000 * t / self.t_max))
            self.slider.blockSignals(False)
        f = int(round(t * self.fps()))
        self.time_label.setText(f"{t:.3f} s · frame {f}")
        self.time_label.setToolTip(f"Side-camera clock {t:.3f} s (frame {f})" + (
            f"\nFront-camera clock {self.view_time('front'):.3f} s" if len(self.sources) == 2 else ""))
        self.timeChanged.emit(t)

    def step(self, n: int):
        self.stop()
        self.seek(self.t + n / self.fps(), force=True)

    def toggle_play(self):
        if self.timer.isActive():
            self.stop()
        else:
            if self.t >= self.t_max - 1e-3:
                self.seek(0.0)
            self._play_t0 = (time.perf_counter(), self.t)
            self.timer.start()
            self.btn_play.setChecked(True)
            self.btn_play.setText("❚❚")

    def stop(self):
        self.timer.stop()
        self.btn_play.setChecked(False)
        self.btn_play.setText("▶")

    def _tick(self):
        wall0, t0 = self._play_t0
        t = t0 + (time.perf_counter() - wall0) * self.speed
        if t >= self.t_max:
            self.seek(self.t_max)
            self.stop()
            return
        self.seek(t)

    def keyPressEvent(self, e):
        k = e.key()
        shift = e.modifiers() & Qt.KeyboardModifier.ShiftModifier
        if k == Qt.Key.Key_Space:
            self.toggle_play()
        elif k == Qt.Key.Key_Left:
            self.step(-10 if shift else -1)
        elif k == Qt.Key.Key_Right:
            self.step(10 if shift else 1)
        else:
            super().keyPressEvent(e)


__all__ = ["SyncVideoPanel", "VideoCanvas"]
