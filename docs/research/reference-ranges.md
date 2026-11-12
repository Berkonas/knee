# Reference ranges and change interpretation

This note collects published values that give context to the app's results. It covers
stair descent with and without trekking poles, analysed with 2D video and a quasi-static
knee moment model. Compiled 2026-11-11.

**Status labels.** *Verified* means the number was read from the abstract, the full text,
or a table in a cited review during this search. *VERIFY* means a full-text check is
still needed: the number came from a secondary source or search snippet, or was not found
at all. No number in this note is estimated or made up. Where the note converts units, it
says so.

**Important caveats**
- Stair values depend strongly on riser and tread size, speed, and step-over versus
  step-by-step pattern. They also depend on lab method: 3D markers and force plates versus
  our 2D sagittal video with a quasi-static model. Our 2D quasi-static moments are not
  directly comparable with 3D inverse-dynamics moments. Use them only as orders of
  magnitude.
- These are context references, not clinical good/bad thresholds (see A.10).

---

## Part A: Reference values for healthy adults

### A.1 Peak knee flexion and knee ROM in stance (stair descent)

| Study (as tabulated) | n | Riser × tread (cm) | Peak flex (°) | Knee ROM (°) | Status |
|---|---|---|---|---|---|
| Riener et al. 2002 | 10 | 13.8×31 / 17×29 / 22.5×25 | 89 / 93 / 102 | 76 / 78 / 89 | verified (via review) |
| McFadyen & Winter 1988 | 3 | 22×28 | 105 | 86 | verified (via review) |
| Protopapadaki et al. 2007 | 33 | 18×28.5 | 91 | 90 | verified (via review) |
| Lewis et al. 2015, self-selected speed | 30 | not recorded here | 82.56 ± 6.58 | n/r | verified (full text) |
| Lewis et al. 2015, fast / slow | 30 | | 81.97 ± 6.10 / 83.11 ± 6.35 | n/r | verified |

- The review is Zhang et al. 2020, *Appl Bionics Biomech*, doi:10.1155/2020/7451683, Tables 7–9. It
  gives means only, with no SDs.
- The table's "ROM" values may cover the whole gait cycle, not stance only. VERIFY.
- Lewis J, Freisinger G, Pan X, et al. 2015, *J Electromyogr Kinesiol* 25(6):982–989, PMC4658237.
  n=30 healthy adults (15 M, 15 F), aged 27.5 ± 10.7 y. Values are from Table 2.
- The Protopapadaki 2007 abstract (*Clin Biomech* 22:203–210; n=33, 16 M / 17 F, aged 18–39)
  reports only between-task differences. Knee angle was 3.39° (SD 7.20) greater in ascent.

### A.2 Peak knee extensor moment

| Condition | Value | Source | Status |
|---|---|---|---|
| Stair descent, self-selected speed | 6.73 ± 1.28 %BW·H (≈1.19 ± 0.23 N·m/kg, converted†) | Lewis et al. 2015, n=30 | verified (conversion is ours) |
| Stair descent, fast / slow speed | 7.53 ± 1.92 / 7.26 ± 1.50 %BW·H | Lewis et al. 2015 | verified |
| Stair descent, second (late-stance) extensor peak | 1.25 / 1.35 / 1.47 N·m/kg (low / mid / steep stair) | Riener 2002, via Zhang 2020 Table 8 | verified (via review) |
| Stair descent, second extensor peak | 1.62 N·m/kg (n=3) | McFadyen & Winter 1988, via Zhang 2020 | verified (via review) |
| Stair descent, peaks from other studies | 1.01–1.11 N·m/kg | Musselman, Law, and Zhang, via Zhang 2020 | verified (via review) |
| Level walking, early stance, 1.25 m/s | 0.57 (SE 0.10) N·m/kg | Lerner et al. 2014, *J Appl Biomech* 30(2):197–205, PMC4423394 | verified (values are mean (SE); n VERIFY) |
| Level walking, 0.75 / 1.50 m/s | 0.32 / 0.77 N·m/kg | Lerner et al. 2014 | verified |

† Our conversion: %BW·H × g × height/100, using the cohort's mean height of 1.80 m. It is approximate.

- Zhang 2020 lists Protopapadaki's descent peaks as only 0.365 N·m/kg. That is far below
  every other study, so it may be a transcription or sign-convention issue. VERIFY against
  the original before using it.
- Reeves et al. 2008 (*J Electromyogr Kinesiol* 18(2):218–227) found that young adults used
  about **30%** of their maximal knee extensor capacity during descent, and older adults about
  **42%**. Their absolute moments were similar (verified, abstract).

