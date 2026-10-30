# Phase-15 sheet nest bounds correction

The original sheet STEP nests placed all 36 rotor profiles using their nominal 8.2 mm chord height and an origin at Y=1 mm. The actual parametric profile extends to local Y=-4.1 mm, so the eight blanks in the first rotor row crossed the sheet's Y=0 edge by 3.1 mm. Native STEP inspection confirmed eight out-of-bounds blanks in each original sheet layout (16 placements across the two files). Their original STEP SHA-256 values were `sheet_A`: `57d27f7fb433158b25809b10be02ca24e239934b7925de758b049869a4236acd`; `sheet_B`: `b72b319bc7f84cb2cafaa81a234fce4fe0def66f0b407459a648b63372389ae4`. The rotor and stator profile shapes and blank counts were otherwise unchanged.

The generator now derives the blank footprint bounds from each profile before placement. The rotor origin is shifted to put the measured minimum profile Y at the 1 mm stock margin, and rotor-row pitch is based on the measured profile height plus the declared 1.5 mm spacing. The stator group starts 1.5 mm after the last rotor row; its existing row pitch is retained because it already exceeds the required spacing for the measured stator profile. The generator checks each placed blank against the stock envelope and margin before writing STEP.

The updated STEP files retain the declared sheets and quantities: 250×120×5 mm and 300×120×5 mm, each with 36 rotor and 63 stator blanks plus raw stock. Native CadQuery/OCC re-import verified, per sheet:

- all 100 solids are positive-volume valid STEP solids (one stock solid plus 99 blanks);
- all 36 rotor and 63 stator blanks fit inside X/Y stock bounds with the 1 mm edge margin and fit within the 5 mm thickness;
- no blank pair can be closer than 1.5 mm; for each sheet, the checker evaluated exact OCC distances for 126 pairs whose bounding-box lower bound was at or within 1e-6 mm of the 1.5 mm threshold (including the adjacent-row/column pairs at the threshold), and used conservative bounding-box lower bounds to rule out failures for all other pairs;
- the minimum exact OCC distance among those threshold pairs was 1.500000 mm; no out-of-bounds blanks or clearance failures were found.

Run `python highspeed_edf/deliverables/phase15_geometry/reports/verify_stock_nest_bounds.py` to regenerate the native evidence at `phase15_stock_nest_bounds_validation.json`. The STEP file hashes and per-blank bounds are recorded there. `phase15_stock_nest_views.png` is a top-down projection rendered from the re-imported STEP meshes.

This correction changes only sheet nesting coordinates and row pitch. It does not alter rotor/stator profile geometry, counts, stock dimensions, or the aircraft assembly. The results validate solid geometry, stock bounds and blank spacing. They do not establish a finished-part toolpath, cutter engagement, workholding, machine travel, material suitability, machining quality, or production readiness; the STEP nests remain geometry-only.
