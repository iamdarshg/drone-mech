#!/usr/bin/env python3
"""Guard fresh Mach 1.05 rhoCentralFoam startup; never relax thresholds."""
from pathlib import Path
import datetime,json,os,re,shutil,signal,subprocess,time
ROOT=Path('/tmp/cfd-run-m105-20261101'); CASE=ROOT/'case'
LOG=ROOT/'rhoCentralFoam.m105_attempt3.log'; STATUS=ROOT/'rhoCentralFoam.m105_attempt3.status'
SAMPLES=ROOT/'monitor.m105_attempt3.jsonl'; STOP=ROOT/'stop_reason.m105_attempt3.json'
HELPER=Path(__file__).with_name('checkpoint_bounds.py')
PATTERN=rf'^/workspace/openfoam-deb/usr/bin/rhoCentralFoam -case {re.escape(str(CASE))}$'
T0_INF_K=327.886735; TT_GUARD_K=1.05*T0_INF_K; SPEED_GUARD_MPS=700.0
TMP_FLOOR_BYTES=1_500_000_000; OVERLAY_FLOOR_BYTES=300_000_000

def pids():
    try:return [int(x) for x in subprocess.check_output(['pgrep','-f',PATTERN],text=True).split()]
    except (subprocess.CalledProcessError,ValueError):return []
def lasttime():
    try:return [x for x in LOG.read_text(errors='replace').splitlines() if x.startswith('Time =')][-1]
    except (OSError,IndexError):return None
while True:
    ids=pids(); item={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pids':ids,'lastLoggedTime':lasttime(),'tmpFreeBytes':shutil.disk_usage('/tmp').free,'overlayFreeBytes':shutil.disk_usage('/workspace').free}
    bounds=None
    if ids:
        try:
            r=subprocess.run(['python3',str(HELPER),str(CASE)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            if r.returncode==0:bounds=json.loads(r.stdout);item['checkpoint']=bounds
            elif 'no complete checkpoint' in r.stdout or 'Compressed file ended' in r.stdout:item['checkpointUnavailable']='no complete checkpoint yet or write in progress'
            else:item['checkpointError']=r.stdout[-1200:]
        except Exception as e:item['checkpointError']=repr(e)
    reason=None
    if bounds is not None and bounds.get('maxTotalTemperatureK',0)>TT_GUARD_K:reason=f'pointwise Tt proxy > 1.05*327.886735 K ({TT_GUARD_K:.6f} K)'
    elif bounds is not None and bounds.get('maxSpeedMps',0)>SPEED_GUARD_MPS:reason=f'speed > {SPEED_GUARD_MPS:.1f} m/s'
    elif bounds is not None and (bounds.get('minTemperatureK',0)<=0 or bounds.get('minPressurePa',0)<=0 or bounds.get('minDensityKgM3',0)<=0):reason='non-positive T/p/rho checkpoint'
    elif item['tmpFreeBytes']<TMP_FLOOR_BYTES:reason=f'/tmp free space below {TMP_FLOOR_BYTES} bytes'
    elif item['overlayFreeBytes']<OVERLAY_FLOOR_BYTES:reason=f'overlay free space below {OVERLAY_FLOOR_BYTES} bytes'
    if reason and ids:
        item['action']='SIGTERM: '+reason
        STOP.write_text(json.dumps({'utc':item['utc'],'reason':item['action'],'checkpoint':bounds,'tmpFreeBytes':item['tmpFreeBytes'],'overlayFreeBytes':item['overlayFreeBytes']},indent=2)+'\n')
        for pid in ids:
            try:os.kill(pid,signal.SIGTERM)
            except ProcessLookupError:pass
    with SAMPLES.open('a') as f:f.write(json.dumps(item)+'\n')
    if not ids and STATUS.exists():break
    time.sleep(30)
