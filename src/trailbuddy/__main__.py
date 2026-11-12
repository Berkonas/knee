"""Entry point: `python -m trailbuddy` (GUI) or `python -m trailbuddy --selftest`."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--version" in argv:
        from . import __version__
        print(__version__)
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
