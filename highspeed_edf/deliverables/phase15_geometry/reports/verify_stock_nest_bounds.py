"""Native OCC check for Phase-15 sheet-stock STEP nests.

Run from the repository root:
  python highspeed_edf/deliverables/phase15_geometry/reports/verify_stock_nest_bounds.py
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import cadquery as cq
from OCP.BRepCheck import BRepCheck_Analyzer

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "stock_nests"
REPORT = ROOT / "reports" / "phase15_stock_nest_bounds_validation.json"
EDGE_MARGIN_MM = 1.0
MIN_PART_SPACING_MM = 1.5
EXACT_DISTANCE_WINDOW_MM = 1e-6
EXPECTED = {
    "sheet_A_250x120x5_36rotors_63stators.step": (250.0, 120.0, 5.0),
    "sheet_B_300x120x5_36rotors_63stators.step": (300.0, 120.0, 5.0),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record_sheet(path: Path, stock_size: tuple[float, float, float]) -> dict:
    sx, sy, sz = stock_size
    imported = cq.importers.importStep(str(path)).val()
    solids = imported.Solids()
    errors: list[str] = []
    if len(solids) != 100:
        errors.append(f"expected 100 solids (raw stock + 99 blanks), found {len(solids)}")
    raw_candidates = sorted(solids, key=lambda solid: solid.Volume(), reverse=True)
    if not raw_candidates:
        return {"path": str(path), "status": "FAIL", "errors": ["STEP contains no solids"]}
    raw = raw_candidates[0]
    raw_bb = raw.BoundingBox()
    raw_valid = bool(BRepCheck_Analyzer(raw.wrapped).IsValid()) and raw.Volume() > 0.0
    if not raw_valid:
        errors.append("raw stock is not a positive-volume valid BREP")
    raw_bounds = [raw_bb.xmin, raw_bb.ymin, raw_bb.zmin,
                  raw_bb.xmax, raw_bb.ymax, raw_bb.zmax]
    expected_bounds = [0.0, 0.0, 0.0, sx, sy, sz]
    if any(abs(a - b) > 1e-5 for a, b in zip(raw_bounds, expected_bounds)):
        errors.append(f"raw-stock bounds differ from declared sheet: {raw_bounds}")

    blanks = [solid for solid in solids if solid is not raw]
    rotor, stator, unknown = [], [], []
    blank_records = []
    for index, blank in enumerate(blanks, start=1):
        bb = blank.BoundingBox()
        dims = (bb.xmax - bb.xmin, bb.ymax - bb.ymin, bb.zmax - bb.zmin)
        if abs(dims[0] - 29.0) < 1e-3:
            kind = "rotor"
            rotor.append(blank)
        elif abs(dims[0] - 16.0) < 1e-3:
            kind = "stator"
            stator.append(blank)
        else:
            kind = "unknown"
            unknown.append(index)
        bounds = [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax]
        valid = bool(BRepCheck_Analyzer(blank.wrapped).IsValid()) and blank.Volume() > 0.0
        if not valid:
            errors.append(f"blank {index} is not a positive-volume valid BREP")
        if (bb.xmin < EDGE_MARGIN_MM - 1e-6 or bb.ymin < EDGE_MARGIN_MM - 1e-6
                or bb.xmax > sx - EDGE_MARGIN_MM + 1e-6
                or bb.ymax > sy - EDGE_MARGIN_MM + 1e-6
                or bb.zmin < -1e-6 or bb.zmax > sz + 1e-6):
            errors.append(f"blank {index} crosses stock/edge margin: {bounds}")
        blank_records.append({"index": index, "kind": kind, "bounds_mm": bounds,
                              "volume_mm3": float(blank.Volume()), "valid_brep": valid})

    if len(rotor) != 36:
        errors.append(f"expected 36 rotor blanks, found {len(rotor)}")
    if len(stator) != 63:
        errors.append(f"expected 63 stator blanks, found {len(stator)}")
    if unknown:
        errors.append(f"could not classify blank solids at indices {unknown}")

    # A bounding-box separation is a conservative lower bound on solid
    # clearance. Run exact OCC distance for all pairs at or near the specified
    # threshold, including pairs whose lower bound is exactly 1.5 mm.
    min_clearance_lower_bound = math.inf
    min_exact_threshold_distance = math.inf
    clearance_failures = []
    threshold_pairs = []
    for i, left in enumerate(blanks):
        a = left.BoundingBox()
        for j in range(i + 1, len(blanks)):
            right = blanks[j]
            b = right.BoundingBox()
            dx = max(0.0, a.xmin - b.xmax, b.xmin - a.xmax)
            dy = max(0.0, a.ymin - b.ymax, b.ymin - a.ymax)
            lower_bound = math.hypot(dx, dy)
            min_clearance_lower_bound = min(min_clearance_lower_bound, lower_bound)
            if lower_bound > MIN_PART_SPACING_MM + EXACT_DISTANCE_WINDOW_MM:
                continue
            distance = float(left.distance(right))
            threshold_pairs.append({"left_index": i + 1, "right_index": j + 1,
                                    "bbox_clearance_lower_bound_mm": lower_bound,
                                    "occ_distance_mm": distance})
            min_exact_threshold_distance = min(min_exact_threshold_distance, distance)
            if distance < MIN_PART_SPACING_MM - 1e-5:
                clearance_failures.append({"left_index": i + 1, "right_index": j + 1,
                                           "clearance_mm": distance})

    return {
        "path": str(path), "sha256": sha256(path), "tool": {
            "cadquery": __import__("importlib.metadata", fromlist=["version"]).version("cadquery"),
            "cadquery_ocp": __import__("importlib.metadata", fromlist=["version"]).version("cadquery-ocp")},
        "declared_stock_mm": list(stock_size), "edge_margin_mm": EDGE_MARGIN_MM,
        "minimum_part_spacing_mm": MIN_PART_SPACING_MM,
        "raw_stock_bounds_mm": raw_bounds, "raw_stock_valid_brep": raw_valid,
        "raw_stock_volume_mm3": float(raw.Volume()), "solid_count": len(solids),
        "blank_count": len(blanks), "rotor_count": len(rotor), "stator_count": len(stator),
        "out_of_bounds_blanks": [r for r in blank_records if any(
            e.startswith(f"blank {r['index']} crosses") for e in errors)],
        "blank_bounds_mm": blank_records,
        "clearance_check": {"exact_distance_window_mm": EXACT_DISTANCE_WINDOW_MM,
                             "pairs_exactly_checked_at_or_near_threshold": len(threshold_pairs),
                             "minimum_occ_distance_among_threshold_pairs_mm": min_exact_threshold_distance,
                             "minimum_bbox_clearance_lower_bound_mm": min_clearance_lower_bound,
                             "threshold_pair_measurements": threshold_pairs,
                             "spacing_failures": clearance_failures},
        "valid": not errors, "errors": errors,
    }


def main() -> int:
    reports = []
    for filename, size in EXPECTED.items():
        path = STOCK / filename
        if not path.is_file():
            reports.append({"path": str(path), "valid": False,
                            "errors": ["expected stock STEP is missing"]})
        else:
            reports.append(record_sheet(path, size))
    result = {"status": "PASS" if all(r.get("valid") for r in reports) else "FAIL",
              "checks": reports,
              "scope_note": "Native STEP solid validity, declared stock envelope, edge margins, blank counts, and pairwise blank clearance only; not CNC toolpath, fixture, machine, material, or fabrication qualification."}
    REPORT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "report": str(REPORT),
                      "sheets": [{"name": Path(r["path"]).name, "valid": r.get("valid"),
                                  "blank_count": r.get("blank_count"),
                                  "rotor_count": r.get("rotor_count"),
                                  "stator_count": r.get("stator_count"),
                                  "pairs_exactly_checked_at_or_near_threshold": r.get("clearance_check", {}).get("pairs_exactly_checked_at_or_near_threshold"),
                                  "minimum_occ_distance_among_threshold_pairs_mm": r.get("clearance_check", {}).get("minimum_occ_distance_among_threshold_pairs_mm"),
                                  "minimum_bbox_clearance_lower_bound_mm": r.get("clearance_check", {}).get("minimum_bbox_clearance_lower_bound_mm"),
                                  "errors": r.get("errors")} for r in reports]}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
