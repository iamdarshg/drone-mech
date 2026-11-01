# Subset CAM buildability screen

This screen evaluates only the manufacturing envelope of existing sample parts and the user's reported tools and machines. It does not redesign the aircraft or release any part for fabrication. All machine work is simulation / software preview only: **no controller-ready NC, no cut authorization, no physical machine or printer test**.

## Machine and inventory assumptions

The CNC is described by the user as a “233018 Pro”. Its exact maker and model are unverified. SainSmart's official [Genmitsu 3018-PRO listing](https://www.sainsmart.com/products/sainsmart-genmitsu-cnc-router-3018-pro-diy-kit?variant=13086288150601) gives a 300 × 180 × 45 mm work area for its 3018-PRO option (retrieved 2026-11-01). This is a conditional reference only if the owner's exact machine is that model and option. The existing stock-layout screen fits the 250 × 120 mm source nest in that conditional XY work envelope, with illustrative 10 mm keepout, but the exact machine travel, Z clearance after stock/fixture installation, and actual fixture/tool envelopes remain unverified.

User-reported inventory: 6 mm and 20 mm 6061 sheet, described as not heat-treated; two-flute carbide PCB cutters ranging from 0.1 to 2 mm; and an A1 Mini. The user's latest flute-length estimate is 8–10 mm for larger cutters, with shorter flutes on smaller diameters. This is not measured, and the user's earlier provisional assumption was 5 mm. No flute length is assigned to every cutter diameter. The source CAD generator labels its Sheet A nest “6061-T6”, which conflicts with the user-reported material condition. Actual temper and hardness need confirmation before process selection. Sheet XY dimensions were not supplied.

## 6 mm aluminum subset previews

Two real FreeCAD Path jobs use selected source geometry from the 250 × 120 × 5 mm Sheet A STEP nest: one 29.000 × 8.564 × 5 mm rotor and one 16.000 × 7.074 × 5 mm stator. They preview fitting each 5 mm part into assumed 6 mm-thick substock, with a 2 mm, two-flute carbide tool model. The saved CAM jobs set 2 mm step-down, face the nominal 1 mm excess, and profile to Z=0. The saved-path checker expands XY motion by the 1 mm modeled cutter radius and reports the path envelope inside the assumed 40 × 20 mm rotor blank and 30 × 20 mm stator blank, with no arc-radius mismatches.

At the latest 8–10 mm flute estimate for the 2 mm cutter, a nominal 6 mm axial engagement leaves 2–4 mm of flute-length difference. Under the user's earlier 5 mm assumption, it would be 1 mm short. Neither estimate is measured or a tool-maker limit; useful tool reach, stick-out, shank/holder clearance, runout, cutting loads, feed/speed, workholding, and stock surface condition are unknown. The existing paths end at the modeled stock bottom Z=0 and omit negative-Z spoilboard overtravel, so they do not establish full part separation. The planar checker is not a 3D stock-removal, holder, fixture, or machine collision simulation. These jobs are geometry previews only.

## 20 mm stock and tool reach

The existing source rotor/stator blanks are 5 mm thick; choosing 20 mm sheet does not change the required part geometry. For the largest, 2 mm cutter, using the user's provisional 8–10 mm flute estimate strictly as a reach screen:

| Scenario | Geometric reach result | Status |
| --- | --- | --- |
| One-sided 20 mm through-profile | 10–12 mm deeper than the estimated flute length | Does not fit the assumed flute reach |
| Two-sided cut, 10 mm from each face | 8 mm flutes leave a nominal 4 mm mid-web; 10 mm flutes meet at zero nominal clearance | Not a through-cut plan; requires registered flips and additional reach/clearance |
| Two-sided cut while reserving 2 mm flute length per face | Leaves a nominal 8 mm web with 8 mm flutes, or 4 mm with 10 mm flutes | Still not through-cut; 2 mm is an illustrative reserve, not a safety factor |
| Face down 20 mm stock to the source 5 mm blank | 15 mm total removal, arithmetically 7.5 mm per face if balanced; nominal flute difference 0.5–2.5 mm | Only a thickness arithmetic screen; no facing plan or fixture exists |

