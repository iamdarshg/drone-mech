#!/usr/bin/env python3
"""Round-trip the experimental STEP with Gmsh and record bounds/volume."""
import hashlib,json
from pathlib import Path
import gmsh
HERE=Path(__file__).resolve().parent
step=HERE/'geometry/halfwing_x0_to_260mm_t30.step'
gmsh.initialize(); gmsh.open(str(step)); gmsh.model.occ.synchronize()
vols=[t for d,t in gmsh.model.getEntities(3)]
if len(vols)!=1: raise RuntimeError(f'expected one volume; got {len(vols)}')
volume=float(gmsh.model.occ.getMass(3,vols[0]))
bbs=[gmsh.model.occ.getBoundingBox(d,t) for d,t in gmsh.model.getEntities(3)]
bb=[min(x[0] for x in bbs),min(x[1] for x in bbs),min(x[2] for x in bbs),max(x[3] for x in bbs),max(x[4] for x in bbs),max(x[5] for x in bbs)]
gmsh.finalize()
result={'step':'geometry/halfwing_x0_to_260mm_t30.step','sha256':hashlib.sha256(step.read_bytes()).hexdigest(),'gmshRuntime':'4.13.1','solidCount':1,'volumeM3':volume,'boundsM':bb}
(HERE/'geometry/step_roundtrip.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
