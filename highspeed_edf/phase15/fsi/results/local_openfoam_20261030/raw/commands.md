# Captured commands and outcomes

All OpenFOAM invocations used the extracted Debian tree at /workspace/openfoam-deb with:

    WM_PROJECT_DIR=/workspace/openfoam-deb/usr/share/openfoam
    FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib
    FOAM_APPBIN=/workspace/openfoam-deb/usr/bin
    LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib

Conversion on the tracked source MSH2 geometry:

    cd /workspace/openfoam-run/source_case
    gmshToFoam wing.msh
    exit 0

Mesh check on the converted source mesh:

    checkMesh
    exit 0; Mesh OK

For each 700 and 900 km/h CAS case, steady solver configuration was based on the source Phase-15 case with fixed wall/symmetry patches, ideal-gas air, kOmegaSST, rhoSimpleFoam, SIMPLE pressure relaxation 0.1, equation relaxation 0.3, PCG/DIC pressure, and bounded limitedLinearV velocity. The executable was:

    rhoSimpleFoam -case /workspace/openfoam-run/wing_ias700
    rhoSimpleFoam -case /workspace/openfoam-run/wing_ias900

Both terminated with SIGFPE before convergence; see the corresponding full logs.

The fixed-wing transient cases use the same source mesh and static state, rhoPimpleFoam, Euler time stepping, maxCo 0.4, adaptive deltaT, and endTime 0.004 s. Both parser/dry-run checks passed. Actual commands were:

    rhoPimpleFoam -case /workspace/openfoam-run/wing_ias700_pimple
    rhoPimpleFoam -case /workspace/openfoam-run/wing_ias900_pimple

The 700 run was interrupted by SIGINT after approximately 42.5 seconds wall time; the 900 run was interrupted after approximately 3.9 seconds. The final solver log lines give the last physical time, deltaT, Courant number, continuity errors, and equation residuals. Neither command reached endTime or emitted a normal End marker.
