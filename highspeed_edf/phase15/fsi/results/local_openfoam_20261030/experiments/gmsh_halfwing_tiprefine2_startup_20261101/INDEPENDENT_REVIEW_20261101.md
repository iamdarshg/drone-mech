# Independent CFD evidence review — 2026-11-01

## Scope and disposition

This review checks retained evidence for the Gmsh/OCC half-wing mesh and the short OpenFOAM startup trials. It does not constitute a new solver run. The mesh-quality pass is reproducible from the pinned log; both solver startups were deliberately stopped before useful developed flow. No aerodynamic coefficients, transonic shock, convergence, structural result, or complete-aircraft performance is established.

Reviewed at `drone-mech` commit `dfb02c9` (the experiment's own source-at-run pin remains `1797a11`). Evidence root is this directory. All 53 path-bearing artifact entries in `evidence.sha256` that are present in the repository were independently SHA-256 checked; no mismatch was found. The large generated Gmsh `.msh` is intentionally omitted, with its hash retained in the evidence manifest.

## Rechecks

- The retained strict `checkMesh -constant -allTopology -allGeometry -meshQuality` log ends in `Mesh OK.` and reports 822,395 tetrahedra, one region, five expected boundary patches, 98,814 total boundary faces, min determinant 0.00113302 against the unchanged 0.001 threshold, max non-orthogonality 60.77 degrees against 65 degrees, max skewness 1.05255, and zero failed error-set counts. This is a strict mesh-quality acceptance for this half-wing volume mesh only; it does not establish wall resolution, y+, turbulence-model adequacy, or geometry fidelity beyond the reported bounds.
- The PIMPLE checkpoint fields were re-read from the pinned compressed native fields. The checkpoint contains 822,395 cells, static temperature range 242.3320–302.1449 K and max speed 328.9069 m/s. Recomputed `T + |U|^2/(2 Cp)` is 355.9826 K with Cp=1004.685 J/(kg K), or 355.9925 K with Cp=1004.5 J/(kg K). Both exceed the configured 330 K tripwire. The solver’s last printed time is 6.0045983e-7 s; it did not reach the configured end time.
- The two rhoCentralFoam checkpoints were re-read from their pinned compressed fields. At 2.7087809e-7 s, recomputed max proxy is 319.6797 K (Cp=1004.685) and max Mach as reported is 0.88483. At 6.793357e-7 s, max proxy is 331.8890 K (Cp=1004.685), max Mach is 0.94916, and no cell is reported at Mach 1. The configured 324 K tripwire was crossed, and the run was deliberately stopped. The solver log continued past the second checkpoint to a last printed time of 9.5958771e-7 s before termination; it did not approach the 0.004 s end time.
- The input total-temperature estimate from the stated ideal-gas state is approximately 308.56 K. The 324 K monitor limit is a declared 5% startup tripwire; the excursion is diagnostic of the current startup/energy/near-wall setup and does not itself prove a physical temperature rise or solver divergence.
- The closed-root-cap snappy experiment is correctly rejected: its strict log records `Failed 2 mesh checks`, one determinant of 5.96311e-19 (minimum 0.001), and 32,469 concave cells. Its final `polyMesh.boundary` lacks a `rootCap` patch, so the intended wall condition was not applied. The retained visual plot places the isolated bad cell beside the root/symmetry-cut geometry; it is diagnostic only.

## Corrections to parent reports

1. `acceptance_report.md` describes the PIMPLE proxy as using Cp=1004.685 J/(kg K), but the retained `analyze_checkpoint.py` and `checkpoint_bounds.py` calculate it with Cp=1004.5. The two values produce 355.9826 K and 355.9925 K respectively for the checkpoint. The stop disposition is unchanged; reports should name the actual postprocessor constant consistently.
2. `rhoCentralFoam/comparison_report.md` says the solver log only reached 8.3991625e-7 s. Grepping the retained `rhoCentralFoam.log` shows later printed times through 9.5958771e-7 s. The checkpoint guard and intentional-stop conclusion are unchanged; this is a last-log-time bookkeeping correction.

## Reproduction snippets

From the repository root:

```sh
sha256sum -c highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/gmsh_halfwing_tiprefine2_startup_20261101/evidence.sha256
rg 'Mesh OK\.|Failed [0-9]+ mesh checks|Time = ' highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/gmsh_halfwing_tiprefine2_startup_20261101/checkMesh.tip2.strict.log highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/gmsh_halfwing_tiprefine2_startup_20261101/rhoCentralFoam/rhoCentralFoam.log
```

The manifest includes descriptive pseudo-filenames (for source/mesh/executable hashes) which are not files; run `sha256sum -c` only over path entries that exist or use the recorded exclusions. The independent in-memory gzip parsing used here checked all 53 existing path entries and recomputed proxy values from the saved native fields.

## Limits

The tested geometry is an experimental half-wing, not a complete aircraft. The current uniform internal velocity conflicts with the no-slip wall at startup, no resolved boundary-layer/y+ validation is shown, and the transient times are below a microsecond. The root-cap snappy route remains mesh-invalid. These artifacts do not support claims that transonic performance was achieved or that CFD is complete, nor do they qualify loads, servos, structural strength, fabrication, or flight readiness.
