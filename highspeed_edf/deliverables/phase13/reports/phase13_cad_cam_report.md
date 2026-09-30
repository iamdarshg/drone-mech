# Phase 13 — fixed-powertrain R30 EDF CAD/CAM and airframe revision

## Disposition and traceability

Phase 13 is an additive revision under `deliverables/phase13`; Phase 12 and its results remain unchanged. The selected inlet is **R30 as a packaging start only**. Phase-10/11 OpenFOAM solver receipts have null pressure recovery (zero solver iterations), and Phase 12 is local preflight-only with no cloud launch. Therefore pressure recovery is **pending**, there is no CFD ranking, and R30 is not described as an aerodynamic optimum. No solver/GCP job or CNC operation was run.

The fixed installation is unchanged: six stock FA4119 KV350 motors (three per EDF set), two Turnigy Rapid 6S5000 packs in series (12S1P, 5Ah), fixed gear ratios 2.35/2.65/2.95, and all existing current, ESC, voltage and RPM limits. Rotor design speeds remain 29,375/33,125/36,360rpm. Each of two EDFs retains a 90mm OD, 88mm bore, 32mm hub, three rotor rows and three stator rows. There are two 25×120mm side-inlet slots per EDF, four total.

## Installed projected area

The exact geometry silhouette union, including both coincident fan disks, selected R30 split-turn inlet outlines/lips, board/spreader silhouettes, cooling-bay rails, motor/battery proxies and body envelope, is **69.143cm²**. The strict installed-area gate is `<75cm²`: **PASS**. The Phase-12 reserve-aware R30 upper screen (fan disk union + 10cm² generic structure reserve, no R30 outboard turn protrusion) is **73.617cm²**, also below 75cm². Keep this conservative reserve in place until dimensioned motor mounts and physical enclosures replace the package proxies.

## Rotor-root reinforcement and strength screen

Each rotor is a fused one-solid hub/blade B-rep. The root now starts at radius 14.0mm, inserts 2.0mm into the 32mm hub, and uses a 20% thick root airfoil lofting smoothly to the nominal 12% section over the first 7.10mm (24% of span). This replaces Phase 12's 16% root loft and separate blade/hub compounds. The strengthened CAD rotor OD remains within the 88mm bore and the planform nest retains the 16mm billet thickness.

Proof speed is 1.25× the maximum fixed gear-derived rotor RPM at the unchanged 12,500rpm motor soft-limit basis: R1 36718.75, R2 41406.25, R3 46093.75rpm. The Phase-12 centrifugal root stress reference (Kt=2.5, 6061-T6 yield 276MPa) is area-scaled by the actual NACA root-section area ratio. The smallest centrifugal-only FOS is **3.462** (target ≥3.0). This is an analytical screen, not an FEA, fatigue, aero-bending, joint, burst-containment or spin-test qualification.

| Row | Gear-derived maximum rpm | 1.25× proof rpm | Phase-13 root area (mm²) | Centrifugal-only FOS | Gate |
|---|---:|---:|---:|---:|---|
| R1 | 29375 | 36718.75 | 34.93 | 5.456 | PASS |
| R2 | 33125 | 41406.25 | 34.93 | 4.290 | PASS |
| R3 | 36875 | 46093.75 | 34.93 | 3.462 | PASS |

## Mass budget and CG

The **sourced mass subtotal is 3.227kg**: motors 1.680kg, battery pair 1.426kg, bare ESC/flight PCBs 0.120585kg from `results/phase9_control_board_mass.csv`. Rotor/stator values below are computed from Phase-13 solid volumes; remaining values are individually identified estimates/allowances.

