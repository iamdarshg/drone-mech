#!/usr/bin/env python3
"""Single-pass remote import/check/solve driver for Phase-13 OpenFOAM cases."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
RESIDUAL_RE = re.compile(
    r"Solving for ([A-Za-z][A-Za-z0-9_]*), Initial residual = "
    + NUMBER + r", Final residual = (" + NUMBER + r")"
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_string(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat()


def run_logged(args: list[str], cwd: Path, timeout_s: int, log_path: Path,
               env: dict[str, str]) -> dict[str, Any]:
    start = time.monotonic()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        try:
            proc = subprocess.Popen(
                args, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            log.write(f"Could not start {args[0]}: {type(exc).__name__}: {exc}\n")
            return {"returnCode": None, "timedOut": False, "elapsedSeconds": time.monotonic() - start}
        try:
            code = proc.wait(timeout=max(1, timeout_s))
            return {"returnCode": code, "timedOut": False,
                    "elapsedSeconds": time.monotonic() - start}
        except subprocess.TimeoutExpired:
            log.write(f"\nPHASE13_COMMAND_TIMEOUT command={args[0]}\n")
            log.flush()
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=8)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            return {"returnCode": proc.returncode, "timedOut": True,
                    "elapsedSeconds": time.monotonic() - start}


def data_rows(root: Path) -> list[list[float]]:
    if not root.exists():
        return []
    candidates: list[Path] = []
    for path in root.rglob("surfaceFieldValue.dat"):
        candidates.append(path)
    rows: list[list[float]] = []
    for path in sorted(candidates):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                values = [float(value) for value in re.findall(NUMBER, stripped)]
            except ValueError:
                continue
            if len(values) >= 2:
                rows.append(values)
    rows.sort(key=lambda row: row[0])
    return rows


def patch_average_history(case_dir: Path, name: str) -> list[dict[str, float]]:
    output: list[dict[str, float]] = []
    for row in data_rows(case_dir / "postProcessing" / name):
        if len(row) < 6:
            continue
        output.append({
            "time": row[0], "pPa": row[1], "Ux": row[2], "Uy": row[3],
            "Uz": row[4], "TK": row[5],
        })
    return output


def patch_massflow_history(case_dir: Path, name: str) -> list[tuple[float, float]]:
    return [(row[0], row[-1]) for row in data_rows(case_dir / "postProcessing" / name)
            if len(row) >= 2]


def total_pressure(avg: dict[str, float], gamma: float, gas_r: float) -> float | None:
    if avg["pPa"] <= 0.0 or avg["TK"] <= 0.0:
        return None
    speed_sq = avg["Ux"]**2 + avg["Uy"]**2 + avg["Uz"]**2
    mach_sq = speed_sq / (gamma * gas_r * avg["TK"])
    return avg["pPa"] * (1.0 + 0.5 * (gamma - 1.0) * mach_sq) ** (
        gamma / (gamma - 1.0)
    )


def latest_total_pressures(case_dir: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    gamma = float(cfg["operatingPoint"]["gamma"])
    gas_r = float(cfg["operatingPoint"]["gasConstantJPerKgK"])
    inlet = patch_average_history(case_dir, "inletAverage")
    outlet = patch_average_history(case_dir, "outletAverage")
    count = min(len(inlet), len(outlet))
    history: list[dict[str, float]] = []
    for index in range(count):
        p0_in = total_pressure(inlet[index], gamma, gas_r)
        p0_out = total_pressure(outlet[index], gamma, gas_r)
        if p0_in and p0_out:
            history.append({
                "time": min(inlet[index]["time"], outlet[index]["time"]),
                "inletTotalPressurePa": p0_in,
                "outletTotalPressurePa": p0_out,
                "branchRecovery": p0_out / p0_in,
                "freestreamRecovery": p0_out / float(
                    cfg["_caseFreestreamTotalPressurePa"]
                ),
            })
    return {
        "inletAverageHistoryCount": len(inlet),
        "outletAverageHistoryCount": len(outlet),
        "recoveryHistory": history,
        "latest": history[-1] if history else None,
    }


def residuals(log_text: str) -> dict[str, float]:
    latest: dict[str, float] = {}
    for field, value in RESIDUAL_RE.findall(log_text):
        normalized = "U" if field.startswith("U") else field
        latest[normalized] = float(value)
    return latest


def massflow_last(case_dir: Path, name: str) -> tuple[float, float] | None:
    history = patch_massflow_history(case_dir, name)
    return history[-1] if history else None


def wall_patch_is_wall(case_dir: Path) -> bool:
    path = case_dir / "constant" / "polyMesh" / "boundary"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"\bwalls\s*\{\s*type\s+wall\s*;", text, flags=re.S))


def checkmesh_passed(result: dict[str, Any], log_path: Path) -> tuple[bool, str | None]:
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    failed = re.search(r"Failed\s+(\d+)\s+mesh checks", text, flags=re.I)
    failed_count = int(failed.group(1)) if failed else None
    passed = (
        result.get("returnCode") == 0 and not result.get("timedOut")
        and "Mesh OK." in text
        and (failed_count is None or failed_count == 0)
    )
    return passed, None if passed else f"checkMesh command/log gate failed; failedCheckCount={failed_count}"


def latest_time_dir(case_dir: Path) -> Path | None:
    times: list[tuple[float, Path]] = []
    for path in case_dir.iterdir():
        if not path.is_dir():
            continue
        try:
            numeric = float(path.name)
        except ValueError:
            continue
        if numeric > 0.0:
            times.append((numeric, path))
    return max(times, default=(0.0, None), key=lambda pair: pair[0])[1]


def retain_case_evidence(case_dir: Path, output_dir: Path) -> None:
    target = output_dir / "caseLogs" / case_dir.name
    target.mkdir(parents=True, exist_ok=True)
    for name in ("gmshToFoam.log", "changeDictionary.log", "checkMesh.log", "solver.log"):
        source = case_dir / name
        if source.is_file():
            shutil.copy2(source, target / name)
    field_dir = latest_time_dir(case_dir)
    if field_dir:
        dest = output_dir / "cfdFields" / case_dir.name / field_dir.name
        shutil.copytree(field_dir, dest, dirs_exist_ok=True)
    mesh_dir = case_dir / "constant" / "polyMesh"
    if mesh_dir.is_dir():
        dest_mesh = output_dir / "cfdFields" / case_dir.name / "constant" / "polyMesh"
        shutil.copytree(mesh_dir, dest_mesh, dirs_exist_ok=True)


def run_case(case_dir: Path, cfg: dict[str, Any], runner_start: float,
             output_dir: Path) -> dict[str, Any]:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    cfg_local = {**cfg, "_caseFreestreamTotalPressurePa": case["freestreamTotalPressurePa"]}
    case_start = utc_now()
    max_case_seconds = int(cfg["solver"]["maxSecondsPerCase"])
    command_results: dict[str, Any] = {}
    command_logs = {
        "gmshToFoam": "gmshToFoam.log",
        "changeDictionary": "changeDictionary.log",
        "checkMesh": "checkMesh.log",
        "rhoSimpleFoam": "solver.log",
    }
    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = "1"

    for command, args, cap in (
        ("gmshToFoam", ["gmshToFoam", "mesh.msh"], 30),
        ("changeDictionary", ["changeDictionary", "-constant"], 25),
        ("checkMesh", ["checkMesh", "-constant", "-allGeometry", "-allTopology"], 40),
    ):
        remaining = int(cfg["runner"]["runnerBudgetSeconds"] - (time.monotonic() - runner_start))
        if remaining < 15:
            command_results[command] = {"returnCode": None, "notRun": True, "reason": "runner time cap"}
            break
        command_results[command] = run_logged(
            args, case_dir, min(cap, remaining - 10), case_dir / command_logs[command], env
        )
        result = command_results[command]
        if result.get("returnCode") != 0 or result.get("timedOut"):
            break
        if command == "changeDictionary" and not wall_patch_is_wall(case_dir):
            result["wallPatchReplacementPassed"] = False
            result["reason"] = "imported walls patch is not type wall after direct changeDictionary"
            break
        if command == "checkMesh":
            passed, reason = checkmesh_passed(result, case_dir / command_logs[command])
            result["qualityGatePassed"] = passed
            if not passed:
                result["reason"] = reason
                break

    mesh_pass = bool(command_results.get("checkMesh", {}).get("qualityGatePassed"))
    wall_pass = bool(command_results.get("changeDictionary", {}).get("returnCode") == 0
                     and wall_patch_is_wall(case_dir))
    started_solver = False
    if mesh_pass and wall_pass and all(
        command_results.get(name, {}).get("returnCode") == 0
        for name in ("gmshToFoam", "changeDictionary", "checkMesh")
    ):
        remaining = int(cfg["runner"]["runnerBudgetSeconds"] - (time.monotonic() - runner_start))
        if remaining >= 25:
            started_solver = True
            command_results["rhoSimpleFoam"] = run_logged(
                ["rhoSimpleFoam"], case_dir,
                min(max_case_seconds, remaining - 8),
                case_dir / command_logs["rhoSimpleFoam"], env,
            )
        else:
            command_results["rhoSimpleFoam"] = {
                "returnCode": None, "notRun": True, "reason": "runner time cap"
            }

    solver_log_path = case_dir / "solver.log"
    solver_text = solver_log_path.read_text(encoding="utf-8", errors="replace") if solver_log_path.exists() else ""
    final_residuals = residuals(solver_text)
    targets = cfg["solver"]["residualTargets"]
    energy = min(final_residuals.get("T", math.inf), final_residuals.get("h", math.inf))
    residual_ok = (
        final_residuals.get("p", math.inf) <= float(targets["p"])
        and final_residuals.get("U", math.inf) <= float(targets["U"])
        and energy <= float(targets["energy"])
        and final_residuals.get("k", math.inf) <= float(targets["k"])
        and final_residuals.get("omega", math.inf) <= float(targets["omega"])
    )
    solver_result = command_results.get("rhoSimpleFoam", {})
    solver_completed = (
        started_solver and solver_result.get("returnCode") == 0
        and not solver_result.get("timedOut") and re.search(r"\bEnd\b", solver_text) is not None
    )
    pressure = latest_total_pressures(case_dir, cfg_local)
    recovery_history = pressure["recoveryHistory"]
    recovery = pressure["latest"]["branchRecovery"] if pressure["latest"] else None
    stability_count = int(cfg["solver"]["recoveryStabilityWindowIterations"])
    stable_history = recovery_history[-stability_count:]
    recovery_stability = None
    if len(stable_history) == stability_count:
        values = [entry["branchRecovery"] for entry in stable_history]
        recovery_stability = (max(values) - min(values)) / max(abs(sum(values) / len(values)), 1e-12)
    recovery_stable = (
        recovery_stability is not None
        and recovery_stability <= float(cfg["solver"]["recoveryStabilityLimitFraction"])
    )
    flow_in = massflow_last(case_dir, "inletMassFlow")
    flow_out = massflow_last(case_dir, "outletMassFlow")
    inlet_flow = abs(flow_in[1]) if flow_in else None
    outlet_flow = abs(flow_out[1]) if flow_out else None
    imbalance = (
        abs(inlet_flow - outlet_flow) / max((inlet_flow + outlet_flow) / 2.0, 1e-12)
        if inlet_flow is not None and outlet_flow is not None else None
    )
    mass_ok = imbalance is not None and imbalance <= float(
        cfg["solver"]["massImbalanceLimitFraction"]
    )
    target_mdot = float(case["targetMassFlowKgPerS"])
    flow_error = abs(outlet_flow - target_mdot) / target_mdot if outlet_flow is not None else None
    target_flow_ok = flow_error is not None and flow_error <= float(
        cfg["solver"]["meanlineMassFlowToleranceFraction"]
    )
    converged = all((
        solver_completed, residual_ok, recovery_stable, mass_ok, target_flow_ok,
        mesh_pass, wall_pass, recovery is not None,
    ))
    retain_case_evidence(case_dir, output_dir)
    if converged:
        status = "converged"
    elif not mesh_pass:
        status = "checkMesh_failed_or_not_run"
    elif not solver_completed:
        status = "solver_failed_timed_out_or_incomplete"
    else:
        status = "solver_completed_not_converged"
    return {
        "caseId": case["caseId"],
        "turnRadiusM": case["turnRadiusM"],
        "transitionProfile": case["transitionProfile"],
        "meshLevel": case["meshLevel"],
        "gmshCells": case["meshEvidence"]["volumeCells"],
        "gmshMinSICN": case["meshEvidence"]["minSICN"],
        "targetMassFlowKgPerS": target_mdot,
        "inletMassFlowKgPerS": inlet_flow,
        "outletMassFlowKgPerS": outlet_flow,
        "massImbalanceFraction": imbalance,
        "meanlineMassFlowErrorFraction": flow_error,
        "outletStaticPressureBoundaryPa": case["outletStaticPressurePa"],
        "inletTotalPressureFromSolutionPa": pressure["latest"]["inletTotalPressurePa"] if pressure["latest"] else None,
        "outletTotalPressureFromSolutionPa": pressure["latest"]["outletTotalPressurePa"] if pressure["latest"] else None,
        "pressureRecovery": recovery,
        "freestreamPressureRecovery": pressure["latest"]["freestreamRecovery"] if pressure["latest"] else None,
        "recoveryHistory": recovery_history,
        "recoveryStabilityFraction": recovery_stability,
        "recoveryStabilityPass": recovery_stable,
        "finalResiduals": final_residuals,
        "solverCompleted": solver_completed,
        "residualTargetsPass": residual_ok,
        "meshCheckPass": mesh_pass,
        "wallPatchTypePass": wall_pass,
        "massBalancePass": mass_ok,
        "meanlineMassFlowPass": target_flow_ok,
        "converged": converged,
        "status": status,
        "commandResults": command_results,
        "startedAtUtc": utc_string(case_start),
        "finishedAtUtc": utc_string(),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields = [
        "caseId", "turnRadiusM", "meshLevel", "gmshCells", "gmshMinSICN",
        "targetMassFlowKgPerS", "outletMassFlowKgPerS", "massImbalanceFraction",
        "meanlineMassFlowErrorFraction", "inletTotalPressureFromSolutionPa",
        "outletTotalPressureFromSolutionPa", "pressureRecovery", "freestreamPressureRecovery",
        "recoveryStabilityPass", "solverCompleted", "residualTargetsPass", "meshCheckPass",
        "wallPatchTypePass", "converged", "status",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--instance-name", default=os.environ.get("PHASE13_INSTANCE_NAME", "unknown"))
    parser.add_argument("--vm-created-at", default=os.environ.get("PHASE13_VM_CREATED_AT"))
    parser.add_argument("--runner-budget-seconds", type=int)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    budget = min(
        int(args.runner_budget_seconds or cfg["runner"]["runnerBudgetSeconds"]),
        int(cfg["runner"]["runnerBudgetSeconds"]),
    )
    cfg["runner"]["runnerBudgetSeconds"] = budget
    runner_start = time.monotonic()
    started_at = utc_now()
    records: list[dict[str, Any]] = []
    case_dirs = [args.case_root / name for name in cfg["runner"]["caseOrder"]]
    stop = False
    for index, case_dir in enumerate(case_dirs):
        if time.monotonic() - runner_start >= budget or stop:
            for pending in case_dirs[index:]:
                records.append({"caseId": pending.name, "status": "not_started_time_cap_or_prior_failure",
                                "converged": False, "pressureRecovery": None})
            break
        try:
            record = run_case(case_dir, cfg, runner_start, args.output)
        except Exception as exc:
            record = {
                "caseId": case_dir.name, "status": "worker_driver_error",
                "error": f"{type(exc).__name__}: {exc}", "converged": False,
                "pressureRecovery": None,
            }
            retain_case_evidence(case_dir, args.output)
        records.append(record)
        if not record.get("converged"):
            stop = True

    converged = [record for record in records if record.get("converged")]
    selected = max(converged, key=lambda record: record["pressureRecovery"], default=None)
    finished_at = utc_now()
    vm_duration = None
    if args.vm_created_at:
        try:
            created = datetime.fromisoformat(args.vm_created_at.replace("Z", "+00:00"))
            vm_duration = max(0.0, (finished_at - created).total_seconds())
        except ValueError:
            pass
    result = {
        "phase": cfg.get("phase", 13),
        "status": "completed" if len(converged) == len(cfg["cases"]) else "partial_or_unconverged",
        "runSource": "one_ephemeral_GCE_Spot_OpenFOAM_worker",
        "instanceName": args.instance_name,
        "solver": cfg["solver"]["family"],
        "turbulenceModel": cfg["solver"]["turbulenceModel"],
        "startedAtUtc": utc_string(started_at),
        "finishedAtUtc": utc_string(finished_at),
        "runnerElapsedSeconds": time.monotonic() - runner_start,
        "observedVmDurationAtWorkerFinishSeconds": vm_duration,
        "records": records,
        "selectedRecovery": selected,
        "evidenceClass": "Real OpenFOAM checkMesh and rhoSimpleFoam solution-field evidence; convergence requires residual, stability, flow, and mass-balance checks",
    }
    (args.output / "phase13_solver_receipt.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(args.output / "phase13_solver_results.csv", records)
    print(json.dumps({
        "status": result["status"], "caseCount": len(records),
        "convergedCount": len(converged), "selectedRecovery": selected,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
