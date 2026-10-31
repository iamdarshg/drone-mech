from pathlib import Path
import math
import importlib.util, sys
sys.path.insert(0, '/tmp/phase15-gmsh')
import gmsh
src=Path('/workspace/drone-mech/highspeed_edf/phase15/optimization/phase15_fsi_casegen.py')
spec=importlib.util.spec_from_file_location('phase15gen', src)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
# Match the current experimental centerline half-wing that was actually run.
def centerline_wing(thickness_mm):
    x0,x1=0.0,260e-3
    chord0,chord1=425e-3,305e-3
    le0=-270e-3
    le1=(-270.0+260.0*math.tan(math.radians(25.0)))/1000.0
    t0=min(thickness_mm/1000.0,0.10*chord0)
    t1=min(thickness_mm/1000.0,0.10*chord1)
    w0=mod.naca_section(x0,le0,chord0,t0)
    w1=mod.naca_section(x1,le1,chord1,t1)
    created=gmsh.model.occ.addThruSections([w0,w1],makeSolid=True,makeRuled=False)
    gmsh.model.occ.synchronize()
    vols=[tag for dim,tag in created if dim==3]
    if len(vols)!=1: raise RuntimeError(f'expected one wing volume, got {created}')
    return vols[0], {'xRootM':x0,'xTipM':x1,'rootChordM':chord0,'tipChordM':chord1,'rootLeadingEdgeZM':le0,'tipLeadingEdgeZM':le1,'rootThicknessM':t0,'tipThicknessM':t1}
mod.wing_volume=centerline_wing
orig=mod.set_mesh_fields

def local_le(surface_tags, min_size, max_size):
    # Keep the baseline wall-distance sizing, add an isolated 3.5 mm nose refinement
    # covering the leading-edge sweep and first ~40 mm of chord.
    orig(surface_tags, min_size, max_size)
    # Lower the global clamp to honor the local edge sizing values below.
    gmsh.option.setNumber("Mesh.MeshSizeMin", 0.0005)
    gmsh.option.setNumber("Mesh.Algorithm3D",10)
    gmsh.option.setNumber("Mesh.OptimizeNetgen",0)
    b=gmsh.model.mesh.field.add('Box')
    gmsh.model.mesh.field.setNumber(b,'VIn',0.0035)
    gmsh.model.mesh.field.setNumber(b,'VOut',max_size)
    gmsh.model.mesh.field.setNumber(b,'XMin',0.060)
    gmsh.model.mesh.field.setNumber(b,'XMax',0.085)
    gmsh.model.mesh.field.setNumber(b,'YMin',-0.025)
    gmsh.model.mesh.field.setNumber(b,'YMax',0.025)
    gmsh.model.mesh.field.setNumber(b,'ZMin',-0.260)
    gmsh.model.mesh.field.setNumber(b,'ZMax',-0.220)
    root_te=gmsh.model.mesh.field.add('Box')
    gmsh.model.mesh.field.setNumber(root_te,'VIn',0.0005)
    gmsh.model.mesh.field.setNumber(root_te,'VOut',max_size)
    gmsh.model.mesh.field.setNumber(root_te,'XMin',0.017)
    gmsh.model.mesh.field.setNumber(root_te,'XMax',0.026)
    gmsh.model.mesh.field.setNumber(root_te,'YMin',-0.010)
    gmsh.model.mesh.field.setNumber(root_te,'YMax',0.004)
    gmsh.model.mesh.field.setNumber(root_te,'ZMin',0.151)
    gmsh.model.mesh.field.setNumber(root_te,'ZMax',0.159)
    f=gmsh.model.mesh.field.add('Min')
    gmsh.model.mesh.field.setNumbers(f,'FieldsList',[2,b,root_te])
    gmsh.model.mesh.field.setAsBackgroundMesh(f)
mod.set_mesh_fields=local_le
out=Path('/tmp/phase15-root-te-micro-hxt-probe'); out.mkdir(exist_ok=True)
fluid=out/'wing_le_root_te_micro_hxt.msh'
gmsh.initialize()
try:
    gmsh.option.setNumber('General.Terminal',1)
    gmsh.option.setNumber('General.NumThreads',1)
    gmsh.model.add('centerline_halfwing_30mm_root_te_micro_hxt')
    wing,dims=mod.wing_volume(30.0)
    data=mod.fluid_mesh(fluid,wing,dims)
    print('RESULT',data)
finally: gmsh.finalize()
