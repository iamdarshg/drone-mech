#!/usr/bin/env python3
"""DM-G4 study-geometry modification (the as-drawn CAD cannot deflect: each elevon nose overlaps
the wing sector by 559 mm^3 and the elevon crosses the duct nozzle wall by 120 mm^3).
 1. cove: subtract a cylinder of radius R about each hinge line (axis +x through (0, y_h, z_h)),
    spanning the elevon +/- 0.6 mm, from the remeshed body (metres) -> wing TE trimmed to a
    round cove; elevon nose radius from the hinge is measured, gap = R - nose radius;
 2. trim each elevon inboard of |x| = x_trim (mm) to clear the nozzle wall;
 3. receipts: removed body volume, elevon span/area after trim.
v2: the cut also removes everything aft of the hinge inside each elevon's span strip
    (|y| <= 14 mm, z <= 158 mm), with 1.2 mm tip / 0.6 mm inboard spanwise clearance, because
    the wrapped relief side wall bulges 1-2 mm into the elevon tip; boolean slivers are then
    repaired by a selected-region isotropic remesh (1 mm) instead of edge collapse.
usage: dm_g4_modify.py <geom_dir> <R_mm> <x_trim_mm> <y_h_mm> <z_h_mm>"""
import json, sys
import numpy as np, trimesh
g, R, XT, YH, ZH = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
rec = {"cove_radius_mm": R, "elevon_trim_abs_x_mm": XT, "hinge_mm": [YH, ZH]}
el = {s: trimesh.load(f"{g}/elevon_{s}_L+0_R+0_mm.stl") for s in "LR"}
for s, m in el.items():
    d = np.hypot(m.vertices[:, 1] - YH, m.vertices[:, 2] - ZH)
    rec[f"elevon_{s}_nose_radius_mm"] = round(float(d[m.vertices[:, 2] < ZH].max()), 3)
    rec[f"elevon_{s}_te_radius_mm"] = round(float(d[m.vertices[:, 2] > ZH].max()), 3)
# 2. trim elevons
for s, m in el.items():
    lo, hi = m.bounds
    if s == "L": box_lo, box_hi = [lo[0] - 1, lo[1] - 5, lo[2] - 5], [-XT, hi[1] + 5, hi[2] + 5]
    else:        box_lo, box_hi = [XT, lo[1] - 5, lo[2] - 5], [hi[0] + 1, hi[1] + 5, hi[2] + 5]
    box = trimesh.creation.box(bounds=[box_lo, box_hi])
    t = trimesh.boolean.intersection([m, box], engine="manifold")
    rec[f"elevon_{s}_trimmed"] = {"span_mm": round(float(t.bounds[1][0] - t.bounds[0][0]), 2), "volume_mm3": round(float(t.volume), 1),
                                  "watertight": bool(t.is_watertight), "bbox_mm": np.round(t.bounds, 3).tolist()}
    t.export(f"{g}/elevon_{s}_trim_0deg_mm.stl")
    el[s] = t   # the cove spans the TRIMMED elevon only (an untrimmed span would cut the nozzle wall)
# 1. cut on each remeshed body shell (metres): cove cylinder + aft-of-hinge box per elevon
import glob, pymeshlab
cut = []
for s_, m in el.items():
    lo, hi = m.bounds
    x0, x1 = (lo[0] - 1.2, hi[0] + 0.6) if s_ == "L" else (lo[0] - 0.6, hi[0] + 1.2)
    c = trimesh.creation.cylinder(radius=R / 1000, height=(x1 - x0) / 1000, sections=256)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    c.apply_translation([(x0 + x1) / 2000, YH / 1000, ZH / 1000])
    bx = trimesh.creation.box(bounds=[[x0 / 1000, (YH - 14) / 1000, ZH / 1000], [x1 / 1000, (YH + 14) / 1000, 0.158]])
    cut.append(trimesh.boolean.union([c, bx], engine="manifold"))
