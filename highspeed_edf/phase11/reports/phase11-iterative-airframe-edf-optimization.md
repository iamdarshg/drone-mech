# Phase 11 — fixed-powertrain inlet, airframe, CAD/CAM and structural screen

## Locked hardware and operating point

The six stock FA4119 KV350 motors, two 6S5000 packs in series (12S1P/5Ah), current limits and ESCs are unchanged. The atmospheric boundary state is derived at 3 km / 720 km/h: Mach 0.60869, freestream total pressure 90.038 kPa and total temperature 288.557 K. The Phase-9 meanline flow is 1.71748 kg/s total, or 0.858742 kg/s per duct.

At the 720 km/h design point, the Phase-9 six-row meanline closes to 1.0202× the requested drag with all six rows passing. This remains a meanline result, not validated installed thrust. With the Phase-10 88 mm bore / 32 mm hub, the 3 km, 11.5 kg, 55 A/motor, 30 mΩ area-scaled static T/W is 1.0218. A 1.10 T/W screen requires all-up mass ≤10.68 kg. The Phase-11 mass screen includes the actual 120.585 g bare PCB mass from `results/phase9_control_board_mass.csv`; populated-board, gearbox, harness and landing-gear mass remain explicit unweighed allowances.

## Iterative geometry screen and projected-area proof

The CAD-aligned sweep samples 65, 70 and 75 mm quarter-turn centreline radii, with a 50×120 mm slot feeding the 90/88/32 mm fan annulus. All branch meshes use the same derived total inlet state and meanline mass-flow target. Local Gmsh screening generated coarse/medium/fine cases with 16,825–71,982 tetrahedra and minimum scaled inverted condition numbers above 0.31.

For the present full-height, single-quarter-turn topology, the 120 mm section has a 60 mm radial half-height; a non-self-intersecting circular turn therefore requires R>60 mm. The conservative complete front-projection model is `63.617 cm² fan union + 10 cm² structure/control allowance + (R−45) cm² turn-strip lower bound`:

| Turn radius | Projection lower bound | <75 cm² gate |
|---:|---:|---|
| 65 mm | 93.62 cm² | fail |
| 70 mm | 98.62 cm² | fail |
| 75 mm | 103.62 cm² | fail |

The same gate permits at most R=46.38 mm under that bound, below the >60 mm geometric limit for the unsplit 120 mm slot section. This topology has no candidate that can meet both constraints. A split/reoriented inlet, a different slot envelope, or a changed area requirement is needed before an integrated compliant design can be selected. The existing 450 mm-span Phase-10 body is not reused as a passing projection; the Phase-11 STEP uses a compact 120 mm body envelope and edge-on bare-board placeholders, while its area ledger retains the conservative structure reserve.

## OpenFOAM status

Phase 11 prepared five CAD-aligned compressible cases: R65 coarse/medium/fine and R70/R75 medium. `gmshToFoam` converted all five; `checkMesh` passed R65 medium/fine and R70 medium, and failed one small-determinant check on R65 coarse and R75 medium. Three `rhoSimpleFoam` processes then aborted before SIMPLE iteration because `changeDictionaryDict` used a wrapper instead of a direct `boundary { walls { type wall; } }` replacement. The raw worker receipt also exposed a case-radius key mismatch. Both local fixes are now in the Phase-11 case generator/worker, but the single approved Spot instance has been used, so these corrections were not re-run. **No pressure-recovery value or grid-convergence result is available.** See `../results/phase11_solver_receipt.json` and `../results/caseLogs/`.

## CAD/CAM, stock, mass and strength

`deliverables/phase11/step/` contains the R65 full assembly, the two EDF assemblies, and R65/R70/R75 inlet-shell alternatives. STEP re-import validity is recorded in `deliverables/phase11/reports/phase11_cad_cam_receipt.json`. The STEP includes the fixed rotor/stator schedules and bare PCB silhouettes. Motor, battery, gearbox and populated-board package outlines were not supplied, so the assembly is not a released installation drawing.

The 6061-T6 centrifugal-only calculation uses the fixed 29 mm rotor envelope and 29,375 / 33,125 / 36,360 rpm rows. With a 2.5 root stress-concentration factor and 276 MPa yield assumption, the minimum blade-root safety factor is 3.34; the hub thin-ring screen is higher. This exceeds the requested 2.5 centrifugal-only target, but does not cover fatigue, aeroelastic loads, joints, flaws, containment or test evidence.

The stock/CAM release is in `deliverables/phase11/stock_layouts/` and `deliverables/phase11/gcode/`. One 250×100×5 plate per EDF holds 63 stator blanks. For 36 rotor blanks per EDF, the 2.5 mm rectangular keep-out envelope area is 12,788.63 mm² versus 12,500 mm² of one 250×50×16 billet; the documented no-overlap nest uses 28+8 blanks in two billets per EDF. It therefore needs **two additional billets total** beyond one billet per motor-set (four billets total). The selected concept additionally lays out 22 extra 250×100×5 plates for segmented body, turn-shell and casing panel blanks; these are outside the two supplied stator plates. The panel G-code is perimeter blanking only; bending, sealing and joining are not represented. All NC files use G54 stock coordinates, 2 mm roughing, 0.5 mm top-band finishing, conservative feeds and no machine execution.

The panelized mass screen is a CAD-material estimate, not an aircraft weighing. It leaves an explicit 4.51 kg allowance to the 10.68 kg healthy-T/W target for populated electronics, shafts/gears, mounts, wiring, landing gear and payload. Mass and CdA remain unverified targets.

## Cloud budget and disposition

The one new Spot worker was capped at 600 seconds and $0.11586 estimated new spend: $0.03334 maximum compute at $0.20/hour, $0.02 temporary storage/network/artifacts, and $0.06252 contingency. It ran for 112.216 seconds; the conservative new-envelope estimate is $0.08875. Combined with Phase 10’s $0.08414 estimated envelope use, the total estimate is $0.17289, below $0.20. The VM and disk were deleted, temporary GCS objects removed, and the CNC was not run.

The geometry trade has no passing projected-area candidate. The OpenFOAM processes did not produce valid recovery data, so no aerodynamic winner can be ranked. Even a high-recovery branch would not make the current unsplit-turn installation pass the area gate. No fully compliant 720 km/h / low-speed-T/W≥1 airframe is claimed from this batch.
