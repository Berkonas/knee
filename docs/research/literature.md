# Annotated bibliography

How sources were checked (2026-11-11):

- Each DOI was confirmed to exist through Crossref metadata and the doi.org handle API (HTTP 200).
- Numbers quoted below come from the PubMed or arXiv abstract unless the entry says otherwise.
- **VERIFY** marks anything we could not confirm from a primary source: values found only in the full text, values from secondary sources, or values from memory. These need checking against the full text before they go into the report.

---

## 1. Trekking and hiking poles and knee loading

**Schwameder, H., Roithner, R., Müller, E., Niessen, W., & Raschner, C. (1999).** Knee joint forces during downhill walking with hiking poles. *Journal of Sports Sciences, 17*(12), 969–978. https://doi.org/10.1080/026404199365362

- **Relevance:** The closest precedent for our method. It used a planar quasi-static knee model to compare downhill walking with and without poles.
- **Values (abstract):**
  - 8 males on a ramp declined at 25°.
  - With poles, peak and average ground reaction force, knee joint moment, and tibiofemoral compressive and shear forces were significantly lower, by **12–25%**.
  - Patellofemoral compressive force, quadriceps tendon force and vastus lateralis activity showed similar reductions, but these were not significant because of high variability.
  - The authors attribute the reduction to the force on the poles and to a more forward-leaning trunk, which shortens the knee moment arm. **Our 2D model should capture both mechanisms.**

**Bohne, M., & Abendroth-Smith, J. (2007).** Effects of hiking downhill using trekking poles while carrying external loads. *Medicine & Science in Sports & Exercise, 39*(1), 177–183. https://doi.org/10.1249/01.mss.0000240328.31276.fc

- **Relevance:** Shows that the pole effect on lower-limb joint moments holds even under backpack load.
- **Values (abstract):**
  - 15 experienced male hikers.
  - Three pack conditions: none, 15% body weight and 30% body weight.
  - 2 × 3 repeated-measures ANOVA.
  - With poles, the sagittal-plane moment fell significantly at the ankle, knee and hip, and peak power absorption fell at the ankle and knee. These results held across pack conditions.
- **Percent reductions and effect sizes are not in the abstract. VERIFY in the full text.**

**Willson, J., Torry, M. R., Decker, M. J., Kernozek, T., & Steadman, J. R. (2001).** Effects of walking poles on lower extremity gait mechanics. *Medicine & Science in Sports & Exercise, 33*(1), 142–147. https://doi.org/10.1097/00005768-200101000-00021

- **Relevance:** A level-walking study, but it reports the **knee extensor angular impulse**, which is the same kind of time-integrated measure we compute.
- **Values (abstract):**
  - 13 adults, 3D inverse dynamics.
  - Knee extensor impulse fell by **7.3%** (no poles vs. selected poles) and by **10.4%** (no poles vs. poles back).
  - Vertical knee joint reaction force and average vertical ground reaction force also fell.
  - Walking speed, stride length and stance time all increased with poles.

**Jensen, S. B., Henriksen, M., Aaboe, J., Hansen, L., Simonsen, E. B., & Alkjær, T. (2011).** Is it possible to reduce the knee joint compression force during level walking with hiking poles? *Scandinavian Journal of Medicine & Science in Sports, 21*(6), e195–e200. https://doi.org/10.1111/j.1600-0838.2010.01241.x

- **Relevance:** A counterpoint for our discussion section. **Note that this is a level-walking study, not downhill.**
- **Values (abstract):**
  - 10 healthy subjects, with pole force measured directly.
  - Subjects could raise pole force to **2.4×** their normal pole force, but knee compression force did **not** fall.
  - The authors suggest poles may unload the knee on terrain (such as descent) or in patients.

**Hawke, A. L., & Jensen, R. L. (2020).** Are trekking poles helping or hindering your hiking experience? A review. *Wilderness & Environmental Medicine, 31*(4), 482–488. https://doi.org/10.1016/j.wem.2020.06.009

- **Relevance:** A narrative review for the introduction.
- **Conclusion (abstract):** Poles decrease lower-extremity loading and forces but increase cardiovascular demand. With heavy external loads, poles may reduce lower-limb muscle activity and improve balance.
- The review covers literature from 1980–2019.

