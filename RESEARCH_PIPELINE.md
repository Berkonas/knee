# Research pipeline: video-based analysis of stair descent with trekking poles

## Overview

**TrailBuddy Analyzer** is a desktop application written for this project. It turns two ordinary smartphone
videos of each stair-descent trial into time-resolved, view-labelled kinematic measures for the body and the trekking
poles. It also gives clearly labelled, assumption-based estimates of knee extensor demand. We use video because it is
non-invasive, portable and available in the CREATE Lab, and because it lets us compare conditions within each
participant (no poles, standard poles, shorter and longer poles). Video cannot measure force. Every output is
therefore tagged as a *video estimate*, a *model estimate* (when measured forces are supplied) or a *scenario*
(when a force is assumed).

## Experimental dataset

* Three participants (P01–P03), each descending the CREATE Lab stairs several times.
* Two phones on tripods recorded each trial:
  * **Front view:** iPhone 11 Pro, 1920×1080, 59.94 fps, H.264
  * **Side view:** iPhone 15 Pro Max, 1920×1080, 59.94 fps, 10-bit HEVC HLG
* An operator clapped once at the start of each recording to synchronise the two views.
* The session folder holds 23 files. Two side files are aborted recordings (under 0.2 s). The app pairs 8 trials
  front + side, 7 of them with high confidence. Three front-only and two side-only recordings of P03 have no
  partner with matching audio, and they are analysed as single-view trials.

## Software

| Purpose | Tool (version) | Licence |
|---|---|---|
| Application and interface | Python 3.12, PySide6 / Qt (6.12), pyqtgraph (0.14) | LGPL-3.0 / MIT |
| Person detection + 2D whole-body keypoints | YOLOX-m and RTMPose-m (Halpe-26 keypoints incl. heels and toes) via rtmlib 0.0.16 on ONNX Runtime 1.32 [1, 2] | Apache-2.0 / MIT |
| Alternative pose backend | MediaPipe Pose Landmarker 1.2 [3] | Apache-2.0 |
| Video and audio decoding | OpenCV 5.0, FFmpeg (bundled by imageio-ffmpeg 0.8) | Apache-2.0 / LGPL |
| Signal processing and statistics | NumPy 2.5, SciPy 1.18, pandas 3.1 | BSD |
| Figures and tables | matplotlib 3.11, openpyxl 3.1 | PSF-based / MIT |

We evaluated OpenCap, OpenSim, Sports2D, Pose2Sim and AnyBody (see `docs/research/open-source-tools.md`). They were not
used, either because they need calibrated multi-camera 3D capture or because they require a commercial licence.
We chose RTMPose over MediaPipe after a side-by-side check on our side-view frames: MediaPipe misplaced the hips and
knees on loose, light-coloured trousers, while RTMPose found the knees, heels and toes.

## Processing pipeline

1. **Import and organisation.**
   * Container metadata is read with FFmpeg: resolution, frame rate, duration, codec, HDR, device and creation time.
     GPS metadata is never read.
   * Recordings under 1 s are excluded.
   * The camera view is classified from the person's posture: front if shoulder width divided by torso height is
     above 0.4, side if it is below 0.3. The result is checked by a majority vote per device.
   * Participants are grouped by k-means clustering of the median clothing colour (CIELAB) of the torso and thighs.
2. **Pairing.**
   * Recording time stamps contradicted the true order, so front and side recordings are paired by their sound.
   * For every front–side candidate, the app computes the normalised cross-correlation of 10 ms log-energy
     envelopes (high-pass above 300 Hz) over lags of ±20 s.
   * A one-to-one assignment then maximises the total correlation (Hungarian algorithm), never pairing different
     participants. Pairs with r ≥ 0.7 and a clear margin over the alternatives are *confident*. Pairs with r < 0.6
     are rejected.
   * Users can correct any pairing.
