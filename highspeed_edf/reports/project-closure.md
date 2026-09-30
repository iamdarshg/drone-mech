> **OBSOLETE — SUPERSEDED.** See `../OBSOLETE.md` and `../design/PHASE15_DESIGN_SPEC.md`.
> This file describes a superseded configuration (90 mm geared FA4119, old mass
> basis, 75 cm2 frontal-area gate, CdA 0.0009 m2). Do NOT use it to size or build.
# High-speed EDF — fixed-powertrain geometry closure

## Geometry-only candidate

The new candidate retains all six FA4119 motors and the two-pack 12S1P battery. It screens at **73.62 cm²**, **T/W=1.040** at 3 km on the 55 A/motor soft point with 30 mΩ assumed pack resistance, **11.5 kg** all-up, and a 720 km/h design point. The ideal-gas cycle screen passes 701–730 km/h for CdA=0.00095 m²; the re-solved 720 km/h row set passes 6/6 meanline checks.

The geometry is a 90 mm OD / 32 mm hub axial fan stack, 16 mm rotor chord, 29 mm blade span, and 8 mm stator chord, all within the 16 mm × 50 mm stock envelope. Two 50×120 mm side inlets feed the annulus; axial duct staggering and side-facing inlets keep the projected area below 75 cm². Equal stage work is the blade-pitch/twist design target to keep all six unchanged motor channels under the current soft limit.

## Actual hardware mass basis and fuselage budget

Six FA4119 motors weigh 1.680 kg from the drone-arm decision record; both Turnigy packs weigh 1.426 kg from the product spec. KiCad stackups plus exported copper coverage give **0.121 kg bare PCB material**. Thus the sourced motor + battery + bare-board floor is 3.227 kg, leaving 8.273 kg for board components/lugs/heatsink, rotors/gears, ducts, side inlets, wiring, fuselage, landing gear and payload.

That residual is an engineering mass allowance, not a measured total: drone-arm BOMs do not assign weights to populated board assemblies, spreaders, harnesses or the airframe. The candidate passes the mass screen only if the completed assembly is weighed at or below 11.5 kg.

## Screens and remaining validation

At 720 km/h, the Phase-1 cycle model predicts 12.93 kW bus power; under the worst screened 30 mΩ pack R0 the soft-current bus cap is 13.17 kW. The 720 meanline solve reports 6/6 rows passing, stator Reynolds minimum near 69k, and continuity residual 5.87e-08.

| Gate | Current disposition | Evidence still needed |
|---|---|---|
| projected_frontal_area | ANALYTIC_PASS_CAD_UNVERIFIED | Dimensioned assembled CAD with board populations, heat spreaders, side-slot lips, mounts and the full projected union. |
| low_speed_static_twr | ANALYTIC_PASS_MASS_BUDGET_OPEN | Weigh the populated controller assemblies, fans/gears, harness, inlet structure and fuselage; stay at or below 11.5 kg, then verify static thrust. |
| 720kmh_rotor_stator_rows | CANDIDATE_MEANLINE_PASS_OFFDESIGN_OPEN | Run the frozen blade metal angles across 0–730 km/h, variable-bypass schedule and inlet distortion; validate by rig or CFD. |
| high_speed_envelope | ANALYTIC_PASS_CDA_TARGET_UNVALIDATED | Build/measure the fuselage/inlet CdA and verify installed drag, pressure recovery, six-channel current sharing and motor RPM on a test article. |
| battery_characterization | ASSUMED_R0_OCV_THERMAL | Measure pack OCV/DCIR pulses and thermal response across SOC and temperature; confirm the 55 A/motor operating point. |
| motor_esc_characterization | FIXED_FA4119_MAP_UNVALIDATED | Guarded dyno with the final blades; record shaft torque/RPM, bus/phase current, motor/ESC temperatures, vibration and efficiency. |
| rotordynamics | OLD_GEOMETRY_RESULT_INVALID_FOR_NEW_ROTOR | Re-run Campbell and forced response with the 90 mm rotor/hub/shaft design; verify startup on the test stand. |
| electronics_mass | BARE_BOARD_MASS_CALCULATED_POPULATION_UNWEIGHED | Weigh the populated Rev-B boards and production heat spreader; reconcile the ESC PCB six-layer saved stackup against its four-layer architecture document. |
| mission_endurance | MISSION_PROFILE_OPEN | Define mission segments, reserve, climb/takeoff and desired loiter/range. |

The Phase-4 ROSS critical-speed results are for the superseded 80 mm rotor/shaft model; re-run after detailed 90 mm blade/hub CAD. Battery DCIR and fan efficiency remain sensitivities. No powertrain component, capacity, voltage, or current limit was changed. No cloud jobs were used.

