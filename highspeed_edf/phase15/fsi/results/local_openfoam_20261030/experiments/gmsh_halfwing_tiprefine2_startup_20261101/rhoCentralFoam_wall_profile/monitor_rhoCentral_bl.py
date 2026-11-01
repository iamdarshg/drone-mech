#!/usr/bin/env python3
from pathlib import Path
import datetime,json,os,shutil,signal,subprocess,time
root=Path('/tmp/gmsh_halfwing_fluid');case=root/'rhoCentral_bl_case';log=root/'rhoCentralFoam.bl.log';status=root/'rhoCentral_bl.status';samples=root/'rhoCentral_bl.monitor.jsonl';helper=root/'checkpoint_bounds_bl.py'
pattern=f'^/workspace/openfoam-deb/usr/bin/rhoCentralFoam -case {case}$'
def pids():
 try:return [int(x) for x in subprocess.check_output(['pgrep','-f',pattern],text=True).split()]
 except (subprocess.CalledProcessError,ValueError):return []
def lasttime():
 try:return [x for x in log.read_text(errors='replace').splitlines() if x.startswith('Time =')][-1]
 except (OSError,IndexError):return None
while True:
 ids=pids();item={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pids':ids,'lastLoggedTime':lasttime(),'diskFreeBytes':shutil.disk_usage(root).free}
 if ids:
  try:
   bounds=json.loads(subprocess.check_output(['python3',str(helper),str(case)],text=True,stderr=subprocess.STDOUT,timeout=90));item['checkpoint']=bounds
   reason=None
   if bounds.get('maxTotalTemperatureK',0)>344.281:reason='adiabatic input Tt guard > 1.05*327.886735 K =344.281 K'
   elif bounds.get('maxSpeedMps',0)>700:reason='700 m/s speed guard'
   elif item['diskFreeBytes']<1_500_000_000:reason='disk free below 1.5 GB'
   if reason:
    item['action']='SIGTERM: '+reason;(root/'rhoCentral_bl.stop_reason.json').write_text(json.dumps({'utc':item['utc'],'reason':item['action'],'checkpoint':bounds},indent=2)+'\n')
    for pid in ids:
     try:os.kill(pid,signal.SIGTERM)
     except ProcessLookupError:pass
  except Exception as e:item['checkpointError']=repr(e)
 with samples.open('a') as f:f.write(json.dumps(item)+'\n')
 if not ids and status.exists():break
 time.sleep(30)
