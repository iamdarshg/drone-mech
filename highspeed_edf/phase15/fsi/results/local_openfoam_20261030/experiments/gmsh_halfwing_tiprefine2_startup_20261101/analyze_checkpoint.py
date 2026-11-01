from pathlib import Path
import numpy as np,re
case=Path('/tmp/gmsh_halfwing_fluid/ias900_case')
t=case/'4.670542e-07'
def field(name, typ, comps=1):
 s=(t/name).read_text(); a=s.index('internalField'); o=s.index('(',s.index('nonuniform',a)); e=s.index('\n)',o)
 vals=np.array([float(v) for v in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',s[o+1:e])])
 return vals.reshape((-1,comps)) if comps>1 else vals
T=field('T','scalar'); p=field('p','scalar'); rho=field('rho','scalar'); U=field('U','vector',3); h=field('h','scalar')
mag=np.linalg.norm(U,axis=1); tt=T+mag**2/(2*1004.5); a=np.sqrt(1.4*p/rho); m=mag/a
for label,x in [('maxTotalT',tt),('maxStaticT',T),('maxSpeed',mag),('minStaticT',T),('minPressure',p),('maxPressure',p),('maxMach',m)]:
 idx=int(np.argmax(x) if label.startswith('max') else np.argmin(x))
 print(label,'idx',idx,'value',float(x[idx]),'T',float(T[idx]),'U',U[idx].tolist(),'speed',float(mag[idx]),'p',float(p[idx]),'rho',float(rho[idx]),'Mach',float(m[idx]))
print('cell36858 h',float(h[36858]),'cpT',1004.685*float(T[36858]),'h_plus_ke',float(h[36858]+0.5*mag[36858]**2),'ideal_gas_rho',float(p[36858]/(287.05*T[36858])))
print('cell36858 q_ratio_to_freestream_total_h',float((h[36858]+0.5*mag[36858]**2)/(1004.685*268.65+0.5*(2.47111015739**2+283.16117725609**2))))
print('freestream static T',268.65,'speed',283.17196,'totalT_proxy',268.65+283.17196**2/(2*1004.5),'p',70100,'rho',70100/(287.05*268.65),'Mach',283.17196/(1.4*287.05*268.65)**.5)
