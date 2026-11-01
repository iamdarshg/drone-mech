#!/usr/bin/env python3
from pathlib import Path
import gzip,json,math,re,sys
case=Path(sys.argv[1]); num=r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
def tv(p):
 try:return float(p.name)
 except ValueError:return -1
def field(d,n,comp):
 p=d/n
 if not p.exists():p=d/(n+'.gz');f=gzip.open(p,'rt')
 else:f=p.open('rt')
 with f:s=f.read()
 a=s.index('internalField');m=re.search(r'nonuniform\s+List<\w+>\s+(\d+)\s*\(',s[a:])
 if not m:raise ValueError('no nonuniform list in '+str(p))
 count=int(m.group(1));o=a+m.end();e=s.index('\n)',o)
 vals=list(map(float,re.findall(num,s[o:e])))
 if len(vals)!=count*comp:raise ValueError(f'incomplete {n}: expected {count*comp}, parsed {len(vals)}')
 return vals
stamps=sorted((p for p in case.iterdir() if p.is_dir() and p.name!='0' and tv(p)>0),key=tv)
for chosen in reversed(stamps):
 try:
  T=field(chosen,'T',1);P=field(chosen,'p',1);rho=field(chosen,'rho',1);U=field(chosen,'U',3)
  break
 except (FileNotFoundError,ValueError,EOFError):continue
else:print(json.dumps({'error':'no complete checkpoint'}));sys.exit(2)
cp=1004.685;gamma=1.4
speed=[math.sqrt(sum(U[i+j]**2 for j in range(3))) for i in range(0,len(U),3)]
tt=[t+v*v/(2*cp) for t,v in zip(T,speed)];mach=[v/math.sqrt(gamma*p/r) for v,p,r in zip(speed,P,rho)]
i=max(range(len(tt)),key=tt.__getitem__);j=max(range(len(mach)),key=mach.__getitem__)
print(json.dumps({'timeSeconds':tv(chosen),'checkpoint':chosen.name,'minTemperatureK':min(T),'maxTemperatureK':max(T),'maxTotalTemperatureK':tt[i],'maxTotalTemperatureCell':i,'maxMach':mach[j],'maxMachCell':j,'maxSpeedMps':max(speed),'minPressurePa':min(P),'maxPressurePa':max(P),'minDensityKgM3':min(rho),'maxDensityKgM3':max(rho)}))
