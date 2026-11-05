from pathlib import Path
import hashlib,json
src=Path('/work/cfd_duct_patch_candidate2_20261105/duct.msh');lines=src.read_text().splitlines()
def block(name):
 i=lines.index('$'+name);n=int(lines[i+1]);return lines[i+2:i+2+n]
phys=block('PhysicalNames');tag=next(int(x.split()[1]) for x in phys if x.endswith('"inlet"'))
els=[]
for l in block('Elements'):
 a=l.split();n=int(a[2])
 if int(a[1])==2 and int(a[3])==tag:els.append(l)
used={int(v) for l in els for v in l.split()[5:]}
nodes=[l for l in block('Nodes') if int(l.split()[0]) in used]
assert len(used)==len(nodes) and len(els)==292
dst=src.with_name('inlet_surface.msh')
with dst.open('w') as f:
 f.write('$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$PhysicalNames\n4\n'+'\n'.join(phys)+'\n$EndPhysicalNames\n')
 f.write('$Nodes\n'+str(len(nodes))+'\n'+'\n'.join(nodes)+'\n$EndNodes\n')
 f.write('$Elements\n'+str(len(els))+'\n'+'\n'.join(els)+'\n$EndElements\n')
print(json.dumps({'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'surface_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'nodes':len(nodes),'triangles':len(els)},indent=2))
