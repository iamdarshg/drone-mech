# Native command record

OpenFOAM runtime environment: `/workspace/openfoam-deb/usr/share/openfoam`, `FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib`, `FOAM_APPBIN=/workspace/openfoam-deb/usr/bin`, `LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib`.

Preflight commands (both returned 0):

```sh
/workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/pimple_transonic/ias700 -dry-run
/workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/pimple_transonic/ias900 -dry-run
```

Bounded native commands (each capped at 75 wall seconds and interrupted with SIGINT):

```sh
timeout --signal=INT --kill-after=10s 75s /workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/pimple_transonic/ias700

timeout --signal=INT --kill-after=10s 75s /workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/pimple_transonic/ias900
```

The solver output was redirected to `rhoPimpleFoam_ias700.log` and `rhoPimpleFoam_ias900.log`. The run logs end during a timestep after SIGINT; neither has a normal `End` marker.
