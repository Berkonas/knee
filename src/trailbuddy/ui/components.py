"""Small custom widgets that give the app its look: cards, step accordion, segmented control,
metric cards with a reference band, and an interactive timeline strip."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)

from .theme import ACCENT, EVIDENCE_COLORS, INK, LINE, MUTED, SIDEBAR, SURFACE


class Card(QFrame):
    """White rounded panel with an optional title and subtitle."""

    def __init__(self, title: str = "", subtitle: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(16, 14, 16, 14)
        self.lay.setSpacing(8)
        if title:
            t = QLabel(title)
            t.setObjectName("cardTitle")
            self.lay.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("muted")
            s.setWordWrap(True)
            self.lay.addWidget(s)

    def add(self, w):
        self.lay.addWidget(w)
        return w


class StepCard(QFrame):
    """One step of the setup accordion: numbered header with a live status line; body expands on click."""

    toggled = Signal(object)

    def __init__(self, number: int, title: str, body: QWidget, hint: str = ""):
        super().__init__()
        self.setObjectName("step")
        self.number, self.title_text = number, title
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.header = QPushButton()
        self.header.setObjectName("stepHeader")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.clicked.connect(lambda: self.toggled.emit(self))
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(12, 9, 12, 9)
        self.badge = QLabel(str(number))
        self.badge.setObjectName("stepBadge")
        self.badge.setFixedSize(24, 24)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt = QVBoxLayout()
        txt.setSpacing(1)
        self.t = QLabel(title)
        self.t.setObjectName("stepTitle")
        self.status = QLabel(hint)
        self.status.setObjectName("stepStatus")
        self.status.setWordWrap(True)
        txt.addWidget(self.t)
        txt.addWidget(self.status)
        hl.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        hl.addLayout(txt, 1)
        self.header.setMinimumHeight(52)
        self.body = QWidget()
        self.body.setObjectName("stepBody")
        bl = QVBoxLayout(self.body)
        bl.setContentsMargins(14, 4, 14, 14)
        bl.addWidget(body)
        lay.addWidget(self.header)
        lay.addWidget(self.body)
        self.body.setVisible(False)

    def set_open(self, on: bool):
        self.body.setVisible(on)
        self.setProperty("open", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def is_open(self) -> bool:
        return self.body.isVisible()

    def set_status(self, text: str, done: bool = False):
        self.status.setText(text)
        self.badge.setText("✓" if done else str(self.number))
        self.badge.setProperty("done", done)
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)


class Accordion(QWidget):
    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(8)
        self.steps: list[StepCard] = []

    def add(self, step: StepCard) -> StepCard:
        step.toggled.connect(self._toggle)
        self.steps.append(step)
        self.lay.addWidget(step)
        return step

    def finish(self):
        self.lay.addStretch(1)
        if self.steps:
            self.steps[0].set_open(True)

    def _toggle(self, step: StepCard):
        opening = not step.is_open()
        for s in self.steps:
            s.set_open(s is step and opening)

    def open(self, step: StepCard):
        for s in self.steps:
            s.set_open(s is step)


class Segmented(QWidget):
    """macOS-style segmented control."""

    changed = Signal(int)

    def __init__(self, labels: list[str]):
        super().__init__()
        self.setObjectName("segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.group = QButtonGroup(self)
        self.buttons = []
        for i, lab in enumerate(labels):
            b = QPushButton(lab)
            b.setCheckable(True)
            b.setObjectName("segment")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(b, i)
            lay.addWidget(b)
            self.buttons.append(b)
        self.buttons[0].setChecked(True)
        self.group.idClicked.connect(self.changed)

    def set_index(self, i: int):
        self.buttons[i].setChecked(True)
        self.changed.emit(i)

    def index(self) -> int:
        return self.group.checkedId()


BAND_COLORS = {"below": "#2F6FAF", "within": "#1F6F66", "above": "#B26B0E"}
BAND_TEXT = {"below": "Below typical", "within": "Typical range", "above": "Above typical"}


class RangeBar(QWidget):
    """Horizontal reference band with a marker for the trial value."""

    def __init__(self, value: float | None, low: float, high: float, lo_unc=None, hi_unc=None):
        super().__init__()
        self.v, self.lo, self.hi, self.lu, self.hu = value, low, high, lo_unc, hi_unc
        self.setFixedHeight(22)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        span = self.hi - self.lo
        vals = [self.lo - 0.6 * span, self.hi + 0.6 * span]
        if self.v is not None:
            vals += [self.v]
        for u in (self.lu, self.hu):
            if u is not None:
                vals.append(u)
        a, b = min(vals), max(vals)
        X = lambda v: 6 + (v - a) / (b - a + 1e-12) * (w - 12)  # noqa: E731
        y = h / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E3E9E8"))
        p.drawRoundedRect(QRectF(6, y - 3, w - 12, 6), 3, 3)
        p.setBrush(QColor("#BFDCD7"))
        p.drawRoundedRect(QRectF(X(self.lo), y - 4, X(self.hi) - X(self.lo), 8), 4, 4)
        if self.lu is not None and self.hu is not None:
            p.setPen(QPen(QColor(INK), 1.5))
            p.drawLine(QPointF(X(self.lu), y), QPointF(X(self.hu), y))
        if self.v is not None:
            p.setPen(QPen(QColor("white"), 2))
            p.setBrush(QColor(INK))
            p.drawEllipse(QPointF(X(self.v), y), 6, 6)
        p.end()


class MetricCard(QFrame):
    """Value, unit, evidence badge, plain-language status vs a reference band, explanation on hover."""

    def __init__(self, label: str, value: str, unit: str, kind: str, kind_label: str, note: str = "",
                 band: tuple | None = None, status: str | None = None, ref_text: str = "", tooltip: str = "",
                 range_text: str = ""):
        super().__init__()
        self.setObjectName("metricCard")
        self.setToolTip(tooltip)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        top = QHBoxLayout()
        lab = QLabel(label)
        lab.setObjectName("metricLabel")
        lab.setWordWrap(True)
        top.addWidget(lab, 1)
        bg, fg = EVIDENCE_COLORS.get(kind, ("#EEE", "#333"))
        chip = QLabel(kind_label)
        chip.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:8px; padding:1px 7px; font-size:10px;")
        top.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        vrow = QHBoxLayout()
        v = QLabel(value)
        v.setObjectName("metricValue" if kind != "unavailable" else "metricValueNA")
        u = QLabel(unit if kind != "unavailable" else "")
        u.setObjectName("metricUnit")
        vrow.addWidget(v)
        vrow.addWidget(u, 0, Qt.AlignmentFlag.AlignBottom)
        vrow.addStretch(1)
        if status:
            st = QLabel(BAND_TEXT[status])
            st.setStyleSheet(f"color:{BAND_COLORS[status]}; font-weight:600; font-size:11px;")
            vrow.addWidget(st, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(vrow)
        if band is not None:
            lay.addWidget(RangeBar(*band))
        if ref_text:
            r = QLabel(ref_text)
            r.setObjectName("metricRef")
            r.setWordWrap(True)
            lay.addWidget(r)
        if range_text:
            r = QLabel(range_text)
            r.setObjectName("metricRef")
            r.setWordWrap(True)
            lay.addWidget(r)
        if note:
            n = QLabel(note)
            n.setObjectName("metricNote")
            n.setWordWrap(True)
            lay.addWidget(n)
        lay.addStretch(1)
        self.setMinimumWidth(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class TimelineStrip(QWidget):
    """Fast interactive strip under the video: knee angle curve, stance bars and a playhead.

    Click or drag to seek. Painted with QPainter, so it stays smooth during playback and resizing.
    """

    seek = Signal(float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(86)
        self.setMaximumHeight(110)
        self.t = None
        self.y = None
        self.lanes: list[tuple[str, np.ndarray, str]] = []
        self.playhead = None
        self.window = None
        self.label = "Knee flexion"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click or drag to jump the video to that moment")

    def set_data(self, t, y, lanes, label="Knee flexion (deg)"):
        self.t, self.y, self.lanes, self.label = np.asarray(t), np.asarray(y), lanes, label
        self.update()

    def clear(self):
        self.t = None
        self.update()

    def set_playhead(self, ts: float):
        self.playhead = ts
        self.update()

    def _x(self, tt):
        w = self.width() - 70
        return 60 + (tt - self.t[0]) / max(self.t[-1] - self.t[0], 1e-9) * w

    def mousePressEvent(self, e):
        self._seek(e.position().x())

    def mouseMoveEvent(self, e):
        if e.buttons():
            self._seek(e.position().x())

    def _seek(self, x):
        if self.t is None or len(self.t) < 2:
            return
        w = self.width() - 70
        tt = self.t[0] + (x - 60) / max(w, 1) * (self.t[-1] - self.t[0])
        self.seek.emit(float(np.clip(tt, self.t[0], self.t[-1])))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(SURFACE))
        p.setPen(QPen(QColor(LINE), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 8, 8)
        f = QFont(self.font())
        f.setPointSizeF(max(8.0, f.pointSizeF() - 2))
        p.setFont(f)
        if self.t is None or len(self.t) < 2:
            p.setPen(QColor(MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Timeline appears after the analysis")
            p.end()
            return
        h = self.height()
        lane_h = 9
        top_curve, bot_curve = 10, h - 12 - lane_h * len(self.lanes)
        # lanes
        for i, (name, mask, color) in enumerate(self.lanes):
            y0 = bot_curve + 6 + i * lane_h
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(4, y0 - 3, 54, lane_h + 2), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, name)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            m = np.asarray(mask).astype(bool)
            edges = np.flatnonzero(np.diff(np.concatenate(([0], m.astype(int), [0]))))
            for a, b in zip(edges[::2], edges[1::2]):
                x1, x2 = self._x(self.t[a]), self._x(self.t[b - 1])
                p.drawRoundedRect(QRectF(x1, y0, max(2, x2 - x1), lane_h - 3), 2, 2)
        # curve
        y = self.y
        ok = np.isfinite(y)
        if ok.sum() > 1:
            lo, hi = np.nanmin(y), np.nanmax(y)
            Y = lambda v: bot_curve - (v - lo) / max(hi - lo, 1e-9) * (bot_curve - top_curve)  # noqa: E731
            path = QPainterPath()
            started = False
            for tt, v in zip(self.t, y):
                if not np.isfinite(v):
                    started = False
                    continue
                pt = QPointF(self._x(tt), Y(v))
                if started:
                    path.lineTo(pt)
                else:
                    path.moveTo(pt)
                    started = True
            p.setPen(QPen(QColor(ACCENT), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(4, top_curve - 4, 54, 14), Qt.AlignmentFlag.AlignRight, f"{hi:.0f}°")
            p.drawText(QRectF(4, bot_curve - 10, 54, 14), Qt.AlignmentFlag.AlignRight, f"{lo:.0f}°")
            p.drawText(QRectF(64, 1, 300, 14), Qt.AlignmentFlag.AlignLeft, self.label)
        if self.playhead is not None and self.t[0] <= self.playhead <= self.t[-1]:
            x = self._x(self.playhead)
            p.setPen(QPen(QColor("#B3261E"), 1.5))
            p.drawLine(QPointF(x, 4), QPointF(x, h - 4))
        p.end()

    def sizeHint(self):
        return QSize(600, 96)


__all__ = ["Card", "StepCard", "Accordion", "Segmented", "MetricCard", "RangeBar", "TimelineStrip", "SIDEBAR"]
