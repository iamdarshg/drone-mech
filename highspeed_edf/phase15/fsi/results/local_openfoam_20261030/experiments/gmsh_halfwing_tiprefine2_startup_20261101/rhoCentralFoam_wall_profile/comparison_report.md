# Wall-profile rhoCentralFoam guarded startup

## Result

This is a guard-failed startup only. A separate `rhoCentralFoam` case on the strict-passed Gmsh half-wing mesh began from a deliberately wall-compatible coarse velocity/enthalpy profile at Mach 1.05 and +0.5 degrees. The fixed stop threshold was `max(T + |U|^2/(2 Cp)) <= 1.05 Tt_inf = 344.281 K`, where `Tt_inf = 327.886735 K` and `Cp = 1004.685 J/(kg K)`. The monitor stopped the run at the step-50 checkpoint, `t=2.6249203e-6 s`, when the maximum proxy reached `345.5197375 K`, exceeding the bound by `1.2387 K`. The stop is not evidence of a physical thermal failure; the cause has not been established.

The run had not developed a useful transonic field: maximum cell Mach was 1.05276, close to the imposed inlet Mach 1.05, and this short transient did not resolve a shock or establish lift, drag, convergence, or aerodynamic performance. No solver-success claim is made. The complete compressed step-50 OpenFOAM outputs (`T`, `U`, `p`, `rho`, `k`, `omega`, `nut`, `alphat`) are retained beside the monitor and full solver log. `rhoCentralFoam` did not write `h` at that time. `h_from_T.gz` is a derived internal-field cross-check made with the case's stated constant Cp; it is explicitly not a native solver output. Run `python3 derive_checkpoint_h.py` to reproduce it.

## Checkpoint progression

| Step | Time (s) | max Tt proxy (K) | max Mach | max speed (m/s) | Notes |
|---:|---:|---:|---:|---:|---|
| 10 | 2.9695076e-7 | 332.316 | 1.05025 | 345.038 | below guard |
| 20 | 8.7898839e-7 | 337.020 | 1.05103 | 345.236 | below guard; p/rho positive |
| 30 | 1.4596548e-6 | 341.044 | 1.05119 | 345.362 | below guard; p/rho positive |
| 40 | 2.0418054e-6 | 343.804 | 1.05198 | 345.800 | 0.477 K below guard |
| 50 | 2.6249203e-6 | 345.5197 | 1.05276 | 346.260 | guard breach; monitor SIGTERM |

At step 50 the full-field monitor reported T=267.023..339.975 K, p=66.822..161.418 kPa, rho=0.87074..1.65650 kg/m^3; values remained finite and positive. The Tt value is a pointwise cell calculation from the same checkpoint's T and U using the stated Cp. The checkpoint is sufficient to independently recompute this proxy; `checkpoint_bounds_bl.py` and `monitor_rhoCentral_bl.py` document the measurement and stopping behavior. The `status` file's wrapper exit 137 reflects monitor SIGTERM, not a solver convergence status.

The maximum-proxy cell was cell 642623. From the exact OpenFOAM polyMesh face connectivity its four vertex bounds are x=0.0817242..0.0869447 m, y=0.00258788..0.00688999 m, z=0.1612164..0.1654874 m; the mean of its four face centers is (0.0840136, 0.00441320, 0.163633) m. These are mesh coordinates, not a claim that the location represents a physical hotspot. Review its native T/U/p/rho against adjacent cells and patch geometry to diagnose the energy overshoot.

## Initialization and limits

The field generator `prepare_bl_profile.py` computes cell centers, nearest wall triangles and a 3 mm smooth tangential-velocity ramp, then reconstructs T, p, rho and h from the energy and perfect-gas relations. At initialization its max Tt deviation from 327.886735 K was `5.7e-14 K`, maximum ideal-gas residual `2.9e-11 Pa`, and maximum `|h-CpT|` residual zero. It is a coarse initialization device, not a resolved boundary layer. The tetra mesh has no demonstrated y+ suitability and no wall-resolved layer; wall-function turbulence and viscous loads are not validated. A diagnostic pressure-only integration is retained in `wall_pressure_force.py`; the half-wing wall is open at the root (net area vector `(-0.00872068,0,0) m^2`) and viscous traction is absent, so that value is not a valid force result.

The source STEP hash is `4d2a6eefd10cc547d45baadd9207218de688696730c3722ae2247bf9c86ef2e2`; final Gmsh mesh hash is `b5fcff66710bcdd48d2189caec2961075df3fc1e2e58e0baade680ef1c8fb7a4`; generator script hash is `a10292325ade3a1b18e1407e808302b5233ab3fc54bb478bbf067709e97a4cdf`. The strict `checkMesh -constant -allTopology -allGeometry -meshQuality` result is in the parent experiment's `checkMesh.tip2.strict.log`. It reports 822,395 tetrahedra, one connected fluid region, the five intended patches and no `defaultFaces`; strict quality checks pass. OpenFOAM is Foundation 1912 build patch 200626. Executable hashes are recorded in `evidence.sha256`.

This startup does not answer the user's transonic performance or high-speed structural questions. The mesh/solver setup needs a diagnosed energy-bound breach and credible wall treatment before any longer run can produce useful aerodynamic evidence.
