"""Common volume of elevon_left with the left wing sector and duct_A nozzle, on copies; bbox per piece + STL."""
import json, sys, gmsh
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0); gmsh.option.setNumber("Geometry.OCCImportLabels", 1)
occ = gmsh.model.occ; occ.importShapes(sys.argv[1]); occ.synchronize()
names = {t: gmsh.model.getEntityName(3, t).split("/")[-1] for _, t in gmsh.model.getEntities(3)}
e = max((t for t, n in names.items() if n.startswith("elevon_left")), key=lambda t: occ.getMass(3, t))
tg = {n: t for t, n in names.items() if n.startswith(("lifting_wing_left_sector", "duct_A_separate_nozzle"))}
out = {}
keep = [e] + list(tg.values())
occ.remove([(3, t) for t in names if t not in keep], recursive=True); occ.synchronize()
pieces = []
for n, t in tg.items():
    a = occ.copy([(3, e)]); b = occ.copy([(3, t)])
    r, _ = occ.intersect(a, b, removeObject=True, removeTool=True); occ.synchronize()
    out[n] = [{"vol_mm3": round(occ.getMass(d, x), 3), "bbox_mm": [round(c, 2) for c in occ.getBoundingBox(d, x)]} for d, x in r if d == 3]
    pieces += [x for d, x in r if d == 3]
occ.remove([(3, t) for t in keep], recursive=True); occ.synchronize()
gmsh.option.setNumber("Mesh.MeshSizeMax", 1.0); gmsh.model.mesh.generate(2); gmsh.write(sys.argv[2])
gmsh.finalize(); print(json.dumps(out, indent=1))
