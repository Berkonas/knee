# Changelog

## Unreleased (evaluation pass, 2026-11-17)
- Pole tips now extend through the dark ferrule. Before this fix, automatic tips sat about 28 px above hand-labelled tips on all 10 detected poles (median error 31 px).
- A pole shaft can no longer be assigned to both hands. When both hands pick the same shaft (common in the side view), the less confident hand is left empty. An earlier version re-searched for the hidden pole, and in validation it picked wrong lines 3 times. The minimum pole confidence is lowered to 0.15.
- Export no longer fails for front-only trials. Figures that need side-view data are skipped and listed in `figures_skipped.txt`. A new front-view figure is added.
- Analysis-interval input is validated: an end before the start is rejected with a message.
- At small window sizes, the plot selector is now a drop-down menu, the time label is compact, and the slider keeps a minimum width. The plot legend follows the light or dark theme.
- Time-series and summary CSVs are written with 9 significant digits, and a `frame_index` column links every sample to its video frame.
- New test checks that the exported CSV matches the in-memory result and that each timestamp falls exactly on a video frame.

## 2.0.0 (2026-11-16)
- Dataset import, audio pairing, RTMPose + YOLOX tracking, markerless pole detection, synchronised front and side workspace, and light/dark interface (see README and RESEARCH_PIPELINE.md).
