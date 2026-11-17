# Known issues

- **Visual clap sync is unreliable in side views.** Both wrists overlap in the projection, so the visual clap agreed with the audio clap in only 3 of 8 pairs. Use it only as a last resort and check the result visually.
- **Audio clap peak can pick a wrong transient.** It did so in 2 of 8 pairs (P01 trial 4, P03 trial 3). The app falls back to the whole-recording envelope correlation, which a frame check confirmed for P03 trial 3. P01 trial 4 remains uncertain by about 0.2 s and is flagged for review.
- **Pole detection is incomplete.** It found 10 of 16 hand-labelled pole tips on 8 reference frames, missing mostly in side views (HDR colour, overlapping poles). The ferrule fix must be re-validated on those frames.
- **Pairing gaps for P03.** Front recordings IMG_5609, 5610 and 5612, and side recordings IMG_7496 and 7498, have no audio-matching partner.
- **Inputs still needed.** Body metrics are placeholders and trial conditions are unassigned. The user must enter both.
- **Windows** is tested only in CI and packaged builds, not on a real PC.
- **Large files in git history.** About 157 MB of model files remain in history (commit 6abf206). Removing them needs an approved force-push.
- **Review findings pending.** The independent council review (software, computer vision, biomechanics, UI/UX, QA) started, but its findings are not yet incorporated.
