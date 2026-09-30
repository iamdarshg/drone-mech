# Phase 15 — isolated-duct RANS on GCP: status and first result

## What was built and run

A governed, budget-capped Spot-VM job that builds an **isolated diffusing duct**
(30 mm inlet → 39 mm outlet, 120 mm long) with **gmsh**, converts it with
**gmshToFoam**, and solves steady **RANS (k-ω SST)** with **simpleFoam**.

- Launcher: `phase15/optimization/launch_phase15_inlet.ps1` (10-cent guard:
  compute ≤ $0.0667 at the conservative $0.20/h rate for a 1200 s Spot VM,
  $0.02 storage/network, remainder contingency).
- Worker: `phase15/optimization/phase15_inlet_worker.py`
- VM startup: `phase15/optimization/phase15_inlet_worker_startup.sh`
- Bucket: `gs://aero-governed-blockers-988177451335-20260919`

Every worker self-deletes on exit (`--instance-termination-action=DELETE` plus a
`shutdown -h now` trap), and uploaded its log and a finish receipt.

## Pipeline status: **validated end-to-end**

| Step | Result |
|---|---|
| GCE Spot instance + metadata + GCS round-trip | OK |
| Bundle fetch / extract | OK |
| OpenFOAM install (distro package 1912) + gmsh | OK |
| gmsh mesh (39,151 elements, quality 0.5–1.0) | rc=0, 0.7 s |
| gmshToFoam | rc=0, 0.2 s |
| checkMesh | **Mesh OK** (max non-orthogonality 61.8°, max skewness 0.83) |
| simpleFoam (k-ω SST, steady) | **rc=0, 26.7 s** |
| Result extraction to GCS | OK |

First extracted numbers (case r_in 30 mm, r_out 39 mm, L 120 mm, U_in 178 m/s):

| Quantity | Value |
|---|---|
| inlet total pressure (kinematic) | 47,959 m²/s² |
| outlet total pressure (kinematic) | 5,966 m²/s² |
| computed "recovery" | 0.124 |

## Why this number is NOT yet trustworthy

1. **Total-pressure metric**: the outlet uses a fixed static pressure (`p = 0`),
   so the outlet "total pressure" is just its dynamic head. The inlet static
   pressure (raised by the solver to drive the flow) dominates `pt_in`. A proper
   recovery needs a **total-pressure inlet** and a **mass-flow / back-pressure
   outlet**, then `pt_fan / pt_freestream`.
2. **Patch orientation**: with a fixed-velocity inlet and fixed-pressure outlet
   the solver drove `p_in ≫ p_out`, which is nozzle-like, not diffuser-like —
   suggesting gmsh's OCC face tags mapped inlet/outlet to the wrong ends. Verify
   by comparing patch areas (inlet should be π·0.030² = 2.83e-3 m², outlet
   π·0.039² = 4.78e-3 m²).
3. **Incompressible at M≈0.52** is a stretch; a compressible run is warranted
   once the BCs are right (OpenFOAM 1912's `rhoSimpleFoam` thermo crashed; the
   pipeline ran with the distro package, so the newer OpenCFD build should be the
   next step for the compressible pass).

## Fixes required (one short iteration each)

1. Swap/verify inlet and outlet patches by area.
2. Use `totalPressure` inlet (`p0`) + `flowRateOutletVelocity`/`fixedValue p`
   back-pressure, and compute recovery as `areaAverage(pt_out)/pt_in`.
3. Re-run compressible on the OpenCFD build for a Mach-correct number.

## Cost

All runs used **e2-standard-2 Spot** instances that self-deleted; the actual
compute was minutes per run at well under the conservative $0.20/h rate, plus
cents of GCS. **No billing amount was queried.** Total is far inside the
**$0.10** approval.

## Honest scope note

This is the **internal duct loss only** — the part geometry controls (diffusion
angle, length, lip). It is **not** the installed inlet recovery, which needs a
coupled external + internal flow (a much larger case than a 10-minute Spot job).
The measured installed recovery remains gate #1 and needs either a bigger CFD
budget or the bench-rig path in the design spec §3a.
