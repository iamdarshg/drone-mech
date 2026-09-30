> **OBSOLETE — SUPERSEDED.** See `../OBSOLETE.md` and `../design/PHASE15_DESIGN_SPEC.md`.
> This file describes a superseded configuration (90 mm geared FA4119, old mass
> basis, 75 cm2 frontal-area gate, CdA 0.0009 m2). Do NOT use it to size or build.
# Phase 1 feasibility report

**Evidence class:** analytical screening. Workbench ideal-gas functions are reused. No native solver, GCP job, CFD, battery discharge test, or EDF dyno result was run.

## 600 km/h reference cases

| CdA (m²) | Required thrust (N) | Captured flow (kg/s) | Required PR | Electrical input (kW) |
|---:|---:|---:|---:|---:|
| 0.0030 | 51.0 | 1.465 | 1.1156 | 19.30 |
| 0.0035 | 59.5 | 1.465 | 1.1302 | 21.62 |
| 0.0040 | 68.0 | 1.465 | 1.1453 | 24.01 |
| 0.0045 | 76.5 | 1.465 | 1.1609 | 26.46 |

The forward model captures only the annular area times an assumed 0.85 capture fraction, then solves the compressor PR needed for momentum thrust through an ideally expanded nozzle. It does not model bypass/core mixing, distortion, spillage, or fan maps, so use this as a feasibility screen rather than a design prediction.

## Altitude comparison: 600 km/h, CdA=0.004 m²

| Altitude (km) | Density (kg/m³) | Thrust (N) | Captured flow (kg/s) | PR | Electrical input (kW) |
|---:|---:|---:|---:|---:|---:|
| 0 | 1.225 | 68.0 | 1.465 | 1.1453 | 24.01 |
| 1 | 1.111 | 61.7 | 1.330 | 1.1476 | 21.65 |
| 2 | 1.006 | 55.9 | 1.204 | 1.1501 | 19.47 |
| 3 | 0.909 | 50.5 | 1.087 | 1.1526 | 17.47 |

The lower density reduces both aircraft drag and captured flow at a fixed true airspeed. This comparison holds CdA fixed and uses ISA temperature/pressure; it is not an altitude schedule or a corrected-airspeed comparison.

## Inlet recovery sensitivity at 600 km/h

| Recovery | Compressor-face Pt (kPa) | Required PR | Electrical input (kW) |
|---:|---:|---:|---:|
| 0.900 | 107.44 | 1.2382 | 38.25 |
| 0.920 | 109.83 | 1.2135 | 34.54 |
| 0.940 | 112.22 | 1.1898 | 30.93 |
| 0.960 | 114.60 | 1.1671 | 27.42 |
| 0.970 | 115.80 | 1.1561 | 25.71 |
| 0.980 | 116.99 | 1.1453 | 24.01 |
| 0.985 | 117.59 | 1.1400 | 23.17 |
| 0.990 | 118.18 | 1.1347 | 22.34 |

## Motor speed gate

| Limit point | RPM | Tip speed (m/s) | Mean blade speed (m/s) | 3-rotor specific work at ψ=0.5 (kJ/kg) |
|---|---:|---:|---:|---:|
| externally sourced limit | 12500 | 52.4 | 36.7 | 2.02 |
| externally sourced limit | 13500 | 56.5 | 39.6 | 2.35 |
| externally sourced limit | 17640 | 73.9 | 51.7 | 4.01 |

The 3-rotor work column is a kinematic screening bound for three same-speed rotors using the annulus mean radius and assumed loading coefficient ψ=0.5; it is not a compressor map or proof the FA4119 can sustain the listed speed. Initial controller hard limit is 13,500 rpm; stock 350 Kv no-load speed at full charge is 17,640 rpm, but that does not supersede the controller/rotor qualification limits.

At 600 km/h, CdA=0.004 m², recovery=0.98, the equal-work 3-rotor speed screen is:

| Assumed rotor loading ψ | Required common RPM |
|---:|---:|
| 0.40 | 37651 |
| 0.50 | 33676 |
| 0.60 | 30742 |

This is optimistic: it uses the fan annulus mean radius for every rotor, equal work split, and excludes incidence, losses, stall margin, and electrical back-EMF. Core rotor radii would be smaller.

The electrical work model requires 24.0 kW for CdA=0.004 m² at 600 km/h. For comparison, the six FA4119 decision-record current limits with assumed 20 mΩ pack resistance yield 12.47 kW at the 55 A/motor soft rollback and 14.27 kW at the 65 A/motor initial hard limit at nominal voltage; the provisional 75 A/motor level gives 15.93 kW, with no validated duration. At full charge these are 14.45/16.61/18.63 kW. Pack resistance is a sensitivity assumption, not measured Turnigy data. The generic 18/21/24 kW sweep is a power-only envelope and must not be read as reachable FA4119 performance.

On the same optimistic loading basis, 3 stages at the initial 13,500 rpm hard limit provide only 2.35 kJ/kg at ψ=0.5 versus 14.63 kJ/kg required in this reference case. Thus stock direct-drive fails the current 3-rotor loading screen by a wide margin, even before motor torque, voltage sag, and core-radius penalties. Phase 1 does not extrapolate the motor beyond its documented RPM limits.

## Battery interpretation and unresolved data

The 12S series pair remains 5 Ah (nominal 222 Wh), not 10 Ah. The FA4119 decision record sets 55 A/motor soft rollback, 60–65 A initial hard current and 70–75 A provisional short current; the latter duration is unvalidated. These are battery-current limits, distinct from the ESC's 60/90 A phase-current ratings. At 6 motors this screens 66C soft, 78C at 65 A, and 90C at 75 A. Pack resistance, voltage-sag curves and temperature response are unmeasured; the advertised 100C is not validated.