### A.3 Peak hip flexion and peak ankle dorsiflexion (stair descent)

- **Hip flexion in stance.** Lewis 2015: 21.15 ± 7.74° at self-selected speed, 22.9 ± 6.79°
  fast, 23.08 ± 7.39° slow (verified).
- **Ankle dorsiflexion.** Lewis 2015: 30.64 ± 7.31° at self-selected speed, 31.06 ± 6.72°
  fast, 29.92 ± 7.13° slow (verified).
- **Protopapadaki 2007.** Dorsiflexion was 9.90° (SD 3.80) greater in descent than in ascent.
  Hip angle was 28.10° (SD 4.08) greater in ascent (verified, abstract; differences only).

### A.4 Trunk forward lean

- **Breloff & Chou 2017**, *Biomed Eng Appl Basis Commun* 29(4); n=34 healthy adults aged 20–59.
  - Trunk flexion **ROM** in stair descent was 6.71 ± 1.14°, against 10.58 ± 3.05° in level
    walking (verified, full text).
  - This is a multi-segment trunk ROM, not absolute forward lean from vertical. Peak angles
    are given only in a figure.
- **Krebs et al. 1992** (as cited by others) reported peak trunk flexion in ascent of about
  twice the descent value (VERIFY).
- **Absolute trunk lean in stair descent: no verified healthy-adult mean ± SD was found.**
  VERIFY. Our app's 2D trunk-from-vertical angle has no published band yet.

### A.5 Quadriceps, patellar tendon and patellofemoral (PF) force

- **Costigan et al. 2002**, *Gait Posture* 16:31–37; n=35, stair **ascent**, verified (abstract).
  - Peak tibiofemoral (distal–proximal) contact force was about 3× BW on average, up to 6× BW.
  - Peak PF contact force was about 8× higher than in level walking.
  - Peak knee flexion moment was 1.16 N·m/kg.
- **Brechter & Powers 2002**, *Gait Posture*; 10 people with PF pain and 10 controls,
  ascent and descent.
  - PF stress did not differ between groups.
  - The PF pain group had lower PF reaction force and lower extensor moment, in ascent.
  - **The abstract gives no ×BW values.** VERIFY in the full text.
- **Stair-descent PF or quadriceps force in ×BW: no verified number was found.** VERIFY.
  Candidate sources to check: Brechter & Powers 2002 full text, and Schwameder 1999 for ramps.

### A.6 Cadence and stance timing (stair descent)

- Riener 2002 found that temporal parameters did not change significantly with stair
  inclination. The abstract gives no values (VERIFY).
- One search snippet reported a self-selected descent cadence of 117.4 (4.2) steps/min in
  young adults. **The source paper could not be identified. VERIFY; do not cite yet.**
- **No verified healthy-adult stance duration (s) for stair descent was found.** VERIFY.

### A.7 Knee power absorption and negative work (stair descent)

- **Peak knee power absorption, late stance (Zhang 2020, Table 9).** Verified (via review).
  - Riener 2002: −3.79, −4.14 and −4.84 W/kg (low, mid and steep stair).
  - McFadyen & Winter 1988: −5.49 W/kg.
  - Musselman: −2.08 W/kg.
- **Knee negative work (J/kg) in descent: no verified value was found.** VERIFY.
  McFadyen & Winter 1988 (doi:10.1016/0021-9290(88)90282-5) is the classic source, and
  describes descent as mainly energy-absorbing.

### A.8 Trekking pole forces

- **Bohne, Dixon & Abendroth, ISBS 2010.** Downhill walking with instrumented poles, n=27
  (14 M, 13 F). Verified (abstract).
  - Combined pole force was **0.61 N/kg** in men and **0.48 N/kg** in women. That is about
    6.2% and 4.9% BW (our conversion), or about 43 N and 34 N for a 70 kg person.
  - Whether "combined" means peak or mean, and per plant or both poles, is VERIFY.
  - The slope is not stated in the abstract.
- **Jensen BR et al., ISB 2009.** Nordic walking on the level, n=9 women. Mean pole force
  was about 3% BW (verified, snippet only).
- **Jensen SB et al. 2011**, *Scand J Med Sci Sports* 21(6):e195–e200; n=10, level walking.
  - When asked to push harder, subjects raised pole force to 2.4× their normal pole force.
  - Knee compression force did **not** fall (verified, abstract).
