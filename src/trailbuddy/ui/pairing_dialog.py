"""Correct the front/side pairing of a trial (choose any recording in the study or a file on disk)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel, QPushButton

from ..core import dataset
from ..core.project import CameraVideo


class PairingDialog(QDialog):
    def __init__(self, parent, project, trial):
        super().__init__(parent)
        self.project, self.trial = project, trial
        self.setWindowTitle(f"Pairing · {trial.id}")
        self.setMinimumWidth(560)
        f = QFormLayout(self)
        f.addRow(QLabel("Choose which recording is the side view and which is the front view of this trial. "
                        "The sync offset is recomputed from the audio when both are set."))
        all_files = sorted({v.path for t in project.trials for v in t.videos})
        self.side, self.front = QComboBox(), QComboBox()
        for box, role in ((self.side, "side"), (self.front, "front")):
            box.addItem("(none)", "")
            for pth in all_files:
                box.addItem(Path(pth).name, pth)
            cur = next((v.path for v in trial.videos if v.role == role), "")
            box.setCurrentIndex(max(0, box.findData(cur)))
            btn = QPushButton("Other file…")
            btn.clicked.connect(lambda _=False, b=box: self._pick(b))
            f.addRow(f"{role.capitalize()} view", box)
            f.addRow("", btn)
        self.info = QLabel("")
        f.addRow(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def _pick(self, box):
        p, _ = QFileDialog.getOpenFileName(self, "Recording", "", "Videos (*.mov *.mp4 *.MOV *.MP4 *.m4v *.avi)")
        if p:
            box.addItem(Path(p).name, p)
            box.setCurrentIndex(box.count() - 1)

    def _save(self):
        side, front = self.side.currentData(), self.front.currentData()
        if not side and not front:
            self.info.setText("Choose at least one recording.")
            return
        vids = []
        for path, role in ((side, "side"), (front, "front")):
            if path:
                r = dataset.read_metadata(path)
                vids.append(CameraVideo(path, role, role.capitalize(),
                                        {k: getattr(r, k) for k in ("width", "height", "fps", "duration_s", "n_frames",
                                                                    "device", "codec", "hdr", "has_audio", "creation_time")}))
        self.trial.videos = vids
        self.trial.sync = {"method": "manual pairing"}
        if side and front:
            try:
                r, lag = dataset.envelope_ncc(dataset.audio_envelope(side), dataset.audio_envelope(front))
                self.trial.sync.update({"offset_s": lag, "method": "audio envelope", "pair_score": round(r, 3),
                                        "pair_status": "manual"})
            except Exception:
                self.trial.sync["offset_s"] = 0.0
        self.trial.status = "new"
        self.accept()
