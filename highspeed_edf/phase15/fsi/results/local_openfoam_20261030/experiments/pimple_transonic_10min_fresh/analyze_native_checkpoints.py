#!/usr/bin/env python3
"""Offline mass-flux, pressure-load, and thermodynamic history from OpenFOAM fields."""
from __future__ import annotations
import argparse, json, math, re
from pathlib import Path

def block(text: str, key: str) -> str:
    m=re.search(rf'(?m)^\s*{re.escape(key)}\s*\{{',text)
    if not m: raise ValueError(f'block {key!r} not found')
    i=text.index('{',m.start()); depth=0
    for j in range(i,len(text)):
        if text[j]=='{':depth+=1
        elif text[j]=='}':
            depth-=1
            if depth==0:return text[i+1:j]
    raise ValueError(f'unterminated {key!r}')

def list_body(text: str) -> str:
    m=re.search(r'\n\s*\d+\s*\n\s*\((.*)\)\s*\n',text,re.S)
    if not m: raise ValueError('list body not found')
    return m.group(1)

def scalar_internal(path: Path) -> list[float]:
    s=path.read_text(); m=re.search(r'internalField\s+nonuniform\s+List<scalar>\s+\d+\s*\((.*?)\)\s*;',s,re.S)
    if not m: raise ValueError(f'internal scalar list missing in {path}')
    return list(map(float,re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',m.group(1))))

def vector_data(text: str) -> list[tuple[float,float,float]]:
    return [tuple(map(float,x)) for x in re.findall(r'\(\s*([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s*\)',text)]

def vector_internal(path: Path) -> list[tuple[float,float,float]]:
    s=path.read_text(); m=re.search(r'internalField\s+nonuniform\s+List<vector>\s+\d+\s*\((.*?)\)\s*;',s,re.S)
    if not m: raise ValueError(f'internal vector list missing in {path}')
    return vector_data(m.group(1))

def patch_scalars(path: Path, patch: str) -> list[float]:
    b=block(block(path.read_text(),'boundaryField'),patch)
    m=re.search(r'value\s+uniform\s+([-+\d.eE]+)',b)
    if m:return [float(m.group(1))]
    m=re.search(r'value\s+nonuniform\s+List<scalar>\s+\d+\s*\((.*?)\)',b,re.S)
    if not m:raise ValueError(f'patch scalar values missing: {path} {patch}')
    return list(map(float,re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',m.group(1))))

def read_mesh(mesh: Path):
    pts=vector_data(list_body((mesh/'points').read_text()))
    faces=[list(map(int,x.split())) for x in re.findall(r'\d+\s*\(([^()]*)\)',list_body((mesh/'faces').read_text()))]
    def ints(n):return list(map(int,re.findall(r'\d+',list_body((mesh/n).read_text()))))
    owner=ints('owner'); neighbour=ints('neighbour')
    ncell=max(max(owner),max(neighbour))+1; verts=[set() for _ in range(ncell)]
    for fi,face in enumerate(faces):
        verts[owner[fi]].update(face)
        if fi<len(neighbour): verts[neighbour[fi]].update(face)
    centers=[tuple(sum(pts[v][j] for v in vs)/len(vs) for j in range(3)) for vs in verts]
    patches={}
    bt=(mesh/'boundary').read_text()
    for name in ('inlet','outlet','farfield','fsi','rootWall'):
        b=block(bt,name); patches[name]=(int(re.search(r'\bstartFace\s+(\d+)',b).group(1)),int(re.search(r'\bnFaces\s+(\d+)',b).group(1)))
    sf=[]
    for f in faces:
        a=[0.,0.,0.]
        for i in range(len(f)):
            p,q=pts[f[i]],pts[f[(i+1)%len(f)]]
            a[0]+=p[1]*q[2]-p[2]*q[1]; a[1]+=p[2]*q[0]-p[0]*q[2]; a[2]+=p[0]*q[1]-p[1]*q[0]
        sf.append(tuple(x*.5 for x in a))
    return owner,patches,sf,centers

def extrema(vals,centers):
    lo=min(range(len(vals)),key=vals.__getitem__); hi=max(range(len(vals)),key=vals.__getitem__)
    return {'min':{'value':vals[lo],'cell':lo,'centerM':centers[lo]},'max':{'value':vals[hi],'cell':hi,'centerM':centers[hi]}}

def analyze(case: Path, speed: str):
    owner,patches,sf,centers=read_mesh(case/'constant/polyMesh'); out=[]
    dirs=[p for p in case.iterdir() if p.is_dir() and p.name[0].isdigit() and p.name!='0']
    for tdir in sorted(dirs,key=lambda p:float(p.name)):
        pfile=tdir/'p'; rfile=tdir/'rho'; phifile=tdir/'phi'
        if not all(x.exists() for x in (pfile,rfile,phifile)): continue
        pvals=scalar_internal(pfile); u=vector_internal(tdir/'U'); umag=[math.sqrt(sum(v*v for v in row)) for row in u]
        T=scalar_internal(tdir/'T'); rho=scalar_internal(rfile)
        flux={}
        for name in ('inlet','outlet','farfield'):
            rv=patch_scalars(rfile,name); fv=patch_scalars(phifile,name)
            if len(rv)==1:rv*=len(fv)
            if len(rv)!=len(fv):raise ValueError(f'{name} rho/phi count mismatch')
            flux[name]={'volumeM3s':sum(fv),'massKgS':sum(a*b for a,b in zip(rv,fv))}
        total=sum(x['massKgS'] for x in flux.values())
        start,n=patches['fsi']; force=[0.,0.,0.]
        for fi in range(start,start+n):
            cell=owner[fi]
            for j in range(3):force[j]-=pvals[cell]*sf[fi][j]
        out.append({'timeS':float(tdir.name),'fields':{'pPa':extrema(pvals,centers),'TK':extrema(T,centers),'rhoKgM3':extrema(rho,centers),'speedMps':extrema(umag,centers)},'massFluxKgS_outwardPositive':flux,'netOpenBoundaryMassFlowKgS':total,'pressureOnlyForceN_XYZ':force})
    return {'speedIASKmh':int(speed),'case':str(case),'checkpointCount':len(out),'results':out,'limitations':['Pressure forces omit viscous stress and are transient.','X pressure force includes the artificial inboard cut; do not interpret it as aircraft spanwise load.']}

ap=argparse.ArgumentParser(); ap.add_argument('--case',required=True); ap.add_argument('--speed',required=True); args=ap.parse_args()
case=Path(args.case).resolve(); result=analyze(case,args.speed)
out=case.parent/f'checkpoint_history_ias{args.speed}.json'; out.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
