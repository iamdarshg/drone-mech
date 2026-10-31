#!/usr/bin/env python3
"""Export the source STEP wing skin as an open-root, one-region ASCII STL.

The root section is deliberately omitted: the CFD half-domain's x-min boundary
at x=0 supplies the symmetry plane.  This avoids overlapping a root-cap STL
surface with the coincident background symmetry boundary.
"""
from __future__ import annotations
import argparse
import hashlib
import math
from pathlib import Path
import gmsh


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-step", type=Path, required=True)
    parser.add_argument("--output-stl", type=Path, required=True)
    parser.add_argument("--root-x", type=float, default=0.0)
    parser.add_argument("--root-tolerance", type=float, default=2.0e-6)
    args = parser.parse_args()
    step = args.source_step.resolve()
    out = args.output_stl.resolve()
    if not step.is_file():
        raise SystemExit(f"STEP not found: {step}")

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        gmsh.model.add("source_halfwing")
        gmsh.model.occ.importShapes(str(step))
        gmsh.model.occ.synchronize()
        surfaces = sorted(tag for dim, tag in gmsh.model.getEntities(2) if dim == 2)
        root_surfaces = []
        skin_surfaces = []
        for tag in surfaces:
            bounds = gmsh.model.getBoundingBox(2, tag)
            if (abs(bounds[0] - args.root_x) <= args.root_tolerance and
                    abs(bounds[3] - args.root_x) <= args.root_tolerance):
                root_surfaces.append(tag)
            else:
                skin_surfaces.append(tag)
        if not root_surfaces or not skin_surfaces:
            raise RuntimeError(f"root/skin classification failed: root={root_surfaces}, skin={len(skin_surfaces)}")

        gmsh.option.setNumber("Mesh.MeshSizeMin", 0.001)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 0.005)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 12)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1)
        gmsh.option.setNumber("Mesh.Algorithm", 6)
        gmsh.model.mesh.generate(2)
        node_tags, coordinates, _ = gmsh.model.mesh.getNodes()
        nodes = {int(node_tags[i]): tuple(coordinates[3*i:3*i+3])
                 for i in range(len(node_tags))}
        out.parent.mkdir(parents=True, exist_ok=True)
        triangles = 0
        with out.open("w", encoding="ascii", newline="\n") as stream:
            stream.write("solid fsi\n")
            for surface in skin_surfaces:
                element_types, element_tags, element_nodes = gmsh.model.mesh.getElements(2, surface)
                for element_type, tags, connectivity in zip(element_types, element_tags, element_nodes):
                    if element_type != 2:
                        continue
                    for offset in range(len(tags)):
                        vertices = [nodes[int(n)] for n in connectivity[3*offset:3*offset+3]]
                        a = [vertices[1][i] - vertices[0][i] for i in range(3)]
                        b = [vertices[2][i] - vertices[0][i] for i in range(3)]
                        normal = [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]
                        magnitude = math.sqrt(sum(v*v for v in normal))
                        if magnitude == 0:
                            raise RuntimeError(f"zero-area triangle on surface {surface}, element {tags[offset]}")
                        normal = [v/magnitude for v in normal]
                        stream.write(" facet normal %.9g %.9g %.9g\n  outer loop\n" % tuple(normal))
                        for vertex in vertices:
                            stream.write("   vertex %.9g %.9g %.9g\n" % vertex)
                        stream.write("  endloop\n endfacet\n")
                        triangles += 1
            stream.write("endsolid\n")
        print({"source_step": str(step), "source_step_sha256": hashlib.sha256(step.read_bytes()).hexdigest(),
               "root_surfaces_omitted": root_surfaces, "skin_surfaces": len(skin_surfaces),
               "triangles": triangles, "stl": str(out), "stl_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
               "stl_bytes": out.stat().st_size})
    finally:
        gmsh.finalize()


if __name__ == "__main__":
    main()
