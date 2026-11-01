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
if errors:
    print('\n'.join('FAIL: ' + e for e in errors), file=sys.stderr)
    raise SystemExit(1)
print(f'PASS: {len(report["parts"])} exact-source slicer records and boundaries verify; slicer warning is preserved.')
