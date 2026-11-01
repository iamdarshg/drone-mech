# Gmsh half-wing / OpenFOAM startup diagnostic

**Disposition:** strict tetra-mesh acceptance passed. The `rhoPimpleFoam` one-step dry run passed. The monitored full-case startup was deliberately stopped on an early wall-adjacent total-temperature proxy excursion; it reached only `6.0045983e-7 s` (the last complete checkpoint is `4.670542e-7 s`) and is unusable as aerodynamic performance evidence. No steady state, force/moment, drag, lift, stall, transonic shock, or aircraft-performance result is established.

## Source pin and repeatability

- Repository: `/workspace/drone-mech`, HEAD `1797a11d6524d0d19f8da7bef1f88db50aa4a9b5` at inspection.
- Source STEP: `highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/geometry/halfwing_x0_to_260mm_t30.step`, SHA-256 `4d2a6eefd10cc547d45baadd9207218de688696730c3722ae2247bf9c86ef2e2`.
- Gmsh OCC Boolean mesher script `build_mesh_tiprefine2.py`, SHA-256 `a10292325ade3a1b18e1407e808302b5233ab3fc54bb478bbf067709e97a4cdf`; generated MSH SHA-256 `b5fcff66710bcdd48d2189caec2961075df3fc1e2e58e0baade680ef1c8fb7a4`.
- OpenFOAM 1912 executables: `rhoPimpleFoam` SHA-256 `925288f3e89e39b06f66e401542c5985eea0a538e9f9d781f1ef09c39155c586`; `rhoCentralFoam` SHA-256 `2a47886510216beb1a03bcbf1f29ae4cddb4c7d796d8f992e3a8a75018a177ed`; shared library SHA-256 `fc8977934901f41c154adf6603146a95ffe2cb1a832fb8ba8a805c4b02c7ea0c`.

## Geometry and strict mesh gate

OCC-difference the STEP source wing from the half-domain fluid block. The exact source-wall patch bounds are `(0, -0.0152345, -0.27)` to `(0.26, 0.0148911, 0.15624)` m. The fluid domain bounds are `(0, -0.35, -0.695)` to `(0.79125, 0.35, 1.43124)` m. The imported mesh contains one connected fluid region, 822,395 tetra cells, and exactly five boundary patches: `symmetryPlane`, `farfield`, `outlet`, `inlet`, `halfwing`; no `defaultFaces` remain. The physical patch face counts sum to all 98,814 boundary faces.

Standalone `checkMesh -constant -allTopology -allGeometry -meshQuality` with the unchanged `meshQualityDict` thresholds reports `Mesh OK.`: minimum determinant `0.00113302` (threshold `0.001`), maximum non-orthogonality `60.77°` (limit `65°`), maximum skewness `1.05255`, minimum face weight `0.126505`, minimum face volume ratio `0.144826`, zero failed error-set counts, one region. Full log SHA-256 `db62efedb64fed93b711a9a4f83035d3acb4cf6047807d7ff814e3eb25dbb847`.

## Field mapping and PIMPLE startup

The case field patch keys in each of the ten `0` files (`T`, `U`, `alphat`, `h`, `k`, `nut`, `omega`, `p`, `pointDisplacement`, `rho`) exactly match the five imported mesh patches. The patch types include wall `halfwing` (`U noSlip`, thermal `zeroGradient`) and `symmetryPlane` (`symmetryPlane`). Thermo is `hePsiThermo`, perfect gas, `Cp=1004.685 J/(kg K)`, `rhoCentral` comparison intended on the same `kOmegaSST` model. The PIMPLE `-dry-run` read the intended mesh bounds and thermo/turbulence setup, advanced one time step to `6e-6 s`, exited `End` with code 0. Dry-run log SHA-256 `817ee35a8f3ac1ef7e0ea11d4291ba2c700512c3b4b023581cfb2c8bd51f7b4a`.

Detached PIMPLE startup case target was `U=(2.47111015739, 0, 283.16117725609) m/s`, `p=70.1 kPa`, `T=268.65 K`, `endTime=0.004 s`, transonic PIMPLE enabled, `maxCo=0.1`. The initial ideal-gas state is consistent: `rho≈0.9090 kg/m³`; freestream total-temperature proxy `T + |U|²/(2 Cp)=308.56 K`. No complete run to endTime occurred. The adaptive timestep was around `4.5e-8 s`; nine logged steps reached only `4.22e-7 s` after about two wall minutes, implying a very long run at this mesh size.

## Monitor stop and cell diagnosis

A guarded checkpoint at `4.670542e-7 s` was parsed from full fields. The monitor threshold `Tt>330 K` was selected as a startup tripwire, but this threshold excursion is **not interpreted as proven physical heating or solver failure**. It triggered termination because it exceeded the declared guard. Last logged solver time after completing its in-progress step was `6.0045983e-7 s`; no convergence claim is possible. The checkpoint maximum of `Tt=T+|U|²/(2 Cp)` (using `Cp=1004.685`) is cell 36858, approximately `(0.00125220, -0.00276243, 0.15495980) m`. This is the average of the four tetra face centroids (exact tetra centroid), not an inferred location from separate extrema. At this cell: `T=302.145 K`, `U=(2.878, -0.0161, 328.894) m/s`, `|U|=328.907 m/s`, `p=61.496 kPa`, `rho=0.7090 kg/m³`, ideal-gas Mach `0.9439`. One of its four faces is a `halfwing` face (boundary face 1620104), so the max is wall-adjacent near the x=0 root seam, not at inlet/outlet/farfield. The wall triangle vertices are `(0.0025,-0.00245914,0.1550119)`, `(0.00124877,-0.00281641,0.15449388)`, `(0,-0.00246669,0.155)` m. Strict mesh-quality checks did not flag this cell.