| Component | Mass (kg) | Evidence/basis |
|---|---:|---|
| Six stock FA4119 KV350 motors | 1.6800 | sourced fixed motor mass 6 x 0.280 kg |
| Two Turnigy Rapid 6S5000 packs in series, 12S1P 5Ah | 1.4260 | sourced 2 x 0.713 kg; 150x50x45 mm package dimensions remain a proxy |
| ESC and flight-control bare PCBs | 0.1206 | results/phase9_control_board_mass.csv; population excluded |
| Remaining populated-board parts, connectors and solder | 0.2000 | explicit analyst allowance beyond bare PCB source mass |
| Aluminium board heat spreaders | 0.0824 | Phase-12 dimension/material estimate retained; two separate spreaders |
| Six 6061-T6 fused rotors and hubs | 0.3140 | Phase-13 CadQuery fused-solid volumes x 2700 kg/m3 |
| Six 6061-T6 stator sets and rails | 0.0537 | Phase-13 CadQuery solid volumes x 2700 kg/m3 |
| Six fixed-ratio gearboxes | 0.7200 | explicit analyst allowance 6 x 0.120 kg; gear ratios unchanged |
| Power, phase, sensor and control harness | 0.2500 | explicit analyst allowance including service loops/connectors |
| PLA/CF fuselage and lifting-body shells | 0.2737 | CAD surface split 0.21314 m2; PLA core + 200gsm CF/100gsm glass per face and 0.8 resin:fibre |
| PLA/CF fan casing shells | 0.1580 | CAD surface 0.12302 m2; same documented laminate/core schedule |
| PLA/CF four R30 split-inlet branches and lips | 0.1205 | CAD surface 0.09383 m2; same documented laminate/core schedule |
| Mounts, clamps, fasteners and cooling-bay support allowance | 0.3500 | explicit analyst allowance; motor/shaft outline dimensions are not sourced |
| Landing gear allowance | 0.4000 | explicit analyst allowance; detailed gear geometry not supplied |
| Payload allowance | 2.0000 | design payload allocation; not an installed/verified payload |
| Unallocated growth/design reserve to 10.5kg ceiling | 2.3512 | budget headroom; not a physical component, excluded from CG |
| TOTAL PLANNED MASS INCLUDING PAYLOAD | 8.1488 | sourced masses + CAD volumes + explicit engineering/payload allowances |
| 10.5kg ALL-UP DESIGN CEILING | 10.5000 | planned mass plus 2.3512 kg unallocated reserve |


**Planned loaded mass including the 2.0kg payload allocation: 8.149kg.** CG including that payload is (X,Y,Z)=(0.0, 2.6, 6.5)mm in the lateral/vertical/flight-axis datum; the nonphysical 2.351kg budget reserve is excluded from CG. The design ceiling is 10.5kg. Against the Phase-9 area-scaled 3km static T/W screen of 1.03955 at 11.5kg, inverse-mass scaling gives approximately **1.139 at 10.5kg**. This is an analytical low-speed margin screen, not installed-thrust or flight evidence.

### Explicit layout and cooling route

- Two battery envelopes (150×50×45mm packaging proxies) occupy the central bay at Z=-337.5 and -177.5mm. The adjacent axial faces leave a 10mm separation; the sourced mass is 0.713kg per pack. Verify the actual pack dimensions and retainable wiring bend radius before fit release.
- ESC PCB center is (0,52,220)mm with 150×150×1.6mm outline, Z145..295mm. Flight PCB is centered at (0,52,345)mm with 140×100×1.6mm outline, Z295..395mm. Their axial envelopes meet without overlap. The separate spreaders are at Y=54.2mm; the layout table records the dimensions and 0.6mm nominal stand-off.
- Cooling route is a dedicated open-ended side-bay tunnel, forward inlet at Z=145mm, wash over the board/spreader bay along the flight axis, and aft outlet at Z=395mm. Two side rails form the airflow guide; the propulsion inlets remain four independent 25×120mm slots. Verify pressure loss, sealing, fan interaction, and board thermal performance on hardware.
- The added hollow lofted lifting-body shell spans 120mm, has 1.5–5mm outer section thickness and 24–120mm chord sections, and is trimmed for both EDF casings. Section stations are in `phase13_lifting_body_sections.csv`. The central pod, nose/tail panels, side rails, and fan cases remain separately identifiable STEP bodies.

