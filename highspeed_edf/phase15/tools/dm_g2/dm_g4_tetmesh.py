#!/usr/bin/env python3
"""DM-G4 volume mesh (derived from dm_g2_tetmesh.py): far-field box around the wrapped Phase-15 OML
without elevons, plus each elevon as its own CAD-tessellated closed shell and wall patch
(elevon_L, elevon_R) so hinge moments are integrated per surface. A second Distance field
refines toward the elevons (elev_h). Flow along +z; angle of attack is set by the inflow BC.

Input: comma-separated closed-shell STLs in metres (oml_remesh_shell*_m.stl, isotropically
remeshed by oml_remesh.py). The wall triangulation is kept as-is (no reparametrization);
2. box domain (flow along +z, nose at -z): x,y in [-B, B], z in [zmin-U, zmax+D];
3. unstructured tets (Distance/Threshold size field wall_h -> far_h), Netgen optimisation;
4. physical groups: aircraft (wall), inlet (z-), outlet (z+), farfield (4 sides), fluid;
5. writes MSH 2.2 ASCII for gmshToFoam + JSON receipt (counts, gmsh quality stats).
usage: dm_g4_tetmesh.py <body0.stl,body1.stl> <elevL.stl> <elevR.stl> <outdir> [wall_h_m=0.003] [far_h_m=0.25] [elev_h_m=0.0007]
"""
import json, math, os, sys, time
import numpy as np
import gmsh

stl, elL, elR, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
wall_h = float(sys.argv[5]) if len(sys.argv) > 5 else 0.003
far_h = float(sys.argv[6]) if len(sys.argv) > 6 else 0.25
elev_h = float(sys.argv[7]) if len(sys.argv) > 7 else 0.0007
B, U, D = 2.0, 2.0, 4.0
t0 = time.time(); rec = {"input": stl, "elevons": [elL, elR], "elev_h_m": elev_h, "wall_h_m": wall_h, "far_h_m": far_h, "box_half_xy_m": B, "upstream_m": U, "downstream_m": D}
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 1); gmsh.option.setNumber("General.NumThreads", 8)
n_before = 0; groups = {}
for name, paths in (("aircraft", stl.split(",")), ("elevon_L", [elL]), ("elevon_R", [elR])):
    for path in paths:
        gmsh.merge(path)
    now = [t for _, t in gmsh.model.getEntities(2)]
    groups[name] = now[n_before:]; n_before = len(now)
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
for name, ss in groups.items():
    gmsh.model.addPhysicalGroup(2, ss, name=name)
gmsh.model.addPhysicalGroup(2, [inlet], name="inlet")
gmsh.model.addPhysicalGroup(2, [outlet], name="outlet")
gmsh.model.addPhysicalGroup(2, side, name="farfield")
gmsh.model.addPhysicalGroup(3, [vol], name="fluid")
f = gmsh.model.mesh.field
fd = f.add("Distance"); f.setNumbers(fd, "SurfacesList", body); f.setNumber(fd, "Sampling", 40)
ft = f.add("Threshold"); f.setNumber(ft, "InField", fd)
f.setNumber(ft, "SizeMin", wall_h); f.setNumber(ft, "SizeMax", far_h)
f.setNumber(ft, "DistMin", 0.002); f.setNumber(ft, "DistMax", 1.6)
fe = f.add("Distance"); f.setNumbers(fe, "SurfacesList", groups["elevon_L"] + groups["elevon_R"]); f.setNumber(fe, "Sampling", 60)
fte = f.add("Threshold"); f.setNumber(fte, "InField", fe)
f.setNumber(fte, "SizeMin", elev_h); f.setNumber(fte, "SizeMax", far_h)
f.setNumber(fte, "DistMin", 0.001); f.setNumber(fte, "DistMax", 0.6)
flist = [ft, fte]
# trailing-edge refinement tubes: TE_LINES="xc,hs,yt,zt;..." (metres): size = te_h + 0.25*d, d = distance
# to the segment {x in [xc-hs, xc+hs], y=yt, z=zt}; sqrt/abs-only form for MathEval
import os
te_h = float(os.environ.get("TE_H", "0.00025")); rec["te_lines"] = os.environ.get("TE_LINES", ""); rec["te_h_m"] = te_h
for line in filter(None, os.environ.get("TE_LINES", "").split(";")):
    xc, hs, yt, zt = (float(v) for v in line.split(","))
    u = f"(Abs(x-({xc}))-({hs}))"
    expr = f"{te_h}+0.25*Sqrt((y-({yt}))^2+(z-({zt}))^2+(({u}+Abs({u}))/2)^2)"
    fx = f.add("MathEval"); f.setString(fx, "F", expr); flist.append(fx)
fm = f.add("Min"); f.setNumbers(fm, "FieldsList", flist)
f.setAsBackgroundMesh(fm)
for k, v in {"Mesh.MeshSizeExtendFromBoundary": 0, "Mesh.MeshSizeFromPoints": 0, "Mesh.MeshSizeFromCurvature": 0,
             "Mesh.Algorithm": 6, "Mesh.Algorithm3D": 10, "Mesh.Optimize": 1, "Mesh.OptimizeNetgen": 1,
             "Mesh.OptimizeThreshold": float(os.environ.get("OPT_THR", "0.3")), "Mesh.MshFileVersion": 2.2, "Mesh.Binary": 0}.items():
    gmsh.option.setNumber(k, v)
try:
    gmsh.model.mesh.generate(2); rec["mesh2d"] = "ok"
    gmsh.model.mesh.generate(3); rec["mesh3d"] = "ok"
    if os.environ.get("NETGEN", "1") == "1":
        for _ in range(int(os.environ.get("NETGEN_PASSES", "1"))):
            gmsh.model.mesh.optimize("Netgen")
        rec["netgen_opt"] = f"ok x{os.environ.get('NETGEN_PASSES', '1')}"
    else:
        rec["netgen_opt"] = "skipped (NETGEN=0)"
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
        gmsh.write(f"{out}/dm_g4_tet.msh")
except Exception as e:
    rec["export_error"] = str(e)
rec["seconds"] = round(time.time() - t0, 1)
gmsh.finalize()
json.dump(rec, open(f"{out}/dm_g4_tet.json", "w"), indent=1); print(json.dumps(rec, indent=1))
