#!/usr/bin/env python3
"""Minute monitor; terminate diagnostic if native fields violate bounds."""
from pathlib import Path
import datetime, json, os, shutil, signal, subprocess, sys, time
root=Path(__file__).resolve().parent
case=root/'ias900'
log=root/'rhoPimpleFoam_ias900.log'
status=root/'status.txt'
monitor=root/'monitor.jsonl'
helper=root/'checkpoint_bounds.py'
pattern=f'rhoPimpleFoam -case {case}'
def process_ids():
    try:
        out=subprocess.check_output(['pgrep','-f',pattern],text=True).split()
        return [int(x) for x in out]
    except (subprocess.CalledProcessError,ValueError): return []
def last_time():
    try:
        lines=[x for x in log.read_text(errors='replace').splitlines() if x.startswith('Time =')]
        return lines[-1] if lines else None
    except OSError:return None
while True:
    ids=process_ids()
    if status.exists() and not ids: break
    item={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pids':ids,'lastLoggedTime':last_time(),'diskFreeBytes':shutil.disk_usage(root).free}
    if ids:
        try:
            raw=subprocess.check_output(['python3',str(helper),str(case)],text=True,stderr=subprocess.STDOUT,timeout=30)
            bounds=json.loads(raw); item['checkpoint']=bounds
            unsafe=(bounds.get('maxTemperatureK',0)>330 or bounds.get('minTemperatureK',1e9)<150 or bounds.get('maxTotalTemperatureK',0)>330 or bounds.get('minPressurePa',1)>0 and bounds.get('minDensityKgM3',1)>0 and bounds.get('maxSpeedMps',0)>700)
            if unsafe:
                item['action']='SIGTERM: thermodynamic/velocity bound exceeded'
                (root/'stop_reason.json').write_text(json.dumps({'utc':item['utc'],'reason':item['action'],'checkpoint':bounds},indent=2)+'\n')
                for pid in ids:
                    try: os.kill(pid,signal.SIGTERM)
                    except ProcessLookupError: pass
            elif item['diskFreeBytes']<1_500_000_000:
                item['action']='SIGTERM: workspace disk free below 1.5 GB'
                (root/'stop_reason.json').write_text(json.dumps({'utc':item['utc'],'reason':item['action'],'checkpoint':bounds},indent=2)+'\n')
                for pid in ids:
                    try: os.kill(pid,signal.SIGTERM)
                    except ProcessLookupError: pass
        except Exception as e:item['checkpointError']=repr(e)
    with monitor.open('a') as f:f.write(json.dumps(item)+'\n')
    if not ids and status.exists(): break
    time.sleep(60)
