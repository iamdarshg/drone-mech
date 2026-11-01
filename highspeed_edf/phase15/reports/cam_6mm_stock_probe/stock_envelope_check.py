#!/usr/bin/env python3
"""Conservative planar tool-envelope check for retained FreeCAD Path text dumps.
Not a stock-removal, holder, fixture, machine travel, or controller simulation.
"""
import json, math, re
from pathlib import Path
BASE=Path(__file__).parent
STOCK=(0.0,0.0,40.0,20.0)
RADIUS=1.0
cmd_re=re.compile(r'^Command\s+(G[0-3])\s+\[(.*)\]$')
param_re=re.compile(r'([XYZIJK]):\s*([-+0-9.eE]+)')
def parse(path):
    current=None; pts=[]; arc_errors=[]; count=0
    for line in path.read_text().splitlines():
        m=cmd_re.match(line.strip())
        if not m: continue
        code, raw=m.groups(); p={k:float(v) for k,v in param_re.findall(raw)}
        if not any(k in p for k in 'XY'):
            if 'Z' in p: pass
            continue
        if current is None:
            current=[p.get('X',0.0),p.get('Y',0.0)]
            pts.append(tuple(current)); continue
        end=[p.get('X',current[0]),p.get('Y',current[1])]
        if code in ('G2','G3') and 'I' in p and 'J' in p:
            cx=current[0]+p['I']; cy=current[1]+p['J']
            a0=math.atan2(current[1]-cy,current[0]-cx); a1=math.atan2(end[1]-cy,end[0]-cx)
            r0=math.hypot(current[0]-cx,current[1]-cy); r1=math.hypot(end[0]-cx,end[1]-cy)
            if abs(r0-r1)>0.03: arc_errors.append((count,r0,r1))
            if code=='G3': delta=(a1-a0)%(2*math.pi)
            else: delta=-((a0-a1)%(2*math.pi))
            n=max(2,math.ceil(abs(delta)/(math.pi/180)))
            for i in range(1,n+1):
                a=a0+delta*i/n; pts.append((cx+r0*math.cos(a),cy+r0*math.sin(a)))
        else:
            pts.append(tuple(end))
        current=end; count+=1
    if not pts: raise RuntimeError(f'No XY moves found in {path}')
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    bounds=[min(xs),min(ys),max(xs),max(ys)]
    expanded=[bounds[0]-RADIUS,bounds[1]-RADIUS,bounds[2]+RADIUS,bounds[3]+RADIUS]
    xmin,ymin,xmax,ymax=STOCK
    inside=expanded[0]>=xmin and expanded[1]>=ymin and expanded[2]<=xmax and expanded[3]<=ymax
    return {'file':path.name,'move_count':count,'centerline_xy_bounds_mm':bounds,'tool_radius_mm':RADIUS,'expanded_xy_bounds_mm':expanded,'stock_xy_bounds_mm':list(STOCK),'swept_planar_tool_envelope_inside_stock':inside,'arc_radius_mismatch_count':len(arc_errors),'largest_arc_radius_mismatch_mm':max((abs(a-b) for _,a,b in arc_errors),default=0.0)}
results=[parse(BASE/'facing_commands.txt'),parse(BASE/'profile_commands.txt')]
with open(BASE/'stock_envelope_check.json','w') as f:json.dump(results,f,indent=2)
print(json.dumps(results,indent=2))
if not all(x['swept_planar_tool_envelope_inside_stock'] for x in results): raise SystemExit(1)
