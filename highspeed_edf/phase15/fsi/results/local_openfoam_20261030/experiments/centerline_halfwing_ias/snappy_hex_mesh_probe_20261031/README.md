# OpenFOAM snappyHexMesh half-wing mesh probe

**Status: no mesh in this report is accepted for CFD.** The native `snappyHexMesh` mesher completed, but every conformal candidate failed the independent standalone `checkMesh -allGeometry -allTopology` gate. The unsnapped probe also failed and its wing-wall boundary is visibly not faithful to the STEP surface. No solver was run and no aerodynamic result is claimed.

This is an experimental half-wing model only. It is not the complete aircraft and does not establish aircraft transonic performance, manufacturing readiness, or flight readiness.

## Source and tool pins

- Base geometry/source-generator revision used for the probe: `iamdarshg/drone-mech` commit `e6bca1764e5ddf5463d759075b457e8ceb275d90`. This evidence commit is based on current `origin/main` `9cb05ced1cc0fbf68582c3f16a1cf8a73b13c065`; the pinned STEP and generator hashes below are unchanged.
- STEP: `highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/geometry/halfwing_x0_to_260mm_t30.step`, SHA256 `4d2a6eefd10cc547d45baadd9207218de688696730c3722ae2247bf9c86ef2e2`.
- Existing generator: `highspeed_edf/phase15/optimization/phase15_fsi_casegen.py`, SHA256 `f2ea9705c2ea10d5a5ce5145df32944f0c80fbeba35fb4a70961dfea7c36acce`.
- `export_open_root_stl.py` imports that STEP with Gmsh 4.13.1, finds the planar x=0 root-cap surface by bounding box, and exports all remaining wing skin as one open-root `fsi` solid. The output is byte-for-byte verified against `open_root/geometry/halfwing_open_root.stl`: SHA256 `6ef617508d4b3073a9264b7cb41f0dc9474b00b7a08c004bb9933c79975785d7` (20,956 triangles, 4,836,898 bytes). The omitted cap is supplied by the half-domain symmetry boundary at x=0.
- OpenFOAM 1912, patch `200626`, 64-bit scalar / 32-bit labels. `blockMesh`, `surfaceCheck`, `surfaceFeatureExtract`, `snappyHexMesh`, and `checkMesh` executables are under `/workspace/openfoam-deb/usr/bin` and their hashes are recorded in `open_root/mesh_hashes.sha256`.
- The extracted OpenFOAM tree omitted Scotch runtime libraries. Debian Scotch/PT-Scotch 7.0.7 packages were extracted under `/tmp/scotch-libs` (no system install); exact package hashes are in the mesh hash manifest.

## Reproduction

From `drone-mech` root, reproduce the open-root STL with:

```sh
python3 highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/snappy_hex_mesh_probe_20261031/export_open_root_stl.py \
  --source-step highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/geometry/halfwing_x0_to_260mm_t30.step \
  --output-stl /tmp/halfwing_open_root.stl
```

The committed `open_root/system` dictionaries and `open_root/geometry` files are the inputs for the accepted-topology probe. Use OpenFOAM 1912 with `FOAMROOT=/workspace/openfoam-deb`, `WM_PROJECT_DIR=/workspace/openfoam-deb/usr/share/openfoam`, `FOAM_LIBBIN=/workspace/openfoam-deb/usr/lib`, `FOAM_APPBIN=/workspace/openfoam-deb/usr/bin`, and `LD_LIBRARY_PATH=/workspace/openfoam-deb/usr/lib:/tmp/scotch-libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`, then run:

```sh
blockMesh -case .
surfaceCheck -case . constant/triSurface/halfwing.stl
surfaceFeatureExtract -case .
checkMesh -case . -allGeometry -allTopology
snappyHexMesh -case . -overwrite
checkMesh -case . -allGeometry -allTopology
```

The exact runs and full logs are retained by case under `open_root/logs`, `rejected_full_domain`, `rejected_half_domain_cap_overlap`, `targeted_root_refinement`, `snap_tuned`, and `no_snap_probe`. OpenFOAM's `checkMesh` returned process status 0 for its reported quality findings; each complete failed report ends with `Failed 2 mesh checks. End`.

## Results and rejected candidates

The source STEP-derived visualization `source_geometry_orthographic.png` has the exact orthographic planform and root/mid/tip sections. Thickness is shown at physical scale without exaggeration. Reproduce it with `python3 visualize_source_geometry.py --output /tmp/source_geometry_orthographic.png`. It depicts a 0.260 m semispan and approximately 0.425→0.305 m root-to-tip chord; this is the small experimental half-wing geometry only.

