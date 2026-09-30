# Phase 12 — split-inlet EDF / composite airframe CAD-CAM screen

## Evidence and disposition

The Phase-12 results directory contains local mesh/preflight artifacts and an execution receipt, but no OpenFOAM iterations or pressure-recovery values. The receipt is `local-preflight-only-no-cloud-launch`: the required local `checkMesh` gate was unavailable, so no cloud request was made; `bestGeometry` is null. Earlier Phase-10 solver cases also aborted before iterations. Four interchangeable **R30/R35/R40/R45 mm** split-inlet variants are retained. **R30 is the provisional packaging selection** because it passes the conservative reserve-aware area screen; it is pending CFD, not a recovery winner. The Phase-9 recovery target of 0.98 is not claimed. The generated inlets use a smoothly lofted rectangular-to-half-annulus split, smooth area change, and splitter noses to avoid an abrupt junction.

The fixed hardware remains six stock FA4119 KV350 motors, two Turnigy Rapid 6S5000 packs in series (12S1P), and fixed gear ratios 2.35/2.65/2.95. No current, voltage, power, or ratio was changed. Each EDF has 13/12/11 rotor blades at 16mm chord and three 23/21/19 stator rows at 8mm chord. Four 25×120mm slots feed four half-annulus branches at 0.42937kg/s each (0.85874kg/s per EDF, 1.71748kg/s total).

## Projected-area screen

The two coincident 90mm fan silhouettes occupy 63.617cm². Board, heatspreader, support-rail, inlet-lip and fuselage projections are included in the detailed lofted CAD envelope calculation; the two battery package proxies lie inside the coincident disk projection. The CAD area screen includes a 41mm motor-size footprint proxy, but no motor mounting solid is claimed because the motor/shaft drawing was not supplied. Detailed union values are in `phase12_front_area_variants.csv` (R30 67.86cm²; R35 68.44cm²). The Phase-12 preflight's conservative constant-height screen uses the whole generic 10cm² structure allowance plus a 2.5mm outboard protrusion at R35, yielding 79.62cm²; at R30 the protrusion is zero and the bound is 73.62cm². **R30 is retained provisionally to honor the strict <75cm² reserve-aware budget.** The detailed shape projection and coarse preflight bound differ; control/hardware mounting must stay within the remaining projected-area budget, and a final projection check is required when motor mounts are dimensioned. The Phase-9 73.617cm² value is retained as the conservative reference budget.

The execution receipt contains four prepared mesh cases (R35 coarse/medium/fine, R45 medium), lexical dictionary checks only, and null recovery for every case. The planned outlet branch area is 2,778.74mm² from the 90/32 gross-annulus reference; the 88mm physical CAD bore gives 2,638.94mm² per half-annulus, a 5.03% contraction to the fan face. The lofted centrebody models this contraction smoothly. The old preflight case area and current CAD bore are not geometrically identical, so no preflight recovery can be transferred to this CAD.

## Mass, CG, and composite panels

The source CSV gives bare ESC and flight-board masses 0.070163kg and 0.050422kg (total 0.120585kg). It excludes population. The ledger keeps the bare values separate from estimated populated-board mass, heat spreaders, six gearboxes, harness and mounts. Battery dimensions 150×50×45mm are packaging proxies at Z=−337.5/−177.5mm with sourced 0.713kg per-pack mass; verify against the physical packs before fit release. Board and heatspreader envelopes are edge-on in the side cooling bay and are located in the CAD/config for CG screening.

The fuselage and duct panels are modeled as printed-PLA cores with carbon/glass hand-layup; **no 22-plate aluminum body budget is used**. CAD inner+outer face area is 0.4152m² (mid-surface area 0.2076m²). Assumptions are one 200gsm carbon ply + one 100gsm glass ply per face, resin:fibre mass ratio 0.8, and 1.2mm PLA core. Estimated laminate mass is 0.224kg and PLA-core mass 0.309kg. These remain coupon/weighing estimates.

The current component mass ledger estimates 5.734kg and CG (X,Y,Z)=(0.0,3.9,20.7)mm in the model datum (X lateral, Y vertical, Z flight axis). It is not a weighed assembly; 5.766kg remains unallocated to the 11.5kg cap. The Phase-9 worst-R0 T/W of 1.0396 at 11.5kg is retained as an analytical screen, not revalidated with the inlet or mass model. CdA≤0.00090m² at 720km/h remains an unverified target.

## 6061-T6 rotor strength

The CAD retains the frozen Phase-9 720km/h rotor schedule (29,375/33,125/36,360rpm) and unchanged 2.35/2.65/2.95 ratios. The structural proof independently uses the maximum fixed motor-soft-limit-derived speeds (12,500rpm × each ratio) at 1.25×: maximum proof speed 46093.8rpm. It scales the Phase-11 centrifugal-only root stresses by RPM², retains Kt=2.5, and increases modeled root area from 20.961 to 26.5mm² using a thickened root loft and 2mm blend target. The CAD represents the thickened root stations; the blend remains a target requiring detailed joint/FEA closure. Minimum centrifugal-only FOS is 2.63 against 6061-T6 yield 276MPa. Aero bending, fatigue, flaws, attachment, burst containment and testing are excluded; this is not a release stress substantiation.

## Stock nesting and GRBL

- Six 300×50×16mm 6061-T6 billets map one rotor row per motor/ESC channel. Both 25mm ends (X0–25 and X275–300) are reserved for clamping; CAM uses X25–275 only. Each row layout nests its 11–13 blades plus one 32mm hub inside that CAM field, with tool-clearance keep-outs and tabs.
- Two 250×100×5mm 6061-T6 plates map one 63-vane stator set per EDF. Both 7×9 nests fit one plate each. No additional aluminum panel stock is assigned to the body or duct shells.
- G-code uses GRBL, G54 lower-left XY / top-face Z0, 8000rpm, 2mm carbide roughing, and 0.5mm carbide finishing. Rotor blanks and hubs are roughed through 16mm with 0.20mm steps; rotor 0.5mm finishing is limited to the top 0.5mm band. Stator 5mm edges have a conditional full-depth microfinish program requiring a ≥6mm flute. The 16mm rotor walls, twisted airfoil surfaces and 3D inlet/body forming are not completed by these 3-axis paths; they require flip/secondary/5-axis or hand layup/forming as noted in the NC comments.

All G-code is a CAM starting point, not safe-to-run release code. Confirm material, long-tool flute/neck, workholding, tabs, fixture collisions, feeds and all motions manually in CAM. Each file contains M0 manual tool-change, touch-off and spindle-off dry-run notes. **No CNC was run; no cloud solver was launched.**

## Files

STEP assemblies, inlet alternatives, stock nests, and channel-specific NC programs are indexed by `reports/phase12_generation_manifest.json`; design inputs/assumptions are in `configs/phase12_fixed_powertrain_design.json`.

All 18 STEP exports were re-imported with Open Cascade and passed `isValid()`. All 16 NC files were checked for G54 presence, spindle/tool-change blocks, Z depth, and XY coordinates inside the declared stock/CAM region.
