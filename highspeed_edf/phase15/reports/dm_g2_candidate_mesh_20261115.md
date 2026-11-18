# DM-G2 (complement) — full-aircraft CFD mesh of the Phase-15 study article (2026-11-15)

**Relation to the existing DM-G2 pass.** DM-G2 was already passed on 2026-11-12 by dsh-lead on
the committed **half-wing centreline case** (mesh c1, 1,690,534 tets, sha `7fadb8d7…`,
patches `fsi`/`rootWall`/…; PR #21 comments). DM-G3 runs on that mesh and should stay on it.
This report adds a **different object**: the **full aircraft** (fuselage, wing sectors, ducts
and inlets, nozzles, fins, rudder, elevons, tail booms, cooling tunnel) as one external-flow
domain. It does not replace c1.

**Result:** the full-aircraft mesh passes OpenFOAM v2406 `checkMesh -allTopology -allGeometry`
("Mesh OK"), including the determinant (≥ 0.001) and face-interpolation-weight (≥ 0.05) gates.
An additional, stricter snappyHexMesh-style `meshQualityDict` check (`-meshQuality`, max
non-orthogonality 65°) flags **2 of 2,734,394 internal faces at 66.9°**; all other strict
criteria pass. The geometry remains an **unpromoted study article** (DM-G1); this mesh is not
aerodynamic evidence by itself.

**Intended use: DM-G4 (50/60 km/h IAS, AoA sweeps with real control geometry).** Estimated
median wall y+ is 31–41 at those anchors (wall-function band, lower edge) but 325–463 at the
700–900 km/h DM-G3 anchors, outside the wall-function band — see "y+" below.

Fidelity label: **surface-wrapped OML at 1.0 mm voxel pitch** (not the exact CAD surface).
Solver/container: OpenFOAM v2406, `opencfd/openfoam-default:2406` (digest `dd5aa206…`),
run in a Lima VM on macOS arm64 — a container run, not a native install.

## Result (final mesh, `checkMesh_allTopology_allGeometry.log`)

| Quantity | Value | Gate |
|---|---|---|
| Cells | 1,421,557 tetrahedra; 293,433 points; 2,734,394 internal faces | — |
| Regions | 1 | OK |
| Patches | `aircraft` (wall, 212,162 faces, closed), `inlet` z−, `outlet` z+, `farfield` (4 sides) | all closed/singly connected |
| Max non-orthogonality | 66.9° (avg 16.0°) | checkMesh 70° OK; strict 65°: 2 faces |
| Max skewness | 1.157 | OK (4 internal / 20 boundary) |
| Min cell determinant | 0.00112 | ≥ 0.001 OK |
| Min face interpolation weight | 0.151 | ≥ 0.05 OK |
| Min face volume ratio | 0.179 | ≥ 0.01 OK |
| Concave cells / face flatness / face pyramids / face tets | none / OK / OK / OK | OK |
| Max aspect ratio | ≈ 6.6 | OK |
| gmsh minSICN | min 0.329, 1st pct 0.652 | — |

Domain: x, y ∈ [−2, 2] m; z from 2.0 m ahead of the nose to 4.0 m behind the tail (flow +z,
nose at −z). Wall target edge 3 mm; far-field 0.25 m; Distance/Threshold sizing.

## Pipeline (scripts in `highspeed_edf/phase15/tools/dm_g2/`)

1. `oml_fuse.py` — from the Phase-15 STEP (sha `9b83f3bf…`), keep the 17 named outer-mould-line
   solids (fuselage shell, wing sectors, canted fins, rudder, ducts A/B, side inlets, nozzles,
   elevons, tail booms, ESC/FC cooling tunnel); OCC fuse → 6 bodies, 952 faces (`oml_fuse.log`).
2. `oml_wrap.py` — OCCT tessellation (2 of 952 faces had no triangulation), voxel wrap at 1.0 mm
   (1-voxel dilation/erosion closing, flood fill from outside), marching cubes, decimation.
   Watertight, consistent winding, genus 13. **Deviation:** wrap→CAD mean 0.64 / p95 1.41 /
   max 2.25 mm; CAD→wrap mean 0.76 / p95 1.49 / max 5.0 mm; 95.6% of CAD area within 1.5 mm
   (`oml_wrap.json`). Features thinner than ~2 mm are thickened; gaps < ~2 mm are sealed.
3. `oml_remesh.py` — pymeshlab isotropic remesh to 3 mm (30 it., feature angle 150°, vertices
   kept within 0.9 mm of the wrap); volume change −0.35% (`oml_remesh.json`).
4. `sliver_collapse.py` — 18 guarded shortest-edge collapses remove the last 20 triangles with
   an angle < 20° (min angle 20.9° after; watertight) (`sliver_collapse.json`).
5. `dm_g2_tetmesh.py` — gmsh 4 HXT tets + Netgen optimisation, MSH 2.2 (`dm_g2_tet.json`).
6. `run_checkmesh.sh` — `gmshToFoam`, `aircraft` patch set to `wall`, `checkMesh
   -allTopology -allGeometry`, then `-meshQuality` with the strict dict (logs in this folder).

Hashes of every intermediate and of the polyMesh are in `dm_g2_20261115/sha256.txt`
(mesh `dm_g2_tet.msh` sha `e9b3b225…`; it is 87 MB and kept out of git).

## All attempts (none hidden)

| # | Change | checkMesh -allTopology -allGeometry |
|---|---|---|
| 0 | gmsh surface mesh of the fused BREP (MeshAdapt) | failed: periodic surface 314; STL covered half the span |
| 1 | wrap → remesh (feature 89°, 20 it.) → tets | 3 cells det < 0.001 (min 0.00041); non-ortho 63.3° |
| 2 | + Delaunay edge flips | HXT: segment/facet intersection at (0.060, −0.0015, 0.152) m — no mesh |
| 3 | feature 150°, + gmsh Relocate3D | 2 cells det < 0.001, 1 face weight 0.026, non-ortho 72° |
| 4 | feature 150°, guarded sliver collapse, no Relocate3D | **Mesh OK** |

Attempts 1 and 3 logs: `attempt1_checkMesh.log`, `attempt3_checkMesh.log`.

## Geometry findings for the owner

* **Tail sub-assembly is not attached.** The wrap yields two closed shells: the airframe and a
  tail unit (canted fins, rudder, twin carbon booms; 0.39 L). The closest approach is **2.8 mm**
  at (−9.4, −0.8, 229.9) mm, the forward end of the left boom. The 1 mm wrap seals gaps below
  ~2 mm, so this is a CAD clearance, not a meshing artefact. The mesh keeps it as-is (air gap
  between booms and airframe). A structural load path for the tail does not exist in this CAD.
* Wing sectors and the fuselage are separate solids with air gaps between them for roughly
  z = −150 … −100 mm (cross-sections show three disjoint regions); they join from z ≈ 0.
* Duct bores are open through-passages (walls at 37.5–38.5 mm from the axis; 78 mm ID less the
  wrap inflation). Rotors/hubs are not part of the OML set, so the ducts are empty tubes.

## y+ (`yplus_estimate.txt`)

First-cell height measured as dsh-lead did for c1, `|Sf·(C_cell − C_f)| / |Sf|` over all 212,162
`aircraft` faces: min 0.151 / p5 0.600 / **median 0.735** / p95 1.00 / max 1.58 mm.
y+ from a local turbulent flat-plate Cf (0.0592 Re_x^−0.2) at x = 0.1 and 0.39 m, 3 km ISA
(ν = 1.863e-5 m²/s):

| anchor | U (m/s) | median y+ | p95 y+ |
|---|---:|---:|---:|
| IAS 50 | 16.12 | 31–35 | 42–48 |
| IAS 60 | 19.34 | 36–41 | 49–56 |
| IAS 700 | 222.13 | 325–372 | 442–507 |
| IAS 800 | 252.81 | 365–418 | 497–569 |
| IAS 900 | 283.17 | 404–463 | 550–630 |

At 50/60 km/h Re_x is 0.9–4×10^5, so part of the wall may be laminar; the turbulent estimate is
an upper bound and some faces will fall below y+ 30. A wall-function DM-G4 run should report
the solver's own y+ field, not this estimate.

## Limits carried forward

* No prism boundary layer (wall-normal spacing uncontrolled, see y+). Not a transonic mesh.
* Rotating regions (EDF rotors) and fan boundary conditions are not modelled (AGENTS.md §2
  requires them for rotor/duct claims).
* Mesh sensitivity needs at least one more level (e.g. 2 mm / 4.5 mm wall) — not done here.
* Two internal faces at 66.9° non-orthogonality need `nNonOrthogonalCorrectors ≥ 1`.
