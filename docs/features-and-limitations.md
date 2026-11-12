# Features and limitations (v1)

Status key: **Tested** = implemented and covered by automated tests (synthetic data or analytic examples).
**Awaiting validation** = implemented and runs, but it needs real participant recordings or reference
measurements before we can claim it is accurate.

## Implemented

| Feature | Status | Test evidence |
|---|---|---|
| Video import, playback, frame stepping, interval selection | Tested | `test_ui.py`, `test_sync_video.py` |
| Non-destructive trimming and aligned-clip export | Tested | the original file's bytes are compared before and after |
| Clap sync from audio (different fps and start times) | Tested | known offsets recovered within 5 ms (raw audio) and 8 ms (AAC MP4) |
| Manual clap-frame sync, offset fine-tuning, linked playback | Tested | `test_two_camera_sync_controls` |
| MediaPipe pose estimation | Runs (tested); **accuracy awaiting validation** on our videos | `test_pose_model.py` (runs, no invented frames); built app `--check-pose` |
| 2D joint angles, filtering, gap handling | Tested | exact to < 0.01° on noise-free synthetic data; < 2° RMS with 1 px noise and 6 Hz filtering |
| Gait events (foot contact, stance, step time, cadence) | Tested on synthetic data; **awaiting validation** on real stairs | within 0.06 s of the true events |
| Scale from clicked points, height, or measured segments | Tested | `test_scale_*` |
| Pole colour-marker tracking | Tested on rendered markers; **awaiting validation** on real poles | within 1.5 px; occluded frames stay empty |
| Manual pole annotation with flagged interpolation | Tested | `test_manual_annotation_*` |
| Pole contact timing and angle | Tested on synthetic data; **awaiting validation** | `test_pole_contact_detection` |
| 2D inverse dynamics with measured GRF | Tested | static hand calculation; analytic pendulum to 0.05 N·m |
| Quasi-static scenario knee model, quadriceps force, power, work, impulse | Tested | hand calculations; eccentric sign check |
| Elbow and shoulder moments from pole force | Tested | hand calculation |
| Sensitivity analysis (support model × COP × moment arm) | Tested | 18 combinations per trial |
| Within-participant comparisons, descriptive group summary | Tested | `test_save_load_and_project_export` |
| CSV, Excel, PNG/SVG/PDF and Markdown summary export | Tested | the files are checked after export |
| Two-camera per-view analysis and frontal-plane knee angle | Tested with injected landmarks | `test_two_camera_run_with_injected_pose` |
| DLT 3D reconstruction | Tested mathematically; output labelled **calibrated, unvalidated** | exact on synthetic cameras |
| macOS launcher app with icon and Desktop alias | Tested on the developer Mac | `scripts/install_mac.command` |
| Standalone macOS build (PyInstaller) | Built and smoke-tested on macOS (arm64) | `--selftest`, `--check-pose` |
| Windows install script and standalone build | **Windows is tested only in CI** (GitHub Actions `windows-latest`) | see the Actions tab |

## Added in v1.1 (second design pass)

| Feature | Status |
|---|---|
| Step-by-step setup panel with a live status for each step | Tested (GUI tests) |
| Clickable knee timeline under the video (jumps the video) | Tested |
| Trial report: metric cards with evidence labels and published reference bands | Tested |
| Movement timeline figure (angles, contacts, knee moment, cumulative demand) and leg stick-figure strip | Tested |
| New metrics: knee angle at landing, peak loaded knee flexion velocity, hip and ankle peaks, step-time CV, knee impulse per step, peak knee power absorption | Tested on synthetic data |
| All-metric overview with a per-person noise check; pole-length response; repetition trends | Tested |
| Export: change table, reference ranges, per-trial timeline and leg figures, raw-data folder | Tested |

## Not implemented / not estimated

* **Tibiofemoral and patellofemoral compression.** These need a musculoskeletal model with co-contraction and
  measured GRF (e.g. OpenSim). The app reports them as *Unavailable*.
* **Pole force from video.** It is physically impossible to see. Use a load cell or a scenario.
* **Automatic pole detection without markers.** The `PoleDetector` interface is ready for a detector trained on our
  own recordings later.
* **Muscle fatigue scores.** Deliberately not implemented, because no published model is defensible for 2D video
  without strength testing or EMG (methods §12). The app reports mechanical-demand metrics and repetition trends
  instead.
* **OpenCap / OpenSim integration.** Evaluated, not integrated in v1 (see `docs/research/open-source-tools.md`).
* **Signed and notarised macOS app / Windows installer.** The builds are unsigned (see troubleshooting).

## Independent review

A separate reviewer re-derived every equation and sign in the analysis code (angles, Newton–Euler, quasi-static
model, quadriceps force, power/work/impulse, arm moments, Winter parameters, sync convention), and all were confirmed.
It found nine robustness bugs, all now fixed with regression tests (`tests/test_review_regressions.py`):

* hidden far-side landmarks no longer turn knee loads into zeros
* an undetectable double support is flagged as an upper bound
* force-plate COP height and stance attribution are corrected
* force channels are filtered before resampling
* camera-B gaps are not bridged
* edge-truncated contacts are excluded from step time
* the pole lever uses the grip point
* peak calculations are safe when values are missing
* the ambiguous `fy` column is rejected

Still open: phone audio and video stream start-time differences in automatic sync (check sync visually), and
horizontal GRF in the video-only model (documented assumption).

## Scientific limitations

* n = 3 team members. Results describe us under our test conditions only. No significance testing.
* 2D video: out-of-plane motion and camera angle bias the angles, and loose clothing can shift landmarks.
* Without force plates, knee moments come from an assumed foot force acting at an assumed COP. They are comparisons, not absolute loads.
* Lab stairs are not a trail, and we test without a backpack.
* Lower estimated loading does not demonstrate less pain, less fatigue or lower injury risk.
