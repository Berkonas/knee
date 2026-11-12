"""Entry point: `python -m trailbuddy` (GUI) or `python -m trailbuddy --selftest`."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--version" in argv:
        from . import __version__
        print(__version__)
        return 0
    if "--check-pose" in argv:  # packaging smoke test: video encode + MediaPipe in the built app
        import tempfile
        from pathlib import Path

        from .core import pose, video
        from .core.synthetic import render_frames, synthetic_descent

        p, _ = synthetic_descent(duration=0.5, fps=30, width=320, img_height=240, px_per_m=100)
        with tempfile.TemporaryDirectory() as td:
            v = video.write_video(render_frames(p), Path(td) / "v.mp4", 30)
            ps = pose.estimate(v, 0, 5, "full")
        print(f"pose check ok: {ps.n_frames} frames processed")
        return 0
    from PySide6.QtWidgets import QApplication

    from .ui.main_window import MainWindow
    from .ui.theme import QSS

    QApplication.setApplicationName("TrailBuddy Analyzer")
    QApplication.setOrganizationName("TrailBuddy")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    if "--no-restore" not in argv:
        win.open_last()
    if "--selftest" in argv:  # used by CI / packaging smoke tests
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