3. **Synchronisation.**
   * The clap is the strongest broadband onset (above 1 kHz) in the first 5 s of each track. It is accepted when it
     agrees within 50 ms with the whole-recording envelope correlation.
   * Visual alternative: the frame where the two wrists are closest after closing quickly.
   * Manual adjustment works in steps of one frame.
   * Clock drift is checked by comparing local offsets at the start and end of each recording, and was below one
     frame in our trials.
   * Different frame rates are handled by mapping both cameras to one clock in seconds.
4. **Person and pose tracking.**
   * YOLOX-m finds the participant: the largest, most confident person in the first frames.
   * From then on each frame is cropped around the previous frame's skeleton (enlarged 25%) and RTMPose-x
     (384×288 input, Halpe-26 keypoints) runs on that crop. The detector runs again when the tracked skeleton's mean
     confidence falls below 0.45 or its height changes by more than 35%. In that case the app picks the detection
     whose hip centre and size are closest to the previous frame, which rejects people walking behind the stairs.
   * Why: re-detecting every frame made the crop box wobble, and that wobble showed up as keypoint jitter. On four
     real recordings, 3 s of descent each, high-frequency leg-keypoint noise (residual above a 6 Hz low-pass) was:

     | Recording | Old (RTMPose-m, detector every frame) | New (RTMPose-x, tracked crop) |
     |---|---|---|
     | P01 side | 2.36 px | 1.11 px (−53%) |
     | P02 side | 2.13 px | 0.65 px (−70%) |
     | P03 side | 3.61 px | 1.24 px (−66%) |
     | P02 front | 1.83 px | 1.42 px (−22%) |

     The new tracker also ran faster: 16–19 vs 8–11 frames/s on an Apple-silicon CPU.
   * If the target is lost, the frame is left empty. Nothing is invented.
   * **Display only:** the skeleton drawn on the video can be smoothed. The app applies a zero-lag 8 Hz filter and
     hides points that make a segment implausibly long or short. A One Euro filter (Casiez et al. 2012) was
     evaluated for this and rejected: it is designed for live input, and offline it left 1.5–3 px error on test
     movements versus 1 px for the zero-lag filter. Measurements never use the display filter.
5. **Pole tracking.**
   * For each hand, pole-coloured pixels (HSV) outside the torso are searched below the wrist.
   * Straight segments are found with the probabilistic Hough transform.
   * A segment is kept only if:
     * it lies on a line passing within 0.07 body heights of the wrist
     * it starts at the hand and does not continue above it, which rejects handrails and curtain folds
     * it points within 40° of vertical
   * The coloured shaft ends above a short dark rubber tip and ferrule, which is hard to see against the black
     stairs. The reported tip therefore extends the hand-to-shaft-end line by 7.1%. That fraction is the median from
     12 hand-labelled tips (IQR 6.6–7.6%).
   * Tip error against the 16 hand labels through the full pipeline: median 14 px, 90th percentile 26 px. With
     each frame left out of the calibration in turn the median is 12 px. Before this change it was median 30 px.
     13 of 16 tips were found and none were on the wrong object. The labels are in
     `docs/validation/manual_pole_tips.json`.
   * Detections are removed if they jump in angle or position between frames, or last fewer than five frames.
   * Users can override any frame with a manual click.
6. **Signal conditioning.**
   * Keypoints below 0.5 confidence are removed.
   * Isolated spikes are removed: a deviation from the 7-frame running median larger than 6 robust SD and larger
     than 8% of leg length.
   * Gaps of 0.1 s or less are filled linearly and flagged. Longer gaps stay missing.
   * Trajectories are low-pass filtered with a zero-lag 2nd-order Butterworth filter at 6 Hz [4].
