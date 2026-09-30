# Phase 13 split-inlet recovery study

## Outcome

The local case package was generated and passed its Gmsh shape, mesh-positivity, static-dictionary, and CAD-area checks. CFD did **not** converge: the one authorized Spot VM's startup script stopped on an HTTP 404 before downloading the case package. No `gmshToFoam`, `changeDictionary`, `checkMesh`, or `rhoSimpleFoam` command ran. Both pressure-recovery results and the selected recovery are therefore null; this is not a CFD result.

The serial console identifies the startup failure at `results/attemptLogs/260926090253/serial_console.log` near line 3900. The attempted metadata `instance/creation-timestamp` lookup is unavailable on this image; the local startup script now falls back safely. The single-launch guard remains consumed, so no retry or second VM was made. `results/attemptLogs/260926090253/cloud_attempt.log` retains the cloud attempt and cleanup trace.

## Tested cases and local mesh evidence

Shared setup: two 90 mm OD / 32 mm hub ducts, four 25 × 120 mm side slots (two per EDF), one 90-degree smoothstep branch per slot to a half-annulus, 0.4293710247 kg/s per branch, unchanged 12S1P powertrain, 3,000 m / 720 km/h / Mach 0.608687. Inlet velocity and static state impose the target flow; the outlet uses freestream static pressure. No target total-pressure recovery is imposed or treated as a result.

| Case | Complete CAD projection | Nodes | Tetra cells | Min / mean SICN | Cells SICN < 0.05 | Outlet-area error | Remote status |
|---|---:|---:|---:|---:|---:|---:|---|
| R30 smoothstep | 67.8587 cm² | 1,934 | 6,909 | 0.042602 / 0.777727 | 4 | 0.7295% | Startup failed before mesh import; `checkMesh` not run |
| R35 smoothstep | 68.4379 cm² | 1,981 | 7,124 | 0.042668 / 0.781573 | 4 | 0.7295% | Startup failed before mesh import; `checkMesh` not run |

Both silhouettes are below 75 cm². Each Gmsh model has one fused positive-volume passage, one inlet face, one outlet face, and 130 wall faces. Local OpenFOAM/checkMesh is absent; that did not block the worker launch. The required *real remote* checkMesh gate was never reached.

| Case | Inlet total pressure from solution | Outlet total pressure from solution | Recovery | Converged |
|---|---:|---:|---:|---|
| R30 smoothstep | null | null | null | No — solver not run |
| R35 smoothstep | null | null | null | No — solver not run |

## Runtime, cleanup, and spend estimate

- One `e2-standard-2` Spot VM in `us-central1-b` was created with a 420-second GCE maximum run duration, DELETE termination action, 12 GB auto-delete boot disk, and one same-region temporary GCS bucket.
- GCE `lastStartTimestamp` to scheduled termination was **409.345 seconds**. The later 47.953-second delete API response latency was outside VM runtime; the instance was already absent and the delete returned not found. The earlier 463.86-second duration included that API latency and has been corrected in the receipt.
- VM, boot disk, and temporary GCS bucket were verified absent. No CNC action occurred.
- Actual invoice/billing amount was not queried (`null`). Conservative observed estimate: compute **$0.02274139** + full ancillary reserve **$0.003** = **$0.02574139** additional. With the Phase-10/11 estimate of $0.17289, cumulative estimated spend is **$0.19863139**, below $0.20. The maximum reserved Phase-13 estimate was $0.02634, or $0.19923 cumulative.

## Retained records and source inventory

- `results/phase13_execution_receipt.json` — final status, duration evidence, null recovery, and cleanup.
- `results/phase13_cost_plan.json` — planned and observed conservative spend estimates.
- `results/phase13_preflight.json` and `results/phase13_cloud_preflight.json` — local, CAD, dictionary, billing, and VM gates.
- `results/phase13_case_matrix.csv` and `results/phase13_solver_results.csv` — mesh evidence and explicit null CFD outcomes.
- `results/phase13_source_manifest.json` — complete list of generated case, template, config, package, and source files.
- `optimization/phase13_openfoam_casegen.py`, `optimization/phase13_openfoam_worker.py`, `optimization/phase13_cloud_runner.py`, `optimization/phase13_worker_startup.sh`, and `configs/phase13_split_inlet_recovery.json` — generator, gated remote runner, startup script, and study definition.

The only external design inputs are the Phase-9 geometry/mass config and 720 km/h meanline summary, plus the Phase-12 CAD projected-area variants listed in the source manifest.