A staged Z step-down does not make a cutter's flute or shank reach longer. A two-face process needs a rigid flip fixture, repeatable datums/registration, remaining-web strategy, cutter reach, and a final severance operation. A zero-web calculation is exact geometry with no allowance for registration error, deflection, runout, or breakthrough. No 20 mm stock CAM job was generated. The existing 6 mm CAM previews cannot be extrapolated to 20 mm stock.

## A1 Mini part-envelope screen

The official [Bambu Lab A1 mini quick-start guide](https://cdn1.bambulab.com/documentation/quick-start-f507128172bdf/Quick%20start%20guide%20-%20A1%20mini-EN.pdf) lists an 180 × 180 × 180 mm build volume (source identified/retrieved 2026-11-01; this environment's direct PDF fetch returned HTTP 402). The repository's bundled A1 mini profile independently records 180 × 180 mm printable area and 180 mm build height. The A1 results below compare all 15 wing segmentation STEP files and 10 fuselage-shell segment STEP files to that axis-aligned profile cube.

The verifier re-imports the exact STEP files with FreeCAD 1.0.0 `Part.insert`, records each STEP length unit, imported solid count, and zero document placement, then tessellates each trimmed B-rep at 0.05 mm deflection and compares the surface mesh extents with the committed segmentation manifest. All 25 files use millimetre units, have expected solid counts and zero FreeCAD document placements, and their tessellated bounds agree with the manifests within 0.02 mm. Some STEP files contain representation-relationship transform entities; those are counted in the JSON, while the imported document placement and final tessellated component extents are independently checked. The largest wing piece extent is 166.202 mm; the largest fuselage piece extent is 144 mm. All listed part bounds fit the A1 Mini cube. This is only a geometric envelope check: it does not establish orientation suitability, adhesion, print time/material, nozzles, joint clearances, assembly, strength, or successful printing.

The JSON retains a diagnostic `freecad_raw_occ_control_pole_span_mm` separately from the actual tessellated part extents. FreeCAD’s untessellated `Shape.BoundBox` can include B-spline control poles outside trimmed faces (for the first wing piece this diagnostic span is 933.226 × 88.643 × 1906.749 mm). This is an overestimate and is explicitly not treated as the part dimension or used for fit. The checked trimmed-face mesh and independent CadQuery manifest agree at 89.835 × 37.739 × 123.185 mm. Fit assertions use tessellated extents cross-checked against source manifests. Some fuselage segment STEP files contain multiple solids; those are recorded as-is. The separate fuselage report notes inherited disconnected shell topology. No joinery, seam strength, or complete airplane assembly is established by this envelope screen.

| Part group | STEP part | Native tessellated X × Y × Z bounds (mm) | Solids |
| --- | --- | ---: | ---: |
| main_wing | `wing_left_sector_x1_z1.step` | 89.835 × 37.739 × 123.185 | 1 |
| main_wing | `wing_left_sector_x1_z2.step` | 89.835 × 39.077 × 166.202 | 1 |
| main_wing | `wing_left_sector_x1_z3.step` | 89.835 × 28.790 × 166.202 | 1 |
| main_wing | `wing_left_sector_x2_z1.step` | 89.835 × 35.072 × 166.202 | 1 |
| main_wing | `wing_left_sector_x2_z2.step` | 88.459 × 30.399 × 166.202 | 1 |
| main_wing | `wing_left_sector_x2_z3.step` | 67.101 × 6.077 × 25.869 | 1 |
| main_wing | `wing_centre_bridge_x1_z1.step` | 17.928 × 36.481 × 141.685 | 1 |
| main_wing | `wing_centre_bridge_x1_z2.step` | 17.925 × 35.775 × 141.685 | 1 |
| main_wing | `wing_centre_bridge_x1_z3.step` | 10.151 × 23.885 × 141.685 | 1 |
| main_wing | `wing_right_sector_x1_z1.step` | 89.835 × 35.072 × 166.202 | 1 |
| main_wing | `wing_right_sector_x1_z2.step` | 88.459 × 30.399 × 166.202 | 1 |
| main_wing | `wing_right_sector_x1_z3.step` | 67.101 × 6.077 × 25.869 | 1 |
| main_wing | `wing_right_sector_x2_z1.step` | 89.835 × 37.739 × 123.185 | 1 |
| main_wing | `wing_right_sector_x2_z2.step` | 89.835 × 39.077 × 166.202 | 1 |
| main_wing | `wing_right_sector_x2_z3.step` | 89.835 × 28.788 × 166.202 | 1 |
| fuselage_shell | `fuselage_shell_segment_01_port.step` | 105.892 × 90.220 × 120.000 | 1 |
| fuselage_shell | `fuselage_shell_segment_02_starboard.step` | 105.892 × 90.220 × 120.000 | 1 |
| fuselage_shell | `fuselage_shell_segment_03_port.step` | 104.346 × 88.560 × 50.902 | 1 |
| fuselage_shell | `fuselage_shell_segment_04_starboard.step` | 104.346 × 88.560 × 50.902 | 1 |
| fuselage_shell | `fuselage_shell_segment_05_port.step` | 95.282 × 90.817 × 111.933 | 3 |
| fuselage_shell | `fuselage_shell_segment_06_starboard.step` | 95.282 × 90.817 × 111.933 | 3 |
| fuselage_shell | `fuselage_shell_segment_07_port.step` | 93.235 × 88.033 × 136.000 | 3 |
| fuselage_shell | `fuselage_shell_segment_08_starboard.step` | 93.235 × 88.033 × 136.000 | 3 |
| fuselage_shell | `fuselage_shell_segment_09_port.step` | 93.235 × 87.979 × 144.000 | 2 |
| fuselage_shell | `fuselage_shell_segment_10_starboard.step` | 93.235 × 87.979 × 144.000 | 2 |

Full per-part boxes, STEP SHA-256 values, placements, units, solid counts, raw and tessellated bounds, manifest comparison differences, and triangle counts are in `native_part_extent_verification.json`.

## Reproduce and verify

From the drone-mech repository root with FreeCAD 1.0.0 and Python 3:

```sh
QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/cam_buildability_screen/build_cad_extent_screen.FCMacro
bash highspeed_edf/phase15/reports/cam_buildability_screen/run_acceptance_subset.sh
```

The checker validates all 25 STEP hashes, imported solid counts, unit/placement records, A1 envelope comparisons, both existing 6 mm job geometry reports, planar swept envelopes, and the reach arithmetic. Inputs are hashed in `screen_verification.json`; output file hashes and source commit are in `artifact_manifest.json`.

## Inputs still required before process planning

- CNC nameplate, manufacturer/manual, actual X/Y/Z travel and travel with the spindle, and controller/firmware and postprocessor.
- Stock XY size, measured thickness/flatness, confirmed 6061 temper/hardness, and a stock-to-datum scheme.
- Exact tool make/model and drawings for each diameter: cutting length/flute length, shank diameter, usable reach, stick-out, helix/end geometry, center-cutting status, runout, and maker's aluminum limits.
- Spindle range/power, collet/holder, measured runout, allowed RPM and feeds, step-down/step-over limits, chip evacuation and cooling plan.
- Rigid workholding that fits the actual machine, cutter/holder/clamp collision checks, safe hold-down outside the tool path, spoilboard/datum, and registered flip fixture if two-sided setups are intended.
- A selected CAM postprocessor and controller-native dry-run/simulation before any controller code; no physical cut is authorized by this report.
- For printing: verified A1 mini hardware/nozzle/plate, selected filament and process, seam/joint fit design, and physical test coupons or printed parts before structural use.
