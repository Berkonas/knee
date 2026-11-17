# Changelog

## Unreleased (evaluation pass, 2026-11-17)
- Pole tips now extend through the dark ferrule. Before this fix, automatic tips sat about 28 px above hand-labelled tips on all 10 detected poles (median error 31 px).
- One pole can no longer be assigned to both hands (common in side views). The minimum pole confidence is lowered to 0.15.
- Time-series and summary CSVs are written with 9 significant digits, and a `frame_index` column links every sample to its video frame.
- New test checks that the exported CSV matches the in-memory result and that each timestamp falls exactly on a video frame.

## 2.0.0 (2026-11-16)
- Dataset import, audio pairing, RTMPose + YOLOX tracking, markerless pole detection, synchronised front and side workspace, and light/dark interface (see README and RESEARCH_PIPELINE.md).
