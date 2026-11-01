import vtk, numpy as np, matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
base='/workspace/snappy-rootcap-closed/constant/triSurface/halfwing.stl'
vtu='/workspace/snappy-rootcap-closed/postProcessing/constant/underdeterminedCells/underdeterminedCells.vtp'
r=vtk.vtkSTLReader();r.SetFileName(base);r.Update(); wing=r.GetOutput()
r=vtk.vtkXMLPolyDataReader();r.SetFileName(vtu);r.Update();bad=r.GetOutput();bb=bad.GetBounds();print('bad bounds',bb)
# Root neighborhood with 15 mm spanwise window and 20 mm thickness window around bad cell.
local=[]
for i in range(wing.GetNumberOfCells()):
 c=wing.GetCell(i); t=np.array([c.GetPoints().GetPoint(j) for j in range(3)])
 if t[:,0].min()<=bb[1]+.012 and t[:,0].max()>=bb[0]-.001 and t[:,1].min()<=bb[3]+.008 and t[:,1].max()>=bb[2]-.008 and t[:,2].min()<=bb[5]+.012 and t[:,2].max()>=bb[4]-.012: local.append(t)
faces=[]
for i in range(bad.GetNumberOfCells()):
 c=bad.GetCell(i);faces.append(np.array([c.GetPoints().GetPoint(j) for j in range(c.GetNumberOfPoints())]))
print('local triangles',len(local),'cell faces',len(faces))
fig=plt.figure(figsize=(8,7));a=fig.add_subplot(111,projection='3d')
a.add_collection3d(Poly3DCollection(local,facecolor='#4c9ac6',edgecolor='#315d77',linewidth=.25,alpha=.48))
a.add_collection3d(Poly3DCollection(faces,facecolor='#d73027',edgecolor='#700000',linewidth=1.4,alpha=.88))
x0,x1=bb[0]-.001,bb[1]+.012;y0,y1=bb[2]-.008,bb[3]+.008;z0,z1=bb[4]-.012,bb[5]+.012
a.plot([0,0,0,0,0],[-.015,.015,.015,-.015,-.015],[-.27,-.27,.156,.156,-.27],color='black',lw=1,alpha=.7)
a.set(xlim=(x0,x1),ylim=(y0,y1),zlim=(z0,z1),xlabel='span x (m)',ylabel='thickness y (m)',zlabel='chord z (m)',title='Closed STEP root-cap: strict-checkMesh underdetermined cell vs source STEP surfaces')
a.set_box_aspect((x1-x0,y1-y0,z1-z0));a.view_init(elev=24,azim=-58)
a.text(x0+.0001,y0+.001,z1-.001,'root symmetry cut x=0',color='black')
a.text((x0+x1)/2,(y0+y1)/2,z0+.002,'red = underdetermined cell',color='darkred')
fig.tight_layout();out='/workspace/drone-mech/highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/snappy_hex_mesh_probe_20261031/closed_step_root_cap_20261101/underdetermined_cell_vs_STEP.png';fig.savefig(out,dpi=200);print(out)
