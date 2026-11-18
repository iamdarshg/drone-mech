#!/usr/bin/env python3
"""Isotropic remesh of the watertight OML wrap (pymeshlab explicit isotropic remeshing),
written in metres, one STL per closed shell, with quality/fidelity receipt.
usage: oml_remesh.py <wrap_mm.stl> <outdir> <target_edge_mm> [iterations=6]
"""
import json, sys, time
import numpy as np
import pymeshlab, trimesh

src, out, h = sys.argv[1], sys.argv[2], float(sys.argv[3])
it = int(sys.argv[4]) if len(sys.argv) > 4 else 6
t0 = time.time(); rec = {"input": src, "target_edge_mm": h, "iterations": it, "featuredeg": float(__import__("os").environ.get("FEATUREDEG", "40"))}
ms = pymeshlab.MeshSet(); ms.load_new_mesh(src)
ms.meshing_isotropic_explicit_remeshing(iterations=it, targetlen=pymeshlab.PureValue(h),
                                        featuredeg=float(__import__("os").environ.get("FEATUREDEG", "40")), checksurfdist=True, maxsurfdist=pymeshlab.PureValue(0.3 * h))
rec["maxsurfdist_mm"] = 0.3 * h
import os
if os.environ.get("FLIP", "0") == "1":  # Delaunay flips between near-coplanar triangles (dihedral <= 10 deg)
    for _ in range(3):
        ms.meshing_edge_flip_by_planar_optimization(planartype="delaunay", pthreshold=10.0, iterations=3)
    rec["delaunay_flips"] = "3x3, dihedral<=10deg"
m = ms.current_mesh()
mesh = trimesh.Trimesh(m.vertex_matrix(), m.face_matrix(), process=True)
trimesh.repair.fix_normals(mesh)
ref = trimesh.load(src)
ang = np.degrees(trimesh.triangles.angles(mesh.triangles))
e = mesh.edges_unique_length
rec.update({"faces": int(len(mesh.faces)), "watertight": bool(mesh.is_watertight), "winding_consistent": bool(mesh.is_winding_consistent),
            "euler": int(mesh.euler_number), "edge_mm": {"min": round(float(e.min()), 4), "p01": round(float(np.percentile(e, 1)), 4),
            "mean": round(float(e.mean()), 4), "max": round(float(e.max()), 4)},
            "min_angle_deg": {"min": round(float(ang.min()), 2), "p01": round(float(np.percentile(ang.min(1), 1)), 2),
            "frac_tris_lt_20deg": round(float((ang.min(1) < 20).mean()), 5)},
            "volume_change_frac": round(float(mesh.volume / ref.volume - 1), 5)})
_, d, _ = trimesh.proximity.closest_point(ref, mesh.vertices[::5])
rec["deviation_to_wrap_mm"] = {"mean": round(float(d.mean()), 3), "p95": round(float(np.percentile(d, 95)), 3), "max": round(float(d.max()), 3)}
shells = sorted(mesh.split(only_watertight=False), key=lambda p: -len(p.faces))
rec["shells"] = [{"faces": int(len(s.faces)), "watertight": bool(s.is_watertight), "volume_m3": float(s.volume * 1e-9)} for s in shells]
for i, s in enumerate(shells):
    s.apply_scale(1e-3); s.export(f"{out}/oml_remesh_shell{i}_m.stl")
rec["seconds"] = round(time.time() - t0, 1)
json.dump(rec, open(f"{out}/oml_remesh.json", "w"), indent=1); print(json.dumps(rec, indent=1))
