#!/usr/bin/env python3
"""Summarize the downloaded, evidence-gated Phase-4 ROSS Campbell receipts."""

from __future__ import annotations

import csv
import json
import tarfile
from pathlib import Path
from typing import Any


def main() -> None:
    study = Path(__file__).resolve().parents[1]
    results = study / "results"
    evidence = json.loads((results / "phase4_ross_evidence.json").read_text(encoding="utf-8"))
    phase3_rows = list(csv.DictReader((results / "phase3_meanline_rows.csv").open(newline="", encoding="utf-8")))
    phase3_ranges: dict[str, list[float]] = {}
    for row in phase3_rows:
        if row["row_kind"] != "rotor":
            continue
        phase3_ranges.setdefault(row["row_id"], []).append(float(row["rotor_rpm"]))

    ross_results: dict[str, dict[str, Any]] = {}
    with tarfile.open(results / "phase4_ross_cases.tar.gz", "r:gz") as archive:
        for member in archive.getmembers():
            if member.name.endswith("/result.json"):
                payload = json.load(archive.extractfile(member))
                case_name = member.name.split("/")[0]
                ross_results[case_name] = payload

    rows: list[dict[str, Any]] = []
    notes: list[str] = []
    for record in evidence["records"]:
        stage = record["design_row"]
        env = record.get("envelope", {})
        scalar = env.get("scalars", {})
        critical = float(scalar.get("first_critical_rpm", 0.0))
        rpm_range = phase3_ranges.get(stage, [])
        rpm_low = min(rpm_range) if rpm_range else 0.0
        rpm_high = max(rpm_range) if rpm_range else float(record["max_speed_rpm"])
        native_job_id = record.get("native_job_id", "")
        case_payload = ross_results.get(f"case-{native_job_id[:12]}", {})
        separation = case_payload.get("forcing_separation", {})
        lines = separation.get("lines", [])
        nearest = min(lines, key=lambda item: float(item.get("margin_hz", float("inf"))), default={})
        envelope_artifacts = {
            item["name"]: item["sha256"] for item in env.get("artifacts", [])
        }
        provenance_mismatches: list[str] = []
        for event in record.get("provenance", []):
            if event.get("event_type") != "native.result-recorded":
                continue
            for artifact in event.get("artifacts", []):
                name = Path(str(artifact.get("uri", ""))).name
                expected_hash = envelope_artifacts.get(name)
                if expected_hash and artifact.get("sha256") != expected_hash:
                    provenance_mismatches.append(name)
        first_crossing_in_runup = bool(critical > 0 and critical < rpm_high)
        row = {
            "stage": stage,
            "state": record.get("state"),
            "source": env.get("source"),
            "solver_version": env.get("solver_version"),
            "first_critical_rpm": critical,
            "phase3_rotor_rpm_min": rpm_low,
            "phase3_rotor_rpm_max": rpm_high,
            "critical_below_steady_operating_range": bool(critical and critical < rpm_low),
            "critical_crossed_during_acceleration": first_crossing_in_runup,
            "ross_sampled_min_forcing_separation_hz": float(scalar.get("min_forcing_separation_hz", float("nan"))),
            "closest_sampled_forcing_label": nearest.get("label"),
            "closest_sampled_forcing_speed_rpm": nearest.get("at_speed_rpm"),
            "closest_sampled_forcing_margin_hz": nearest.get("margin_hz"),
            "provenance_artifact_hash_mismatches": json.dumps(sorted(set(provenance_mismatches))),
            "validity_passed": env.get("validity", {}).get("passed"),
            "native_job_id": record.get("native_job_id"),
            "run_id": env.get("run_id"),
            "provenance_id": env.get("provenance_id"),
        }
        rows.append(row)
        notes.append(
            f"{stage}: first critical {critical:.0f} rpm; Phase-3 steady schedule {rpm_low:.0f}–{rpm_high:.0f} rpm; "
            f"ROSS sampled nearest forcing {nearest.get('label')} at {float(nearest.get('at_speed_rpm',0)):.0f} rpm, "
            f"margin {float(nearest.get('margin_hz',float('nan'))):.2f} Hz."
        )

    with (results / "phase4_ross_review.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    table = [
        "| Stage | First critical | Steady rotor RPM range | Critical on startup ramp? | Closest ROSS sampled forcing | Margin |",
        "|---|---:|---:|---|---|---:|",
    ]
    for row in rows:
        table.append(
            f"| {row['stage']} | {row['first_critical_rpm']:.0f} rpm | "
            f"{row['phase3_rotor_rpm_min']:.0f}–{row['phase3_rotor_rpm_max']:.0f} rpm | "
            f"{'Yes' if row['critical_crossed_during_acceleration'] else 'No'} | "
            f"{row['closest_sampled_forcing_label']} at {float(row['closest_sampled_forcing_speed_rpm'] or 0):.0f} rpm | "
            f"{float(row['closest_sampled_forcing_margin_hz'] or 0):.2f} Hz |"
        )
    provenance_mismatch_names = sorted({
        name
        for row in rows
        for name in json.loads(row["provenance_artifact_hash_mismatches"])
    })
    provenance_text = (
        "The phase-4 review found a provenance artifact-hash name mismatch in the workbench output map: "
        + ", ".join(provenance_mismatch_names)
        + ". The native envelope hashes match the independently observed case-file hashes, but the `native.result-recorded` event associates the run_ross.py/result.json hashes with the opposite filenames. Treat those provenance references as a workbench publication bug to fix before relying on artifact-to-provenance link resolution."
        if provenance_mismatch_names
        else "Envelope artifact hashes match their provenance references."
    )
    report = [
        "# Phase 4 ROSS Campbell review",
        "",
        f"**Evidence:** governed `{evidence['records'][0]['envelope']['source']}` envelopes; ROSS {evidence['records'][0]['envelope']['solver_version']}; workbench commit `{evidence['workbench_commit']}`. Three stage cases completed on one Spot GCE worker.",
        "",
        *table,
        "",
        "## Engineering interpretation",
        "",
        "All three assumed rotor assemblies produce a first critical near 18,433 rpm, below the Phase-3 steady rotor schedules but inside the 0-to-operating-speed acceleration ramp. Treat this as a startup resonance crossing that requires a controlled run-up/response check or a stiffness/mass/support redesign; do not interpret it as safe merely because the ROSS participant validity envelope passed.",
        "",
        "ROSS's declared-forcing scan reports nearest sampled-line margins. It samples the Campbell speed sweep at 41 points; the 1× synchronous line necessarily intersects a critical speed, and that continuous crossing is not represented by the sampled minimum margin. R3's 3.09 Hz sampled margin is a watch item (the participant uses 5 Hz warning / 2 Hz critical thresholds).",
        "",
        provenance_text,
        "",
        "The beam plausibility check estimates a first critical near 204 krpm, over 11× higher than the ROSS bearing/disk model. Although inside the workbench's deliberately broad factor-50 plausibility band, this large spread makes the assumed shaft, bearing stiffness and equivalent disk mass dominant uncertainties. FA4119/output-bearing CAD and measured support stiffness are needed to refine the model.",
        "",
        "The current ROSS result supplies critical speeds and forcing separation but no full Campbell-curve artifact or forced-response amplitude. Gear-mesh orders, rolling-bearing frequencies, blade modes/stress, containment and left/right structural coupling were not modeled. No forced-response job was included because measured unbalance amplitude is unavailable.",
        "",
        "## GCP cost and cleanup",
        "",
        "The single Spot VM ran from about 18:55:37 to 19:00:48 UTC (about 5.2 minutes). At the conservative $0.10/hour reference rate this is about **0.9¢ compute**, below the 10¢ target and 12¢ ceiling; this is an estimate, not the billing invoice. The VM was explicitly deleted after evidence retrieval; temporary plan/runner objects were removed. Evidence objects remain in the GCS bucket and local results.",
        "",
        "## Artifacts",
        "",
        "- `results/phase4_ross_evidence.json` — envelopes, hashes, provenance chains.",
        "- `results/phase4_ross_cases.tar.gz` — case/result/run-script/solver-log artifacts.",
        "- `results/phase4_ross_review.csv` — compact per-stage review table.",
        "- `reports/phase4-prejob-brief.md` — pre-run purpose/cost/assumptions.",
    ]
    (study / "reports" / "phase4-ross-review.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("Wrote results/phase4_ross_review.csv and reports/phase4-ross-review.md")


if __name__ == "__main__":
    main()
