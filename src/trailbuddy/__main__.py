"""Entry point: `python -m trailbuddy` (GUI) or `python -m trailbuddy --selftest`."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--version" in argv:
        from . import __version__
        print(__version__)
        return 0
    if "--check-pose" in argv:  # packaging smoke test: video encode + MediaPipe in the built app
        import tempfile

        from .core import pose, video
        from .core.synthetic import render_frames, synthetic_descent

        p, _ = synthetic_descent(duration=0.5, fps=30, width=320, img_height=240, px_per_m=100)
        with tempfile.TemporaryDirectory() as td:
            v = video.write_video(render_frames(p), Path(td) / "v.mp4", 30)
            ps = pose.estimate(v, 0, 5, "full")
            from .core import pose_rtm
            pr = pose_rtm.estimate(v, 0, 5)
        print(f"pose check ok: MediaPipe {ps.n_frames} frames, RTMPose {pr.n_frames} frames processed")
        return 0
    from PySide6.QtWidgets import QApplication

    from .ui.main_window import MainWindow
    from .ui.theme import apply_theme

    QApplication.setApplicationName("TrailBuddy Analyzer")
    QApplication.setOrganizationName("TrailBuddy")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    from PySide6.QtCore import QSettings
    pref = QSettings("TrailBuddy", "Analyzer").value("appearance", "system")
    apply_theme(app, None if pref in (None, "system") else pref)
    win = MainWindow()
    win.show()
    if "--no-restore" not in argv:
        win.open_last()
    import logging
    from .core.paths import user_data_dir, is_frozen
    log_dir = (user_data_dir() if is_frozen() else Path(__file__).resolve().parents[2]) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_dir / "app.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.excepthook = lambda *exc: logging.getLogger("trailbuddy").error("Unhandled exception", exc_info=exc)
    if "--selftest" in argv:  # used by CI / packaging smoke tests
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
