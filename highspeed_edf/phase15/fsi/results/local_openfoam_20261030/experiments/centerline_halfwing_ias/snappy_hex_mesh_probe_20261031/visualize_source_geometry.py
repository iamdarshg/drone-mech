from pathlib import Path
import argparse, hashlib
import vtk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
parser=argparse.ArgumentParser()
parser.add_argument('--source-stl',type=Path,default=Path(__file__).resolve().parent/'open_root/geometry/halfwing_full_regions.stl')
parser.add_argument('--output',type=Path,default=Path('source_geometry_orthographic.png'))
args=parser.parse_args()
stl=args.source_stl.resolve()
reader=vtk.vtkSTLReader(); reader.SetFileName(str(stl)); reader.MergingOn(); reader.Update(); poly=reader.GetOutput()
pts=np.array([poly.GetPoint(i) for i in range(poly.GetNumberOfPoints())])
faces=[]
for i in range(poly.GetNumberOfCells()):
    cell=poly.GetCell(i); faces.append([cell.GetPointId(j) for j in range(cell.GetNumberOfPoints())])
faces=np.asarray(faces,dtype=int)
# Source geometry axes: x is span (0.260 m), z is chordwise (0.425 m root to 0.305 m tip); y is physical thickness.
fig,axs=plt.subplots(1,2,figsize=(12,5.7),constrained_layout=True)
ax=axs[0]
polys=pts[faces][:,:,[0,2]]
coll=PolyCollection(polys,facecolors='#72a9c9',edgecolors='#17324d',linewidths=.07)
ax.add_collection(coll); ax.autoscale(); ax.set_aspect('equal','box'); ax.set_xlabel('Span x (m)'); ax.set_ylabel('Chord axis z (m)')
ax.set_title('Exact source STL orthographic planform')
ax.grid(True,alpha=.2)
ax.annotate('semispan = 0.260 m',xy=(.13,-.29),ha='center')
ax.annotate('root chord ≈ 0.425 m',xy=(.003,-.05),rotation=90,ha='left',va='center')
ax.annotate('tip chord ≈ 0.305 m',xy=(.255,-.08),rotation=90,ha='right',va='center')
# Orthographic cross-sections from the exact imported STL. x cuts avoid edge degeneracy by 0.5 mm.
ax=axs[1]
colors=['#1f77b4','#ff7f0e','#2ca02c']; labels=['root-near x=0.0005 m','mid x=0.1300 m','tip-near x=0.2595 m']
for x,c,label in zip([0.0005,0.13,0.2595],colors,labels):
    plane=vtk.vtkPlane(); plane.SetOrigin(x,0,0); plane.SetNormal(1,0,0)
    cutter=vtk.vtkCutter(); cutter.SetCutFunction(plane); cutter.SetInputData(poly); cutter.Update(); out=cutter.GetOutput()
    seg=[]
    for j in range(out.GetNumberOfCells()):
        cell=out.GetCell(j)
        if cell.GetNumberOfPoints()>=2:
            q=np.array([out.GetPoint(cell.GetPointId(k)) for k in range(cell.GetNumberOfPoints())])
            for k in range(len(q)-1): seg.append((q[k],q[k+1]))
    if not seg: continue
    # draw all exact planar section segments, y horizontal and z vertical
    for a,b in seg:
        ax.plot([a[1],b[1]],[a[2],b[2]],color=c,lw=.65,label=label if a is seg[0][0] else None)
# dedupe legend labels because segments share no references
handles=[]
for c,l in zip(colors,labels): handles.append(plt.Line2D([0],[0],color=c,lw=2,label=l))
ax.legend(handles=handles,loc='best',fontsize=8)
ax.set_xlabel('Physical thickness direction y (m)'); ax.set_ylabel('Chord axis z (m)')
ax.set_title('Orthographic root/mid/tip sections\nphysical thickness scale (no exaggeration)')
ax.grid(True,alpha=.2); ax.set_aspect('equal','box')
fig.suptitle('STEP-derived half-wing geometry; thickness is actual, not exaggerated',fontsize=13)
out=args.output.resolve();out.parent.mkdir(parents=True,exist_ok=True);fig.savefig(out,dpi=180)
print({'step_sha256':'4d2a6eefd10cc547d45baadd9207218de688696730c3722ae2247bf9c86ef2e2','stl_sha256':hashlib.sha256(stl.read_bytes()).hexdigest(),'points':poly.GetNumberOfPoints(),'triangles':poly.GetNumberOfCells(),'bounds':poly.GetBounds(),'png':str(out),'png_sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
