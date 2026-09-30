"""Preflight and run the bounded Phase-15 aeroelastic FSI candidate sweep."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PHASE = Path(__file__).resolve().parents[1]
EDF_ROOT = PHASE.parent
CASE_ROOT = PHASE / "fsi" / "cases"
REPORTS = PHASE / "fsi" / "reports"
RESULTS = PHASE / "fsi" / "results"
STARTUP = PHASE / "optimization" / "phase15_fsi_worker_startup.sh"
PROJECT_DEFAULT = "project-ba289c9c-3c25-4e15-9dc"
BUCKET_DEFAULT = "aero-governed-blockers-988177451335-20260919"
ZONE = "us-central1-b"
WORKBENCH_ROOT_DEFAULT = EDF_ROOT.parent.parent / "aero-multiphysics-workbench"
ANCILLARY_CEILING_USD = 0.03
MAX_ARTIFACT_BYTES = 15_000_000
UTC = timezone.utc


def now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None = None) -> str:
    return (value or now()).isoformat()


def run(args: list[str], timeout: int = 30, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    command: list[str] | str = args
    shell = False
    if os.name == "nt" and args and args[0] == "gcloud":
        command = subprocess.list2cmdline(args)
        shell = True
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                            check=False, shell=shell)
    if result.returncode and not allow_fail:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n"
                           f"{result.stderr[-3000:]}")
    return result


def gcloud_json(args: list[str], timeout: int = 45) -> Any:
    result = run(["gcloud", *args, "--format=json", "--quiet"], timeout=timeout)
    return json.loads(result.stdout or "{}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_workbench_remote_policy(workbench_root: Path, project: str) -> dict[str, Any]:
    if not workbench_root.is_dir():
        raise FileNotFoundError(f"Aero Multiphysics Workbench not found: {workbench_root}")
    solvers_root = workbench_root / "solvers"
    if str(solvers_root) not in sys.path:
        sys.path.insert(0, str(solvers_root))
    from participants.remote_policy import (  # type: ignore[import-not-found]
        CostLedger,
        CostPlan,
        RemoteComputePolicy,
        RemoteResourceRequest,
    )

    policy = RemoteComputePolicy.from_environment()
    policy.require_enabled()
    limits = policy.limits
    machine_shape = {"e2-standard-2": (2.0, 4096.0), "e2-standard-4": (4.0, 8192.0)}
    if limits.machine_type not in machine_shape:
        raise ValueError(f"workbench FSI run does not admit machine type {limits.machine_type}")
    vcpu, memory = machine_shape[limits.machine_type]
    # Poll-to-completion: the wall time is the cost cap (at the workbench
    # reference rate, 5400 s on e2-standard-2 == $0.15), not a guess at runtime.
    wall = min(int(limits.max_wall_time_s), 5400)
    request = RemoteResourceRequest(vcpu=vcpu, memory_mib=memory, wall_time_s=float(wall),
                                    machine_type=limits.machine_type)
    policy.assert_within_limits(request)
    policy.assert_placement_allowed(region="us-central1", project=project)
    job_id = f"phase15-wing-fsi-{now().strftime('%Y%m%dT%H%M%SZ')}"
    plan = CostPlan.build(job_id, request)
    all_in = plan.planned_max_cost_usd + ANCILLARY_CEILING_USD
    if all_in > limits.max_job_cost_usd + 1e-9:
        raise ValueError(f"Workbench per-job cost ceiling blocks FSI plan: {all_in:.6f} > {limits.max_job_cost_usd:.6f}")
    history_path = RESULTS / "phase15_fsi_cost_history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.is_file() else []
    prior_spend = sum(float(x.get("allInConservativeUsd", 0.0)) for x in history)
    if prior_spend + all_in > min(limits.max_session_cost_usd, limits.max_daily_cost_usd,
                                  limits.max_project_cost_usd) + 1e-9:
        raise ValueError("Workbench session/daily/project remote-cost ceiling would be exceeded")
    ledger = CostLedger(limits, project_spent_usd=prior_spend,
                        daily_spent_usd=prior_spend, session_spent_usd=prior_spend)
    ledger.reserve(plan)
    return {"policy": policy, "ledger": ledger, "plan": plan, "request": request,
            "machineType": limits.machine_type, "maxRuntimeSeconds": wall,
            "vcpu": vcpu, "memoryMiB": memory, "plannedComputeUsd": plan.planned_max_cost_usd,
            "ancillaryCeilingUsd": ANCILLARY_CEILING_USD, "allInCeilingUsd": all_in,
            "maxJobCostUsd": limits.max_job_cost_usd, "maxSessionCostUsd": limits.max_session_cost_usd,
            "maxDailyCostUsd": limits.max_daily_cost_usd, "maxProjectCostUsd": limits.max_project_cost_usd,
            "priorAllInConservativeUsd": prior_spend, "workbenchRoot": str(workbench_root)}


def local_preflight() -> dict[str, Any]:
    casegen_path = REPORTS / "phase15_fsi_casegen.json"
    screen_path = REPORTS / "phase15_aero_multiphysics_candidates.json"
    if not casegen_path.is_file():
        raise FileNotFoundError("run phase15_fsi_casegen.py before GCP preflight")
    if not screen_path.is_file():
        raise FileNotFoundError("run phase15_aero_multiphysics_screen.py before GCP preflight")
    generated = json.loads(casegen_path.read_text(encoding="utf-8"))
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    if not screen.get("workbenchCommit") or not screen.get("workbenchRoot"):
        raise ValueError("Aero Multiphysics candidate screen lacks repository provenance")
    case_ids = sorted(p.name for p in CASE_ROOT.iterdir()
                      if p.is_dir() and (p / "precice-config.xml").is_file())
    case_rows = []
    for case_id in case_ids:
        root = CASE_ROOT / case_id
        required = [root / "precice-config.xml", root / "fluid" / "wing.msh",
                    root / "fluid" / "system" / "preciceDict",
                    root / "solid" / "config.yml", root / "solid" / "wing.inp",
                    root / "solid" / "wing.msh"]
        if not all(p.is_file() for p in required):
            raise FileNotFoundError(f"incomplete case package: {case_id}")
        config_text = (root / "precice-config.xml").read_text(encoding="utf-8")
        for token in ("<participant name=\"Fluid\"", "<participant name=\"Solid\"",
                      "parallel-implicit", "Displacement", "Force"):
            if token not in config_text:
                raise ValueError(f"preCICE configuration token missing for {case_id}: {token}")
        candidates = generated.get("candidates", [])
        meta = next((x for x in candidates if x.get("candidate") == case_id), None)
        if meta is None:
            raise ValueError(f"candidate generation receipt missing: {case_id}")
        if int(meta["fluid"]["fluidCells"]) < 10_000 or int(meta["solid"]["solidElements"]) < 5_000:
            raise ValueError(f"mesh below minimum cells for {case_id}")
        case_rows.append({"candidate": case_id,
                          "fluidCells": meta["fluid"]["fluidCells"],
                          "solidTetrahedra": meta["solid"]["solidElements"],
                          "fluidMshBytes": (root / "fluid" / "wing.msh").stat().st_size,
                          "solidInpBytes": (root / "solid" / "wing.inp").stat().st_size})
    if len(case_rows) != 2:
        raise ValueError(f"expected two thickness candidates, found {len(case_rows)}")
    return {
        "caseCount": len(case_rows), "cases": case_rows,
        "workbench": {"status": screen.get("status"),
                      "commit": screen.get("workbenchCommit"),
                      "fidelity": screen.get("physicsSource"),
                      "nativeEvidence": screen.get("nativeSolverEvidence"),
                      "inputHash": sha256(screen_path)},
        "meshAndCaseGeneration": "PASS",
        "maximumArtifactBytes": MAX_ARTIFACT_BYTES,
    }


def cloud_preflight(project: str, bucket: str, machine_type: str,
                    boot_image: str | None = None) -> dict[str, Any]:
    billing = gcloud_json(["beta", "billing", "projects", "describe", project])
    machine = gcloud_json(["compute", "machine-types", "describe", machine_type,
                           f"--zone={ZONE}", f"--project={project}"])
    zone = gcloud_json(["compute", "zones", "describe", ZONE, f"--project={project}"])
    images = gcloud_json(["compute", "images", "list", "--project=ubuntu-os-cloud",
                          "--filter=family=ubuntu-2204-lts AND status=READY",
                          "--sort-by=~creationTimestamp", "--limit=1"])
    image_name = images[0].get("name") if images else None
    active = run(["gcloud", "compute", "instances", "list", f"--project={project}",
                  "--filter=labels.study=wing-fsi AND status=RUNNING",
                  "--format=value(name)", "--quiet"], timeout=30).stdout.splitlines()
    bucket_meta = gcloud_json(["storage", "buckets", "describe", f"gs://{bucket}"])
    enabled = run(["gcloud", "services", "list", "--enabled", f"--project={project}",
                   "--format=value(config.name)", "--quiet"], timeout=30).stdout.splitlines()
    return {
        "project": project, "billingEnabled": bool(billing.get("billingEnabled")),
        "computeApiEnabled": "compute.googleapis.com" in enabled,
        "storageApiEnabled": "storage.googleapis.com" in enabled,
        "zone": ZONE, "zoneStatus": zone.get("status"),
        "machineType": machine.get("name"), "machineVcpus": machine.get("guestCpus"),
        "machineMemoryMb": machine.get("memoryMb"),
        "bootImage": image_name,
        "bucket": bucket, "bucketLocation": bucket_meta.get("location"),
        "existingRunningFsiInstances": active,
        "pass": bool(billing.get("billingEnabled")) and
                "compute.googleapis.com" in enabled and "storage.googleapis.com" in enabled and
                zone.get("status") == "UP" and machine.get("name") == machine_type and
                bool(image_name) and (boot_image is None or image_name == boot_image) and
                bucket_meta.get("location", "").upper() == "US-CENTRAL1" and not active,
    }


def package_bundle(path: Path) -> tuple[int, str]:
    members = [PHASE / "optimization" / "phase15_fsi_worker.py",
               PHASE / "optimization" / "phase15_fsi_casegen.py",
               PHASE / "optimization" / "phase15_aero_multiphysics_screen.py",
               PHASE / "fsi" / "reports" / "phase15_fsi_casegen.json",
               PHASE / "fsi" / "reports" / "phase15_aero_multiphysics_candidates.json",
               CASE_ROOT]
    with tarfile.open(path, "w:gz", compresslevel=6) as archive:
        for source in members:
            if source.is_dir():
                for item in sorted(source.rglob("*")):
                    if item.is_file() and "__pycache__" not in item.parts:
                        archive.add(item, arcname=Path("phase15") / item.relative_to(PHASE))
            else:
                archive.add(source, arcname=Path("phase15") / source.relative_to(PHASE))
    size = path.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        raise RuntimeError(f"FSI worker bundle {size} exceeds {MAX_ARTIFACT_BYTES} bytes")
    return size, sha256(path)


def safe_extract(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    base = destination.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            if target != base and base not in target.parents:
                raise RuntimeError(f"unsafe worker archive member: {member.name}")
        archive.extractall(destination)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=PROJECT_DEFAULT)
    ap.add_argument("--bucket", default=BUCKET_DEFAULT)
    ap.add_argument("--workbench-root", default=str(WORKBENCH_ROOT_DEFAULT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = now().strftime("%Y%m%dT%H%M%SZ")
    policy_context: dict[str, Any] | None = None
    try:
        policy_context = load_workbench_remote_policy(Path(args.workbench_root), args.project)
        policy_error = None
    except Exception as exc:
        policy_error = f"{type(exc).__name__}: {exc}"
    local = local_preflight()
    machine = policy_context["machineType"] if policy_context else "e2-standard-2"
    wall_s = policy_context["maxRuntimeSeconds"] if policy_context else 1800
    cloud = cloud_preflight(args.project, args.bucket, machine)
    if policy_context:
        estimate_total = policy_context["allInCeilingUsd"]
        policy_budget_pass = estimate_total <= policy_context["maxJobCostUsd"] + 1e-9
        workbench_policy_receipt = {
            "enabled": True, "workbenchRoot": policy_context["workbenchRoot"],
            "machineType": policy_context["machineType"], "vcpu": policy_context["vcpu"],
            "memoryMiB": policy_context["memoryMiB"], "maxWallTimeSeconds": wall_s,
            "plannedComputeUsd": policy_context["plannedComputeUsd"],
            "ancillaryCeilingUsd": policy_context["ancillaryCeilingUsd"],
            "allInCeilingUsd": estimate_total, "maxJobCostUsd": policy_context["maxJobCostUsd"],
            "maxSessionCostUsd": policy_context["maxSessionCostUsd"],
            "maxDailyCostUsd": policy_context["maxDailyCostUsd"],
            "maxProjectCostUsd": policy_context["maxProjectCostUsd"],
            "priorAllInConservativeUsd": policy_context["priorAllInConservativeUsd"],
            "pass": policy_budget_pass,
        }
    else:
        estimate_total = None
        policy_budget_pass = False
        workbench_policy_receipt = {"enabled": False, "pass": False, "detail": policy_error}
    preflight = {"local": local, "cloud": cloud, "workbenchRemotePolicy": workbench_policy_receipt}
    preflight["launchPermitted"] = (preflight["local"]["meshAndCaseGeneration"] == "PASS"
                                    and preflight["cloud"]["pass"] and policy_budget_pass)
    preflight["launchRequested"] = not args.dry_run
    preflight["checkedAtUtc"] = iso(now())
    preflight_path = RESULTS / f"phase15_fsi_preflight_{stamp}.json"
    preflight_path.write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
    if not preflight["launchPermitted"] or args.dry_run:
        print(json.dumps(preflight, indent=2))
        return 0 if preflight["launchPermitted"] else 2

    instance = f"hsedf-fsi-{stamp.lower().replace('t','-').replace('z','')}"
    prefix = f"phase15-fsi/{stamp}"
    bundle = RESULTS / f"phase15_fsi_bundle_{stamp}.tar.gz"
    bundle_bytes, bundle_sha = package_bundle(bundle)
    objects = {"bundle": f"{prefix}/input.tar.gz", "result": f"{prefix}/output.tar.gz",
               "log": f"{prefix}/worker.log", "finish": f"{prefix}/finish.json"}
    attempt = RESULTS / "attempts" / stamp
    attempt.mkdir(parents=True, exist_ok=True)
    attempt_log = attempt / "gcp_attempt.log"
    events: list[str] = []

    def event(text: str) -> None:
        line = f"{iso()} {text}"
        events.append(line)
        attempt_log.write_text("\n".join(events) + "\n", encoding="utf-8")

    created = False
    zone_used = ZONE
    finish_obj: dict[str, Any] | None = None
    runner_status = "launch_failed"
    start_time = time.monotonic()
    vm_started_monotonic: float | None = None
    result_tar = attempt / "worker_output.tar.gz"
    startup = str(STARTUP)
    try:
        event(f"PREFLIGHT_PASS instance={instance} bundleBytes={bundle_bytes} sha256={bundle_sha} "
              f"workbenchCostCeilingUsd={policy_context['allInCeilingUsd']}")
        run(["gcloud", "storage", "cp", str(bundle), f"gs://{args.bucket}/{objects['bundle']}", "--quiet"], timeout=120)
        event("BUNDLE_UPLOAD_COMPLETE")
        metadata = ",".join([f"BUCKET={args.bucket}", f"BUNDLE_OBJECT={objects['bundle']}",
                              f"RESULT_OBJECT={objects['result']}", f"LOG_OBJECT={objects['log']}",
                              f"FINISH_OBJECT={objects['finish']}", f"MAX_ARTIFACT_BYTES={MAX_ARTIFACT_BYTES}"])
        create = ["gcloud", "compute", "instances", "create", instance,
                  f"--project={args.project}", f"--zone={ZONE}", f"--machine-type={machine}",
                  "--provisioning-model=SPOT", "--instance-termination-action=DELETE",
                  f"--max-run-duration={wall_s}s", "--maintenance-policy=TERMINATE",
                  "--no-restart-on-failure", "--image-family=ubuntu-2204-lts",
                  "--image-project=ubuntu-os-cloud", "--boot-disk-size=20GB",
                  "--boot-disk-type=pd-standard", "--boot-disk-auto-delete",
                  "--scopes=storage-rw", f"--metadata={metadata}",
                  f"--metadata-from-file=startup-script={startup}",
                  "--labels=phase=15,study=wing-fsi", "--quiet"]
        image_name = preflight["cloud"].get("bootImage")
        if not image_name:
            raise RuntimeError("pinned Ubuntu boot image not available")
        create[create.index("--image-family=ubuntu-2204-lts")] = f"--image={image_name}"
        event("VM_CREATE_REQUEST " + " ".join(create))
        create_result = run(create, timeout=120, allow_fail=True)
        event(f"VM_CREATE_RETURN rc={create_result.returncode} {create_result.stderr[-1000:]}")
        describe = run(["gcloud", "compute", "instances", "describe", instance,
                        f"--project={args.project}", f"--zone={ZONE}", "--format=json", "--quiet"],
                       timeout=45, allow_fail=True)
        created = describe.returncode == 0
        if not created:
            raise RuntimeError("GCE instance create did not produce a describable instance")
        vm_started_monotonic = time.monotonic()
        event(f"VM_CREATED; one pinned Ubuntu image; {wall_s}s max runtime; automatic termination configured")
        deadline = time.monotonic() + wall_s + 180
        while time.monotonic() < deadline:
            stat = run(["gcloud", "storage", "cat", f"gs://{args.bucket}/{objects['finish']}", "--quiet"],
                       timeout=20, allow_fail=True)
            if stat.returncode == 0:
                try:
                    finish_obj = json.loads(stat.stdout)
                    break
                except json.JSONDecodeError:
                    event("INVALID_FINISH_JSON")
            status = run(["gcloud", "compute", "instances", "describe", instance,
                          f"--project={args.project}", f"--zone={zone_used}",
                          "--format=value(status)", "--quiet"], timeout=20, allow_fail=True)
            vm_status = status.stdout.strip() if status.returncode == 0 else "DELETED"
            if vm_status in ("TERMINATED", "DELETED"):
                event(f"VM_STOPPED status={vm_status}; waiting briefly for final GCS receipt")
                time.sleep(8)
            else:
                time.sleep(10)
        if finish_obj is None:
            runner_status = "worker_finish_missing_at_deadline"
            event(runner_status)
        else:
            event(f"FINISH_OBJECT exitCode={finish_obj.get('exitCode')}")
            download = run(["gcloud", "storage", "cp", f"gs://{args.bucket}/{objects['result']}",
                            str(result_tar), "--quiet"], timeout=120, allow_fail=True)
            if download.returncode == 0:
                safe_extract(result_tar, attempt / "worker_output")
                runner_status = "worker_finished" if int(finish_obj.get("exitCode", 1)) == 0 else "worker_failed"
            else:
                runner_status = "worker_artifact_missing"
                event(download.stderr[-2000:])
        if created:
            delete = run(["gcloud", "compute", "instances", "delete", instance,
                          f"--project={args.project}", f"--zone={zone_used}", "--quiet"],
                         timeout=90, allow_fail=True)
            event(f"VM_DELETE rc={delete.returncode}")
    except Exception as exc:
        runner_status = "runner_exception"
        event(f"RUNNER_EXCEPTION {type(exc).__name__}: {exc}")
        if created:
            run(["gcloud", "compute", "instances", "delete", instance,
                 f"--project={args.project}", f"--zone={zone_used}", "--quiet"],
                timeout=90, allow_fail=True)
    finally:
        for object_name in objects.values():
            run(["gcloud", "storage", "rm", f"gs://{args.bucket}/{object_name}", "--quiet"],
                timeout=45, allow_fail=True)

    worker_receipt_path = attempt / "worker_output" / "phase15_fsi_worker_receipt.json"
    worker_receipt = json.loads(worker_receipt_path.read_text(encoding="utf-8")) if worker_receipt_path.is_file() else None
    runtime_s = (time.monotonic() - vm_started_monotonic) if vm_started_monotonic else 0.0
    workbench_cost = None
    if policy_context:
        if created:
            settled = policy_context["ledger"].settle(
                policy_context["plan"].job_id, actual_cost_usd=None, runtime_s=runtime_s,
                machine_type=machine, preempted=finish_obj is None,
            )
            workbench_cost = {
                "jobId": settled.job_id,
                "plannedMaxCostUsd": settled.planned_max_cost_usd,
                "estimatedComputeCostUsd": settled.estimated_cost_usd,
                "actualCloudInvoiceUsd": settled.actual_cost_usd,
                "ancillaryCeilingUsd": ANCILLARY_CEILING_USD,
                "allInConservativeEstimateUsd": round(settled.estimated_cost_usd + ANCILLARY_CEILING_USD, 6),
                "vmWallSecondsEstimate": settled.runtime_s,
                "machineType": settled.machine_type,
                "resourceReleased": settled.released,
                "preempted": settled.preempted,
            }
            history_path = RESULTS / "phase15_fsi_cost_history.json"
            history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.is_file() else []
            history.append(workbench_cost)
            history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        else:
            policy_context["ledger"].release(policy_context["plan"].job_id)
            workbench_cost = {"status": "released_without_vm", "plannedMaxCostUsd":
                              policy_context["plan"].planned_max_cost_usd}
    result = {
        "phase": 15, "study": "GCP OpenFOAM-preCICE-CalculiX coupled wing-sector FSI",
        "executionPath": "Aero Multiphysics candidate/remote-cost policy plus one bounded GCE Spot worker; workbench GCP Batch transport is not provisioned",
        "status": runner_status, "project": args.project, "zone": zone_used,
        "instanceName": instance, "maxRuntimeSeconds": wall_s,
        "conservativeBudgetUsd": estimate_total,
        "hardBudgetUsd": policy_context["maxJobCostUsd"] if policy_context else None,
        "workbenchCostReceipt": workbench_cost,
        "pinnedBootImage": preflight["cloud"].get("bootImage"),
        "bundleBytes": bundle_bytes, "bundleSha256": bundle_sha,
        "startedAtUtc": iso(now()),
        "observedRunnerSeconds": round(time.monotonic() - start_time, 3),
        "workerFinish": finish_obj, "workerReceipt": worker_receipt,
        "attemptDirectory": str(attempt.relative_to(PHASE)),
        "log": str(attempt_log.relative_to(PHASE)), "preflight": preflight,
    }
    result_path = RESULTS / "phase15_fsi_execution_receipt.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if runner_status == "worker_finished" and worker_receipt and \
        worker_receipt.get("status") == "all_candidates_completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
