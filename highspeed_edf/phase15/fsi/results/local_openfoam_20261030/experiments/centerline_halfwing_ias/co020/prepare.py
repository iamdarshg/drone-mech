#!/usr/bin/env python3
"""Create fresh-from-zero maxCo=0.2 diagnostics on centerline mesh."""
import os,re,shutil
from pathlib import Path
here=Path(__file__).resolve().parent
exp=here.parent
root=Path('/workspace/drone-mech-transonic/highspeed_edf/phase15/fsi/results/local_openfoam_20261030')
tmpl=root/'cases/pimple'
for speed in ('700','900'):
 c=here/'cases'/f'ias{speed}'
 if c.exists(): shutil.rmtree(c)
 shutil.copytree(tmpl/f'ias{speed}',c,symlinks=True)
 poly=c/'constant/polyMesh'
 if poly.is_symlink() or poly.exists(): poly.unlink()
 poly.symlink_to(os.path.relpath(exp/'mesh/polyMesh',poly.parent))
 # Apply only clean transonic setting, exactly 3 nonorthogonal corrections, matching prior experiment.
 fv=c/'system/fvSolution'; text=fv.read_text(); m=re.search(r'PIMPLE\s*\{[^}]*\}',text); block=m.group(0)
 block=re.sub(r'\btransonic\s+yes\s*;\s*','',block); block=re.sub(r'\bnNonOrthogonalCorrectors\s+\d+\s*;\s*','',block)
 block=block.replace('PIMPLE {','PIMPLE { transonic yes; nNonOrthogonalCorrectors 3;')
 text=text[:m.start()]+block+text[m.end():].replace('p { solver GAMG;','p { solver PBiCGStab; preconditioner DILU;')
 fv.write_text(text)
 fs=c/'system/fvSchemes'; fs.write_text(fs.read_text().replace('laplacianSchemes { default Gauss linear corrected; }','laplacianSchemes { default Gauss linear limited corrected 0.33; }'))
 ctrl=c/'system/controlDict'; t=ctrl.read_text().replace('deltaT 1e-5;','deltaT 5e-6;').replace('maxCo 0.4;','maxCo 0.2;').replace('maxDeltaT 2e-5;','maxDeltaT 1e-5;').replace('writeInterval 100;','writeInterval 100;'); ctrl.write_text(t)
