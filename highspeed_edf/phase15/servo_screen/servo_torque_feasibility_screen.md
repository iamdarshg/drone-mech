# Phase-15 servo torque feasibility screen

**Result: servo adequacy is undetermined.** The source design contains no selected servo product or rated torque. The CAD's 23×12×29 mm, 25 g item is an analyst envelope placeholder, not a servo datasheet. There is consequently no valid actual-servo margin comparison and no manufacturer torque sheet to cite for a selected unit.

The source-pinned geometry uses each elevon's `ELEVON_SPAN × ELEVON_CHORD` rectangular envelope (150 mm span × 40 mm chord, 0.006 m²); taper/sweep and actual hinge-line integration are not modeled. The rudder area is the CAD relief rectangle, `(FIN_HEIGHT−1 mm) × (0.30 × FIN_CHORD)`. Each vane uses its CAD rectangle with the 30 mm blade dimension as hinge reference chord. These are geometric envelopes, not validated aerodynamic effective areas.

The input speeds are indicated airspeeds (IAS), per the clarified design convention; this executable explicitly assumes CAS≈IAS with ideal instrument calibration. It computes hinge-axis torque sensitivities at all Phase-14 speed anchors, every 50 km/h from 50 through 900 km/h, and at 60 km/h explicitly for the requested low-speed band, for both sea level and the primary altitude from the pinned Phase-14 airframe configuration. A subsonic compressible pitot relation converts IAS to Mach and TAS at each pressure altitude, and dynamic pressure is computed as `q = 0.5 γ p M²`. The 3,000 m density is derived from the ISA atmosphere and is close to the pinned Phase-14 0.90913 kg/m³ input. It evaluates `H = q S c Ch` at |Ch| = 0.01, 0.05, 0.10, and 0.20. These are illustrative analyst-selected sensitivity values, not literature-derived bounds, not measured coefficients, and not predictions. The 1.5 multiplier is borrowed from the Phase-14 strong control-authority reserve requirement as a display-only demand reserve; it is not a servo design standard.

Elevons and rudder use freestream dynamic pressure. For each vector vane, the output includes local-vane/freestream velocity ratios of 1, 2, and 4, so vane dynamic pressure scales by 1, 4, and 16 while retaining the same freestream density. This velocity-only adjustment is a hypothetical sensitivity, not jet-flow physics: actual jet velocity, density, swirl, pressure, and vane incidence are unknown. Powered static vane loading is not represented by freestream scaling. Outputs are absolute hinge-axis torques; converting these to required servo output torque needs linkage ratios and losses that are absent from the design.

## IAS conversion and freestream dynamic pressure at 3 km

| IAS (km/h) | Mach | TAS (m/s) | q (Pa) |
|---:|---:|---:|---:|
| 50 | 0.04906 | 16.12 | 118.1 |
| 60 | 0.05887 | 19.34 | 170.1 |
| 700 | 0.67604 | 222.13 | 22429.3 |
| 800 | 0.76942 | 252.81 | 29052.8 |
| 900 | 0.86181 | 283.17 | 36449.7 |

## Example envelope results

At |Ch|=0.20 and the Phase-14 1.5 reserve, primary-altitude hinge-axis torque demand is tabulated at the requested 50–60 km/h low-speed band and at 700/800/900 km/h IAS. Vector vane is shown at local-velocity ratio 1; actual jet scenario can be higher or lower.

| Surface | 50 IAS, 3 km (kgf·cm) | 60 IAS, 3 km | 700 IAS, 3 km | 800 IAS, 3 km | 900 IAS, 3 km | 900 IAS, sea level |
|---|---:|---:|---:|---:|---:|---:|
| elevon_left | 0.087 | 0.125 | 16.468 | 21.330 | 26.761 | 28.106 |
| elevon_right | 0.087 | 0.125 | 16.468 | 21.330 | 26.761 | 28.106 |
| rudder_right | 0.018 | 0.026 | 3.451 | 4.471 | 5.609 | 5.891 |
| vector_vane_A1 | 0.013 | 0.019 | 2.470 | 3.200 | 4.014 | 4.216 |
| vector_vane_A2 | 0.013 | 0.019 | 2.470 | 3.200 | 4.014 | 4.216 |
| vector_vane_B1 | 0.013 | 0.019 | 2.470 | 3.200 | 4.014 | 4.216 |
| vector_vane_B2 | 0.013 | 0.019 | 2.470 | 3.200 | 4.014 | 4.216 |

These values are not pass/fail points: coefficient sensitivity dominates the range, local vane flow is unknown, and no servo rating or linkage ratio exists. The pitot conversion accounts for compressibility in the IAS-to-Mach and q conversion, but compressibility-dependent hinge coefficients are not modeled. CAS≈IAS itself is only an ideal calibration assumption; real instrument position error and installation corrections are absent. At 900 km/h IAS, the conversion gives Mach 0.862 and TAS about 1,019 km/h at 3,000 m, versus Mach 0.735 at sea level. The requested maximum remains subsonic, but compressibility is material.

## Reproduction and source limits

Run `python highspeed_edf/phase15/optimization/phase15_servo_torque_screen.py`. The script validates SHA-256 and Git blob pins before reading the CAD constants and Phase-14 speed anchors; `source_pins.json` records exact revision/blob IDs and source URLs. Full rows and assumptions are in the adjacent CSV and JSON.

No external servo manufacturer source applies because no actuator make/model was selected. No hinge coefficient is imported from a generic airfoil report: the whole coefficient range is exposed as a parameter sensitivity. The standard-atmosphere and pitot equations are conventional analytical relations; NASA context URLs, source input values, and exact local design inputs are recorded in `source_pins.json`.

**Not a qualification:** this analytical screen does not validate control authority, aeroelastic stability, structural strength, actuator response, wiring/power, failure modes, or flight safety. The seven actuator positions versus six allocated channels is an independent unresolved control-interface issue.
