"""Exact OCC boolean: elevon main solids vs every other OML solid (and the duct nozzles). Read-only."""
import json, sys, gmsh
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0); gmsh.option.setNumber("Geometry.OCCImportLabels", 1)
occ = gmsh.model.occ; occ.importShapes(sys.argv[1]); occ.synchronize()
names = {t: gmsh.model.getEntityName(3, t).split("/")[-1] for _, t in gmsh.model.getEntities(3)}
elev = {s: max((t for t, n in names.items() if n.startswith(f"elevon_{s}")), key=lambda t: occ.getMass(3, t)) for s in ("left", "right")}
targets = [t for t, n in names.items() if any(n.startswith(k) for k in ("lifting_wing", "duct_A_separate_nozzle", "duct_B_separate_nozzle", "duct_A_82OD", "duct_B_82OD", "fuselage_battery_bay_shell"))]
out = {}
for s, e in elev.items():
    eb = occ.getBoundingBox(3, e); hits = []
    for t in targets:
        tb = occ.getBoundingBox(3, t)
        if any(eb[i] > tb[i + 3] or tb[i] > eb[i + 3] for i in range(3)): continue
        r, _ = occ.intersect([(3, e)], [(3, t)], removeObject=False, removeTool=False); occ.synchronize()
        v = sum(occ.getMass(d, x) for d, x in r if d == 3)
        if v > 1e-6:
            bb = [round(c, 2) for c in occ.getBoundingBox(*r[0])] if r else None
            hits.append({"solid": names[t], "overlap_mm3": round(v, 3), "overlap_bbox_mm": bb})
        if r: occ.remove(r, recursive=True); occ.synchronize()
    out[f"elevon_{s}"] = {"volume_mm3": round(occ.getMass(3, e), 2), "bbox_mm": [round(c, 2) for c in eb], "overlaps": hits}
gmsh.finalize(); json.dump(out, open(sys.argv[2], "w"), indent=1); print(json.dumps(out, indent=1))
