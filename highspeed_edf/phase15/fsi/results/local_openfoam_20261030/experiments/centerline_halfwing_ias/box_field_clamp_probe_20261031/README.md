# Nominal leading-edge Box sizing probe: field-clamp failure

This probe attempted to add a 3.5 mm Gmsh Box background field around the swept leading edge of the experimental centerline half-wing. It did **not** create a 3.5 mm mesh. The tracked source generator sets the global `Mesh.MeshSizeMin` to 12 mm; Gmsh clamps a Box `VIn=3.5 mm` request to that lower limit. The imported mesh has 53,366 tetrahedra, but this count increase is not proof of local leading-edge refinement. This was a failed sizing experiment and is retained to document the clamp and its numerical outcome. Do not use it to claim a mesh fix.

The exact script regenerates the same MSH2 file byte-for-byte with the recorded local runtime. Its output is 53,366 cells and SHA256 `44fe5a490fa1d6d45a3a00d85131835527a3dbb0dc3a6f73beb72bfcbbb7e173`. It prints both `requestedBoxVInM=0.0035` and the effective `Mesh.MeshSizeMinM=0.012`. The local Gmsh binding is 4.15.2 linked to Gmsh 4.13.1; the source generator and baseline centerline mesh hashes are in `manifest.json`.

Native `gmshToFoam` import and `checkMesh` completed. The import uses the same named inlet/outlet/farfield, wall, and root-symmetry patches as the centerline study. `checkMesh` reports Mesh OK, 53,366 cells, max aspect ratio 20.16, minimum volume 1.306e-9 m³, maximum/average non-orthogonality 83.46°/22.23°, 95 faces above 70°, and maximum skewness 2.774. The 49,208-cell centerline base mesh has essentially the same maximum non-orthogonality (83.46°), average 22.36°, and 83 faces above 70°. This does not show improved mesh quality.

## Solver runs

Both speed cases use the same refined-probe MSH2 import and the same `rhoPimpleFoam` case dictionaries and control values. The exact fresh and continuation `controlDict`, `fvSchemes`, and `fvSolution` are copied under `inputs/`; source initial-field paths and all input hashes are in `manifest.json`. OpenFOAM is the locally extracted Debian OpenFOAM 1912.200626-3+b1. The actual controls were `deltaT=1e-5 s`, `adjustTimeStep=yes`, `maxCo=0.4`, `maxDeltaT=2e-5 s`, `writeInterval=10` steps. Earlier project runs at maxCo 0.1 are separate experiments; these runs did not use maxCo 0.1.

IAS700 started fresh, reached a complete checkpoint at 5.2627291e-5 s under a 90 s wall cap, continued to 1.5416701e-4 s under a 180 s cap, and then stopped with native SIGFPE in `hePsiThermo::calculate` after the last complete checkpoint at 1.8019075e-4 s. At that final checkpoint, `T=53.83–1551.82 K`, `p=13.45–524.28 kPa`, and max `|U|=2984.76 m/s`. The maximum-temperature cell center is `(0.00375, -0.02063, -0.20353) m`; the maximum-speed cell center is `(0.00418, -0.01904, -0.19483) m`. Both are near the leading edge, inside the nominal Box region, yet the Box field was clamped to 12 mm.

IAS900 started fresh, reached 6.2577277e-5 s under a 180 s cap, continued to 1.1772309e-4 s under a second 180 s cap, and continued to a complete checkpoint at 1.6493441e-4 s under another 180 s cap. The third run was interrupted at the wall cap mid-iteration around 1.6588612e-4 s (exit 124); it did not print `End` and did not converge. At its latest complete checkpoint, `T=162.36–1163.41 K`, `p=20.68–330.67 kPa`, and max `|U|=2327.54 m/s`. Maximum-temperature and maximum-speed cell centers are `(0.19506, 0.00150, 0.15672) m` and `(0.16817, -0.01880, -0.13100) m` respectively. The fields are nonphysical; the timeout is not a solver success.

These short transient checks produce no accepted aerodynamic coefficients, transonic design conclusion, mesh/time-step convergence, or flight-readiness evidence. They show the original instability persists on this nominal/clamped sizing probe. A corrected sizing field must lower the global size floor and then pass native mesh-quality checks before a follow-up solver run can test whether local refinement changes this behavior.

## Reproduction

With the pinned Gmsh wheel installed outside the repository (`gmsh==4.15.2`, whose binding links to runtime 4.13.1), run from any directory:

```sh
PYTHONPATH=/path/to/gmsh-4.15.2 \
  python3 highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/box_field_clamp_probe_20261031/generate_clamped_box_mesh.py
```

The script writes `wing_nominal_box_clamped.msh` beside itself and reports the effective global mesh-size minimum. Native import and quality logs are under `logs/`. This folder is a failure record, not an accepted solver case.