## 2. Stair descent knee biomechanics

**Protopapadaki, A., Drechsler, W. I., Cramp, M. C., Coutts, F. J., & Scott, O. M. (2007).** Hip, knee, ankle kinematics and kinetics during stair ascent and descent in healthy young individuals. *Clinical Biomechanics, 22*(2), 203–210. https://doi.org/10.1016/j.clinbiomech.2006.09.010

- **Relevance:** Normative stair data for checking that our angles and moments are plausible, and step geometry to compare with our staircase.
- **Values (abstract):**
  - n = 33 (16 men, 17 women, aged 18–39).
  - Step rise 18 cm, tread 28.5 cm.
  - The knee moment was greater in ascent than in descent by a mean of 0.17 Nm/kg (SD 0.15).
  - The coefficient of variation of moments between repeat tests was 4.65–40.73%.
- Absolute peak descent knee moments are in the full text only. **VERIFY.**

**Riener, R., Rabuffetti, M., & Frigo, C. (2002).** Stair ascent and descent at different inclinations. *Gait & Posture, 15*(1), 32–44. https://doi.org/10.1016/S0966-6362(01)00162-X

- **Relevance:** Shows how staircase inclination affects joint moments and power. Needed if our staircase differs from lab norms.
- **Values (abstract):**
  - 10 subjects on staircases inclined at 24°, 30° and 42°, with 6-DOF force steps.
  - Joint angles and moments depended only weakly (but significantly) on inclination. Joint powers depended on it strongly.
  - The forefoot strikes first in both ascent and descent, which matters for our foot-contact detection.

## 3. Patellar tendon and quadriceps moment arm versus knee angle

**Krevolin, J. L., Pandy, M. G., & Pearce, J. C. (2004).** Moment arm of the patellar tendon in the human knee. *Journal of Biomechanics, 37*(5), 785–788. https://doi.org/10.1016/j.jbiomech.2003.09.010

- **Relevance:** The main source for the moment arm in quadriceps force = knee extensor moment / patellar tendon moment arm.
- **Values (abstract):**
  - Six cadaver knees, with the moment arm taken about the finite screw axis.
  - **Peak patellar tendon moment arm 4–6 cm, maximal near 45° of knee flexion.**
  - Near full extension, the moment arm is smaller than the perpendicular distance.
  - The moment arm stays roughly constant across individuals when normalized by femoral condyle width.

**Tsaopoulos, D. E., Baltzopoulos, V., Richards, P. J., & Maganaris, C. N. (2009).** A comparison of different two-dimensional approaches for the determination of the patellar tendon moment arm length. *European Journal of Applied Physiology, 105*(5), 809–814. https://doi.org/10.1007/s00421-008-0968-3

- **Relevance:** An in vivo 2D (sagittal X-ray) measurement, a good match for our 2D model. It also shows how much the value depends on the choice of joint center.
- **Values (abstract):**
  - 7 men, passive extension.
  - About the instant center of rotation or the posterior femoral condyle center, the moment arm **decreased from ~5.8–5.9 cm at full extension to ~4.8 cm at 90° flexion**.
  - About the tibiofemoral contact point, the curve rose and then fell, peaking at **~5 cm at 60°**.

**Tsaopoulos, D. E., Baltzopoulos, V., Richards, P. J., & Maganaris, C. N. (2007).** In vivo changes in the human patellar tendon moment arm length with different modes and intensities of muscle contraction. *Journal of Biomechanics, 40*(15), 3325–3332. https://doi.org/10.1016/j.jbiomech.2007.05.005

- **Relevance:** Passive or cadaver moment arms underestimate the loaded case, so our quadriceps force may be biased high. This belongs in the error discussion.
- **Values (abstract):**
  - The moment arm increased by 14–15% from rest to maximum voluntary contraction, or by 6–26% after correcting for the change in joint angle.
  - It increased by 3–15% during concentric and eccentric extension compared with passive extension.

**Tsaopoulos, D. E., Maganaris, C. N., & Baltzopoulos, V. (2007).** Can the patellar tendon moment arm be predicted from anthropometric measurements? *Journal of Biomechanics, 40*(3), 645–651. https://doi.org/10.1016/j.jbiomech.2006.01.022

