from pathlib import Path
import importlib.util,sys,os,json,hashlib
src=Path('/work/phase15_inlet_worker_prism_final3.py');base=Path('/work/cfd_failed_solver_replay3_20261105');assert not base.exists();base.mkdir();b=base/'bin';b.mkdir()
fail='mkdir -p postProcessing/inletpt/0 postProcessing/outletpt/0; printf "100 1 0 0 1\\n" > postProcessing/inletpt/0/surfaceFieldValue.dat; printf "100 1 0 0 1\\n" > postProcessing/outletpt/0/surfaceFieldValue.dat; exit 7'
cmds={'gmsh':'cp /work/cfd_duct_patch_candidate2_20261105/duct.msh duct.msh','gmshToFoam':'exit 0','checkMesh':'cat /work/cfd_duct_prism_repro_check/checkMesh.log','simpleFoam':fail}
for name,cmd in cmds.items():
 p=b/name;p.write_text('#!/bin/sh\nset -e\n'+cmd+'\n');p.chmod(0o755)
os.environ['PATH']=str(b)+':'+os.environ['PATH']
spec=importlib.util.spec_from_file_location('worker',src);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sys.argv=['worker','--work',str(base/'work'),'--output',str(base/'out'),'--mesh','prism']
m.main();result=json.loads((base/'out/phase15_inlet_result.json').read_text())
assert result['evidence']['steps']['simpleFoam']['rc']==7
assert result['status']=='solver-failed' and result['internalRecovery'] is None and result['inletTotalPressure'] is None and result['outletTotalPressure'] is None
receipt={'worker_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'status':result['status'],'solver_exit':7,'recovery':None,'scope':'mocked failed solver and stale pressure files; no CFD solve'}
(base/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
