from pathlib import Path
import importlib.util,sys,json,hashlib
src=Path('/work/phase15_inlet_worker_prism_final3.py');spec=importlib.util.spec_from_file_location('worker',src);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
base=Path('/work/cfd_fresh_case_replay_20261105');assert not base.exists();case=base/'work/duct';case.mkdir(parents=True);marker=case/'old_result';marker.write_text('preserve')
sys.argv=['worker','--work',str(base/'work'),'--output',str(base/'out')]
try:m.main();raise AssertionError('existing case should be rejected')
except SystemExit as exc:assert 'Refusing to reuse existing case' in str(exc)
assert marker.read_text()=='preserve'
out={'worker_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'existing_case_rejected':True,'prior_data_preserved':True,'scope':'case-reuse guard test; no CFD solve'}
(base/'receipt.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