- **Relevance:** Supports using a literature moment-arm curve rather than scaling it per subject by body size.
- **Values (abstract):**
  - 22 men, MRI.
  - Only knee circumference predicted the moment arm, and weakly (R² = 0.139).
  - The two joint-center definitions differed by 0.84–1.89 cm.

**Herzog, W., & Read, L. J. (1993).** Lines of action and moment arms of the major force-carrying structures crossing the human knee joint. *Journal of Anatomy, 182*(Pt 2), 213–230. PMCID: PMC1259832. No DOI found; the journal issue is in PubMed Central. https://pmc.ncbi.nlm.nih.gov/articles/PMC1259832/

- **Relevance:** Gives sagittal quadriceps moment arm as polynomial regression equations of knee angle, which suits code.
- **Numbers:** The abstract gives none. The coefficients and the range are in the scanned full text, which we could not extract. **VERIFY the coefficients and range before use.**

**Tsaopoulos, D. E., Baltzopoulos, V., & Maganaris, C. N. (2006).** Human patellar tendon moment arm length: Measurement considerations and clinical implications for joint loading assessment. *Clinical Biomechanics, 21*(7), 657–667. https://doi.org/10.1016/j.clinbiomech.2006.02.009

- **Relevance:** A review of methods (geometric, tendon excursion, direct load) for the methods section.

**Values for our model:** a patellar tendon moment arm of **about 4.8–6 cm** over 0–90° of flexion.

- In 2D in vivo data (Tsaopoulos 2009) it falls with flexion: ~5.9 cm at 0° and ~4.8 cm at 90°.
- In cadaver screw-axis data (Krevolin 2004) it peaks at 4–6 cm near 45°.
- A constant 5 cm is a defensible baseline.
- A sensitivity analysis of ±1 cm covers the reported spread.

## 4. Anthropometric segment parameters

**Winter, D. A. (2009).** *Biomechanics and motor control of human movement* (4th ed.). Wiley. https://doi.org/10.1002/9780470549148

