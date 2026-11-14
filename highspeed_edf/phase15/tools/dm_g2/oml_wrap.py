#!/usr/bin/env python3
"""Watertight surface wrap of the fused Phase-15 OML (DM-G2 meshing input).

1. OCCT tessellation of the fused BREP (BRepMesh_IncrementalMesh; robust to faces
   gmsh could not mesh).
2. Voxel wrap at pitch h: surface voxels, 1-voxel dilation (seals gaps < ~2h),
   flood fill from the domain corner, 1-voxel erosion of the solid (closing),
   Gaussian-smoothed indicator, marching cubes at 0.5.
3. Decimation to a target face count; watertight/manifold checks.
4. Fidelity: distance from wrap vertices to the CAD tessellation and from CAD
   samples to the wrap (mean/p95/max), so the geometric deviation is measured.
Output: <out>/oml_wrap.stl (mm) + oml_wrap.json receipt. Read-only on the BREP.
usage: oml_wrap.py <fused.brep> <outdir> <pitch_mm> <target_faces>
"""
import json, sys, time
import numpy as np

from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Shape
import trimesh
from scipy import ndimage
from skimage import measure
import fast_simplification

brep, out, h, target = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
t0 = time.time(); rec = {"brep": brep, "pitch_mm": h, "target_faces": target}

shape = TopoDS_Shape(); BRepTools.Read_s(shape, brep, BRep_Builder())
BRepMesh_IncrementalMesh(shape, 0.05, False, 0.25, True)
V, F, off, nface, nfail = [], [], 0, 0, 0
exp = TopExp_Explorer(shape, TopAbs_FACE)
while exp.More():
    face = TopoDS.Face(exp.Current()) if hasattr(TopoDS, "Face") else TopoDS.Face_s(exp.Current()); nface += 1
    loc = TopLoc_Location(); tri = BRep_Tool.Triangulation_s(face, loc)
    if tri is None:
        nfail += 1; exp.Next(); continue
    trsf = loc.Transformation()
    pts = [tri.Node(i).Transformed(trsf) for i in range(1, tri.NbNodes() + 1)]
    V.append(np.array([[p.X(), p.Y(), p.Z()] for p in pts]))
    rev = face.Orientation() == TopAbs_REVERSED
    for i in range(1, tri.NbTriangles() + 1):
        a, b, c = tri.Triangle(i).Get()
        F.append([a - 1 + off, c - 1 + off, b - 1 + off] if rev else [a - 1 + off, b - 1 + off, c - 1 + off])
    off += tri.NbNodes(); exp.Next()
cad = trimesh.Trimesh(np.vstack(V), np.array(F), process=True)
rec.update({"brep_faces": nface, "faces_without_triangulation": nfail, "cad_triangles": int(len(cad.faces)),
            "cad_bbox_mm": np.round(cad.bounds.ravel(), 2).tolist(), "cad_watertight": bool(cad.is_watertight)})
cad.export(f"{out}/oml_cad_tess.stl")

# voxel wrap
pad = 4
lo = cad.bounds[0] - pad * h
shp = np.ceil((cad.bounds[1] - cad.bounds[0]) / h).astype(int) + 2 * pad + 1
surf = np.zeros(shp, bool)
# dense surface sampling (spacing <= h/3) marks every surface voxel
area = cad.area_faces
n_per = np.maximum(1, np.ceil(area / (h / 3) ** 2)).astype(int)
for chunk in np.array_split(np.arange(len(cad.faces)), 64):
    tri = cad.triangles[chunk]; k = n_per[chunk]
    rep = np.repeat(np.arange(len(chunk)), k)
    r1, r2 = np.random.default_rng(0).random((2, len(rep)))
    s = np.sqrt(r1)
    p = (1 - s)[:, None] * tri[rep, 0] + (s * (1 - r2))[:, None] * tri[rep, 1] + (s * r2)[:, None] * tri[rep, 2]
    p = np.vstack([p, tri.reshape(-1, 3)])
    ijk = np.floor((p - lo) / h).astype(int)
    surf[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = True
wall = ndimage.binary_dilation(surf, iterations=1)
lab, _ = ndimage.label(~wall)
exterior = lab == lab[0, 0, 0]
solid = ndimage.binary_erosion(~exterior, iterations=1)
rec["grid"] = shp.tolist(); rec["solid_voxels"] = int(solid.sum())
lab2, nsolid = ndimage.label(solid); rec["solid_components"] = int(nsolid)
field = ndimage.gaussian_filter(solid.astype(np.float32), 0.8)
verts, faces, _, _ = measure.marching_cubes(field, 0.5, spacing=(h, h, h))
verts += lo
wrap = trimesh.Trimesh(verts, faces[:, ::-1], process=True)
rec["wrap_faces_raw"] = int(len(wrap.faces))
if len(wrap.faces) > target:
    v2, f2 = fast_simplification.simplify(wrap.vertices.astype(np.float32), wrap.faces.astype(np.int64),
                                          target_reduction=1 - target / len(wrap.faces))
    wrap = trimesh.Trimesh(v2, f2, process=True)
trimesh.repair.fix_normals(wrap)
# keep the largest bodies only if tiny floaters appear
parts = wrap.split(only_watertight=False)
rec["wrap_components"] = len(parts)
rec.update({"wrap_faces": int(len(wrap.faces)), "wrap_watertight": bool(wrap.is_watertight),
            "wrap_winding_consistent": bool(wrap.is_winding_consistent), "wrap_volume_mm3": float(wrap.volume),
            "wrap_bbox_mm": np.round(wrap.bounds.ravel(), 2).tolist(), "euler": int(wrap.euler_number)})
# fidelity
rng = np.random.default_rng(1)
wv = wrap.vertices[rng.choice(len(wrap.vertices), min(60000, len(wrap.vertices)), replace=False)]
_, d1, _ = trimesh.proximity.closest_point(cad, wv)
cs, _ = trimesh.sample.sample_surface(cad, 60000, seed=2)
_, d2, _ = trimesh.proximity.closest_point(wrap, cs)
st = lambda d: {"mean": round(float(d.mean()), 3), "p95": round(float(np.percentile(d, 95)), 3), "max": round(float(d.max()), 3)}
rec["deviation_wrap_to_cad_mm"] = st(d1); rec["deviation_cad_to_wrap_mm"] = st(d2)
rec["cad_area_frac_within_1p5h"] = round(float((d2 <= 1.5 * h).mean()), 4)
wrap.export(f"{out}/oml_wrap.stl")
rec["seconds"] = round(time.time() - t0, 1)
json.dump(rec, open(f"{out}/oml_wrap.json", "w"), indent=1); print(json.dumps(rec, indent=1))
