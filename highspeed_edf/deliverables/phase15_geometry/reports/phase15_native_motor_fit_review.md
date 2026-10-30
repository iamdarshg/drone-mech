# Phase-15 motor fit: native geometry and view review

The imported Phase-15 motor envelopes are not physically compatible with the modeled three-station arrangement. This is a geometric fit failure in the supplied STEP model, not a supplier-drawing verification or a flight/buildability qualification.

The six `motor_*_3670_42x72_envelope.step` files were imported with CadQuery 2.7.0 / Open Cascade 7.8.1.1.post1 and checked by exact OCC solid intersections and shape distance. A current full-directory round-trip also imported all 81 Phase-15 STEP files as valid positive-volume solids, with no errors. All 15 motor pairs were checked. Six pairs intersect: in each duct, the adjacent R1/R2 and R2/R3 cans overlap axially by 36 mm at 36 mm center pitch, with 50,033 mm³ intersection per pair. The R1/R3 pair also has a smaller 157 mm³ intersection; their 72 mm can sections do not overlap, but the imported total envelopes still intersect by 8 mm at the shaft/can ends. This rules out the current coaxial direct-drive stack as modeled.

The axial and isometric PNGs below are camera views tessellated from the native STEP solids. Blue is duct A and orange is duct B; transparency makes coincident volumes visible. They are intended to expose the CAD interference, not to imply a completed aircraft assembly or clearance check.

- `native_views/phase15_motor_envelopes_side.png`
- `native_views/phase15_motor_envelopes_isometric.png`
- `native_views/native_motor_interference.json` — measured pairs, intersections, clearances, input paths and hashes
- `render_native_motor_views.py` — reproducible rendering command: `python highspeed_edf/deliverables/phase15_geometry/reports/render_native_motor_views.py`

The current full STEP-import receipt is `native_views/native_step_import.json`. That check only establishes successful STEP parsing and BREP validity; it does not cure the motor collisions. Manufacturing evidence also remains blocked: the stock layouts are geometry-only, with no finished rotor machining toolpaths, tool reach/workholding proof, machine simulation, or CNC execution. The geometry therefore has no supported CNC release or 3D-print process definition. Do not treat these views or import receipts as mechanical validation, manufacturing release, or flight readiness.
