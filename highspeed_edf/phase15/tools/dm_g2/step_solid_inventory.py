"""Inventory solids of a STEP assembly: name, bbox, volume. Read-only."""
import json, sys, collections
import gmsh
step, out = sys.argv[1], sys.argv[2]
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0)
gmsh.option.setNumber("Geometry.OCCImportLabels", 1)
gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
rows = []
for dim, tag in gmsh.model.getEntities(3):
    name = gmsh.model.getEntityName(dim, tag)
    bb = gmsh.model.getBoundingBox(dim, tag)
    try: vol = gmsh.model.occ.getMass(dim, tag)
    except Exception: vol = None
    rows.append({"tag": tag, "name": name, "bbox_mm": [round(v, 2) for v in bb], "volume_mm3": vol})
gmsh.finalize()
json.dump(rows, open(out, "w"), indent=1)
prefixes = collections.Counter(r["name"].split("/")[-1].rstrip("0123456789_") for r in rows)
print(len(rows), "solids"); print(prefixes.most_common(40))
