# Scientific methods

This document lists every calculation the app performs: the equation, the assumptions, the units and the
source. The analysis code lives in [`src/trailbuddy/core/`](../src/trailbuddy/core). Each formula below
names the function that implements it, and the unit tests in [`tests/`](../tests) check each one against
hand calculations or exact synthetic data.

## 1. Evidence labels

Every output carries one label. The app shows it as a coloured badge, and every exported table has it as a column.

| Label | Meaning | Examples |
|---|---|---|
| Measured | Measured directly by an instrument | Force-plate GRF, pole load cell, body mass |
| Video estimate (2D) | Kinematics from pose tracking in 2D video | Joint angles, contact timing, speed |
| Model estimate | Model output that uses *measured* external forces | Inverse-dynamics knee moment with a force plate |
| Scenario (assumed force) | Model output that uses an *assumed* external force | Quasi-static knee moment from video alone, arm moments with an assumed pole force |
| Unavailable | Cannot be estimated credibly with the data we have | Tibiofemoral compression; pole force from video alone |

**Knee angle is not knee load.** Video gives angles. A load needs an external force plus a model.

## 2. Pose estimation and signal processing

* **Landmarks.** MediaPipe Pose Landmarker (BlazePose GHUM, 33 landmarks) runs in video mode on every frame of
  the analysis interval (`pose.estimate`). Frames with no detection are stored as NaN, and the app never fills them with invented values.
* **Confidence gate.** Any landmark with visibility below 0.5 is discarded (`kinematics.compute`).
* **Gap filling.** Gaps of 0.1 s or less are filled by linear interpolation and flagged. Longer gaps stay empty (`signal.fill_gaps`).
* **Filtering.** A 2nd-order Butterworth low-pass filter runs forward and backward, which gives zero phase lag
  and an effective 4th-order response. The default cutoff is 6 Hz (Winter et al., 1974; Winter, 2009) and can be changed (`signal.lowpass`).
* **Missing far-side landmarks.** In a side view the far limbs are often hidden. Mid-hip and mid-shoulder use
  whichever side is visible, and whole-body centre of mass substitutes the visible side for hidden far-side segments.
* **Camera-B resampling** never bridges gaps longer than 0.1 s.
* **Lab frame.** x points horizontally in the direction of travel (the app detects which way the person walks across the image) and y points up.
  Pixels are converted to metres with a scale *s* (m/px):
  * **Measured distance (preferred):** *s* = *d*<sub>real</sub> / *d*<sub>px</sub> between two points you click,
    such as a stair riser of known height (`kinematics.scale_from_points`).
  * **Body height (approximate):** *s* = *H* (0.245 + 0.246) / median(thigh<sub>px</sub> + shank<sub>px</sub>), using
    Winter's segment-length fractions (`kinematics.scale_from_height`). Expect roughly ±5–10% error.

## 3. Joint angles (2D)

Segment angle θ is measured counter-clockwise from +x, using the vector that runs from the distal end to the proximal end.

| Angle | Definition | Zero | Positive |
|---|---|---|---|
| Knee flexion | θ<sub>thigh</sub> − θ<sub>shank</sub> | straight leg | flexed |
| Hip flexion | θ<sub>thigh</sub> − θ<sub>trunk</sub> | thigh in line with trunk | thigh forward |
| Ankle dorsiflexion | 90° − (θ<sub>shank</sub> − θ<sub>foot</sub>) | shank ⟂ heel–toe line | dorsiflexed |
| Trunk lean | 90° − θ<sub>trunk</sub> (mid-hip → mid-shoulder) | vertical | forward lean |
| Shoulder flexion | θ<sub>upper arm</sub> − θ<sub>trunk, pointing down</sub> | arm along trunk | arm forward |
| Elbow flexion | 180° − ∠(shoulder, elbow, wrist) | straight | flexed |

