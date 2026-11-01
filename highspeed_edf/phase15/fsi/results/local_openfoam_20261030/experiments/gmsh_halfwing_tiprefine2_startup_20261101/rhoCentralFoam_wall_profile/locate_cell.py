#!/usr/bin/env python3
"""Get a cell's vertex bounds and face-center-mean location from OpenFOAM mesh lists."""
import argparse
from pathlib import Path
import re
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("polyMesh", type=Path, help="constant/polyMesh directory")
ap.add_argument("cell", type=int)
args = ap.parse_args()
mesh = args.polyMesh

def list_body(name):
    s = (mesh / name).read_text()
    start = s.index("\n(", s.index("object")) + 2
    return s[start:s.rfind(")")].strip()

number = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
points = np.array([
    [float(x) for x in number.findall(line)]
    for line in list_body("points").splitlines() if line.strip()
])
owner = np.fromstring(list_body("owner"), sep=" ", dtype=np.int64)
neighbour = np.fromstring(list_body("neighbour"), sep=" ", dtype=np.int64)
faces = []
for line in list_body("faces").splitlines():
    line = line.strip()
    if line:
        a, b = line.find("("), line.rfind(")")
        faces.append(np.fromstring(line[a + 1:b], sep=" ", dtype=np.int64))
if args.cell < 0 or args.cell >= max(owner.max(), neighbour.max()) + 1:
    raise SystemExit("cell id outside mesh")
vertex_ids, fc = set(), []
for i, face in enumerate(faces):
    if owner[i] == args.cell or (i < len(neighbour) and neighbour[i] == args.cell):
        vertex_ids.update(face.tolist())
        fc.append(points[face].mean(axis=0))
vertices = points[list(vertex_ids)]
print({
    "cell": args.cell,
    "nVertices": int(len(vertex_ids)),
    "nFaces": len(fc),
    "vertexBoundsMin_m": vertices.min(axis=0).tolist(),
    "vertexBoundsMax_m": vertices.max(axis=0).tolist(),
    "meanFaceCenter_m": np.mean(fc, axis=0).tolist(),
})
