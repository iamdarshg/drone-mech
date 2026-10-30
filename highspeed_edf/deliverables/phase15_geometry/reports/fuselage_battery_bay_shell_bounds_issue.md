# Phase 15 fuselage shell bounds discrepancy

Status: evidence report; cause not yet confirmed. No geometry or acceptance files are changed by this report.

## Pinned inputs

- CAD input commit: `13143f9e750e8d4c743b9b863d623bd0ab141df1` (`Add pinned Phase 15 native CAD render evidence`).
- Generator blob at that commit: `52a2b1f752567c21631a431372c637513253d010` (`highspeed_edf/phase15/optimization/phase15_generate_geometry.py`).
- Shell STEP SHA-256 at that commit: `d5b4b081c42f0929f7ceb72766f5419989bcf033f941cc16c87df091bda7ede6`.

## Confirmed discrepancy

The generator declares `BODY_Z_MIN = -360` and `BODY_Z_MAX = 280` and constructs the outer loft through stations at both endpoints. That is a 640 mm axial span. The individual-part exporter passes the registered `part.shape` directly to CadQuery's STEP exporter; it applies no crop or transform. The registered part is named `fuselage_battery_bay_shell` and its note says “640 mm shell master.”

The committed native STEP import manifest at `highspeed_edf/deliverables/phase15_geometry/reports/native_views/native_step_import.json` records two valid BREP solids for this file. Their bounds are:

- Solid 0: X 65.9999999…97.0184857, Y −38.0287777…38.0287776, Z −112.0000001…−27.9999999 mm.
- Solid 1: X −97.0184857…−65.9999999, Y −38.0287776…38.0287777, Z −112.0000001…−27.9999999 mm.

Together they span 194.0369714 × 76.0575553 × 84.0000002 mm, with total volume 253001.3280 mm³. The manifest records the matching STEP hash above. The geometry is therefore not a 640 mm exported master and is not simply a mislabeled subcomponent.

The generator's `make_body_shell()` subtracts an inner loft, two axial duct cylinders, two side-slot tools, and a hatch tool from the outer loft using one `outer.cut(Compound(...))` operation. The committed round-trip report also records the shell as two solids with this volume. This establishes that the registered/exported geometry is already reduced before STEP serialization. It does not establish which cut operation or kernel behavior caused the loss.

## Reproduction and diagnostic evidence

Reimport the pinned STEP with CadQuery 2.7.0 / OCP 7.8.1.1.post1:

```python
import cadquery as cq
s = cq.importers.importStep("highspeed_edf/deliverables/phase15_geometry/step/fuselage_battery_bay_shell.step").val()
b = s.BoundingBox()
print(b.xlen, b.ylen, b.zlen, s.Volume(), len(s.Solids()))
```

This returns approximately `194.03697 76.05756 84.00000 253001.32803 2`.

As a source-only check, the outer loft built from the generator's listed stations was valid and one solid, with bbox X −105.89…105.89, Y −48.46…48.46, Z −360…280 mm and volume 7,955,314.2 mm³. This confirms that the stated axial span exists before the Boolean cuts.

An instrumented attempt to run cuts one at a time completed the outer-loft construction, then did not complete the first `outer.cut(cavity)` within more than two minutes and was interrupted. This is a runtime observation, not proof that the cavity cut is defective; it did not produce a post-cut shape to compare.

## Next experiment

On an isolated candidate branch, compare the current compound cut with cuts applied individually in a fixed order (cavity, each duct bore, each side slot, hatch). Record time, `isValid()`, solid count, volume, and six-axis bounds after every operation; also compare a fused tool where valid. Preserve the full station span and verify that the cavity, duct bores, side capture slots, and service aperture remain represented. Import the final candidate STEP back through CadQuery/OCP and review axial, side, and isometric native views. Do not claim a fix until the reimported candidate has the intended full axial envelope and valid geometry.
