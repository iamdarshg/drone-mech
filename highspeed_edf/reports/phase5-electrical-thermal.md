> **OBSOLETE — SUPERSEDED.** See `../OBSOLETE.md` and `../design/PHASE15_DESIGN_SPEC.md`.
> This file describes a superseded configuration (90 mm geared FA4119, old mass
> basis, 75 cm2 frontal-area gate, CdA 0.0009 m2). Do NOT use it to size or build.
# Phase 5 battery, motor, ESC and thermal screen

**Evidence:** local PyBaMM 26.8.0.0 Thevenin-model simulations with application parameter overrides, plus the workbench ThermalNetwork. No GCP, native EM or Elmer job was run. OCV, pack R0/R1/thermal mass, FA4119 Kt/efficiency, gearbox and ESC loss assumptions are explicitly analyst sensitivities—not measured Turnigy/FA4119 maps.

## Phase-3 load -> electrical/pack envelope at 3 km ISA

| Speed | System bus power | Pack current at initial OCV, 10 mΩ | Loaded voltage | Ohmic pack heat | C-rate | 450 A (75 A/channel) cap? |
|---:|---:|---:|---:|---:|---:|---|
| 500 km/h | 10.10 kW | 212 A | 47.7 V | 0.45 kW | 42.4C | yes |
| 600 km/h | 15.25 kW | 328 A | 46.5 V | 1.07 kW | 65.6C | yes |
| 650 km/h | 18.44 kW | 403 A | 45.8 V | 1.62 kW | 80.6C | yes |
| 700 km/h | 22.07 kW | 492 A | 44.9 V | 2.42 kW | 98.4C | NO |

At 700 km/h the selected reference point asks for more than the current provisional six-channel battery-current ceiling even at the optimistic 10 mΩ pack assumption. At higher assumed R0 values, the constant-power source equation may have no solution or demands >100C; see `phase5_pack_power_envelope.csv`.

## Stage-specific FA4119/ESC current screen

| Speed | Max battery current/channel at 44.4 V, no sag | Max Kt-derived torque-current estimate | Max per-channel bus power |
|---:|---:|---:|---:|
| 500 km/h | 46.4 A | 62.7 A | 2.06 kW |
| 600 km/h | 68.8 A | 84.5 A | 3.05 kW |
| 650 km/h | 82.3 A | 95.3 A | 3.65 kW |
| 700 km/h | 94.4 A | 106.2 A | 4.19 kW |

The Kt-derived current is a convention-sensitive ideal estimate from 350 Kv, not an independently measured FOC phase current. The six-channel drone-arm hardware contract is 60 A RMS phase continuous / 90 A RMS phase burst; the FA4119 decision record separately gives 55 A soft battery-current rollback, 60–65 A initial hard battery current, and 70–75 A provisional short current with no validated duration. Do not compare battery amps and phase RMS amps as if they were the same limit.

The FA4119 published 3.47 kW / 74 A / 11,256 rpm result is for an HQ 13x9 prop; it is a comparison point, not a qualified EDF continuous rating. Phase-3 channel loads at high speed approach/exceed this point and exceed the provisional current targets.

## Custom-parameter PyBaMM discharge

The Thevenin model is configured as one equivalent 12S pack with 5 Ah capacity, a generic analyst OCV curve, pack-level R0=10/20/30 mΩ, assumed R1=20% of R0 with 5 s time constant, and initial SOC=95%. It simulates fixed-power bursts for 600/650/700 km/h over 5/10/20/30 s. These results are useful sensitivity data, not a Turnigy-identified cell model.

| Speed | R0 (mΩ) | Requested / solved | End pack voltage | End SOC | Peak pack current | End pack temp | Model status |
|---:|---:|---:|---:|---:|---:|---:|---|
| 700 | 10 | 10 / 10.0 s | 40.3 V | 0.660 | 548 A | 77.7 °C | completed |
| 700 | 10 | 30 / 18.2 s | 38.1 V | 0.403 | 579 A | 109.6 °C | voltage_cutoff_before_requested_duration |
| 700 | 20 | 10 / 0.0 s | 38.3 V | 0.950 | 577 A | 45.0 °C | voltage_cutoff_before_requested_duration |
| 700 | 20 | 30 / 0.0 s | 38.3 V | 0.950 | 577 A | 45.0 °C | voltage_cutoff_before_requested_duration |
| 700 | 30 | 10 s | — | — | — | — | failed_or_infeasible |
| 700 | 30 | 30 s | — | — | — | — | failed_or_infeasible |

## Motor/ESC/gearbox heat sensitivity

Motor, ESC and gearbox steady temperatures are computed with the workbench thermal RC network under assumed component-to-air thermal resistances. Heat totals count both mirrored ducts while the reported temperatures are representative per-channel nodes. The workbench solver's strict convergence flag is false for these cases, although its energy residual is about 2.4e-5 W; treat temperatures as indicative screening estimates, not certified equilibria. See `phase5_thermal_steady_bounds.csv`; these are not a substitute for Elmer with application geometry and measured convection/contact data.

## Phase 5 disposition

- **Pack-limited:** the 12S 5 Ah series pair has nominal energy 222 Wh; at 700 km/h the requested electrical power is not achievable under the six-channel 75 A provisional current cap for the tested pack-R0 envelope. Even under the 100C label, duration and voltage sag are not validated.
- **Motor/ESC-limited:** FA4119 shaft/current losses and Rev-B phase current do not close at the current high-speed load estimate. The selected motor's actual resistance, inductance, Kv, phase-current convention, thermal resistance and efficiency map require first-article dyno data.
- **Thermal:** battery peak heat and motor/ESC/gearbox temperature are highly sensitive to unmeasured pack R0, thermal capacity and cooling resistance. Passive duct-air cooling/cooling drag are not yet coupled.
- **GCP spend:** $0.00 for this pass. A GCP PyBaMM job would not improve the answer without a Turnigy OCV/DCIR/thermal data set. An Elmer job is not justified before motor/ESC/battery CAD and boundary conditions exist.

Requested workbench capability, for owner review: allow a versioned custom PyBaMM Thevenin parameter set / inline parameter payload and lift the generic participant's 100 A discharge-current limit for pack-level high-C discharge studies, with tests and explicit parameter provenance. The current application-side override is retained here and not added to the shared repository.

PyBaMM full-duration runs: 10/36; 18 ended at voltage cutoff before requested duration; infeasible/solver failures and their errors are preserved in `phase5_pybamm_runs.csv`.

