#!/usr/bin/env python3
"""Preflight and, when explicitly requested, run one cost-capped Phase-13 Spot VM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PHASE = Path(__file__).resolve().parents[1]
EDF_ROOT = PHASE.parent
CONFIG_PATH = PHASE / "configs" / "phase13_split_inlet_recovery.json"
RESULTS = PHASE / "results"
STARTUP = PHASE / "optimization" / "phase13_worker_startup.sh"
UTC = timezone.utc


def now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None = None) -> str:
    return (value or now()).isoformat()


def run(args: list[str], timeout: int = 30, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    command: list[str] | str = args
    use_shell = False
    if os.name == "nt" and args and args[0] == "gcloud":
        if not re.fullmatch(r"[A-Za-z0-9._:-]+", next(
                (arg.split("=", 1)[1] for arg in args if arg.startswith("--project=")), "local"
        )):
            raise ValueError("invalid GCP project identifier")
        command = subprocess.list2cmdline(args)
        use_shell = True
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=False, shell=use_shell
    )
    if result.returncode and not allow_fail:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout={result.stdout[-4000:]}\nstderr={result.stderr[-4000:]}"
        )
    return result


def gcloud_json(args: list[str], timeout: int = 30) -> dict[str, Any]:
    result = run(["gcloud", *args, "--format=json", "--quiet"], timeout=timeout)
    return json.loads(result.stdout or "{}")


def parse_gcloud_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def cost_breakdown(cfg: dict[str, Any]) -> dict[str, float]:
    budget = cfg["cloudBudget"]
    seconds = int(budget["maxRunDurationSeconds"])
    compute = seconds / 3600.0 * float(budget["conservativeComputeRateUsdPerHour"])
    max_bytes = int(budget["maximumWorkerArtifactBytes"])
    internet_egress = max_bytes / 1_000_000_000.0 * 0.12
    ipv4 = seconds / 3600.0 * 0.005
    boot_disk = 12.0 * 0.04 * seconds / (30.0 * 24.0 * 3600.0)
    temp_storage_and_operations = 0.00005
    ancillary_modeled = internet_egress + ipv4 + boot_disk + temp_storage_and_operations
    return {
        "computeMaximumUsd": round(compute, 8),
        "artifactInternetEgressMaximumUsd": round(internet_egress, 8),
        "ephemeralIpv4MaximumUsd": round(ipv4, 8),
        "bootDiskMaximumUsd": round(boot_disk, 8),
        "temporaryGcsAndApiAllowanceUsd": round(temp_storage_and_operations, 8),
        "ancillaryModeledUsd": round(ancillary_modeled, 8),
        "ancillaryAllowanceUsd": float(budget["ancillaryAllowanceUsd"]),
        "ancillaryHeadroomUsd": round(float(budget["ancillaryAllowanceUsd"]) - ancillary_modeled, 8),
        "maximumNewEstimateUsd": float(budget["aggregateEstimateUsd"]),
        "cumulativeMaximumEstimateUsd": (
            float(budget["priorEstimatedEnvelopeUsd"]) + float(budget["aggregateEstimateUsd"])
        ),
    }


def local_gates(cfg: dict[str, Any]) -> dict[str, Any]:
    preflight_path = RESULTS / "phase13_preflight.json"
    matrix_path = RESULTS / "phase13_case_matrix.csv"
    if not preflight_path.is_file() or not matrix_path.is_file():
        raise FileNotFoundError("run the Phase-13 local case generator before cloud preflight")
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    rows = list(__import__("csv").DictReader(matrix_path.open(encoding="utf-8", newline="")))
    case_ids = [item["id"] for item in cfg["cases"]]
    row_by_id = {row["caseId"]: row for row in rows}
    cases_ok = len(rows) == len(case_ids) and all(
        case_id in row_by_id
        and row_by_id[case_id]["localDictionaryStaticCheckPass"].lower() == "true"
        and row_by_id[case_id]["projectedAreaGatePass"].lower() == "true"
        and float(row_by_id[case_id]["minSICN"]) >= float(cfg["mesh"]["minimumSICN"])
        and int(row_by_id[case_id]["volumeCells"]) >= int(cfg["mesh"]["minimumCells"])
        and (PHASE / "cases" / case_id / "mesh.msh").is_file()
        for case_id in case_ids
    )
    cost = cost_breakdown(cfg)
    return {
        "preflightStatus": preflight.get("status"),
        "caseCount": len(rows),
        "allLocalMeshDictionaryAndAreaGatesPass": cases_ok,
        "localOpenFOAMCheckMeshAvailable": preflight.get("localToolAvailability", {}).get("checkMeshOnPath"),
        "localCheckMeshIsNotALaunchPrerequisite": True,
        "allCompleteProjectionAreasBelow75Cm2": all(
            float(row["completeProjectedAreaCm2"]) < float(cfg["projectedAreaGate"]["maximumCm2"])
            for row in rows
        ),
        "costBreakdown": cost,
        "costEstimatePass": (
            cost["ancillaryHeadroomUsd"] >= 0.0
            and cost["maximumNewEstimateUsd"] <= float(cfg["cloudBudget"]["approvedNewEnvelopeUsd"])
            and cost["cumulativeMaximumEstimateUsd"] <= float(cfg["cloudBudget"]["approvedTotalEnvelopeUsd"])
        ),
    }


def cloud_gates(cfg: dict[str, Any], project: str) -> dict[str, Any]:
    budget = cfg["cloudBudget"]
    billing = gcloud_json(["beta", "billing", "projects", "describe", project])
    enabled_apis = run([
        "gcloud", "services", "list", "--enabled", f"--project={project}",
        "--format=value(config.name)", "--quiet",
    ], timeout=30).stdout.splitlines()
    machine = gcloud_json([
        "compute", "machine-types", "describe", budget["machineType"],
        f"--zone={budget['zone']}",
    ])
    zone = gcloud_json(["compute", "zones", "describe", budget["zone"]])
    active_phase_instances = run([
        "gcloud", "compute", "instances", "list", f"--project={project}",
        "--filter=labels.phase=13 AND status=RUNNING", "--format=value(name)", "--quiet",
    ], timeout=30).stdout.splitlines()
    needed = {"compute.googleapis.com", "storage.googleapis.com"}
    return {
        "projectId": project,
        "billingEnabled": bool(billing.get("billingEnabled")),
        "billingAccountName": billing.get("billingAccountName"),
        "requiredApisEnabled": sorted(needed.intersection(enabled_apis)) == sorted(needed),
        "enabledApis": sorted(needed.intersection(enabled_apis)),
        "machineType": machine.get("name"),
        "machineVcpus": machine.get("guestCpus"),
        "machineMemoryMb": machine.get("memoryMb"),
        "zoneStatus": zone.get("status"),
        "existingRunningPhase13Instances": active_phase_instances,
        "gceMaxRunDurationSupportedByCli": True,
        "boundedResourceSpec": {
            "machineType": budget["machineType"],
            "provisioningModel": budget["provisioningModel"],
            "zone": budget["zone"],
            "maxRunDurationSeconds": budget["maxRunDurationSeconds"],
            "terminationAction": budget["terminationAction"],
            "bootDiskGb": budget["bootDiskGb"],
            "bootDiskAutoDelete": budget["bootDiskAutoDelete"],
            "sameRegionGcsBucket": "us-central1",
            "maxInternetEgressArtifactBytes": budget["maximumWorkerArtifactBytes"],
        },
    }


def package_worker(cfg: dict[str, Any]) -> tuple[Path, int, str]:
    package_dir = PHASE / "packages"
    package_dir.mkdir(parents=True, exist_ok=True)
    bundle = package_dir / "phase13_worker_bundle.tar.gz"
    include = [
        PHASE / "configs" / "phase13_split_inlet_recovery.json",
        PHASE / "optimization" / "phase13_openfoam_worker.py",
        *(PHASE / "cases" / item["id"] for item in cfg["cases"]),
    ]
    with tarfile.open(bundle, "w:gz", compresslevel=6) as archive:
        for source in include:
            if not source.exists():
                raise FileNotFoundError(f"worker package input missing: {source}")
            if source.is_dir():
                for path in sorted(source.rglob("*")):
                    if path.is_file() and "__pycache__" not in path.parts:
                        archive.add(path, arcname=path.relative_to(PHASE.parent))
            else:
                archive.add(source, arcname=source.relative_to(PHASE.parent))
    size = bundle.stat().st_size
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    if size > int(cfg["cloudBudget"]["maximumWorkerArtifactBytes"]):
        raise RuntimeError(
            f"worker bundle is {size} bytes, over the 15 MB egress/artifact cap; no launch"
        )
    return bundle, size, digest


def ensure_safe_extract(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    base = destination.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            if target != base and base not in target.parents:
                raise RuntimeError(f"unsafe worker archive member path: {member.name}")
        archive.extractall(destination)


def update_cost_receipt(cfg: dict[str, Any], vm_duration_s: float | None,
                        status: str, actual_billing: float | None = None) -> dict[str, Any]:
    plan = json.loads((RESULTS / "phase13_cost_plan.json").read_text(encoding="utf-8"))
    rate = float(cfg["cloudBudget"]["conservativeComputeRateUsdPerHour"])
    compute = max(0.0, vm_duration_s or 0.0) / 3600.0 * rate
    ancillary_reserved = float(cfg["cloudBudget"]["ancillaryAllowanceUsd"])
    plan.update({
        "status": status,
        "observedVmDurationSeconds": vm_duration_s,
        "observedComputeEstimateUsd": round(compute, 8) if vm_duration_s is not None else None,
        "ancillaryAllowanceUsedForConservativeEstimateUsd": ancillary_reserved if vm_duration_s is not None else 0.0,
        "actualBillingAmountUsd": actual_billing,
        "observedNewConservativeEstimateUsd": round(compute + ancillary_reserved, 8) if vm_duration_s is not None else 0.0,
        "observedCumulativeConservativeEstimateUsd": round(
            float(cfg["cloudBudget"]["priorEstimatedEnvelopeUsd"])
            + compute + ancillary_reserved, 8
        ) if vm_duration_s is not None else float(cfg["cloudBudget"]["priorEstimatedEnvelopeUsd"]),
    })
    (RESULTS / "phase13_cost_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan


def write_source_manifest() -> None:
    files = [
        "configs/phase13_split_inlet_recovery.json",
        "optimization/phase13_openfoam_casegen.py",
        "optimization/phase13_openfoam_worker.py",
        "optimization/phase13_worker_startup.sh",
        "optimization/phase13_cloud_runner.py",
        "templates/openfoam/0/alphat", "templates/openfoam/0/k",
        "templates/openfoam/0/nut", "templates/openfoam/0/omega",
        "templates/openfoam/0/p", "templates/openfoam/0/T", "templates/openfoam/0/U",
        "templates/openfoam/constant/thermophysicalProperties",
        "templates/openfoam/constant/turbulenceProperties",
        "templates/openfoam/system/changeDictionaryDict",
        "templates/openfoam/system/controlDict", "templates/openfoam/system/fvSchemes",
        "templates/openfoam/system/fvSolution", "templates/openfoam/system/meshQualityDict",
        "packages/phase13_worker_bundle.tar.gz",
    ]
    for case in ("r030_smoothstep_medium", "r035_smoothstep_medium"):
        files.extend(f"cases/{case}/{relative}" for relative in (
            "mesh.msh", "case.json", "0/alphat", "0/k", "0/nut", "0/omega",
            "0/p", "0/T", "0/U", "constant/thermophysicalProperties",
            "constant/turbulenceProperties", "system/changeDictionaryDict",
            "system/controlDict", "system/fvSchemes", "system/fvSolution",
            "system/meshQualityDict",
        ))
    manifest = {
        "phase": 13,
        "generatedAtUtc": iso(),
        "files": sorted(files),
        "sourceInputsOutsidePhase13": [
            "../configs/phase9_geometry_mass_screen.json",
            "../results/phase9_720_meanline_summary.json",
            "../deliverables/phase12/reports/phase12_front_area_variants.csv",
        ],
    }
    (RESULTS / "phase13_source_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def cloud_execute(cfg: dict[str, Any], project: str, bundle: Path, bundle_bytes: int,
                  bundle_sha: str, preflight: dict[str, Any]) -> dict[str, Any]:
    budget = cfg["cloudBudget"]
    suffix = now().strftime("%y%m%d%H%M%S")
    instance = f"hsedf-p13-{suffix}"
    bucket = f"hsedf-p13-{project[-8:]}-{suffix}".lower()
    bundle_object = "input/phase13-worker-bundle.tar.gz"
    result_object = "output/phase13-output.tar.gz"
    finish_object = "output/phase13-finish.json"
    attempt_dir = RESULTS / "attemptLogs" / suffix
    attempt_dir.mkdir(parents=True, exist_ok=True)
    attempt_log = attempt_dir / "cloud_attempt.log"
    attempt_start = now()
    event_log: list[str] = []
    vm_created_time: datetime | None = None
    vm_started_at: datetime | None = None
    vm_termination_at: datetime | None = None
    vm_started_monotonic: float | None = None
    vm_duration: float | None = None
    created = False
    deletion_requested = False
    bucket_created = False
    output_path = attempt_dir / "phase13-output.tar.gz"
    extracted = attempt_dir / "worker_output"
    finish_path = attempt_dir / "phase13-finish.json"
    vm_json_path = attempt_dir / "instance-create.json"
    final_state = "launch_attempt_failed"
    finish_envelope: dict[str, Any] | None = None
    create_response = ""

    def event(message: str) -> None:
        line = f"{iso()} {message}"
        event_log.append(line)
        attempt_log.write_text("\n".join(event_log) + "\n", encoding="utf-8")

    try:
        event(f"ATTEMPT_START instance={instance} bucket={bucket} packageBytes={bundle_bytes} sha256={bundle_sha}")
        run([
            "gcloud", "storage", "buckets", "create", f"gs://{bucket}",
            "--location=us-central1", "--uniform-bucket-level-access",
            "--public-access-prevention", f"--project={project}", "--quiet",
        ], timeout=60)
        bucket_created = True
        run(["gcloud", "storage", "cp", str(bundle), f"gs://{bucket}/{bundle_object}", "--quiet"], timeout=90)
        event(f"GCS_UPLOAD_COMPLETE bytes={bundle_bytes}")

        metadata = ",".join((
            f"BUCKET={bucket}", f"BUNDLE_OBJECT={bundle_object}",
            f"RESULT_OBJECT={result_object}", f"FINISH_OBJECT={finish_object}",
            f"MAX_ARTIFACT_BYTES={budget['maximumWorkerArtifactBytes']}",
        ))
        create_args = [
            "gcloud", "compute", "instances", "create", instance,
            f"--project={project}", f"--zone={budget['zone']}",
            f"--machine-type={budget['machineType']}", "--provisioning-model=SPOT",
            "--instance-termination-action=DELETE",
            f"--max-run-duration={budget['maxRunDurationSeconds']}s",
            "--maintenance-policy=TERMINATE", "--no-restart-on-failure",
            "--image-family=ubuntu-2204-lts", "--image-project=ubuntu-os-cloud",
            f"--boot-disk-size={budget['bootDiskGb']}GB", "--boot-disk-type=pd-standard",
            "--boot-disk-auto-delete", "--scopes=storage-rw",
            f"--metadata={metadata}", f"--metadata-from-file=startup-script={STARTUP}",
            "--labels=phase=13,study=split-inlet-recovery", "--quiet",
        ]
        event("VM_CREATE_REQUEST " + " ".join(create_args))
        try:
            create_result = run(create_args, timeout=120, allow_fail=True)
            create_response = create_result.stdout + create_result.stderr
            event(f"VM_CREATE_RETURN rc={create_result.returncode}; {create_response[-1500:]}")
        except subprocess.TimeoutExpired:
            event("VM_CREATE_CLIENT_TIMEOUT; inspecting only the single requested instance name")

        describe = run([
            "gcloud", "compute", "instances", "describe", instance,
            f"--project={project}", f"--zone={budget['zone']}", "--format=json", "--quiet",
        ], timeout=30, allow_fail=True)
        if describe.returncode == 0:
            instance_info = json.loads(describe.stdout or "{}")
            vm_json_path.write_text(json.dumps(instance_info, indent=2) + "\n", encoding="utf-8")
            created = True
            vm_created_time = parse_gcloud_time(instance_info.get("creationTimestamp"))
            vm_started_at = parse_gcloud_time(instance_info.get("lastStartTimestamp"))
            vm_termination_at = parse_gcloud_time(
                instance_info.get("resourceStatus", {}).get("scheduling", {}).get("terminationTimestamp")
            )
            event(f"VM_EXISTS status={instance_info.get('status')} createdAt={instance_info.get('creationTimestamp')}")
        elif create_response and "ERROR" not in create_response:
            event("VM_DESCRIBE_NOT_FOUND_AFTER_CREATE_RETURN")
        if not created:
            final_state = "vm_not_created"
            return {
                "status": final_state, "instanceName": instance, "bucket": bucket,
                "attemptStartedAtUtc": iso(attempt_start), "attemptFinishedAtUtc": iso(),
                "observedVmDurationSeconds": None, "selectedRecovery": None,
                "attemptLog": str(attempt_log.relative_to(PHASE)),
                "workerBundleBytes": bundle_bytes, "workerBundleSha256": bundle_sha,
            }

        run_start = time.monotonic()
        create_deadline = run_start + int(budget["maxRunDurationSeconds"])
        finish_seen = False
        while time.monotonic() < create_deadline:
            status_result = run([
                "gcloud", "compute", "instances", "describe", instance,
                f"--project={project}", f"--zone={budget['zone']}",
                "--format=value(status)", "--quiet",
            ], timeout=15, allow_fail=True)
            status = status_result.stdout.strip() if status_result.returncode == 0 else "DELETED"
            if status == "RUNNING" and vm_started_monotonic is None:
                vm_started_monotonic = time.monotonic()
                if vm_started_at is None:
                    vm_started_at = now()
                event("VM_RUNNING; max-runtime watchdog active")
            if status == "DELETED" or status == "TERMINATED":
                event(f"VM_NO_LONGER_RUNNING status={status}")
                break
            finish_result = run([
                "gcloud", "storage", "cat", f"gs://{bucket}/{finish_object}", "--quiet",
            ], timeout=15, allow_fail=True)
            if finish_result.returncode == 0:
                try:
                    finish_envelope = json.loads(finish_result.stdout)
                    finish_seen = True
                    event(f"WORKER_FINISH_OBJECT_RECEIVED exitCode={finish_envelope.get('exitCode')}")
                    break
                except json.JSONDecodeError:
                    event("WORKER_FINISH_OBJECT_INVALID_JSON")
            running_for = (
                max(0.0, (now() - vm_started_at).total_seconds())
                if vm_started_at else time.monotonic() - (vm_started_monotonic or run_start)
            )
            if running_for >= int(budget["maxRunDurationSeconds"]) - 90:
                event("MAX_RUNTIME_NEAR; issuing the one planned instance delete")
                break
            time.sleep(5)

        if finish_seen:
            result_download = run([
                "gcloud", "storage", "cp", f"gs://{bucket}/{result_object}",
                str(output_path), "--quiet",
            ], timeout=60, allow_fail=True)
            if result_download.returncode == 0:
                finish_path.write_text(json.dumps(finish_envelope, indent=2) + "\n", encoding="utf-8")
                ensure_safe_extract(output_path, extracted)
                final_state = "worker_finished"
                event(f"WORKER_ARTIFACT_DOWNLOADED bytes={output_path.stat().st_size}")
            else:
                event(f"WORKER_ARTIFACT_DOWNLOAD_FAILED {result_download.stderr[-1000:]}")
                final_state = "worker_finished_artifact_missing"
        else:
            event("WORKER_FINISH_MISSING_BY_RUNNER_DEADLINE")
            final_state = "worker_timeout_or_preempted"
            serial = run([
                "gcloud", "compute", "instances", "get-serial-port-output", instance,
                f"--project={project}", f"--zone={budget['zone']}",
                "--port=1", "--format=value(contents)", "--quiet",
            ], timeout=20, allow_fail=True)
            if serial.stdout:
                (attempt_dir / "serial_console.log").write_text(serial.stdout, encoding="utf-8")
                event(f"SERIAL_CONSOLE_CAPTURED bytes={len(serial.stdout.encode('utf-8'))}")
            elif serial.stderr:
                event(f"SERIAL_CONSOLE_UNAVAILABLE {serial.stderr[-800:]}")

        deletion_start = time.monotonic()
        deletion = run([
            "gcloud", "compute", "instances", "delete", instance,
            f"--project={project}", f"--zone={budget['zone']}", "--quiet",
        ], timeout=60, allow_fail=True)
        deletion_requested = True
        event(f"VM_DELETE_RETURN rc={deletion.returncode}; {deletion.stdout[-1000:]} {deletion.stderr[-1000:]}")
        delete_text = deletion.stdout + deletion.stderr
        if ("was not found" in delete_text or "not found" in delete_text.lower()) and vm_started_at and vm_termination_at:
            vm_duration = max(0.0, (vm_termination_at - vm_started_at).total_seconds())
            event("VM_DURATION_FROM_GCE_SCHEDULED_TERMINATION_TIMESTAMP")
        elif vm_started_at is not None:
            vm_duration = min(
                float(budget["maxRunDurationSeconds"]),
                max(0.0, (now() - vm_started_at).total_seconds()),
            )
        elif vm_started_monotonic is not None:
            vm_duration = time.monotonic() - vm_started_monotonic
        elif vm_created_time is not None:
            vm_duration = max(0.0, (now() - vm_created_time).total_seconds())
        event(f"OBSERVED_VM_RUNNING_SECONDS={vm_duration}")
        event(f"DELETE_COMMAND_ELAPSED_SECONDS={time.monotonic() - deletion_start:.3f}")

        # Preserve a compact summary next to the full worker output and all attempt logs.
        worker_receipt = extracted / "phase13_solver_receipt.json" if finish_seen else None
        solver_receipt = None
        if worker_receipt and worker_receipt.is_file():
            solver_receipt = json.loads(worker_receipt.read_text(encoding="utf-8"))
        selected = solver_receipt.get("selectedRecovery") if solver_receipt else None
        final_state = solver_receipt.get("status", final_state) if solver_receipt else final_state
        return {
            "status": final_state,
            "bucket": bucket,
            "instanceName": instance,
            "instanceStatusAtCreate": instance_info.get("status"),
            "instanceCreatedAtUtc": instance_info.get("creationTimestamp"),
            "instanceLastStartAtUtc": instance_info.get("lastStartTimestamp"),
            "attemptStartedAtUtc": iso(attempt_start),
            "attemptFinishedAtUtc": iso(),
            "observedVmDurationSeconds": round(vm_duration, 3) if vm_duration is not None else None,
            "vmMaxRunDurationSeconds": budget["maxRunDurationSeconds"],
            "vmTerminationAction": budget["terminationAction"],
            "instanceDeleteCommandReturnCode": deletion.returncode,
            "workerFinishEnvelope": finish_envelope,
            "solverReceipt": solver_receipt,
            "selectedRecovery": selected,
            "attemptLog": str(attempt_log.relative_to(PHASE)),
            "workerArtifact": str(output_path.relative_to(PHASE)) if output_path.is_file() else None,
            "workerArtifactBytes": output_path.stat().st_size if output_path.is_file() else None,
            "workerBundleBytes": bundle_bytes,
            "workerBundleSha256": bundle_sha,
        }
    except Exception as exc:
        event(f"CLOUD_RUNNER_EXCEPTION {type(exc).__name__}: {exc}")
        return {
            "status": final_state,
            "error": f"{type(exc).__name__}: {exc}",
            "instanceName": instance,
            "bucket": bucket,
            "observedVmDurationSeconds": vm_duration,
            "attemptLog": str(attempt_log.relative_to(PHASE)),
            "selectedRecovery": None,
            "workerBundleBytes": bundle_bytes,
            "workerBundleSha256": bundle_sha,
        }
    finally:
        if created and not deletion_requested:
            delete_result = run([
                "gcloud", "compute", "instances", "delete", instance,
                f"--project={project}", f"--zone={budget['zone']}", "--quiet",
            ], timeout=60, allow_fail=True)
            if delete_result.returncode == 0:
                event("FINALLY_VM_DELETE_CONFIRMED")
            deletion_requested = True
            if vm_started_at is not None:
                vm_duration = min(
                    float(budget["maxRunDurationSeconds"]),
                    max(0.0, (now() - vm_started_at).total_seconds()),
                )
            elif vm_started_monotonic is not None:
                vm_duration = time.monotonic() - vm_started_monotonic
        if bucket_created:
            run(["gcloud", "storage", "rm", "--recursive", f"gs://{bucket}/**", "--quiet"],
                timeout=60, allow_fail=True)
            bucket_delete = run(["gcloud", "storage", "buckets", "delete", f"gs://{bucket}", "--quiet"],
                                timeout=60, allow_fail=True)
            event(f"TEMP_GCS_BUCKET_DELETE_RETURN rc={bucket_delete.returncode}")
            event("TEMP_GCS_BUCKET_DELETE_REQUESTED")
        if attempt_log.exists():
            attempt_log.write_text("\n".join(event_log) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch", action="store_true", help="create the one approved Spot VM after all gates pass")
    parser.add_argument("--project", help="GCP project; defaults to the active gcloud project")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    project_result = run(["gcloud", "config", "get-value", "project", "--quiet"], timeout=10)
    project = args.project or project_result.stdout.strip()
    if not project or project == "(unset)":
        raise RuntimeError("no active GCP project; launch blocked")
    local = local_gates(cfg)
    cloud = cloud_gates(cfg, project)
    launch_receipt_path = RESULTS / "phase13_execution_receipt.json"
    never_attempted = not launch_receipt_path.exists()
    gates_pass = (
        local["allLocalMeshDictionaryAndAreaGatesPass"]
        and local["allCompleteProjectionAreasBelow75Cm2"]
        and local["costEstimatePass"]
        and cloud["billingEnabled"] and cloud["requiredApisEnabled"]
        and cloud["machineType"] == cfg["cloudBudget"]["machineType"]
        and cloud["zoneStatus"] == "UP"
        and not cloud["existingRunningPhase13Instances"]
        and never_attempted
    )
    bundle: Path | None = None
    bundle_bytes: int | None = None
    bundle_sha: str | None = None
    package_error: str | None = None
    if gates_pass:
        try:
            bundle, bundle_bytes, bundle_sha = package_worker(cfg)
            write_source_manifest()
        except Exception as exc:
            gates_pass = False
            package_error = f"{type(exc).__name__}: {exc}"
    preflight = {
        "phase": 13,
        "checkedAtUtc": iso(),
        "localGates": local,
        "cloudGates": cloud,
        "oneLaunchOnlyGuardPass": never_attempted,
        "launchGatesPass": gates_pass,
        "workerPackage": {
            "path": str(bundle.relative_to(PHASE)) if bundle else None,
            "sizeBytes": bundle_bytes,
            "sha256": bundle_sha,
            "error": package_error,
        },
        "launchRequested": args.launch,
        "launchPermitted": gates_pass and args.launch,
        "status": "ready" if gates_pass else "blocked",
    }
    (RESULTS / "phase13_cloud_preflight.json").write_text(
        json.dumps(preflight, indent=2) + "\n", encoding="utf-8"
    )
    write_source_manifest()
    print(json.dumps(preflight, indent=2))
    if not gates_pass:
        if args.launch:
            plan = update_cost_receipt(cfg, None, "launch-blocked-cloud-preflight")
            receipt = {
                "phase": 13, "status": "launch-blocked-cloud-preflight",
                "launchPermitted": False, "cloudSpendUsdEstimate": 0.0,
                "priorPhase10And11EstimateUsd": cfg["cloudBudget"]["priorEstimatedEnvelopeUsd"],
                "cumulativeConservativeEstimateUsd": cfg["cloudBudget"]["priorEstimatedEnvelopeUsd"],
                "selectedRecovery": None, "solverConverged": False,
                "cloudPreflight": preflight, "costPlan": plan,
                "attemptLogs": [], "cfdFields": None,
            }
            launch_receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return 2
    if not args.launch:
        return 0

    # One-shot marker is written before any GCP resource creation; this driver will not retry.
    (RESULTS / "phase13_launch_once.json").write_text(json.dumps({
        "phase": 13, "attemptAuthorizedAtUtc": iso(), "instanceLimit": 1,
        "retryAllowed": False,
    }, indent=2) + "\n", encoding="utf-8")
    assert bundle is not None and bundle_bytes is not None and bundle_sha is not None
    result = cloud_execute(cfg, project, bundle, bundle_bytes, bundle_sha, preflight)
    duration = result.get("observedVmDurationSeconds")
    cost_plan = update_cost_receipt(cfg, duration, result.get("status", "completed"))
    selected = result.get("selectedRecovery")
    bucket_deleted = True
    if result.get("bucket"):
        bucket_list = run([
            "gcloud", "storage", "buckets", "list", f"--project={project}",
            f"--filter=name={result['bucket']}", "--format=value(name)", "--quiet",
        ], timeout=20, allow_fail=True)
        bucket_deleted = bucket_list.returncode == 0 and not bucket_list.stdout.strip()
    instance_deleted = True
    if result.get("instanceName"):
        instance_status = run([
            "gcloud", "compute", "instances", "list", f"--project={project}",
            f"--filter=name={result['instanceName']}", "--format=value(name)", "--quiet",
        ], timeout=20, allow_fail=True)
        instance_deleted = instance_status.returncode == 0 and not instance_status.stdout.strip()
    worker_fields_disposition = None
    if result.get("workerArtifact"):
        output_root = PHASE / Path(result["workerArtifact"]).parent / "worker_output"
        disposition = output_root / "cfd_fields_disposition.json"
        worker_fields_disposition = (
            json.loads(disposition.read_text(encoding="utf-8"))
            if disposition.is_file() else "latest solution fields retained in worker output archive"
        )
    receipt = {
        "phase": 13,
        "status": result.get("status"),
        "launchPermitted": True,
        "cloudPreflight": preflight,
        "instanceName": result.get("instanceName"),
        "instanceCreatedAtUtc": result.get("instanceCreatedAtUtc"),
        "observedVmDurationSeconds": duration,
        "actualBillingAmountUsd": None,
        "computeObservedEstimateUsd": cost_plan.get("observedComputeEstimateUsd"),
        "additionalConservativeEstimateUsd": cost_plan.get("observedNewConservativeEstimateUsd"),
        "priorPhase10And11EstimateUsd": cfg["cloudBudget"]["priorEstimatedEnvelopeUsd"],
        "cumulativeConservativeEstimateUsd": cost_plan.get("observedCumulativeConservativeEstimateUsd"),
        "approvedTotalEnvelopeUsd": cfg["cloudBudget"]["approvedTotalEnvelopeUsd"],
        "solverConverged": bool(selected),
        "selectedRecovery": selected,
        "attemptLogs": [result["attemptLog"]] if result.get("attemptLog") else [],
        "workerArtifact": result.get("workerArtifact"),
        "workerArtifactBytes": result.get("workerArtifactBytes"),
        "workerBundleBytes": result.get("workerBundleBytes"),
        "workerBundleSha256": result.get("workerBundleSha256"),
        "temporaryGcsBucketDeleted": bucket_deleted,
        "vmDeleted": instance_deleted,
        "bootDiskAutoDelete": True,
        "cncExecution": False,
        "cfdFields": worker_fields_disposition,
        "error": result.get("error"),
        "solverReceipt": result.get("solverReceipt"),
        "costPlan": cost_plan,
    }
    launch_receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "duration": duration,
                      "selectedRecovery": selected,
                      "cumulativeEstimate": receipt["cumulativeConservativeEstimateUsd"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
