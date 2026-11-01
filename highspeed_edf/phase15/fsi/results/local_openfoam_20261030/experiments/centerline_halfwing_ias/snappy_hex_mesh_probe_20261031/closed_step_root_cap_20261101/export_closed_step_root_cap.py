#!/usr/bin/env python3
"""Export STEP skin and its planar x=0 cap as named ASCII STL regions."""
import argparse, hashlib, math
from pathlib import Path
import gmsh

parser = argparse.ArgumentParser()
parser.add_argument('--source-step', type=Path, required=True)
parser.add_argument('--output-stl', type=Path, required=True)
args = parser.parse_args()
step, out = args.source_step.resolve(), args.output_stl.resolve()
gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 1)
gmsh.model.add('closed_halfwing')
gmsh.model.occ.importShapes(str(step))
gmsh.model.occ.synchronize()
surfaces = sorted(tag for dim, tag in gmsh.model.getEntities(2))
root, skin = [], []
for surface in surfaces:
    bounds = gmsh.model.getBoundingBox(2, surface)
    (root if abs(bounds[0]) < 2e-6 and abs(bounds[3]) < 2e-6 else skin).append(surface)
if not root or not skin:
    raise RuntimeError(f'root/skin classification failed: root={root}, skin={len(skin)}')
gmsh.option.setNumber('Mesh.ElementOrder', 1)
gmsh.option.setNumber('Mesh.MeshSizeMin', 0.0005)
gmsh.option.setNumber('Mesh.MeshSizeMax', 0.002)
gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', 12)
gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary', 1)
gmsh.option.setNumber('Mesh.Algorithm', 6)
gmsh.model.mesh.generate(2)
tags, coords, _ = gmsh.model.mesh.getNodes()
nodes = {int(tags[i]): tuple(coords[3*i:3*i+3]) for i in range(len(tags))}
out.parent.mkdir(parents=True, exist_ok=True)
counts = {'fsi': 0, 'rootCap': 0}
with out.open('w', encoding='ascii', newline='\n') as stream:
    for region, region_surfaces in (('fsi', skin), ('rootCap', root)):
        stream.write(f'solid {region}\n')
        for surface in region_surfaces:
            types, element_tags, connectivity = gmsh.model.mesh.getElements(2, surface)
            for kind, tags, conn in zip(types, element_tags, connectivity):
                if kind != 2:
                    continue
                for i in range(len(tags)):
                    tri = [nodes[int(n)] for n in conn[3*i:3*i+3]]
                    a = [tri[1][j]-tri[0][j] for j in range(3)]
                    b = [tri[2][j]-tri[0][j] for j in range(3)]
                    normal = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
                    mag = math.sqrt(sum(x*x for x in normal))
                    normal = [x/mag for x in normal]
                    stream.write(' facet normal %.9g %.9g %.9g\n  outer loop\n' % tuple(normal))
                    for point in tri:
                        stream.write('   vertex %.9g %.9g %.9g\n' % point)
                    stream.write('  endloop\n endfacet\n')
                    counts[region] += 1
        stream.write(f'endsolid {region}\n')
print({'gmsh': gmsh.__version__, 'root_surfaces': root, 'skin_surfaces': len(skin),
       'triangles': counts, 'stl_sha256': hashlib.sha256(out.read_bytes()).hexdigest()})
gmsh.finalize()
