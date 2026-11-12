# Developer guide

## Setup

```bash
# needs uv: https://docs.astral.sh/uv/
uv sync --extra dev          # Python 3.12 + locked dependencies in .venv
uv run python -m trailbuddy  # start the app
uv run pytest -q             # all tests (GUI tests run offscreen)
uv run ruff check src tests  # lint
```

Python 3.10–3.12 is supported, limited by the MediaPipe wheels. Exact dependency versions are pinned in `uv.lock`.

## Layout

```
src/trailbuddy/core/   analysis (no Qt): video, sync, pose, kinematics, events, dynamics, pole, analysis,
                       runner, compare, export, plots, metrics, project, synthetic, demo, triangulation
src/trailbuddy/ui/     PySide6 app: main_window, project_page, single_page, two_page, results_page, methods_page
tests/                 unit, integration and GUI tests (synthetic ground truth)
scripts/               install/run scripts, icon generator
packaging/             PyInstaller spec
docs/                  methods, guides, research notes, project documents
```

## Building standalone apps

```bash
uv sync --extra build
uv run python -c "from trailbuddy.core.pose import model_path; model_path('full')"   # bundle the model
uv run pyinstaller packaging/trailbuddy.spec --noconfirm
"dist/TrailBuddy Analyzer.app/Contents/MacOS/TrailBuddy Analyzer" --check-pose        # smoke test
```

CI: `.github/workflows/ci.yml` runs lint, tests and an app-start check on Ubuntu, macOS and Windows.
`build.yml` (manual trigger or a `v*` tag) builds and smoke-tests the macOS and Windows apps and uploads them.

## Adding a pole detector

Implement the `PoleDetector` protocol in `core/pole.py`: `detect(frame, prev) -> (x, y, confidence) | None`. Then
pass it to `pole.track`. Return `None` when unsure, because missing frames must stay NaN.

## How this was built

The project brief and protocol were read first, and the brief's requirements took priority over app features.
Library and literature research was delegated to a research agent (outputs in `docs/research/`). An independent
agent reviewed every biomechanics equation. Process skills (Superpowers, Frontend Design) were used for design and
verification. *UI UX Pro Max* and *Vercel React Best Practices* target web/React stacks, so they were not used for
this Qt app. *Grill Me*, *GSD*, *Context Mode* and *Handoff* were not installed: they add interactive or
process overhead that the brief asked us to avoid. No third-party install scripts were run.
