# Failed rhoSimpleFoam steady-start attempts

These are recorded failures from exploratory steady initialization on the same Gmsh half-wing mesh and wall-profile field. They do not constitute a converged flow result. Exact solver logs and relevant `controlDict`, `fvSchemes`, and `fvSolution` snapshots are in the sibling files/directories. Source mesh/STEP and binary hashes are in the parent experiment's `evidence.sha256`.

| Snapshot | What happened | Evidence and interpretation |
|---|---|---|
| `attempt_GAMG_FPE` | First steady iteration failed with floating-point exception in GAMG while solving pressure after U and h had been processed. | `GAMG_FPE.log`; no usable converged state. |
| `attempt_PBiCGStab_divergence` | Pressure solve hit 1000 iterations; initial residual 0.2165109 rose to 6975.0504, local continuity error 2,438,385.579, global 632,057.0807; omega was bounded from -42,260 to 710,578. | `PBiCGStab_divergence.log`; clearly divergent and invalid. |
| `attempt_PCG_rejected` | Pressure matrix is asymmetric for this transonic formulation; PCG was rejected by OpenFOAM before solving. | `PCG_rejected_asymmetric.log`; solver choice incompatible with matrix. |
| `attempt_bounded_upwind_strong_relaxation` | More dissipative upwind configuration with stronger relaxation failed with an FPE in the Gauss-Seidel pressure smoother. | `bounded_upwind_strong_relaxation_FPE.log`; no stable pressure solution. |
| `function_objects_sha1` | Adding OpenFOAM force function objects caused a fatal IO-stream SHA1 error in this packaged runtime. The force-only variant reproduced it. | `function_objects_sha1_failure.log`, `forces_only_sha1_failure.log`; function-object outputs unavailable. |

`rhoSimpleFoam_dry_run_without_functions.log` shows a one-iteration dry-run without force function objects could parse and execute a step; it is only a smoke test. The force-object failure is a tooling limitation; the solver divergences/FPEs are separate numerical failures. No attempt supports any aerodynamic coefficient or design claim. The initial wall profile files are preserved for audit, and each configuration snapshot records the attempted settings. Do not relax energy guards or claim success from these failures.
