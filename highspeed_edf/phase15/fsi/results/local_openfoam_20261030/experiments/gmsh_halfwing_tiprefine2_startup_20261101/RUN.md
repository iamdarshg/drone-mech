# Reproduction command and provenance

This experiment used OpenFOAM 1912 (`Build: patch=200626`), Gmsh 4.13.1, the STEP source and mesh generator pinned in `evidence.sha256`. Commands (the case lived in `/tmp/gmsh_halfwing_fluid/ias900_case`):

```sh
/workspace/openfoam-deb/usr/bin/checkMesh \
  -case /tmp/gmsh_halfwing_fluid/tip_case2 \
  -constant -allTopology -allGeometry -meshQuality -writeSets vtk
/workspace/openfoam-deb/usr/bin/rhoPimpleFoam \
  -case /tmp/gmsh_halfwing_fluid/ias900_case -dry-run
/workspace/openfoam-deb/usr/bin/rhoPimpleFoam \
  -case /tmp/gmsh_halfwing_fluid/ias900_case
```

The Gmsh mesh was converted with `gmshToFoam`, copied into the case, and boundary patch types were set to `symmetryPlane`, `wall`, and `patch` for the five named regions. Runtime environment used `FOAMROOT=/workspace/openfoam-deb`, `WM_PROJECT_DIR=/workspace/openfoam-deb/usr/share/openfoam`, `FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib`, `FOAM_APPBIN=/workspace/openfoam-deb/usr/bin`, and `LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib:/tmp/scotch-libs/usr/lib/x86_64-linux-gnu`.

The initial launcher had a 1800 s timeout wrapper. At the parent agent's direction, that wrapper was killed while the solver process remained detached. The separate monitor sent SIGTERM after the checkpoint violated the configured total-temperature proxy guard; the solver then stopped at its in-progress step. The wrapper status `137` is not a solver failure code. See the complete solver log, monitor timeline and guard record.

This is evidence for a strict mesh pass and a short numerical startup only. The run did not reach its configured `endTime=0.004 s`; it does not establish a converged transonic solution or aerodynamic performance.
