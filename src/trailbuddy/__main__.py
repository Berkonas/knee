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
    if "--acceptance" in argv:  # headless end-to-end check of a packaged build on a folder of recordings
        return _acceptance(Path(argv[argv.index("--acceptance") + 1]), Path(argv[argv.index("--acceptance") + 2]))
    from PySide6.QtWidgets import QApplication

    from .ui.main_window import MainWindow
    from .ui.theme import apply_theme

    QApplication.setApplicationName("TrailBuddy Analyzer")
    QApplication.setOrganizationName("TrailBuddy")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    from .ui.state import app_settings
    pref = app_settings().value("appearance", "system")
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
        if "--open-trial" in argv:  # e.g. check that a study's videos and results load in a packaged build
            QTimer.singleShot(300, lambda: win.pages["workspace"].open_trial(argv[argv.index("--open-trial") + 1]))
        if "--screenshot" in argv:  # save what the window shows, to check a packaged build renders correctly
            shot = argv[argv.index("--screenshot") + 1]
            QTimer.singleShot(4400, lambda: win.grab().save(shot))
        QTimer.singleShot(4500, app.quit)
    return app.exec()


def _acceptance(folder: Path, out: Path) -> int:
    """Import -> pair -> sync -> track -> calculate -> export on real recordings, then check the export.

    Uses test body metrics (75 kg, 1.75 m) so the kinetics path runs; the values are labelled as test values."""
    import numpy as np
    import pandas as pd

    from .core import export, importer
    from .core.analysis import AnalysisSettings
    from .core.project import Project
    from .core.runner import run_pair

    proj = Project.new(out / "study", "Acceptance test")
    plan = importer.organise(folder, n_participants=1)
    trials = importer.apply_plan(proj, plan)
    for p in proj.participants:
        p.body_mass_kg, p.height_m, p.metrics_entered = 75.0, 1.75, True
    proj.save()
    print(f"imported {len(trials)} trial(s): " + ", ".join(f"{t.id} ({'+'.join(v.role for v in t.videos)})" for t in trials))
    ok = True
    for t in trials:
        res = run_pair(proj, t, AnalysisSettings(), {"backend": "rtmpose", "mode": "balanced", "stride": 1})
        export.export_trial(proj, t, res, out / "export", annotated_video=False)
        ts = pd.read_csv(out / "export" / t.participant_id / t.id / "timeseries.csv")
        same = np.allclose(ts.to_numpy(float), res.timeseries.to_numpy(float), rtol=1e-6, atol=1e-6, equal_nan=True)
        knee, mom = res.metric("knee_flexion_peak"), res.metric("knee_ext_moment_peak")
        print(f"{t.id}: sync {t.sync.get('offset_s', 0):+.3f} s ({t.sync.get('method', '-')}), "
              f"peak knee flexion {knee.value if knee else None}, knee moment {mom.value if mom else None} "
              f"({mom.kind if mom else '-'}), export matches: {same}")
        ok &= bool(same)
    print("acceptance ok" if ok else "acceptance FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
