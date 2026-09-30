# Phase 11 — iterative fixed-powertrain airframe / EDF screen

## Outcome

The fixed six FA4119 KV350 motors, two 6S5000 packs in series (12S1P/5Ah), per-motor current limits and ESCs were unchanged. The Phase-9 720 km/h meanline remains a 1-D result with 1.0202× thrust closure and 6/6 blade rows passing; it is not installed-system validation. The Phase-9 3 km, 55 A/motor, 30 mΩ static T/W of 1.0396 scales to **1.0218** using the Phase-10 88 mm bore / 32 mm hub. That clears T/W≥1 analytically at 11.5 kg, but does not provide a healthy 1.10 margin; 1.10 requires all-up mass ≤10.68 kg.

No complete installed-aircraft winner was found. The sampled single-quarter-turn inlet family cannot satisfy the front-area constraint, and the OpenFOAM worker produced no converged pressure-recovery values.

## Geometric infeasibility in the current inlet topology

For two coincident 90 mm fan silhouettes the front-view fan union is 63.617 cm². The candidate reserves 10 cm² for structure and controls. With 50 mm-wide outboard side-turn envelopes, the conservative incremental projected area is `(R − 45 mm)` cm² for R>45 mm. Thus the <75 cm² requirement limits the turn centerline radius to **R≤46.38 mm**.

The same full-height 120 mm slot section spans 60 mm radially through a 90-degree bend; avoiding a self-intersection requires **R>60 mm** for this single-pass topology. The Phase-11 sweep tested R65/R70/R75, all below the required area gate:

| R | Complete-area lower bound | Area gate |
|---:|---:|---|
| 65 mm | 93.62 cm² | fail |
| 70 mm | 98.62 cm² | fail |
| 75 mm | 103.62 cm² | fail |

This is a topology conflict, not a radius-tuning optimum. A split/reoriented inlet or another change to the slot/turn topology is required before a full-airframe candidate can be selected. The 120 mm slot / R65 turn is retained as a component-level airflow experiment only.

## OpenFOAM record

Five CAD-aligned Gmsh cases were generated at R65 coarse/medium/fine and R70/R75 medium. They represent one symmetric duct branch at Mach 0.60869 with 0.858742 kg/s branch target, derived from the Phase-9 720 km/h meanline and a 3 km ISA total state (90.038 kPa, 288.557 K). The physical fan-face annulus uses the 88 mm bore and 32 mm hub: 52.779 cm² per duct. `gmshToFoam` imported all five cases.

`checkMesh` passed three meshes; R65 coarse and R75 medium each failed one determinant-quality check. Three solver invocations aborted at initialization because the cloud case used a wrapped `changeDictionaryDict`, leaving patch `walls` typed `patch`; `nutkWallFunction` requires type `wall`. The shared worker also initially assumed a `bendRadiusM` case key rather than Phase-11's `turnRadiusM`. Both issues are corrected in the local Phase-11 inputs/runner, but the one-instance cloud allowance was consumed and no second run was launched. **No SIMPLE iterations completed; no pressure-recovery CFD result or grid convergence is claimed.**

See `../../../phase11/results/phase11_solver_receipt.json`, `../../../phase11/results/phase11_solver_results.csv`, `../../../phase11/results/caseLogs/`, `../../../phase11/results/phase11_worker.log` and `../../../phase11/results/phase11_execution_receipt.json` for the per-case outcomes and retained logs.

## CAD, CAM, stock, mass and strength

- `step/phase11_full_assembly_R065.step`, both module STEP files and R65/R70/R75 inlet-shell alternatives re-import as valid solids. The assembly includes fixed rotor/stator schedules, 6061-T6 inlet shells, compact lifting-body sections and edge-on *bare* PCB silhouettes. Motor/battery/gearbox package outlines were not available, so this is not a released installation drawing.
- `phase11_fuselage_sections.csv` records an approximately 120 mm maximum-span, 5 mm maximum-thickness compact body; the 6061 solid-envelope estimate is 0.241 kg. It is a packaging concept, not a validated lifting-body aerodynamic or structural design.
- The known fixed mass is 3.2266 kg: motors 1.680 kg, packs 1.426 kg, and 120.585 g actual bare PCBs from `results/phase9_control_board_mass.csv`. Populated boards, heat spreaders, gearboxes, shafts, wiring, mounts, landing gear and payload remain an explicit unweighed allowance. The panelized major-part estimate leaves 4.51 kg to the 10.68 kg healthy-T/W screen; total mass is unverified.
- The 6061-T6 centrifugal-only screen at the unchanged 29/33/36 krpm schedule gives a minimum blade-root safety factor of **3.34** after a 2.5 stress-concentration factor; the hub-ring screen is 11.0. This does not establish fatigue, aeroelastic, attachment, burst-containment or test margin.
- The supplied per-EDF stock pair nests the 63 stator blanks on one 250×100×5 plate. For 36 rotor blanks, the 2.5 mm rectangular keep-out envelopes total **12,788.63 mm²** versus **12,500 mm²** in one 250×50×16 billet. The safe no-overlap CAM nest therefore uses two billets per EDF (28+8 blanks): **two extra billets total** beyond one per EDF. This is a proof for the declared 2.5 mm rectangular keep-out process, not for every possible common-line nest.
- The segmented body/inlet/casing panel concept lays out **22 additional 250×100×5 plates** beyond the two stator plates. Their 2.5D blank contours are CAM-starting operations; forming, sealing, seams and assembly joints are not part of the modeled CNC operations. The NC package contains 56 G-code files, uses G54 stock coordinates, 2 mm roughing and 0.5 mm top-band finishing, and all coordinates were checked against stock bounds. **No CNC was run.**

## Budget and retained outputs

The one new GCE Spot worker was capped at 600 seconds; it ran for 112.216 seconds and was deleted with its boot disk. Conservative new compute estimate: **$0.00623**. Including the full temporary-storage/network and contingency reserve, Phase-11 envelope estimate: **$0.08875**, within the remaining $0.11586 approval. Combined with Phase-10's $0.08414 estimate, the estimated total envelope is **$0.17289 ≤ $0.20**. Actual billing was not queried. Temporary GCS objects were deleted.

Machine-readable results and receipts are under `../../../phase11/results/`; generated STEP, stock layouts, and NC files are under `../` (`step/`, `stock_layouts/`, `gcode/`). No pressure-recovery result is reported as CFD success, and no geometry is marked best or flight-ready.
