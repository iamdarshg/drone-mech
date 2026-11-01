# Closed STEP root-cap mesh probe: strict failure

Status: failed standalone strict `checkMesh`; no CFD solver was run. This
candidate is a separate half-domain topology experiment after the open-root
and x=0 feature-filter attempts.

## Geometry and meshing

`export_closed_step_root_cap.py` imports the pinned STEP with Gmsh 4.13.1 and
exports its original wing skin as region `fsi` plus its exact planar x=0 cut
face as region `rootCap`. Both regions use one shared surface tessellation;
the cap is not an added aerodynamic shape. Gmsh generated 123,022 skin
triangles and 5,912 cap triangles. `surfaceCheck.log` reports a closed surface,
one connected part, and all edges shared by two faces.

The generated feature file contained 1,502 edges. `filter_root_seam_features.py`
removed 462 edges whose two endpoints both lie on x=0 and retained the other
1,040. Its proof is in `filter_proof.txt`. The half-domain blockMesh and
refinement dictionaries retain the baseline quality thresholds and surface
levels. Snappy completed without errors in 405.44 s and wrote 1,492,542 cells.

The cap was configured as a `wall` region in `snappyHexMeshDict`, which would
represent a solid cut face and require a no-through-flow wall/slip treatment;
that is physically different from a symmetry plane. The final OpenFOAM
`polyMesh.boundary` contains the usual `symmetryPlane` and `halfwing_fsi`
patches, but no separate `rootCap` patch. The coincident cap was not retained
as a distinct wall patch; the actual mesh therefore still has the x=0 symmetry
boundary. The intended wall condition was not applied in a solver.

## Independent strict check

Command (OpenFOAM 1912, patch 200626):

```sh
checkMesh -case CASE -constant -allTopology -allGeometry -meshQuality
```

`checkMesh.strict.log` and the `-writeSets vtk` rerun are retained. Both finish
with `Failed 2 mesh checks` even though the executable returns process status
0. The mesh has one underdetermined cell with minimum determinant
`5.96311e-19` (required at least `0.001`) and 32,469 concave cells. Maximum
non-orthogonality is 57.9195 degrees and maximum skewness is 2.71728. The
underdetermined-cell VTP bounds are x=0..0.003866 m, y=0.007038..0.009528 m,
z=0.027473..0.034166 m: the defect remains on the root/symmetry cut after
adding the closed STEP cap, on the opposite thickness side from the previous
open-root candidate. The closed cap did not resolve the seam collapse.

## Visual surface comparison

`snapped_wall_vs_STEP.png` overlays the final `halfwing_fsi` faces on the
STEP-derived source STL in planform and at root, midspan, and tip sections on
physical-scale axes. The wall and source surfaces visually coincide closely.
The patch bounds are x=0..0.26007 m, y=-0.0152341..0.0148889 m,
z=-0.269903..0.156168 m. The source STEP-derived STL bounds are
x=0..0.26000 m, y=-0.0152345..0.0148911 m, z=-0.27000..0.15624 m.
`underdetermined_cell_vs_STEP.png` shows the remaining bad cell against the
same STEP-derived surfaces. These overlays assess the generated wall against
the tessellated STEP surfaces; they do not replace native CAD deviation checks.

Reproduce the wall overlay from the repository root with:

```sh
python3 highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/snappy_hex_mesh_probe_20261031/closed_step_root_cap_20261101/compare_wall_to_step.py --case CASE --source-stl CASE/constant/triSurface/halfwing.stl --output /tmp/snapped_wall_vs_STEP.png
```

## Pins

- Source STEP SHA256: `4d2a6eefd10cc547d45baadd9207218de688696730c3722ae2247bf9c86ef2e2`
- Region STL SHA256: `bbd7faefeea0134ab2aea1d092a861a348a31a65d89df8ef8b3424455123a6d2`
- Filtered eMesh SHA256: `3bc0e15bcc5312a13b9d2bf6c0e488e9b150527d3ebf3e94594d46e5ab65876d`
- `blockMeshDict`: `382b29b6503c0b14291f2baff335b60d36f8d7f8667e216e49f4d7c8c9dcbeef`
- `snappyHexMeshDict`: `d4567ecab494c4fac123ddb61aaac5900056e910b8af08704202340c86d972b5`
- `meshQualityDict`: `1c9112ce3995fec1786e95f8c2ad94d60a8c7a0f3747ae72fe3343228b2a4ab4e`
- Final mesh points SHA256: `c4d1095e071db7dd8b373f174411e0642d683a974d8cbe4bc607b82e5c67a96b`
- Final mesh faces SHA256: `97b92ee3c798b5dfbf1aec65444d9c7ef1d0931a78a0d2fda8c4a9d8115655d8`
- Final mesh owner SHA256: `c8b1a9f5d71d30c9c32c8a9b73b757c87d1849b450a0a62e45aee34f8cf4bd24`
- Final mesh neighbour SHA256: `2da069074123e53f9303602c8cfcb2edac8f2ce2c9e7cf52dbeb4f20b83cb151`
- `native_polyMesh_files.sha256` records hashes for every file in the final `constant/polyMesh`, including the boundary and diagnostic sets.

The strict limits remain: max non-orthogonality 65 degrees, internal/boundary
skewness 4/20, max concavity 80 degrees, minimum volume `1e-13`, tet quality
`1e-9`, area `1e-15`, twist 0.05, determinant 0.001, face weight 0.05, and
volume ratio 0.01. This remains an exploratory failed mesh, not CFD or design
evidence.
