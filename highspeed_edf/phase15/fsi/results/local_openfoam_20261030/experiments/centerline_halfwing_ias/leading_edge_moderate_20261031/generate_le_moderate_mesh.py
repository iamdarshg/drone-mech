#!/usr/bin/env python3
"""Regenerate the experimental centerline half-wing with local LE refinement."""
from __future__ import annotations
import hashlib, importlib.util, json, math, platform
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
REPO=next(p for p in HERE.parents if (p/'highspeed_edf/phase15/optimization/phase15_fsi_casegen.py').is_file())
SOURCE=REPO/'highspeed_edf/phase15/optimization/phase15_fsi_casegen.py'
spec=importlib.util.spec_from_file_location('phase15_fsi_casegen',SOURCE)
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)
import gmsh

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def halfwing(thickness_mm:float):
    x0,x1=0.,0.260
    chord0,chord1=0.425,0.305
    le0=-0.270
    le1=(-270.0+260.0*math.tan(math.radians(25.0)))/1000.0
    t0=min(thickness_mm/1000.,0.10*chord0); t1=min(thickness_mm/1000.,0.10*chord1)
    w0=mod.naca_section(x0,le0,chord0,t0); w1=mod.naca_section(x1,le1,chord1,t1)
    created=gmsh.model.occ.addThruSections([w0,w1],makeSolid=True,makeRuled=False)
    gmsh.model.occ.synchronize(); vols=[tag for dim,tag in created if dim==3]
    if len(vols)!=1:raise RuntimeError(f'expected one wing volume, got {created}')
    return vols[0],{'xRootM':x0,'xTipM':x1,'rootChordM':chord0,'tipChordM':chord1,
                    'rootLeadingEdgeZM':le0,'tipLeadingEdgeZM':le1,'rootThicknessM':t0,'tipThicknessM':t1}

mod.wing_volume=halfwing
base_set=mod.set_mesh_fields
selection={}
def le_refined_fields(surface_tags:list[int],min_size:float,max_size:float)->None:
    base_set(surface_tags,min_size,max_size)
    # Permit a local LE threshold of 10–12 mm, restricted to a 2–6 mm influence band to bound total mesh growth.
    gmsh.option.setNumber('Mesh.MeshSizeMin',0.010)
    tags=list(gmsh.model.mesh.field.list()); base_background=max(tags)
    le0=-0.270; le1=(-270.0+260.0*math.tan(math.radians(25.0)))/1000.0
    candidates=[]
    for dim,tag in gmsh.model.getEntities(1):
        bb=gmsh.model.getBoundingBox(dim,tag)
        if bb[0]<1e-5 and bb[3]>0.25999 and abs(bb[2]-le0)<0.002 and abs(bb[5]-le1)<0.002:
            candidates.append((tag,bb))
    if not candidates:
        raise RuntimeError('could not locate the full-span leading-edge seam after wing/domain fragmentation')
    # The loft exposes one or more seam edges; refine all that share the LE x/z schedule.
    d=gmsh.model.mesh.field.add('Distance')
    gmsh.model.mesh.field.setNumbers(d,'CurvesList',[x[0] for x in candidates])
    gmsh.model.mesh.field.setNumber(d,'Sampling',120)
    th=gmsh.model.mesh.field.add('Threshold')
    gmsh.model.mesh.field.setNumber(th,'InField',d)
    gmsh.model.mesh.field.setNumber(th,'SizeMin',0.010)
    gmsh.model.mesh.field.setNumber(th,'SizeMax',0.012)
    gmsh.model.mesh.field.setNumber(th,'DistMin',0.002)
    gmsh.model.mesh.field.setNumber(th,'DistMax',0.006)
    mn=gmsh.model.mesh.field.add('Min')
    gmsh.model.mesh.field.setNumbers(mn,'FieldsList',[base_background,th])
    gmsh.model.mesh.field.setAsBackgroundMesh(mn)
    selection.update({'baseMeshSizeMinM':min_size,'baseMeshSizeMaxM':max_size,
                      'baseFieldTag':base_background,'leadingEdgeCurves':[{'tag':t,'bboxM':list(bb)} for t,bb in candidates],
                      'localSizeMinM':0.010,'localSizeMaxM':0.012,'distanceMinM':0.002,'distanceMaxM':0.006,
                      'combinedBackgroundFieldTag':mn,'netgenOptimizer':'disabled; unavailable in Gmsh runtime'})

mod.set_mesh_fields=le_refined_fields
GEOM=HERE/'geometry/halfwing_x0_to_260mm_t30.step'; GEOM.parent.mkdir(exist_ok=True)
MESH=HERE/'mesh/wing_centerline_le_moderate.msh'; MESH.parent.mkdir(exist_ok=True)
gmsh.initialize()
try:
    gmsh.option.setNumber('General.Terminal',1); gmsh.option.setNumber('General.NumThreads',1)
    gmsh.option.setNumber('Mesh.OptimizeNetgen',0)
    gmsh.model.add('centerline_halfwing_le_moderate')
    wing,dims=halfwing(30.)
    wing_vol=float(gmsh.model.occ.getMass(3,wing))
    gmsh.write(str(GEOM))
    mesh_result=mod.fluid_mesh(MESH,wing,dims)
    gmsh_runtime=gmsh.option.getString('General.Version')
finally:gmsh.finalize()
result={'candidate':'experimental centerline half-wing with leading-edge distance refinement',
        'geometryDeviation':'same experimental x=0..260 mm half-wing and outer box as parent centerline mesh; no fuselage or root fillet',
        'meshResult':mesh_result,'wingVolumeM3':wing_vol,'stationParameters':dims,
        'refinement':selection,'gmshPythonBinding':gmsh.__version__,'gmshRuntime':gmsh_runtime,
        'phase15Generator':str(SOURCE.relative_to(REPO)),'phase15GeneratorSHA256':sha(SOURCE),
        'scriptSHA256':sha(Path(__file__).resolve()),'geometrySHA256':sha(GEOM),'meshSHA256':sha(MESH),
        'sourceCenterlineMeshSHA256':sha(HERE.parent/'mesh/wing_centerline.msh')}
(HERE/'mesh_provenance.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
