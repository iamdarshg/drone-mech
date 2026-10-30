"""Source-pinned mass/CG sensitivity screen for the issue 11 camera placeholder."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(root: Path, manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = json.loads(manifest_path.read_text())
    baseline = manifest["baseline"]
    for key, hash_key in (("generator", "generator_sha256"), ("mass_csv", "mass_csv_sha256")):
        path = root / baseline[key]
        if not path.is_file() or sha256(path) != baseline[hash_key]:
            raise ValueError(f"source pin mismatch: {baseline[key]}")
    candidate = manifest["candidate"]
    snapshot = root / candidate["source_snapshot"]
    if not snapshot.is_file() or sha256(snapshot) != candidate["source_snapshot_sha256"]:
        raise ValueError(f"source pin mismatch: {candidate['source_snapshot']}")
    with (root / baseline["mass_csv"]).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    return manifest, rows


def compute(manifest: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    entries = [{"name": r["component"], "mass_kg": float(r["massKg"]),
                "x_mm": float(r["cgXmm"]), "y_mm": float(r["cgYmm"]), "z_mm": float(r["cgZmm"])} for r in rows]
    payloads = [e for e in entries if e["name"] == "payload_point_mass"]
    if len(payloads) != 1:
        raise ValueError("expected exactly one payload_point_mass row")
    legacy = payloads[0]
    if abs(legacy["mass_kg"] - manifest["assumptions"]["legacy_payload_mass_kg"]) > 1e-9:
        raise ValueError("legacy payload mass differs from pinned assumption")
    if [legacy["x_mm"], legacy["y_mm"], legacy["z_mm"]] != manifest["assumptions"]["legacy_payload_cg_mm"]:
        raise ValueError("legacy payload CG differs from pinned assumption")

    base = [e for e in entries if e is not legacy]
    base_mass = sum(e["mass_kg"] for e in base)
    base_moments = {axis: sum(e["mass_kg"] * e[f"{axis}_mm"] for e in base) for axis in "xyz"}
    source_candidate = manifest["candidate"]
    camera_mass = float(source_candidate["mass_kg"])
    camera_cg = manifest["assumptions"]["legacy_payload_cg_mm"]
    rows_out = []
    for supplemental in manifest["assumptions"]["supplemental_mass_scenarios_kg"]:
        pay_mass = camera_mass + supplemental
        total_mass = base_mass + pay_mass
        cg = {axis: (base_moments[axis] + pay_mass * camera_cg[i]) / total_mass
              for i, axis in enumerate("xyz")}
        rows_out.append({
            "scenario": f"camera_plus_{supplemental:g}kg_supplemental",
            "camera_mass_kg": camera_mass,
            "supplemental_mass_kg": supplemental,
            "combined_payload_mass_kg": pay_mass,
            "payload_mass_change_vs_legacy_kg": pay_mass - legacy["mass_kg"],
            "total_mass_kg": total_mass,
            "cg_mm": cg,
            "cg_shift_vs_legacy_mm": {axis: cg[axis] - (sum(e["mass_kg"] * e[f"{axis}_mm"] for e in entries) / sum(e["mass_kg"] for e in entries)) for axis in "xyz"},
        })
    return {
        "schema": manifest["schema"],
        "issue": manifest["issue"],
        "evidence_status": "SCREENING_ONLY_BLOCKED_FOR_INSTALLATION",
        "candidate": source_candidate,
        "source_manifest_sha256": None,
        "baseline_revision": manifest["baseline"]["revision"],
        "source_pins": {
            "mass_csv_revision": manifest["baseline"]["revision"],
            "mass_csv_sha256": manifest["baseline"]["mass_csv_sha256"],
            "generator_source_revision": manifest["baseline"].get("generator_source_revision",
                                                                  manifest["baseline"]["revision"]),
            "generator_sha256": manifest["baseline"]["generator_sha256"],
            "historical_generator_sha256": manifest["baseline"].get("historical_generator_sha256"),
        },
        "baseline_mass_kg": sum(e["mass_kg"] for e in entries),
        "baseline_cg_mm": {axis: sum(e["mass_kg"] * e[f"{axis}_mm"] for e in entries) / sum(e["mass_kg"] for e in entries) for axis in "xyz"},
        "non_payload_mass_kg": base_mass,
        "legacy_payload": {"mass_kg": legacy["mass_kg"], "cg_mm": {a: legacy[f"{a}_mm"] for a in "xyz"}},
        "scenarios": rows_out,
        "blocked_gates": [
            "payload bay/available envelope is unspecified; camera dimensions cannot be checked for fit",
            "camera location is inherited from an analyst-selected point mass, not a mounting datum",
            "mount, cable, power, thermal, vibration, hatch, and service envelopes are absent",
            "online catalog values are not independently measured or physically validated",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, default=Path.cwd())
    p.add_argument("--inputs", type=Path, default=Path("highspeed_edf/phase15/configs/payload_mass_screen_sources.json"))
    p.add_argument("--json", type=Path, default=Path("highspeed_edf/phase15/reports/issue11_payload_mass_screen.json"))
    args = p.parse_args()
    manifest, rows = load_inputs(args.source_root, args.source_root / args.inputs)
    result = compute(manifest, rows)
    result["source_manifest_sha256"] = sha256(args.source_root / args.inputs)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["evidence_status"], "baseline_mass_kg": result["baseline_mass_kg"],
                      "scenario_count": len(result["scenarios"]), "output": str(args.json)}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
