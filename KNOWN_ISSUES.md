# Known issues

- **Visual clap sync is unreliable in side views.** Both wrists overlap in the projection, so the visual clap agreed with the audio clap in only 3 of 8 pairs. Use it only as a last resort and check the result visually.
- **Audio clap peak can pick a wrong transient.** It did so in 2 of 8 pairs (P01 trial 4, P03 trial 3). The app falls back to the whole-recording envelope correlation, which a frame check confirmed for P03 trial 3. P01 trial 4 remains uncertain by about 0.2 s and is flagged for review.
- **Pole detection is incomplete.** Against 16 hand-labelled pole tips on 8 reference frames (all 3 participants, both views), version 3:
  - found 13 tips; the misses were the hidden second pole in side views
  - had no wrong-shaft detections
  - had a tip error of median 13 px, 90th percentile 25 px and maximum 28 px through the full pipeline (12 px median when each frame is left out of the calibration). Version 2 had a median of 30 px.

  At this camera distance 13 px is about 4 cm. Pole angles remain more reliable than tip coordinates. The labels came from one annotator reading zoomed frames against a 20 px grid, with an estimated uncertainty of about ±5 px.
- **Pairing gaps for P03.** Front recordings IMG_5609, 5610 and 5612, and side recordings IMG_7496 and 7498, have no audio-matching partner.
- **Inputs still needed.** No participant has measured body mass or height yet, and all 13 trials have no condition assigned (`UNSET`). Loads stay unavailable and condition comparisons are empty until these are entered.
- **Peak knee flexion rose with the new tracker.** With RTMPose-x on tracked crops, peak knee flexion on full descents is 90–95°, versus 85–90° with the old model. Published values are 83 ± 7° (Lewis 2015). No marker-based reference exists for our recordings, so we cannot say which model is closer. Compare conditions within one tracker version.
- **Keypoint accuracy is not measured against hand labels.** Jitter and pole tips are measured. Joint-centre error would need hand-labelled joints, which we have not made.
- **Playback** steps in 29 ms (median) with both HD videos, about 34 frames/s, so 60 fps playback drops frames at 1×. Random scrubbing takes about 120 ms per seek.
- **Knee moment is a scenario estimate.** Even with the force directed toward the centre of mass, the estimate on real data (1.5–1.8 N·m/kg with test body metrics) sits at or above the top of the published range (1.0–1.6 N·m/kg). Use it to compare conditions within a participant, not as an absolute value.
- **Windows** builds and tests run only on GitHub's Windows CI runners. The installer has not been tried on a real PC.
- **Unsigned builds.** The macOS app is not notarised and the Windows installer is not signed, so each shows a one-time security prompt.
- **Large files in git history.** About 157 MB of model files remain in history (commit 6abf206). Removing them needs an approved force-push.
- **Pole dragging** cannot be told apart from planting in 2D video and is not assessed. In side views a hidden pole can make technique read as "single pole".
- **OpenSim is not integrated.** Joint contact or muscle forces would need measured ground reaction forces and 3D or scaled kinematics.
- **Council review incomplete (version 2.0).** The five independent reviewer agents were interrupted repeatedly by usage limits and session drops, so their written reports are not available. The review was completed directly instead: a QA run on all 13 real trials, a biomechanics consistency check, a UI check at three window sizes in both themes, and computer-vision validation against hand labels.
- **Rapid trial switching.** Memory grows to about 1 GB resident, mostly from the pose models and decoded frames, and is stable after switching trials 30 times.
