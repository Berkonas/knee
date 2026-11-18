# Answering our research questions with TrailBuddy

**Our study design**
* Conditions: no poles (C0), standard (C1), −5 cm (C2) and +5 cm (C3).
* Terrains: flat ground, downhill ramp and stairs.
* 3 participants × 3 trials per cell = 108 trials. Choose *TrailBuddy full design* when creating a study.
* The terrain is part of each trial ID, for example `P01_C1_RAMP_T02`.
* Comparisons never pool terrains.

**Video cannot measure force.** Knee and shoulder loads come from two sources:
* **Mode B (scenario):** stated assumptions, labelled *scenario*.
* **Mode C (measured):** measured forces from a force plate or pole sensor.

Joint angles, timing and technique come from video in every mode.

## What we collect and where it goes in the app

| Data | Where to enter | Used for |
|---|---|---|
| Body mass, height | Participant information (required) | Every force and moment, normalisation (N·m/kg, × BW), video scale |
| Leg, thigh, shank, arm and forearm lengths | Participant information | Video scale; segment geometry |
| Age, sex or gender, dominant and lead leg, footwear, load | Participant information (optional) | Reporting only; never replaces measured anatomy |
| Pole length, number of poles, grip | Condition and trial details | Pole-length comparisons |
| Terrain, stair riser and tread, ramp angle, surface | Trial details | Terrain comparisons; knee impulse per metre descended |
| Pole push on a scale (kg) | Participant information, *Baseline tests* | Participant-specific scenario pole force (% body weight) |
| Pole sensor calibration (scale kg vs sensor reading) | Study, *Pole force calibration…* | Converts `pole_left_raw` / `pole_right_raw` to newtons with the inverse model F = (reading − b)/a |
| Force plate (fz_n, fx_n, cop_x_m) and pole force | Analyse, *Settings*, *Force data* | Mode C: measured-force inverse dynamics |
| EMG maximum tests (MVC) | Participant information, *Load MVC trial…* | Normalising EMG to %MVC |
| EMG during trials | Analyse, *Settings*, *EMG* (with a time offset) | %MVC peak and stance mean per muscle |

## The ten questions

| # | Question | In the app | Needs |
|---|---|---|---|
| 1 | Do poles reduce knee extensor demand? | Compare, *By condition* and *Overview*, metric *knee extensor moment* (baseline C0) | Mode B or C, body mass |
| 2 | Which length offloads most? | Compare, *Pole length* | as 1, conditions C1–C3 assigned |
| 3 | Does less knee demand mean more arm load? | Compare, *Trade-off*: paired change from C0, knee % vs shoulder N·m/kg | Mode B or C. In mode B the same pole force drives both sides, so the trade-off follows from the assumption: use a measured pole force or scale-test values for evidence. |
| 4 | Where are poles most useful? | Compare, *Terrain* filter: run 1 for flat, ramp and stairs | Trial terrain set |
| 5 | More pole force → less knee demand? | Compare, *Correlations*: pole support (% BW) vs knee moment | Measured pole force (mode C). Scenario forces make this circular. |
| 6 | Does pole timing matter? | Compare, *Correlations*: pole plant timing vs knee moment. Biomechanics and Analyse show the technique. | Pole tracking (video) and a knee moment |
| 7 | Does quadriceps EMG follow modelled load? | Compare, *Correlations*: EMG vastus %MVC vs quadriceps-equivalent force | EMG with MVC tests |
| 8 | Does shoulder demand raise arm EMG? | Compare, *Correlations*: EMG triceps or deltoid %MVC vs shoulder moment | EMG with MVC tests, pole force |
| 9 | Does trunk lean change joint demands? | Compare, *Correlations*: trunk lean vs knee or shoulder moment | Video, plus mode B or C |
| 10 | Are changes repeatable? | Compare, *Repetitions*. The change table flags changes larger than each participant's trial-to-trial noise. | ≥ 2 trials per cell |

**Statistics.** With 3 participants the app reports paired changes within each participant, the variability
across repetitions, and Spearman's ρ per participant. It does not report pooled p-values: repeated trials of one
person are not independent observations.

**What the literature leads us to expect.** Schwameder et al. (1999, *J Sports Sci* 17:969–978) found 12–25% lower
knee joint moments and forces with poles on a 25° downhill ramp. Bohne et al. (ISB 2005) found reduced knee
moments and power absorption on a 36° ramp. Stair-descent evidence with poles is scarce, so our stair data are
the novel part.

## Recommended protocol additions

**Scale test (cheap, no sensor).** For each participant and pole length:
1. Put a board on the scale to spread the load.
2. Have the participant plant the pole as on the stairs, five times.
3. Enter the readings in kg.

The app uses the mean as that participant's scenario pole force.

**Pole sensor.** If a load cell or strain gauge is available:
1. Calibrate it on the scale at 5–8 forces covering 0–25 kg.
2. Enter the points under *Pole force calibration…*. The app reports R² and the error in newtons.
3. Record trials with `pole_left_raw` / `pole_right_raw` columns.

**MVC tests** (one CSV per muscle test is fine; the values accumulate). Three 3–5 s maximal efforts per muscle:
* quadriceps: seated knee extension against resistance
* triceps: elbow extension
* deltoid: shoulder flexion or abduction

The app takes the largest 0.5 s average of the envelope.

**Sync.** Clap once in view of both cameras. Record the clap on the EMG or force system too, for example a tap on
the force plate, so you can read its time offset.
