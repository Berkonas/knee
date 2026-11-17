# Calculation audit

For each output, this table lists its equation, its inputs, the assumptions it needs, the analysis mode that
produces it, and how it is checked.

**Validation states**
* **unit-tested:** the software matches hand calculations or analytic cases.
* **checked on real data:** compared with hand labels or published ranges from our recordings.
* **not validated:** no independent reference exists for our setup.

Unit tests prove the code does what the equations say. They do not show that the equations describe our
participants.

Symbols: *m* body mass, *g* = 9.81 m/s², θ angles from vertical, *r* knee-extensor moment arm.

## Kinematics (mode A and up)

| Output | Equation | Inputs | Assumptions | Validation |
|---|---|---|---|---|
| Knee flexion (deg) | θ<sub>thigh</sub> − θ<sub>shank</sub> | hip, knee, ankle keypoints (side view) | camera roughly perpendicular to the sagittal plane; 2D projection | unit-tested (analytic geometry, < 0.01°); checked on real data: P01–P03 peaks 80–95° vs 83 ± 7° published (Lewis 2015) |
| Hip flexion, ankle dorsiflexion, trunk lean | segment-angle differences | keypoints | as above | unit-tested; hip and ankle within published bands on most trials |
| Angular velocity (deg/s) | central difference of the 6 Hz-filtered angle | angle series | 6 Hz cut-off keeps stair-descent content (Winter 2009) | unit-tested |
| Knee frontal-plane projection angle | 180° − ∠(hip, knee, ankle) in the front view | front keypoints | 2D frontal projection | unit-tested; not validated |
| Foot contact, foot strike, toe-off | heel or toe speed below 20% of its 95th percentile for ≥ 0.12 s | heel, toe keypoints | a stationary foot is in contact | unit-tested on synthetic gait; not validated against a force plate |
| Cadence, step and stance time | from same-foot strides and contacts | contacts | as above | unit-tested |
| Movement segments | mid-hip speed > 0.25 leg/s, pauses < 0.6 s bridged, labelled by hip-height change | hip, ankle keypoints | descending hips mean descent | unit-tested (synthetic two-descent trace) |

## Poles (mode A and up)

| Output | Equation | Inputs | Assumptions | Validation |
|---|---|---|---|---|
| Pole tip position | Hough segment from the hand + 7.1% of the hand-to-shaft-end length for the dark tip | video frame, wrist | pole colour (HSV), shaft starts at the hand | checked on real data: 13/16 hand-labelled tips found, none on the wrong object; median 14 px, 90th percentile 26 px (12 px median with each frame left out of the calibration) |
| Pole angle (deg) | angle of the hand→tip line from vertical | tip, wrist | 2D projection | unit-tested |
| Pole contact, plant timing | tip stationary; plant minus nearest foot strike | tip track, contacts | a stationary tip is planted | unit-tested |
| Technique (alternating, simultaneous, single, mixed) | share of plants within 0.15 s of the other pole's plant | pole contacts | both poles visible | unit-tested; a hidden pole in side views can read as "single pole" |
| Steps without a pole plant (%) | foot strikes with no plant within 0.35 s | events | as above | unit-tested |

## Loads, mode B (scenario) or C (measured)

All loads need the measured body mass and a metric scale. Without them they are *unavailable*.

| Output | Equation | Inputs | Assumptions | Validation |
|---|---|---|---|---|
| Vertical support | F<sub>feet</sub> + Σ F<sub>pole</sub> cos θ<sub>pole</sub> = m·g (static) or m·(g + a<sub>COM,y</sub>) | m, pole force, pole direction | quasi-static; inertia ignored in the static option | unit-tested (F cos θ, mass scaling) |
| Leg share | 1 in single support; linear hand-over in double support | foot contacts | load transfers linearly | unit-tested |
| Foot force direction | from the COP toward the whole-body COM (default), or vertical | COP, COM (Winter / de Leva segment parameters) | small angular momentum about the COM (Herr & Popovic 2008) | unit-tested: a force line through the knee gives zero moment; a COM above the COP reduces to the vertical model |
| Knee extensor moment (N·m, N·m/kg) | M = (x<sub>k</sub> − x<sub>COP</sub>)F<sub>y</sub> + (y<sub>COP</sub> − y<sub>k</sub>)F<sub>x</sub> | above + knee position | COP at c = 0.5 of heel→toe (range 0.25–0.75) | unit-tested (hand calculations 35 and −28 N·m); real data with test body metrics: 1.4–1.8 N·m/kg vs 1.0–1.6 published (Zhang 2020) |
| Knee moment, measured force | 2D Newton–Euler foot→shank→thigh | GRF, COP, m, segment kinematics | rigid segments; Winter inertia | unit-tested (static hand calculation, swinging pendulum) |
| Quadriceps-equivalent force (N, ×BW) | max(M, 0) / r, r = 5 cm (4–6 cm) | M | no co-contraction; **not** tendon or tibiofemoral force | unit-tested |
| Knee power, negative work, impulse | P = M·ω<sub>ext</sub>; ∫min(P,0)dt / m; ∫max(M,0)dt / m | M, knee angle | as above | unit-tested |
| Elbow and shoulder moment (N·m, N·m/kg) | (r<sub>grip</sub> − r<sub>joint</sub>) × F<sub>pole</sub> + segment-weight moments | pole force (same value as in the knee model), grip, joints | quasi-static arm; force along the pole | unit-tested (direction and sign); pole force ±50% sensitivity |
| Knee vs shoulder trade-off | paired change from the baseline condition within each participant | condition means, repetition SD | no-pole baseline has zero pole-induced arm moment | unit-tested |
| Pole support (% BW) | mean vertical pole force / (m·g) during stance | pole force | scenario or load-cell | unit-tested |

## Never calculated from video

These would need a constrained musculoskeletal model, such as OpenSim with measured GRF and EMG or
co-contraction constraints:
* tibiofemoral compression or joint contact force
* shoulder joint reaction force
* muscle fatigue, pain or injury risk

## Settings recorded with every result

Each trial's `analysis.json` stores everything needed to reproduce it:
* load mode
* every assumption (COP, pole force, force direction, moment arm, support model)
* tracking model and pipeline version
* scale source and analysis interval
* sync offset and method
