#!/usr/bin/env python3
"""Remove residual sliver triangles from a closed shell by guarded edge collapse.

For every triangle with min angle < A (default 20 deg): collapse its shortest edge to the
midpoint. A collapse is rejected (reverted) if any surviving incident face flips its normal
by more than 60 deg or becomes degenerate. Repeats up to 6 rounds. Watertightness is
re-checked; max vertex displacement is recorded. In-place on each given STL (metres).
usage: sliver_collapse.py <out.json> <shell0.stl> [shell1.stl ...]
"""
import json, sys
import numpy as np
import trimesh

A = 20.0
rec = {"min_angle_threshold_deg": A, "shells": []}


def tri_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    a = np.linalg.norm(n, axis=1)
    return n / np.maximum(a, 1e-300)[:, None], a


def min_angles(V, F):
    return np.degrees(trimesh.triangles.angles(V[F])).min(1)


for path in sys.argv[2:]:
    m = trimesh.load(path, process=True)
    V, F = m.vertices.copy(), m.faces.copy()
    V0 = V.copy()
    before = int((min_angles(V, F) < A).sum())
    done = rejected = 0
    for rnd in range(6):
        bad = np.where(min_angles(V, F) < A)[0]
        if not len(bad):
            break
        for fi in bad:
            tri = F[fi]
            if len(set(tri.tolist())) < 3 or min_angles(V, F[fi:fi + 1])[0] >= A:
                continue  # already removed or fixed earlier in this round
            e = [(tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])]
            L = [np.linalg.norm(V[a] - V[b]) for a, b in e]
            u, v = e[int(np.argmin(L))]
            inc = np.where((F == u).any(1) | (F == v).any(1))[0]
            n_old, _ = tri_normals(V, F[inc])
            Vn = V.copy(); Vn[u] = 0.5 * (V[u] + V[v])
            Fn = F.copy(); Fn[Fn == v] = u
            if np.linalg.norm(V[u] - V[v]) == 0:
                continue
            keep = np.array([len(set(f.tolist())) == 3 for f in Fn[inc]])
            n_new, area = tri_normals(Vn, Fn[inc])
            ok = keep.sum() > 0 and np.all((n_old[keep] * n_new[keep]).sum(1) > 0.5) and np.all(area[keep] > 1e-14)
            if not ok:
                rejected += 1
                continue
            V, F = Vn, Fn  # degenerate faces stay in place until the round ends (indices stable)
            done += 1
        F = F[np.array([len(set(f.tolist())) == 3 for f in F])]
    out = trimesh.Trimesh(V, F, process=True)
    out.remove_unreferenced_vertices()
    after_ang = min_angles(out.vertices, out.faces)
    _, d, _ = trimesh.proximity.closest_point(m, out.vertices)
    row = {"file": path, "slivers_before": before, "collapses": done, "rejected": rejected,
           "slivers_after": int((after_ang < A).sum()), "min_angle_after": round(float(after_ang.min()), 2),
           "watertight": bool(out.is_watertight), "winding_consistent": bool(out.is_winding_consistent),
           "faces": int(len(out.faces)), "max_dev_from_input_mm": round(float(d.max()) * 1e3, 3)}
    rec["shells"].append(row)
    if out.is_watertight and out.is_winding_consistent:
        out.export(path)
    else:
        row["written"] = False
print(json.dumps(rec, indent=1)); json.dump(rec, open(sys.argv[1], "w"), indent=1)
