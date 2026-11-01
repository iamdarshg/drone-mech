from pathlib import Path
import argparse, re, vtk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection
parser=argparse.ArgumentParser()
parser.add_argument('--case',type=Path,required=True,help='snappyHexMesh case directory containing constant/polyMesh')
parser.add_argument('--source-stl',type=Path,default=Path(__file__).resolve().parents[1]/'open_root/geometry/halfwing_full_regions.stl')
parser.add_argument('--output',type=Path,default=Path('unsnapped_wall_vs_source.png'))
args=parser.parse_args()
case=args.case.resolve()
# Read ASCII OpenFOAM point list; coordinate record is one line per point.
pts=[]; inlist=False
with (case/'constant/polyMesh/points').open() as f:
 for line in f:
  t=line.strip()
  if not inlist:
   if t=='(': inlist=True
   continue
  if t==')': break
  m=re.match(r'\(([-+0-9.eE ]+)\)',t)
  if m: pts.append(tuple(map(float,m.group(1).split())))
# Parse the halfwing patch face range and only read its polygons.
b=(case/'constant/polyMesh/boundary').read_text()
m=re.search(r'\bhalfwing_fsi\s*\{[^}]*?nFaces\s+(\d+);[^}]*?startFace\s+(\d+);',b,re.S)
if not m: raise SystemExit('halfwing boundary patch missing')
n,start=map(int,m.groups())
faces=[]; idx=0; inlist=False
with (case/'constant/polyMesh/faces').open() as f:
 for line in f:
  t=line.strip()
  if not inlist:
   if t=='(': inlist=True
   continue
  if t==')': break
  if start<=idx<start+n:
   q=re.match(r'(\d+)\(([^()]*)\)',t)
   if not q: raise SystemExit(f'face parse fail {idx}')
   ids=list(map(int,q.group(2).split()))
   if len(ids)!=int(q.group(1)): raise SystemExit(f'face point mismatch {idx}')
   faces.append(ids)
  idx+=1
if len(faces)!=n: raise SystemExit(f'patch face count mismatch {len(faces)} != {n}')
# Compact the wall patch into vtkPolyData.
unique=sorted({v for f in faces for v in f}); index={v:i for i,v in enumerate(unique)}
vpts=vtk.vtkPoints();vpts.SetNumberOfPoints(len(unique))
for j,i in enumerate(unique):vpts.SetPoint(j,*pts[i])
polys=vtk.vtkCellArray()
for f in faces:
 ids=vtk.vtkIdList()
 for i in f:ids.InsertNextId(index[i])
 polys.InsertNextCell(ids)
wall=vtk.vtkPolyData();wall.SetPoints(vpts);wall.SetPolys(polys)
# Read source CAD surface STL, including its full root cap only for true source sections.
stl=args.source_stl.resolve()
r=vtk.vtkSTLReader();r.SetFileName(str(stl));r.MergingOn();r.Update();source=r.GetOutput()
def triangles(poly):
 p=np.array([poly.GetPoint(i) for i in range(poly.GetNumberOfPoints())]); out=[]
 for i in range(poly.GetNumberOfCells()):
  c=poly.GetCell(i);out.append([p[c.GetPointId(j)] for j in range(c.GetNumberOfPoints())])
 return np.asarray(out)
src=triangles(source)
mesh_polys=np.asarray([[pts[i] for i in f] for f in faces],dtype=object)
# planform projected triangles in span x / chord z.
fig,axs=plt.subplots(1,2,figsize=(12,5.5),constrained_layout=True)
ax=axs[0]
sproj=[t[:,[0,2]] for t in src]
ax.add_collection(PolyCollection(sproj,facecolors='#6ca6ca',edgecolors='none',alpha=.35,label='source STL'))
mproj=[np.array(p)[:,[0,2]] for p in mesh_polys]
ax.add_collection(PolyCollection(mproj,facecolors='none',edgecolors='#d55e00',linewidths=.14,alpha=.8,label='snapped wall patch'))
ax.autoscale();ax.set_aspect('equal','box');ax.set_xlabel('Span x (m)');ax.set_ylabel('Chord axis z (m)');ax.set_title('Planform projection: source vs snapped patch');ax.grid(alpha=.2);ax.legend(loc='lower right',fontsize=8)
ax=axs[1]
for x,label in ((.0005,'root-near 0.5 mm'),(.13,'mid 130 mm'),(.2595,'tip-near 259.5 mm')):
 for poly,color in ((source,'#0072b2'),(wall,'#d55e00')):
  plane=vtk.vtkPlane();plane.SetOrigin(x,0,0);plane.SetNormal(1,0,0)
  cutter=vtk.vtkCutter();cutter.SetCutFunction(plane);cutter.SetInputData(poly);cutter.Update();o=cutter.GetOutput()
  lines=[]
  for j in range(o.GetNumberOfCells()):
   c=o.GetCell(j)
   for k in range(c.GetNumberOfPoints()-1):
    a=o.GetPoint(c.GetPointId(k));b=o.GetPoint(c.GetPointId(k+1));lines.append([(a[1],a[2]),(b[1],b[2])])
  if lines:
   # Label once per section/source class for legend clarity.
   colorlabel=('source STL' if color=='#0072b2' else 'snapped wall patch')
   ax.add_collection(LineCollection(lines,colors=color,linewidths=.9,alpha=.9,label=f'{label}: {colorlabel}'))
ax.autoscale();ax.set_aspect('equal','box');ax.set_xlabel('Thickness direction y (m)');ax.set_ylabel('Chord axis z (m)');ax.set_title('Root/mid/tip section overlays\nphysical scale; no exaggeration');ax.grid(alpha=.2)
# concise two-item legend
ax.legend(handles=[plt.Line2D([0],[0],color='#0072b2',lw=2,label='source STL'),plt.Line2D([0],[0],color='#d55e00',lw=2,label='snapped wall patch')],loc='best',fontsize=8)
fig.suptitle('Snapped wall patch compared with STEP surface',fontsize=13)
out=args.output.resolve();out.parent.mkdir(parents=True,exist_ok=True);fig.savefig(out,dpi=180)
print({'patch_faces':len(faces),'patch_points':len(unique),'source_triangles':len(src),'patch_bounds':(min(pts[i][j] for i in unique for j in [0]),max(pts[i][0] for i in unique),min(pts[i][1] for i in unique),max(pts[i][1] for i in unique),min(pts[i][2] for i in unique),max(pts[i][2] for i in unique)),'png':str(out)})
