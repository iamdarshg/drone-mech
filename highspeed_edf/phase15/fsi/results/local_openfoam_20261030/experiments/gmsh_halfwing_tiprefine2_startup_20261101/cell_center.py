from pathlib import Path
import numpy as np,re
m=Path('/tmp/gmsh_halfwing_fluid/ias900_case/constant/polyMesh')
def body(name):
 s=(m/name).read_text(); start=s.index('\n(',s.index('object'))+2; end=s.rfind(')'); return s[start:end].strip()
# Points are one tuple per line.
pts=np.array([[float(x) for x in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',line)] for line in body('points').splitlines() if line.strip()],dtype=float)
# Read owner/neighbour label lists.
owner=np.fromstring(body('owner'),sep=' ',dtype=np.int64)
nei=np.fromstring(body('neighbour'),sep=' ',dtype=np.int64)
faces=[]
for line in body('faces').splitlines():
 line=line.strip()
 if not line: continue
 # after face point-count prefix, parentheses hold point labels
 a=line.find('('); b=line.rfind(')')
 faces.append([int(x) for x in line[a+1:b].split()])
print('points',pts.shape,'faces',len(faces),'owner',owner.size,'neigh',nei.size)
nCells=int(max(owner.max(),nei.max())+1); centers=np.zeros((nCells,3)); counts=np.zeros(nCells)
for i,ids in enumerate(faces):
 c=pts[ids].mean(axis=0)
 o=owner[i]; centers[o]+=c; counts[o]+=1
 if i<nei.size:
  n=nei[i]; centers[n]+=c; counts[n]+=1
centers/=counts[:,None]
for idx in (36858,115521):
 ids=np.where((owner==idx)|((np.arange(owner.size)<nei.size)&(np.r_[nei,np.full(owner.size-nei.size,-1)]==idx)))[0]
 def patch(i):
  if i<1595383:return 'internal'
  if i<1606107:return 'symmetryPlane'
  if i<1613469:return 'farfield'
  if i<1614331:return 'outlet'
  if i<1615193:return 'inlet'
  return 'halfwing'
 print('cell',idx,'center',centers[idx].tolist(),'faces',[(int(i),patch(i)) for i in ids]);
 for i in ids:
  if patch(int(i))=='halfwing': print('wall-face',i,'vertices',pts[faces[i]].tolist())
