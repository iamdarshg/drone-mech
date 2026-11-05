from pathlib import Path
import importlib.util,sys,os,json,hashlib
src=Path('/work/phase15_inlet_worker_prism_final3.py');base=Path('/work/cfd_prism_worker_replay_final3_20261105');assert not base.exists();base.mkdir();b=base/'bin';b.mkdir()
cmds={'gmsh':'cp /work/cfd_duct_patch_candidate2_20261105/duct.msh duct.msh','gmshToFoam':'exit 0','checkMesh':'cat /work/cfd_duct_prism_repro_check/checkMesh.log','simpleFoam':'echo STUB_SOLVER_NOT_A_FLOW_RUN'}
for name,cmd in cmds.items():
 p=b/name;p.write_text('#!/bin/sh\nset -e\n'+cmd+'\n');p.chmod(0o755)
os.environ['PATH']=str(b)+':'+os.environ['PATH']
spec=importlib.util.spec_from_file_location('worker',src);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sys.argv=['worker','--work',str(base/'work'),'--output',str(base/'out'),'--mesh','prism']
m.main();result=json.loads((base/'out/phase15_inlet_result.json').read_text())
assert result['evidence']['steps']['prismMesh']['rc']==0
assert result['evidence']['steps']['checkMesh']['rc']==0
assert result['evidence']['steps']['simpleFoam']['rc']==0
assert result['status']=='no-recovery-extracted' and result['internalRecovery'] is None
mesh=base/'work/duct/duct.msh'
assert hashlib.sha256(mesh.read_bytes()).hexdigest()==hashlib.sha256(Path('/work/duct_prism_repro.msh').read_bytes()).hexdigest()
receipt={'worker_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'prism_script_sha256':hashlib.sha256(Path('/work/prism_duct_mesh.py').read_bytes()).hexdigest(),'generated_mesh_sha256':hashlib.sha256(mesh.read_bytes()).hexdigest(),'status':result['status'],'scope':'Actual prism generator and worker; external gmsh, OpenFOAM mesh check and solver commands stubbed/replayed, no CFD solve'}
(base/'replay_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
