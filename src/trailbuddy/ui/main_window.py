from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QMessageBox, QStackedWidget, QToolBar, QWidget

from .. import APP_NAME, __version__
from ..core.paths import assets_dir
from .components import Segmented
from .methods_page import MethodsPage
from .project_page import ProjectPage
from .results_page import ResultsPage
from .state import AppState
from .theme import apply_theme
from .workspace import WorkspacePage

MODES = [("Analyse", "workspace"), ("Study", "project"), ("Compare", "results"), ("Methods", "methods")]


class MainWindow(QMainWindow):
    def __init__(self, state: AppState | None = None):
        super().__init__()
        self.state = state or AppState()
        self.setWindowTitle(APP_NAME)
        self.setUnifiedTitleAndToolBarOnMac(True)
        icon = assets_dir() / "icon.png"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1480, 920)
        self.setMinimumSize(QSize(1080, 680))
        self.pages = {"workspace": WorkspacePage(self.state), "project": ProjectPage(self.state),
                      "results": ResultsPage(self.state), "methods": MethodsPage(self.state)}
        self.stack = QStackedWidget()
        for _, key in MODES:
            self.stack.addWidget(self.pages[key])
        self.setCentralWidget(self.stack)
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        title = QLabel(f"  {APP_NAME}")
        title.setObjectName("cardTitle")
        tb.addWidget(title)
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding, spacer.sizePolicy().verticalPolicy())
        from PySide6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.mode = Segmented([m for m, _ in MODES])
        self.mode.changed.connect(self._switch_mode)
        tb.addWidget(self.mode)
        spacer2 = QWidget()
        spacer2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer2)
        self.study_label = QLabel("No study open  ")
        self.study_label.setObjectName("muted")
        tb.addWidget(self.study_label)
        self.state.status.connect(lambda m: self.statusBar().showMessage(m, 8000))
        self.state.projectChanged.connect(self._project_changed)
        self.state.openTrial.connect(self._open_trial)
        self.pages["workspace"].browser.importRequested.connect(self.import_recordings)
        self._reduce_motion = self.reduce_motion()
        self._menus()
        self.statusBar().showMessage("Ready. Open or create a study, then import recordings.")

    def _menus(self):
        mb = self.menuBar()
        m = mb.addMenu("&File")
        for text, key, fn in (("New study…", QKeySequence.StandardKey.New, self.pages["project"].new_project),
                              ("Open study…", QKeySequence.StandardKey.Open, self.pages["project"].open_project),
                              ("Import recordings…", "Ctrl+I", self.import_recordings)):
            a = QAction(text, self)
            a.setShortcut(key)
            a.triggered.connect(fn)
            m.addAction(a)
        m.addSeparator()
        a = QAction("Export all results…", self)
        a.setShortcut("Ctrl+E")
        a.triggered.connect(self.pages["results"].export)
        m.addAction(a)
        m.addSeparator()
        a = QAction("Quit", self)
        a.setShortcut(QKeySequence.StandardKey.Quit)
        a.triggered.connect(self.close)
        m.addAction(a)
        v = mb.addMenu("&View")
        for i, (label, _) in enumerate(MODES):
            a = QAction(label, self)
            a.setShortcut(f"Ctrl+{i + 1}")
            a.triggered.connect(lambda _=False, i=i: self.mode.set_index(i))
            v.addAction(a)
        v.addSeparator()
        ap = v.addMenu("Appearance")
        grp = QActionGroup(self)
        for lab, val in (("System", None), ("Light", "light"), ("Dark", "dark")):
            a = QAction(lab, self, checkable=True)
            a.setChecked(val is None)
            a.triggered.connect(lambda _=False, val=val: self.set_appearance(val))
            grp.addAction(a)
            ap.addAction(a)
        rm = QAction("Reduce motion", self, checkable=True)
        rm.setChecked(self._reduce_motion)
        rm.toggled.connect(lambda on: (setattr(self, "_reduce_motion", on), self.state.settings.setValue("reduce_motion", on)))
        v.addAction(rm)
        pb = mb.addMenu("&Playback")
        ws = self.pages["workspace"]
        for text, key, fn in (("Play / pause", "Space", ws.video.toggle_play),
                              ("Previous frame", "Left", lambda: ws.video.step(-1)),
                              ("Next frame", "Right", lambda: ws.video.step(1)),
                              ("Back 10 frames", "Shift+Left", lambda: ws.video.step(-10)),
                              ("Forward 10 frames", "Shift+Right", lambda: ws.video.step(10))):
            a = QAction(text, self)
            a.setShortcut(key)
            a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            a.triggered.connect(fn)
            pb.addAction(a)
        h = mb.addMenu("&Help")
        a = QAction(f"About {APP_NAME}", self)
        a.triggered.connect(self._about)
        h.addAction(a)

    def reduce_motion(self) -> bool:
        """User setting, or the operating system's Reduce Motion preference (macOS)."""
        v = self.state.settings.value("reduce_motion", None)
        if v is not None:
            return str(v).lower() in ("true", "1")
        import subprocess
        import sys
        if sys.platform == "darwin":
            try:
                r = subprocess.run(["defaults", "read", "com.apple.universalaccess", "reduceMotion"],
                                   capture_output=True, text=True, timeout=2)
                return r.stdout.strip() == "1"
            except Exception:
                return False
        return False

    def _switch_mode(self, i: int):
        """Short cross-fade into the new page (160 ms); instant when reduced motion is preferred."""
        self.stack.setCurrentIndex(i)
        if self._reduce_motion:
            return
        from PySide6.QtCore import QEasingCurve, QPropertyAnimation
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        w = self.stack.currentWidget()
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", w)
        anim.setDuration(160)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: w.setGraphicsEffect(None))  # remove: effects slow video painting
        anim.start()
        self._anim = anim

    def set_appearance(self, val):
        apply_theme(QApplication.instance(), val)
        self.state.settings.setValue("appearance", val or "system")
        ws = self.pages["workspace"]
        ws.plots.redraw()
        for c in ws.video.canvas.values():
            c.update()

    def import_recordings(self):
        from .import_dialog import ImportDialog
        if self.state.project is None:
            QMessageBox.information(self, "Create a study first",
                                    "Create a study (File > New study) to hold the imported trials and results.")
            self.mode.set_index(1)
            return
        ImportDialog(self, self.state).exec()

    def _about(self):
        QMessageBox.about(self, APP_NAME, f"<b>{APP_NAME}</b> {__version__}<br>Video-based biomechanics for "
                          "trekking-pole descent experiments (CREATE Lab class project).<br><br>Body tracking: RTMPose / "
                          "YOLOX via rtmlib (Apache-2.0), MediaPipe (Apache-2.0). See RESEARCH_PIPELINE.md.")

    def _project_changed(self):
        p = self.state.project
        self.study_label.setText(f"Study: {p.name}  " if p else "No study open  ")
        if p:
            self.statusBar().showMessage(f"Opened {p.name}: {len(p.trials)} trials, "
                                         f"{sum(t.status == 'analysed' for t in p.trials)} analysed", 8000)

    def _open_trial(self, tid: str, page: str):
        self.mode.set_index(0)
        self.pages["workspace"].browser.select_trial(tid)
        self.pages["workspace"].open_trial(tid)

    def open_last(self):
        last = self.state.settings.value("last_project")
        if last and (Path(last) / "project.json").exists():
            self.pages["project"].load_path(last)
