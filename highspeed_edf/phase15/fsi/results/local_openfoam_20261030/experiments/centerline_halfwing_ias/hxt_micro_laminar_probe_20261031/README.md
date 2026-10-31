# Root/trailing-edge HXT micro-refinement and laminar transonic probe

This source-pinned probe records a failed mesh/solver attempt on the experimental centerline half-wing. It does **not** validate aerodynamic coefficients, loads, structural margins, or the aircraft. The mesh itself fails two strict `checkMesh` checks, and both turbulent and laminar `rhoCentralFoam` attempts encounter a floating-point exception within the first 5 microseconds. The checkpoint fields are nonphysical and are preserved only to localize the failure.

## Run definition

- Geometry: experimental 30 mm-thick half-wing section, generated with `highspeed_edf/phase15/optimization/phase15_fsi_casegen.py`; root at x=0, semispan 0.260 m, root chord 0.425 m, tip chord 0.305 m, 25 degree sweep; no fuselage, root fillet, EDF, coupling, or moving mesh.
- Freestream: 3 km reference, `p=70100 Pa`, `T=268.65 K`, `U=(0,0,222.1322043) m/s`, nominal IAS/CAS 700 km/h. **The vector applies 0 degree incidence** (the inherited candidate metadata says 0.5 degrees; that metadata is inconsistent and must not be used as the actual run angle).
- Mesh generation: Gmsh HXT algorithm 10. An outer leading-edge box asks for 3.5 mm elements; a root/trailing-edge micro-box asks for 0.5 mm with global `MeshSizeMin=0.5 mm`. The MSH contains 73,798 fluid cells. The Gmsh 4.15.2 generator is preserved in `artifacts/phase15_root_te_micro_hxt_probe.py`; its Python module was loaded from `/tmp/phase15-gmsh`.
- OpenFOAM: extracted OpenFOAM 1912.200626-3+b1 (`rhoCentralFoam`); local runtime only, no cloud run. Inputs are copied under `artifacts/inputs/`; exact generated mesh and full command logs are in `artifacts/`.
- This is a laminar follow-up to an otherwise identical HXT-mesh RAS run. The RAS continuation also failed at about 4.76 microseconds. Laminar run begins at time zero, `maxCo=0.1`, `maxDeltaT=5e-6 s`, requested end time `0.004 s`; it failed at 4.7274 microseconds after 126 CPU seconds (173 s wall time).

## Findings

`artifacts/strict_checkMesh.log` reports 73,798 cells, 76 faces over 70 degrees non-orthogonality, 337 cells with determinant below 0.001, and 11 faces with interpolation weight below 0.05. It ends `Failed 2 mesh checks`. The import and `rhoCentralFoam -dry-run` logs are preserved, but a passing dry run does not cure invalid mesh quality.

The laminar solver log ends in SIGFPE in `hePsiThermo::calculate`. At the last complete checkpoint (`4.6960991e-06 s`), cell extrema are: `T=35.39..315.84 K` (freestream 268.65 K), `p=3.76..146.49 kPa` (freestream 70.1 kPa), and `|U|max=722.66 m/s` (freestream 222.13 m/s). `artifacts/checkpoint_4.6960991e-06/` contains the native OpenFOAM fields. The existing RAS run on this mesh likewise failed in the thermo update at ~4.76 microseconds; a finer local patch and removal of turbulence therefore did not fix the instability.

No `Cd`, `Cl`, pressure distribution, converged transonic solution, or design load is inferred from these corrupt early-time fields. Do not use them to choose geometry or claim low drag. The next useful work is mesh/topology and boundary-condition diagnosis, followed by strict mesh acceptance and a stable solver run with verified force integration; this probe does not establish that the current flow setup is valid.

## Evidence and reproduction

- `artifacts/wing_le_root_te_micro_hxt.msh` SHA-256: `fea6b7e674b0d488b99fa4b8b8117948c99b1ed7bcd709e35232d27ffc20fe10`.
- `artifacts/phase15_root_te_micro_hxt_probe.py` SHA-256: `c2b5a6cd441bcaf449b861e513c59fc3bfb590c2d0823f914e1f6833d121e11e`.
- `artifacts/strict_checkMesh.log` SHA-256: `cda1075f98f04d7f66afcb91272b1fcf1e1dad1537b01837159cdd1e1a389ab7`.
- `artifacts/rhoCentralFoam_laminar.log` SHA-256: `b7bb91d708ce94b2690c29dc915a302cf12f3cfe7cc408d0561f33d06f5ef029`.
- The checked-in generator imports `highspeed_edf/phase15/optimization/phase15_fsi_casegen.py` via the recorded workspace path and the Gmsh 4.15.2 Python module at `/tmp/phase15-gmsh`. Replay requires those sources, the equivalent Gmsh binary/runtime, and OpenFOAM 1912.200626-3+b1. The complete MSH and copied OpenFOAM initial fields/configuration are authoritative inputs for the solver portion; captured import, quality, dry-run, and failed-solver logs are under `artifacts/`.

## Boundary of claim

No solver converged. The mesh fails strict quality acceptance. No fabrication-readiness, aircraft performance, servo adequacy, structural safety, or flight-readiness claim follows from this experiment.
