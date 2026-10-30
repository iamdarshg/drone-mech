"""Negative checks for the issue #4 inventory gate."""
import csv
import contextlib
import io
import json
from pathlib import Path

from highspeed_edf.verification.material_matrix import (
    build_matrix, main, validate_material_record, _verify_source_pins,
    _check_pinned_sources, sha256,
)


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "highspeed_edf/phase15/optimization/phase15_generate_geometry.py"
MASS = ROOT / "highspeed_edf/deliverables/phase15_geometry/reports/mass_cg.csv"


def test_inventory_keeps_unqualified_inputs_blocked():
    result = build_matrix(GENERATOR, MASS)
    assert result["status"] == "BLOCKED"
    assert result["parts"]
    assert result["source_row_count"] == result["mapped_row_count"] == len(result["parts"]) == 74
    assert all(part["allowables"] is None for part in result["parts"])
    assert all(part["measured_mass_status"].startswith("BLOCKED") for part in result["parts"])
    assert all("proposed" in part["process_provenance"] or part["material_label"] == "not-geometrized" for part in result["parts"])
    payload = next(part for part in result["parts"] if part["material_label"] == "not-geometrized")
    assert payload["material_scope"] == "excluded_from_material_property_validation"
    assert payload["exclusion_reason"]


def test_material_validator_rejects_missing_and_negative_properties():
    assert "nominal_density_kg_m3 must be a finite positive number" in validate_material_record({})
    assert "nominal_density_kg_m3 must be a finite positive number" in validate_material_record({"nominal_density_kg_m3": -1})
    missing = validate_material_record({"nominal_density_kg_m3": 1000})
    assert "property tensile_strength_mpa is missing" in missing
    assert "property modulus_mpa is missing" in missing
    assert "property tensile_strength_mpa is missing" in validate_material_record(
        {"nominal_density_kg_m3": 1000, "properties": {"tensile_strength_mpa": None}}
    )
    assert "property modulus_mpa must be finite and positive" in validate_material_record(
        {"nominal_density_kg_m3": 1000, "properties": {"modulus_mpa": -2}}
    )


def test_hot_side_screen_rejects_incompatible_material(tmp_path):
    with MASS.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        fields = rows[0].keys()
    hot_side_part = next(row for row in rows if row["component"].startswith("duct_"))
    hot_side_part["material"] = "PLA-core-CF-wrap"
    changed = tmp_path / "mass.csv"
    with changed.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = build_matrix(GENERATOR, changed, enforce_pins=False)
    assert result["status"] == "FAIL"
    assert any("hot-side screening class" in error for error in result["errors"])


def test_stale_and_missing_source_statuses_are_distinct(tmp_path):
    pins = json.loads((ROOT / "highspeed_edf/verification/material_sources.json").read_text())
    actual = {
        "highspeed_edf/phase15/optimization/phase15_generate_geometry.py": sha256(GENERATOR),
        "highspeed_edf/deliverables/phase15_geometry/reports/mass_cg.csv": sha256(MASS),
    }
    pins["sources"]["highspeed_edf/phase15/optimization/phase15_generate_geometry.py"] = "0" * 64
    errors, status = _check_pinned_sources(actual, pins["sources"])
    assert status == "FAIL"
    assert any("stale material source" in error for error in errors)

    _, errors, status = _verify_source_pins(GENERATOR, tmp_path / "absent.csv")
    assert status == "BLOCKED"
    assert errors == ["one or more required material inputs are absent"]


def test_mandatory_blocked_inventory_has_nonzero_cli_exit():
    output = io.StringIO()
    args = ["--generator", str(GENERATOR), "--mass-csv", str(MASS)]
    with contextlib.redirect_stdout(output):
        result = main(args)
    assert json.loads(output.getvalue())["status"] == "BLOCKED"
    assert result == 1

    output = io.StringIO()
    args[3] = str(ROOT / "absent-material-source.csv")
    with contextlib.redirect_stdout(output):
        result = main(args)
    missing = json.loads(output.getvalue())
    assert missing["status"] == "BLOCKED"
    assert "absent" in missing["errors"][0]
    assert result == 1