The global checkpoint min static temperature and speed share cell 115521: `T=242.332 K`, `|U|=248.762 m/s`, `p=80.752 kPa`, `rho=1.161 kg/m³`, Mach `0.7971`; it is also adjacent to `halfwing`. The output max-temperature/max-speed state is therefore in the wall-adjacent field, while the farfield boundary remains prescribed at the initial state. The uniform initial internal velocity conflicts with the no-slip wall at startup, and the mesh has no resolved boundary layer / y+ assessment; these limitations plus sub-microsecond elapsed flow time make the checkpoint unsuitable as a physical transonic or aerodynamic result. `postProcess -func writeCellCentres` failed with an OpenFOAM IO error on `sha1`; the tetra cell centroid was instead independently obtained from the mesh face/owner/neighbour connectivity.

The input-state total-temperature reference is `308.56 K`. A `330 K` guard represents about `+21.4 K` / `+6.9%` over this freestream total temperature and is not a universal physical failure threshold. It was conservative as a startup alarm, and the observed wall-cell excursion must be resolved by energy-equation/BC/startup and wall-resolution validation. Do not raise the threshold merely to permit continuation. Any replacement bound should be stated relative to the adiabatic input stagnation enthalpy and validated against BCs and a checkpointed solution.

## Artifacts

The run was performed in `/tmp/gmsh_halfwing_fluid/`; the reviewable evidence below is copied into this source-pinned experiment directory. The generated `.msh` is 47 MB and is omitted from Git; its exact SHA-256 is recorded in `evidence.sha256`. Key files:

- Strict mesh log: `checkMesh.tip2.strict.log`
- PIMPLE dry-run: `rhoPimpleFoam.dry-run.log`
- PIMPLE startup log: `rhoPimpleFoam.log` (SHA-256 `f13aa4ea1673aab11be24080e01119e07f2e205f1acbcd15a63b618cdc3e2fcb`)
- Checkpoint: `checkpoint_4.670542e-07/{T,U,p,rho}.gz` (uncompressed file hashes are also recorded in `evidence.sha256`)
- Monitor samples: `monitor.jsonl` (SHA-256 `92e40f05035f014a47fa32b707caab1c85a803f432461b342d305db5e6824bf4`)
- Stop record: `stop_reason.json` (SHA-256 `3c8d1a051dbd9b51af56f348dc6510267a184bc2bc19f0dd46d767cdd4672934`)
- Cell/max-field analysis: `analyze_checkpoint.py`, `cell_center.py`

No fabrication readiness, aircraft readiness, successful transonic solution, or physical-test authorization is implied.


## Density-based solver comparison

A separate Kurganov `rhoCentralFoam` startup on the same mesh is recorded in [`rhoCentralFoam/comparison_report.md`](rhoCentralFoam/comparison_report.md). Its first complete checkpoint passed a 5% input total-temperature tolerance; the second exceeded it and was deliberately stopped. It remained subsonic (max Mach 0.9492) and is not developed flow or a transonic result.

## Wall-compatible startup and steady-solver attempts

A separate coarse wall-profile initialization followed by `rhoCentralFoam` is documented in [`rhoCentralFoam_wall_profile/comparison_report.md`](rhoCentralFoam_wall_profile/comparison_report.md). The monitor stopped this step-50 startup at `2.6249203e-6 s` after the pointwise total-temperature proxy reached `345.5197 K`, exceeding the unchanged 5% input stagnation-temperature guard (`344.281 K`) by `1.2387 K`. This is an unresolved startup guard breach, not proof of physical heating and not an aerodynamic result. Full compressed checkpoint fields and source/runtime pins are retained in this experiment directory.

The steady `rhoSimpleFoam` attempts and their exact settings/logs are itemized in [`rhoSimpleFoam_failures/report.md`](rhoSimpleFoam_failures/report.md); attempts either diverged or raised floating-point errors. No convergence, shock, force, lift, drag, or performance result is established.

The narrow `maxCo=0.05` wall-profile sensitivity run and syntax correction are recorded in [`rhoCentralFoam_wall_profile/maxCo_0p05_retry/REPORT.md`](rhoCentralFoam_wall_profile/maxCo_0p05_retry/REPORT.md). It was stopped on the unchanged 1.5 GB free-disk guard before a developed flow; two complete checkpoints are retained and independently recomputed.

The repository-mapped 900 km/h IAS / 3 km half-wing target case is recorded in [`rhoCentralFoam_wall_profile/ias900_target/REPORT.md`](rhoCentralFoam_wall_profile/ias900_target/REPORT.md). Attempt 1 stopped before a checkpoint when shared `/tmp` fell below its unchanged 1.5 GB floor. Fresh-from-zero attempt 2 reached complete startup checkpoints but was stopped at `t=2.6595984e-6 s` when the pointwise Tt proxy reached `324.1853 K`, above the fixed 5% guard (`323.9840 K`). Native fields, full logs and independently recomputed checkpoint metrics are retained. It is not developed flow or aerodynamic performance evidence.


The fresh Mach 1.05/+0.5 degree `rhoCentralFoam` startup sensitivity is recorded in [`rhoCentralFoam_wall_profile/m105_sensitivity_attempt3/REPORT.md`](rhoCentralFoam_wall_profile/m105_sensitivity_attempt3/REPORT.md). It advanced 20 output steps on the strict-passed mesh and was stopped while still in startup as `/tmp` approached its unchanged 1.5 GB floor; the archived last complete checkpoint remains below the fixed 5% Tt guard and positive. The measured runtime projects roughly 18.5 days to the configured 0.004 s end time, so no continuation was launched. It provides no developed flow, shock, forces, coefficients, or aerodynamic result.