- **Peak axial force per plant in newtons for downhill hiking: not verified.** VERIFY.
  Check the full texts of Schwameder 1999 and Bohne & Abendroth-Smith 2007.
- **Elbow and shoulder moments from pole use: none found.** VERIFY.

### A.9 Effect of poles on knee loading

| Study | Task | Effect | Status |
|---|---|---|---|
| Schwameder et al. 1999, *J Sports Sci* 17(12):969–978; n=8 M | 25° downhill ramp | GRF, knee moment, and tibiofemoral compressive and shear forces fell **12–25%**. PF force and quadriceps force fell, but not significantly. Attributed to pole force plus more forward trunk lean. | verified (abstract) |
| Willson et al. 2001, *Med Sci Sports Exerc* 33(1):142–147; n=13 | Level walking | Knee extensor impulse fell **7.3%** (selected poles) and **10.4%** (poles back). Vertical GRF and vertical knee joint reaction force fell. Stance time rose. | verified (abstract) |
| Bohne & Abendroth-Smith 2007, *MSSE* 39:177–183, doi:10.1249/01.mss.0000240328.31276.fc; n=15 M | 36° ramp, 0–30% BW pack | Poles reduced modelled ankle and knee loads under every load condition. % values VERIFY. | partly verified (secondary summary) |
| Jensen SB et al. 2011 | Level walking | No reduction in knee compression force | verified (abstract) |

Schwameder's trunk-lean finding matters for our model. Pole use changes trunk posture, so
trunk lean is a confounder of the knee moment, and the app should report it next to the
knee results.

### A.10 Summary table

| Metric | Typical healthy value (stair descent unless noted) | Unit | Source(s) | Status |
|---|---|---|---|---|
| Peak knee flexion, stance | 82.6 ± 6.6 (one cohort); 89–105 (study means) | ° | Lewis 2015; Zhang 2020 review | verified |
| Knee ROM | 76–90 (study means) | ° | Zhang 2020 review | verified (stance vs cycle VERIFY) |
| Peak knee extensor moment | ≈1.0–1.6 (study means); 6.73 ± 1.28 %BW·H | N·m/kg | Zhang 2020; Lewis 2015 | verified |
| Same, level walking | 0.57 (1.25 m/s) | N·m/kg | Lerner 2014 | verified |
| Peak hip flexion, stance | 21.2 ± 7.7 | ° | Lewis 2015 | verified |
| Peak ankle dorsiflexion | 30.6 ± 7.3 | ° | Lewis 2015 | verified |
| Trunk flexion ROM | 6.7 ± 1.1 | ° | Breloff & Chou 2017 | verified (ROM, not lean) |
| Absolute trunk lean | not found | ° | none | VERIFY |
| PF or quadriceps force | not found for descent (ascent tibiofemoral ≈3× BW) | ×BW | Costigan 2002 | VERIFY |
| Cadence and stance time | not found | steps/min, s | none | VERIFY |
| Peak knee power absorption | −2.1 to −5.5 | W/kg | Zhang 2020 review | verified |
| Knee negative work | not found | J/kg | none | VERIFY |
| Pole force (downhill) | 0.48–0.61 (≈5–6% BW) | N/kg | Bohne et al. 2010 | verified (definition VERIFY) |
| Pole effect on knee load | −12 to −25% (downhill); −7 to −10% extensor impulse (level) | % | Schwameder 1999; Willson 2001 | verified |

**How to define bands defensibly**
- Use one cohort with reported mean ± SD and a matching task: Lewis 2015 for angles and
  extensor moment.
  - "Below typical": below mean − 1 SD.
  - "Typical": within mean ± 1 SD.
  - "Above typical": above mean + 1 SD.
- Where only study means exist (the Zhang review), show the min–max range of those means as
  a "reported range". Do not build an SD band from them.
- Label every band with its cohort, n, stair size, and speed, and note the method mismatch
  (3D lab against our 2D quasi-static model).
- Say plainly that being outside a band is **not** a sign of injury or poor technique. Bands
  are context, not clinical cut-offs. No validated clinical thresholds exist for these
  measures in stair descent.

---

## Part B: Is a within-subject change meaningful?

Recommended layered approach for a small repeated-measures pilot (poles versus no poles,
k trials per condition):

1. **Measurement noise (typical error, TE).** For each subject, metric, and condition, take
   the SD across trials. Pool it across subjects as the RMS of the within-subject SDs.
   - Hopkins 2000, "Measures of reliability in sports medicine and science", *Sports Med*
     30(1):1–15. It defines typical error as within-subject SD; with two trials, TE = SD of
     the differences / √2.
   - The SE of a condition mean is TE/√k, so the SE of a between-condition difference is
     TE·√(2/k). This is standard algebra.