These are projections onto the image plane. They equal true sagittal angles only when the camera's optical
axis is perpendicular to the plane of motion. The app analyses the side that faces the camera, which is the side with the higher mean
landmark visibility, unless you choose a side yourself.

Two-camera trials also report the camera-B knee angle. When camera B faces the participant from the front, the app reports
the **knee frontal-plane projection angle** (180° − hip–knee–ankle angle in the frontal image). This is a 2D screening
measure, not a 3D valgus angle.

## 4. Gait and pole events

A foot is **in contact** while the speed of its midpoint (halfway between heel and toe) stays below 15% of its
95th-percentile speed for at least 0.08 s (`events.contact_intervals`). On stairs the foot stays still on each
tread while it carries weight, so this velocity-threshold approach works for descent. Similar kinematic methods are
used for level walking (O'Connor et al., 2007; Zeni et al., 2008). Pole-tip contacts are detected the same way.
Treat event times as estimates accurate to about ±1–2 frames, and spot-check them on the video.

* Step time is the time between foot strikes of alternating feet. A contact that is already in progress at the first frame is not a strike, so it is excluded. Cadence = 60 / mean step time.
* Stance time is the duration of each complete contact. Contacts cut off by the clip edges are excluded.

## 5. Lower-limb kinetics

### 5a. With a measured ground reaction force (force plate or instrumented step)

The app runs 2D Newton–Euler inverse dynamics, working up from the foot to the shank to the thigh (Winter, 2009, ch. 5; `dynamics.inverse_dynamics_leg`). For each segment
with mass *m*, moment of inertia about its centre of mass *I*, centre-of-mass acceleration **a** and angular acceleration α:

    F_p = m·a − m·g − F_d
    M_p = I·α − M_d − r_p × F_p − r_d × F_d

Here *d*/*p* are the distal and proximal joints, and **r** runs from the segment's centre of mass to that joint. For the foot, **F**<sub>d</sub> is the GRF applied at
the centre of pressure (COP). Segment parameters come from Winter (2009, Table 4.1), which is derived from Dempster (1955). The
unit tests check this against a static hand calculation and an analytic swinging pendulum. Sign convention: knee + = extensor, and hip
and ankle are reported as extensor and plantarflexor.

### 5b. Video only: quasi-static scenario model (labelled *Scenario*)

Video cannot measure external forces, so a transparent quasi-static model is used instead (`dynamics.quasi_static_knee`):

    M_knee,ext(t) = F_foot(t) · [ x_knee(t) − x_COP(t) ]
    F_foot(t)     = share(t) · max( F_support(t) − F_pole,vertical(t), 0 )

* **F<sub>support</sub>:** body weight *mg* (static, the default), or *m*(*g* + *a*<sub>COM,y</sub>), where the whole-body
  centre of mass comes from Winter segment masses (dynamic option). The dynamic option uses the second derivative of video
  data and is noisy.
* **share(t):** the analysed leg carries 1 in single support, 0 in swing, and changes linearly from the trailing leg to the leading leg during double support (`dynamics.leg_load_share`). If the other foot's contacts can't be detected (it is often hidden), double
  support can't be identified. The analysed leg is then assumed to carry all support, the result is an **upper bound**,
  and a note is added.
* **x<sub>COP</sub>:** an assumed point on the foot, given as a fraction of the heel-to-toe distance (default 0.5).
* **Assumptions:** the GRF is vertical, and inertia and the weight of the shank and foot are ignored. The model therefore
  **does not capture impact peaks**, which during stair descent can exceed body weight. It is meant for
  comparing conditions under the same assumptions, not for reporting absolute loads.
* **Sensitivity analysis.** Each trial is re-computed for {static, dynamic support} × COP {0.25, 0.5, 0.75} ×
  moment arm {4, 5, 6 cm}. The range is reported next to each value and saved in `sensitivity.csv`.

### 5c. Quadriceps (patellar tendon) force

    F_quad = max(M_knee,ext, 0) / r_PT

The patellar tendon moment arm *r*<sub>PT</sub> defaults to **5 cm**, and every trial also reports the range for **4–6 cm**. These values come from
in vivo 2D measurements of about 5.9 cm at 0° falling to about 4.8 cm at 90° (Tsaopoulos et al., 2009) and cadaver peaks of 4–6 cm
(Krevolin et al., 2004). The moment arm grows by 6–26% under contraction (Tsaopoulos et al., 2007), so resting values
probably *overestimate* force. Antagonist co-contraction is ignored, which means this is a **net-moment-equivalent** estimate and
is likely an underestimate of true quadriceps force. The two biases work in opposite directions. Compare conditions
rather than reading absolute values.

### 5d. Knee power and eccentric work

    P_knee = M_knee,ext · ω_ext,   ω_ext = −d(knee flexion)/dt   [rad/s]
    W_neg  = ∫ min(P_knee, 0) dt   over stance   [J/kg after dividing by body mass]

Negative power, where the knee flexes while an extensor moment acts, means the knee extensors are absorbing energy eccentrically.

## 6. Upper-limb kinetics and pole force

Ordinary video **cannot measure pole force**. The app accepts measured pole force from a load cell CSV,
or an explicitly assumed **scenario** of *X*% body weight of axial force per planted pole. The pole is treated as a
two-force member, so it pushes on the hand along its own axis (from the tip towards the hand). Pole direction comes from the tracked tip and
the wrist landmark, or is assumed vertical (and flagged) when the pole is not tracked.

    F_hand = F_axial · û(tip → hand)
    M_elbow,int = −[(r_hand − r_elbow) × F_hand + (r_COM,forearm+hand − r_elbow) × W_forearm+hand]
    M_shoulder,int = −[(r_hand − r_shoulder) × F_hand + Σ arm segment weight moments]

These are quasi-static, because arm motion during planting is slow (`dynamics.arm_moments`). Elbow + = extensor. Shoulder + =
flexor (arm-forward direction). Peaks are reported as absolute values. The same pole force reduces the foot force in §5b,
so knee unloading and arm loading always come from one consistent assumption.

## 7. Mechanical-demand metrics (not fatigue)

* **Cumulative knee extensor angular impulse:** ∫ max(M<sub>knee,ext</sub>, 0) dt over all stance phases in the window
  (N·m·s/kg). This captures both the size and the duration of extensor demand.
* **Impulse per metre descended:** the cumulative impulse divided by the height descended (step height × steps). This
  follows the per-unit-distance loading idea of Miller et al. (2014).
* **Negative knee work** (J/kg), defined in §5d, and **peak knee power absorption** (W/kg, the magnitude of the most
  negative knee power in stance).
* **Impulse per step:** the cumulative impulse divided by the number of stance phases.

These describe **mechanical loading**. They are not muscle fatigue (no EMG or force-decline measurement), perceived
exertion, pain or injury risk, and the app never combines them into a "fatigue score". A defensible fatigue measure
would need, for example, EMG median-frequency shifts, maximal-strength testing before and after descent, or validated
ratings of perceived exertion.

## 8. Not estimated (reported as *Unavailable*)

* **Tibiofemoral and patellofemoral compression.** These need a musculoskeletal model with antagonist
  (hamstring and gastrocnemius) forces and measured GRF, for example OpenSim with force-plate data. Lower quadriceps force does not
  show lower joint compression (see Jensen et al., 2011).
* **Pole force from video alone.**
* **3D kinematics without calibration.** With a DLT calibration (≥ 6 non-coplanar control points; Abdel-Aziz &
  Karara, 1971/2015), the app reconstructs 3D hip, knee and ankle positions and reports knee flexion labelled *"calibrated,
  unvalidated"* until it has been checked against a known distance or angle.

## 9. Two-camera synchronisation

Automatic sync (`sync.sync_audio`) works in five steps:

1. Decode each audio track to mono at 16 kHz.
2. High-pass filter above 1 kHz, so the clap stands out over speech and footsteps.
3. Compute the RMS envelope with a 2.5 ms hop, then the positive log-energy difference weighted by loudness.
4. Take the strongest onset as the clap.
5. Refine the offset by cross-correlating the envelopes within ±0.25 s.

Known limitation: phone MP4 files can start their audio stream a few tens of milliseconds before or after the
first video frame, and this offset can differ between phones. The app does not yet correct for it, so check sync
visually on the clap frame, or use manual frame sync when single-frame precision matters. Clap clarity is the peak divided by the 99th percentile of the rest of the envelope, and the app warns when it is below 3. Manual sync uses the frame where the hands first touch in each video:
offset = *f*<sub>A</sub>/fps<sub>A</sub> − *f*<sub>B</sub>/fps<sub>B</sub>. Convention: *t*<sub>A</sub> = *t*<sub>B</sub> + offset. Different frame rates are
handled by resampling camera-B landmarks onto camera A's time base with linear interpolation. The tests check
offsets within 5 ms on raw audio and within 8 ms after AAC encoding in MP4 files, with cameras at 60 fps and 30 fps.

## 10. Reference ranges (context, not good/bad)

Each metric card shows the trial value against a published band for healthy adults descending stairs. The band is
either mean ± 1 SD of a cited cohort or the range of study means from a review (`core/reference.py`; details and
verification status in [research/reference-ranges.md](research/reference-ranges.md)):

| Metric | Band | Source |
|---|---|---|
| Peak knee flexion (stance) | 76–89° | Lewis et al. 2015 (82.6 ± 6.6°, n = 30) |
| Knee flexion range of motion | 76–90° | Zhang et al. 2020 review (study means) |
| Peak hip flexion (stance) | 13–29° | Lewis et al. 2015 (21.2 ± 7.7°) |
| Peak ankle dorsiflexion (stance) | 23–38° | Lewis et al. 2015 (30.6 ± 7.3°) |
| Peak knee extensor moment | 1.0–1.6 N·m/kg | Zhang et al. 2020 review (late-stance peak, study means) |
| Peak knee power absorption | 2.1–5.5 W/kg | Zhang et al. 2020 review; Riener et al. 2002 |

The labels are *below typical*, *typical range* and *above typical*. They describe where a value sits relative
to lab data. They are not health, performance or injury judgements. The bands come from 3D motion capture, while our
values are 2D video estimates, and the scenario model has no impact peaks, so small offsets are expected. Compare
conditions within a person first.

## 11. Is a change bigger than the noise?

Each participant repeats every condition (usually 3 trials). The app uses the **typical error** idea (Hopkins, 2000), which is the
same logic as the minimal detectable change (Weir, 2005), applied to the mean of repeated trials. A difference
between two condition means counts as *larger than the noise* when

    |mean_condition − mean_baseline| > 1.96 · sqrt( SD_b² / n_b + SD_c² / n_c )

where SD is that participant's trial-to-trial standard deviation in each condition. The overview figure colours these
changes and greys out the rest. This is a per-person repeatability check, not a population significance test.

## 12. Fatigue: what we report and why

Published fatigue models, such as the three-compartment model of Xia and Frey-Law, implemented in bioptim
(MIT), need each person's load as a percentage of their *maximal* knee strength. They are validated mainly for
sustained isometric efforts. We have no strength testing, no EMG and no validation for eccentric stair descent, so a
fatigue estimate would not be defensible. The app reports **mechanical demand** instead:

* peak and cumulative knee extensor angular impulse (total, per step, and per metre descended)
* negative knee work and peak knee power absorption
* **change across repetitions** (Results → Repetitions). This plot shows drift over trials 1 → 3, which may reflect
  fatigue, learning or pacing and cannot separate them.

Other tools we checked: opencap-processing (Apache-2.0) needs 3D OpenCap data from two or more phones;
opencap-monocular has a non-commercial licence; OpenSim needs 3D kinematics; kineticstoolkit (Apache-2.0) is
an option for future filtering and cycle tools.

## 13. Statistics and comparisons

Trials are averaged **within each participant** first. Differences are reported per participant as absolute values and as
100 × (condition − baseline) / |baseline|. Trial-to-trial variability is reported as SD and CV. Group summaries are
descriptive: the mean, minimum and maximum of participant percentage changes, and how many participants decreased. Repeated trials
are never treated as independent participants, and no p-values are computed (n = 3).

## References

Full annotated list with verified DOIs: [research/literature.md](research/literature.md). Tool survey:
[research/open-source-tools.md](research/open-source-tools.md).

* Abdel-Aziz, Y. I., & Karara, H. M. (1971/2015). Direct linear transformation… *Photogramm. Eng. Remote Sens., 81*(2), 103–107. https://doi.org/10.14358/PERS.81.2.103
* Bazarevsky, V., et al. (2020). BlazePose: On-device real-time body pose tracking. arXiv:2006.10204.
* de Leva, P. (1996). Adjustments to Zatsiorsky-Seluyanov's segment inertia parameters. *J. Biomech., 29*(9), 1223–1230. https://doi.org/10.1016/0021-9290(95)00178-6
* Dempster, W. T. (1955). *Space requirements of the seated operator* (WADC-TR-55-159).
* Hopkins, W. G. (2000). Measures of reliability in sports medicine and science. *Sports Med., 30*(1), 1–15.
* Lewis, J., et al. (2015). *J. Electromyogr. Kinesiol., 25*(6), 982–989 (PMC4658237).
* Weir, J. P. (2005). Quantifying test-retest reliability using the intraclass correlation coefficient and the SEM. *J. Strength Cond. Res., 19*(1), 231–240.
* Zhang, et al. (2020). Review of stair-descent biomechanics. https://doi.org/10.1155/2020/7451683 (see reference-ranges.md)
* Jensen, S. B., et al. (2011). Can hiking poles reduce knee joint compression force? *Scand. J. Med. Sci. Sports* (see literature.md).
* Krevolin, J. L., Pandy, M. G., & Pearce, J. C. (2004). *J. Biomech., 37*(5), 785–788. https://doi.org/10.1016/j.jbiomech.2003.09.010
* Miller, R. H., et al. (2014). *Med. Sci. Sports Exerc., 46*(3), 572–579. https://doi.org/10.1249/MSS.0000000000000135
* O'Connor, C. M., Thorpe, S. K., O'Malley, M. J., & Vaughan, C. L. (2007). Automatic detection of gait events using kinematic data. *Gait & Posture, 25*(3), 469–474. (VERIFY DOI before citing.)
* Schwameder, H., et al. (1999). *J. Sports Sci., 17*(12), 969–978. https://doi.org/10.1080/026404199365362
* Tsaopoulos, D. E., et al. (2007). *J. Biomech., 40*(15), 3325–3332. https://doi.org/10.1016/j.jbiomech.2007.05.005
* Tsaopoulos, D. E., et al. (2009). *Eur. J. Appl. Physiol., 105*(5), 809–814. https://doi.org/10.1007/s00421-008-0968-3
* Winter, D. A. (2009). *Biomechanics and Motor Control of Human Movement* (4th ed.). Wiley. https://doi.org/10.1002/9780470549148
* Winter, D. A., Sidwall, H. G., & Hobson, D. A. (1974). *J. Biomech., 7*(2), 157–159. https://doi.org/10.1016/0021-9290(74)90056-6
* Zeni, J. A., Richards, J. G., & Higginson, J. S. (2008). *Gait & Posture, 27*(4), 710–714. https://doi.org/10.1016/j.gaitpost.2007.07.007
