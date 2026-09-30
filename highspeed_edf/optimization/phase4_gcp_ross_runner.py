#!/usr/bin/env python3
"""Run the prepared ROSS cases through NativeJobManager on a GCP worker.

The worker uses the governed local NativeJobManager executor; the GCE VM is the
user-approved compute host. This is not the unprovisioned GCPBatchExecutor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def add_workbench_path(root: Path) -> None:
    for path in [root, root / "solvers", root / "services" / "api"]:
        sys.path.insert(0, str(path))
    for package in (root / "packages").glob("*"):
        if package.is_dir():
            sys.path.insert(0, str(package))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbench", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    add_workbench_path(args.workbench.resolve())
    from participants.lifecycle import NativeJobManager

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    args.job_root.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    manager = NativeJobManager(args.job_root, timeout_s=600.0)
    records: list[dict[str, Any]] = []
    try:
        for job in plan["jobs"]:
            record: dict[str, Any] = {
                "job_id_label": job["jobId"],
                "participant_id": job["participantId"],
                "design_row": job["designRow"],
                "max_speed_rpm": job["maxSpeedRpm"],
                "started_at_utc": datetime.now(UTC).isoformat(),
                "input_hash": hashlib.sha256(
                    json.dumps(job["inputs"], sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            }
            try:
                job_id = manager.submit(
                    job["participantId"],
                    job["inputs"],
                    design_id=job["jobId"],
                    analysis="campbell",
                    fidelity="beam-campbell",
                    deferred=True,
                )
                record["native_job_id"] = job_id
                state = manager.run(job_id)
                state_value = getattr(state, "value", str(state))
                record["state"] = state_value
                record["status"] = manager.status(job_id)
                record["events"] = manager.events(job_id)
                if state_value == "COMPLETED":
                    record["envelope"] = manager.envelope(job_id)
                    record["provenance"] = manager.provenance(job_id)
                    artifacts: dict[str, Any] = {}
                    case_dir = args.job_root / f"case-{job_id[:12]}"
                    for name in ("case.json", "result.json", "solver.log", "stdout.log", "stderr.log", "run_ross.py"):
                        path = case_dir / name
                        if path.is_file():
                            artifacts[name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
                    record["case_artifacts"] = artifacts
                else:
                    record["error"] = record["status"].get("error_detail")
            except Exception as exc:  # record actual failure; never make a result
                record["state"] = "DRIVER_ERROR"
                record["error"] = f"{type(exc).__name__}:{exc}"
            record["finished_at_utc"] = datetime.now(UTC).isoformat()
            records.append(record)
    finally:
        manager.close()

    evidence = {
        "study_id": "highspeed-edf",
        "phase": 4,
        "run_source": "governed-native-job-manager-local-executor-on-gce-spot-worker",
        "workbench_commit": subprocess.run(
            ["git", "-C", str(args.workbench), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "completed_count": sum(record.get("state") == "COMPLETED" for record in records),
        "records": records,
        "plan_sha256": sha256(args.plan),
    }
    out = args.output / "phase4_ross_evidence.json"
    out.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    archive = args.output / "phase4_ross_cases.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for case_dir in sorted(args.job_root.glob("case-*")):
            tar.add(case_dir, arcname=case_dir.name)
    print(json.dumps({"state": "completed-driver", "records": len(records), "completed": evidence["completed_count"], "evidence": str(out)}, default=str))
    return 0 if evidence["completed_count"] == len(records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
