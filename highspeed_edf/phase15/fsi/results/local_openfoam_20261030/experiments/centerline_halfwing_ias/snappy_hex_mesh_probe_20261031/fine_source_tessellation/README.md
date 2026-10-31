# Fine source-tessellation probe: open-root half-wing

**Result: rejected for CFD.** Regenerating the STEP-derived open-root surface with a 2 mm maximum surface mesh size did not remove the strict mesh defect. `snappyHexMesh` completed in 374.33 s and reported no internal quality errors, but an independent standalone `checkMesh -allGeometry -allTopology` reported `Failed 2 mesh checks.` No solver was run.

This remains an experimental centerline half-wing model, not the complete aircraft and not evidence of transonic performance or flight/fabrication readiness.

## Inputs and geometry

- Source STEP: `../geometry/halfwing_x0_to_260mm_t30.step`, SHA256 `4d2a6eefd10cc547d45baadd9207218de688696730c3722ae2247bf9c86ef2e2`.
- Source generator revision: `iamdarshg/drone-mech` e6bca1764e5ddf5463d759075b457e8ceb275d90; `phase15_fsi_casegen.py` SHA256 `f2ea9705c2ea10d5a5ce5145df32944f0c80fbeba35fb4a70961dfea7c36acce`.
- Fine surface exporter is included as `export_open_root_stl_fine.py`. It is the recorded open-root exporter with Gmsh surface sizing changed from min/max 1/5 mm to 0.5/2 mm; the root cap remains omitted and the x=0 half-domain symmetry boundary supplies the cut plane.
- Gmsh 4.13.1 generated 123,022 triangles in 28,533,566 bytes. STL SHA256 `edafbbf4046c1756ec63caf65f1c3ab485f631131600fbc4968717a41967fcc0`.
- The STL still represents the same source STEP surfaces and overall bounds: x=0..0.26 m, y=−0.0152345..0.0148911 m, z=−0.27..0.15624 m. Surface density increased from 20,956 triangles in the baseline to 123,022; no aerodynamic shape or acceptance threshold was intentionally changed.
- The included `underdetermined_fine_stl_overlay.png` visualizes the failed cell polyhedron from the native VTP set (red) against nearby STEP-derived STL skin (blue). The cell bounds are x=0..0.00190446 m, y=−0.00963812..−0.00841466 m, z=0.0698770..0.0731422 m. It is adjacent to the open root/symmetry cut, at an interior chord station rather than the leading/trailing edge (root chord z≈−0.270..+0.156 m). The higher surface tessellation moved the bad cell to the opposite thickness side and another chord station; it did not eliminate the root-cut collapse.

## Run and independent result

The case uses the committed baseline open-root `blockMeshDict`, `snappyHexMeshDict`, and `surfaceFeatureExtractDict`. The quality thresholds are byte-for-byte unchanged from the baseline in `../open_root/system/snappyHexMeshDict`; no `meshQualityControls` value was relaxed. Cell count remained bounded by the same configured `maxGlobalCells=1,200,000` (OpenFOAM refinement batching produced 1,495,779 cells).

The input, executable, logs, and native mesh hashes are in `core_hashes.sha256`, `input_output_hashes.sha256`, `native_mesh_files.sha256`, and `native_mesh_tree.sha256`. Full logs are retained here. OpenFOAM 1912 patch 200626 was invoked with the prepared local runtime paths:

```sh
blockMesh -case CASE
surfaceFeatureExtract -case CASE
snappyHexMesh -case CASE -overwrite
checkMesh -case CASE -allGeometry -allTopology
checkMesh -case CASE -allGeometry -allTopology -writeSets vtk
```

The standalone strict run reported 1,495,779 cells; one underdetermined cell (minimum determinant `1.0842e-18`, required ≥0.001); 32,807 concave cells; 688 concave faces (maximum reported concavity 77.2742°); one warped face (minimum flatness 0.604015). Other reported checks passed: one connected region; patch topology OK; max non-orthogonality 57.9195°; max skewness 2.71728; min volume 2.78215e-11 m³; min face interpolation weight 0.110715. The checker process returned 0 despite its explicit `Failed 2 mesh checks.` summary. The `-writeSets vtk` output provided the defect coordinates shown above.

## Decision

This distinct geometry-tessellation attempt did not satisfy the strict gate. Do not run CFD on this mesh. It narrows the blocker to the root cut / symmetry intersection: the defect persists at a different root-side location after the STEP surface tessellation was made substantially finer. A separate cap/sewing topology experiment is still required before any solver case.
