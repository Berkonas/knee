# Open-source tools survey

Scope: tools that could support our pipeline. The pipeline analyzes 2D sagittal video of stair descent with and without trekking poles. It uses MediaPipe pose, a quasi-static knee extensor moment, quadriceps force from the patellar tendon moment arm, elbow and shoulder moments from pole force, clap-based audio sync of two cameras, and colored-marker pole tracking.

Verification date: 2026-11-11. Repository metadata (license SPDX id, last push, latest release) came from the GitHub REST API. Package versions and licenses came from the PyPI JSON API. Platform and dependency claims come from each project's README unless marked otherwise. Anything we did not check directly is marked **not verified**.

Decision key: **Used**: in our app. **Evaluated, not used**: considered and rejected for this project. **Future**: worth trying in a later version.

---

## 1. brunobedo/mediapipe2dangle

- **What it does:** Computes 2D hip and knee joint angles from a video using MediaPipe. Writes CSV, images and an annotated video, for the left or right side.
- **Maintenance:** Last push 2026-04-14 (a README citation edit). No GitHub releases. 4 stars.
- **License:** GPL-3.0.
- **Dependencies:** `opencv-python`, `mediapipe`, `matplotlib`. The README suggests Python 3.9.
- **OS:** The README gives activation steps for Windows and macOS/Linux.
- **Video:** Reads video files through OpenCV.
- **Fit:** A small reference script for computing sagittal angles from MediaPipe landmarks. It is close to what our angle step does.
- **Limitations:**
  - Its code uses the legacy `mp.solutions.pose` API (`maintools.py`, line 9). GitHub issue google-ai-edge/mediapipe#6192 reports that mediapipe 0.10.31 for Python no longer ships `mediapipe.solutions`, so the script likely needs an older mediapipe pin.
  - Hip and knee only. No kinetics, no ankle, no filtering options found.
  - GPL-3.0 means copying its code would put our code under the same license.
- **Decision:** Evaluated, not used. We read it for reference only and copied no code.

## 2. AnyBody/ammr (AnyBody Managed Model Repository)

- **What it does:** A library of musculoskeletal models and examples for the AnyBody Modeling System (AMS).
- **Maintenance:** Last push 2026-08-10. Latest release `ammr-3.2.1` (2026-06-19).
- **License:** Proprietary. GitHub reports `NOASSERTION`. The LICENSE file says use is covered by the AnyBody Technology A/S Software License Agreement. Forks are allowed only through GitHub's fork system and must keep the license certificate.
- **Requires commercial software:** **AMMR needs the commercial AnyBody Modeling System.** The README says "An AnyBody license with active maintenance is required to use the models from GitHub."
- **Dependencies:** AnyBody Modeling System (commercial).
- **OS:** Not verified. We believe AMS runs on Windows only, but did not confirm this.
- **Video:** None. AMMR takes marker or kinematic input files, not video.
- **Fit:** Could serve as a gold-standard muscle-force model to compare with our single-moment-arm quadriceps estimate.
- **Limitations:** Needs a paid license. Needs 3D input. Far more complex than a class project needs.
- **Decision:** Evaluated, not used.

## 3. OpenCap (stanfordnmbl/opencap-core, stanfordnmbl/opencap-processing)

- **What it does:**
  - `opencap-core` turns two or more videos into 3D marker positions and OpenSim joint angles.
  - `opencap-processing` adds dynamic simulation (kinetics) and other utilities.
  - The hosted web app (app.opencap.ai) records with iOS devices and processes the videos in the cloud.
- **Maintenance:**
  - opencap-core: last push 2026-11-11.
  - opencap-processing: last push 2026-09-10.
  - Both have only a `v1.0.0` GitHub release, from 2022-12-09.
- **License:** Apache-2.0 (both repositories).
- **Dependencies:** OpenSim (conda package), ffmpeg, a pose estimator (the README names OpenPose settings), and a CUDA GPU with at least 4 GB to run the pipeline locally.
- **OS:**
  - Local opencap-core: the README gives instructions for Windows 10 and says it also runs on Ubuntu.
  - opencap-processing on macOS: the README says only x86_64 is supported. Apple-silicon users must use an x86_64 conda environment.
- **Video:** The hosted service needs iOS devices recording through its app. Local processing needs synchronized multi-view video plus calibration.
- **Fit:** Validated against lab data in Uhlrich et al. (2023). A future 3D, OpenSim-based way to cross-check our knee moments.
- **Limitations:**
  - Needs at least two calibrated cameras, iPhones for the hosted workflow, and cloud upload of participant videos (a privacy question).
  - Does not model poles or upper-limb loading from external poles.
- **Decision:** Future, as a validation reference.

## 4. OpenSim (opensim-org/opensim-core)

