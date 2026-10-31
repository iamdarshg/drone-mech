# Moderate leading-edge refinement attempt

This source-pinned local experiment targets the experimental rigid centerline half-wing (x=0..260 mm, 30 mm thick) using 10–12 mm tetrahedral sizing around its swept leading-edge seam. It reuses the existing phase-15 Gmsh fluid-domain generator and the co0.1 IAS700/IAS900 solver decks. No cloud or paid compute was used.

Two sizing bands were explored. The broader band (10–30 mm from the seam) advanced to over 600,000 generated volume nodes before it was stopped; the narrower band now represented in `generate_le_moderate_mesh.py` (2–6 mm from the seam) also reached 540,448 generated volume nodes before it was stopped. The source mesh has 49,208 fluid cells. Both attempts show that this Gmsh setup is growing far beyond the requested 2–3x cell budget before it can write an MSH file. The current `generation.log` preserves the narrow-band attempt through interruption. No refined mesh was written, imported into OpenFOAM, or checked with native `checkMesh`; no refined transient was launched.

This does not resolve the co0.1 instability. The source runs remain the paired IAS700/IAS900 evidence in `../co010_fresh2_20261031`: they stopped at 138.11 and 120.78 microseconds, with respective maxima of 1128.7/707.6 K and 1088.3/1252.5 m/s, far short of the 4 ms target. Thus a meaningful refined checkMesh and a matched-time transient could not be produced using this mesh-generation route. The existing coarse-mesh checkMesh logs and solver evidence are retained with those source runs.

The geometry STEP is copied from the prior 6–12 mm feasibility probe. `generate_le_moderate_mesh.py`, `prepare_cases.py`, and `probe_manifest.json` pin the current source, setup, and hashes. The mesh path remains absent because generation did not complete.
