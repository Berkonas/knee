# Open-source tools evaluated (2026-11-17)

We checked each tool's licence and last activity from GitHub's API on 2026-11-17. The question for each was whether it improves our smartphone stair-descent analysis enough to justify a dependency in a PySide6 desktop app that must work offline.

| Project | Licence | Use for us | Decision |
|---|---|---|---|
| [RTMLib](https://github.com/Tau-J/rtmlib) | Apache-2.0 | Lightweight ONNX runner for RTMPose and YOLOX, no PyTorch | **Kept.** We now call its pose model directly on a crop that follows the previous skeleton, the same idea as its `PoseTracker`. We also switched to the RTMPose-x 384×288 model. Side-view jitter fell 53–70% and tracking ran faster. |
| [MMPose](https://github.com/open-mmlab/mmpose) | Apache-2.0 | Training framework and model zoo (RTMPose comes from here) | **Not integrated.** It needs PyTorch and MMCV (gigabytes), and inference would add nothing over RTMLib. We use its published RTMPose-x and YOLOX ONNX weights. |
| [Sports2D](https://github.com/davidpagnon/Sports2D) | BSD-3-Clause | 2D angles from RTMPose, with filtering options | **Not integrated; methods compared.** It applies the same Butterworth filtering and 2D angle conventions we already use. Its CLI-oriented pipeline would duplicate ours. |
| [One Euro Filter](https://github.com/casiez/OneEuroFilter) | none detected | Speed-adaptive smoothing for live input | **Re-implemented from the paper (Casiez et al. 2012), no code copied, and evaluated.** For offline display, a zero-lag 8 Hz Butterworth filter tracked test movements with less error (1.0 vs 1.5–3.1 px), so it became the display filter. One Euro remains in `core/filters.py` for live previews. |
| [myogait](https://github.com/IDMDataHub/myogait) | MIT | Gait-event detection from markerless pose | **Not integrated.** It is young (13 stars) and targets level walking. Our heel/toe-velocity contact detector is tested on synthetic gait. Neither detector has been checked against a force plate on stairs, so swapping one for the other would gain nothing provable. |
| [OpenSim](https://github.com/opensim-org/opensim-core) | Apache-2.0 | Musculoskeletal modelling, joint reaction analysis | **Not integrated now.** Credible joint-contact or muscle forces need measured GRF and a scaled model with marker data or 3D kinematics. We have neither (2D video, no force plate). Mode C exports GRF, COP and kinematics in SI units, ready for an OpenSim workflow when force data exist. |
| [Pose2Sim](https://github.com/perfanalytics/pose2sim) | BSD-3-Clause | Multi-camera calibration, triangulation, OpenSim scaling | **Not integrated.** It needs ≥2 calibrated, synchronised cameras with overlapping views of the same body side. Our front and side phones are uncalibrated and view different planes. |
| [OpenCap Core](https://github.com/opencap-org/opencap-core) | Apache-2.0 | Smartphone 3D kinematics and kinetics via cloud processing | **Not integrated.** It uses its own capture protocol (calibration board, 2+ iOS devices) and cloud servers, so it does not fit our recorded data or the offline requirement. It is a good option for a future protocol. |
| [pyomeca](https://github.com/pyomeca/pyomeca) | Apache-2.0 | Biomechanical signal processing on xarray | **Not integrated.** Our filters (Butterworth, despiking, gap filling) are already implemented and tested. Adding xarray would mean a dependency without a measurable gain. |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | MIT | Design-guidance skill for AI coding tools | **Not available as a skill here; principles applied by hand:** <br>• one primary action per panel <br>• progressive disclosure (advanced assumptions on the Biomechanics page, Methods as one screen plus a searchable list) <br>• colour never the only signal (evidence labels are text) <br>• consistent tokens in light and dark themes <br>• reduced motion respected |

| [vision-demos](https://github.com/jeremyipark/vision-demos) | Apache-2.0 | Sports CV demos (running gait, reps, form) built on cloud ViTPose | **Ideas adopted, no code or model:**<br>• leg length = median thigh + median shank<br>• foot-strike flash and fading trails on the video<br>• checking left/right leg swaps (1 frame in our 21 recordings, so no correction is needed)<br>Its cloud ViTPose gateway was rejected: participant videos would leave the machine. |

## What changed in the code as a result

- `core/pose_rtm.py`: tracked crops plus RTMPose-x ("accurate" mode, the default), re-detection on low confidence.
- `core/filters.py`: display filter (zero-lag 8 Hz), plausibility masking, One Euro (live use only).
- `core/pole_auto.py`: dark-tip extension calibrated on hand labels.

The exact jitter and tip-error numbers are in `RESEARCH_PIPELINE.md` and `docs/VALIDATION_REPORT.md`.
