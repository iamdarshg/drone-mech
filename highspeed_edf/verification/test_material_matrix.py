"""Negative checks for the issue #4 inventory gate."""
import csv
from pathlib import Path

from highspeed_edf.verification.material_matrix import build_matrix, validate_material_record


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "highspeed_edf/phase15/optimization/phase15_generate_geometry.py"
MASS = ROOT / "highspeed_edf/deliverables/phase15_geometry/reports/mass_cg.csv"


def test_inventory_keeps_unqualified_inputs_blocked():
    result = build_matrix(GENERATOR, MASS)
    assert result["status"] == "BLOCKED"
    assert result["parts"]
    assert all(part["allowables"] is None for part in result["parts"])
    assert all(part["measured_mass_status"] == "BLOCKED_NOT_WEIGHED" for part in result["parts"])
    assert all("proposed" in part["process_provenance"] for part in result["parts"])


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
    result = build_matrix(GENERATOR, changed)
    assert result["status"] == "FAIL"
    assert any("hot-side screening class" in error for error in result["errors"])
