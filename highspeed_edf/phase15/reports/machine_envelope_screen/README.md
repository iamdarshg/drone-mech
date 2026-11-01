# CNC / printer envelope and stock-layout screen

This native FreeCAD model compares the actual Phase 15 Sheet A STEP nest and the already-sliced wing centre-bridge STL with two explicitly different kinds of envelope evidence. It is an envelope/space-planning screen, **not a CAM release, machine-ready fixture, or fabrication authorization**.

## What is grounded in project source

- The imported STEP nest has 100 solids and an actual source bounding box of 250 × 120 × 5 mm. The STEP SHA-256 is `f9a8b9f55d9711dcfafa27f25edf7447ae3189a4db49cd23a72c4497a2c0b233`.
- The A1 mini profile saved in the existing OrcaSlicer evidence reports a 180 × 180 mm printable area and 180 mm printable height. Its profile SHA-256 is `85632b53bc044034e1606685cb83e3bbc405815a7920b5583e0e4bab99e59bb7`. The actual bridge STL from that software slice measures 17.928 × 36.481 × 141.685 mm (source STL SHA-256 `f582a95d8921aa3106b7a30755579406d6b761b49d1d1f2c9268f9454d4fafa9`). It fits the profile bounds and was already accepted by the previous software-slice run. This does not verify the physical printer or a successful print.
- The FreeCAD model includes the actual imported source nest translated to an illustrative XY location (25,30) mm in a dimensioned nominal CNC envelope, a 250 × 120 × 5 mm stock block, and a 10 mm perimeter keepout. The CNC arrangement fits the assumed 300 × 180 × 45 mm box with nominal edge margins; this is a coordinate layout illustration only, not a fixture or clamp design. The source STL is positioned in a separate A1 profile envelope for the printer comparison.

## CNC travel is not identified

Repository records and user-provided context call the router a “233018 Pro” / 3018-class machine, but no manufacturer, exact model, manual, firmware setting, or measured axis travel was found. Accordingly, **actual CNC travel could not be established**. The 300 × 180 × 45 mm box in the model is only a generic 3018-class comparison assumption. Under that assumption, 250 × 120 × 5 mm source nest geometry fits. That conditional fit does not establish that the owner's machine can traverse the nest, that it can cut the material, or that the complete tool/fixture envelope clears.

The perimeter ring is a 10 mm geometric keepout illustration. It is not a clamp design or a collision-checked fixture. Actual machine travel, clamps, datum strategy, machine coordinates, stock squareness/flatness, feeds/speeds, tool-holder reach, runout, tool limits, and controller postprocessor remain unknown. No NC file was generated or posted.

## Reproduce and verify

From the repo root with FreeCAD 1.0.0 installed:

```sh
QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/machine_envelope_screen/build_envelope_model.FCMacro
QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/machine_envelope_screen/verify_envelope_model.FCMacro
```

`envelope_screen.json` records source hashes and bounds. `saved_model_verification.json` independently reopens the saved FCStd and checks the exact nominal envelope boxes, all 100 STEP imports, and that the placed bridge mesh lies inside the profile-derived A1 mini envelope. These are geometry checks only. No machine was operated and no physical test, CNC simulation, cutter/holder collision check, structural test, or build verification occurred.