- **What it does:** C++ musculoskeletal modeling and simulation libraries, with Java and Python bindings: inverse kinematics, inverse dynamics, static optimization and more.
- **Maintenance:** Last push 2026-11-12 (UTC). Latest release `4.6` (2026-07-09).
- **License:** Apache-2.0.
- **OS:** The 4.6 release assets include Windows, macOS arm64, a macOS universal2 Python wheel (cp311), and Ubuntu 22 and 24 builds.
- **Video:** None. It takes marker (.trc) and force data.
- **Fit:** A gold-standard musculoskeletal pipeline. Our 2D quasi-static model is a deliberate simplification of what OpenSim does.
- **Limitations:**
  - Needs 3D kinematics and ground reaction forces for full inverse dynamics. We have neither.
  - Steep learning curve. The Python API is easiest to install through conda.
- **Decision:** Future.

## 5. Sports2D (davidpagnon/Sports2D)

- **What it does:** Computes 2D pose and joint and segment angles from a video or webcam. Optional OpenSim kinematics and scaling. Outputs angles (.mot), a scaled OpenSim model and a calibration file (.toml).
- **Maintenance:** Last push 2026-11-10. Latest release `v0.8.34` (2026-07-10).
- **License:** BSD-3-Clause. Paper: Pagnon & Kim (2024), JOSS, doi:10.21105/joss.06849.
- **Dependencies:** Its `pyproject.toml` depends on Pose2Sim, pinned to a git commit. That brings in rtmlib (RTMPose), onnxruntime, OpenCV, OpenSim and others. Optional `PySide6` for a GUI.
- **OS:** The README gives install instructions for Windows and for Linux/macOS.
- **Video:**
  - Reads video files and webcams.
  - The README notes a known issue with some iPhone portrait-mode videos and suggests converting them first with ffmpeg.
- **Fit:** The closest open-source equivalent to our angle step. Useful for cross-checking our MediaPipe sagittal angles on the same clips.
- **Limitations:**
  - Kinematics only. No quasi-static kinetics, pole force or audio sync.
  - The README itself warns that angle estimation is only as good as the pose estimator.
  - Its scaling step skips frames where knee or hip flexion exceeds 90°, which is relevant for deep stair-descent flexion.
- **Decision:** Future, for cross-validating angles.

## 6. Pose2Sim (perfanalytics/pose2sim)

- **What it does:** Multi-camera markerless kinematics, from 2D pose through calibration, triangulation and filtering to OpenSim inverse kinematics.
- **Maintenance:** Last push 2026-11-10. Latest release `v0.10.49` (2026-07-10).
- **License:** BSD-3-Clause. Paper: Pagnon et al. (2022), JOSS, doi:10.21105/joss.04362.
- **Dependencies (from pyproject):** `opensim`, `rtmlib` (which pulls in onnxruntime and opencv-python), `openvino`, `av`, `caliscope`, `pandas`, `scipy`, `statsmodels`, `filterpy`, `PySide6-essentials`, among others.
- **Pose backends:** RTMPose is the default. The README also documents MediaPipe BlazePose input.
- **OS:** Cross-platform Python. Per-OS testing was not verified.
- **Video:** Multi-view video files, with calibration of intrinsics and extrinsics.
- **Fit:** Our two-camera setup could feed Pose2Sim for 3D reconstruction if both cameras were calibrated.
- **Limitations:** Needs calibrated, synchronized, overlapping views. Our cameras are set up for separate 2D sagittal views. Heavy dependency stack.
- **Decision:** Future.

## 7. MediaPipe (google-ai-edge/mediapipe), Pose Landmarker

- **What it does:** Cross-platform ML solutions. The Pose Landmarker task (BlazePose) outputs 33 body landmarks per frame. The current Python interface is the Tasks API (`mediapipe.tasks.python.vision.PoseLandmarker`).
- **Maintenance:** Last push 2026-11-11. Latest release `v1.2.3` (2026-11-11). PyPI `mediapipe` 1.2.3.
- **License:** Apache-2.0.
- **Wheels for 1.2.3 (PyPI):**
  - macOS 11+ arm64
  - Windows amd64 and arm64
  - Linux x86_64 and aarch64 (manylinux_2_28)
  - **No macOS x86_64 wheel**, so Intel Macs would need an older version (not tested by us).
- **Legacy API:** Google's legacy Solutions (`mp.solutions`) ended support in March 2023. Issue #6192 reports that `mediapipe.solutions` is missing from 0.10.31.
- **Video:** The Tasks API has a VIDEO running mode that takes frames with timestamps. Frames are decoded by OpenCV in our app.
- **Fit:** Our pose estimator. Light, CPU-only, and installs with pip on macOS arm64 and Windows.
- **Limitations:**
  - Single person per detector instance by default.
  - Joint centers are image landmarks, not anatomical joint centers.
  - Depth (z) is unreliable in monocular video, which is why we stay 2D sagittal.
  - Foot landmarks can jitter on stair edges.
