# Phase 10 — fixed-powertrain EDF / fuselage CAD and CAM package

## Package contents

- `step/phase10_edf_A_configuration.step` and `step/phase10_edf_B_configuration.step` — editable STEP B-rep assemblies for the two installed EDF modules, including the mirrored side-inlet elbow for each module.
- `step/phase10_full_assembly.step` — both modules, lifting-body interface and module collars in the installed coordinate system.
- `stock_layouts/` — editable STEP stock-nest layouts; the transparent stock envelope is deliberately overlaid with the cut blanks for visibility.
- `gcode/` — separate GRBL rough/finish files for each EDF's rotor-blade billet(s) and stator plate.
- `reports/phase10_geometry_audit.json` and `phase10_manifest.json` — machine-readable gate/nesting summary and file inventory.
- `optimization/phase10_generate_deliverables.py` — local CadQuery source for rebuilding the CAD, nests and NC files.

All STEP files were re-imported with Open Cascade and passed `isValid()`. The two EDF STEP files each contain 112 solids; the installed assembly contains 227 solids. Rotor billet layouts contain 24 blanks in billet 1 and 12 in billet 2 per EDF; stator plate layouts contain 63 vanes per plate, in addition to the stock envelope.

## Fixed hardware and modeled rows

The powertrain remains locked at six stock FA4119 KV350 motors and two Turnigy Rapid 6S 5000mAh packs in series (12S1P, 5Ah). The modules each contain three rotor rows with 13/12/11 blades, 16mm chord, and the Phase-9 720km/h RPM schedule (29,375 / 33,125 / 36,360 rpm), plus three 8mm-chord stator rows (23/21/19 vanes). Rotor and stator vanes are lofted, twisted, cambered airfoil solids with separate rotor hubs and stator inner/tip rails.

The housing is 90mm OD with an 88mm bore and 1mm nominal casing wall. A 0.4mm rotor-tip clearance is modeled. The 29mm blade envelope includes 1.4mm root engagement into the 32mm hub; the working gaspath span is 27.6mm. Consequently, the actual annulus is 52.779cm² per EDF rather than the Phase-9 55.575cm² per EDF that treated the full 90mm envelope as the flow bore. A simple actuator-disk area-only scaling of the Phase-9 worst-case 3km T/W gives approximately 1.022 at 11.5kg; that is a sensitivity, not a new thrust solution.

The 8mm hub bore in the CAD is a provisional shaft-interface placeholder because the provided Phase-9 inputs do not include the motor/gearbox shaft drawing. Six motor mounting envelopes, pack outlines, populated electronics, gearboxes, and measured structural materials likewise cannot be dimensioned from the supplied inputs; do not treat the STEP assembly as a released motor/battery installation drawing.

## Requirement disposition — important geometry conflicts

The Phase-9 projected-area result (63.617cm² coincident fan disks + 10cm² structure allowance = 73.617cm²) is retained as the nominal screen. It does **not** include the physical packaging of the specified 225mm-radius side turns. With a 50mm minimum projected transition width, each turn occupies at least a 180mm outboard strip beyond the 90mm disk radius. The two mirrored transitions therefore add a conservative 180cm² front-view envelope. The installed fan-plus-transition lower bound is about **243.6cm²** before adding the fuselage; carrying the existing 10cm² structure allowance gives a 253.6cm² envelope. The complete installed design therefore **fails the <75cm² projected-area gate** with the 50×120mm slots and R225 turns as currently specified. The CAD includes the real turns and makes this conflict visible; the earlier 73.62cm² candidate is not a full-airframe projection.

The nominal 90mm casing / 32mm hub / 29mm radial span also has no room for a useful casing wall and tip clearance if all 29mm are active flow span. This model preserves 29mm overall blade extent by embedding 1.4mm at the hub and uses the realistic 88mm bore/0.4mm tip gap, leaving 27.6mm active span. The resulting reduced annulus is recorded in the audit.

