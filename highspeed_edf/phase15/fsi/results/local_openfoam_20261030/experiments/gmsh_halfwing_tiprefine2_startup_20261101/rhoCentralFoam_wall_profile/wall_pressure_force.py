#!/usr/bin/env python3
from pathlib import Path
import gzip,json,re,sys,numpy as np
case=Path(sys.argv[1]);tm=sys.argv[2];mesh=case/'constant/polyMesh';d=case/tm
num=re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
def body(path):
 s=path.read_text();start=s.index('\n(',s.index('object'))+2;end=s.rfind(')');return s[start:end].strip()
def floats(path):
 if Path(str(path)+'.gz').exists():
  with gzip.open(str(path)+'.gz','rt') as f:s=f.read()
 else:s=Path(path).read_text()
 a=s.index('internalField');o=s.index('(',s.index('nonuniform',a));e=s.index('\n)',o);return np.fromiter((float(x) for x in num.findall(s[o+1:e])),dtype=float)
points=np.array([[float(x) for x in num.findall(line)] for line in body(mesh/'points').splitlines() if line.strip()])
owner=np.fromstring(body(mesh/'owner'),sep=' ',dtype=np.int64)
faces=[]
for line in body(mesh/'faces').splitlines():
 line=line.strip()
 if line:
  a=line.find('(');b=line.rfind(')');faces.append(np.fromstring(line[a+1:b],sep=' ',dtype=np.int64))
b=(mesh/'boundary').read_text();m=re.search(r'\n    halfwing\s*\{.*?nFaces\s+(\d+);\s*startFace\s+(\d+);',b,re.S);n,start=map(int,m.groups());ids=np.arange(start,start+n)
if any(len(faces[i])!=3 for i in ids):raise SystemExit('non-triangular wall face')
tri=np.array([faces[i] for i in ids]);v=points[tri];avec=np.cross(v[:,1]-v[:,0],v[:,2]-v[:,0])/2
p=floats(d/'p');ow=owner[ids];pref=70100.;F=np.einsum('n,ni->i',p[ow]-pref,avec)
print(json.dumps({'time':tm,'pressureForceHalfwingN':F.tolist(),'netAreaVectorM2':avec.sum(axis=0).tolist(),'wallFaceCount':len(ids),'pressureGaugeReferencePa':pref,'viscousForce':'omitted: no resolved boundary-layer/y+ support'}))
