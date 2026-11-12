# Data formats

## Study folder

```
<study>/project.json                 participants, conditions, trial log, sync and settings
<study>/trials/<P01_C1_T01>/
    pose_A.csv / pose_A.json         raw MediaPipe landmarks (pixels) + cache key
    pose_B.csv                       camera B landmarks (two-camera trials)
    timeseries.csv                   time series: angles, stance, moments, forces, power
    summary.csv                      one row per metric: value, sd, low/high range, unit, evidence, note
    events.csv                       foot and pole contact intervals
    sensitivity.csv                  scenario-model sensitivity grid
    analysis.json                    settings, notes, tracking quality
    poles_manual.json, pole_*_marker.csv   pole annotations/tracks
    aligned/, *_clip_*.mp4           trimmed copies (originals are never modified)
```

## Force import (CSV)

The file needs a header row and a `time_s` column, plus any of the following:

| Column | Meaning |
|---|---|
| `fz_n` (or `fy_n`, `vertical_n`) | Vertical ground reaction force on the analysed foot, N, + up |
| `fx_n` (or `ap_n`) | Horizontal GRF along the walking direction, N, + forward |
| `cop_x_m` | Centre of pressure along the walking direction, m, in the plate frame |
| `pole_left_n`, `pole_right_n` | Pole axial forces, N, compression positive |

Align the clocks with **Force time offset** under advanced settings: t<sub>video</sub> = t<sub>force</sub> + offset.
A sharp tap on the plate during the clap works well as a shared event.

## DLT calibration (CSV, optional)

One row per control point, with at least 6 non-coplanar points: `X_m, Y_m, Z_m, uA, vA, uB, vB` (pixel coordinates in
camera A and camera B).

## Export folder

`all_metrics_long.csv`, `trials_by_metric.csv`, `within_participant_changes.csv`, `trailbuddy_results.xlsx` (sheets:
trials × metrics, participant means, within-participant, group, trial log, participants, metric definitions),
`figures/*.png|svg|pdf`, `analysis_summary.md`.
