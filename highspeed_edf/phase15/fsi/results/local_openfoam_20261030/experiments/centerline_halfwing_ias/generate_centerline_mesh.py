#!/usr/bin/env python3
"""Build an experimental x=0-to-tip half-wing using the Phase-15 source schedule."""
from __future__ import annotations
import hashlib, json, math, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[6]
SRC=REPO/'highspeed_edf/phase15/optimization/phase15_fsi_casegen.py'
sys.path.insert(0,str(SRC.parent))
import phase15_fsi_casegen as source
import gmsh

def full_halfwing(thickness_mm: float):
    x0,x1=0.0,260e-3
    f0,f1=x0/0.260,1.0
    chord0=(425.0+(305.0-425.0)*f0)/1000.0
    chord1=305e-3
    le0=(-270.0+x0*1000.0*math.tan(math.radians(25.0)))/1000.0
    le1=(-270.0+260.0*math.tan(math.radians(25.0)))/1000.0
    t0=min(thickness_mm/1000.0,0.10*chord0)
    t1=min(thickness_mm/1000.0,0.10*chord1)
    w0=source.naca_section(x0,le0,chord0,t0)
    w1=source.naca_section(x1,le1,chord1,t1)
    created=gmsh.model.occ.addThruSections([w0,w1],makeSolid=True,makeRuled=False)
    gmsh.model.occ.synchronize()
    vols=[tag for dim,tag in created if dim==3]
    if len(vols)!=1: raise RuntimeError(f'expected one wing volume, got {created}')
    return vols[0],{'xRootM':x0,'xTipM':x1,'rootChordM':chord0,'tipChordM':chord1,
        'rootLeadingEdgeZM':le0,'tipLeadingEdgeZM':le1,'rootThicknessM':t0,'tipThicknessM':t1}

def sha(path:Path):return hashlib.sha256(path.read_bytes()).hexdigest()

source.wing_volume=full_halfwing
_original_set_mesh_fields=source.set_mesh_fields
def set_mesh_fields_no_netgen(surface_tags,min_size,max_size):
    _original_set_mesh_fields(surface_tags,min_size,max_size)
    gmsh.option.setNumber('Mesh.OptimizeNetgen',0)
source.set_mesh_fields=set_mesh_fields_no_netgen
# The pinned binding uses bundled Gmsh 4.13.1; Netgen optimizer is absent locally.
gmsh.initialize()
gmsh.option.setNumber('General.Terminal',1)
gmsh.option.setNumber('Mesh.OptimizeNetgen',0)
gmsh.model.add('centerline_halfwing_30mm')
wing,dims=source.wing_volume(30.0)
wing_vol=float(gmsh.model.occ.getMass(3,wing))
step=HERE/'geometry/halfwing_x0_to_260mm_t30.step'
gmsh.write(str(step))
mesh=HERE/'mesh/wing_centerline.msh'
summary=source.fluid_mesh(mesh,wing,dims)
gmsh.finalize()
result={'candidate':'experimental centerline half-wing, 30 mm thickness','geometryDeviation':'extends the source generator wing schedule from x=80.33 mm to x=0; preserves its linear chord/sweep and NACA-like section formula. No fuselage or root fillet is included.',
        'rootSymmetryPlaneXM':0.0,'sourceGenerator':str(SRC.relative_to(REPO)),'sourceGeneratorSHA256':sha(SRC),
        'generatorScriptSHA256':sha(Path(__file__)),'gmshPythonBinding':'4.15.2','gmshRuntime':'4.13.1 bundled',
        'netgenOptimization':'disabled; unavailable in pinned runtime','wingVolumeM3':wing_vol,'stationParameters':dims,
        'meshSummary':summary,'stepSHA256':sha(step),'meshSHA256':sha(mesh)}
(HERE/'mesh_provenance.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
