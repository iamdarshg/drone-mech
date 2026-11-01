# Phase-15 visual CAD and shop-envelope review

**Disposition: experimental layout and CAM previews only; fabrication is blocked.** This report records a direct visual review of the native Phase-15 STEP render and the existing FreeCAD CAM/machine-envelope artifacts. It makes no geometry changes and does not authorize a CNC cut, print, hardware test, or flight.

## Source pins and reproduction

- Repository HEAD during geometry/render review: `dfb02c957e61596db5f88448ac8bdc87f1be11b6`; current-main source geometry is pinned independently by the STEP hash below, so later documentation-only commits do not alter the reviewed assembly.
- Native assembly STEP SHA-256: `9b83f3bfa5ea261c2055152c9fdd2147b9e16819634715c3c4ae23b45deae772`.
- Native render script SHA-256: `98563a8a79a27dd8ce1b1a7c9a8193cc3037a756f49e6b3bbf73dc153b09c160`.
- Existing render manifest: `highspeed_edf/deliverables/phase15_geometry/native_visual/images/render_manifest.json`; it identifies 73 named STEP assembly components, 516 solids and 61,534 triangles. The four render hashes are recorded there.
- Reviewed CAM files: rotor probe SHA-256 `a505062dc10a97dad13c2aeec420b72a2e7f8157c571525275e6f7502ebe383f`; stator probe `0a186b382e4023ab32abe23aea955d1c39d461e3b487891ab7338ff585716b5e`.
- Machine-envelope report source: `highspeed_edf/phase15/reports/machine_envelope_screen/envelope_screen.json`, SHA-256 `41736be0191ed1a431fbb40462be01c2f5e46d347bdcf6569f2b753b6f844744`.

Re-render the native views from the pinned STEP with the documented CadQuery/Blender dependencies:

```sh
python3 highspeed_edf/deliverables/phase15_geometry/native_visual/scripts/render_native_views.py \
  --step highspeed_edf/deliverables/phase15_geometry/step/phase15_airframe_full_assembly.step \
  --output-dir /tmp/phase15-native-visual-review \
  --blender /usr/bin/blender
```

The committed view images are opaque projections. The plan view hides the four named outer skin parts; the other full-assembly views hide none. This is useful for recognizing envelopes, but does not expose every contact, cavity, fastener, or service path.

## Visual observations

The isometric and plan views show two long, tightly packed duct/fan paths carried through a center body/wing assembly, with large battery and electronics/spreader envelopes close to the ducts and elevated relative to the central body. The nose projection shows a crowded central stack and external lateral support/landing features. Opaque overlap makes internal interfaces and access difficult to judge from the all-parts projections; the render cannot establish that overlapping solids are joined, clearanced, serviceable, or supported.

The dedicated motor-envelope view and the source manufacturing report show the most consequential visible incompatibility: each 72 mm motor can overlaps the next 36 mm-pitch station by 36 mm (R1 span 12–92 mm, R2 48–128 mm, R3 84–164 mm). The source report explicitly leaves this collision in the STEP. The six motor shapes are envelopes, not manufacturer models or a workable direct-drive assembly. It is a hard buildability stop for the current six-motor coaxial station arrangement.

Three additional targeted projections are rendered from the same pinned STEP by `highspeed_edf/deliverables/phase15_geometry/native_visual/scripts/render_diagnostic_views.py`; exact camera basis, screen axes, hidden-part prefixes, component names/bounds, source hash and PNG hashes are in `highspeed_edf/phase15/reports/visual_buildability_20261101/diagnostic_views_manifest.json`. In `05_drive_a_side_projection.png`, the three charcoal motor-can envelopes stack over the blue rotor/stator stations; their visible axial overlap is consistent with the source bounds but is not a collision calculation. The single-duct projection (`07_duct_a_top_projection.png`) exposes three rows against the motors, with the outer duct hidden. The battery/electronics view (`06_battery_electronics_side_projection.png`) is an explicitly labeled side projection that hides wing, ducts and skins; the red battery group and green avionics/cooling group occupy separate axial stations in the actual STEP placements. The two Bonka pack envelopes end at Z=−115 mm; the earliest ESC/cooling envelope begins at Z=144 mm, a 259 mm gap between these named component bounds. These are model coordinates, not evidence that the space is unsupported; the omitted airframe is not shown in this projection. The two groups are distributed along the fuselage, not one compact assembly. The manifest records each included component's world bounds. Each image is opaque and projection-based; neither projected overlap nor separation proves 3D contact or clearance.

