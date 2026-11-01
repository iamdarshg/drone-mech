#!/usr/bin/env python3
"""Remove explicit feature edges lying entirely on the x=0 half-domain seam."""
import argparse, hashlib, re
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--emesh',type=Path,required=True)
p.add_argument('--proof',type=Path,required=True)
a=p.parse_args(); raw=a.emesh.read_text()
header=raw.split('// points:',1)[0]
psec=raw.split('// points:',1)[1].split('// edges:',1)[0]
esec=raw.split('// edges:',1)[1].split('// * * *',1)[0]
def rows(s):
    return [tuple(re.findall(r'[-+.0-9eE]+',line)) for line in s.splitlines() if line.strip().startswith('(')]
points=[tuple(map(float,r)) for r in rows(psec) if len(r)==3]
edges=[tuple(map(int,r)) for r in rows(esec) if len(r)==2]
kept=[]; removed=[]
for x,y in edges:
    (removed if abs(points[x][0])<1e-10 and abs(points[y][0])<1e-10 else kept).append((x,y))
if not removed: raise SystemExit('No x=0 seam edges found')
nl=chr(10)
body=header+'// points:'+nl+str(len(points))+nl+'('+nl+''.join('(%s %s %s)%s'%(p[0],p[1],p[2],nl) for p in points)+')'+nl+nl+'// edges:'+nl+str(len(kept))+nl+'('+nl+''.join('(%d %d)%s'%(e[0],e[1],nl) for e in kept)+')'+nl+nl+'// ************************************************************************* //'+nl
a.emesh.write_text(body)
a.proof.write_text(nl.join([f'points={len(points)}',f'original_edges={len(edges)}',f'removed_edges={len(removed)}',f'retained_edges={len(kept)}','removed endpoints checked: both x == 0 within 1e-10 m',f'removed_edge_sha256={hashlib.sha256(repr(removed).encode()).hexdigest()}'])+nl)
print(a.proof.read_text())
