#!/usr/bin/env python3
"""Per-solid volume, centroid and unit-density inertia (about the solid's own centroid) from the
Phase-15 assembly STEP (OCC via gmsh). Read-only. Output JSON list.
usage: dm_g7_solid_props.py <assembly.step> <out.json>"""
import json, sys, gmsh
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0); gmsh.option.setNumber("Geometry.OCCImportLabels", 1)
occ = gmsh.model.occ; occ.importShapes(sys.argv[1]); occ.synchronize()
rows = []
for _, t in gmsh.model.getEntities(3):
    name = gmsh.model.getEntityName(3, t)
    v = occ.getMass(3, t); c = occ.getCenterOfMass(3, t); I = occ.getMatrixOfInertia(3, t)
    rows.append({"tag": t, "name": name, "base": name.split("/")[-1], "volume_mm3": v, "centroid_mm": [float(x) for x in c], "inertia_unit_density_mm5": [float(x) for x in I]})
gmsh.finalize(); json.dump(rows, open(sys.argv[2], "w")); print(len(rows), "solids")