7. **Events, technique and segments.**
   * Foot strike and toe-off are the start and end of each foot contact. Contacts already under way at the clip
     edges give no event.
   * Single- and double-support time come from the two feet's contacts.
   * Pole technique is classified from the pole-tip contacts: *alternating*, *simultaneous* (plants within 0.15 s of
     each other in at least 70% of cases), *single pole* or *mixed*. Each plant is timed against the nearest foot
     strike: early, within ±0.1 s, or late. Steps without a pole plant within 0.35 s are counted.
   * Every classification carries a confidence (number of plants × pole tracking coverage). Pole dragging is not
     assessed.
   * Candidate movement segments are periods of whole-body movement (mid-hip speed above 0.25 leg lengths/s, pauses
     under 0.6 s bridged), labelled descent, ascent or level by the change in hip height. They are stored as
     timestamps and the videos are never cut.
8. **Biomechanical calculations.** Details are in the table below and in `docs/calculation-audit.md`.
9. **Export.** For each trial the app writes the time-series CSV, a summary table with evidence label and camera
   view, events, figures, an annotated video and a JSON file of all processing settings. For the study it writes
   within-participant comparison tables, an Excel workbook and figures.

## Measurements

| Measure | Definition | Unit | View |
|---|---|---|---|
| Knee / hip flexion, ankle dorsiflexion | θ_thigh − θ_shank; θ_thigh − θ_trunk; 90° − (θ_shank − θ_foot), segment angles from image coordinates | deg | side |
| Trunk lean; shoulder flexion; elbow flexion | trunk from vertical; upper arm vs trunk; 180° − ∠(shoulder, elbow, wrist) | deg | side |
| Angular velocity | central difference of filtered joint angles | deg/s | side |
| Segment orientation | thigh, shank, upper arm, forearm from vertical | deg | side |
| Peak knee flexion, flexion at foot contact, range of motion | from the knee angle time series during stance | deg | side |
| Foot contacts, stance and step time, cadence | foot midpoint speed < 15% of its 95th percentile for ≥ 0.08 s [5] | s, steps/min | side |
| Pole angle; pole contact time; plant timing | wrist→tip axis from vertical; stationary tip; plant time minus nearest foot strike | deg, s | side / front |
| Knee frontal-plane projection angle | 180° − ∠(hip, knee, ankle) | deg | front |
| Trunk sway, pelvic tilt range | mid-hip→mid-shoulder from vertical; hip line from horizontal | deg | front |
| Step width, pole tip spread | ankle separation / hip width; tip separation / shoulder width | ratio | front |
| Knee extensor moment (scenario) | quasi-static foot force at an assumed COP, directed toward the body COM (equations below) | N·m/kg | side + model |
| Quadriceps force (scenario) | knee moment / patellar-tendon moment arm (5 cm, sensitivity range 4–6 cm) [6] | N, ×BW | side + model |
| Mechanical demand | cumulative knee extensor angular impulse; negative knee work; peak power absorption | N·m·s/kg, J/kg, W/kg | side + model |

## Estimated loading: exact equations

**Analysis modes.**
* **A, video only** (default): angles, timing and pole geometry. No force or moment is estimated.
* **B, scenario:** loads from the stated assumptions below, labelled *scenario*.
* **C, measured:** loads from imported force-plate, insole or pole load-cell data. A quasi-static calculation is
  never shown as inverse dynamics, and mode C never falls back to scenario values.

Estimated loads are calculated only after a participant's **measured** body mass *m* (kg) is entered in
*Participant information…*. Height, measured segment lengths or a calibrated scene distance give the scale. Until then every force, moment, power, impulse and work value is shown as
*unavailable*, and the matching columns are left out of the time series and exports. No default mass or height is
ever used. All quantities are SI: N, N·m, W, J and s; normalised values are per kg of body mass.