2. **Minimal detectable change (MDC95) = 1.96 × √2 × SEM**, where SEM is the TE of a single
   trial. Divide by √k when comparing means of k trials.
   - Weir 2005, *J Strength Cond Res* 19(1):231–240, doi:10.1519/15184.1 (citation verified;
     page of the formula VERIFY).
   - A change smaller than the MDC is not distinguishable from noise for that person.
3. **Smallest worthwhile change (SWC) = 0.2 × between-subject SD.**
   - Hopkins 2004, "How to interpret changes in an athletic performance test", *Sportscience*
     8:1–7 (verified: 0.2 of the between-athlete SD as a default).
   - Take the between-subject SD from the cited reference cohort, for example 0.2 × 1.28 %BW·H
     ≈ 0.26 %BW·H for descent extensor moment, or from our own sample if n ≥ about 10.
4. **Decision rule** (state it in the app and report):
   - The change is "likely real and worthwhile" only if |Δ| > MDC **and** |Δ| > SWC.
   - If |Δ| > SWC but < MDC, it is "possibly worthwhile, but within noise".
   - Otherwise it is "trivial or undetectable".
   - Also report the group mean Δ with a 95% CI, from a paired t or bootstrap.
   - Report the paired effect size d_z = mean Δ / SD(Δ), which Cohen's small/medium/large
     labels describe only loosely.
5. **Caution.** Magnitude-based inference (Batterham & Hopkins 2006, VERIFY) is debated and
   should not be used as a stand-alone inference. Use the thresholds above descriptively
   alongside CIs. With n of about 5, report individual changes against MDC and SWC rather
   than group p-values.

---

## Part C: Open-source code for knee loading, muscle forces and fatigue

GitHub metadata was checked with `gh api` on 2026-11-11.

| Repo | What it does | License | Maintained | Works from 2D video only? | Python desktop app? |
|---|---|---|---|---|---|
| opencap-org/opencap-processing | OpenCap post-processing: kinematics plus muscle-driven tracking simulations (CasADi/OpenSimAD) for joint moments and muscle forces. Paper: Uhlrich et al. 2023, *PLoS Comput Biol*, doi:10.1371/journal.pcbi.1011462 | Apache-2.0 | Active (pushed 2026-09) | No. Needs OpenCap 3D kinematics from ≥2 synced phones. Our single sagittal 2D video does not fit. | Heavy: conda OpenSim; the muscle-driven workflow is x86_64 only on macOS |
| utahmobl/opencap-processing-grf | Machine learning plus simulation to improve GRF, moment and joint contact force estimates (Miller et al., bioRxiv 2025) | Apache-2.0 | Active (2026-06) | No (OpenCap input) | Heavy |
| utahmobl/opencap-monocular | 3D kinematics and dynamics from one smartphone video | **PolyForm Noncommercial 1.0.0** | Active | Closest fit, but it needs its own capture pipeline | Licence allows class use only; heavy |
| opensim-org/opensim-core (+Moco) | Musculoskeletal modelling: inverse dynamics, static optimisation, JointReaction, Moco optimal control. The separate Moco repo is **archived** (Moco is now in opensim-core). | Apache-2.0 | Active | No. Needs 3D kinematics and a scaled model. | Python bindings via conda; large dependency |
| opensim-jam-org/jam-resources | COMAK knee contact mechanics (OpenSim-JAM) | Apache-2.0 | Low (2025-01) | No | Hard |
| pyomeca/bioptim | Optimal control on biorbd models. Includes `XiaFatigue`, `XiaTauFatigue` and `MichaudFatigue` (3- and 4-compartment) dynamics. | MIT | Active (2026-11) | No measurement-driven estimator. Fatigue is a state inside an optimal control problem. | Possible (pip/conda, CasADi), but it is research-grade |
| pyomeca/biorbd | Rigid-body dynamics and inverse dynamics on custom models | MIT | Active | Could take 2D sagittal joint angles in a planar model | Yes, but overkill for a quasi-static model |
| s2mLab/dumbbell_lifting | Paper code linking Xia fatigue to an OCP (arm lifting) | MIT | Stale (2024-06) | No | No |
| ClaudioUrrea/3CC-Fatigue-Shield | Python 3CC fatigue model for a human-robot collaboration paper | MIT | New (2026-10), 0 stars | Not a biomechanics pipeline | Small, but unvetted |
| JimPotvin/Potvin_Fuglevand_Muscle_Fatigue_Model | Motor-unit fatigue model | No licence (all rights reserved) | Stale (2018), MATLAB | No | No (licence) |
| pyCGM2/pyCGM2 | Conventional Gait Model (3D markers from c3d) plus inverse dynamics | CC-BY-SA-4.0 | Active | No (3D markers) | Licence is share-alike |
| kineticstoolkit/kineticstoolkit | General Python biomechanics library: TimeSeries, filters, cycles, C3D and 3D geometry | Apache-2.0 | Active | Usable for filtering and cycle tools only | Yes, lightweight |
| perfanalytics/pose2sim | Multi-camera markerless pipeline to OpenSim | BSD-3-Clause | Active | Needs ≥2 calibrated cameras | Moderate |