- **Relevance:** Standard source for segment mass fractions, center-of-mass locations and radii of gyration (from Dempster's data), and for filtering practice.
- **Values:** Segment-table values from memory, all **VERIFY** against the book's anthropometric table: thigh 0.100 of body mass, leg 0.0465, foot 0.0145, upper arm 0.028, forearm 0.016, hand 0.006.

**de Leva, P. (1996).** Adjustments to Zatsiorsky-Seluyanov's segment inertia parameters. *Journal of Biomechanics, 29*(9), 1223–1230. https://doi.org/10.1016/0021-9290(95)00178-6

- **Relevance:** An alternative segment table with separate male and female values, referenced to joint centers. That makes it compatible with landmark-based joint centers like MediaPipe's.
- **Numbers:** The abstract gives none. **VERIFY the table.**

**Dempster, W. T. (1955).** *Space requirements of the seated operator: Geometrical, kinematic, and mechanical aspects of the body with special reference to the limbs.* Wright-Patterson Air Force Base, Ohio. https://doi.org/10.21236/AD0087892

- **Relevance:** The original cadaver data behind Winter's tables. Cite it when using Winter's values.
- WADC Technical Report number 55-159: **VERIFY.**

## 5. Filtering cutoffs

**Winter, D. A., Sidwall, H. G., & Hobson, D. A. (1974).** Measurement and reduction of noise in kinematics of locomotion. *Journal of Biomechanics, 7*(2), 157–159. https://doi.org/10.1016/0021-9290(74)90056-6

- **Relevance:** The origin of the common low-pass Butterworth cutoff of **6 Hz** for gait marker data. It was designed for 60 Hz TV-camera data and applied forward and backward with zero lag, giving an effective 4th-order filter.
- **Status:** PubMed has no abstract. We confirmed the 6 Hz value and the second-order, two-pass design only from secondary sources, not the original paper. **VERIFY.**
- **For our pipeline:** A zero-lag (`filtfilt`) Butterworth filter at about 6 Hz for landmark trajectories. Ideally, choose the cutoff by residual analysis (Winter 2009, chapter on signal processing; **VERIFY the chapter**), because MediaPipe noise is not marker noise.

## 6. Cumulative and per-unit-distance load

**Miller, R. H., Edwards, W. B., Brandon, S. C., Morton, A. M., & Deluzio, K. J. (2014).** Why don't most runners get knee osteoarthritis? A case for per-unit-distance loads. *Medicine & Science in Sports & Exercise, 46*(3), 572–579. https://doi.org/10.1249/MSS.0000000000000135

- **Relevance:** Justifies reporting load per unit distance or per step, not just the peak. Poles may change step count or length on the stairs.
- **Values (abstract):**
  - Peak load: 8.02 body weight (BW) running vs. 2.72 BW walking.
  - Per-unit-distance load: 0.80 vs. 0.75 BW/m, not significant.
  - Contact-force impulse: 1.30 vs. 1.04 BW·s ("body weight per second" in the abstract).

**Seedhom, B. B., & Wallbridge, N. C. (1985).** Walking activities and wear of prostheses. *Annals of the Rheumatic Diseases, 44*(12), 838–843. https://doi.org/10.1136/ard.44.12.838

- **Relevance:** Early cumulative-loading idea: daily step counts drive implant wear.
- **Values (abstract):** 243 individuals. Means were 9,537 steps per day for males and 9,839 for females, about 6.7 and 6.5 km per day.

**Thorp, L. E., Sumner, D. R., Block, J. A., Moisio, K. C., Shott, S., & Wimmer, M. A. (2006).** Knee joint loading differs in individuals with mild compared with moderate medial knee osteoarthritis. *Arthritis & Rheumatism, 54*(12), 3842–3849. https://doi.org/10.1002/art.22247

- **Relevance:** A precedent for using the **angular impulse** (the time integral of a knee moment) as a complement to the peak. We apply the same idea to the sagittal extensor moment.
- **Values (abstract):** n = 28, 66 and 23 across Kellgren/Lawrence grades 0–1, 2 and 3. Only the impulse, not the peak moment, separated grade 2 from grade 3.

## 7. Gait event detection from kinematics

**Zeni, J. A., Jr., Richards, J. G., & Higginson, J. S. (2008).** Two simple methods for determining gait events during treadmill and overground walking using kinematic data. *Gait & Posture, 27*(4), 710–714. https://doi.org/10.1016/j.gaitpost.2007.07.007

- **Relevance:** Detects heel strike and toe-off from the horizontal position or velocity of foot markers relative to the pelvis. This works with MediaPipe heel, foot and hip landmarks.
- **Values (abstract):**
  - 94% of treadmill events in healthy subjects fell within 1 frame (0.0167 s) of force-plate events.
  - 89% fell within 2 frames in impaired populations.
  - 98% of overground events fell within 2 frames.
- **Caveat:** Validated on level walking only. Stair descent with forefoot-first contact (Riener 2002) needs our own check.

## 8. Pose estimation and markerless pipelines

**Bazarevsky, V., Grishchenko, I., Raveendran, K., Zhu, T., Zhang, F., & Grundmann, M. (2020).** BlazePose: On-device real-time body pose tracking. *arXiv*. https://doi.org/10.48550/arXiv.2006.10204

- **Relevance:** The model behind MediaPipe Pose Landmarker.
- **Values (abstract):** 33 body keypoints for one person, over 30 fps on a Pixel 2. Presented at a CVPR 2020 workshop.

**Jiang, T., Lu, P., Zhang, L., Ma, N., Han, R., Lyu, C., Li, Y., & Chen, K. (2023).** RTMPose: Real-time multi-person pose estimation based on MMPose. *arXiv*. https://doi.org/10.48550/arXiv.2303.07399

- **Relevance:** The alternative pose backend used by Sports2D and Pose2Sim.

**Uhlrich, S. D., Falisse, A., Kidziński, Ł., Muccini, J., Ko, M., Chaudhari, A. S., Hicks, J. L., & Delp, S. L. (2023).** OpenCap: Human movement dynamics from smartphone videos. *PLOS Computational Biology, 19*(10), e1011462. https://doi.org/10.1371/journal.pcbi.1011462

- **Relevance:** Validation precedent for estimating joint moments and loads from smartphone video. It uses two or more phones, 3D, and OpenSim.
- **Values (abstract):** A 100-subject field study, done 25× faster than the lab-based approach at under 1% of the cost.
- Specific error values (for example, knee moment RMSE) are in the full text only. **VERIFY.**

**Seth, A., Hicks, J. L., Uchida, T. K., Habib, A., Dembia, C. L., Dunne, J. J., Ong, C. F., DeMers, M. S., Rajagopal, A., Millard, M., Hamner, S. R., Arnold, E. M., Yong, J. R., Lakshmikanth, S. K., Sherman, M. A., Ku, J. P., & Delp, S. L. (2018).** OpenSim: Simulating musculoskeletal dynamics and neuromuscular control to study human and animal movement. *PLOS Computational Biology, 14*(7), e1006223. https://doi.org/10.1371/journal.pcbi.1006223

- **Note:** The author list beyond the first four (taken from Crossref) is from memory. **VERIFY.**

**Pagnon, D., Domalain, M., & Reveret, L. (2022).** Pose2Sim: An open-source Python package for multiview markerless kinematics. *Journal of Open Source Software, 7*(77), 4362. https://doi.org/10.21105/joss.04362

**Pagnon, D., & Kim, H. (2024).** Sports2D: Compute 2D human pose and angles from a video or a webcam. *Journal of Open Source Software, 9*(101), 6849. https://doi.org/10.21105/joss.06849

## 9. Camera calibration (DLT)

**Abdel-Aziz, Y. I., & Karara, H. M. (2015).** Direct linear transformation from comparator coordinates into object space coordinates in close-range photogrammetry. *Photogrammetric Engineering & Remote Sensing, 81*(2), 103–107. https://doi.org/10.14358/PERS.81.2.103

- **Note:** Originally published in 1971 in the *Proceedings of the ASP/UI Symposium on Close-Range Photogrammetry*. The 1971 version has no DOI; its venue name is **VERIFY**.
- **Relevance:** The basis for 2D (planar) and 3D DLT scaling, which turns pixel coordinates into metres for our moment arms.

## 10. Video synchronization by audio

**Shrestha, P., Barbieri, M., & Weda, H. (2007).** Synchronization of multi-camera video recordings based on audio. In *Proceedings of the 15th ACM International Conference on Multimedia* (pp. 545–548). ACM. https://doi.org/10.1145/1291233.1291367

- **Relevance:** Precedent for aligning two cameras by audio. We use a simpler variant: cross-correlate or peak-pick a clap transient.
- **Notes:** Crossref spells the first author "Shrstha", which appears to be a metadata error. Accuracy numbers: **VERIFY in the full text.**

---

## Key numbers we use

| Quantity | Value | Source | Status |
|---|---|---|---|
| Patellar tendon moment arm | 4–6 cm peak, maximal near 45° flexion (cadaver) | Krevolin et al. 2004 | Verified (abstract) |
| Patellar tendon moment arm vs. angle | ~5.8–5.9 cm at 0° to ~4.8 cm at 90° (in vivo, 2D) | Tsaopoulos et al. 2009 | Verified (abstract) |
| Moment arm increase under contraction | +6–26% vs. rest | Tsaopoulos et al. 2007 | Verified (abstract) |
| Quadriceps moment arm regression | polynomial in knee angle | Herzog & Read 1993 | VERIFY coefficients |
| Pole effect, downhill (25° ramp) | −12–25% knee moment, ground reaction force and tibiofemoral forces | Schwameder et al. 1999 | Verified (abstract) |
| Pole effect, downhill with packs | Significant drop in sagittal joint moments at ankle, knee and hip; no % in abstract | Bohne & Abendroth-Smith 2007 | VERIFY % |
| Pole effect, level walking | −7.3% to −10.4% knee extensor impulse | Willson et al. 2001 | Verified (abstract) |
| Low-pass cutoff | 6 Hz, zero-lag Butterworth | Winter et al. 1974 | VERIFY (secondary only) |
| Gait event accuracy | 94% within 1 frame at 60 Hz (treadmill, healthy) | Zeni et al. 2008 | Verified (abstract) |
