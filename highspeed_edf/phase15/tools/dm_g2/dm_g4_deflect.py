#!/usr/bin/env python3
"""Rotate the 0-deg CAD tessellation of an elevon about its hinge line (axis +x through
(0, y_h, z_h)) by delta deg (TE-down positive = +rotation about +x), write it in metres, and
measure clearance to the body surface (signed: negative = elevon vertex inside the body).
usage: dm_g4_deflect.py <elevon_0deg_mm.stl> <y_h_mm> <z_h_mm> <delta_deg> <body_wrap_mm.stl> <out_m.stl> <out.json>"""
import json, math, sys
import numpy as np, trimesh
src, yh, zh, d, bodyp, outp, js = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5], sys.argv[6], sys.argv[7]
m = trimesh.load(src); v = m.vertices.copy()
a = math.radians(d); c, s = math.cos(a), math.sin(a)
y, z = v[:, 1] - yh, v[:, 2] - zh
v[:, 1] = yh + c * y - s * z; v[:, 2] = zh + s * y + c * z
r = trimesh.Trimesh(v, m.faces, process=False)
body = trimesh.load(bodyp)
lo, hi = v.min(0) - 15.0, v.max(0) + 15.0          # crop the body to a 15 mm box around the elevon
cen = body.triangles_center; keep = np.all((cen > lo) & (cen < hi), axis=1)
near = body.submesh([np.nonzero(keep)[0]], append=True) if keep.any() else None
idx = np.arange(len(v))
if near is None:
    sd = np.full(len(v), -15.0)
else:
    _, dist, tri = trimesh.proximity.closest_point(near, v)
    # sign: inside the (closed) full body if the ray-parity test says so
    inside = body.contains(v[np.nonzero(dist < 3.0)[0]]) if (dist < 3.0).any() else np.array([], bool)
    sd = -dist; sd[np.nonzero(dist < 3.0)[0][inside]] *= -1
rec = {"src": src, "delta_deg": d, "hinge_mm": [yh, zh], "watertight": bool(r.is_watertight),
       "volume_mm3": round(float(r.volume), 2), "bbox_mm": np.round(r.bounds, 3).tolist(),
       "min_clearance_mm": round(float(-sd.max()), 4), "vertices_inside_body": int((sd > 0).sum()),
       "sampled_vertices": int(len(idx)), "te_point_mm": np.round(v[np.argmax(v[:, 2] if d >= 0 else v[:, 2])], 3).tolist()}
r.apply_scale(0.001); r.export(outp)
json.dump(rec, open(js, "w"), indent=1); print(json.dumps(rec))
