# IAS700 maxCo 1.0 bounded rerun

The case at `ias700/` is an isolated copy of the packaged Phase-15 IAS700 transient input. Only `system/controlDict` differs from `cases/pimple/ias700`: `maxCo` is 1.0 instead of 0.4. The mesh is the existing packaged mesh through the relative symlink `ias700/constant/polyMesh -> ../../../../mesh/polyMesh`; it resolves to `local_openfoam_20261030/mesh/polyMesh`. It is not copied into this experiment.

The earlier native run log is `rhoPimpleFoam_native.log`. It was stopped by the 45 s wall cap (timeout status 124) before OpenFOAM emitted `End`. It reached about 1.00918e-4 s and then had deltaT about 9.07e-11 s. This does not claim convergence or an aerodynamic result.

To rerun from the packaged shared mesh, start in the `local_openfoam_20261030` directory and use the same extracted OpenFOAM 1912 installation:

```sh
env WM_PROJECT_DIR=/workspace/openfoam-deb/usr/share/openfoam \
  FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib \
  FOAM_APPBIN=/workspace/openfoam-deb/usr/bin \
  LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib \
  timeout --signal=INT --kill-after=5s 45s \
  /workspace/openfoam-deb/usr/bin/rhoPimpleFoam \
  -case experiments/maxCo1/ias700
```

GNU `timeout` returns 124 at the intentional wall cap. The case uses `startFrom startTime`, so this command begins again at time zero and reads the packaged shared mesh via the symlink.
