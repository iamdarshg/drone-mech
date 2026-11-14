"""Extract and fuse the outer-mould-line (OML) solids of the Phase-15 study article.
Read-only on the source STEP; writes a fused BREP + STL + JSON receipt."""
import json, sys, time
import gmsh
step, outdir = sys.argv[1], sys.argv[2]
OML = ("fuselage_battery_bay_shell", "lifting_wing_left_sector", "lifting_wing_right_sector",
       "lifting_wing_centre_bridge_sector", "canted_tail_fin_left", "canted_tail_fin_right",
       "single_right_fin_rudder", "duct_A_82OD", "duct_B_82OD", "duct_A_side_inlet", "duct_B_side_inlet",
       "duct_A_separate_nozzle", "duct_B_separate_nozzle", "elevon_left", "elevon_right",
       "twin_carbon_tail_support_booms", "esc_fc_open_ended_cooling_tunnel")
t0 = time.time()
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0)
gmsh.option.setNumber("Geometry.OCCImportLabels", 1)
gmsh.model.occ.importShapes(step); gmsh.model.occ.synchronize()
keep, drop = [], []
for dim, tag in gmsh.model.getEntities(3):
    base = gmsh.model.getEntityName(dim, tag).split("/")[-1]
    (keep if base.startswith(OML) else drop).append((dim, tag))
gmsh.model.occ.remove(drop, recursive=True); gmsh.model.occ.synchronize()
rec = {"kept_solids": len(keep), "dropped_solids": len(drop)}
try:
    out, _ = gmsh.model.occ.fuse(keep[:1], keep[1:], removeObject=True, removeTool=True)
    gmsh.model.occ.removeAllDuplicates(); gmsh.model.occ.synchronize()
    rec["fuse"] = "ok"
except Exception as e:
    rec["fuse"] = f"failed: {e}"
vols = gmsh.model.getEntities(3)
rec["volumes_after_fuse"] = len(vols)
rec["surfaces"] = len(gmsh.model.getEntities(2))
gmsh.model.occ.exportShapes = None
gmsh.write(f"{outdir}/oml_fused.brep")
gmsh.option.setNumber("Mesh.MeshSizeMax", 4.0); gmsh.option.setNumber("Mesh.MeshSizeMin", 0.5)
gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 24)
gmsh.model.mesh.generate(2)
nodes = gmsh.model.mesh.getNodes()[1].reshape(-1, 3)
rec["surface_mesh_bbox_mm"] = [round(float(v), 2) for v in list(nodes.min(0)) + list(nodes.max(0))]
gmsh.write(f"{outdir}/oml_fused.stl")
rec["seconds"] = round(time.time() - t0, 1)
gmsh.finalize()
json.dump(rec, open(f"{outdir}/oml_fuse_receipt.json", "w"), indent=1); print(json.dumps(rec))
