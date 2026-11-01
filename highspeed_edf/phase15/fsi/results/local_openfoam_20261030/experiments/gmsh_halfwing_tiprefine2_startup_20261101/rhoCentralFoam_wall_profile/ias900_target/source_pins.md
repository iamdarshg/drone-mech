# IAS900 target source/runtime pins

The speed/altitude/air-state mapping is taken from the repository's existing native IAS900 case, not recomputed from a new assumption: `highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/pimple_transonic/ias900/candidate.json` SHA-256 `1d86c97baa1bb3a222b80ca90b776ac7d7d9d495fd19087c1233f881a6feb225` and `run_manifest.json` SHA-256 `39934bbbbfa98c00d4163aa395c4881e9b7cdf7e05baca25a032fc0dedfd94a3`. These give TAS 283.1719595766233 m/s, altitude 3000 m, static temperature 268.65 K, solver static pressure 70100 Pa, and Mach 0.8618149633208082.

The native source geometry and generated Gmsh mesh are the same files used by the parent strict mesh acceptance experiment:

- STEP: `highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/geometry/halfwing_x0_to_260mm_t30.step`, SHA-256 `4d2a6eefd10cc547d45baadd9207218de688696730c3722ae2247bf9c86ef2e2`.
- Gmsh MSH: `/tmp/gmsh_halfwing_fluid/halfwing_fluid_tiprefine2.msh`, SHA-256 `b5fcff66710bcdd48d2189caec2961075df3fc1e2e58e0baade680ef1c8fb7a4`.
- Mesh generator `build_mesh_tiprefine2.py`, SHA-256 `a10292325ade3a1b18e1407e808302b5233ab3fc54bb478bbf067709e97a4cdf`; strict thresholds `meshQualityDict`, SHA-256 `1c9112ce3995fec1786e95f8c2ad94d0a8c7a0f3747ae72fe3343228b2a4ab4e`.
- OpenFOAM Foundation 1912 build patch 200626: `rhoCentralFoam` SHA-256 `2a47886510216beb1a03bcbf1f29ae4cddb4c7d796d8f992e3a8a75018a177ed`; `librhoCentralFoam.so` SHA-256 `fc8977934901f41c154adf6603146a95ffe2cb1a832fb8ba8a805c4b02c7ea0c`; `checkMesh` SHA-256 `d62326097607d40e460bdd5d63df245896dd51ea16cf965199b75509308de791`.

The exact copied OpenFOAM polyMesh files are individually hashed in `mesh_file_hashes.json`; target dictionaries, initialized case fields (compressed copies in `initial_fields/`), initializer and monitor scripts, and each captured run artifact are covered by the experiment-level `evidence.sha256`. This distinguishes a source-pinned geometry/mesh from a solver result, which remains contingent on the monitored run.

For direct verification of the actual copied mesh and generated initial state, `mesh_file_hashes.json` records all eight native polyMesh file hashes and a canonical tree digest; it asserts byte equality between the existing case and this target case. `initial_field_hashes.json` records raw and archived-compressed hashes for all ten fields and verifies they match the target run's `0/` files byte-for-byte after decompression.
