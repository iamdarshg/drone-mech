#!/usr/bin/env python3
from pathlib import Path
import datetime,json,os,shutil,signal,subprocess,time
root=Path('/tmp/gmsh_halfwing_fluid');case=root/'rhoCentral_bl_case';log=root/'rhoCentralFoam.co005.log';status=root/'rhoCentral_bl.co005.status';samples=root/'rhoCentral_bl.co005.monitor.jsonl';helper=root/'checkpoint_bounds_bl.co005.py'
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
  bounds=None
  try:
   result=subprocess.run(['python3',str(helper),str(case)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
   if result.returncode == 0:
    bounds=json.loads(result.stdout);item['checkpoint']=bounds
   elif 'no complete checkpoint' in result.stdout:
    item['checkpointUnavailable']='expected before the first complete writeInterval checkpoint'
   else:
    item['checkpointError']=result.stdout[-1200:]
  except Exception as e:item['checkpointError']=repr(e)
  reason=None
  if bounds is not None and bounds.get('maxTotalTemperatureK',0)>344.281:reason='adiabatic input Tt guard > 1.05*327.886735 K =344.281 K'
  elif bounds is not None and bounds.get('maxSpeedMps',0)>700:reason='700 m/s speed guard'
  elif item['diskFreeBytes']<1_500_000_000:reason='disk free below 1.5 GB'
  if reason:
   item['action']='SIGTERM: '+reason;(root/'rhoCentral_bl.co005.stop_reason.json').write_text(json.dumps({'utc':item['utc'],'reason':item['action'],'checkpoint':bounds},indent=2)+'\n')
   for pid in ids:
    try:os.kill(pid,signal.SIGTERM)
    except ProcessLookupError:pass
 with samples.open('a') as f:f.write(json.dumps(item)+'\n')
 if not ids and status.exists():break
 time.sleep(30)