## Materials, composite and payload allowances

The ledger separately carries 0.232kg carbon/glass/resin laminate and 0.320kg PLA core across fuselage/lifting shell, EDF casing and four split-inlet branches. Layup estimate: one 200gsm carbon ply plus one 100gsm glass ply per face, resin:fibre mass ratio 0.8, 1.2mm printed-PLA core, 2700kg/m³ Al and 1240kg/m³ PLA assumptions. These are not weighed coupons. Six gearboxes (0.720kg), board population/connectors (0.200kg), spreaders (0.08235kg), harness (0.250kg), mounts (0.350kg), landing gear (0.400kg) and payload (2.000kg) are explicit allowances, not sourced mass facts. Remaining 2.351kg is unallocated mass growth/design reserve beneath the 10.5kg ceiling.

## Stock, machine and CAM

- Six 300×50×16mm 6061-T6 billets; one rotor row/hub per motor/ESC channel. Billet ends X0..25 and X275..300 are reserved for clamps; all cutting coordinates are checked within CAM X25..275 and Y0..50.
- Two 250×100×5mm 6061-T6 plates; one 63-stator set (23/21/19) per EDF. Both nests fit the stock envelope.
- Machine basis: TwoTrees 3018 Pro / GRBL, nominal 300×180×40mm, ER11, spindle 7–9krpm. Programs use S8000, G54 lower-left stock XY and top-face Z0, T1 2mm carbide roughing and T2 0.5mm carbide finishing. Conservative programmed feeds are rough F40/F8 plunge and finish F20/F5 plunge (mm/min). Rotor roughing reaches Z-16 in 0.2mm layers; 0.5mm rotor finish is limited to the top 0.5mm band. Stator 0.5mm finish uses full-depth edge passes with long-flute tooling called out in the NC comments.
- Every NC file was parsed: all X/Y/Z words remain within declared stock and travel depth; rotor clamp margins are clear; G54, S8000, tool declaration, manual-change stop, and program end are present. Validation counts and extents are in `phase13_nc_validation.csv`. This is offline CAM input, not machine-release code; confirm fixtures, flute reach, tabs, workholding, and toolpaths in CAM before any future operation.
- All 12 STEP outputs were reimported; 552 reimported solids were individually checked valid with positive volume. Per-file validity and bounding boxes are in `phase13_step_reimport_validation.csv`.

### Fit and non-fitting geometry screen

No NC cutting-coordinate or stator-plate-nesting non-fit was found: all six rotor programs stay inside X25..275/Y0..50 on their 300×50×16mm billets, and both stator nests/programs stay within 250×100×5mm plates. The raw rotor billet length equals the machine's full nominal 300mm X travel, leaving **zero machine-envelope allowance** for fixture overhang or travel tolerance; actual clamp/workholding fit is not demonstrated and needs a machine-specific setup check. The revised rotor maximum planar B-rep envelope is 87.271mm against the 88mm bore, leaving 0.729mm diametral CAD clearance; axial blade/hub thickness remains 16.000mm against the 16mm billet. These are nominal model clearances without runout/tolerance allowance. No sourced FA4119 shaft/gearbox outline is available, and battery dimensions remain a 150×50×45mm proxy; those physical package fits are **not verified** and are the remaining fit unknowns.

## Deliverables

The STEP assembly, two EDF sets, R30 four-slot inlet, six rotor-billet nests, two stator-plate nests, and 16 NC programs are indexed by `reports/phase13_generation_manifest.json`. Design values and immutability declarations are in `configs/phase13_fixed_powertrain_design.json`. The assembly is a packaging/production concept; motor shaft and gearbox CAD are unavailable, and detailed fit, structural FEA, pressure recovery, thermal test, mass weighing, and flight validation remain open.
