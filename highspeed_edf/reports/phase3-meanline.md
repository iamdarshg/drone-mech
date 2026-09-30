> **OBSOLETE — SUPERSEDED.** See `../OBSOLETE.md` and `../design/PHASE15_DESIGN_SPEC.md`.
> This file describes a superseded configuration (90 mm geared FA4119, old mass
> basis, 75 cm2 frontal-area gate, CdA 0.0009 m2). Do NOT use it to size or build.
# Phase 3 meanline screening

**Evidence class:** workbench analytical meanline row matching. No native solver, CFD, GCP job, or physical measurement was used.

The 75 cm² projected-frontal-area checkpoint is recorded in requirements revision 2 and kept separate from CdA. The aerodynamic operation points below use CdA=0.00315 m² as a separate Phase 2 reference input.

## Three-rotor serial axial candidate, 3 km ISA

| Speed | Target work (kJ/kg) | Meanline work (kJ/kg) | Target PR | Meanline PR | Rotor RPM R1/R2/R3 | Rows passing custom screening | Max motor current at 44.4 V, no sag | Electrical estimate with assumed 95% gear (kW) |
|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 500 | 9.45 | 9.45 | 1.1004 | 1.1040 | 24250/27270/30300 | 3/6 | 46.4 A | 10.10 |
| 550 | 10.62 | 10.62 | 1.1124 | 1.1159 | 25250/28785/31815 | 3/6 | 57.4 A | 12.48 |
| 600 | 11.89 | 11.89 | 1.1254 | 1.1291 | 27270/30300/33330 | 3/6 | 68.8 A | 15.25 |
| 650 | 13.27 | 13.27 | 1.1394 | 1.1437 | 29290/32320/35350 | 3/6 | 82.3 A | 18.44 |
| 700 | 14.75 | 14.75 | 1.1544 | 1.1592 | 31310/34340/36360 | 3/6 | 94.4 A | 22.07 |

There are 15 row records failing at least one declared screening indicator or correlation-validity gate; in this candidate all 15 failures are stator Reynolds numbers below the declared 50,000 floor (range about 31,000–44,000). Rotor diffusion, incidence, relative-Mach and loading screens pass at the updated RPM schedule. See `phase3_meanline_rows.csv` for per-row detail. A screen failure is a rejection warning, not proof of physical failure; a pass is not validation.

The motor-current column divides each rotor's calculated electrical load by 44.4 V and assumes no pack sag. Compare it to the 55 A soft / 65 A initial hard / 75 A provisional per-motor limits; actual loaded current will be higher as voltage sags. The provisional 75 A limit has no established run duration.

At 600 km/h the highest stage current estimate already exceeds the 65 A initial hard limit; at 650/700 km/h the highest channels exceed the provisional 75 A limit even before battery sag. 700 km/h also asks about 22.1 kW bus input in this candidate, over the current 20.66 kW best-case provisional pack/current screen.

## Station continuity and total-pressure tracking

`phase3_station_audit.csv` records compressor-face plus each rotor/stator exit with Pt, Ps, Tt, Ts, Mach, V, density, mdot, annulus area, and swirl. The candidate holds 32 mm hub / 80 mm casing, solving the required axial velocity from continuity at each face.

## Stator Reynolds / variable core-annulus sensitivity

The uniform 80 mm annulus puts all stators below the workbench's 50k Reynolds screening floor. A lossless continuity sensitivity sizes a smaller core annulus at each speed to bring the 5 mm S1 stator to Re≈50k:

| Speed | Uniform S1 Re | Core area for Re≈50k (m²/duct) | Equivalent core outer diameter, 32 mm hub | Core area / fan annulus |
|---:|---:|---:|---:|---:|
| 500 km/h | 31126 | 0.002628 | 66.1 mm | 0.623 |
| 550 km/h | 34164 | 0.002885 | 68.5 mm | 0.683 |
| 600 km/h | 37275 | 0.003148 | 70.9 mm | 0.746 |
| 650 km/h | 40334 | 0.003406 | 73.2 mm | 0.807 |
| 700 km/h | 43483 | 0.003672 | 75.5 mm | 0.870 |

A fixed annulus at the 500 km/h minimum area (0.00263 m²) has no subsonic continuity solution at 550–700 km/h for the captured mass flow. The first architecture-sensitive path to investigate is therefore a mechanically scheduled core annulus/splitter area that opens with speed (about 0.00263→0.00367 m² per duct from 500→700 in this idealized estimate), corresponding to roughly 66.1→75.5 mm outer core diameter with the current 32 mm hub, while preserving the 80 mm fan envelope. This is a sizing target, not a validated passive mechanism. Core-radius contraction also raises the required R2/R3 RPM/gear ratios; the per-speed schedule and fixed-area flow-capacity sensitivity are saved in `phase3_core_area_schedule_sensitivity.csv` and `phase3_core_contraction_sensitivity.csv`.

## Design interpretation

- The work split is assigned proportional to each rotor's U² to target approximately equal loading coefficient, with R1 slower and the rear rotors faster.
- Stage 3 (S3) targets zero exit swirl; S1/S2 are also initially deswirled as a conservative first baseline. Their residual-swirl schedule remains an optimization variable.
- Each motor is independently scheduled through its fixed stage gearbox. The fixed 95% gear efficiency is assumed, not measured.
- The current meanline baseline is one common stream through three rotors and three stators. Core-annulus contraction is a sensitivity only; it has not yet been re-solved through all six rows. Bypass remains unmatched in this meanline chain.
- Rotor chords are 16/15/14 mm and stator chords are 5 mm, within revision-2 geometric limits. Blade counts are 13/12/11 rotors and 23/21/19 stators.

## Phase 3 gate

Do not accept the candidate unless its rows meet user screening targets (especially Reynolds validity, diffusion, de Haller, relative Mach, incidence, and loading) across the speed range, and electrical channels remain within current limits. The workbench solver is meanline row matching, not S1/S2 or CFD; spanwise twist/radial equilibrium and true annulus blockage are absent. Next iteration should implement the speed-dependent core annulus profile in the application model, re-solve all rows, and co-optimize rotor work/RPM and gear ratios while preserving the 75 cm² projected-area checkpoint.