The all-up 11.5kg cap and CdA≤0.00090m² at 720km/h remain **unverified targets**. Phase-9 mass accounting is a screen, not a weighed assembly; the body material density, six motor/gearbox interfaces, wiring, and mounted electronics are not closed. No CFD, wind-tunnel, or flight validation was run. The thin lifting-body surface is a packaging interface concept, not a structural airframe release.

## Stock nesting and purchase quantity

The CNC layouts are conservative collision-free 2mm-tool nests, not a claim that arbitrary common-line/optimized nesting has been exhausted:

- Each EDF has 36 rotor blanks. Each 250×50×16mm billet layout uses a 6×4 keep-out grid with 2.5mm clearance between the 29×8.2mm planform envelopes; billet 1 carries 24 blanks and billet 2 carries the remaining 12. The supplied, reproducible CAM plan therefore uses **two billets per EDF (four total)**.
- Each EDF has 63 stator vanes. Each 250×100×5mm plate layout has an 8×10 capacity and nests all 63; **one plate per EDF (two total)** is sufficient.
- One plate/billet pair shared across both EDFs is impossible: the two modules' generated rotor profiles have 15,569mm² combined planform area, already larger than one billet's 12,500mm² area before kerf or holding tabs.
- Two pairs total provide only two billets, while the safe NC nest delivered here uses four. For the provided 2mm-tool paths, procure **two 250×100×5mm plates and four 250×50×16mm billets** (two full pairs plus two extra billets). This is the purchase quantity for the delivered conservative nest; a different validated optimized/common-line toolpath could potentially reduce billet count, but it is not represented by these files.

The stock layouts and G-code cover 2.5D blade/vane **blank perimeters only**. They do not machine the full twisted 3D airfoil surfaces, hub interfaces, 90mm casing, stator rails, inlet elbows or fuselage. Those parts need separately selected fabrication processes/materials and additional stock. In particular, the 0.5mm toolpath is only a 0.5mm-deep top-edge finishing band; it is not represented as a safe full-depth finish in 5mm or 16mm stock.

## GRBL / TwoTrees 3018 Pro setup

The NC files assume a GRBL controller, nominal 300×180×40mm travel, 775 spindle, ER11, two-flute carbide cutters, and a conservative **7000rpm**. The individual 250×50 and 250×100 XY stock envelopes fit the nominal bed. G54 is set with XY at the stock lower-left and Z0 at the stock top.

Roughing uses a 2mm carbide end mill, 55mm/min feed and 0.20mm stepdown for the rotor billets; the stator plate uses 60mm/min and 0.25mm stepdown. Plunge rates are 12/14mm/min respectively. Rough contours leave 0.25mm radial stock and 1mm-high tabs on the final through-pass. The 16mm billet path requires at least 18mm usable flute/neck reach; verify tool stickout, flute length, collet clearance, workholding and the machine's actual Z envelope before use. The 0.5mm carbide finish file runs at 20mm/min, 0.10mm Z steps, and stops at Z−0.5mm.

The stock material/alloy was not specified in the candidate inputs, so feeds are conservative CAM starting values and still require confirmation against the actual material and cutter maker's chip-load guidance. Do not use these files on carbon fibre or unknown abrasive stock. The 3018 has no assumed automatic tool changer: each file pauses with M0 for manual installation and re-touch-off of G54 Z0. Clamp only outside the paths and tabs. Before cutting, run an air/dry simulation with spindle off and stock removed or with a verified safe Z offset that keeps the deepest programmed point above the stock; check every move against clamps and actual travel, then restore Z0 to the stock top. Remove parts and tabs manually after the rough operation. No CNC was connected to or run for this task.

## Rebuild

From `highspeed_edf`, run:

```powershell
python optimization/phase10_generate_deliverables.py
```

This is an offline CadQuery build. It does not launch local or cloud solvers.