The original full-domain setup used x bounds -0.53125..0.79125 m with the root cap assigned `symmetryPlane`. Although the source root-cap triangles lie at x=0, snappy moved root patch vertices as far as -1.27757 mm. Standalone `checkMesh` immediately rejected `halfwing_rootWall` as nonplanar. Enabling documented `strictRegionSnap` and `multiRegionFeatureSnap` did not change that failure.

A half-domain background mesh with x-min=0 and the root cap still in the STL caused snappy to assign non-root faces to `halfwing_rootWall` (including a local face with a -z normal at x≈2.18 mm), then fatally report a nonplanar symmetry patch. This rejected overlap case is retained in `rejected_half_domain_cap_overlap`.

The open-root half-domain fixed the boundary topology: one retained region, x bounds 0..0.79125 m, and a dedicated x=0 symmetryPlane patch; the wall patch bounds follow the source wing. Its `snappyHexMesh` run completed in 361.86 s and satisfied all configured snappy checks, but standalone `checkMesh` still failed two checks. It produced 1,492,074 cells / 1,567,159 points / 4,549,731 faces. The failure set was one underdetermined cell with determinant minimum `1.24683e-18` (required minimum 0.001) and 32,388 concave cells. It also reported 652 concave faces (maximum reported angle 77.34°) and one warped face (minimum flatness 0.604). Other checks passed: max non-orthogonality 57.92°, max skewness 2.717, min edge 0.111 mm, one connected region. The requested `maxGlobalCells=1,200,000` setting overshot to 1,492,074 after refinement batches.

`targeted_root_refinement` added a level-6 refinement box around the localized underdetermined root cell (x 0..10 mm, y 5..12 mm, z 22..42 mm) and increased only `maxGlobalCells` to 2,000,000 so that the targeted refinement could be applied. Quality thresholds were unchanged. This increased the mesh to 1,523,689 cells but did not remove the defect: one cell determinant minimum `2.43945e-18`, 33,145 concave cells, 683 concave faces, and one warped face. It failed the same two standalone checks.

`snap_tuned` kept the open-root topology and original refinement levels but changed `tolerance 2.0→1.0`, `nSmoothPatch 3→5`, and `nRelaxIter 5→10`. It took 447 s, produced 1,492,074 cells, and still failed two strict checks: one cell determinant minimum `3.06287e-18`, 32,323 concave cells, 719 concave faces, and seven warped faces. Maximum non-orthogonality increased to 64.76° (below the configured 65° gate), maximum skewness 2.731.

`no_snap_probe` disabled only `snap` while retaining the same open-root geometry, castellated refinement, and strict quality settings. The standalone check again failed two checks: one cell determinant exactly 0 and 36,099 concave cells. Its wall patch spans y=-19.444..+19.444 mm while the source STL spans y=-15.235..+14.891 mm: the mesh overshoots by 4.21 mm on the negative-y side and 4.55 mm on the positive-y side (total thickness 38.89 mm versus 30.13 mm). Its x max is 0.260356 m versus source 0.260000 m. Although face skewness and non-orthogonality improved, its block-faceted wing wall is not faithful to the STEP and is not a CFD candidate.

The unsnapped mesh is overlaid against the STEP-derived STL in `no_snap_probe/unsnapped_wall_vs_source.png`; `no_snap_probe/compare_wall.py` reproduces the planform and physical-scale section comparison with `python3 no_snap_probe/compare_wall.py --case /path/to/no-snap-case --output /tmp/unsnapped_wall_vs_source.png`. Image hashes: source geometry `e9d43effc66fdf2f0d0cf28e4d4694ecf510d6a6844756fe54cb4dd1beb98cd9`; unsnapped wall comparison `b01f5b4e66dd9114a1ad35dc60ee5e15f2d9f7b9c7756cde6cdf375066dcef02`. The quality thresholds were never relaxed: max non-orthogonality 65°, max internal/boundary skewness 4/20, max concave face angle 80°, minimum volume 1e-13, minimum tet quality 1e-9, minimum area 1e-15, minimum twist 0.05, minimum determinant 0.001, minimum face weight 0.05, and minimum volume ratio 0.01. No solver run was performed because no candidate passed standalone strict `checkMesh`.

## Mesh hashes

`open_root/mesh_hashes.sha256` pins the open-root baseline inputs, native mesh files, complete logs, OpenFOAM binaries, and runtime packages. The open-root mesh top-level polyMesh tree hash is `04ceb82f80bac14b6ab0ce4eea6b6b51137243c766f343ff5f3eec390871774f` (diagnostic sets excluded).

The targeted-root and snap-tuned variants also retain their exact `snappyHexMeshDict`, snappy log, strict checkMesh log, and per-file mesh hashes. The no-snap variant is retained as a diagnostic-only case with the same evidence. All files are evidence of failed probes, not release artifacts.