- **Decision:** Used.

## 8. pyomeca (pyomeca/pyomeca)

- **What it does:** A Python toolbox for biomechanics data built on xarray: reading C3D and other formats, filtering (Butterworth and others), EMG processing and rotations.
- **Maintenance:** Last push 2026-08-11. Latest release `v2026.0.2` (2026-08-11).
- **License:** Apache-2.0. Paper: Martinez et al. (2020), JOSS, doi:10.21105/joss.02431.
- **OS:** Pure Python, so expected to be cross-platform. Not verified on our machines.
- **Video:** None. It processes time-series data.
- **Fit:** Could replace our own SciPy Butterworth filter and data containers.
- **Limitations:** Adds an xarray dependency for functions that a few SciPy calls already cover.
- **Decision:** Evaluated, not used. We call `scipy.signal.butter` and `filtfilt` directly.

## 9. FreeMoCap (freemocap/freemocap)

- **What it does:** A GUI system for free multi-camera markerless motion capture: calibration, tracking (via skellytracker), 3D reconstruction and export.
- **Maintenance:**
  - Last push 2026-11-11.
  - Latest GitHub release `v2.0.0-alpha.26` (2026-11-11, alpha).
  - Latest stable on PyPI is 1.8.2, which requires Python >=3.10 and <3.13.
- **License:** AGPL-3.0.
- **OS:** The README gives commands for Windows, macOS and Linux. NVIDIA GPU acceleration works on Windows and Linux. macOS is CPU-only (`pip install freemocap[cpu]`).
- **Video:** Webcams and recorded multi-camera video.
- **Fit:** An alternative full capture system, mainly for 3D work.
- **Limitations:**
  - AGPL-3.0 is incompatible with embedding its code in our app unless we also release under AGPL.
  - Needs calibrated multi-camera capture.
  - The v2 line is alpha.
- **Decision:** Evaluated, not used.

## 10. Kinovea

- **What it does:** A desktop video annotation and measurement tool for sport and motion analysis: slow motion, side-by-side comparison, angle and distance tools, and tracking.
- **Maintenance:**
  - Latest version 2025.2.0, per kinovea.org/download.html (page updated 2026-03-21).
  - GitHub (Kinovea/Kinovea) last push 2026-10-29. No GitHub releases.
- **License:** GPL-2.0.
- **OS:** Windows 7–11 only, 64-bit Intel/AMD, with .NET Framework 4.8. The download page says Apple-silicon Macs are not supported, even through Parallels or other virtualization.
- **Video:** Wide format support and capture from cameras.
- **Fit:** A manual ground-truth check. Digitize knee angles by hand on a few frames and compare them with MediaPipe.
- **Limitations:** Does not run on our macOS arm64 machines. Manual work. No kinetics.
- **Decision:** Evaluated, not used. It is an option for a teammate on Windows doing manual spot checks.

## 11. RTMPose / rtmlib (Tau-J/rtmlib; model from open-mmlab/mmpose)

- **What it does:**
  - rtmlib is a lightweight wrapper that runs RTMPose, DWPose, RTMO, RTMW and ViTPose ONNX models without mmcv, mmpose or mmdet.
  - RTMPose itself comes from Jiang et al. (2023), arXiv:2303.07399.
- **Maintenance:**
  - rtmlib: last push 2026-11-07, latest release `0.0.16` (2026-08-03).
  - mmpose: last push 2025-08-04, latest release `v1.3.2` (2024-07-12), so it is less active.
- **License:** Apache-2.0 (both rtmlib and mmpose). Model weight licenses not verified.
- **Dependencies:** `numpy`, `opencv-python`, `opencv-contrib-python` and `onnxruntime`. Optional OpenVINO and TensorRT backends.
- **OS:** Cross-platform through onnxruntime. Not tested by us.
- **Video:** Frame-based. The caller decodes the video.
- **Fit:** A drop-in alternative 2D pose backend. It is the default in Sports2D and Pose2Sim. Its Halpe-26 model includes heel and toe keypoints, useful for stair foot contact.
- **Limitations:**
  - Models download from external servers on first use.
  - A heavier runtime than MediaPipe.
  - We would have to remap keypoints to our angle definitions.
- **Decision:** Future, as a second pose backend for robustness checks.

## 12. aniposelib (lambdaloop/aniposelib), extra tool

- **What it does:** Multi-camera calibration (ChArUco or checkerboard boards, or from tracked points) and triangulation of 2D points into 3D. It is the library behind Anipose (Karashchuk et al., 2021, *Cell Reports*).
- **Maintenance:** Last push 2026-11-05. No GitHub releases. PyPI 0.8.0.
- **License:** BSD-2-Clause.
- **Fit:** Would replace a hand-written DLT if we move to two-camera 3D. Its `estimate_scale` function sets metric units.
- **Limitations:** Needs a calibration board and overlapping camera views.
- **Decision:** Future.

