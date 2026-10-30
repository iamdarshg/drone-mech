# Local OpenFOAM feasibility run: Phase-15 wing sector

This package records a real local OpenFOAM 1912 run on the tracked Phase-15 outboard wing-sector mesh at 3 km ISA for 700 and 900 km/h CAS, using the requested CAS≈IAS assumption. The native checkMesh command passes. The steady solver attempts fail early, and the transient solver advances only a short physical time because the Courant controller reduces the time step sharply. There is no converged aerodynamic result in this package.

The only geometry analyzed is the 30 mm Phase-15 outboard wing sector, spanwise x=80.33–260 mm, at 0.5° angle of attack. It is a fixed rigid wing section with a symmetry plane at the inboard cut. There is no full aircraft, fuselage, EDF/rotor, moving mesh, or preCICE structural coupling in these runs.

## Airspeed conversion

The solver uses static 3 km ISA conditions: T=268.65 K and p=70,108 Pa. The indicated speeds are treated as calibrated airspeeds per the request. For each CAS, the sea-level isentropic Pitot impact pressure is computed as

    qc = p0 * ((1 + 0.2 * Mcas^2)^3.5 - 1)

with Mcas = CAS / sqrt(1.4 R 288.15 K). At 3 km, the corresponding Mach is recovered from qc/p = (1 + 0.2 M^2)^3.5 - 1, then TAS is M * sqrt(1.4 R T).

| CAS≈IAS | Pitot impact pressure | 3 km Mach | TAS used |
|---|---:|---:|---:|
| 700 km/h | 25,110.53 Pa | 0.676045 | 222.132 m/s |
| 900 km/h | 43,729.58 Pa | 0.861815 | 283.172 m/s |

These are the freestream conditions applied to the compressible cases. The 900 km/h point is high subsonic and is appropriate for a compressible assessment; this incomplete run does not establish shock behavior or aerodynamic coefficients.

## Solver and mesh evidence

OpenFOAM was not available as an executable initially. Debian trixie OpenFOAM 1912.200626-3+b1 and its matching library package were downloaded from the pinned Debian snapshot and extracted with dpkg-deb -x under /workspace/openfoam-deb; no root install, Docker, or paid compute was used. Package URLs and SHA256 hashes are in package-provenance.txt. The install_rootless.sh helper repeats that pinned extraction.

gmshToFoam imported the tracked Gmsh 2.2 mesh (34,166 tetrahedral cells). The source controlDict caused a nonfatal warning that the preCICE adapter library was unavailable during import; mesh conversion continued. The import log notes that 5,464 boundary faces were initially assigned to defaultFaces; the resulting mesh has the five expected named patches and checkMesh reports Mesh OK. The quality summary is:

- 34,166 cells, 7,158 points, one connected region.
- Maximum non-orthogonality 82.87°, with 50 faces above 70°; average 17.10°.
- Maximum aspect ratio 16.31; maximum skewness 1.223.
- Minimum cell volume 2.507×10⁻¹⁰ m³.
- The mesh was not refined or compared against another mesh. Mesh OK is the OpenFOAM check result, not evidence of adequate shock or wall resolution.

The imported geometry and original sources are pinned by SHA256 in study-manifest.json. The packaged 700/900 IAS cases share one converted polyMesh through relative symlinks to avoid duplicating the same mesh; the source Gmsh mesh and STEP remain at their tracked repository paths. fsi was set to a stationary wall and the inboard rootWall cut was treated as a symmetry plane for the rigid-sector flow. The original moving-wall/preCICE settings were not active in these runs.

The first steady rhoSimpleFoam attempts at both speeds ended in SIGFPE before convergence: IAS700 at about iteration 13 after omega became strongly negative and the thermodynamic correction failed; IAS900 at about iteration 5 during thermodynamic correction. Neither reached convergence. The original logs are retained in raw/logs/.

Transient rhoPimpleFoam passed -dry-run and advanced without immediate failure. It did not reach its configured 0.004 s horizon:

- IAS700: 42.5 s wall time; latest logged physical time 3.2306×10⁻⁵ s, with deltaT 1.966×10⁻¹⁰ s at max Courant 0.400.
- IAS900: 3.9 s wall time; latest logged physical time 8.7246×10⁻⁶ s, with deltaT 3.286×10⁻⁷ s at max Courant 0.401.

The stop was due to runtime feasibility, not a solver convergence decision. Raw logs are retained. Continuity errors are printed per time step, but inlet/outlet mass-flow balance was not separately extracted. No force history, CL/CD, shock location, residual convergence, grid sensitivity, time-step sensitivity, or candidate ranking is claimed.

## Reproduction

1. Set OPENFOAM_ROOT to a writable directory and run install_rootless.sh, or provide an already extracted OpenFOAM 1912 package root.
2. Regenerate fresh source-derived inputs and run mesh/parser preflight:

       python3 prepare_cases.py --output-dir /tmp/openfoam-cases --openfoam-root "$OPENFOAM_ROOT"

3. To re-run the packaged transient cases under a per-case wall-time cap:

       OPENFOAM_ROOT=/path/to/openfoam-root MAX_SECONDS=45 ./run_bounded.sh

The generated inputs and logs in this package are the records from the actual attempt. The bounded rerun script is a reproducibility aid; it does not turn the interrupted run into a converged result.
