# Phase 15 manufacturing software and handoff screen

This records a software and envelope screen for the experimental main-wing partitions. It does not qualify the geometry, material, toolpath, printer process, assembly, or structure for fabrication or flight.

## A1 mini software slice

A real OrcaSlicer 2.4.2 software slice was completed for `wing_centre_bridge_x1_z1.stl` using the bundled Bambu Lab system profiles as provisional assumptions: `Bambu Lab A1 mini 0.4 nozzle`, `0.20mm Standard @BBL A1M`, `Bambu PLA Basic @BBL A1M`, and the machine profile's default `Textured PEI Plate`. The printer, nozzle, plate and filament were not confirmed against physical hardware or stock. The official Linux AppImage required missing WebKitGTK libraries; Debian 13 runtime packages were extracted under `/tmp` and used rootlessly. The AppImage SHA-256 and extracted package versions are recorded in the evidence manifest.

The run enabled OrcaSlicer's automatic orientation and arrangement. Its CLI selected orientation vector `(0, 0, -1)` and placed the single part on plate 1. The exact inherited effective machine, process and filament settings are saved with the output. Key values are a 0.4 mm nozzle, 0.20 mm layer height, two wall loops, five top and three bottom shell layers, 15% crosshatch infill, supports disabled, automatic 5 mm brim, 220 °C nozzle, and 65 °C textured plate. The output is a valid completed slice: `result.json` reports `return_code: 0`, `error_string: Success.`, and an empty `warning_message`.

The generated G-code estimates 1 h 27 min 30 s of model printing and 1 h 33 min 29 s total, with 708 layers and 15.87 g (12.59 cm³) of filament. These are slicer estimates under the provisional settings. The sample STL is a mesh exchange export of `wing_centre_bridge_x1_z1.step`, tessellated at 0.05 mm linear and 0.1 rad angular tolerances; its SHA-256 is `f582a95d8921aa3106b7a30755579406d6b761b49d1d1f2c9268f9454d4fafa9`. The source STEP SHA-256 is `93284123106b832534c072bd9b8325df825c31111df20d1a7abddcac59f124d3`. The piece bounds are 17.928 × 36.481 × 141.685 mm; STL does not store units, and millimetres are intended.

The reproducibility record, profile snapshots, slicer log, result JSON and G-code are in [`software_slice/`](software_slice/). The G-code is retained as software evidence for review; it is not an instruction to print. The slice does not establish that the selected orientation is suitable, supports are unnecessary, adhesion will succeed, dimensions will be accurate, or the part will print, assemble or carry load. No printer, CNC machine or other hardware was used.

## 3018-class CNC path

FreeCAD 1.0.0 is installed rootless and includes its CAM workbench; it is the best available free starting point for 3018-class CAM because it can create and post-process operations for a selected controller. No operation, feeds/speeds, stock setup, post-processor, or NC file was created in this screen. The actual 3018 model, controller/firmware, travel, spindle, workholding, cutter manufacturer, flute count, and runout are unspecified, so a safe machine profile cannot be inferred.

The stated 6/20 mm 6061 stock and 0.1–2 mm cutters do not by themselves define a workable process. The 0.1 mm end of that range is especially fragile for aluminum, and 8–10 mm axial engagement would need to be justified against the exact tool maker's limits, flute length, stick-out, spindle speed, rigidity, and chip evacuation. The A1 mini sized STEP pieces also do not imply a CNC-friendly part: their thin curved surfaces, fixturing, stock allowance, multiple setups, and material-removal strategy are unresolved. Do not treat this report or the mesh as a machining plan.

## Current handoff boundary

The segmentation remains planar butt cuts without joiners or clearances. A software slice now exists for one wing segment. No printer run, CNC toolpath, structural evidence, or physical validation was performed. The STEP, STL, and G-code are geometry and software-review artifacts only; fabrication and flight release remain blocked.
