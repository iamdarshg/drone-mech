#!/usr/bin/env python3
from pathlib import Path
import json,math,re,sys
case=Path(sys.argv[1])
def time_value(p):
 try:return float(p.name)
 except ValueError:return -1.0
dirs=sorted((p for p in case.iterdir() if p.is_dir() and p.name!='0' and time_value(p)>=0),key=time_value)
candidates=list(reversed(dirs[:-1])) if len(dirs)>1 else list(reversed(dirs))
for d in candidates:
 if all((d/n).is_file() for n in ('T','U','p','rho')): chosen=d;break
else: print(json.dumps({'error':'no complete checkpoint'}));sys.exit(2)
def vals(path):
 s=path.read_text(); a=s.index('internalField'); o=s.index('(',s.index('nonuniform',a)); e=s.index('\n)',o)
 nums=re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',s[o+1:e]);return list(map(float,nums))
T=vals(chosen/'T');p=vals(chosen/'p');rho=vals(chosen/'rho');u=vals(chosen/'U')
mag=[math.sqrt(sum(u[i+j]**2 for j in range(3))) for i in range(0,len(u),3)]
cp=1004.685; t0=[t+v*v/(2*cp) for t,v in zip(T,mag)]
print(json.dumps({'timeSeconds':float(chosen.name),'checkpoint':chosen.name,'minTemperatureK':min(T),'maxTemperatureK':max(T),'maxTotalTemperatureK':max(t0),'minPressurePa':min(p),'maxPressurePa':max(p),'minDensityKgM3':min(rho),'maxDensityKgM3':max(rho),'minSpeedMps':min(mag),'maxSpeedMps':max(mag),'maxTotalTemperatureCell':max(range(len(t0)),key=t0.__getitem__)}))