**Three-compartment (3CC) fatigue model**
- **Source papers.**
  - Xia & Frey-Law 2008, *J Biomech* 41:3046–3052 (VERIFY pages).
  - Frey-Law, Looft & Heitsman 2012, *J Biomech* 45(10):1803–1808,
    doi:10.1016/j.jbiomech.2012.04.018, PMC3397684.
- **Equations.** The compartments are resting, active and fatigued (MR, MA, MF):
  - dMR/dt = −C + R·MF
  - dMA/dt = C − F·MA
  - dMF/dt = F·MA − R·MF
  - C is a controller that drives MA towards the target load TL (% of maximum), with L = 10.
- **Knee parameters.** F = 0.01500 and R = 0.00149 (PMC Table; VERIFY against the PDF).
- **Validated for sustained isometric contractions only.** The authors say it "may or may
  not" transfer to dynamic or intermittent tasks.

**Recommendation**
- **Do not add a fatigue estimate.** The 3CC input is load as % of each person's *maximal*
  joint torque (MVC). We have no MVC, no EMG, and no validation for dynamic eccentric stair
  descent. Running the model would give us numbers we cannot check, and the parameters were
  fitted to isometric endurance times. If anything is reported, call it a "cumulative knee
  extensor load index": the sum or time-integral of knee moment per step (impulse), clearly
  labelled. It is not fatigue.
- **Knee loading.** Keep our quasi-static sagittal model. Optionally add a documented
  patellofemoral or quadriceps force estimate (moment / patellar-tendon moment arm), with
  literature moment arms, and flag it as a model estimate.
  - None of the muscle-driven tools above accept single-view 2D input. OpenCap needs ≥2
    phones and is not practical to embed in a PySide6 app.
  - opencap-monocular has a noncommercial licence and its own capture pipeline.
- **Libraries worth using.** kineticstoolkit (Apache-2.0) is safe to add for filtering and
  cycle segmentation. biorbd (MIT) would be the choice if we later move from quasi-static to
  a planar inverse-dynamics model with force plate data.

---

## Sources consulted

- Zhang et al. 2020 review: https://pmc.ncbi.nlm.nih.gov/articles/PMC7160724/
- Lewis et al. 2015: https://pmc.ncbi.nlm.nih.gov/articles/PMC4658237
- Lerner et al. 2014: https://pmc.ncbi.nlm.nih.gov/articles/PMC4423394
- Protopapadaki 2007 abstract: https://manuscript.isc.ac/Inventory/10/486685.htm
- Riener 2002 abstract: https://search.isc.ac/inventory/10/487922.htm
- Costigan 2002 abstract: https://manuscript.isc.ac/Inventory/10/487958.htm
- Breloff & Chou 2017: https://stacks.cdc.gov/view/cdc/76289
- Reeves 2008: https://eprints.lancs.ac.uk/id/eprint/235936
- Schwameder 1999: https://pubmed.ncbi.nlm.nih.gov/10622357/
- Willson 2001: https://pubmed.ncbi.nlm.nih.gov/11194099/
- Bohne et al. 2010 (ISBS): https://ojs.ub.uni-konstanz.de/cpa/article/view/4575
- Jensen 2011: https://research.regionh.dk/da/publications/is-it-possible-to-reduce-the-knee-joint-compression-force-during-/
- Frey-Law 2012: https://pmc.ncbi.nlm.nih.gov/articles/PMC3397684
- Hopkins 2004: https://sportsci.org/jour/04/wghtests.htm
- Hopkins 2000 PDF: https://statistics.sportsci.org/resource/stats/Hopkins_SportsMed_rely_00.pdf
