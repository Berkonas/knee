# Known issues

- **Visual clap sync is unreliable in side views.** Both wrists overlap in the projection, so the visual clap agreed with the audio clap in only 3 of 8 pairs. Use it only as a last resort and check the result visually.
- **Audio clap peak can pick a wrong transient.** It did so in 2 of 8 pairs (P01 trial 4, P03 trial 3). The app falls back to the whole-recording envelope correlation, which a frame check confirmed for P03 trial 3. P01 trial 4 remains uncertain by about 0.2 s and is flagged for review.
- **Pole detection is incomplete.** Against 16 hand-labelled pole tips on 8 reference frames (all 3 participants, both views), the final detector:
  - found 12 tips; all 4 misses were the hidden second pole in side views
  - had no wrong-shaft detections
  - had a tip error of median 30.5 px, 90th percentile 34 px, maximum 38.5 px

  At this camera distance 30 px is about 9 cm, so tip position is approximate and pole angles are more reliable than tip coordinates. The labels came from one annotator reading zoomed frames against a 20 px grid, with an estimated uncertainty of about ±5 px.
- **Pairing gaps for P03.** Front recordings IMG_5609, 5610 and 5612, and side recordings IMG_7496 and 7498, have no audio-matching partner.
- **Inputs still needed.** Body metrics are placeholders and trial conditions are unassigned. The user must enter both.
- **Windows** is tested only in CI and packaged builds, not on a real PC.
- **Large files in git history.** About 157 MB of model files remain in history (commit 6abf206). Removing them needs an approved force-push.
- **Council review incomplete.** The five independent reviewer agents were interrupted repeatedly by usage limits and session drops, so their written reports are not available. The review was completed directly instead: a QA run on all 13 real trials, a biomechanics consistency check, a UI check at three window sizes in both themes, and computer-vision validation against hand labels.
- **Rapid trial switching.** Memory grows to about 1 GB resident, mostly from the pose models and decoded frames, and is stable after switching trials 30 times.
