from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..core.paths import assets_dir
from .methods_page import MethodsPage
from .project_page import ProjectPage
from .results_page import ResultsPage
from .single_page import SinglePage
from .state import AppState
from .two_page import TwoPage

PAGES = [("Study", "project"), ("One camera", "single"), ("Two cameras", "two"), ("Results", "results"),
         ("Methods", "methods")]


class MainWindow(QMainWindow):
    def __init__(self, state: AppState | None = None):
        super().__init__()
        self.state = state or AppState()
        self.setWindowTitle(APP_NAME)
        icon = assets_dir() / "icon.png"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1360, 860)
        self.setMinimumSize(QSize(1000, 680))
        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(196)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        t = QLabel("TrailBuddy\nAnalyzer"); t.setObjectName("appTitle")
        sub = QLabel("Pole descent biomechanics"); sub.setObjectName("appSubtitle")
        sl.addWidget(t); sl.addWidget(sub)
        self.nav = QListWidget(); self.nav.setObjectName("nav")
        for label, key in PAGES:
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.nav.addItem(it)
        sl.addWidget(self.nav, 1)
        self.project_badge = QLabel("No study open"); self.project_badge.setObjectName("projectBadge")
        self.project_badge.setWordWrap(True)
        sl.addWidget(self.project_badge)
        h.addWidget(side)
        self.stack = QStackedWidget()
        self.pages = {"project": ProjectPage(self.state), "single": SinglePage(self.state), "two": TwoPage(self.state),
                      "results": ResultsPage(self.state), "methods": MethodsPage(self.state)}
        for _, key in PAGES:
            self.stack.addWidget(self.pages[key])
        h.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.state.status.connect(lambda m: self.statusBar().showMessage(m, 8000))
        self.state.projectChanged.connect(self._project_changed)
        self.state.openTrial.connect(self._open_trial)
        self._menus()
        self.statusBar().showMessage("Ready. Create or open a study to begin.")

    def _menus(self):
        m = self.menuBar().addMenu("&File")
        for text, key, fn in (("New study…", QKeySequence.StandardKey.New, self.pages["project"].new_project),
                              ("Open study…", QKeySequence.StandardKey.Open, self.pages["project"].open_project)):
            a = QAction(text, self); a.setShortcut(key); a.triggered.connect(fn); m.addAction(a)
        m.addSeparator()
        a = QAction("Quit", self); a.setShortcut(QKeySequence.StandardKey.Quit); a.triggered.connect(self.close)
        m.addAction(a)
        v = self.menuBar().addMenu("&View")
        for i, (label, _) in enumerate(PAGES):
            a = QAction(label, self); a.setShortcut(f"Ctrl+{i + 1}")
            a.triggered.connect(lambda _=False, i=i: self.nav.setCurrentRow(i)); v.addAction(a)
        hm = self.menuBar().addMenu("&Help")
        a = QAction(f"About {APP_NAME}", self); a.triggered.connect(self._about); hm.addAction(a)

    def _about(self):
        QMessageBox.about(self, APP_NAME, f"<b>{APP_NAME}</b> {__version__}<br>Video-based biomechanics for "
                          "trekking-pole descent experiments (class project).<br><br>Pose estimation: MediaPipe Pose "
                          "(Apache-2.0). See README and docs/methods.md for methods and limitations.")

    def _project_changed(self):
        p = self.state.project
        self.project_badge.setText(f"Study: {p.name}" if p else "No study open")

    def _open_trial(self, tid: str, page: str):
        self.nav.setCurrentRow([k for _, k in PAGES].index(page))
        self.pages[page].reload_trials()
        self.pages[page].select_trial(tid)

    def open_last(self):
        last = self.state.settings.value("last_project")
        if last and (Path(last) / "project.json").exists():
            self.pages["project"].load_path(last)
