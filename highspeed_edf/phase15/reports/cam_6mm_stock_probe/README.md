# 6 mm aluminum stock, single-rotor CAM geometry probe

This is a reproducible FreeCAD Path geometry preview for one rotor blank from the existing Phase 15 Sheet A STEP nest. It is a review artifact, **not controller-ready NC, not a cut-approved process, and not fabrication release**. No machine or material was operated.

## Model and stock

- Source STEP: `highspeed_edf/deliverables/phase15_geometry/stock_nests/sheet_A_250x120x5_36rotors_63stators.step` (SHA-256 `f9a8b9f55d9711dcfafa27f25edf7447ae3189a4db49cd23a72c4497a2c0b233`). The STEP contains a 250 × 120 × 5 mm nest with 36 rotor blanks and 63 stator blanks.
- The isolated rotor blank has source bounds 29.0 × 8.564 × 5.0 mm. The CAM macro moves that instance by +4 mm in X and Y; the saved model bounds are X=5..34, Y=5..13.564, Z=0..5 mm.
- The native CAM stock is an assumed 40 × 20 × 6 mm subblank at X/Y/Z=0. It models one blank cut from the user's stated 6 mm sheet, rather than assuming the full 250 × 120 mm sheet fits the machine. Preparing this subblank and locating it on the machine are unverified.
- The face operation removes the nominal 1 mm excess from Z=6 to the source model top at Z=5. The profile path starts at Z=6 and ends at the stock bottom Z=0 in passes at approximately Z=4, 2, and 0 mm. The saved Path reports a 2 mm stepdown; its motion command Z range is 0..11 mm. There is no negative-Z spoilboard overtravel in this preview.

## Native toolpath and checks

`sheet_A_one_rotor_6mm_stock_probe.FCStd` retains the imported source geometry, selected part, 40 × 20 × 6 stock, native FreeCAD Job, native 2 mm tool bit, face operation, and profile operation. It was generated with FreeCAD 1.0.0. Literal operation commands are retained as `facing_commands.txt` (61 commands) and `profile_commands.txt` (43 commands). These are FreeCAD Path commands, not postprocessed controller code.

The modeled cutter uses the user's 2 mm, two-flute carbide description and an approximate 8 mm flute length at the low end of the user's 8–10 mm estimate. FreeCAD represents only an 8 mm flute envelope; its shank diameter is a zero placeholder to suppress shank geometry, not a measurement. Actual cutter reach, shank, stickout, runout, center-cutting status and maker limits are unknown. The user's stock was described as 6061 not heat-treated; actual temper and machinability are unverified, while the CAD generator labels its nest material 6061-T6.

`verify_saved_job.FCMacro` reopens the saved FCStd. `saved_job_verification.json` records the persisted stock bounds, part bounds, operation command counts and tool values. `stock_envelope_check.py` independently samples the retained G2/G3 arcs at one-degree increments, checks arc radii, and expands the XY path by the modeled 1 mm cutter radius. The sampled planar cutter envelope remains inside the assumed blank: facing X/Y bounds 3.972..35.035 / 3.972..14.566 mm; profile bounds 3.000..36.000 / 3.000..15.547 mm. Both had zero sampled arc-radius mismatches. This is only a 2D envelope check; it does not simulate stock removal, verify the holder/shank, fixtures/clamps, machine travel, spindle collision, chip evacuation, or dimensional tolerances.

Reproduce from the repository root:

```sh
QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/cam_6mm_stock_probe/make_sheet_a_6mm_cam_preview.FCMacro
QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/cam_6mm_stock_probe/verify_saved_job.FCMacro
python3 highspeed_edf/phase15/reports/cam_6mm_stock_probe/stock_envelope_check.py
```

## Release boundary

The CNC was identified as a 233018 Pro/3018-class machine that can only lightly cut aluminum, but its controller, firmware, postprocessor, travel envelope, spindle RPM range, runout, tool holders, workholding and spoilboard datum have not been verified. Feeds/speeds are intentionally unspecified. The chosen 40 × 20 mm blank is a geometric assumption only. No NC file is postprocessed, no cut is authorized by this artifact, and it does not establish that the rotor itself is structurally or aerodynamically acceptable.
