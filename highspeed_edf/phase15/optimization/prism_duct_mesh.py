#!/usr/bin/env python3
"""Extrude a Gmsh-2 inlet triangulation into a tapered prism duct mesh.

This is an experimental mesh generator, not an aerodynamic validation. The
inlet and outlet must be planar, circular end caps of a coaxial linear taper.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import math
from pathlib import Path


def generate(source: Path, output: Path, layers: int, r_in: float, r_out: float, length: float) -> None:
    if layers < 1 or min(r_in, r_out, length) <= 0:
        raise ValueError('layers, radii and length must be positive')
    if source.resolve() == output.resolve():
        raise ValueError('source and output paths must differ')
    lines = source.read_text(encoding='utf-8').splitlines()

    def block(name: str) -> list[str]:
        index = lines.index('$' + name)
        count = int(lines[index + 1])
        return lines[index + 2:index + 2 + count]

    physical = {}
    for line in block('PhysicalNames'):
        dim, tag, name = line.split(maxsplit=2)
        physical[name.strip('"')] = (int(dim), int(tag))
    if set(physical) != {'inlet', 'outlet', 'walls', 'internal'}:
        raise ValueError('expected inlet, outlet, walls and internal physical groups')
    nodes = {}
    for line in block('Nodes'):
        fields = line.split()
        nodes[int(fields[0])] = tuple(map(float, fields[1:4]))
    inlet = []
    for line in block('Elements'):
        fields = line.split()
        element_type, count = int(fields[1]), int(fields[2])
        tags = list(map(int, fields[3:3 + count]))
        if element_type == 2 and tags and tags[0] == physical['inlet'][1]:
            inlet.append(list(map(int, fields[3 + count:])))
    if not inlet:
        raise ValueError('no inlet triangles')
    used = sorted({node for triangle in inlet for node in triangle})
    if any(abs(nodes[node][2]) > 1e-8 for node in used):
        raise ValueError('inlet triangles must be on z=0')
    mapping = {node: index + 1 for index, node in enumerate(used)}
    count = len(used)
    triangles = []
    edges = defaultdict(list)
    for ids in inlet:
        a, b, c = (nodes[node] for node in ids)
        cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(cross) <= 1e-16:
            raise ValueError('degenerate inlet triangle')
        if cross < 0:
            ids = [ids[0], ids[2], ids[1]]
        triangles.append([mapping[node] for node in ids])
        for u, v in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0])):
            edges[tuple(sorted((u, v)))].append((mapping[u], mapping[v]))
    if any(len(adjacent) > 2 for adjacent in edges.values()):
        raise ValueError('non-manifold inlet edge')
    perimeter = [adjacent[0] for adjacent in edges.values() if len(adjacent) == 1]
    if not perimeter:
        raise ValueError('inlet boundary is empty')
    reverse_mapping = {index: node for node, index in mapping.items()}
    for vertex in {node for edge in perimeter for node in edge}:
        x, y, _ = nodes[reverse_mapping[vertex]]
        if abs(math.hypot(x, y) - r_in) > 1e-5:
            raise ValueError('inlet boundary does not match the requested circular radius')
    elements = []

    def add(kind: int, name: str, entity: int, ids: list[int]) -> None:
        elements.append((kind, physical[name][1], entity, ids))

    for a, b, c in triangles:
        add(2, 'inlet', 3, [a, c, b])
        add(2, 'outlet', 2, [a + layers * count, b + layers * count, c + layers * count])
    for layer in range(layers):
        lo, hi = layer * count, (layer + 1) * count
        for a, b in perimeter:
            add(3, 'walls', 1, [a + lo, b + lo, b + hi, a + hi])
        for a, b, c in triangles:
            add(6, 'internal', 1, [a + lo, b + lo, c + lo, a + hi, b + hi, c + hi])
    with output.open('w', encoding='utf-8') as out:
        out.write('$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$PhysicalNames\n4\n')
        for name in ('inlet', 'walls', 'outlet', 'internal'):
            dim, tag = physical[name]
            out.write(f'{dim} {tag} "{name}"\n')
        out.write(f'$EndPhysicalNames\n$Nodes\n{count * (layers + 1)}\n')
        for layer in range(layers + 1):
            z = length * layer / layers
            scale = 1 + (r_out / r_in - 1) * layer / layers
            for old in used:
                x, y, _ = nodes[old]
                out.write(f'{mapping[old] + layer * count} {x * scale:.14g} {y * scale:.14g} {z:.14g}\n')
        out.write(f'$EndNodes\n$Elements\n{len(elements)}\n')
        for index, (kind, tag, entity, ids) in enumerate(elements, 1):
            out.write(f'{index} {kind} 2 {tag} {entity} ' + ' '.join(map(str, ids)) + '\n')
        out.write('$EndElements\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--layers', type=int, default=24)
    parser.add_argument('--r-in', type=float, default=.030)
    parser.add_argument('--r-out', type=float, default=.039)
    parser.add_argument('--length', type=float, default=.120)
    args = parser.parse_args()
    generate(args.source, args.output, args.layers, args.r_in, args.r_out, args.length)


if __name__ == '__main__':
    main()
