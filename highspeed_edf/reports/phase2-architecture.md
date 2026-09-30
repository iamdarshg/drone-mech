> **OBSOLETE — SUPERSEDED.** See `../OBSOLETE.md` and `../design/PHASE15_DESIGN_SPEC.md`.
> This file describes a superseded configuration (90 mm geared FA4119, old mass
> basis, 75 cm2 frontal-area gate, CdA 0.0009 m2). Do NOT use it to size or build.
# Phase 2 architecture screening

**Evidence class:** reduced-order analytical screening. No native solver or GCP job was run.

## Requirement checkpoint

Active requirements revision 2 records projected frontal area ≤75 cm², lower preferred. This is distinct from the CdA values used as propulsion operating points; the frontal-area ceiling does not imply CdA without a geometry-specific drag coefficient and reference convention.

## VBR comparison at 3 km ISA, CdA=0.00315 m²

| Speed | Serial three-row electric input | Best VBR input | Best bypass fraction | Fan PR | Core PR | Rotor speed at ψ=0.5 |
|---:|---:|---:|---:|---:|---:|---:|
| 100 km/h | 0.99 kW | 0.66 kW | 0.50 | 1.000 | 1.067 | 15429 rpm |
| 200 km/h | 2.02 kW | 2.02 kW | 0.00 | 1.000 | 1.051 | 19153 rpm |
| 400 km/h | 6.36 kW | 6.36 kW | 0.00 | 1.000 | 1.079 | 24013 rpm |
| 500 km/h | 10.10 kW | 10.10 kW | 0.00 | 1.000 | 1.100 | 27067 rpm |
| 550 km/h | 12.48 kW | 12.48 kW | 0.00 | 1.000 | 1.112 | 28691 rpm |
| 600 km/h | 15.25 kW | 15.25 kW | 0.00 | 1.000 | 1.125 | 30363 rpm |
| 650 km/h | 18.44 kW | 18.44 kW | 0.00 | 1.000 | 1.139 | 32075 rpm |
| 700 km/h | 22.07 kW | 22.07 kW | 0.00 | 1.000 | 1.154 | 33820 rpm |

Bypass fraction is defined as bypass mass flow / total captured mass flow. The two exits are modeled as separate, ideally expanded nozzles. The grid minimizes electrical input while meeting the momentum-thrust target, subject to assumed minimum core flow and core pressure rise so the core motors are not numerically unloaded. It does not model mixer/nozzle maps, static capture, flow separation, or actual variable-nozzle kinematics. Interpret the optimizer's bypass schedule as a hypothesis for Phase 3, not a selected hardware schedule. Static T/W remains the Phase-1 actuator-disk bound and is not improved by this split model.

## Fixed overdrive and stage layouts

For the 3-rotor equal-work screen, `phase2_fixed_gear_screen.csv` gives rotor RPM and required gear ratio at the motor's 13,500 rpm initial hard limit. A fixed ratio transmits the independent motor RPM schedule; it does not add shaft power. A 95% gear efficiency is an explicit screening assumption. Counter-rotating fan pair and a fourth tandem stage remain candidates but are not aerodynamically distinguished by this reduced cycle model.

`phase2_stage_count_screen.csv` divides the same total PR/work over one to four rotor rows. With stage efficiency held equal, total cycle power is identical by construction; the result is a loading/rotor-speed trade only. For the 700 km/h point, the 3-row option is the natural one-motor-per-rotor mapping; 2-stage/3-motor contra-rotation and a 4th tandem stage need mechanical closure before a fair comparison.

## Candidate disposition

- **A — serial three-row:** baseline, no bypass branch; easiest baseline to compare/bench.
- **B — fan + two core rows + VBR:** retain as a low-speed-control/operating-range candidate, not as a proven efficiency winner. In the present sweep the high-speed optimizer closes the bypass branch (β=0) at 600–700 km/h; at 500 km/h its gain is negligible. The low-speed results are not a static-thrust validation. Do not add the mechanical bypass device until actual component maps show worthwhile low-speed authority or drag benefit.
- **C — contra-rotating fan pair + core:** retained for a later meanline/rotordynamics comparison; zero-D power alone cannot credit swirl recovery.
- **D — four pressure-adding rows / three motors:** no extra stage accepted yet; motor-to-tandem shaft allocation and packaging must close first.

No architecture is declared validated or converged. The 75 cm² projected frontal checkpoint is carried forward; actual aircraft geometry and `CdA(V)` still need VLM/VSPAERO and installed-flow validation.

