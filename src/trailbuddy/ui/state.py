from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal

from ..core.project import Project


class AppState(QObject):
    projectChanged = Signal()
    trialsChanged = Signal()
    resultsChanged = Signal()
    openTrial = Signal(str, str)  # trial id, page ('single' | 'two')
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.settings = QSettings("TrailBuddy", "Analyzer")

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
