from pathlib import Path
import re,math,json
root=Path('/work/cfd_duct_patch_candidate2_20261105');mesh=root/'constant/polyMesh'
def payload(file):
 text=file.read_text();m=re.search(r'\n\s*(\d+)\s*\n\(\s*\n',text);assert m
 return int(m.group(1)),text[m.end():]
n,s=payload(mesh/'points')
points=[tuple(float(v) for v in x.split()) for x in re.findall(r'\(([^()]*)\)',s)[:n]]
assert len(points)==n and all(len(x)==3 for x in points)
nf,s=payload(mesh/'faces');faces=[]
for m in re.finditer(r'(\d+)\(([^()]*)\)',s):
 k=int(m.group(1));x=[int(a) for a in m.group(2).split()];assert len(x)==k;faces.append(x)
 if len(faces)==nf:break
assert len(faces)==nf
nb,s=payload(mesh/'boundary');patches={}
for m in re.finditer(r'([\w.-]+)\s*\{([^{}]*)\}',s):
 body=m.group(2);nn=re.search(r'nFaces\s+(\d+)',body);st=re.search(r'startFace\s+(\d+)',body)
 if nn and st:patches[m.group(1)]=(int(st.group(1)),int(nn.group(1)))
assert set(patches)=={'inlet','outlet','walls'}
def area(face):
 a=points[face[0]];v=0.0
 for i in range(1,len(face)-1):
  b=points[face[i]];c=points[face[i+1]]
  x=[b[j]-a[j] for j in range(3)];y=[c[j]-a[j] for j in range(3)]
  cross=(x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0]);v+=.5*math.sqrt(sum(q*q for q in cross))
 return v
out={}
for name,(start,count) in patches.items():
 fs=faces[start:start+count];zs=[points[x][2] for f in fs for x in f]
 out[name]={'faces':count,'area_m2':sum(area(f) for f in fs),'z_min_m':min(zs),'z_max_m':max(zs)}
tol=1e-5
gate=abs(out['inlet']['z_min_m'])<tol and abs(out['inlet']['z_max_m'])<tol and abs(out['outlet']['z_min_m']-.12)<tol and abs(out['outlet']['z_max_m']-.12)<tol and out['walls']['z_min_m']<tol and out['walls']['z_max_m']>.12-tol
result={'source_commit':'candidate based on 023bc5c5af1ad6080225baacfa7c34e35b9c5fcd','patches':out,'expected':'inlet z=0 radius .030m; outlet z=.120 radius .039m; walls span full length','mapping_pass':gate,'scope':'native OpenFOAM mesh boundary geometry only; no flow solved'}
(root/'foam_patch_geometry.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if not gate:raise SystemExit('FAIL: duct physical patches do not match intended geometry')
