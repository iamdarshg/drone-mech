#!/usr/bin/env python3
"""Build an energy-consistent wall-compatible initial state on imported OpenFOAM tets."""
from pathlib import Path
import sys
import re, math, numpy as np
from scipy.spatial import cKDTree
case=Path(sys.argv[1]); mesh=case/'constant/polyMesh'; fields=case/'0'
# Read OpenFOAM list bodies.
def body(name):
 s=(mesh/name).read_text(); start=s.index('\n(',s.index('object'))+2; end=s.rfind(')'); return s[start:end].strip()
nums=re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
pts=np.array([[float(x) for x in nums.findall(line)] for line in body('points').splitlines() if line.strip()],dtype=float)
owner=np.fromstring(body('owner'),sep=' ',dtype=np.int64); nei=np.fromstring(body('neighbour'),sep=' ',dtype=np.int64)
faces=[]
for line in body('faces').splitlines():
 line=line.strip()
 if line:
  a=line.find('('); b=line.rfind(')'); faces.append(np.fromstring(line[a+1:b],sep=' ',dtype=np.int64))
print(f'points={len(pts)} faces={len(faces)} cells={int(max(owner.max(),nei.max())+1)} internalFaces={len(nei)}',flush=True)
fc=np.array([pts[ids].mean(axis=0) for ids in faces])
ncells=int(max(owner.max(),nei.max())+1); csum=np.zeros((ncells,3)); nface=np.zeros(ncells)
np.add.at(csum,owner,fc);np.add.at(nface,owner,1)
np.add.at(csum[:len(nei)],nei,fc[:len(nei)]);np.add.at(nface[:len(nei)],nei,1)
centers=csum/nface[:,None]
# Wall patch addresses from the exact polyBoundaryMesh range.
b=(mesh/'boundary').read_text(); m=re.search(r'\n    halfwing\s*\{.*?nFaces\s+(\d+);\s*startFace\s+(\d+);',b,re.S)
if not m: raise SystemExit('halfwing patch not found')
nwall,start=map(int,m.groups()); wallids=np.arange(start,start+nwall); tri=np.array([faces[i] for i in wallids],dtype=np.int64)
triPts=pts[tri]; wcent=triPts.mean(axis=1); wnormal=np.cross(triPts[:,1]-triPts[:,0],triPts[:,2]-triPts[:,0]); wnormal/=np.linalg.norm(wnormal,axis=1)[:,None]
print(f'wall faces={nwall} start={start}; query nearest wall triangles...',flush=True)
_,near=cKDTree(wcent).query(centers,k=1,workers=-1)
vec=centers-wcent[near]; dist=np.abs(np.einsum('ij,ij->i',vec,wnormal[near]))
# +0.5 deg Mach 1.05 at the declared 3 km static-temperature state.
Tinf=268.65; pinf=70100.; R=287.05; gamma=1.4; cp=1004.685; ainf=math.sqrt(gamma*R*Tinf); V=283.1719595766233; alpha=math.radians(.5); Uinf=np.array([V*math.sin(alpha),0,V*math.cos(alpha)])
T0=Tinf+V*V/(2*cp); p0=pinf*(T0/Tinf)**(gamma/(gamma-1))
# Smooth coarse turbulent layer: slip direction follows the local surface; amplitude rises over delta.
delta=0.003; local=dist<4*delta; U=np.tile(Uinf,(ncells,1)); n=wnormal[near[local]]; d=dist[local]
Ut=Uinf[None,:]-(n@Uinf)[:,None]*n
orientBlend=np.exp(-d/(4*delta)); ramp=1-np.exp(-d/delta)
U[local]=ramp[:,None]*(Uinf[None,:]+orientBlend[:,None]*(Ut-Uinf[None,:]))
speed=np.linalg.norm(U,axis=1)
T=T0-speed**2/(2*cp)
if T.min()<=0: raise SystemExit(f'non-positive static T {T.min()}')
p=p0*(T/T0)**(gamma/(gamma-1)); rho=p/(R*T); h=cp*T
# Turbulence intensity 1% freestream; decay k to wall and use a conventional omega wall scale.
kInf=1.5*(0.01*V)**2; mu=1.458e-6*T**1.5/(T+110.4); nu=mu/rho; beta1=.075
k=np.full(ncells,kInf); omega=np.full(ncells,180.0)
k[local]=kInf*ramp**2
omega[local]=np.maximum(180.0,6*nu[local]/(beta1*np.maximum(dist[local],1e-4)**2))
omega=np.minimum(omega,1e5)
nut=.09*k/omega; alphat=nut/.9

def write_scalar(path,obj,dims,vals,bcs):
 with path.open('w') as f:
  f.write(f'''FoamFile\n{{ version 2.0; format ascii; class volScalarField; location "0"; object {obj}; }}\ndimensions {dims};\ninternalField nonuniform List<scalar>\n{len(vals)}\n(\n''')
  for x in vals:f.write(f'{x:.10g}\n')
  f.write(')\n;\nboundaryField\n{\n')
  for name,body in bcs.items():f.write(f' {name} {{ {body} }}\n')
  f.write('}\n')