The diagnostic renderer completed under Blender 4.3.2. It emitted two `EGL_BAD_MATCH` warnings in this headless container before successfully importing all 73 named components and rendering the views. Its battery/electronics view now derives the camera target from the included component bounds and selects a scale 1.12 times the maximum projected span. It labels the world axes and warns that the view cannot establish contact/clearance. The full-view re-render also regenerated four views at the same source hash, tessellating 516 solids / 61,534 triangles; its first isometric PNG hash exactly matched the committed `585b10…579690` image. The other rerendered PNGs were not byte-identical, so the committed original manifest remains the hash authority for those four original views.

The native layout also contains four vector vanes, two elevons and one rudder, while the flight board interface has six PWM outputs. Visual presence of all seven surfaces/mounts does not assign or demonstrate seven independent actuator channels. The source geometry report also identifies the short nose imposed by the bay, unresolved dorsal cooling flow, and payload mount/envelope checks as open items.

## Subset CAM evidence and shop-fit limits

The existing FreeCAD Path probes are executable native geometry previews for **one rotor blank and one stator blank each**, using assumed 40×20×6 mm and 30×20×6 mm stock subsets extracted from the 250×120×5 mm nest. Their source model features a 2 mm two-flute cutter, a face pass removing the nominal 1 mm extra stock, and profile passes down to Z=0. Their own saved-job verifiers and planar cutter-envelope checks pass. This is meaningful subset evidence only; there is no material-removal simulation or machine-specific postprocessed NC.

The user's 2 mm PCB-style cutter has only an 8–10 mm visually estimated flute length, and the CNC is described as barely cutting aluminum. Neither the exact tool geometry/condition nor machine identity, axis travel, spindle/runout, controller, workholding, datum, clamping, tool-holder clearance, feeds/speeds, or postprocessor is verified. A 20 mm aluminum sheet is outside the estimated flute reach for a single through-depth operation; the existing preview uses 6 mm stock, not the 20 mm sheet. Its assumed blank and fixture coordinates are not physically evidenced. No collision, chip evacuation, cut force, tolerance, tool wear or thermal checks exist. Do not produce controller code from these previews.

The machine-envelope model's 250×120×5 mm nest only conditionally fits a generic 3018-class / SainSmart 3018-PRO box; the user-described “233018 Pro” has not been identified as that exact model or measured. Even if the nominal XY envelope matches, full-sheet clamping and tool access are unresolved. The reported A1 mini 180×180×180 mm envelope is adequate for the existing **segmented prototype pieces** by bounding-box checks, but a bounding-box pass is not an orientation/support/slicer/print validation. The shell/wing segments use different build methods and their joints, composite reinforcement and loads are not validated. A nominal print fit does not establish a buildable flight article.

## Required closure before any buildability claim

The current CAD should stay an unpromoted engineering layout until the incompatible motor/rotor geometry is resolved; the surface-channel allocation is closed; all assembly interfaces, clearances, fasteners, access and supports are checked against the assembled native solids; and a real machine-specific job is built from measured stock/tool/machine setup with fixture-aware collision simulation and a matching post. Printed/composite parts also require actual slicer output, materials/layup and joint definition, and structural evidence. These are engineering prerequisites, not claims that such checks have been performed here.

## Evidence boundary

No CFD result, structural solver result, rotor containment result, validated control margin, cut, successful print, hardware test, or flight test is created or inferred by this visual/CAM review. Native CAD validity, tessellation screenshots, a subset Path job, and an A1 bounding-box fit are not equivalents for those results.
