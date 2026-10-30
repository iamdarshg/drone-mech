Parent: https://github.com/iamdarshg/drone-mech/issues/1

## Verified gap
Current `phase15_parameter_register.json`: two Ø82/Ø78 duct modules, rotor Z=12/48/84 mm (36 mm pitch); the selected Ø36×72 mm Surpass 3670 motor envelopes overlap by 36 mm between stages. `phase15_geometry_audit.json` and `HANDOFF.md` explicitly keep these collisions visible. The file calls this a geometrical conflict, not a small tolerance issue.

## Source files / evidence
`highspeed_edf/phase15/optimization/phase15_generate_geometry.py`, `highspeed_edf/design/PHASE15_DESIGN_SPEC.md`, `highspeed_edf/deliverables/phase15_geometry/reports/phase15_geometry_audit.json`, `drone-arm/docs/hardware/REV_B_ARCHITECTURE.md`.

## Detailed implementation plan
1. Extract true imported motors: envelope, can, shafts, bearing and end-cap dimensions and cooling access; flag estimated/unknown values.
2. Create at least three explicitly distinct candidates: revised axial-spacing/duct length; a mechanically packaged shaft/gear/belt transmission if feasible; a simpler fewer-driven-stages architecture. Preserve six-channel ESC as a contract unless the alternative intentionally changes it and creates a linked drone-arm task.
3. Regenerate complete *solid* duct, shaft, bearing, mount, cable and rotor station assemblies; compute collision matrix, min clearances and access paths for every part, including thermal expansion and tolerance sweeps.
4. Quantify structural/thermal/electrical consequences, mass/CG, rotor support and potential loss of 720 km/h target. Do not select a topology on looks or a 1-D thrust estimate.

## Acceptance tests / definition of done
- [ ] All interpenetrations of physically distinct solids eliminated, with numeric min clearances and collision test using the native CAD shapes.
- [ ] The candidate preserves material/fastener/bearing/wire installation access and removal sequence; if not, remains an unpromoted option.
- [ ] A comparison table identifies mechanical feasibility, predicted performance sensitivity, mass, cost, fabrication operations and evidence class for each option.
- [ ] At least one non-self-intersecting complete STEP round-trips and matches the source generator hash; unresolved propulsion qualification stays BLOCKED.
- [ ] PR contains baseline SHA, commands, results table, source citations, output hashes, risk register and truthful evidence label; rerun from clean checkout.
- [ ] Tests fail meaningfully for a deliberate invalid unit, missing part or mismatched interface (not just snapshots).

## Sequencing / dependencies
Dependency for almost all downstream EDF flowpath, thermal, rotor and airframe qualification issues.

## Agent execution
Use distinct branch/PR. Delegate source inspection, CAD/analysis, and verification independently. Resolve routine tool/setup blockers yourself. If physical data/certification missing, preserve as BLOCKED and prepare an explicit test plan. Never claim validated/flight-ready without independent native solver and physical gates; no purchases, hardware energization, flight or unbounded cloud costs.
