# Leading-edge refinement feasibility probe

This local source-pinned mesh experiment reuses `phase15_fsi_casegen.py` at commit `86d8385206e9a213fa9e1fe66e506d8bb1477cbb`, with a Distance/Threshold/Min field on the swept leading-edge seam: 6–12 mm requested size at 2–10 mm from the seam. The parent generator's surface sizing and farfield geometry were retained; `Mesh.MeshSizeMin` was lowered to 6 mm to permit the local field to apply. STEP geometry and the exact generator script are included.

Gmsh Python binding 4.15.2 (runtime 4.13.1) completed Delaunay generation and reported 5,693,285 tetrahedra / 934,944 nodes. This is about 115 times the 49,208-cell parent OpenFOAM mesh. The process was stopped during volume optimization before MSH output, OpenFOAM import, or checkMesh; therefore no refined transient was launched and this is not a grid-sensitivity result. The mesh was judged impractical for the paired transient on this local workspace. The case templates and preparation script are retained as the reproducible setup for a future lower-cost refinement design.

The generator log contains the Delaunay count and intermediate quality data. Since output was not written, there is no MSH/polyMesh hash or checkMesh result. The geometry remained the experimental x=0..260 mm, 30 mm thick half-wing in the same farfield box, without a fuselage or root fillet.
