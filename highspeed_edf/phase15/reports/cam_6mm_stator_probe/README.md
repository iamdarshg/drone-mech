# 6 mm aluminum stock, single-stator CAM geometry probe

This is a reproducible FreeCAD Path geometry preview for one stator blank from the Phase 15 Sheet A STEP nest. It is a review artifact, **not controller-ready NC, not a cut-approved process, and not fabrication release**. No machine or material was operated.

## Model and stock

- Source STEP: `highspeed_edf/deliverables/phase15_geometry/stock_nests/sheet_A_250x120x5_36rotors_63stators.step`, SHA-256 `f9a8b9f55d9711dcfafa27f25edf7447ae3189a4db49cd23a72c4497a2c0b233`. The STEP contains a 250 × 120 × 5 mm nest with 36 rotor blanks and 63 stator blanks.
- The selected stator blank bounds are 16.0 × 7.074 × 5.0 mm. The macro translates this instance to X=5..21, Y=5..12.074, Z=0..5 mm in an assumed 30 × 20 × 6 mm subblank.
- The face operation removes the nominal 1 mm excess from Z=6 to the source model top at Z=5. The profile starts at Z=6 and ends at the stock bottom Z=0 in passes at Z≈4, 2, and 0 mm. No negative-Z spoilboard overtravel is included.
- The assumed subblank is a geometric subset of the user's 6 mm sheet stock. How that blank is prepared, located, and clamped is unknown.

## Native toolpath and checks

`sheet_A_one_stator_6mm_stock_probe.FCStd` retains the STEP source nest, selected stator instance, native 30 × 20 × 6 mm stock, FreeCAD Path Job, 2 mm tool, face operation, and profile operation. It was generated with FreeCAD 1.0.0. The literal FreeCAD Path commands are retained in `facing_commands.txt` (41 commands) and `profile_commands.txt` (37 commands); they are not postprocessed controller code.

The tool geometry uses the user's 2 mm, two-flute carbide description and an approximate 8 mm flute estimate (the low end of the stated 8–10 mm range). The saved tool shape represents only the flute envelope; the zero shank value is a placeholder to suppress shank geometry. Actual shank/reach, stickout, runout, center-cutting status, and cutter-maker limits are unknown. The user described the stock as 6061 not heat-treated; actual temper and machinability are unverified, while the design generator tags its nest 6061-T6.

`verify_saved_job.FCMacro` reopens the FCStd and writes `saved_job_verification.json`. `stock_envelope_check.py` samples every G2/G3 arc at one-degree increments, checks arc radii, and expands the XY centerline by the modeled 1 mm tool radius. For this assumed subblank, the expanded facing envelope is X=3.974..22.042, Y=4.137..13.105 mm; the expanded profile envelope is X=3..23, Y=3..14.084 mm. Both stay inside X=0..30/Y=0..20 and report zero arc-radius mismatches. This is a planar envelope check only; it does not verify 3D stock removal, shank/holder or clamp collisions, machine travel, workholding, chip evacuation, cutting loads, or final dimensions.

Reproduce from the repository root:

```sh
QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/cam_6mm_stator_probe/make_sheet_a_6mm_stator_cam_preview.FCMacro
QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/cam_6mm_stator_probe/verify_saved_job.FCMacro
python3 highspeed_edf/phase15/reports/cam_6mm_stator_probe/stock_envelope_check.py
```

## Release boundary

The CNC is a 233018 Pro/3018-class machine that can only lightly cut aluminum, but its controller, firmware, postprocessor, travel envelope, spindle RPM range, runout, holders, workholding, and spoilboard datum remain unverified. Feed and speed are intentionally unspecified. The nominal 30 × 20 × 6 mm blank is an assumption. No NC file is postprocessed and this preview does not authorize a cut. It does not establish structural or aerodynamic acceptability of the stator.
