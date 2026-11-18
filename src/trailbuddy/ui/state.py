from __future__ import annotations

import os

from PySide6.QtCore import QObject, QSettings, Signal

from ..core.project import Project


def app_settings() -> QSettings:
    """The user's preferences. Tests set TRAILBUDDY_SETTINGS_APP so they never touch the real ones."""
    return QSettings("TrailBuddy", os.environ.get("TRAILBUDDY_SETTINGS_APP", "Analyzer"))


class AppState(QObject):
    projectChanged = Signal()
    trialsChanged = Signal()
    resultsChanged = Signal()
    openTrial = Signal(str, str)  # trial id, page ('single' | 'two')
    trialSelected = Signal(str)   # emitted when Analyse shows a trial (other pages follow it)
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.settings = app_settings()
        self.busy = False      # an analysis job is running: trial edits that would misfile its results wait
        self.workers: list = []  # keep Python references until each job's thread ends

    def refuse_if_busy(self, parent) -> bool:
        if self.busy:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(parent, "Analysis running",
                                    "Wait for the running analysis to finish (or cancel it) before changing trials.")
            return True
        return False

    def set_project(self, p: Project | None) -> None:
        self.project = p
        if p is not None and p.root is not None:
            self.settings.setValue("last_project", str(p.root))
        self.projectChanged.emit()
        self.trialsChanged.emit()
        self.resultsChanged.emit()

    def save(self) -> None:
        if self.project:
            self.project.save()