## 13. bbc/audio-offset-finder, extra tool

- **What it does:** Finds the time offset of one audio file inside another. It cross-correlates standardized MFCC features, and the README states typical accuracy "within about 0.01s".
- **Maintenance:** Last push 2026-10-02. Latest release `v0.5.5` (2024-06-25).
- **License:** Apache-2.0.
- **Dependencies and OS:** Uses FFmpeg for decoding. The README says it is tested with Python 3.9–3.14 on Linux, Windows and macOS.
- **Fit:** An independent check on our clap-based sync. Run it on the two cameras' audio tracks and compare its offset with our clap-peak offset.
- **Limitations:** A 10 ms resolution is coarser than one frame at 120 fps (8.3 ms). It works on the whole audio track, not a single clap transient.
- **Decision:** Future, as a validation tool.

## 14. AudioAlign (protyposis/AudioAlign), extra tool

- **What it does:** A GUI tool that synchronizes and analyzes multiple audio and video recordings through audio fingerprinting and cross-correlation.
- **Maintenance:** Last push and latest release `v1.7.0`, both 2024-01-30.
- **License:** AGPL-3.0.
- **OS:** Not verified. We believe it is a Windows (.NET) application.
- **Decision:** Evaluated, not used. It is a GUI tool, has an AGPL license and is not scriptable from our app.

## 15. gaitmap (mad-lab-fau/gaitmap), extra tool

- **What it does:** A gait and movement analysis package, mainly for IMU (foot-worn sensor) data, with event detection and stride segmentation.
- **Maintenance:** Last push 2026-10-23. Latest release `v2.6.0` (2026-03-05).
- **License:** GitHub reports `NOASSERTION`. The exact license terms were not verified.
- **Fit:** Weak. It targets IMU data, not video kinematics. For video we follow the Zeni et al. (2008) kinematic method instead (see literature.md).
- **Decision:** Evaluated, not used.

---

## Selected stack and why

| Component | Role in our app | Version checked (PyPI) | License (verified) |
|---|---|---|---|
| MediaPipe (Tasks API `PoseLandmarker`) | 2D pose landmarks | 1.2.3 | Apache-2.0 |
| OpenCV (`opencv-python`) | Video decode, color-marker pole tracking, drawing | 5.0.0.93 | Apache-2.0 |
| NumPy | Arrays and vector math | 2.5.4 | BSD-3-Clause (wheels also bundle 0BSD, MIT, Zlib and CC0-1.0 components, per PyPI) |
| SciPy | Butterworth filter, `filtfilt`, signal cross-correlation | 1.18.1 | BSD-3-Clause ("BSD License" classifier) |
| pandas | Tabular per-frame data and exports | 3.1.1 | BSD-3-Clause |
| matplotlib | Plots | 3.11.2 | Matplotlib License (PSF-based, BSD-compatible) |
| PySide6 | Desktop GUI (Qt for Python) | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| imageio-ffmpeg | Bundled ffmpeg binary for extracting audio and re-encoding | 0.8.1 | BSD-2-Clause for the wrapper. The bundled ffmpeg executable has its own license, which we did not verify. |
| openpyxl | Excel (.xlsx) export | 3.1.5 | MIT |

Why this stack:

1. **Installs with pip on our machines.** Every package above has wheels for macOS arm64 and Windows. MediaPipe has no macOS x86_64 wheel in 1.2.3, so Intel Macs are out of scope.
2. **Light and CPU-only.** No CUDA, no cloud upload of participant video (unlike OpenCap's hosted workflow) and no commercial license (unlike AnyBody).
3. **Fits a 2D sagittal quasi-static model.** Our research question compares knee extensor moment with and without poles. That needs reliable sagittal angles plus segment geometry, not full 3D musculoskeletal simulation. OpenSim, OpenCap and Pose2Sim stay as Future validation paths.
4. **Licenses allow a class-project release.** All are permissive except PySide6. Using PySide6 under LGPL-3.0 means users must be able to swap the Qt and PySide6 libraries, which a normal pip-installed environment allows. GPL and AGPL tools (mediapipe2dangle, Kinovea, FreeMoCap, AudioAlign) were deliberately not embedded.
5. **Tasks API rather than legacy `mp.solutions`.** The legacy API is out of support and is reported missing from recent mediapipe builds.

Sources: GitHub REST API (`/repos/{owner}/{repo}` and `/releases/latest`), PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`), each project's README and LICENSE file, https://www.kinovea.org/download.html, and https://github.com/google-ai-edge/mediapipe/issues/6192.