**Scale.** Pixel coordinates are converted to metres with *s* = (participant's leg length from *h* and
Winter's segment proportions [4], or the entered thigh and shank lengths) / (median leg length in pixels). A
calibrated scene distance can be used instead. Without a scale, all kinetics are unavailable.

**Support force (video-only trials).** Total vertical support F_s = m·g (quasi-static, default) or
m·(g + a_COM,y), with a_COM from the filtered whole-body COM (Winter segment parameters [4]; foot COM
from de Leva [8]). The stance leg carries

  F_foot = share · max(F_s − F_pole,y, 0)

where share = 1 in single support and ramps linearly from the trailing to the leading leg in double support, and
F_pole,y = Σ (axial pole force · vertical component of the tip→hand direction). Pole force is 0 unless a measured
pole force is loaded or the *scenario* option is chosen (default 10 % of body weight per planted pole).

**Foot force direction.** The force acts at an assumed centre of pressure COP = heel + c·(toe − heel), with
c = 0.5 by default. By default its line of action runs from the COP toward the whole-body COM, because with small
angular momentum about the COM the ground reaction force points close to the COM [9]:

  F = (F_x, F_y) = F_foot · ((x_COM − x_COP)/(y_COM − y_COP), 1)

A purely vertical force (F_x = 0) can be selected instead. This is an alternative assumption, not a bound: when the COM is behind the COP (early stance) the vertical force gives a *smaller* moment. The sensitivity range includes both directions.

**Knee extensor moment** (internal, + = extensor; minus the external moment of F about the knee, with segment
weight and inertia below the knee neglected):

  M_knee = (x_knee − x_COP)·F_y + (y_COP − y_knee)·F_x

With a measured ground reaction force, the app instead uses full 2D Newton–Euler inverse dynamics through the
foot, shank and thigh [4]. Each segment satisfies F_p = m_s·a − m_s·g − F_d and
M_p = I·α − M_d − r_p × F_p − r_d × F_d.

**Derived quantities.**
* Peak knee moment: max over stance of M_knee / m (N·m/kg).
* Quadriceps (patellar tendon) force: F_quad = max(M_knee, 0) / r, with r = 5 cm and a sensitivity range of
  4–6 cm [6]. This is a net-moment-equivalent force. It ignores co-contraction, so it is not a measured muscle
  force, and it is **not** knee joint contact force, which is not estimated.
* Knee power: P = M_knee · ω_ext, with ω_ext = −d(knee flexion)/dt in rad/s. Negative power is eccentric energy
  absorption.
* Negative work: ∫ min(P, 0) dt over stance, divided by m (J/kg). Peak power absorption: −min(P) / m (W/kg).
* Extensor angular impulse: ∫ max(M_knee, 0) dt over stance, divided by m (N·m·s/kg). It is reported per step,
  in total and per metre descended. It measures mechanical demand, not fatigue.
* Arm moments (when a pole force exists): quasi-static elbow and shoulder moments from the pole force at the grip
  (midway between wrist and index knuckle) plus forearm and upper-arm weight.

**Sensitivity.** For every scenario trial the app recomputes the peak moment, quadriceps force and impulse over a
grid: support model (static, dynamic) × force direction (toward COM, vertical) × c ∈ {0.25, 0.5, 0.75} ×
pole force (0.5, 1 and 1.5 × the assumed value) × r ∈ {4, 5, 6} cm. The reported range is the grid's minimum to
maximum. Elbow and shoulder moments are recomputed at 0.5 and 1.5 × the pole force. Knee and arm models always use
the **same** pole force, so the modelled transfer of load from the legs to the arms is consistent.

**Physical consistency checks (automated tests).**
* Moments scale linearly with body mass, and scale-free angles are unchanged.
* A force line through the knee gives zero moment.
* With the COM directly above the COP, the COM model equals the vertical model.
* Hand-calculated examples match to 10⁻⁶ N·m: 700 N at 5 cm gives 35 N·m; a force tilted toward the COM gives −28 N·m.
* Static inverse dynamics matches a hand calculation, and a swinging pendulum matches I·α plus the gravity term.
* Without measured body metrics, every kinetic output is blocked.

**Check on real data.** These numbers use labelled test values (75 kg, 1.75 m) on a copy of the study, because
real body metrics are not entered yet.
* P01 trial 1, version 2.1 tracker, no pole force: 2.87 N·m/kg with a vertical force; 1.82 with the force toward
  the COM; 1.50 at c = 0.75.
* Same trial, version 3 tracker, 10% body weight per pole: 1.42 N·m/kg (sensitivity range 1.04–3.27). Peak shoulder
  moment 18 N·m (8–29).

Published stair-descent values are 1.0–1.6 N·m/kg [10]. The vertical model overestimates, which is why the COM
direction is the default. Other reasons an estimate can be high: the quasi-static support ignores segment inertia,
and the 2D projection misplaces the COP.

## Validation and limitations

* **2D only.** All angles are projections onto each camera's image plane. They equal sagittal (side) or frontal
  (front) angles only when the camera is perpendicular to that plane. The cameras were not calibrated, so we report
  no 3D kinematics and no distances in metres unless a scene distance is calibrated. DLT triangulation is implemented
  but needs ≥ 6 surveyed control points, and its output is labelled *unvalidated*.
* **Forces are not measured.** Knee moments and muscle forces come from a stated scenario model with sensitivity
  ranges. They are suitable only for comparing conditions within a participant. Joint contact force and fatigue are
  not estimated.
* **Tracking uncertainty.** The app reports keypoint confidence, detection rate, the percentage of removed spikes and
  of gap-filled samples, and pole tracking coverage and confidence for each trial. Pole detection relies on the
  colour of our poles. It was checked visually on frames from all three participants (it correctly found no pole in
  trials without poles), but it has not been validated against reference markers.
* **Reliability.** Trials are averaged within each participant. A change between conditions is called *larger than
  noise* only when it exceeds 1.96·√(SD_b²/n_b + SD_c²/n_c) of that participant's repeated trials [7]. With n = 3
  we make no population inferences.
* **Automated tests.** The test suite checks the calculations against analytic geometry (angles to < 0.01°), a static
  hand calculation and a swinging pendulum (inverse dynamics), synthetic clap offsets (< 8 ms), known envelope lags
  (pairing), rendered pole frames, and the interface workflows.

## Reproducibility

The default processing settings are:

* tracking with RTMPose-m + YOLOX-m ("balanced"), every frame, CPU
* keypoint confidence ≥ 0.5
* spike removal: k = 6 robust SD, a 7-frame window, and a floor of 8% of leg length
* gap filling up to 0.1 s, and a 6 Hz Butterworth filter
* a pole hue of 95–150 (OpenCV), saturation ≥ 45 and value ≥ 55, a maximum pole angle of 40°, and a minimum run of 5 frames
* audio envelopes with a 10 ms hop and a 300 Hz high-pass

Every exported trial includes `processing_settings.json` with these values, the sync offset and method, the
pairing score and the software version. Dependencies are pinned in `uv.lock`.

**References.**
[1] Jiang T. et al. (2023) RTMPose. arXiv:2303.07399.
[2] Ge Z. et al. (2021) YOLOX. arXiv:2107.08430.
[3] Bazarevsky V. et al. (2020) BlazePose. arXiv:2006.10204.
[4] Winter D.A. (2009) *Biomechanics and Motor Control of Human Movement*, 4th ed.
[5] Zeni J.A. et al. (2008) *Gait Posture* 27:710–714.
[6] Tsaopoulos D.E. et al. (2009) *Eur J Appl Physiol* 105:809–814; Krevolin J.L. et al. (2004) *J Biomech* 37:785–788.
[7] Hopkins W.G. (2000) *Sports Med* 30:1–15.
[8] de Leva P. (1996) *J Biomech* 29:1223–1230.
[9] Herr H., Popovic M. (2008) *J Exp Biol* 211:467–481.
[10] Zhang et al. (2020) *Appl Bionics Biomech*, doi:10.1155/2020/7451683, Tables 7–9 (including Riener et al. 2002 and McFadyen & Winter 1988); see `docs/research/reference-ranges.md`.
