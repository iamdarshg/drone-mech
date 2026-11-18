#!/usr/bin/env python3
"""Repair residual slivers: select faces within <radius> mm of any triangle with min angle < A,
isotropic-remesh only that selection (pymeshlab, target edge h mm, surface-distance guard), then
report min angle / slivers / watertightness. In place on a metres STL.
usage: sliver_local_remesh.py <shell_m.stl> <out.json> [A=20] [radius_mm=6] [h_mm=1.5]"""
import json, sys
import numpy as np, pymeshlab, trimesh
p, js = sys.argv[1], sys.argv[2]
A = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0; rad = float(sys.argv[4]) if len(sys.argv) > 4 else 6.0
h = float(sys.argv[5]) if len(sys.argv) > 5 else 1.5
def minang(t):
    a = np.linalg.norm(t[:, 1] - t[:, 2], axis=1); b = np.linalg.norm(t[:, 0] - t[:, 2], axis=1); c = np.linalg.norm(t[:, 0] - t[:, 1], axis=1)
    X = np.degrees(np.arccos(np.clip((b*b + c*c - a*a) / (2*b*c + 1e-30), -1, 1))); Y = np.degrees(np.arccos(np.clip((a*a + c*c - b*b) / (2*a*c + 1e-30), -1, 1)))
    return np.minimum(np.minimum(X, Y), 180 - X - Y)
m = trimesh.load(p); m.apply_scale(1000); rec = {"file": p, "A_deg": A, "radius_mm": rad, "h_mm": h}
for it in range(4):
    ang = minang(m.triangles); bad = np.nonzero(ang < A)[0]
    rec[f"iter{it}_slivers"] = int(len(bad))
    if len(bad) == 0: break
    cen = m.triangles_center; tree = __import__("scipy.spatial", fromlist=["cKDTree"]).cKDTree(cen[bad])
    d, _ = tree.query(cen, k=1); sel = d < rad
    ms = pymeshlab.MeshSet(); ms.add_mesh(pymeshlab.Mesh(m.vertices, m.faces, f_scalar_array=sel.astype(float)))
    ms.compute_selection_by_condition_per_face(condselect="fq>0.5")
    ms.meshing_isotropic_explicit_remeshing(iterations=10, targetlen=pymeshlab.PureValue(h), featuredeg=40,
                                            selectedonly=True, checksurfdist=True, maxsurfdist=pymeshlab.PureValue(0.15))
    ms.meshing_remove_null_faces(); ms.meshing_remove_duplicate_vertices()
    mm = ms.current_mesh(); m = trimesh.Trimesh(mm.vertex_matrix(), mm.face_matrix(), process=True); trimesh.repair.fix_normals(m)
    rad *= 1.5
ang = minang(m.triangles)
rec.update(min_angle_deg=round(float(ang.min()), 2), slivers_after=int((ang < A).sum()), watertight=bool(m.is_watertight),
           winding=bool(m.is_winding_consistent), faces=int(len(m.faces)))
m.apply_scale(0.001); m.export(p); json.dump(rec, open(js, "w"), indent=1); print(json.dumps(rec))
