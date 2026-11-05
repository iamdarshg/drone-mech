from pathlib import Path
import math,shutil,json,hashlib
root=Path('/work');source=root/'cfd_duct_patch_candidate2_20261105';dst=root/'cfd_duct_prisms_20261105'
assert not dst.exists();dst.mkdir()
for name in ['0','system','constant']:
 if name=='constant':
  (dst/name).mkdir()
  for x in (source/name).iterdir():
   if x.is_file():shutil.copy2(x,dst/name/x.name)
 else:shutil.copytree(source/name,dst/name)
lines=(source/'duct.msh').read_text().splitlines()
def block(name):
 i=lines.index('$'+name);n=int(lines[i+1]);return lines[i+2:i+2+n]
phys={}
for line in block('PhysicalNames'):
 dim,tag,name=line.split(maxsplit=2);phys[name.strip('"')]=(int(dim),int(tag))
assert set(phys)=={'inlet','outlet','walls','internal'}
nodes={}
for l in block('Nodes'):
 a=l.split();nodes[int(a[0])]=tuple(map(float,a[1:4]))
inlet=[]
for l in block('Elements'):
 a=l.split();typ=int(a[1]);nt=int(a[2]);tags=list(map(int,a[3:3+nt]))
 if typ==2 and tags[0]==phys['inlet'][1]:inlet.append(list(map(int,a[3+nt:])))
assert inlet
used=sorted({v for t in inlet for v in t})
assert all(abs(nodes[n][2])<1e-8 for n in used)
mapping={v:i+1 for i,v in enumerate(used)};n=len(used);layers=24
tri=[];edge={}
for ids in inlet:
 a,b,c=[nodes[x] for x in ids]
 cross=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 assert abs(cross)>1e-16
 if cross<0:ids=[ids[0],ids[2],ids[1]]
 tri.append([mapping[v] for v in ids])
 for u,v in [(ids[0],ids[1]),(ids[1],ids[2]),(ids[2],ids[0])]:
  key=tuple(sorted((u,v)));edge.setdefault(key,[]).append((mapping[u],mapping[v]))
perimeter=[v[0] for v in edge.values() if len(v)==1]
assert all(len(v)<=2 for v in edge.values()) and perimeter
elements=[]
def add(typ,tag,entity,ns):elements.append((typ,tag,entity,ns))
for a,b,c in tri:
 add(2,phys['inlet'][1],3,[a,c,b]);add(2,phys['outlet'][1],2,[a+layers*n,b+layers*n,c+layers*n])
for layer in range(layers):
 for a,b in perimeter:add(3,phys['walls'][1],1,[a+layer*n,b+layer*n,b+(layer+1)*n,a+(layer+1)*n])
 for a,b,c in tri:add(6,phys['internal'][1],1,[a+layer*n,b+layer*n,c+layer*n,a+(layer+1)*n,b+(layer+1)*n,c+(layer+1)*n])
with (dst/'duct.msh').open('w') as f:
 f.write('$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$PhysicalNames\n4\n')
 for name in ['inlet','walls','outlet','internal']:
  dim,tag=phys[name];f.write(f'{dim} {tag} "{name}"\n')
 f.write(f'$EndPhysicalNames\n$Nodes\n{n*(layers+1)}\n')
 for layer in range(layers+1):
  z=.12*layer/layers;scale=1+.3*layer/layers
  for old in used:
   x,y,_=nodes[old];f.write(f'{mapping[old]+layer*n} {x*scale:.14g} {y*scale:.14g} {z:.14g}\n')
 f.write(f'$EndNodes\n$Elements\n{len(elements)}\n')
 for idx,(typ,tag,entity,ns) in enumerate(elements,1):f.write(f'{idx} {typ} 2 {tag} {entity} '+' '.join(map(str,ns))+'\n')
 f.write('$EndElements\n')
data={'source_surface_mesh_sha256':hashlib.sha256((source/'duct.msh').read_bytes()).hexdigest(),'layers':layers,'inlet_nodes':n,'inlet_triangles':len(tri),'perimeter_edges':len(perimeter),'prism_cells':layers*len(tri),'scope':'mesh-only axial scaled extrusion of existing triangulated cone, no change to target dimensions, no flow solution'}
(dst/'mesh_manifest.json').write_text(json.dumps(data,indent=2));print(json.dumps(data,indent=2))
