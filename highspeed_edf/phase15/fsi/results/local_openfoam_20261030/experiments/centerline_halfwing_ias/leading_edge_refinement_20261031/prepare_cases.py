#!/usr/bin/env python3
"""Import the refined centerline mesh and prepare matching co0.1 transient cases."""
from __future__ import annotations
import hashlib,json,os,re,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=next(p for p in HERE.parents if (p/'highspeed_edf/phase15/optimization/phase15_fsi_casegen.py').is_file())
PKG=REPO/'highspeed_edf/phase15/fsi/results/local_openfoam_20261030'
FOAM=Path('/workspace/openfoam-deb').resolve()
ENV=os.environ.copy(); ENV.update({'WM_PROJECT_DIR':str(FOAM/'usr/share/openfoam'),'FOAM_LIBBIN':str(FOAM/'usr/lib'),'FOAM_APPBIN':str(FOAM/'usr/bin')})
ENV['LD_LIBRARY_PATH']=str(FOAM/'usr/lib')+(':'+ENV['LD_LIBRARY_PATH'] if ENV.get('LD_LIBRARY_PATH') else '')
MESH_MSH=HERE/'mesh/wing_centerline_le_refined.msh'

def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,cwd,log):
    with log.open('w') as f:subprocess.run(argv,cwd=cwd,env=ENV,stdout=f,stderr=subprocess.STDOUT,check=True)
def file_hashes(case:Path):return {str(p.relative_to(case)):sha(p) for p in sorted(case.rglob('*')) if p.is_file() and not p.is_symlink() and p.name!='run_manifest.json'}

if not MESH_MSH.exists():raise SystemExit(f'missing generated mesh: {MESH_MSH}')
stage=HERE/'import_case'; stage.mkdir(exist_ok=True); (stage/'system').mkdir(exist_ok=True)
source_case=PKG/'experiments/centerline_halfwing_ias/co010_fresh2_20261031/ias700'
for f in ('controlDict','fvSchemes','fvSolution'):
    shutil.copy2(source_case/'system'/f,stage/'system'/f)
shutil.copy2(MESH_MSH,stage/'wing.msh')
run([str(FOAM/'usr/bin/gmshToFoam'),'wing.msh'],stage,HERE/'gmshToFoam.log')
boundary=stage/'constant/polyMesh/boundary'; b=boundary.read_text()
b=re.sub(r'(\bfsi\s*\{\s*type\s+)patch;',r'\1wall;',b)
b=re.sub(r'(\brootWall\s*\{\s*type\s+)patch;',r'\1symmetryPlane;',b)
boundary.write_text(b)
poly=HERE/'mesh/polyMesh'
if poly.exists():shutil.rmtree(poly)
shutil.copytree(stage/'constant/polyMesh',poly)
run([str(FOAM/'usr/bin/checkMesh'),'-case',str(stage),'-allTopology','-allGeometry'],stage,HERE/'checkMesh.log')
mesh_quality=HERE/'mesh_quality';mesh_quality.mkdir(exist_ok=True)
for name in ('lowWeightFaces','twoInternalFacesCells','underdeterminedCells','nonOrthoFaces'):
    p=stage/'constant/polyMesh/sets'/name
    if p.exists():shutil.copy2(p,mesh_quality/name)
# Case decks match the fresh co0.1 base except for the imported mesh path.
for speed in (700,900):
    dst=HERE/f'ias{speed}'; dst.mkdir(exist_ok=True)
    src=PKG/'experiments/centerline_halfwing_ias/co010_fresh2_20261031'/f'ias{speed}'
    for name in ('0','constant','system','candidate.json'):
        target=dst/name
        if target.is_symlink():target.unlink()
        elif target.is_dir():shutil.rmtree(target)
        elif target.exists():target.unlink()
        origin=src/name
        if origin.is_dir():shutil.copytree(origin,target,symlinks=True)
        else:shutil.copy2(origin,target)
    case_poly=dst/'constant/polyMesh'
    if case_poly.exists() or case_poly.is_symlink():case_poly.unlink()
    case_poly.symlink_to(os.path.relpath(poly,case_poly.parent))
    candidate=json.loads((dst/'candidate.json').read_text())
    candidate.update({'candidate':f'centerline_halfwing_t30mm_ias{speed}_leading_edge_refined','meshSHA256':sha(MESH_MSH),'meshCells':json.loads((HERE/'mesh_provenance.json').read_text())['meshResult']['fluidCells']})
    (dst/'candidate.json').write_text(json.dumps(candidate,indent=2)+'\n')
    run([str(FOAM/'usr/bin/rhoPimpleFoam'),'-case',str(dst),'-dry-run'],dst,HERE/f'dryrun_ias{speed}.log')
    manifest={'experiment':'leading_edge_refinement_20261031','speedIASkmh':speed,'freshFromT0':True,'targetEndTimeSeconds':0.004,'maxCourant':0.1,'deltaTInitialSeconds':5e-6,'maxDeltaTSeconds':1e-5,'writeIntervalTimeSteps':50,'purgeWrite':3,'solver':'rhoPimpleFoam OpenFOAM 1912.200626-3+b1','solverBinarySHA256':'925288f3e89e39b06f66e401542c5985eea0a538e9f9d781f1ef09c39155c586','meshMSHSHA256':sha(MESH_MSH),'meshOpenFoamPolyMeshSHA256':None,'geometrySHA256':json.loads((HERE/'mesh_provenance.json').read_text())['geometrySHA256'],'meshCells':candidate['meshCells'],'boundaryConditionAndSolverDeckSource':str(src),'inputSHA256':file_hashes(dst),'status':'prepared','scope':'experimental rigid centerline half-wing; no fuselage, EDF, preCICE or moving mesh'}
    (dst/'run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('prepared IAS700/IAS900 with same maxCo=0.1 controls on refined centerline mesh')
