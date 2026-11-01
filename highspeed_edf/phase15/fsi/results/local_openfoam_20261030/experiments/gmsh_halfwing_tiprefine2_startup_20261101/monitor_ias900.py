#!/usr/bin/env python3
from pathlib import Path
import datetime, json, os, shutil, signal, subprocess, sys, time
root=Path('/tmp/gmsh_halfwing_fluid'); case=root/'ias900_case'; log=root/'rhoPimpleFoam.log'; status=root/'status.txt'; monitor=root/'monitor.jsonl'; helper=root/'checkpoint_bounds.py'
pattern=f'^/workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case {case}$'
def pids():
    try:return [int(x) for x in subprocess.check_output(['pgrep','-f',pattern],text=True).split()]
    except (subprocess.CalledProcessError,ValueError):return []
def last_time():
    try:
        lines=[x for x in log.read_text(errors='replace').splitlines() if x.startswith('Time =')]
        return lines[-1] if lines else None
    except OSError:return None
while True:
    ids=pids(); item={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pids':ids,'lastLoggedTime':last_time(),'diskFreeBytes':shutil.disk_usage(root).free}
    if ids:
        try:
            raw=subprocess.check_output(['python3',str(helper),str(case)],text=True,stderr=subprocess.STDOUT,timeout=60)
            bounds=json.loads(raw); item['checkpoint']=bounds
            unsafe=(bounds.get('maxTemperatureK',0)>330 or bounds.get('minTemperatureK',1e9)<150 or bounds.get('maxTotalTemperatureK',0)>330 or (bounds.get('maxSpeedMps',0)>700))
            if unsafe:
                item['action']='SIGTERM: thermodynamic/velocity bound exceeded'
                (root/'stop_reason.json').write_text(json.dumps({'utc':item['utc'],'reason':item['action'],'checkpoint':bounds},indent=2)+'\n')
                for pid in ids:
                    try:os.kill(pid,signal.SIGTERM)
                    except ProcessLookupError:pass
            elif item['diskFreeBytes']<1_500_000_000:
                item['action']='SIGTERM: workspace disk free below 1.5 GB'
                (root/'stop_reason.json').write_text(json.dumps({'utc':item['utc'],'reason':item['action'],'checkpoint':bounds},indent=2)+'\n')
                for pid in ids:
                    try:os.kill(pid,signal.SIGTERM)
                    except ProcessLookupError:pass
        except Exception as e:item['checkpointError']=repr(e)
    with monitor.open('a') as f:f.write(json.dumps(item)+'\n')
    if not ids and status.exists():break
    time.sleep(30)
