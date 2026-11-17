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
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.settings = app_settings()

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
