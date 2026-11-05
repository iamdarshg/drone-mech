from pathlib import Path
import importlib.util,sys,json,hashlib
src=Path('/work/phase15_inlet_worker_prism_final3.py')
spec=importlib.util.spec_from_file_location('worker',src);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
base=Path('/work/cfd_gate_replay_current3_20261105');assert not base.exists();base.mkdir()
actual=Path('/work/cfd_duct_patch_candidate2_20261105/checkMesh.log').read_text()
assert 'Failed 1 mesh checks.' in actual and '87' in actual and 'Mesh OK.' not in actual
missing=m.run(['/no/such/command'],base,base/'missing.log')
assert missing['rc'] is None and 'EXECUTION ERROR:' in (base/'missing.log').read_text()
calls=[]
def fake_run(args,cwd,log,timeout=300,env=None):
 calls.append(args[0])
 if args[0]=='simpleFoam':raise AssertionError('solver must not run on failed mesh')
 log.write_text(actual if args[0]=='checkMesh' else 'fixture command succeeded\n')
 return {'rc':0,'elapsed':0}
m.run=fake_run
sys.argv=['worker','--work',str(base/'work'),'--output',str(base/'out')]
m.main()
result=json.loads((base/'out/phase15_inlet_result.json').read_text())
assert result['status']=='blocked-mesh' and result['internalRecovery'] is None
assert calls==['gmsh','gmshToFoam','checkMesh']
receipt={'candidate_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'input_checkmesh_sha256':hashlib.sha256(actual.encode()).hexdigest(),'checkmesh_fixture':'actual candidate OpenFOAM log; external execution commands replayed','calls':calls,'status':result['status'],'missing_executable_handled':True}
(base/'replay_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
