# Phase 15 fuselage shell bounds discrepancy

Status: compound-cut reproduction confirmed; repair unproven. No geometry or acceptance files are changed by this report.

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

An isolated reproduction used the `make_body_shell()` stations and tools from the pinned generator blob above with CadQuery 2.7.0 / OCP 7.8.1.1. The exact `outer.cut(cq.Compound.makeCompound(cut_tools))` pattern completed in 157.3 seconds and returned a valid shape with two solids, volume 253001.3280 mm³, and bounds X −97.01849…97.01849, Y −38.02878…38.02878, Z −112…−28 mm. These match the pinned STEP manifest and volume. The source and STEP pins were read-only during this experiment. This confirms that the compound-cut operation reproduces the loss before STEP export; it does not identify which member of the compound or which kernel behavior is responsible.

The proposed fixed-order individual-cut experiment was only partly completed. Using the same source-pinned lofts and tools, each reported stage returned valid geometry:

| Operation | Time | Solids | Volume (mm³) | Bounds Z (mm) |
| --- | ---: | ---: | ---: | ---: |
| `outer.cut(cavity)` | 52.6 s | 2 | 1039788.372 | −360…280 |
| first duct bore | 34.0 s | 3 | 953528.323 | −360…280 |
| second duct bore | 71.8 s | 4 | 867266.614 | −360…280 |
| first side slot | 161.1 s | 4 | 844511.609 | −360…280 |

The second slot did not return within a further 300 seconds and was interrupted. The hatch stage was therefore not run, and no completed individually-cut candidate was exported or round-tripped. Timings varied with machine load (the first cavity cut took 41.0 seconds in a separate run); these measurements are diagnostic runtime observations, not performance guarantees. The evidence shows that the cavity, both duct bores, and first slot do not individually collapse the axial bounds. It does not establish the result of the second slot or hatch in the fixed-order path.

## Remaining experiment

Continue with a bounded experiment that isolates the second slot and hatch behavior, and compare sequential cuts with staged/fused tools where valid. A candidate repair must preserve the full station span while representing the cavity, duct bores, both side capture slots, and service aperture. Export and reimport the completed candidate through CadQuery/OCP, then inspect axial, side, and isometric native views. Do not claim a fix until the round-tripped candidate has the intended envelope and valid geometry.
