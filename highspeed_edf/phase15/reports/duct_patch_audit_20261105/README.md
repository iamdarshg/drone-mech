# Phase-15 isolated duct patch audit

The source baseline is drone-mech main `023bc5c5af1ad6080225baacfa7c34e35b9c5fcd`;
the original worker SHA-256 is
`d2c976e4d1bf1cada2c3e0c6d2a4d0de6413cbee39e2d4800e63d258214fef5b`.
The baseline's Gmsh/OpenCASCADE surface IDs assign the conical side to
`inlet`, the large end to `walls`, and the small end to `outlet`. Native
OpenFOAM mesh inspection confirmed that mapping in `baseline_patches.json`.

The candidate selects end surfaces by geometry and assigns the remainder as
walls. Its converted mesh places inlet at z=0, outlet at z=0.12 m and walls
along the duct. The expected cap radii are 0.030 and 0.039 m; the measured
triangulated areas are 0.002815 and 0.004765 m² respectively. See
`candidate_patches.json`. The native Gmsh and OpenFOAM checks ran in WSL;
the candidate geometry was generated from worker SHA-256
`887697c35ae2d094137cf0a95852b94af49eebb455dc68bc8dde63646ec8836c`.
Later changes to command-error handling and result labeling did not alter its
geometry generator.

Both baseline and candidate meshes fail `checkMesh -allTopology -allGeometry`:
87 cells have determinant below 0.001. `checkMesh` returned exit code 0 despite
reporting one failed mesh check, so the worker now also checks its text and
blocks `simpleFoam` unless it reports `Mesh OK.`. A replay using the real
candidate checkMesh log and stubbed command execution confirmed that the
final worker reports `blocked-mesh` without invoking the solver. The replay
also exercised missing-executable handling; see `gate_replay.json`. The replay
is not a solver run.

`native_evidence.tar.gz` contains the baseline OpenFOAM points and faces plus
both boundary files (SHA-256
`e323d21ae07f7970c75b8f3958deae076a7e5f93c57d49c65c40f78d055afdcf`).
The baseline and candidate points and faces have identical SHA-256 hashes;
to replay both patch audits, extract the archive under `/work` and copy the
baseline `points` and `faces` into the candidate's `constant/polyMesh`.
`baseline.geo`, `candidate.geo`, scripts, patch summaries and checkMesh logs
are included.

No CFD flow solver was run for this audit. The isolated-duct incompressible
worker's pressure boundary conditions, flux, convergence and recovery metric
remain unvalidated. It is not an installed-inlet, transonic, aircraft
performance or flight-readiness result.
