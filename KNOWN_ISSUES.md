# Known issues

- **Visual clap sync is unreliable in side views.** Both wrists overlap in the projection, so the visual clap agreed with the audio clap in only 3 of 8 pairs. Use it only as a last resort and check the result visually.
- **Audio clap peak can pick a wrong transient.** It did so in 2 of 8 pairs (P01 trial 4, P03 trial 3). The app falls back to the whole-recording envelope correlation, which a frame check confirmed for P03 trial 3. P01 trial 4 remains uncertain by about 0.2 s and is flagged for review.
- **Pole detection is incomplete.** Against 16 hand-labelled pole tips on 8 reference frames (all 3 participants, both views), the final detector:
  - found 12 tips; all 4 misses were the hidden second pole in side views
  - had no wrong-shaft detections
  - had a tip error of median 30.5 px, 90th percentile 34 px, maximum 38.5 px

  At this camera distance 30 px is about 9 cm, so tip position is approximate and pole angles are more reliable than tip coordinates. The labels came from one annotator reading zoomed frames against a 20 px grid, with an estimated uncertainty of about ±5 px.
- **Pairing gaps for P03.** Front recordings IMG_5609, 5610 and 5612, and side recordings IMG_7496 and 7498, have no audio-matching partner.
- **Inputs still needed.** No participant has measured body metrics yet, so all estimated loads are blocked. Trial conditions are unassigned. Enter both in the app.
- **Knee moment is a scenario estimate.** Even with the force directed toward the centre of mass, the estimate on real data (1.5–1.8 N·m/kg with test body metrics) sits at or above the top of the published range (1.0–1.6 N·m/kg). Use it to compare conditions within a participant, not as an absolute value.
- **Windows** builds and tests run only on GitHub's Windows CI runners. The installer has not been tried on a real PC.
- **Unsigned builds.** The macOS app is not notarised and the Windows installer is not signed, so each shows a one-time security prompt.
- **Large files in git history.** About 157 MB of model files remain in history (commit 6abf206). Removing them needs an approved force-push.
- **Council review incomplete.** The five independent reviewer agents were interrupted repeatedly by usage limits and session drops, so their written reports are not available. The review was completed directly instead: a QA run on all 13 real trials, a biomechanics consistency check, a UI check at three window sizes in both themes, and computer-vision validation against hand labels.
- **Rapid trial switching.** Memory grows to about 1 GB resident, mostly from the pose models and decoded frames, and is stable after switching trials 30 times.
