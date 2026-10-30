# Phase-15 servo torque feasibility screen

**Result: servo adequacy is undetermined.** The source design contains no selected servo product or rated torque. The CAD's 23×12×29 mm, 25 g item is an analyst envelope placeholder, not a servo datasheet. There is consequently no valid actual-servo margin comparison and no manufacturer torque sheet to cite for a selected unit.

The input speeds are indicated airspeeds (IAS), per the clarified design convention; this executable explicitly assumes CAS≈IAS with ideal instrument calibration. It computes hinge-axis torque sensitivities at all Phase-14 speed anchors and every 50 km/h from 50 through 900 km/h for both sea level and the primary altitude from the pinned Phase-14 airframe configuration. A subsonic compressible pitot relation converts IAS to Mach and TAS at each pressure altitude, and dynamic pressure is computed as `q = 0.5 γ p M²`. The 3,000 m density is derived from the ISA atmosphere and is close to the pinned Phase-14 0.90913 kg/m³ input. It evaluates `H = q S c Ch` at |Ch| = 0.01, 0.05, 0.10, and 0.20. These are illustrative analyst-selected sensitivity values, not literature-derived bounds, not measured coefficients, and not predictions. The 1.5 multiplier is borrowed from the Phase-14 strong control-authority reserve requirement as a display-only demand reserve; it is not a servo design standard.

Elevons and rudder use freestream dynamic pressure. For each vector vane, the output includes local-vane/freestream velocity ratios of 1, 2, and 4, so vane dynamic pressure scales by 1, 4, and 16 while retaining the same freestream density. This velocity-only adjustment is a hypothetical sensitivity, not jet-flow physics: actual jet velocity, density, swirl, pressure, and vane incidence are unknown. Powered static vane loading is not represented by freestream scaling. Outputs are absolute hinge-axis torques; converting these to required servo output torque needs linkage ratios and losses that are absent from the design.

## Example envelope results

At |Ch|=0.20 and the Phase-14 1.5 reserve, primary-altitude hinge-axis torque demand rises from 50 to 900 km/h IAS. Vector vane is shown at local-velocity ratio 1; actual jet scenario can be higher or lower.

| Surface | 50 IAS, primary altitude (kgf·cm) | 900 IAS, primary altitude (kgf·cm) | 900 IAS, sea level (kgf·cm) |
|---|---:|---:|---:|
| elevon_left | 0.087 | 26.761 | 28.106 |
| elevon_right | 0.087 | 26.761 | 28.106 |
| rudder_right | 0.018 | 5.609 | 5.891 |
| vector_vane_A1 | 0.013 | 4.014 | 4.216 |
| vector_vane_A2 | 0.013 | 4.014 | 4.216 |
| vector_vane_B1 | 0.013 | 4.014 | 4.216 |
| vector_vane_B2 | 0.013 | 4.014 | 4.216 |

These values are not pass/fail points: coefficient sensitivity dominates the range, local vane flow is unknown, and no servo rating or linkage ratio exists. The pitot conversion accounts for compressibility in the IAS-to-Mach and q conversion, but compressibility-dependent hinge coefficients are not modeled. CAS≈IAS itself is only an ideal calibration assumption; real instrument position error and installation corrections are absent. At 900 km/h IAS, the conversion gives Mach 0.862 and TAS about 1,019 km/h at 3,000 m, versus Mach 0.735 at sea level. The requested maximum remains subsonic, but compressibility is material.

## Reproduction and source limits

Run `python highspeed_edf/phase15/optimization/phase15_servo_torque_screen.py`. The script validates SHA-256 and Git blob pins before reading the CAD constants and Phase-14 speed anchors; `source_pins.json` records exact revision/blob IDs and source URLs. Full rows and assumptions are in the adjacent CSV and JSON.

No external servo manufacturer source applies because no actuator make/model was selected. No hinge coefficient is imported from a generic airfoil report: the whole coefficient range is exposed as a parameter sensitivity. The standard-atmosphere and pitot equations are conventional analytical relations; NASA context URLs, source input values, and exact local design inputs are recorded in `source_pins.json`.

**Not a qualification:** this analytical screen does not validate control authority, aeroelastic stability, structural strength, actuator response, wiring/power, failure modes, or flight safety. The seven actuator positions versus six allocated channels is an independent unresolved control-interface issue.
