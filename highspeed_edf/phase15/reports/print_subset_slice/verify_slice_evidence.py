#!/usr/bin/env python3
"""Verify hashes and retained software-slice facts; never changes expectations."""
from pathlib import Path
import hashlib, json, re, sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROFILE = ROOT / 'highspeed_edf/phase15/print_prototype/main_wing/software_slice'
load = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
report = load(HERE / 'slice_subset_results.json')
conversion = load(HERE / 'step_mesh_conversion.json')
errors = []
def check(condition, message):
    if not condition:
        errors.append(message)
check(report['status'] == 'software_only_slice_evidence_not_print_release', 'unexpected report status')
check(report['slicer']['runtime_lock_sha256'] == sha(HERE / 'runtime_lock.json'), 'runtime lock hash mismatch')
for name, expected in report['profile']['effective_profile_hashes'].items():
    check(sha(PROFILE / name) == expected, f'profile hash mismatch: {name}')
conv = {p['part']: p for p in conversion['parts']}
for part in report['parts']:
    src = ROOT / part['step_source']
    stl, gcode, log = HERE / part['stl'], HERE / (part['part'] + '.a1mini-review.gcode'), HERE / ('wing_slicer.log' if part['part'].startswith('wing_') else 'fuselage_slicer.log')
    check(src.exists() and sha(src) == part['step_source_sha256'], f'STEP hash mismatch: {part["part"]}')
    check(stl.exists() and sha(stl) == part['stl_sha256'], f'STL hash mismatch: {part["part"]}')
    check(gcode.exists() and sha(gcode) == part['gcode_sha256'], f'G-code hash mismatch: {part["part"]}')
    check(log.exists() and sha(log) == part['cli_log_sha256'], f'slicer log hash mismatch: {part["part"]}')
    check(part['part'] in conv and conv[part['part']]['source_step_sha256'] == part['step_source_sha256'], f'conversion/source disagreement: {part["part"]}')
    if gcode.exists():
        body = gcode.read_text(errors='replace')
        supports = len(re.findall(r'^; FEATURE: Support\b|^;TYPE:Support\b', body, re.M | re.I))
        check(supports == part['gcode_support_feature_markers'], f'support marker count mismatch: {part["part"]}')
    if part['part'] == 'fuselage_shell_segment_01_port':
        check('floating cantilever' in part['slicer_warning'], 'fuselage warning was lost')
        check(part['gcode_support_feature_markers'] == 0, 'unexpected support markers; re-review evidence')
check(report['boundary']['physical_printer_used'] is False, 'physical printer boundary changed')
check(report['boundary']['adhesion_orientation_and_strength_verified'] is False, 'unsupported verification claim')
check(report['boundary']['fabrication_or_aircraft_release'] is False, 'unsupported release claim')
# The support-on subset is separate and must not rewrite baseline evidence.
trial = load(HERE / 'support_orientation_subset.json')
trial_process = load(HERE / 'fuselage_trial_support_on_process.json')
base_process = load(PROFILE / 'effective-process.json')
trial_gcode = HERE / trial['gcode']['path']
trial_result = load(HERE / 'fuselage_trial_support_on_result.json')
changes = {k: [base_process.get(k), trial_process.get(k)] for k in set(base_process) | set(trial_process) if base_process.get(k) != trial_process.get(k)}
check(changes == {'enable_support': ['0', '1']}, 'support trial changed more than enable_support')
check(sha(HERE / 'fuselage_trial_support_on_process.json') == trial['trial_process_sha256'], 'support trial process hash mismatch')
check(trial['source']['step_sha256'] == next(p['step_source_sha256'] for p in report['parts'] if p['part'] == 'fuselage_shell_segment_01_port'), 'support variant source STEP mismatch')
check(trial_gcode.exists() and sha(trial_gcode) == trial['gcode']['sha256'], 'support variant G-code hash mismatch')
check(trial_result['return_code'] == 0 and trial_result['sliced_plates'][0]['warning_message'] == '', 'support variant slicer warning/result mismatch')
if trial_gcode.exists():
    trial_text = trial_gcode.read_text(errors='replace')
    trial_supports = len(re.findall(r'^; FEATURE: Support\b|^;TYPE:Support\b', trial_text, re.M | re.I))
    check(trial_supports == trial['gcode']['support_feature_markers'] and trial_supports > 0, 'support feature marker count mismatch')
check(trial['baseline_comparison']['baseline_warning_cleared_by_slicer'] is True, 'support-on warning clearance not recorded')
check(trial['boundary']['physical_print_performed'] is False and trial['boundary']['structural_print_success_established'] is False and trial['boundary']['production_release'] is False, 'unsupported physical/readiness claim')
if errors:
    print('\n'.join('FAIL: ' + e for e in errors), file=sys.stderr)
    raise SystemExit(1)
print(f'PASS: baseline records and one support-on variant verify; baseline warning preserved and support-on warning clearance independently confirmed.')
