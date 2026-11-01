# Source and runtime pins for this experiment

- Source geometry: `highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/geometry/halfwing_x0_to_260mm_t30.step`, SHA-256 `4d2a6eefd10cc547d45baadd9207218de688696730c3722ae2247bf9c86ef2e2`.
- Generated mesh: `/tmp/gmsh_halfwing_fluid/halfwing_fluid_tiprefine2.msh`, SHA-256 `b5fcff66710bcdd48d2189caec2961075df3fc1e2e58e0baade680ef1c8fb7a4`.
- Mesh generator: `build_mesh_tiprefine2.py`, SHA-256 `a10292325ade3a1b18e1407e808302b5233ab3fc54bb478bbf067709e97a4cdf`.
- Mesh quality thresholds: `case_config/meshQualityDict`, SHA-256 `1c9112ce3995fec1786e95f8c2ad94d0a8c7a0f3747ae72fe3343228b2a4ab4e`.
- Runtime: OpenFOAM Foundation 1912, build patch 200626. `rhoCentralFoam` SHA-256 `2a47886510216beb1a03bcbf1f29ae4cddb4c7d796d8f992e3a8a75018a177ed`; `rhoSimpleFoam` SHA-256 `6fea6027f009a3341db5e245b0504169438d92d9024bb08d0013a0cab10d6b16`; `librhoCentralFoam.so` SHA-256 `fc8977934901f41c154adf6603146a95ffe2cb1a832fb8ba8a805c4b02c7ea0c`.

`evidence.sha256` contains valid sha256sum-format hashes for every file in this evidence directory. It covers compressed checkpoint files; for decompression the retained `.gz` files are regular OpenFOAM compressed ASCII outputs. The source STEP and generated `.msh` remain in their original source/work locations and are pinned above by hash rather than duplicated.
