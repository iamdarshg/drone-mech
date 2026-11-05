from pathlib import Path
import re,json
p=Path('/work/cfd_duct_prisms_flow_diagnostic/100/phi');text=p.read_text();part=text.split('boundaryField',1)[1];out={}
for name in ['inlet','outlet','walls']:
 m=re.search(r'\b'+name+r'\s*\{([^{}]*)\}',part,re.S);assert m
 x=m.group(1);non=re.search(r'value\s+nonuniform\s+List<scalar>\s+(\d+)\s*\((.*?)\)',x,re.S)
 if non:
  values=[float(v) for v in non.group(2).split()];assert len(values)==int(non.group(1));out[name]=sum(values)
 else:
  v=re.search(r'value\s+uniform\s+([-+\deE.]+)',x);assert v and float(v.group(1))==0;out[name]=0.0
result={'iteration':100,'patch_flux_m3_per_s':out,'inlet_negative_outlet_positive':out['inlet']<0<out['outlet'],'imbalance_relative_to_inlet':abs(sum(out.values()))/abs(out['inlet']),'scope':'diagnostic incompressible numerical run; not converged, no validated pressure recovery or design conclusion'}
Path('/work/duct_prisms_flux_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
