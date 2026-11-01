#!/usr/bin/env python3
"""Hash-pin OrcaSlicer subset outputs and verify they match selected CAD inputs."""
from pathlib import Path
import hashlib, json, re
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'highspeed_edf/phase15/reports/print_subset_slice'
PROFILE_DIR=ROOT/'highspeed_edf/phase15/print_prototype/main_wing/software_slice'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
conversion=read(OUT/'step_mesh_conversion.json')
mesh_by_part={p['part']:p for p in conversion['parts']}
source_info={
 'wing_left_sector_x1_z1':{
  'out_name':'wing_left_sector_x1_z1','result':'wing_result.json','gcode':'wing_left_sector_x1_z1.a1mini-review.gcode','log':'wing_slicer.log','output_dir':'/tmp/orca-subset/wing-out','datadir':'/tmp/orca-subset/wing-data','expected_warning':''
 },
 'fuselage_shell_segment_01_port':{
  'out_name':'fuselage_shell_segment_01_port','result':'fuselage_result.json','gcode':'fuselage_shell_segment_01_port.a1mini-review.gcode','log':'fuselage_slicer.log','output_dir':'/tmp/orca-subset/fuse-out','datadir':'/tmp/orca-subset/fuse-data','expected_warning':'floating cantilever'
 }
}
results=[]
for part,meta in source_info.items():
 converted=mesh_by_part[part]
 result=read(OUT/meta['result'])
 gcode_path=OUT/meta['gcode']; gtext=gcode_path.read_text(errors='replace')
 log=(OUT/meta['log']).read_text(errors='replace')
 header=gtext.split('; HEADER_BLOCK_END',1)[0]
 def header_line(label):
  m=re.search(r'^; '+re.escape(label)+r':?\s*(.*?)\s*$',header,re.M)
  return m.group(1).strip() if m else None
 time=re.search(r'^; model printing time: (.*?); total estimated time: (.*?)$',header,re.M)
 orientation=re.search(r'^best:([^\n]+)$',log,re.M)
 warning=result['sliced_plates'][0]['warning_message']
 support_markers=len(re.findall(r'^; FEATURE: Support\b|^;TYPE:Support\b',gtext,re.M|re.I))
 results.append({
  'part':part,
  'step_source':converted['source_step'],
  'step_source_sha256':converted['source_step_sha256'],
  'mesh_conversion':'FreeCAD MeshPart export from exact STEP source at 0.05 mm linear / 0.1 rad angular deflection',
  'stl':converted['stl'],'stl_sha256':converted['stl_sha256'],'stl_extents_mm':converted['mesh_bounds_mm'],'stl_facets':converted['mesh_facets'],
  'slicer_input_unit_interpretation':'Millimetres, inherited from FreeCAD-converted STEP units; STL itself has no unit metadata.',
  'slicer_return_code':result['return_code'],'slicer_error_string':result['error_string'],'slicer_plate_id':result['sliced_plates'][0]['id'],'slicer_triangle_count':result['sliced_plates'][0]['triangle_count'],'slicer_warning':warning,
  'slicer_reported_best_orientation_candidate':orientation.group(1).strip() if orientation else None,
  'gcode_model_time':time.group(1) if time else None,'gcode_total_estimated_time':time.group(2) if time else None,'gcode_total_layers':int(header_line('total layer number')) if header_line('total layer number') else None,'gcode_max_z_height_mm':float(header_line('max_z_height')) if header_line('max_z_height') else None,
  'gcode_support_feature_markers':support_markers,'gcode_sha256':sha(gcode_path),'gcode_bytes':gcode_path.stat().st_size,
  'cli_args':['--datadir',meta['datadir'],'--load-settings',str(PROFILE_DIR/'effective-machine.json')+';'+str(PROFILE_DIR/'effective-process.json'),'--load-filaments',str(PROFILE_DIR/'effective-filament.json'),'--orient','1','--arrange','1','--outputdir',meta['output_dir'],'--slice','0',str(OUT/converted['stl'])],
  'cli_log_sha256':sha(OUT/meta['log']),
  'slicer_warning_expected':meta['expected_warning']
 })
profile_names={f:sha(PROFILE_DIR/f) for f in ['effective-machine.json','effective-process.json','effective-filament.json']}
runtime=read(OUT/'runtime_lock.json')
summary={
 'status':'software_only_slice_evidence_not_print_release',
 'generated_utc':'2026-11-01',
 'slicer':{'name':'OrcaSlicer','version':'2.4.2','appimage_url':runtime['orca_slicer']['appimage_url'],'appimage_sha256':runtime['orca_slicer']['appimage_sha256'],'runtime_lock_sha256':sha(OUT/'runtime_lock.json'),'os':runtime['runtime_os'],'private_rootless_runtime':True},
 'profile':{'printer':'Bambu Lab A1 mini 0.4 nozzle (profile assumption; physical configuration unverified)','process':'0.20mm Standard @BBL A1M','filament':'Bambu PLA Basic @BBL A1M (user material not verified)','plate':'Textured PEI Plate (profile default; actual plate not verified)','effective_profile_hashes':profile_names,'layer_height_mm':0.2,'wall_loops':2,'infill_percent':15,'brim_width_mm':5,'support_generation':'same effective process used by prior subset slice; no support feature markers in either G-code'},
 'parts':results,
 'checks':{
  'both_slice_jobs_return_success':all(p['slicer_return_code']==0 and p['slicer_error_string']=='Success.' for p in results),
  'selected_wing_piece_has_no_slicer_warning':results[0]['slicer_warning']=='',
  'fuselage_slice_warning_preserved':bool(results[1]['slicer_warning']) and 'floating cantilever' in results[1]['slicer_warning'],
  'both_gcodes_contain_no_support_features':all(p['gcode_support_feature_markers']==0 for p in results),
  'both_parts_fit_profile_cube_by_source_extents':all(max(p['stl_extents_mm'])<=180.0 for p in results)
 },
 'boundary':{'gcode_review_only':True,'physical_printer_used':False,'adhesion_orientation_and_strength_verified':False,'fabrication_or_aircraft_release':False,'fuselage_floating_cantilever_warning_resolved':False,'flight_readiness_claim':False}
}
summary['all_recorded_checks_pass']=all(summary['checks'].values())
(OUT/'slice_subset_results.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'all_recorded_checks_pass':summary['all_recorded_checks_pass'],'checks':summary['checks'],'parts':[{k:p[k] for k in ['part','stl_extents_mm','slicer_return_code','slicer_warning','gcode_model_time','gcode_total_estimated_time','gcode_total_layers','gcode_max_z_height_mm','gcode_sha256']} for p in results]},indent=2))
if not summary['all_recorded_checks_pass']:raise SystemExit('slice evidence verification failed')
