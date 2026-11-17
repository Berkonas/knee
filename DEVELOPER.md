# Developer guide

## Install and run from source

```bash
# 1. uv (Python manager): https://docs.astral.sh/uv/   (macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh)
uv sync --extra dev            # Python 3.12 + pinned dependencies (uv.lock) in ./.venv
uv run python -m trailbuddy     # start the app
uv run pytest -q               # all tests (GUI tests run offscreen)
uv run ruff check src tests    # lint
```

The first analysis downloads the pose models once (about 160 MB) into `models/`. Downloaded models are not
committed to git.

## Architecture

```
src/trailbuddy/
  core/                      no Qt imports: everything here is testable headless
    dataset.py               scan a folder, read metadata, detect views, group participants, pair by audio
    importer.py              turn a scanned folder into participants and trials (with confidence flags)
    pose_rtm.py              RTMPose + YOLOX (rtmlib / ONNX Runtime) with participant locking
    pose.py                  MediaPipe Pose (alternative backend)
    pole_auto.py             markerless pole detection anchored at the hands
    pole.py                  pole tracks, manual annotations, colour-marker tracker
    pipeline.py              per-recording processing with an on-disk cache
    sync.py                  audio clap, envelope correlation, visual clap, drift check, resampling
    kinematics.py signal.py  filtering, spike removal, 2D joint angles
    frontal.py               front-view (frontal-plane) measures
    events.py dynamics.py    contacts, inverse dynamics, scenario model, arm moments
    analysis.py runner.py    trial analysis (side + front), saving and loading results
    compare.py export.py plots.py metrics.py reference.py
  ui/                        PySide6 interface
    main_window.py           modes: Analyse | Study | Compare | Methods
    workspace.py             browser | synchronised videos + linked plots | inspector
    sync_video.py data_plots.py browser.py import_dialog.py pairing_dialog.py theme.py
tests/                       unit, integration and GUI tests (synthetic ground truth)
packaging/                   PyInstaller spec      scripts/  install/run scripts, icon generator
```

Data flow: recordings → `pipeline.process_recording` (pose + poles over the whole file, cached in
`<study>/cache`) → `runner.run_pair` (slices the cache by the trial interval and sync offset, runs the side-view
`analysis.analyse` and the front-view `frontal.analyse_front`) → `<study>/trials/<trial>/` (CSV + JSON).
The UI never runs inference on the UI thread. All long jobs go through `ui.widgets.Worker`, which supports
progress reporting and cancellation.

## Performance notes

* RTMPose-m with YOLOX-m runs at about 0.1 s per 1080p frame on an Apple-silicon CPU, so a 13 s, 60 fps recording takes
  about 1.5 minutes once and is then cached. Use "Every 2nd frame" or "Fast" in Settings for quicker previews.
* GPU: on Windows or Linux with an NVIDIA GPU, install `onnxruntime-gpu` instead of `onnxruntime`. The app then picks CUDA
  automatically and falls back to CPU if the CUDA session fails. CoreML on macOS was slower and less stable in our tests, so the app uses the CPU there.
* Playback decodes frames sequentially and paces them by wall-clock time, skipping frames instead of slowing
  down, so both views stay on the same instant.

## Packaging

```bash
uv sync --extra build
uv run python -c "from trailbuddy.core.pose import model_path; model_path('full')"
uv run python -c "from trailbuddy.core import pose_rtm; pose_rtm.detector('balanced', 'cpu')"
uv run pyinstaller packaging/trailbuddy.spec --noconfirm
"dist/TrailBuddy Analyzer.app/Contents/MacOS/TrailBuddy Analyzer" --check-pose   # smoke test (macOS)
```

On GitHub, `.github/workflows/build.yml` (run it manually or push a `v*` tag) builds and smoke-tests the macOS (arm64)
and Windows (x64) apps and uploads them as artifacts. `.github/workflows/ci.yml` runs lint and the tests on
Ubuntu, macOS and Windows for every push.

The builds are **not code-signed**. On macOS, right-click the app and choose Open the first time. On Windows,
SmartScreen asks once: click More info, then Run anyway.

## Logs and troubleshooting

* Source runs write `logs/app.log` in the repository. Packaged apps write `app.log` in the per-user data folder
  (`~/Library/Application Support/TrailBuddy Analyzer/logs` on macOS, `%APPDATA%\TrailBuddy Analyzer\logs` on Windows).
* For a stale cache, delete `<study>/cache`. It is rebuilt on the next analysis.
* For more problems, see [docs/troubleshooting.md](docs/troubleshooting.md).

## Conventions

* Every metric carries an evidence label (`metrics.KINDS`) and a camera view. New metrics need an entry in
  `metrics.INFO` (what / why / can conclude / cannot conclude).
* Never fill long gaps or invent coordinates. Missing data stays NaN and is reported.
* Original recordings are never modified. Trimmed or annotated videos are always written as new files.
