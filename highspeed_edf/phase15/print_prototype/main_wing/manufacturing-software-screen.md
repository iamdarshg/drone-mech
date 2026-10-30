# Phase 15 manufacturing software and handoff screen

This records a software and envelope screen for the experimental main-wing partitions. It does not qualify the geometry, material, toolpath, printer process, assembly, or structure for fabrication or flight.

## A1 mini print path

OrcaSlicer 2.4.2 (free, open source) is the strongest fit among the available rootless options because its bundled profiles include the Bambu Lab A1 mini, several nozzle sizes, material profiles, and standard layer-height presets. Its bundled A1 mini 0.4 mm nozzle profile reports a 180 × 180 mm printable area and 180 mm height; the stock 0.20 mm Standard preset is named `0.20mm Standard @BBL A1M`. These are stock presets only, not settings selected for this wing.

I attempted to start the official Linux AppImage with `--appimage-extract-and-run --help`. It stopped before launching because the host lacks `libwebkit2gtk-4.1.so.0` and `libjavascriptcoregtk-4.1.so.0`. Consequently no orientation, supports, adhesion, material/process selection, preview, time estimate, or G-code was generated. The STL below is only a mesh exchange export from the pinned STEP part, not slicer output.

The sample is `wing_centre_bridge_x1_z1.step`, imported as one valid CadQuery/OCP solid and exported to binary STL at 0.05 mm linear and 0.1 rad angular tessellation tolerances. Its STEP bounds are 17.928 × 36.481 × 141.685 mm, below the nominal A1 mini envelope in this orientation. That box check does not establish bed contact, support strategy, printability, tolerances, warping, strength, or fit. FreeCAD 1.0.0 reimported the mesh as a closed solid with no detected self-intersections; it contains 334 facets and is 16,784 bytes. STL has no unit metadata; the intended coordinate unit is millimetres.

- STEP SHA-256: `93284123106b832534c072bd9b8325df825c31111df20d1a7abddcac59f124d3`
- STL SHA-256: `f582a95d8921aa3106b7a30755579406d6b761b49d1d1f2c9268f9454d4fafa9`

For a future software-only slice review, OrcaSlicer or Bambu Studio with the exact A1 mini, nozzle, and filament profile is appropriate. A slice would still need human review and physical process qualification before manufacturing use.

## 3018-class CNC path

FreeCAD 1.0.0 is installed rootless and includes its CAM workbench; it is the best available free starting point for 3018-class CAM because it can create and post-process operations for a selected controller. No operation, feeds/speeds, stock setup, post-processor, or NC file was created in this screen. The actual 3018 model, controller/firmware, travel, spindle, workholding, cutter manufacturer, flute count, and runout are unspecified, so a safe machine profile cannot be inferred.

The stated 6/20 mm 6061 stock and 0.1–2 mm cutters do not by themselves define a workable process. The 0.1 mm end of that range is especially fragile for aluminum, and 8–10 mm axial engagement would need to be justified against the exact tool maker's limits, flute length, stick-out, spindle speed, rigidity, and chip evacuation. The A1 mini sized STEP pieces also do not imply a CNC-friendly part: their thin curved surfaces, fixturing, stock allowance, multiple setups, and material-removal strategy are unresolved. Do not treat this report or the mesh as a machining plan.

## Current handoff boundary

The segmentation remains planar butt cuts without joiners or clearances. There is no printer slice, CNC toolpath, structural evidence, or physical validation. The STEP and STL are geometry handoff files for continued design and software review only.
