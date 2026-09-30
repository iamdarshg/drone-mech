# Phase 10 — side-inlet / bend / annulus pressure-recovery study

## Scope and operating point

This study uses one representative duct branch, with the second branch treated as symmetric. The fixed geometry is a 50×120 mm side slot, a 90-degree smooth turn, and a 90 mm OD / 32 mm hub annulus. The 3018-class router's 50 mm stock width, 16 mm stock thickness, and 225 mm minimum centerline bend radius are retained; the 90 mm shell is understood as segmented panels, while the CFD wall is an ideal smooth 6061-T6 aerodynamic envelope. This is not a toolpath-level fabrication model. The case does not include rotor/stator blades, a spinning fan, fuselage blockage, or surface roughness.

At 3,000 m ISA and 720 km/h (200 m/s), the ideal-gas state is 268.65 K and 70.108 kPa static, Mach 0.6087, with freestream total state 288.557 K and 90.038 kPa. Phase 9 gives 1.71748 kg/s for both ducts, or 0.858742 kg/s per branch. Each branch has a 0.006000 m² slot and a 0.0055575 m² annulus: area ratio 1.07963 and net contraction 7.375%, consistent with the Phase-9 stated 1.08 / 7.4% values. The candidate flow uses 78.7% of ideal slot capture and 72.1% of the ideal choked annulus-flow limit, so the subsonic compressible setup is feasible.

The inlet total-pressure/total-temperature state is derived isentropically from the candidate freestream. The target branch mass flow is derived from the Phase-9 720 km/h meanline and is used to derive an inlet initialization plus the common outlet static-pressure boundary corresponding to the 0.98 recovery target. The inlet mass flow is allowed to emerge from the compressible solve, so geometry-dependent losses change mass flow and outlet total pressure; recovery is evaluated from computed outlet pressure, velocity, and temperature relative to freestream total pressure, not copied from the target.

## Planned design matrix

| Case family | Bend centerline radius | Transition contour | Mesh |
|---|---:|---|---|
| Grid convergence reference | 225 mm | Linear | 8.0 / 5.5 / 3.8 mm maximum size |
| Radius sweep | 270, 315 mm | Linear | 5.5 mm |
| Contraction-profile sweep | 225 mm | Cosine, front-loaded | 5.5 mm |

The seven generated cases are listed in `../results/phase10_case_matrix.csv`; each has an inlet/outlet/walls mesh boundary and a `rhoSimpleFoam` input deck. The reference mesh levels contain 32,511 / 91,363 / 257,986 tetrahedral cells. Other medium meshes range from 91,325 to 114,781 cells. `gmshToFoam` converted all seven meshes and `checkMesh` logs are retained.

## Solver and comparison method

The selected solver was Ubuntu OpenFOAM 1912 `rhoSimpleFoam`, ideal-gas air with sensible enthalpy, steady compressible RANS, and `kOmegaSST` wall functions. Each input was capped at 180 seconds and 250 SIMPLE iterations. All seven `rhoSimpleFoam` invocations aborted during initialization: the imported `walls` patch had type `patch`, but the turbulence wall functions require type `wall`. No SIMPLE iterations or pressure-recovery values were produced. The representative 225 mm / medium mesh also failed four `checkMesh` quality checks: maximum aspect ratio 1,239.9 (8 cells), maximum non-orthogonality 89.86° (155 faces above 70°), 635 low-determinant cells, 112 low-interpolation-weight faces, and 83 low-volume-ratio faces. The local case generator now includes a `changeDictionary` conversion for the wall patch and the runner gates solving on checkMesh quality, but that correction was not re-executed remotely after the five-instance cap was reached. No grid-convergence result or best geometry is supportable from this batch.

## Spend and lifecycle control

The hard ceiling was **$0.20 aggregate**. Five sequential Spot VM lifetimes totaled approximately 614.53 seconds; the conservative compute estimate is $0.03414. Including the full $0.03 storage/network/artifact allowance and $0.02 contingency, the envelope estimate is $0.08414; actual billing was not queried. All instances and temporary disks were deleted, temporary GCS objects were removed, and the five-instance cap was reached. No further cloud job was launched. See `../results/phase10_cost_plan.json` and `../results/phase10_launch_attempts.json` for the retained cost and execution receipts.

## Evidence status and disposition

The analytic state and geometry checks pass, and all seven meshes were generated and imported. The compressible solver executable was invoked, but every run aborted before iteration; actual pressure recovery is **null for all variants**, grid convergence is **not established**, and **no best geometry is selected**. Do not interpret the 0.98 target boundary condition or mesh-only output as CFD pressure-recovery evidence. Retained evidence is in `../results/phase10_solver_receipt.json`, `../results/phase10_solver_results.csv`, `../results/caseLogs/`, `../results/phase10_worker.log`, and `../results/phase10_execution_receipt.json`.
