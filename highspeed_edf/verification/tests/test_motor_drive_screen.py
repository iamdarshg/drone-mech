"""Adversarial checks for the source-pinned issue-2 bounds screen."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import cadquery as cq
import pytest

from highspeed_edf.verification.motor_drive_screen import (
    DEFAULT_INPUTS,
    git_blob_provenance,
    in_bore_motor_separation,
    overlap_bound,
    parse_motor_source_variants,
    read_generator_constants,
    run_screen,
    validate_inputs,
    verify_local_sources,
)
from highspeed_edf.verification.native_adapters import (
    aabb_intersection_volume,
    import_step,
    motor_bbox_collision,
)

REPO = Path(__file__).resolve().parents[3]
ARM_ROOT = Path(os.environ.get("DRONE_ARM_SOURCE_ROOT", REPO.parent / "drone-arm"))


def _inputs() -> dict:
    return json.loads(DEFAULT_INPUTS.read_text(encoding="utf-8"))


def test_end_to_end_screen_reimports_baseline_and_source_pinned_interfaces():
    report = run_screen(REPO, _inputs(), DEFAULT_INPUTS, ARM_ROOT)
    screen = report["preliminary_screen"]
    integration = screen["shared_installed_constraints"]
    assert report["overall_status"] == "FAIL"
    assert report["source_integrity"]["status"] == "PASS"
    assert screen["native_motor_geometry"]["pairs_checked"] == 15
    assert screen["native_motor_geometry"]["collision_count"] == 6
    assert sum(bool(pair["collides"]) for pair in screen["native_motor_geometry"]["pair_measurements"]) == 6
    assert [(v["id"], v["zero_clearance_axial_overlap_mm"])
            for v in screen["motor_conflict_variants"]] == [
                ("phase15_generated_can", 36.0),
                ("issue2_text_claim", 36.0),
                ("donor_3670_note", 34.0),
                ("donor_3660_note", 24.0),
            ]
    assert integration["board_outlines"]["main"]["measured_edge_centerline_mm"] == [140.0, 100.0]
    assert integration["board_outlines"]["esc"]["measured_edge_centerline_mm"] == [173.8, 282.93]
    assert integration["board_outlines"]["main"]["placeholder_comparison_status"] == "PASS"
    assert integration["board_outlines"]["esc"]["placeholder_comparison_status"] == "FAIL"
    assert integration["distinct_pwm_count"] == 6
    assert integration["independent_effector_count_from_mech_native_audit"] == 7
    assert integration["component_solid_heights"].startswith("BLOCKED")
    assert integration["integrated_board_fit_status"].startswith("BLOCKED")
    assert report["candidate_ranking"] == "NOT_APPLICABLE"
    assert report["claims"] == {
        "native_solver_run": False,
        "geometry_redesign": False,
        "hardware_run": False,
        "flight_claim": False,
        "overall_evidence_class": "PRELIMINARY ANALYTICAL BOUNDS",
    }


def test_obb_positive_but_occ_boolean_disjoint_is_not_a_false_collision(tmp_path: Path):
    """Two spheres have overlapping AABBs but are disjoint under exact OCC Boolean."""
    first = cq.Solid.makeSphere(1.0, cq.Vector(0.0, 0.0, 0.0))
    second = cq.Solid.makeSphere(1.0, cq.Vector(1.5, 1.5, 0.0))
    first_path, second_path = tmp_path / "first.step", tmp_path / "second.step"
    cq.exporters.export(first, str(first_path))
    cq.exporters.export(second, str(second_path))
    first_record, second_record = import_step(first_path), import_step(second_path)
    a = first_record["solids"][0]["bbox_mm"]
    b = second_record["solids"][0]["bbox_mm"]
    assert aabb_intersection_volume(a, b) > 0.0
    result = motor_bbox_collision([first_record, second_record])
    assert result["pairs_checked"] == 1
    assert result["pairs"][0]["exact_intersection_mm3"] == pytest.approx(0.0, abs=1e-9)
    assert result["pairs"][0]["measured_clearance_mm"] > 0.0
    assert result["collisions"] == []
    assert result["status"] == "PASS"


def test_exact_touching_length_is_not_reported_as_positive_overlap():
    assert overlap_bound(36.0, 36.0)["zero_clearance_axial_overlap_mm"] == 0.0
    assert overlap_bound(36.01, 36.0)["zero_clearance_axial_overlap_mm"] == pytest.approx(0.01)
    with pytest.raises(ValueError):
        overlap_bound(-1.0, 36.0)


def test_in_bore_bound_separates_model_conflict_from_oem_variant():
    model = in_bore_motor_separation(78.0, 42.0)
    donor = in_bore_motor_separation(78.0, 36.0)
    assert model["maximum_center_separation_within_bore_mm"] == 36.0
    assert model["minimum_center_separation_for_nonoverlap_mm"] == 42.0
    assert model["necessary_cross_section_bound"] == "FAIL"
    assert donor["maximum_center_separation_within_bore_mm"] == 42.0
    assert donor["necessary_cross_section_bound"] == "PASS"
    assert donor["assumption"].startswith("both equal motor cans")


def test_motor_variants_are_parsed_from_pinned_sources_not_input_numbers():
    constants = read_generator_constants(REPO / "highspeed_edf/phase15/optimization/phase15_generate_geometry.py")
    variants = parse_motor_source_variants(REPO, _inputs(), constants)
    assert [(v["id"], v["diameter_mm"], v["can_length_mm"]) for v in variants] == [
        ("phase15_generated_can", 42.0, 72.0),
        ("issue2_text_claim", 36.0, 72.0),
        ("donor_3670_note", 36.0, 70.0),
        ("donor_3660_note", 36.0, 60.0),
    ]
    assert variants[0]["modeled_stub"]["interpretation"].endswith("not an identified supplier shaft diameter")
    assert variants[2]["shaft_diameter_mm_secondary_claim"] == 5.0
    assert "not independently measured" in variants[2]["evidence_class"]


def test_pinned_source_tampering_fails_closed(tmp_path: Path):
    inputs = _inputs()
    for row in inputs["baseline"]["local_sources"]:
        source = REPO / row["path"]
        dest = tmp_path / row["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    for name in inputs["baseline"]["native_motor_step_sha256"]:
        source = REPO / "highspeed_edf/deliverables/phase15_geometry/step" / name
        dest = tmp_path / "highspeed_edf/deliverables/phase15_geometry/step" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    mutated = tmp_path / inputs["external_sources"]["issue2_text_snapshot_path"]
    mutated.write_text(mutated.read_text(encoding="utf-8").replace("36×72", "36×71"), encoding="utf-8")
    result = verify_local_sources(tmp_path, inputs)
    assert result["status"] == "FAIL"
    assert any("drone-mech-issue-2.md" in error for error in result["errors"])


def test_missing_native_motor_part_fails_closed(tmp_path: Path):
    inputs = _inputs()
    for row in inputs["baseline"]["local_sources"]:
        source = REPO / row["path"]
        dest = tmp_path / row["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    names = sorted(inputs["baseline"]["native_motor_step_sha256"])
    for name in names[:-1]:
        source = REPO / "highspeed_edf/deliverables/phase15_geometry/step" / name
        dest = tmp_path / "highspeed_edf/deliverables/phase15_geometry/step" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    result = verify_local_sources(tmp_path, inputs)
    assert result["status"] == "BLOCKED"
    assert any("expected six pinned motor STEP files, found 5" in error for error in result["errors"])


def test_external_board_blob_mutation_is_rejected():
    inputs = _inputs()
    ext = inputs["external_sources"]
    main_path = ext["arm_source_files"]["main_pcb"]
    expected = ext["arm_expected_git_blob_sha1"][main_path]
    good = git_blob_provenance(ARM_ROOT, ext["arm_source_revision"], main_path, expected)
    forged_pin = git_blob_provenance(ARM_ROOT, ext["arm_source_revision"], main_path, "0" * 40)
    assert good["status"] == "PASS"
    assert forged_pin["status"] == "FAIL"


def test_external_worktree_board_mutation_is_rejected(tmp_path: Path):
    source_root = tmp_path / "arm-source"
    board = source_root / "hardware/main/rev_b/main_rev_b.kicad_pcb"
    board.parent.mkdir(parents=True)
    board.write_text("(kicad_pcb (version 1))\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source_root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(source_root), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source_root), "config", "user.name", "Source mutation fixture"], check=True)
    subprocess.run(["git", "-C", str(source_root), "add", str(board)], check=True)
    subprocess.run(["git", "-C", str(source_root), "commit", "-qm", "pinned board fixture"], check=True)
    revision = subprocess.run(["git", "-C", str(source_root), "rev-parse", "HEAD"],
                              check=True, text=True, capture_output=True).stdout.strip()
    blob = subprocess.run(["git", "-C", str(source_root), "rev-parse", f"{revision}:hardware/main/rev_b/main_rev_b.kicad_pcb"],
                          check=True, text=True, capture_output=True).stdout.strip()
    assert git_blob_provenance(source_root, revision, "hardware/main/rev_b/main_rev_b.kicad_pcb", blob)["status"] == "PASS"
    board.write_text(board.read_text(encoding="utf-8") + "(net 1)\n", encoding="utf-8")
    changed = git_blob_provenance(source_root, revision, "hardware/main/rev_b/main_rev_b.kicad_pcb", blob)
    assert changed["status"] == "FAIL"


def test_invalid_units_or_missing_source_declaration_fail_validation():
    inputs = _inputs()
    inputs["units"] = "in"
    assert any("declare mm" in error for error in validate_inputs(inputs))
    inputs = _inputs()
    del inputs["external_sources"]["arm_expected_git_blob_sha1"]
    assert any("arm_expected_git_blob_sha1" in error for error in validate_inputs(inputs))
