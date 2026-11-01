#!/usr/bin/env python3
"""Verify source pins and arithmetic in the machining/print envelope screen."""
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'highspeed_edf/phase15/reports/cam_buildability_screen'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assumptions=read(OUT/'user_setup_assumptions.json')
parts=read(OUT/'native_part_extent_verification.json')
rotor=read(ROOT/'highspeed_edf/phase15/reports/cam_6mm_stock_probe/saved_job_verification.json')
stator=read(ROOT/'highspeed_edf/phase15/reports/cam_6mm_stator_probe/saved_job_verification.json')
rotor_env=read(ROOT/'highspeed_edf/phase15/reports/cam_6mm_stock_probe/stock_envelope_check.json')
stator_env=read(ROOT/'highspeed_edf/phase15/reports/cam_6mm_stator_probe/stock_envelope_check.json')
cnc_envelope=read(ROOT/'highspeed_edf/phase15/reports/machine_envelope_screen/envelope_screen.json')
reach=assumptions['cutters']['latest_user_estimate_flute_length_mm']
flute_min,flute_max=reach
stock6=6.0; stock20=20.0; nesting_blank=5.0
report={
 'status':'screen_only_no_cut_approval',
 'freecad_native_import_count':parts['part_count'],
 'checks':{
  'all_25_step_files_hash_and_solid_count_recorded':len(parts['native_step_imports'])==25 and parts['all_step_solid_counts_match_manifest'],
  'all_native_tessellated_bounds_match_segment_manifest_within_0_02mm':parts['all_part_imports_match_segment_manifest_within_0_02mm'],
  'all_step_units_are_mm':parts['all_step_units_mm'],
  'all_step_import_object_placements_at_origin':parts['all_document_placements_at_origin'],
  'all_a1_parts_fit_axis_aligned_180mm_profile_cube_by_tessellated_geometry':parts['all_parts_fit_axis_aligned_profile_envelope'],
  '6mm_rotor_cam_job_is_2mm_2flute_geometry_preview':rotor['stock_bbox_mm'][-1]==6.0 and rotor['tool_diameter_mm']==2.0 and rotor['tool_flutes']==2 and rotor['profile_final_depth_mm']==0.0,
  '6mm_stator_cam_job_is_2mm_2flute_geometry_preview':stator['stock_bbox_mm'][-1]==6.0 and stator['tool_diameter_mm']==2.0 and stator['flutes']==2 and stator['final_depth_mm']==0.0,
  '6mm_saved_paths_planar_envelope_inside_assumed_subblank':all(x['swept_planar_tool_envelope_inside_stock'] and x['arc_radius_mismatch_count']==0 for x in rotor_env+stator_env),
  '6mm_depth_has_nominal_latest_flute_margin_only':min(flute_min-stock6,flute_max-stock6)>=0,
  '6mm_depth_fails_earlier_5mm_provisional_tool_estimate':assumptions['cutters']['earlier_user_provisional_estimate_mm']<stock6,
  '20mm_one_side_exceeds_latest_2mm_tool_flute_estimate':flute_max<stock20,
  'two_sided_8mm_flute_leaves_midweb':stock20-2*flute_min>0,
  'two_sided_10mm_flute_has_zero_nominal_midweb':stock20-2*flute_max==0,
  'no_controller_nc_or_physical_test':assumptions['authorization_boundary']['controller_ready_nc_emitted'] is False and assumptions['authorization_boundary']['physical_hardware_tested'] is False,
  'exact_user_cnc_identity_unverified':assumptions['cnc']['exact_make_model_verified'] is False,
  'conditional_sainsmart_envelope_layout_fits':cnc_envelope['cnc_layout_fit_conditional_sainsmart_3018_pro'] is True and cnc_envelope['cnc_exact_user_machine_identity_verified'] is False
 },
 'derived_reach_arithmetic_mm':{
  '6mm_stock_single_face_flute_margin_for_latest_estimate':[flute_min-stock6,flute_max-stock6],
  '6mm_stock_single_face_margin_for_earlier_5mm_estimate':assumptions['cutters']['earlier_user_provisional_estimate_mm']-stock6,
  '20mm_one_side_depth_deficit_for_latest_estimate':[stock20-flute_max,stock20-flute_min],
  '20mm_two_side_cut_depth_per_side':stock20/2,
  '20mm_two_side_residual_midweb_for_latest_estimate':[stock20-2*flute_min,stock20-2*flute_max],
  '20mm_two_side_residual_web_if_reserving_2mm_flute_margin_each_side':[stock20-2*(flute_min-2),stock20-2*(flute_max-2)],
  '20mm_to_5mm_nest_blank_total_face_reduction':stock20-nesting_blank,
  'balanced_two_face_reduction_per_face_for_20_to_5mm':[ (stock20-nesting_blank)/2, (stock20-nesting_blank)/2 ],
  'balanced_20_to_5mm_face_reduction_flute_margin_for_latest_estimate':[flute_min-(stock20-nesting_blank)/2,flute_max-(stock20-nesting_blank)/2]
 },
 'limitations':['Arithmetic is a reach screen only. Flute length is a user estimate, not measured or backed by cutter-maker data.','No holder/shank, workholding, alignment pins, spoilboard, stock flatness, machine datum, spindle, feeds/speeds, postprocessor, or 3D collision simulation was verified.','6mm path fixtures omit negative-Z spoilboard overtravel, so they do not establish a complete severance path.','20mm calculations are not toolpaths. A two-sided flip requires registered setups and actual axial reach/clearance; zero nominal web is not clearance.','CAD envelope fit and slicer volume fit do not establish print success, strength, assembly fit, or CNC feasibility.'],
 'source_inputs':{}
}
source_paths=[
 'highspeed_edf/deliverables/phase15_geometry/stock_nests/sheet_A_250x120x5_36rotors_63stators.step',
 'highspeed_edf/phase15/reports/cam_6mm_stock_probe/result.json',
 'highspeed_edf/phase15/reports/cam_6mm_stock_probe/sheet_A_one_rotor_6mm_stock_probe.FCStd',
 'highspeed_edf/phase15/reports/cam_6mm_stock_probe/make_sheet_a_6mm_cam_preview.FCMacro',
 'highspeed_edf/phase15/reports/cam_6mm_stock_probe/facing_commands.txt',
 'highspeed_edf/phase15/reports/cam_6mm_stock_probe/profile_commands.txt',
 'highspeed_edf/phase15/reports/cam_6mm_stock_probe/stock_envelope_check.py',
 'highspeed_edf/phase15/reports/cam_6mm_stock_probe/saved_job_verification.json',
 'highspeed_edf/phase15/reports/cam_6mm_stock_probe/stock_envelope_check.json',
 'highspeed_edf/phase15/reports/cam_6mm_stator_probe/result.json',
 'highspeed_edf/phase15/reports/cam_6mm_stator_probe/sheet_A_one_stator_6mm_stock_probe.FCStd',
 'highspeed_edf/phase15/reports/cam_6mm_stator_probe/make_sheet_a_6mm_stator_cam_preview.FCMacro',
 'highspeed_edf/phase15/reports/cam_6mm_stator_probe/facing_commands.txt',
 'highspeed_edf/phase15/reports/cam_6mm_stator_probe/profile_commands.txt',
 'highspeed_edf/phase15/reports/cam_6mm_stator_probe/stock_envelope_check.py',
 'highspeed_edf/phase15/reports/cam_6mm_stator_probe/saved_job_verification.json',
 'highspeed_edf/phase15/reports/cam_6mm_stator_probe/stock_envelope_check.json',
 'highspeed_edf/phase15/print_prototype/main_wing/segmentation_manifest.json',
 'highspeed_edf/phase15/print_prototype/fuselage_shell/segmentation_manifest.json',
 'highspeed_edf/phase15/print_prototype/main_wing/software_slice/effective-machine.json',
 'highspeed_edf/phase15/print_prototype/main_wing/software_slice/plate_1.gcode',
 'highspeed_edf/phase15/reports/machine_envelope_screen/envelope_screen.json',
 'highspeed_edf/phase15/reports/machine_envelope_screen/machine_envelopes_and_stock.FCStd'
]
for rel in source_paths:report['source_inputs'][rel]=sha(ROOT/rel)
report['checks']['all_part_hashes_match_import_log']=all(x['step_sha256']==sha(ROOT/(('highspeed_edf/phase15/print_prototype/main_wing/' if x['group']=='main_wing' else 'highspeed_edf/phase15/print_prototype/fuselage_shell/')+x['step'])) for x in parts['native_step_imports'])
checks=report['checks']
report['all_checks_pass']=all(checks.values())
(OUT/'screen_verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'all_checks_pass':report['all_checks_pass'],'checks':checks,'derived_reach_arithmetic_mm':report['derived_reach_arithmetic_mm']},indent=2))
if not report['all_checks_pass']:raise SystemExit('buildability screen checks failed')
