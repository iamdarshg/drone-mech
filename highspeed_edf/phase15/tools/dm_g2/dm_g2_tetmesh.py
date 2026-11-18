#!/usr/bin/env python3
"""DM-G2 candidate volume mesh: far-field box around the wrapped Phase-15 OML.

Input: comma-separated closed-shell STLs in metres (oml_remesh_shell*_m.stl, isotropically
remeshed by oml_remesh.py). The wall triangulation is kept as-is (no reparametrization);
2. box domain (flow along +z, nose at -z): x,y in [-B, B], z in [zmin-U, zmax+D];
3. unstructured tets (Distance/Threshold size field wall_h -> far_h), Netgen optimisation;
4. physical groups: aircraft (wall), inlet (z-), outlet (z+), farfield (4 sides), fluid;
5. writes MSH 2.2 ASCII for gmshToFoam + JSON receipt (counts, gmsh quality stats).
usage: dm_g2_tetmesh.py <shell0.stl,shell1.stl> <outdir> [wall_h_m=0.003] [far_h_m=0.25]
"""
import json, math, sys, time
import numpy as np
import gmsh

stl, out = sys.argv[1], sys.argv[2]
wall_h = float(sys.argv[3]) if len(sys.argv) > 3 else 0.003
far_h = float(sys.argv[4]) if len(sys.argv) > 4 else 0.25
B, U, D = 2.0, 2.0, 4.0
t0 = time.time(); rec = {"input": stl, "wall_h_m": wall_h, "far_h_m": far_h, "box_half_xy_m": B, "upstream_m": U, "downstream_m": D}
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 1); gmsh.option.setNumber("General.NumThreads", 8)
for path in stl.split(","):
    gmsh.merge(path)
nodes, coords, _ = gmsh.model.mesh.getNodes()
# each merged STL is one closed discrete surface; used directly as a hole loop
body = [t for _, t in gmsh.model.getEntities(2)]
# group discrete surfaces into closed shells via shared boundary curves
parent = {s: s for s in body}
def find(s):
    while parent[s] != s:
        parent[s] = parent[parent[s]]; s = parent[s]
    return s
owner = {}
for s in body:
    for _, c in gmsh.model.getBoundary([(2, s)], oriented=False):
        c = abs(c)
        if c in owner:
            parent[find(s)] = find(owner[c])
        else:
            owner[c] = s
shells = {}
for s in body:
    shells.setdefault(find(s), []).append(s)
rec["body_surfaces"] = len(body); rec["shells"] = len(shells)
xyz = coords.reshape(-1, 3)
lo, hi = xyz.min(0), xyz.max(0)
rec["body_bbox_m"] = np.round(np.r_[lo, hi], 4).tolist()
x0, x1, y0, y1 = -B, B, -B, B
z0, z1 = lo[2] - U, hi[2] + D
g = gmsh.model.geo
P = {}
for i, (x, y, z) in enumerate([(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]):
    P[i] = g.addPoint(x, y, z, far_h)
def L(a, b): return g.addLine(P[a], P[b])
# corners: index = 4*zi + 2*yi + xi
l = {k: L(*k) for k in [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]}
def loop(*edges):
    seq = []
    for a, b in edges:
        seq.append(l[(a, b)] if (a, b) in l else -l[(b, a)])
    return g.addPlaneSurface([g.addCurveLoop(seq)])
inlet = loop((0, 1), (1, 3), (3, 2), (2, 0))
outlet = loop((4, 5), (5, 7), (7, 6), (6, 4))
side = [loop((0, 1), (1, 5), (5, 4), (4, 0)), loop((2, 3), (3, 7), (7, 6), (6, 2)),
        loop((0, 2), (2, 6), (6, 4), (4, 0)), loop((1, 3), (3, 7), (7, 5), (5, 1))]
box_loop = g.addSurfaceLoop([inlet, outlet] + side)
holes = [g.addSurfaceLoop(v) for v in shells.values()]
vol = g.addVolume([box_loop] + holes)
g.synchronize()
gmsh.model.addPhysicalGroup(2, body, name="aircraft")
gmsh.model.addPhysicalGroup(2, [inlet], name="inlet")
gmsh.model.addPhysicalGroup(2, [outlet], name="outlet")
gmsh.model.addPhysicalGroup(2, side, name="farfield")
gmsh.model.addPhysicalGroup(3, [vol], name="fluid")
f = gmsh.model.mesh.field
fd = f.add("Distance"); f.setNumbers(fd, "SurfacesList", body); f.setNumber(fd, "Sampling", 40)
ft = f.add("Threshold"); f.setNumber(ft, "InField", fd)
f.setNumber(ft, "SizeMin", wall_h); f.setNumber(ft, "SizeMax", far_h)
f.setNumber(ft, "DistMin", 0.002); f.setNumber(ft, "DistMax", 1.6)
f.setAsBackgroundMesh(ft)
for k, v in {"Mesh.MeshSizeExtendFromBoundary": 0, "Mesh.MeshSizeFromPoints": 0, "Mesh.MeshSizeFromCurvature": 0,
             "Mesh.Algorithm": 6, "Mesh.Algorithm3D": 10, "Mesh.Optimize": 1, "Mesh.OptimizeNetgen": 1,
             "Mesh.OptimizeThreshold": 0.3, "Mesh.MshFileVersion": 2.2, "Mesh.Binary": 0}.items():
    gmsh.option.setNumber(k, v)
try:
    gmsh.model.mesh.generate(2); rec["mesh2d"] = "ok"
    gmsh.model.mesh.generate(3); rec["mesh3d"] = "ok"
    gmsh.model.mesh.optimize("Netgen"); rec["netgen_opt"] = "ok"
except Exception as e:
    rec["error"] = str(e)
try:
    types, tags, _ = gmsh.model.mesh.getElements(3)
    rec["tets"] = int(sum(len(t) for t in tags))
    tri = gmsh.model.mesh.getElements(2, -1)
    rec["boundary_tris"] = int(sum(len(t) for t in tri[1]))
    if rec["tets"]:
        allt = np.concatenate(tags)
        q = np.array(gmsh.model.mesh.getElementQualities(allt, "minSICN"))
        g2 = np.array(gmsh.model.mesh.getElementQualities(allt, "gamma"))
        rec["minSICN"] = {"min": float(q.min()), "p01": float(np.percentile(q, 1)), "frac_lt_0.1": float((q < 0.1).mean())}
        rec["gamma"] = {"min": float(g2.min()), "p01": float(np.percentile(g2, 1))}
        gmsh.write(f"{out}/dm_g2_tet.msh")
except Exception as e:
    rec["export_error"] = str(e)
rec["seconds"] = round(time.time() - t0, 1)
gmsh.finalize()
json.dump(rec, open(f"{out}/dm_g2_tet.json", "w"), indent=1); print(json.dumps(rec, indent=1))
