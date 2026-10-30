#!/usr/bin/env python3
"""Import the experimental centerline mesh and prepare clean transonic cases."""
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[6]
PKG=REPO/'highspeed_edf/phase15/fsi/results/local_openfoam_20261030'
TEMPLATE=PKG/'cases/pimple'
FOAM=Path(os.environ.get('OPENFOAM_ROOT','/workspace/openfoam-deb')).resolve()
ENV=os.environ.copy(); ENV.update({'WM_PROJECT_DIR':str(FOAM/'usr/share/openfoam'),'FOAM_LIBBIN':str(FOAM/'usr/lib'),'FOAM_APPBIN':str(FOAM/'usr/bin')})
ENV['LD_LIBRARY_PATH']=str(FOAM/'usr/lib')+(':'+ENV['LD_LIBRARY_PATH'] if ENV.get('LD_LIBRARY_PATH') else '')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def run(argv,cwd,log):
    with log.open('w') as f: subprocess.run(argv,cwd=cwd,env=ENV,stdout=f,stderr=subprocess.STDOUT,check=True)

# Native Gmsh-to-OpenFOAM import into an isolated staging case.
stage=HERE/'mesh/import_case'; stage.mkdir(parents=True,exist_ok=True)
(stage/'system').mkdir(exist_ok=True)
shutil.copy2(TEMPLATE/'ias700/system/controlDict',stage/'system/controlDict')
shutil.copy2(TEMPLATE/'ias700/system/fvSchemes',stage/'system/fvSchemes')
shutil.copy2(TEMPLATE/'ias700/system/fvSolution',stage/'system/fvSolution')
shutil.copy2(HERE/'mesh/wing_centerline.msh',stage/'wing.msh')
run([str(FOAM/'usr/bin/gmshToFoam'),'wing.msh'],stage,HERE/'logs/gmshToFoam.log')
boundary=stage/'constant/polyMesh/boundary'; b=boundary.read_text()
b=re.sub(r'(\bfsi\s*\{\s*type\s+)patch;',r'\1wall;',b)
b=re.sub(r'(\brootWall\s*\{\s*type\s+)patch;',r'\1symmetryPlane;',b)
if not re.search(r'\btype\s+wall;',re.search(r'\bfsi\s*\{[^}]*\}',b,re.S).group(0)): raise RuntimeError('fsi patch was not set to wall')
if not re.search(r'\btype\s+symmetryPlane;',re.search(r'\brootWall\s*\{[^}]*\}',b,re.S).group(0)): raise RuntimeError('rootWall patch was not set to symmetryPlane')
boundary.write_text(b)
shutil.copytree(stage/'constant/polyMesh',HERE/'mesh/polyMesh',dirs_exist_ok=True)
run([str(FOAM/'usr/bin/checkMesh'),'-case',str(stage)],stage,HERE/'logs/checkMesh_mesh.log')

for speed in ('700','900'):
    case=HERE/f'cases/ias{speed}'
    if case.exists(): shutil.rmtree(case)
    shutil.copytree(TEMPLATE/f'ias{speed}',case,symlinks=True)
    poly=case/'constant/polyMesh'
    if poly.is_symlink() or poly.exists(): poly.unlink()
    poly.symlink_to(os.path.relpath(HERE/'mesh/polyMesh',start=poly.parent))
    shutil.copy2(HERE/'mesh/wing_centerline.msh',case/'wing.msh')
    # Keep the source speed conversion and all input fields; select a clean transonic scheme.
    fv=case/'system/fvSolution'; text=fv.read_text(); m=re.search(r'PIMPLE\s*\{[^}]*\}',text)
    if not m: raise RuntimeError(f'PIMPLE block missing in IAS{speed}')
    block=m.group(0)
    block=re.sub(r'\btransonic\s+yes\s*;\s*','',block)
    block=re.sub(r'\bnNonOrthogonalCorrectors\s+\d+\s*;\s*','',block)
    block=block.replace('PIMPLE {','PIMPLE { transonic yes; nNonOrthogonalCorrectors 3;')
    text=text[:m.start()]+block+text[m.end():]
    text=text.replace('p { solver GAMG;', 'p { solver PBiCGStab; preconditioner DILU;')
    fv.write_text(text)
    schemes=case/'system/fvSchemes'; text=schemes.read_text().replace('laplacianSchemes { default Gauss linear corrected; }','laplacianSchemes { default Gauss linear limited corrected 0.33; }'); schemes.write_text(text)
    control=case/'system/controlDict'; text=control.read_text(); text=re.sub(r'writeInterval\s+[^;]+;', 'writeInterval 100;', text); control.write_text(text)
    candidate=json.loads((case/'candidate.json').read_text())
    candidate.update({'candidate':f'centerline_halfwing_t30mm_ias{speed}','sourceGeometry':'Experimental source-schedule extension from x=80.33 mm to x=0 m; no fuselage/root fillet','meshSHA256':sha(HERE/'mesh/wing_centerline.msh'),'meshCells':49208,'rootSymmetryPlaneXM':0.0,'solver':'rhoPimpleFoam OpenFOAM 1912.200626-3+b1'})
    (case/'candidate.json').write_text(json.dumps(candidate,indent=2)+'\n')
    run([str(FOAM/'usr/bin/checkMesh'),'-case',str(case)],case,HERE/f'logs/checkMesh_ias{speed}.log')
    run([str(FOAM/'usr/bin/rhoPimpleFoam'),'-case',str(case),'-dry-run'],case,HERE/f'logs/dryrun_ias{speed}.log')
print('prepared IAS700/IAS900 cases at',HERE)
