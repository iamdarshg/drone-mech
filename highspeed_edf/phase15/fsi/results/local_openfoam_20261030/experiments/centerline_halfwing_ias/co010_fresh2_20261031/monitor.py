#!/usr/bin/env python3
"""Observe latest persisted checkpoints and stop before unbounded nonphysical divergence."""
import json, math, os, re, signal, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def scalar(path):
    s=path.read_text(); m=re.search(r'internalField\s+nonuniform\s+List<scalar>\s+\d+\s*\((.*?)\)\s*;',s,re.S)
    if not m: raise ValueError(f'missing scalar values in {path}')
    a=list(map(float,re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',m.group(1))))
    return min(a),max(a)
def vector(path):
    s=path.read_text(); m=re.search(r'internalField\s+nonuniform\s+List<vector>\s+\d+\s*\((.*?)\)\s*;',s,re.S)
    if not m: raise ValueError(f'missing vector values in {path}')
    a=[math.sqrt(sum(float(v)**2 for v in x)) for x in re.findall(r'\(\s*([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s*\)',m.group(1))]
    return min(a),max(a)
def proc_for(case):
    # Exact binary/case string match; monitor itself does not contain this as argv.
    p=subprocess.run(['pgrep','-f',f'^/workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case {case}$'],text=True,capture_output=True)
    return [int(x) for x in p.stdout.split() if x.isdigit()]
with (ROOT/'monitor.log').open('a',buffering=1) as log:
    while True:
        alive=False
        for speed in (700,900):
            case=ROOT/f'ias{speed}'
            dirs=[p for p in case.iterdir() if p.is_dir() and p.name!='0' and re.fullmatch(r'\d+(?:\.\d+)?(?:[eE][-+]?\d+)?',p.name)]
            latest=max(dirs,key=lambda p:float(p.name)) if dirs else None
            pids=proc_for(str(case)); alive |= bool(pids)
            if latest:
                try:
                    tmin,tmax=scalar(latest/'T'); pmin,pmax=scalar(latest/'p'); umin,umax=vector(latest/'U')
                    row={'utc':datetime.now(timezone.utc).isoformat(),'speedIASkmh':speed,'pid':pids,'checkpoint':float(latest.name),'temperatureK':[tmin,tmax],'pressurePa':[pmin,pmax],'speedMps':[umin,umax]}
                    log.write(json.dumps(row)+'\n')
                    # For this external-flow case, T>1000 K or |U|>1000 m/s signals the documented runaway.
                    if tmax>1000 or umax>1000 or pmin<1000 or pmax>500000:
                        row['stopReason']='persisted field crossed broad nonphysical guardrail'
                        log.write(json.dumps(row)+'\n')
                        for pid in pids:
                            try: os.kill(pid,signal.SIGINT)
                            except ProcessLookupError: pass
                except (OSError,ValueError) as e:
                    log.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'speedIASkmh':speed,'checkpoint':str(latest),'parseError':str(e)})+'\n')
            else:
                log.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'speedIASkmh':speed,'pid':pids,'checkpoint':None})+'\n')
        if not alive: break
        time.sleep(60)