def write_vector(path,obj,dims,vals,bcs):
 with path.open('w') as f:
  f.write(f'''FoamFile\n{{ version 2.0; format ascii; class volVectorField; location "0"; object {obj}; }}\ndimensions {dims};\ninternalField nonuniform List<vector>\n{len(vals)}\n(\n''')
  for x,y,z in vals:f.write(f'({x:.10g} {y:.10g} {z:.10g})\n')
  f.write(')\n;\nboundaryField\n{\n')
  for name,body in bcs.items():f.write(f' {name} {{ {body} }}\n')
  f.write('}\n')
uf=tuple(Uinf.tolist()); ufmt=f'({uf[0]:.12g} 0 {uf[2]:.12g})'; h0=cp*T0; rhoInf=pinf/(R*Tinf)
write_vector(fields/'U','U','[0 1 -1 0 0 0 0]',U,{'inlet':f'type fixedValue; value uniform {ufmt};','outlet':f'type pressureInletOutletVelocity; value uniform {ufmt};','farfield':f'type freestream; freestreamValue uniform {ufmt}; value uniform {ufmt};','halfwing':'type noSlip;','symmetryPlane':'type symmetryPlane;'})
write_scalar(fields/'T','T','[0 0 0 1 0 0 0]',T,{'inlet':f'type fixedValue; value uniform {Tinf};','outlet':'type zeroGradient;','farfield':f'type fixedValue; value uniform {Tinf};','halfwing':'type zeroGradient;','symmetryPlane':'type symmetryPlane;'})
write_scalar(fields/'h','h','[0 2 -2 0 0 0 0]',h,{'inlet':f'type fixedValue; value uniform {cp*Tinf};','outlet':'type zeroGradient;','farfield':f'type fixedValue; value uniform {cp*Tinf};','halfwing':'type zeroGradient;','symmetryPlane':'type symmetryPlane;'})
write_scalar(fields/'p','p','[1 -1 -2 0 0 0 0]',p,{'inlet':'type zeroGradient;','outlet':f'type fixedValue; value uniform {pinf};','farfield':f'type freestreamPressure; freestreamValue uniform {pinf}; value uniform {pinf};','halfwing':'type zeroGradient;','symmetryPlane':'type symmetryPlane;'})
write_scalar(fields/'rho','rho','[1 -3 0 0 0 0 0]',rho,{'inlet':f'type calculated; value uniform {rhoInf};','outlet':f'type calculated; value uniform {rhoInf};','farfield':f'type calculated; value uniform {rhoInf};','halfwing':'type zeroGradient;','symmetryPlane':'type symmetryPlane;'})
write_scalar(fields/'k','k','[0 2 -2 0 0 0 0]',k,{'inlet':f'type fixedValue; value uniform {kInf};','outlet':f'type inletOutlet; inletValue uniform {kInf}; value uniform {kInf};','farfield':f'type fixedValue; value uniform {kInf};','halfwing':f'type kqRWallFunction; value uniform 0;','symmetryPlane':'type symmetryPlane;'})
write_scalar(fields/'omega','omega','[0 0 -1 0 0 0 0]',omega,{'inlet':'type fixedValue; value uniform 180;','outlet':'type inletOutlet; inletValue uniform 180; value uniform 180;','farfield':'type fixedValue; value uniform 180;','halfwing':'type omegaWallFunction; value uniform 180;','symmetryPlane':'type symmetryPlane;'})
write_scalar(fields/'nut','nut','[0 2 -1 0 0 0 0]',nut,{'inlet':'type calculated; value uniform 0;','outlet':'type calculated; value uniform 0;','farfield':'type calculated; value uniform 0;','halfwing':'type nutkWallFunction; value uniform 0;','symmetryPlane':'type symmetryPlane;'})
write_scalar(fields/'alphat','alphat','[1 -1 -1 0 0 0 0]',alphat,{'inlet':'type calculated; value uniform 0;','outlet':'type calculated; value uniform 0;','farfield':'type calculated; value uniform 0;','halfwing':'type compressible::alphatWallFunction; value uniform 0;','symmetryPlane':'type symmetryPlane;'})
# Validate initialization invariants from written arrays.
tt=T+speed**2/(2*cp); idealResidual=np.max(np.abs(p-rho*R*T)); enthalpyResidual=np.max(np.abs(h-cp*T))
print(f'Vinf={V:.6f} m/s Mach={V/ainf:.6f} alpha=+0.5 deg; T0={T0:.6f} K p0={p0:.3f} Pa rhoInf={rhoInf:.6f}',flush=True)
print(f'BL delta={delta} m, affected cell centers={int(local.sum())}/{ncells}, dwall[0.5,50,99]mm={np.quantile(dist,[.5,.95,.99])*1e3}',flush=True)
print(f'initialized T={T.min():.4f}..{T.max():.4f} K; speed={speed.min():.4f}..{speed.max():.4f} m/s; Tt={tt.min():.6f}..{tt.max():.6f} K; maxTt deviation={max(abs(tt-T0)):.3e} K',flush=True)
print(f'max |p-rhoRT|={idealResidual:.3e} Pa; max |h-CpT|={enthalpyResidual:.3e} J/kg; kInf={kInf:.6f} omega range={omega.min():.3f}..{omega.max():.3f} 1/s',flush=True)
