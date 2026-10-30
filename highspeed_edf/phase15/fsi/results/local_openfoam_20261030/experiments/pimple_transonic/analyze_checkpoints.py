#!/usr/bin/env python3
"""Compute boundary mass flux and pressure-only wing load from native snapshots."""
from __future__ import annotations
import json, math, re
from pathlib import Path

HERE = Path(__file__).resolve().parent

def dictionary_block(text: str, key: str) -> str:
    match = re.search(rf'(?m)^\s*{re.escape(key)}\s*\{{', text)
    if not match:
        raise ValueError(f"block {key!r} not found")
    start = text.index('{', match.start())
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{': depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0: return text[start + 1:i]
    raise ValueError(f"unterminated block {key!r}")

def scalar_list(text: str, *, internal=False) -> list[float]:
    if internal:
        match = re.search(r'internalField\s+nonuniform\s+List<scalar>\s+\d+\s*\((.*?)\)\s*;', text, re.S)
    else:
        match = re.search(r'value\s+nonuniform\s+List<scalar>\s+\d+\s*\((.*?)\)', text, re.S)
    if not match: raise ValueError("nonuniform scalar list not found")
    return [float(v) for v in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', match.group(1))]

def field_patch(path: Path, patch: str) -> list[float]:
    text = path.read_text(); block = dictionary_block(dictionary_block(text, 'boundaryField'), patch)
    m = re.search(r'value\s+uniform\s+([-+\d.eE]+)', block)
    if m: return [float(m.group(1))]
    return scalar_list(block)

def vector_list(path: Path) -> list[tuple[float,float,float]]:
    text=path.read_text()
    m=re.search(r'internalField\s+nonuniform\s+List<vector>\s+\d+\s*\((.*?)\)\s*;',text,re.S)
    if not m: m=re.search(r'\n\s*\d+\s*\n\s*\((.*)\)\s*\n',text,re.S)
    if not m: raise ValueError(f'no vector list in {path}')
    return [tuple(map(float,v)) for v in re.findall(r'\(\s*([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s*\)',m.group(1))]


def read_mesh(mesh: Path):
    pts=vector_list(mesh/'points')
    face_text=(mesh/'faces').read_text(); face_body=re.search(r'\n\s*\d+\s*\n\s*\((.*)\)\s*\n',face_text,re.S).group(1)
    faces=[list(map(int,x.split())) for x in re.findall(r'\d+\s*\(([^()]*)\)',face_body)]
    def ints(name):
        t=(mesh/name).read_text(); b=re.search(r'\n\s*\d+\s*\n\s*\((.*)\)\s*\n',t,re.S).group(1); return list(map(int,re.findall(r'\d+',b)))
    owner=ints('owner'); neighbour=ints('neighbour')
    btext=(mesh/'boundary').read_text(); patches={}
    for name in ('inlet','outlet','farfield','fsi','rootWall'):
        b=dictionary_block(btext,name)
        sf=int(re.search(r'\bstartFace\s+(\d+)',b).group(1)); nf=int(re.search(r'\bnFaces\s+(\d+)',b).group(1)); patches[name]=(sf,nf)
    areas=[]
    for f in faces:
        a=[0.,0.,0.]
        for i in range(len(f)):
            p,q=pts[f[i]],pts[f[(i+1)%len(f)]]
            a[0]+=p[1]*q[2]-p[2]*q[1]; a[1]+=p[2]*q[0]-p[0]*q[2]; a[2]+=p[0]*q[1]-p[1]*q[0]
        areas.append(tuple(x*0.5 for x in a))
    return faces,owner,patches,areas

def analyze(speed: str, time_dir: Path):
    case=HERE/f'ias{speed}'; mesh=case/'constant/polyMesh'; faces,owner,patches,areas=read_mesh(mesh)
    rho=case/time_dir.name/'rho'; phi=case/time_dir.name/'phi'; p=case/time_dir.name/'p'
    outputs={}
    for name in ('inlet','outlet','farfield'):
        r=field_patch(rho,name); f=field_patch(phi,name)
        if len(r)==1: r*=len(f)
        if len(r)!=len(f): raise ValueError(f'{name}: rho faces={len(r)}, phi faces={len(f)}')
        outputs[name]={'faceCount':len(f),'volumeFluxM3s':sum(f),'massFluxKgS_outwardPositive':sum(a*b for a,b in zip(r,f))}
    open_mass=sum(v['massFluxKgS_outwardPositive'] for v in outputs.values())
    inout=outputs['inlet']['massFluxKgS_outwardPositive']+outputs['outlet']['massFluxKgS_outwardPositive']
    pv=scalar_list(p.read_text(),internal=True)
    sf, nf=patches['fsi']; force=[0.,0.,0.]
    for fi in range(sf,sf+nf):
        # Pressure-only traction on the wing: -p*n, with n outward from fluid.
        cell=owner[fi]; area=areas[fi]
        for j in range(3): force[j]-=pv[cell]*area[j]
    return {'speedIASKmh':int(speed),'snapshotTime':time_dir.name,'massFluxes':outputs,'netOpenBoundaryMassFlowKgS':open_mass,'inletPlusOutletMassFlowKgS':inout,'pressureOnlyWingForceN_outwardFluidNormalConvention':force,'pressureOnlyForceOmitsViscousStress':True}

all_data=[]
for speed in ('700','900'):
    case=HERE/f'ias{speed}'
    dirs=[p for p in case.iterdir() if p.is_dir() and p.name[0].isdigit()]
    if dirs: all_data.append(analyze(speed,max(dirs,key=lambda x:float(x.name))))
(HERE/'checkpoint_flux_and_pressure_loads.json').write_text(json.dumps(all_data,indent=2)+'\n')
print(json.dumps(all_data,indent=2))
