#!/usr/bin/env python3
"""Blunt the knife-edge elevon trailing edge (CAD TE thickness -> 0 at z=155.98 mm produces
degenerate tets): keep z <= z_cut (mm), giving a flat base. Receipt: base thickness, chord loss.
usage: dm_g4_blunt_te.py <geom_dir> <z_cut_mm>"""
import json, sys
import numpy as np, trimesh
g, zc = sys.argv[1], float(sys.argv[2]); rec = {"z_cut_mm": zc}
for s in "LR":
    m = trimesh.load(f"{g}/elevon_{s}_trim_0deg_mm.stl"); lo, hi = m.bounds
    box = trimesh.creation.box(bounds=[lo - 1, [hi[0] + 1, hi[1] + 1, zc]])
    t = trimesh.boolean.intersection([m, box], engine="manifold")
    sec = m.section(plane_origin=[0, 0, zc], plane_normal=[0, 0, 1]).vertices
    yb = sec[:, 1]
    rec[s] = {"chord_before_mm": round(float(hi[2] - lo[2]), 3), "chord_after_mm": round(float(t.bounds[1][2] - t.bounds[0][2]), 3),
              "base_thickness_mm": round(float(yb.max() - yb.min()), 3), "base_y_mid_mm": round(float((yb.max() + yb.min()) / 2), 3),
              "volume_mm3": round(float(t.volume), 1), "watertight": bool(t.is_watertight)}
    t.export(f"{g}/elevon_{s}_trimte_0deg_mm.stl")
json.dump(rec, open(f"{g}/dm_g4_blunt_te.json", "w"), indent=1); print(json.dumps(rec))
