from pathlib import Path
import hashlib,importlib.util,json,sys
source=Path('/work/phase15_inlet_worker_candidate2.py')
expected='887697c35ae2d094137cf0a95852b94af49eebb455dc68bc8dde63646ec8836c'
assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
case=Path('/work/cfd_duct_patch_candidate2_20261105');assert not case.exists()
spec=importlib.util.spec_from_file_location('inlet_worker',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.write_case(case,.030,.039,.120,.005,178.0)
sys.path.insert(0,'/work/vendor')
import gmsh
gmsh.initialize();gmsh.open(str(case/'duct.geo'));gmsh.model.mesh.generate(3);gmsh.option.setNumber('Mesh.MshFileVersion',2.2);gmsh.write(str(case/'duct.msh'))
report=[]
for dim,tag in gmsh.model.getPhysicalGroups(2):
 name=gmsh.model.getPhysicalName(dim,tag)
 for entity in gmsh.model.getEntitiesForPhysicalGroup(dim,tag):
  report.append({'name':name,'surface':int(entity),'bounds':list(gmsh.model.getBoundingBox(dim,int(entity))),'occ_area_m2':gmsh.model.occ.getMass(dim,int(entity))})
gmsh.finalize()
data={'source_commit':'candidate based on 023bc5c5af1ad6080225baacfa7c34e35b9c5fcd','worker_sha256':expected,'physical_surfaces':report,'scope':'CAD physical group diagnostic only; no flow solve or installed-inlet claim'}
(case/'gmsh_physical_surfaces.json').write_text(json.dumps(data,indent=2));print(json.dumps(data,indent=2))
