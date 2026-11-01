import gmsh, math, os, sys
step='/workspace/drone-mech/highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/geometry/halfwing_x0_to_260mm_t30.step'
out='/tmp/gmsh_halfwing_fluid/halfwing_fluid_tiprefine2.msh'
# Half-domain bounds from pinned snappy case.
x0,x1=0.0,0.79125
y0,y1=-0.35,0.35
z0,z1=-0.695,1.43124

gmsh.initialize()
gmsh.option.setNumber('General.Terminal',1)
gmsh.option.setNumber('Geometry.OCCBooleanPreserveNumbering',0)
gmsh.model.add('halfwing_fluid_boolean')
wing=gmsh.model.occ.importShapes(step)
gmsh.model.occ.synchronize()
wv=[tag for dim,tag in wing if dim==3]
if len(wv)!=1: raise RuntimeError(f'Expected one wing solid, got {wv}')
print('wing bbox',gmsh.model.getBoundingBox(3,wv[0]))
box=gmsh.model.occ.addBox(x0,y0,z0,x1-x0,y1-y0,z1-z0)
# Subtract exact STEP wing from the half-domain fluid box. The wing root cap is
# coplanar with x=0; OCC boolean creates a symmetry face with a cutout.
res,_=gmsh.model.occ.cut([(3,box)],[(3,wv[0])],removeObject=True,removeTool=True)
gmsh.model.occ.synchronize()
vols=[tag for dim,tag in res if dim==3]
print('fluid vols',vols,'all volumes',gmsh.model.getEntities(3))
if len(vols)!=1: raise RuntimeError(f'Expected one connected fluid volume, got {vols}')
vol=vols[0]
bnd=gmsh.model.getBoundary([(3,vol)],oriented=False,recursive=False)
faces=[tag for dim,tag in bnd if dim==2]
print('boundary faces',len(faces))
# classify surfaces by bbox at outer planes. Remaining surfaces are exact STEP wing wall.
physical={}
physid=1
wingfaces=[]
for s in faces:
    b=gmsh.model.getBoundingBox(2,s)
    xmin,ymin,zmin,xmax,ymax,zmax=b
    if abs(xmin-x0)<1e-6 and abs(xmax-x0)<1e-6:
        name='symmetryPlane'
    elif abs(zmin-z0)<1e-6 and abs(zmax-z0)<1e-6:
        name='inlet'
    elif abs(zmin-z1)<1e-6 and abs(zmax-z1)<1e-6:
        name='outlet'
    elif abs(xmin-x1)<1e-6 and abs(xmax-x1)<1e-6:
        name='farfield'
    elif abs(ymin-y0)<1e-6 and abs(ymax-y0)<1e-6:
        name='farfield'
    elif abs(ymin-y1)<1e-6 and abs(ymax-y1)<1e-6:
        name='farfield'
    else:
        name='halfwing'
        wingfaces.append(s)
    physical.setdefault(name,[]).append(s)
for name,tags in physical.items():
    pid=gmsh.model.addPhysicalGroup(2,tags,physid)
    gmsh.model.setPhysicalName(2,pid,name)
    print('physical',name,'faces',len(tags),'id',pid,'bboxes', [gmsh.model.getBoundingBox(2,t) for t in tags[:2]])
    physid+=1
pid=gmsh.model.addPhysicalGroup(3,[vol],physid)
gmsh.model.setPhysicalName(3,pid,'fluid')
# Mesh controls: modest farfield resolution and a distance-based wing refinement.
gmsh.option.setNumber('Mesh.MshFileVersion',2.2)
gmsh.option.setNumber('Mesh.ElementOrder',1)
gmsh.option.setNumber('Mesh.Algorithm',6)
gmsh.option.setNumber('Mesh.Algorithm3D',10)
gmsh.option.setNumber('Mesh.Optimize',1)
gmsh.option.setNumber('Mesh.OptimizeNetgen',1)
gmsh.option.setNumber('Mesh.MeshSizeMin',0.0025)
gmsh.option.setNumber('Mesh.MeshSizeMax',0.04)
gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',1)
gmsh.option.setNumber('Mesh.MeshSizeExtendFromBoundary',1)
f=gmsh.model.mesh.field.add('Distance')
gmsh.model.mesh.field.setNumbers(f,'SurfacesList',wingfaces)
gmsh.model.mesh.field.setNumber(f,'Sampling',80)
th=gmsh.model.mesh.field.add('Threshold')
gmsh.model.mesh.field.setNumber(th,'InField',f)
gmsh.model.mesh.field.setNumber(th,'SizeMin',0.0025)
gmsh.model.mesh.field.setNumber(th,'SizeMax',0.04)
gmsh.model.mesh.field.setNumber(th,'DistMin',0.004)
gmsh.model.mesh.field.setNumber(th,'DistMax',0.12)
boxf=gmsh.model.mesh.field.add('Box')
gmsh.model.mesh.field.setNumber(boxf,'VIn',0.0008)
gmsh.model.mesh.field.setNumber(boxf,'VOut',0.04)
gmsh.model.mesh.field.setNumber(boxf,'XMin',0.195)
gmsh.model.mesh.field.setNumber(boxf,'XMax',0.260)
gmsh.model.mesh.field.setNumber(boxf,'YMin',-0.008)
gmsh.model.mesh.field.setNumber(boxf,'YMax',0.001)
gmsh.model.mesh.field.setNumber(boxf,'ZMin',0.150)
gmsh.model.mesh.field.setNumber(boxf,'ZMax',0.160)
gmsh.model.mesh.field.setNumber(boxf,'Thickness',0.003)
mn=gmsh.model.mesh.field.add('Min')
gmsh.model.mesh.field.setNumbers(mn,'FieldsList',[th,boxf])
gmsh.model.mesh.field.setAsBackgroundMesh(mn)
gmsh.model.mesh.generate(3)
# Optimize 3D netgen once; keep mesh first-order.
gmsh.model.mesh.optimize('Netgen')
gmsh.write(out)
print('wrote',out,'nodes',len(gmsh.model.mesh.getNodes()[0]),'elements',sum(len(x) for x in gmsh.model.mesh.getElements(3)[1]))
gmsh.finalize()
