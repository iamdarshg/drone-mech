#!/usr/bin/env python3
from pathlib import Path
import datetime,json,os,shutil,signal,subprocess,time
root=Path('/tmp/gmsh_halfwing_fluid');case=root/'rhoCentral_case';log=root/'rhoCentralFoam.log';status=root/'rhoCentral.status'; samples=root/'rhoCentral.monitor.jsonl';helper=root/'checkpoint_bounds_central.py'
pattern=f'^/workspace/openfoam-deb/usr/bin/rhoCentralFoam -case {case}$'
def pids():
 try:return [int(x) for x in subprocess.check_output(['pgrep','-f',pattern],text=True).split()]
 except (subprocess.CalledProcessError,ValueError):return []
def last_time():
 try:
  return [x for x in log.read_text(errors='replace').splitlines() if x.startswith('Time =')][-1]
 except (OSError,IndexError):return None
while True:
 ids=pids(); item={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pids':ids,'lastLoggedTime':last_time(),'diskFreeBytes':shutil.disk_usage(root).free}
 if ids:
  try:
   raw=subprocess.check_output(['python3',str(helper),str(case)],text=True,stderr=subprocess.STDOUT,timeout=90);bounds=json.loads(raw);item['checkpoint']=bounds
   reason=None
   if bounds.get('maxTotalTemperatureK',0)>324.0:reason='adiabatic input total-temperature bound: >1.05*308.56 K =324.0 K'
   elif bounds.get('maxSpeedMps',0)>700:reason='700 m/s velocity guard'
   elif item['diskFreeBytes']<1_500_000_000:reason='disk free below 1.5 GB'
   if reason:
    item['action']='SIGTERM: '+reason;(root/'rhoCentral.stop_reason.json').write_text(json.dumps({'utc':item['utc'],'reason':item['action'],'checkpoint':bounds},indent=2)+'\n')
    for pid in ids:
     try:os.kill(pid,signal.SIGTERM)
     except ProcessLookupError:pass
  except Exception as e:item['checkpointError']=repr(e)
 with samples.open('a') as f:f.write(json.dumps(item)+'\n')
 if not ids and status.exists():break
 time.sleep(30)
