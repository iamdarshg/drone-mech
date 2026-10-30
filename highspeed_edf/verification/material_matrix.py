"""Source-pinned, provenance-preserving material/process inventory for issue #4.

This is an inventory and screening gate only. Generator labels and nominal
density values are design inputs; they are not supplier allowables, laminate
properties, thermal limits, or measured part masses.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_material_record(record: dict, required_properties=("tensile_strength_mpa", "modulus_mpa")) -> list[str]:
    """Reject absent/non-positive nominal density and malformed property values."""
    errors = []
    density = record.get("nominal_density_kg_m3")
    if isinstance(density, bool) or not isinstance(density, (int, float)) or not math.isfinite(density) or density <= 0:
        errors.append("nominal_density_kg_m3 must be a finite positive number")
    properties = record.get("properties", {})
    if not isinstance(properties, dict):
        errors.append("properties must be an object")
    else:
        for name in required_properties:
            if properties.get(name) is None:
                errors.append(f"property {name} is missing")
        for name, value in properties.items():
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0):
                errors.append(f"property {name} must be finite and positive")
    return errors


def _declared_densities(generator: Path) -> dict:
    """Read only the literal density register from the reviewed generator."""
    import ast
    tree = ast.parse(generator.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "MATERIAL_DENSITY_KG_M3"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict):
                raise ValueError("MATERIAL_DENSITY_KG_M3 is not a mapping")
            return value
    raise ValueError("generator has no literal MATERIAL_DENSITY_KG_M3 register")


def build_matrix(generator: Path, mass_csv: Path) -> dict:
    densities = _declared_densities(generator)
    with mass_csv.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    required = {"component", "material", "basis", "note"}
    if not rows or not required.issubset(rows[0]):
        return {"status": "FAIL", "errors": ["mass table is empty or lacks component/material/basis/note columns"], "parts": []}

    parts, errors, missing_materials = [], [], set()
    seen = set()
    for row in rows:
        name, material = row["component"].strip(), row["material"].strip()
        if not name or name in seen:
            errors.append(f"missing or duplicate component ID: {name!r}")
            continue
        seen.add(name)
        if material == "not-geometrized":
            continue
        density = densities.get(material)
        if density is None:
            missing_materials.add(material)
            errors.append(f"{name}: material {material!r} has no declared density")
        elif isinstance(density, bool) or not isinstance(density, (int, float)) or not math.isfinite(density) or density <= 0:
            errors.append(f"{name}: material {material!r} has invalid nominal density")

        # Hot-side classification is a conservative name-based gate for the
        # explicitly duct/EDF path. It does not assert an operating temperature.
        hot_side = name.startswith(("duct_", "six_hot_side_"))
        if hot_side and material in {"PLA-core-CF-wrap", "carbon-rod", "servo-envelope"}:
            errors.append(f"{name}: {material!r} is incompatible with the hot-side screening class")

        parts.append({
            "component": name,
            "material_label": material,
            "part_label_provenance": "source_mass_table",
            "part_label_source": str(mass_csv),
            "nominal_density_kg_m3": density,
            "density_provenance": "generator_nominal_design_input" if density is not None else "missing",
            "process_proposal": _process_proposal(material),
            "process_provenance": "proposed_from_issue4_intent_or_generator_label",
            "hot_side_screen": "hot_side_candidate" if hot_side else "not_classified_hot_side",
            "allowables": None,
            "layup_and_coupon_status": "BLOCKED_MISSING",
            "temperature_and_adhesive_status": "BLOCKED_MISSING",
            "measured_mass_status": "BLOCKED_NOT_WEIGHED",
        })

    sources = {str(path): sha256(path) for path in (generator, mass_csv)}
    unresolved = [
        "supplier identity and batch/condition for each structural material",
        "printed core/mold/mandrel material choice and whether retained or removed",
        "fiber grade, fabric/UD product, orientation, ply count and cured fiber fraction",
        "resin system, cure schedule and maximum qualified exposure temperature",
        "bondline adhesive, surface preparation, fastener and insert specification",
        "hot-side temperature history, thermal gradients and local temperature limits",
        "orthotropic allowables and environmental knockdowns from supplier or coupons",
        "coupon and joint acceptance criteria/results; measured component and assembly masses",
        "process traveler, printer/stock limits, inspection plan and rejection limits",
    ]
    status = "FAIL" if errors else "BLOCKED"
    return {
        "schema_version": 1,
        "requirement": "drone-mech#4",
        "status": status,
        "source_sha256": sources,
        "provenance_note": "Declared labels/densities are design inputs; proposals are not sourced qualifications; no physical measurements are present.",
        "materials_used": sorted({part["material_label"] for part in parts}),
        "parts": parts,
        "unresolved_gates": unresolved,
        "errors": errors,
    }


def _process_proposal(material: str) -> str:
    proposals = {
        "PLA-core-CF-wrap": "proposed_printed_core_with_carbon_skin; retained_vs_removed_unknown",
        "high-temp-CF-composite": "proposed_carbon_composite_shell_or_duct; print/tooling/layup route unknown",
        "6061-T6": "proposed_machined_or_sheet_6061_T6; temper and process records unverified",
        "carbon-rod": "proposed_carbon_rod_reinforcement; product and bond route unknown",
    }
    return proposals.get(material, "process_unspecified")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generator", type=Path, required=True)
    parser.add_argument("--mass-csv", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    result = build_matrix(args.generator, args.mass_csv)
    blob = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(blob, encoding="utf-8")
    print(blob, end="")
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
