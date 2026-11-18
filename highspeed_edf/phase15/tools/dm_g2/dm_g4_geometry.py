#!/usr/bin/env python3
"""DM-G4 geometry: OML without elevons (fused BREP, for the voxel wrap) + each elevon as its own
CAD solid, rotated about its hinge line by delta (TE-down positive), tessellated to STL (metres).
Interference of every rotated elevon with the remaining OML solids is checked by OCC boolean.
Hinge line: axis +x through (y_h, z_h) = centroid of the elevon hinge-pin solids.
usage: dm_g4_geometry.py <assembly.step> <outdir>   (elevon 0-deg STLs: see dm_g4_deflect.py)
"""
import json, math, sys, time
import gmsh
step, out = sys.argv[1], sys.argv[2]
OML = ("fuselage_battery_bay_shell", "lifting_wing_left_sector", "lifting_wing_right_sector",
       "lifting_wing_centre_bridge_sector", "canted_tail_fin_left", "canted_tail_fin_right",
       "single_right_fin_rudder", "duct_A_82OD", "duct_B_82OD", "duct_A_side_inlet", "duct_B_side_inlet",
       "duct_A_separate_nozzle", "duct_B_separate_nozzle",
       "twin_carbon_tail_support_booms", "esc_fc_open_ended_cooling_tunnel")
t0 = time.time(); rec = {"step": step, "cases": {}}
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0)
gmsh.option.setNumber("Geometry.OCCImportLabels", 1)
gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
occ = gmsh.model.occ
body, elev = [], {"L": [], "R": []}
for dim, tag in gmsh.model.getEntities(3):
    base = gmsh.model.getEntityName(dim, tag).split("/")[-1]
    if base.startswith(OML): body.append(tag)
    elif base.startswith("elevon_left"): elev["L"].append(tag)
    elif base.startswith("elevon_right"): elev["R"].append(tag)
def vol(t): return occ.getMass(3, t)
def bbox(t): return [round(v, 3) for v in occ.getBoundingBox(3, t)]
hinge = {}
for s in "LR":
    ts = sorted(elev[s], key=vol)
    main = ts[-1]; pins = [t for t in ts if abs(vol(t) - 42.41) < 1.0]
    horn = [t for t in ts if t not in pins and t != main]
    cy = sum(occ.getCenterOfMass(3, t)[1] for t in pins) / len(pins)
    cz = sum(occ.getCenterOfMass(3, t)[2] for t in pins) / len(pins)
    bb = occ.getBoundingBox(3, main)
    hinge[s] = {"main": main, "pins": pins, "horn": horn, "axis_point_mm": [0.0, round(cy, 3), round(cz, 3)],
                "bbox_mm": bbox(main), "area_planform_mm2": round((bb[3] - bb[0]) * (bb[5] - bb[2]), 1),
                "chord_mm": round(bb[5] - bb[2], 2), "span_mm": round(bb[3] - bb[0], 2),
                "hinge_frac_chord": round((cz - bb[2]) / (bb[5] - bb[2]), 3)}
rec["elevons"] = hinge; rec["body_solids"] = len(body)
# body without elevons (pins and horns dropped with the elevons; they sit inside the elevon/relief)
keep_tags = set(body) | {hinge[s]["main"] for s in "LR"}
drop = [(3, t) for d, t in gmsh.model.getEntities(3) if t not in keep_tags]
occ.remove(drop, recursive=True); occ.synchronize()
# (per-case rotation/interference moved to dm_g4_deflect.py; see git history for the slow version)
# body-only BREP for the wrap
occ.remove([(3, hinge[s]["main"]) for s in "LR"], recursive=True); occ.synchronize()
try:
    o, _ = occ.fuse([(3, body[0])], [(3, t) for t in body[1:]], removeObject=True, removeTool=True)
    occ.removeAllDuplicates(); occ.synchronize(); rec["body_fuse"] = "ok"
except Exception as e:
    rec["body_fuse"] = f"failed: {e}"
gmsh.model.mesh.clear(); gmsh.write(f"{out}/oml_noelevon_fused.brep")
rec["seconds"] = round(time.time() - t0, 1); gmsh.finalize()
for s in "LR":
    hinge[s].pop("pins"); hinge[s].pop("horn")
json.dump(rec, open(f"{out}/dm_g4_geometry.json", "w"), indent=1); print(json.dumps(rec["elevons"], indent=1))