The low-speed table uses an ideal actuator disk and assumed fan efficiencies. It is an upper-bound sensitivity and does not demonstrate T/W≥1 for the actual fan. `battery_duration_bounds.csv` is energy-only; it excludes reserve, temperature, voltage cut-off, and acceleration.

### Static thrust sensitivity examples

| Altitude (km) | Pack / assumed resistance | Current scenario | Fan efficiency | Static T/W upper bound |
|---:|---|---|---:|---:|
| 0 | nominal / 20 mΩ | 55A-per-motor-soft-rollback | 0.65 | 0.582 |
| 0 | nominal / 20 mΩ | 65A-per-motor-initial-hard-limit | 0.65 | 0.636 |
| 0 | fully_charged / 10 mΩ | 75A-per-motor-provisional-short-duration-unvalidated | 0.65 | 0.814 |
| 0 | fully_charged / 10 mΩ | 75A-per-motor-provisional-short-duration-unvalidated | 0.80 | 0.935 |
| 3 | nominal / 20 mΩ | 55A-per-motor-soft-rollback | 0.65 | 0.527 |
| 3 | nominal / 20 mΩ | 65A-per-motor-initial-hard-limit | 0.65 | 0.576 |
| 3 | fully_charged / 10 mΩ | 75A-per-motor-provisional-short-duration-unvalidated | 0.65 | 0.737 |
| 3 | fully_charged / 10 mΩ | 75A-per-motor-provisional-short-duration-unvalidated | 0.80 | 0.847 |

At nominal voltage and assumed 20 mΩ resistance, the idealized 0.65-efficiency cases clear T/W=0.5 at the soft and initial-hard current limits, but T/W≥1 is not demonstrated. The provisional 75 A/motor current is not assigned a duration. Actual duct, rotor and motor losses reduce these upper bounds.

## Artifacts

- `forward_speed_cda_map.csv` — 100–700 km/h at each configured altitude.
- `pressure_recovery_sensitivity.csv` — 600/700 km/h at each altitude.
- `speed_power_map.csv` and `cda_requirement_map.csv` — altitude-indexed idealized power/speed/CdA grids.
- `static_thrust_sensitivity.csv` — altitude-indexed ideal actuator-disk upper bounds.
- `motor_rpm_screen.csv` and `required_rotor_loading_screen.csv` — RPM/work screen; required-work rows cover every altitude.
- `battery_duration_bounds.csv` — energy-only burst-duration bounds.
- `fighter_drag_analog.csv` — F-16C/Gripen C polar-based reference-area and estimated frontal-area analog at 3 km.
- `phase1_results.json` — machine-readable assumptions, provenance, and summary.

## Fighter analog: frontal-area interpretation of 31.5 cm² CdA

The F-16 and Gripen do not have a single speed-independent published total Cd suitable for this conversion. Their conventional aircraft drag coefficients are referenced to wing planform area, and depend on lift coefficient. This screen used the parabolic polar `CD = CD0 + CL²/(π AR e)`, fighter reference geometry, representative weights (F-16C 12,000 kg; Gripen C 8,500 kg), clean-configuration CD0/e ranges, and a separately assumed frontal-projection/wing-area ratio of 0.08–0.12. The last ratio is only a silhouette estimate; it is not a measured F-16/Gripen frontal area.

| Speed | F-16C frontal-equivalent range (central) | Gripen C frontal-equivalent range (central) |
|---:|---:|---:|
| 500 km/h | 48–89 cm² (66 cm²) | 53–105 cm² (76 cm²) |
| 600 km/h | 66–127 cm² (93 cm²) | 67–137 cm² (97 cm²) |
| 700 km/h | 78–155 cm² (112 cm²) | 76–156 cm² (110 cm²) |

These are **equivalent allowable projected frontal areas** for the 31.5 cm² CdA target under the assumed fighter analog polar—not the aircraft's literal measured frontal silhouette. If the 31.5 cm² CdA ceiling must hold across the whole 500–700 km/h band, the limiting 500 km/h estimate is roughly **66–76 cm² central**, with a conservative lower bound near **48–53 cm²**. At the 700 km/h design point, the central estimate is about **110 cm²**. See the CSV for the full coefficient and reference-area ranges.

Sources for conventions and reference geometry: [NASA drag equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/modern-drag-equation/) (reference area and induced-drag relation); [parabolic drag polar](https://agodemar.github.io/FlightMechanics4Pilots/mypages/drag-polar/); [F-16 specifications](https://en.wikipedia.org/wiki/General_Dynamics_F-16_Fighting_Falcon); [Gripen C specifications](https://en.wikipedia.org/wiki/Saab_JAS_39_Gripen). Exact fighter polar points are not published in these sources; CD0, Oswald efficiency, representative flight masses, and frontal/wing area ratio are explicitly analyst assumptions.

## Phase 1 conclusion

At 600 km/h and CdA=0.004 m², the screen predicts 24.01 kW at sea level and 17.47 kW at 3 km ISA; the density reduction lowers drag and captured flow at the same true airspeed. At 3 km the power demand is near the best-case fully charged battery/current envelope, but this result depends on unmeasured pack resistance and the provisional FA4119 current ceiling. The preliminary equal-work rotor screen still requires roughly 30–38 krpm, versus the stock baseline's initial 13.5 krpm hard limit. Therefore altitude helps the power balance but does not remove the direct-drive RPM mismatch. These are screening results, not a demonstrated flight envelope. Next: quantify achievable lower speed with stock motors across altitude, then compare requalified motor/gearbox options if needed; obtain measured FA4119 torque/current/loss and pack DCIR before detailed geometry or GCP spend.

Requirements file SHA-256: `181e5847d1b67d27088d5ae283c9acf6f70c895e635e5946cf57bff57824df05`

