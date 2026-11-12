# User guide and experiment workflow

## A. Before test day

1. **Find out which forces are available.** Ask the CREATE lab about a force plate, an instrumented step, pressure
   insoles or a pole load cell. Write down which forces you will measure and which you will assume. This decides
   whether knee loads are reported as *Model* or *Scenario* estimates.
2. **Mark the poles.** Wrap 3–4 cm of bright tape (fluorescent orange or green) just above each pole tip. If you
   can, add a second band of a different colour below the grip. The app's colour tracker relies on these.
3. **Prepare a calibration distance.** Measure a stair riser height, or place a 1 m stick in the plane of motion.
   It must be visible in the side camera.

## B. Camera setup

* **Camera A (side view):** perpendicular to the walking direction, at about hip height, 3–5 m away. Keep the whole
  body and both pole tips in frame for the entire descent. Use 60 fps if your phone allows. Keep the camera still
  (use a tripod) and keep its settings the same for every trial.
* **Camera B (optional):** in front of the participant, or at about 45°. Record audio on both cameras.
* **Clap.** At the start of every trial, one person claps once, sharply, where both cameras can see and hear it.
* **File names:** `P01_C1_T01.mp4` (participant, condition, trial). Conditions: C0 = no poles, C1 = standard,
  C2 = standard − 5 cm, C3 = standard + 5 cm.

## C. Body metrics (once per participant)

Enter these in **Study → Add participant**. They can be edited any time with **Body metrics…**.

| Field | How to measure | Used for |
|---|---|---|
| Body mass (kg) | Scale, with shoes | All forces and moments, segment masses |
| Height (m) | Standing, with shoes | Scale estimate if no calibration distance |
| Standard pole length (cm) | Elbow at ~90° with the tip on level ground | Pole length per condition (±5 cm) |
| Thigh, shank (m), optional | Greater trochanter → knee joint line → outer ankle bone | Replaces textbook proportions in the scale |
| Foot, upper arm, forearm (m), optional | See the tooltips in the app | Stored with the participant's data for reporting |

## D. Test day (per trial)

1. Start both cameras and clap.
2. The participant descends at their usual pace, starting on the same foot each time, using the assigned technique.
3. Stop recording and note any deviations, such as a slip, a missed step or the pole catching.
4. Do 1–2 practice descents per condition, then 3 recorded trials. Randomise the order of conditions for each participant.

## E. Analysis workflow in the app

1. **Study:** create the study, add participants and trials.
2. **One camera / Two cameras:** open a trial and set the start and end of the descent.
3. **Scale:** pick two points on your calibration distance (best), or use height or measured segments.
4. **Sync (two cameras):** **Detect clap from audio**. Check the reported clap clarity, and scrub to confirm
   both views match. If they don't, mark the clap frames and click **Apply manual sync**. Fine-tune the offset with the arrows.
5. **Poles:** pick the marker colour and track it, or annotate by hand. Uncertain or missing frames stay empty; they are never invented.
6. **External forces:** choose *Scenario* (assumed % body weight per planted pole) or import measured force data.
7. **Run analysis.** Then check the **Events** tab against the video and read the **Methods notes** tab.
8. **Results:** pick a metric and a baseline condition. Read the per-participant changes. **Export all results…**

## F. Reading the numbers

* Compare **conditions within a participant**, not absolute values across people.
* A *Scenario* value means "if the poles carried X% body weight, the model predicts…". Report it as a
  sensitivity or what-if result, not as a measurement.
* The **Range** column shows how a value changes when the model's assumptions change (moment arm, centre of pressure,
  support model). If two conditions differ by less than this range, say the difference is not robust.
* Never call cumulative impulse or negative work "fatigue". They measure mechanical demand.
