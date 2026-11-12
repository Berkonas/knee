"""Draw the app icon (contour lines, a descending knee and a trekking pole) -> assets/icon.png/.ico/.icns.

Run: uv run python scripts/make_icon.py
"""

import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen

ROOT = Path(__file__).resolve().parents[1]


def draw(size: int = 1024) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 1024
    m = 100 * s
    rect = QRectF(m, m, size - 2 * m, size - 2 * m)
    bg = QPainterPath()
    bg.addRoundedRect(rect, 185 * s, 185 * s)
    p.fillPath(bg, QColor("#17302D"))
    p.setClipPath(bg)
    # topographic contour lines
    pen = QPen(QColor("#2B5852"), 14 * s)
    p.setPen(pen)
    for k in range(7):
        path = QPainterPath()
        y0 = 260 * s + k * 95 * s
        path.moveTo(0, y0)
        for x in range(0, size + 1, 16):
            y = y0 + 38 * s * math.sin(x / size * 2 * math.pi * 1.2 + k * 0.6) + 0.18 * x
            path.lineTo(x, y)
        p.drawPath(path)
    # leg: hip -> knee -> ankle (flexed knee), with angle arc
    hip, knee, ankle = QPointF(395 * s, 300 * s), QPointF(560 * s, 520 * s), QPointF(440 * s, 760 * s)
    p.setPen(QPen(QColor("#EEF1F0"), 46 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    path = QPainterPath(hip); path.lineTo(knee); path.lineTo(ankle)
    p.drawPath(path)
    p.setPen(QPen(QColor("#E69F00"), 18 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    r = 95 * s
    p.drawArc(QRectF(knee.x() - r, knee.y() - r, 2 * r, 2 * r), int(126 * 16), int(117 * 16))
    # trekking pole
    p.setPen(QPen(QColor("#7FC7BC"), 22 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(660 * s, 330 * s), QPointF(740 * s, 800 * s))
    p.setBrush(QColor("#7FC7BC")); p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(740 * s, 806 * s), 20 * s, 20 * s)
    for pt in (hip, knee, ankle):
        p.setBrush(QColor("#17302D")); p.drawEllipse(pt, 20 * s, 20 * s)
        p.setBrush(QColor("#EEF1F0")); p.drawEllipse(pt, 11 * s, 11 * s)
    p.end()
    return img


def main():
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    img = draw(1024)
    img.save(str(out / "icon.png"))
    img.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(str(out / "icon.ico"))
    if sys.platform == "darwin" and shutil.which("iconutil"):
        with tempfile.TemporaryDirectory() as td:
            iset = Path(td) / "icon.iconset"
            iset.mkdir()
            for n in (16, 32, 128, 256, 512):
                for scale in (1, 2):
                    px = n * scale
                    name = f"icon_{n}x{n}{'@2x' if scale == 2 else ''}.png"
                    img.scaled(px, px, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(str(iset / name))
            subprocess.run(["iconutil", "-c", "icns", str(iset), "-o", str(out / "icon.icns")], check=True)
    print("icons written to", out)


if __name__ == "__main__":
    main()
