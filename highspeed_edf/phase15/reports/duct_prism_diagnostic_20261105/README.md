# Isolated duct prism-mesh diagnostic

The tetrahedral duct mesh in the adjacent patch audit had 87 low-determinant
cells. A separate experiment extruded the corrected inlet triangulation into
24 axial layers of tapered prisms: 7,008 cells with the same nominal 30 mm
inlet radius, 39 mm outlet radius and 120 mm length. The circular boundary is
polygonal at mesh resolution. Gmsh 4.13.1 generated the inlet triangulation;
OpenFOAM 2406 `checkMesh -allTopology -allGeometry` reported `Mesh OK.`, with
minimum determinant 0.0520 and maximum skewness 0.298. The native patch audit
confirmed the inlet and outlet locations and the wall spanning the duct.

The worker now offers this generator via `--mesh prism`; tetrahedral meshing
remains the default. This is an experimental mesh option, not an aerodynamic
acceptance. The generator independently reproduced the same output from a
surface-only input, SHA-256
`48127ecd3c88f01539e2958dcc493c444672091438317b672ce01d0ab1f7a296`, and
the resulting OpenFOAM mesh passed the same check. The earlier experiment's
mesh differed by two last-decimal characters due to floating-point arithmetic;
its independent check also passed. The mesh has no validated wall layers or
mesh-sensitivity study.

A separate 100-iteration `simpleFoam` diagnostic finished on the earlier
prism mesh. At iteration 100, inlet flux was -0.500993 m³/s and outlet flux
0.500990 m³/s; the relative net imbalance was 6.44e-6. The pressure initial
residual was about 0.10 and the local continuity error about 0.036. This short
run is not converged and does not validate total-pressure recovery. Its
incompressible isolated duct and current boundary conditions do not assess
transonic or installed-aircraft performance.

The actual worker and prism generator were exercised in a replay using
stubbed external commands and the real `checkMesh` log; it produced the
independently checked prism mesh. Additional replays confirmed that the
default failed tetrahedral mesh blocks the solver and that a failed solver
cannot report recovery from stale files. The worker also refuses to reuse an
existing case directory; a separate replay confirmed it preserves prior data.
These replays are not flow solves.
Their scripts and machine-readable receipts are included.

`evidence.tar.gz` (SHA-256
`d30db0804ff8d8ed21d5fc3b9c3d3a3be11ea19916207620ecc3f38b52ff2ae4`)
contains the source inlet surface mesh, native OpenFOAM mesh, `checkMesh` log,
and the diagnostic solver's flux field and log. The source surface SHA-256 is
`98573780d9914498e04c29264376f827d92bd19f1c1590ef0690606ba5877705`.
These are numerical setup checks, not flight-readiness evidence.
