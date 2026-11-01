#!/usr/bin/env python3
from pathlib import Path
import json, math, re, sys
case=Path(sys.argv[1])
def numeric(p):
    try:return float(p.name)
    except ValueError:return -1
stamps=sorted((p for p in case.iterdir() if p.is_dir() and p.name!='0' and numeric(p)>0),key=numeric)
candidates = list(reversed(stamps[:-1])) if len(stamps) > 1 else list(reversed(stamps))
for d in candidates:
    if all((d/n).is_file() for n in ('T','U','p','rho')):
        chosen=d; break
else:
    print(json.dumps({'error':'no complete prior checkpoint'})); sys.exit(2)
def values(path, typ):
    s=path.read_text()
    m=re.search(rf'internalField\s+nonuniform\s+List<{typ}>\s+\d+\s*\((.*?)\)\s*;',s,re.S)
    if not m: raise ValueError(f'cannot parse {typ}: {path}')
    nums=re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',m.group(1))
    return list(map(float,nums))
T=values(chosen/'T','scalar'); p=values(chosen/'p','scalar'); rho=values(chosen/'rho','scalar'); u=values(chosen/'U','vector')
mag=[math.sqrt(u[i]*u[i]+u[i+1]*u[i+1]+u[i+2]*u[i+2]) for i in range(0,len(u),3)]
cp=1004.5
total=[temp+speed*speed/(2*cp) for temp,speed in zip(T,mag)]
print(json.dumps({'timeSeconds':numeric(chosen),'checkpoint':chosen.name,'minTemperatureK':min(T),'maxTemperatureK':max(T),'minTotalTemperatureK':min(total),'maxTotalTemperatureK':max(total),'minPressurePa':min(p),'maxPressurePa':max(p),'minDensityKgM3':min(rho),'maxDensityKgM3':max(rho),'minSpeedMps':min(mag),'maxSpeedMps':max(mag)}))
