# Phase-15 CNC and FDM manufacturability screen

**Disposition:** FAIL geometry containment / BLOCKED machine-specific CAM and FDM feasibility. Fabrication release is not supported by this screen.

Input CAD/source revision: `6acc0a73b5f34ef1d5b28878dcf4b28dae5f7989`. Geometry and source hashes are recorded in the companion JSON.

## Native geometry findings

All dimensions below were measured by importing the committed STEP BREP, in mm. This is a geometric preflight; no CAM toolpath or sliced print was generated.

| Asset | BREP solids | X × Y × Z bounds | Result |
|---|---:|---:|---|
| `sheet_A` | 100 | 250 × 123.1 × 5 | valid positive-volume BREP |
| `sheet_B` | 100 | 300 × 123.1 × 5 | valid positive-volume BREP |
| `hub_bar` | 7 | 300 × 50 × 16 | valid positive-volume BREP |
| `rotor` | 14 | 76.746 × 77.297 × 16 | valid positive-volume BREP |
| `stator` | 25 | 78 × 78 × 8 | valid positive-volume BREP |
| `duct` | 1 | 82 × 82 × 110 | valid positive-volume BREP |
| `nozzle` | 2 | 82 × 82 × 135 | valid positive-volume BREP |
| `fuselage_shell` | 2 | 194.037 × 76.058 × 84 | valid positive-volume BREP |
| `wing_left` | 1 | 179.67 × 39.091 × 498.607 | valid positive-volume BREP |
| `wing_center` | 1 | 17.928 × 36.481 × 425.054 | valid positive-volume BREP |
| `wing_right` | 1 | 179.67 × 39.091 × 498.607 | valid positive-volume BREP |

## Fabrication blockers

- **sheet_A: FAIL stock containment.** Nominal stock (250.0, 120.0, 5.0) mm; measured (250.0, 120.0, 5.0) mm; 8 of 99 loose blanks extend beyond the raw-stock BREP (maximum 3.1 mm; minimum bounding-box edge margin -3.1 mm).
- **sheet_B: FAIL stock containment.** Nominal stock (300.0, 120.0, 5.0) mm; measured (300.0, 120.0, 5.0) mm; 8 of 99 loose blanks extend beyond the raw-stock BREP (maximum 3.1 mm; minimum bounding-box edge margin -3.1 mm).
- **hub_bar: PASS stock containment.** Nominal stock (300.0, 50.0, 16.0) mm; measured (300.0, 50.0, 16.0) mm; 0 of 6 loose blanks extend beyond the raw-stock BREP (maximum 0.0 mm; minimum bounding-box edge margin 0.0 mm).
- The CNC design requirement is **≥320 × 140 × 45 mm**. User-stated machine identifier is `233018 Pro`; manufacturer and exact model remain unverified, and no measured travel is available. The user reports it can barely cut aluminum. The design brief separately mentions generic 3018-class equipment. Stock dimensions and the nominal class do not establish setup fit; clamps, fixture, tool and approach clearances remain unknown.
- User-reported stock is 6061 aluminum with unspecified temper, as 6 mm and 20 mm sheets (sheet dimensions unknown). The nests require 5 mm sheets and a 300 × 50 × 16 mm hub bar. The 6 mm sheet is 1 mm thicker than the modeled sheet; no 300 × 50 × 16 mm bar is identified. Available stock cannot be matched to the geometry yet.
- User-reported tooling is two-flute PCB-style carbide cutters, nominal Ø0.1–2 mm, plus V-cutters. Flutes are visually estimated at 8–10 mm, not measured. A 6 mm through-cut has only 2–4 mm nominal flute spare under that estimate; a 20 mm through-cut is 10–12 mm deeper. This does not prove flute reach, shank/holder clearance, tool stickout, clamp access, safe feeds/speeds, runout, or suitability for the unspecified 6061 temper. A staged strategy or suitable longer-reach tooling must be evidenced for 20 mm stock.
- Rotor/stator blanks are nested stock geometry only. The design calls for indexed/two-sided 3D machining, but there is no tool library, operation plan, feeds/speeds, machine model, collision check, postprocessor identity or NC file. The stock-sheet overhangs also prevent CAM sign-off as nested.
- The fuselage shell STEP measures only 194.04 × 76.06 × 84 mm, while the geometry notes describe a 640 mm master divided into sections up to 260 mm. The exported shell file does not contain that master or the described print sections.
- The selected printer is the Bambu Lab A1 mini; Bambu Lab lists a 180 × 180 × 180 mm build volume ([official specifications](https://bambulab.com/en/a1-mini/tech-specs)). Rotor, stator, duct and nozzle axis-aligned extents fit the cube. For both wing sectors, even the lower bound on the part's maximum point separation (maximum of vertex-pair distance and any axis extent) exceeds the cube's 311.77 mm diagonal, proving no orientation can fit. The shell's lower bound is between 180 mm and the cube diagonal: its direct fit fails one axis, while a rotated fit is unresolved. It is only the short shell export described above.
- Each exported left/right wing sector is a single BREP solid with a 498.61 mm axis-aligned extent, above the design note's 260 mm maximum print-section length and beyond the A1 mini's orientation-independent size limit. No smaller split STEP artifacts or sliced job are present.
- A FreeCAD 1.0.0 native STEP import independently confirmed the sheet-A nest and tessellated wing/shell surfaces at 0.1 mm linear deflection. FreeCAD's default spline-control-polygon `BoundBox` can report much larger extents; this screen uses tight OCCT `AddOptimal` bounds, which agree with the mesh extents. FreeCAD's `Path` CAM module is installed, but this only proves module availability; no machine configuration, postprocessor or toolpath was executed.
- FDM material/process feasibility remains blocked despite the user-stated printer and known nominal volume: no slicer profile, filament grade/datasheet, material/process qualification, orientation/support plan or sliced job is pinned. Composite and hot-side material requirements need separate qualification.

## Scope and reproducibility

Run from the repository root with `python highspeed_edf/verification/native_manufacturability.py`. The program imports 11 actual STEP assets with CadQuery/OpenCascade, records per-file SHA-256 and tight `BRepBndLib.AddOptimal` bounds/volumes, checks loose-blank BREP bounding boxes against the stock solid, then independently imports sheet A and compares selected print-part bounds against FreeCAD tessellation at 0.1 mm linear deflection. It writes JSON and this report in the Phase-15 reports directory.

Stock containment checks use bounding boxes only; part-to-part spacing, cutter compensation, fixtures, machine travel, collision-free toolpaths and sliced print volume are not evaluated. Do not infer fabrication readiness from STEP validity or this screen.