rec["cut_spanwise_clearance_mm"] = {"tip": 1.2, "inboard": 0.6}; rec["cut_aft_box_mm"] = {"y_half": 14, "z_max": 158}
rec["shells"] = []
for p in sorted(glob.glob(f"{g}/oml_remesh_shell*_m.stl")):
    b = trimesh.load(p); v0 = b.volume
    hit = [c for c in cut if np.all(b.bounds[0] < c.bounds[1]) and np.all(c.bounds[0] < b.bounds[1])]
    nb = trimesh.boolean.difference([b] + hit, engine="manifold") if hit else b
    o = p.replace("oml_remesh_", "oml_cove_")
    r = {"in": p, "out": o, "cuts_hit": len(hit), "removed_volume_mm3": round((v0 - nb.volume) * 1e9, 1)}
    if hit:
        ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(nb.vertices * 1000, nb.faces))
        ms.meshing_remove_duplicate_vertices(); ms.meshing_remove_null_faces()
        cen = ms.current_mesh().vertex_matrix()[ms.current_mesh().face_matrix()].mean(1)
        sel = np.zeros(len(cen), bool)
        for c in hit:
            clo, chi = c.bounds * 1000
            sel |= np.all((cen > clo - 4) & (cen < chi + 4), axis=1)
        ms.current_mesh()  # selection via condition on face index list
        ms.compute_selection_by_condition_per_face(condselect="(fi>=0)")
        ms.set_selection_none()
        idx = np.nonzero(sel)[0]
        # select by bounding boxes (pymeshlab condition on face barycentre)
        conds = []
        for c in hit:
            clo, chi = c.bounds * 1000 
            conds.append(f"((x0+x1+x2)/3>{clo[0]-4:.3f} && (x0+x1+x2)/3<{chi[0]+4:.3f} && (y0+y1+y2)/3>{clo[1]-4:.3f} && (y0+y1+y2)/3<{chi[1]+4:.3f} && (z0+z1+z2)/3>{clo[2]-4:.3f} && (z0+z1+z2)/3<{chi[2]+4:.3f})")
        ms.compute_selection_by_condition_per_face(condselect=" || ".join(conds))
        ms.meshing_isotropic_explicit_remeshing(iterations=8, targetlen=pymeshlab.PureValue(1.0), featuredeg=40,
                                                selectedonly=True, checksurfdist=True, maxsurfdist=pymeshlab.PureValue(0.1))
        mm = ms.current_mesh(); nb = trimesh.Trimesh(mm.vertex_matrix() / 1000, mm.face_matrix(), process=True)
        trimesh.repair.fix_normals(nb)
        tri = nb.triangles * 1000
        def angles(t):
            a = np.linalg.norm(t[:, 1] - t[:, 2], axis=1); b_ = np.linalg.norm(t[:, 0] - t[:, 2], axis=1); c_ = np.linalg.norm(t[:, 0] - t[:, 1], axis=1)
            A = np.degrees(np.arccos(np.clip((b_**2 + c_**2 - a**2) / (2 * b_ * c_ + 1e-30), -1, 1)))
            B = np.degrees(np.arccos(np.clip((a**2 + c_**2 - b_**2) / (2 * a * c_ + 1e-30), -1, 1)))
            return np.minimum(np.minimum(A, B), 180 - A - B)
        ang = angles(tri)
        r.update(selected_faces_remeshed=int(len(idx)), min_angle_deg=round(float(ang.min()), 2),
                 tris_lt_20deg=int((ang < 20).sum()), tris_lt_10deg=int((ang < 10).sum()))
    nb.export(o)
    r.update(watertight=bool(nb.is_watertight), winding=bool(nb.is_winding_consistent), faces=int(len(nb.faces)))
    rec["shells"].append(r)
json.dump(rec, open(f"{g}/dm_g4_modify.json", "w"), indent=1); print(json.dumps(rec, indent=1))
