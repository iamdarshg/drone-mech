"""Source-pinned preliminary feasibility bounds for drone-mech issue #2.

This screen reimports the existing motor STEP envelopes and evaluates only
necessary geometric bounds and source-backed integration constraints. It does
not generate or rank a redesign, run a native solver, or establish hardware fit.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_INPUTS = REPO_ROOT / "highspeed_edf/phase15/configs/motor_drive_screen_sources.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_local_sources(repo_root: Path, inputs: dict[str, Any]) -> dict[str, Any]:
    """Check every byte-pinned local input, including all six native STEP files."""
    checked: list[dict[str, Any]] = []
    errors: list[str] = []
    missing_inputs = False
    unexpected_inputs = False
    for row in inputs["baseline"]["local_sources"]:
        path = repo_root / row["path"]
        actual = sha256_file(path) if path.is_file() else None
        ok = actual == row["sha256"]
        checked.append({"path": row["path"], "expected_sha256": row["sha256"],
                        "actual_sha256": actual,
                        "status": "PASS" if ok else "BLOCKED" if actual is None else "FAIL"})
        if not ok:
            errors.append(f"missing or changed pinned source: {row['path']}")
            missing_inputs |= actual is None
    motor_root = repo_root / "highspeed_edf/deliverables/phase15_geometry/step"
    expected_steps = inputs["baseline"]["native_motor_step_sha256"]
    actual_names = sorted(path.name for path in motor_root.glob("motor_*_3670_*_envelope.step"))
    if actual_names != sorted(expected_steps):
        errors.append(f"expected six pinned motor STEP files, found {len(actual_names)}")
        missing_inputs |= bool(set(expected_steps) - set(actual_names))
        unexpected_inputs |= bool(set(actual_names) - set(expected_steps))
    for name, expected in sorted(expected_steps.items()):
        path = motor_root / name
        actual = sha256_file(path) if path.is_file() else None
        ok = actual == expected
        checked.append({"path": str(path.relative_to(repo_root)), "expected_sha256": expected,
                        "actual_sha256": actual,
                        "status": "PASS" if ok else "BLOCKED" if actual is None else "FAIL"})
        if not ok:
            errors.append(f"missing or changed pinned motor solid: {name}")
            missing_inputs |= actual is None
    status = "FAIL" if unexpected_inputs or any(row["status"] == "FAIL" for row in checked) else \
        "BLOCKED" if missing_inputs else "PASS"
    return {"status": status, "checked": checked,
            "errors": errors}


def validate_inputs(inputs: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if inputs.get("schema_version") != 1:
        errors.append("unsupported or missing schema_version")
    if inputs.get("units") != "mm":
        errors.append("all geometric inputs must declare mm")
    try:
        sources = inputs["external_sources"]
        for key in ("issue2_text_snapshot_path", "donor_motor_note_path", "arm_source_revision", "arm_source_files",
                    "arm_expected_git_blob_sha1", "board_measurement_adapter"):
            if key not in sources:
                errors.append(f"missing source declaration: external_sources.{key}")
        if not inputs["baseline"].get("native_motor_step_sha256"):
            errors.append("native STEP source hashes are missing")
    except (KeyError, TypeError) as exc:
        errors.append(f"malformed source manifest: {type(exc).__name__}: {exc}")
    return errors


def read_generator_constants(generator_path: Path) -> dict[str, Any]:
    """Read literal generator constants without importing/executing CAD code."""
    tree = ast.parse(generator_path.read_text(encoding="utf-8"))
    wanted = {"ROTOR_CHORD", "ROTOR_Z", "MOTOR_CAN_D", "MOTOR_CAN_LENGTH",
              "MOTOR_MASS_KG", "DUCT_ID", "DUCT_LENGTH", "ESC_BOARD", "FC_BOARD"}
    values: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                try:
                    values[target.id] = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
    missing = sorted(wanted - set(values))
    if missing:
        raise ValueError(f"generator constants are not literal or are absent: {missing}")
    return values


def parse_motor_source_variants(repo_root: Path, inputs: dict[str, Any], constants: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse each contradictory dimension from its named source, keeping classes separate."""
    external = inputs["external_sources"]
    issue_text = (repo_root / external["issue2_text_snapshot_path"]).read_text(encoding="utf-8")
    donor_text = (repo_root / external["donor_motor_note_path"]).read_text(encoding="utf-8")
    issue_match = re.search(r"Ø\s*(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)\s*mm\s+Surpass\s+3670", issue_text)
    if not issue_match:
        raise ValueError("issue #2 text snapshot no longer contains the pinned ØD×L motor assertion")
    donor_3670_line = next((line for line in donor_text.splitlines() if "36×70 can" in line), "")
    donor_3660_line = next((line for line in donor_text.splitlines() if "36×60" in line), "")
    donor_3670_match = re.search(r"(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)\s+can", donor_3670_line)
    donor_3660_match = re.search(r"(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)", donor_3660_line)
    mass_match = re.search(r"~?(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)\s*g", donor_text)
    shaft_match = re.search(r"(\d+(?:\.\d+)?)\s*mm shaft", donor_text)
    if not donor_3670_match or not donor_3660_match or not mass_match:
        raise ValueError("donor note no longer provides the pinned 3670/3660 envelope and mass-range strings")
    native_stub = None
    tree = ast.parse((repo_root / "highspeed_edf/phase15/optimization/phase15_generate_geometry.py").read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "makeCylinder" or len(node.args) < 2:
            continue
        try:
            first, second = ast.literal_eval(node.args[0]), ast.literal_eval(node.args[1])
        except (ValueError, TypeError):
            continue
        if first == 2.5 and second == 8.0:
            native_stub = {"radius_argument_mm": 2.5, "length_mm": 8.0,
                           "interpretation": "generator cylinder primitive only; not an identified supplier shaft diameter"}
            break
    return [
        {"id": "phase15_generated_can", "diameter_mm": float(constants["MOTOR_CAN_D"]),
         "can_length_mm": float(constants["MOTOR_CAN_LENGTH"]),
         "evidence_class": "literal generator constants; generated envelope, not supplier-native geometry",
         "modeled_stub": native_stub},
        {"id": "issue2_text_claim", "diameter_mm": float(issue_match.group(1)),
         "can_length_mm": float(issue_match.group(2)),
         "evidence_class": "dimension parsed from SHA-pinned GitHub issue body snapshot"},
        {"id": "donor_3670_note", "diameter_mm": float(donor_3670_match.group(1)),
         "can_length_mm": float(donor_3670_match.group(2)),
         "shaft_diameter_mm_secondary_claim": float(shaft_match.group(1)) if shaft_match else None,
         "mass_range_kg_secondary_claim": [float(mass_match.group(1)) / 1000.0,
                                           float(mass_match.group(2)) / 1000.0],
         "evidence_class": "secondary sourcing note with stated OEM dimensions; not independently measured"},
        {"id": "donor_3660_note", "diameter_mm": float(donor_3660_match.group(1)),
         "can_length_mm": float(donor_3660_match.group(2)),
         "evidence_class": "secondary donor shortlist; not selected or measured"},
    ]


def read_installed_constraints(repo_root: Path, inputs: dict[str, Any], arm_source_root: Path,
                               constants: dict[str, Any], geometry_audit: dict[str, Any]) -> dict[str, Any]:
    """Re-import source-pinned PCB outlines with PR34's native adapter each run."""
    from highspeed_edf.verification.native_adapters import import_kicad_board, board_placeholder_comparison

    external = inputs["external_sources"]
    revision = external["arm_source_revision"]
    files = external["arm_source_files"]
    expected_blobs = external["arm_expected_git_blob_sha1"]
    source_results: dict[str, Any] = {}
    for key, relative_path in files.items():
        source_results[key] = git_blob_provenance(arm_source_root, revision, relative_path,
                                                   expected_blobs.get(relative_path, ""))
    if any(row["status"] != "PASS" for row in source_results.values()):
        status = "FAIL" if any(row["status"] == "FAIL" for row in source_results.values()) else "BLOCKED"
        return {"status": status, "source_files": source_results,
                "errors": ["arm PCB/pinmap/architecture source bytes are missing or differ from the pinned issue-23 revision"]}

    board_data: dict[str, Any] = {}
    board_refs = {"main": files["main_pcb"], "esc": files["esc_pcb"]}
    placeholders = {"main": list(constants["FC_BOARD"][:2]),
                    "esc": list(constants["ESC_BOARD"][:2])}
    for board_name, relative_path in board_refs.items():
        measured = import_kicad_board(arm_source_root / relative_path)
        comparison = board_placeholder_comparison(measured, tuple(placeholders[board_name]))
        board_data[board_name] = {"measured_edge_centerline_mm": [measured["width_mm"], measured["height_mm"]],
                                  "cad_placeholder_mm": placeholders[board_name],
                                  "difference_mm": comparison["difference_mm"],
                                  "placeholder_comparison_status": comparison["status"],
                                  "pcb_sha256": measured["sha256"],
                                  "git_blob_sha1": source_results["main_pcb" if board_name == "main" else "esc_pcb"]["working_tree_git_blob_sha1"],
                                  "pcbnew_version": measured["version"],
                                  "edge_primitive_count": measured["edge_graphic_count"]}
    pinmap_path = arm_source_root / files["mcu_pinmap"]
    pinmap = json.loads(pinmap_path.read_text(encoding="utf-8"))
    nets = sorted({str(row.get("net", "")).split("/")[-1]
                   for row in pinmap.get("pins", {}).values()
                   if re.search(r"(?:^|/)PWM_ESC\d+$", str(row.get("net", "")))})
    effector_count = int(geometry_audit["checks"]["servoPositions"])
    pwm_count = len(nets)
    architecture_path = arm_source_root / files["architecture"]
    architecture_text = architecture_path.read_text(encoding="utf-8")
    motor_row = re.search(r"^\|\s*Motors\s*\|\s*(\d+|six)\s+independent\s+three-phase\s+BLDC/PMSM channels", architecture_text, re.MULTILINE | re.IGNORECASE)
    if not motor_row:
        raise ValueError("pinned Rev-B architecture has no parseable independent motor-channel row")
    motor_count_text = motor_row.group(1).lower()
    motor_channels = 6 if motor_count_text == "six" else int(motor_count_text)
    return {
        "status": "PASS" if board_data and pwm_count > 0 else "BLOCKED",
        "source_repository_revision": revision,
        "source_checkout_root": os.path.relpath(arm_source_root, repo_root),
        "source_files": source_results,
        "measurement_adapter": external["board_measurement_adapter"],
        "outline_method": "Edge.Cuts endpoint/arc-center coordinates from native pcbnew; stroke extents excluded",
        "board_outlines": board_data,
        "component_solid_heights": "BLOCKED: pcbnew audit has no native component-solid vertical bounds",
        "mcu_pwm_nets": nets,
        "distinct_pwm_count": pwm_count,
        "independent_effector_count_from_mech_native_audit": effector_count,
        "actuator_channel_status": "PASS" if effector_count == pwm_count else "FAIL",
        "independent_motor_channel_count_from_arm_architecture": motor_channels,
        "fabrication_release_authority": "NONE_DECLARED",
        "integrated_board_fit_status": "BLOCKED: component heights, mounting/service volumes, and body-to-board datum are unavailable",
    }


def overlap_bound(can_length_mm: float, station_pitch_mm: float) -> dict[str, Any]:
    """Return zero-clearance can overlap and the mathematical pitch lower bound."""
    if not all(math.isfinite(float(x)) and float(x) >= 0 for x in (can_length_mm, station_pitch_mm)):
        raise ValueError("can length and station pitch must be finite nonnegative millimetres")
    overlap = max(0.0, float(can_length_mm) - float(station_pitch_mm))
    return {"can_length_mm": float(can_length_mm), "station_pitch_mm": float(station_pitch_mm),
            "zero_clearance_axial_overlap_mm": overlap,
            "zero_clearance_minimum_pitch_mm": float(can_length_mm),
            "operating_clearance_mm": None,
            "clearance_status": "BLOCKED: no sourced tolerance or operating-clearance value"}


def in_bore_motor_separation(duct_id_mm: float, motor_diameter_mm: float) -> dict[str, Any]:
    """Necessary cross-section bound for two equal cans wholly inside one bore."""
    if duct_id_mm <= 0 or motor_diameter_mm <= 0:
        raise ValueError("duct and motor diameters must be positive mm values")
    available_center_separation = max(0.0, float(duct_id_mm) - float(motor_diameter_mm))
    required_center_separation = float(motor_diameter_mm)
    fits = available_center_separation + 1e-9 >= required_center_separation
    return {"duct_inner_diameter_mm": float(duct_id_mm),
            "motor_can_diameter_mm": float(motor_diameter_mm),
            "maximum_center_separation_within_bore_mm": available_center_separation,
            "minimum_center_separation_for_nonoverlap_mm": required_center_separation,
            "shortfall_mm": max(0.0, required_center_separation - available_center_separation),
            "necessary_cross_section_bound": "PASS" if fits else "FAIL",
            "assumption": "both equal motor cans fully inside a circular bore; shafts/transmission excluded"}


def git_blob_provenance(arm_source_root: Path, revision: str, relative_path: str,
                        expected_blob: str) -> dict[str, Any]:
    """Require both the pinned revision blob and checked-out bytes to match."""
    path = arm_source_root / relative_path
    if not path.is_file():
        return {"path": relative_path, "status": "BLOCKED", "error": "source file is missing"}
    pinned = subprocess.run(["git", "-C", str(arm_source_root), "rev-parse", f"{revision}:{relative_path}"],
                            text=True, capture_output=True)
    current = subprocess.run(["git", "-C", str(arm_source_root), "hash-object", str(path)],
                             text=True, capture_output=True)
    pinned_blob = pinned.stdout.strip() if pinned.returncode == 0 else None
    current_blob = current.stdout.strip() if current.returncode == 0 else None
    passed = bool(expected_blob and pinned_blob == expected_blob and current_blob == expected_blob)
    return {"path": relative_path, "source_revision": revision,
            "expected_git_blob_sha1": expected_blob,
            "revision_git_blob_sha1": pinned_blob,
            "working_tree_git_blob_sha1": current_blob,
            "sha256": sha256_file(path), "status": "PASS" if passed else "FAIL"}


def _read_register(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _import_motor_geometry(repo_root: Path, inputs: dict[str, Any]) -> dict[str, Any]:
    try:
        from highspeed_edf.verification.native_adapters import import_step, motor_bbox_collision
        paths = sorted((repo_root / "highspeed_edf/deliverables/phase15_geometry/step")
                       .glob(inputs["baseline"]["native_motor_step_glob"].split("/")[-1]))
        records = [import_step(path) for path in paths]
        collision = motor_bbox_collision(records)
        measured_solids = []
        for record in records:
            solids = []
            for solid in record["solids"]:
                box = solid["bbox_mm"]
                solids.append({**solid, "dimensions_mm": [box[3] - box[0], box[4] - box[1], box[5] - box[2]]})
            measured_solids.append({"path": str(Path(record["path"]).resolve().relative_to(repo_root.resolve())),
                                    "sha256": record["sha256"],
                                    "valid": record["valid"], "solid_count": record["solid_count"],
                                    "solids": solids})
        return {"status": collision["status"], "motor_count": len(records),
                "pairs_checked": collision["pairs_checked"],
                "collision_count": len(collision["collisions"]),
                "imported_solids": measured_solids,
                "pair_measurements": collision["pairs"],
                "tool_versions": {name: importlib.metadata.version(name)
                                  for name in ("cadquery", "cadquery-ocp")}}
    except Exception as exc:  # missing CadQuery is an honest blocked native check
        return {"status": "BLOCKED", "motor_count": 0, "pairs_checked": 0,
                "collision_count": 0, "imported_solids": [], "pair_measurements": [],
                "errors": [f"native motor import/interference could not run: {type(exc).__name__}: {exc}"]}


def run_screen(repo_root: Path, inputs: dict[str, Any], input_path: Path,
               arm_source_root: Path | None = None) -> dict[str, Any]:
    validation_errors = validate_inputs(inputs)
    source_check = verify_local_sources(repo_root, inputs) if not validation_errors else {
        "status": "BLOCKED", "checked": [], "errors": validation_errors}
    report: dict[str, Any] = {
        "screen_id": inputs.get("screen_id"),
        "issue": "iamdarshg/drone-mech#2",
        "scope": "preliminary necessary-bound calculations; no candidate selection",
        "input_path": str(input_path.resolve().relative_to(repo_root.resolve()))
                      if input_path.resolve().is_relative_to(repo_root.resolve()) else input_path.name,
        "input_sha256": sha256_file(input_path) if input_path.is_file() else None,
        "runner": {"path": str(Path(__file__).resolve().relative_to(repo_root.resolve())),
                   "sha256": sha256_file(Path(__file__).resolve()),
                   "python_version": sys.version.split()[0]},
        "source_integrity": source_check,
        "candidate_ranking": "NOT_APPLICABLE",
        "claims": {"native_solver_run": False, "geometry_redesign": False,
                   "hardware_run": False, "flight_claim": False,
                   "overall_evidence_class": "PRELIMINARY ANALYTICAL BOUNDS"},
        "errors": validation_errors,
    }
    if validation_errors or source_check["status"] != "PASS":
        report["overall_status"] = "FAIL" if validation_errors else source_check["status"]
        return report

    generator_path = repo_root / "highspeed_edf/phase15/optimization/phase15_generate_geometry.py"
    register_path = repo_root / "highspeed_edf/deliverables/phase15_geometry/reports/phase15_parameter_register.json"
    constants = read_generator_constants(generator_path)
    register = _read_register(register_path)
    geometry_audit = _read_register(repo_root / "highspeed_edf/deliverables/phase15_geometry/reports/phase15_geometry_audit.json")
    from highspeed_edf.verification.native_adapters import validate_cad_datum
    datum = validate_cad_datum(register_path)
    if datum["status"] != "PASS":
        report["overall_status"] = "FAIL"
        report["errors"].extend(datum["errors"])
        return report
    motor_variants = parse_motor_source_variants(repo_root, inputs, constants)
    rotor_z = [float(x) for x in register["nominal"]["rotorZmm"]]
    pitches = [rotor_z[index + 1] - rotor_z[index] for index in range(len(rotor_z) - 1)]
    if not pitches or any(abs(p - pitches[0]) > 1e-9 for p in pitches):
        report["overall_status"] = "FAIL"
        report["errors"].append("rotor station pitch is missing or nonuniform; this screen only supports uniform spacing")
        return report
    pitch = pitches[0]
    duct_id = float(register["nominal"]["ductInnerDiameterMm"])
    module_length = float(register["nominal"]["moduleLengthMm"])
    native = _import_motor_geometry(repo_root, inputs)

    dimension_variants = []
    for variant in motor_variants:
        bound = overlap_bound(variant["can_length_mm"], pitch)
        dimension_variants.append({"id": variant["id"], "diameter_mm": variant["diameter_mm"],
                                  "can_length_mm": variant["can_length_mm"],
                                  "evidence_class": variant["evidence_class"], **bound})

    # Conservative planning envelope: take the largest diameter and length
    # independently across the recorded claims. This is an analytical box,
    # not a measured or supplier-certified package.
    planning_envelope = {
        "diameter_mm": max(float(v["diameter_mm"]) for v in motor_variants),
        "can_length_mm": max(float(v["can_length_mm"]) for v in motor_variants),
        "dimension_policy": "independent maxima across source variants; planning envelope only",
        "evidence_class": "unverified conservative analytical envelope; actual SKU dimensions unverified",
    }

    model_length = float(constants["MOTOR_CAN_LENGTH"])
    model_diameter = float(constants["MOTOR_CAN_D"])
    required_pitch = planning_envelope["can_length_mm"]
    delta_pitch = max(0.0, required_pitch - pitch)
    row_gaps = max(0, len(rotor_z) - 1)
    # Explicit bound: preserve current first/last end-clearance allowances and
    # add the pitch delta once per existing inter-row gap. This is not duct CAD.
    axial_module_bound = module_length + row_gaps * delta_pitch

    if arm_source_root is None:
        arm_source_root = repo_root.parent / "drone-arm"
    try:
        integration_constraints = read_installed_constraints(repo_root, inputs, arm_source_root,
                                                             constants, geometry_audit)
    except Exception as exc:
        integration_constraints = {"status": "BLOCKED", "errors": [
            f"source-pinned arm board extraction unavailable: {type(exc).__name__}: {exc}"]}

    two_row_count = int(inputs["screen_assumptions"]["reduced_stage_scenario_stages_per_duct"])
    current_motors = int(integration_constraints.get("independent_motor_channel_count_from_arm_architecture", 0))
    reduced_motor_count = 2 * two_row_count
    donor_3670 = next(v for v in motor_variants if v["id"] == "donor_3670_note")
    mass_low, mass_high = donor_3670["mass_range_kg_secondary_claim"]
    removed_motor_mass = [(current_motors - reduced_motor_count) * mass_low,
                          (current_motors - reduced_motor_count) * mass_high]
    candidates = [
        {"id": "current_six_motor_inline_direct_drive", "status": "FAIL" if native["status"] == "FAIL" else native["status"],
         "native_geometry": "measured existing STEP envelopes",
         "finding": "Existing layout has positive-volume motor-solid intersections; baseline geometry remains unchanged.",
         "native_collision_pair_count": native["collision_count"]},
        {"id": "increase_axial_station_spacing", "status": "BLOCKED",
         "lower_bound": {"current_pitch_mm": pitch, "required_zero_clearance_pitch_mm": model_length,
                         "minimum_pitch_increase_mm": max(0.0, model_length - pitch),
                         "module_length_lower_bound_mm": axial_module_bound,
                         "module_length_formula": f"{module_length:g} + {row_gaps} * {delta_pitch:g}",
                         "assumption": "preserves existing row-train end allowances; omits motor service length, tolerances, supports, and installed hardware"},
         "remaining": "Full rotor/motor/stator/shaft solids and native aero/performance sensitivity are not defined."},
        {"id": "off_axis_motor_with_shaft_belt_or_gear", "status": "BLOCKED",
         "planning_envelope": planning_envelope,
         "in_bore_bounds": [in_bore_motor_separation(duct_id, planning_envelope["diameter_mm"])],
         "remaining": "External mount, transmission, bearings, shafts, cooling, wires, supports, service volume, and drive losses have no sourced dimensions/evidence."},
        {"id": "two_driven_stages_per_duct", "status": "BLOCKED",
         "scenario_assumption": {"driven_rows_per_duct": two_row_count, "resulting_motor_count": reduced_motor_count},
         "component_motor_mass_delta_kg_screen_only": [-removed_motor_mass[1], -removed_motor_mass[0]],
         "motor_channel_contract": {"existing_channels": current_motors,
                                    "scenario_channels": reduced_motor_count,
                                    "unused_channels": max(0, current_motors - reduced_motor_count),
                                    "status": "FAIL" if reduced_motor_count != current_motors else "PASS"},
         "remaining": "No rotor/stator schedule, measured per-row load allocation, aero rerun, power closure, or companion ESC contract exists."},
        {"id": "shorter_direct_drive_motor_at_current_pitch", "status": "FAIL",
         "per_source_variant": dimension_variants,
         "remaining": "Every documented motor can exceeds the 36 mm stage pitch at zero clearance; the donor dimensions are not supplier-native measurements."},
    ]

    screen_facts = {
        "design_sources": {
            "parameter_register": register["sourceFiles"],
            "datum": datum["measured"],
            "rotor_station_z_mm": rotor_z,
            "rotor_pitch_mm": pitch,
            "duct_inner_diameter_mm": duct_id,
            "module_length_mm": module_length,
            "rotor_chord_mm": float(constants["ROTOR_CHORD"]),
            "motor_can_model_mm": {"diameter": model_diameter, "length": model_length,
                                   "mass_kg": float(constants["MOTOR_MASS_KG"])},
        },
        "native_motor_geometry": native,
        "motor_conflict_variants": dimension_variants,
        "motor_planning_envelope": planning_envelope,
        "shared_installed_constraints": integration_constraints,
        "alternatives": candidates,
        "unavailable_release_evidence": inputs["unavailable_release_evidence"],
    }
    report["preliminary_screen"] = screen_facts
    report["overall_status"] = "FAIL" if (native["status"] == "FAIL"
        or integration_constraints.get("actuator_channel_status") == "FAIL"
        or any(row.get("placeholder_comparison_status") == "FAIL"
               for row in integration_constraints.get("board_outlines", {}).values())) else "BLOCKED"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--arm-source-root", type=Path, default=REPO_ROOT.parent / "drone-arm",
                        help="checkout containing the exact issue-23 source bytes pinned by the input manifest")
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--json", type=Path, required=True, help="write reproducible JSON evidence to this path")
    args = parser.parse_args(argv)
    source_root = args.source_root.resolve()
    input_path = args.inputs.resolve()
    try:
        inputs = json.loads(input_path.read_text(encoding="utf-8"))
        report = run_screen(source_root, inputs, input_path, args.arm_source_root.resolve())
    except Exception as exc:
        report = {"issue": "iamdarshg/drone-mech#2", "overall_status": "FAIL",
                  "errors": [f"{type(exc).__name__}: {exc}"],
                  "claims": {"native_solver_run": False, "geometry_redesign": False,
                             "hardware_run": False, "flight_claim": False}}
    output = args.json.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"screen_id": report.get("screen_id"), "overall_status": report["overall_status"],
                      "json": str(output), "errors": report.get("errors", [])}, sort_keys=True))
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
