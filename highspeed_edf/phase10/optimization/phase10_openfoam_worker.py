#!/usr/bin/env python3
"""Run prepared phase-10 OpenFOAM cases and retain solver evidence."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
RESIDUAL_RE = re.compile(r"Solving for ([A-Za-z][A-Za-z0-9_]*), Initial residual = " + NUMBER + r", Final residual = (" + NUMBER + r")")
UTC = timezone.utc


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def run_command(args: list[str], cwd: Path, timeout: int, log_path: Path, env: dict[str, str]) -> dict[str, Any]:
    start = time.monotonic()
    try:
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False)
        output = result.stdout + ("\n--- STDERR ---\n" + result.stderr if result.stderr else "")
        log_path.write_text(output, encoding="utf-8", errors="replace")
        return {"returnCode": result.returncode, "timedOut": False, "elapsedSeconds": time.monotonic() - start}
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        log_path.write_text(str(stdout) + "\n--- TIMEOUT ---\n" + str(stderr), encoding="utf-8")
        return {"returnCode": None, "timedOut": True, "elapsedSeconds": time.monotonic() - start}


def last_data_line(path: Path) -> str | None:
    if not path.exists():
        return None
    candidates = []
    for item in path.rglob("surfaceFieldValue.dat"):
        for line in item.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                candidates.append(stripped)
    return candidates[-1] if candidates else None


def numeric_tokens(line: str | None) -> list[float] | None:
    if line is None:
        return None
    values = re.findall(NUMBER, line)
    try:
        return [float(value) for value in values]
    except ValueError:
        return None


def patch_average(case_dir: Path, name: str) -> dict[str, float] | None:
    tokens = numeric_tokens(last_data_line(case_dir / "postProcessing" / name))
    # surfaceFieldValue's p/U/T weighted-average row is time, p, (Ux Uy Uz), T.
    if not tokens or len(tokens) < 6:
        return None
    return {"time": tokens[0], "pPa": tokens[1], "Ux": tokens[2], "Uy": tokens[3], "Uz": tokens[4], "TK": tokens[5]}


def patch_sum(case_dir: Path, name: str) -> float | None:
    tokens = numeric_tokens(last_data_line(case_dir / "postProcessing" / name))
    return tokens[-1] if tokens and len(tokens) >= 2 else None


def total_pressure(avg: dict[str, float] | None, gamma: float, gas_r: float) -> float | None:
    if not avg or avg["pPa"] <= 0 or avg["TK"] <= 0:
        return None
    speed2 = avg["Ux"] ** 2 + avg["Uy"] ** 2 + avg["Uz"] ** 2
    mach2 = speed2 / (gamma * gas_r * avg["TK"])
    return avg["pPa"] * (1.0 + 0.5 * (gamma - 1.0) * mach2) ** (gamma / (gamma - 1.0))


def residuals(log: str) -> dict[str, float]:
    latest: dict[str, float] = {}
    for field, value in RESIDUAL_RE.findall(log):
        key = "U" if field.startswith("U") else field
        latest[key] = max(latest.get(key, 0.0), float(value))
    return latest


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def retain_case_logs(case_dir: Path, output_dir: Path) -> None:
    target = output_dir / "caseLogs" / case_dir.name
    target.mkdir(parents=True, exist_ok=True)
    for name in ("gmshToFoam.log", "changeDictionary.log", "checkMesh.log", "solver.log"):
        source = case_dir / name
        if source.exists():
            (target / name).write_bytes(source.read_bytes())


def run_case(case_dir: Path, cfg: dict[str, Any], started_monotonic: float, total_budget_s: int, output_dir: Path) -> dict[str, Any]:
    started_at = utc_now()
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    max_case_s = int(cfg["solver"]["maxSecondsPerCase"])
    remaining = total_budget_s - int(time.monotonic() - started_monotonic)
    if remaining < 45:
        return {"caseId": case["caseId"], "status": "not_started_time_cap", "startedAtUtc": started_at}
    timeout = min(max_case_s, remaining - 20)
    env = dict(os.environ)
    commands = [
        (["gmshToFoam", "mesh.msh"], "gmshToFoam.log"),
        (["changeDictionary", "-constant"], "changeDictionary.log"),
        (["checkMesh", "-constant", "-allGeometry", "-allTopology"], "checkMesh.log"),
        (["rhoSimpleFoam"], "solver.log"),
    ]
    command_results: dict[str, Any] = {}
    for args, logfile in commands:
        result = run_command(args, case_dir, timeout, case_dir / logfile, env)
        command_results[args[0]] = result
        if result["returnCode"] != 0 or result["timedOut"]:
            break
        if args[0] == "checkMesh":
            check_output = (case_dir / logfile).read_text(encoding="utf-8", errors="replace")
            failed_checks = re.search(r"Failed\s+(\d+)\s+mesh checks", check_output)
            if failed_checks and int(failed_checks.group(1)) > 0:
                result["qualityChecksFailed"] = int(failed_checks.group(1))
                break

    retain_case_logs(case_dir, output_dir)
    solver_log_path = case_dir / "solver.log"
    solver_log = solver_log_path.read_text(encoding="utf-8", errors="replace") if solver_log_path.exists() else ""
    check_log_path = case_dir / "checkMesh.log"
    check_log = check_log_path.read_text(encoding="utf-8", errors="replace") if check_log_path.exists() else ""
    r = residuals(solver_log)
    criteria = cfg["solver"]["residualTargets"]
    residual_ok = all(r.get(field, math.inf) <= float(criteria[field]) for field in ("p", "U", "k", "omega"))
    energy_residual = min(r.get("T", math.inf), r.get("h", math.inf))
    residual_ok = residual_ok and energy_residual <= float(criteria["energy"])
    solver_completed = command_results.get("rhoSimpleFoam", {}).get("returnCode") == 0 and "End" in solver_log
    avg_out = patch_average(case_dir, "outletAverage")
    avg_in = patch_average(case_dir, "inletAverage")
    p0_in = total_pressure(avg_in, float(cfg["operatingPoint"]["gamma"]), float(cfg["operatingPoint"]["gasConstantJPerKgK"]))
    p0_out = total_pressure(avg_out, float(cfg["operatingPoint"]["gamma"]), float(cfg["operatingPoint"]["gasConstantJPerKgK"]))
    recovery = p0_out / float(case["totalPressurePa"]) if p0_out else None
    m_in = patch_sum(case_dir, "inletMassFlow")
    m_out = patch_sum(case_dir, "outletMassFlow")
    mass_imbalance = (
        abs(abs(m_in) - abs(m_out)) / max((abs(m_in) + abs(m_out)) / 2.0, 1e-12)
        if m_in is not None and m_out is not None else None
    )
    mass_ok = mass_imbalance is not None and mass_imbalance <= float(cfg["solver"]["massImbalanceLimitFraction"])
    target_flow = float(case["targetMassFlowKgPerS"])
    flow_error = abs(abs(m_out) - target_flow) / target_flow if m_out is not None else None
    target_flow_ok = flow_error is not None and flow_error <= float(cfg["solver"]["meanlineMassFlowToleranceFraction"])
    mesh_command = command_results.get("checkMesh", {})
    mesh_ok = mesh_command.get("returnCode") == 0 and not mesh_command.get("qualityChecksFailed") and "Failed" not in check_log
    converged = solver_completed and residual_ok and mass_ok and target_flow_ok and mesh_ok and recovery is not None
    return {
        "caseId": case["caseId"],
        "bendRadiusM": case.get("bendRadiusM", case.get("turnRadiusM")),
        "contractionProfile": case["contractionProfile"], "meshLevel": case["meshLevel"],
        "meshCells": case.get("meshEvidence", {}).get("tetraCellCount"),
        "targetMassFlowKgPerS": case["targetMassFlowKgPerS"],
        "inletMassFlowKgPerS": abs(m_in) if m_in is not None else None,
        "outletMassFlowKgPerS": abs(m_out) if m_out is not None else None,
        "massImbalanceFraction": mass_imbalance,
        "meanlineMassFlowErrorFraction": flow_error,
        "meanlineMassFlowPass": target_flow_ok,
        "outletTotalPressurePa": p0_out,
        "freestreamTotalPressurePa": case["totalPressurePa"],
        "pressureRecovery": recovery,
        "finalResiduals": r,
        "solverCompleted": solver_completed,
        "residualTargetsPass": residual_ok,
        "meshCheckPass": mesh_ok,
        "massBalancePass": mass_ok,
        "converged": converged,
        "status": "converged" if converged else (
            "mesh_quality_gate_failed" if mesh_command.get("qualityChecksFailed")
            else ("solver_completed_not_converged" if solver_completed else "solver_failed_or_timed_out")
        ),
        "commandResults": command_results,
        "startedAtUtc": started_at, "finishedAtUtc": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--instance-name", default=os.environ.get("PHASE10_INSTANCE_NAME", "unknown"))
    parser.add_argument("--run-budget-seconds", type=int, default=300)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    started_at = utc_now()
    records = []
    for case_dir in sorted(p for p in args.case_root.iterdir() if p.is_dir()):
        if time.monotonic() - start > args.run_budget_seconds:
            records.extend({"caseId": p.name, "status": "not_started_time_cap"} for p in sorted(args.case_root.iterdir()) if p.is_dir() and p.name not in {r.get("caseId") for r in records})
            break
        try:
            records.append(run_case(case_dir, cfg, start, args.run_budget_seconds, args.output))
        except Exception as exc:
            retain_case_logs(case_dir, args.output)
            records.append({"caseId": case_dir.name, "status": "driver_error", "error": f"{type(exc).__name__}:{exc}"})
    medium = [r for r in records if r.get("meshLevel") == "medium" and r.get("pressureRecovery") is not None]
    best = max((r for r in medium if r.get("converged")), key=lambda r: r["pressureRecovery"], default=None)
    grid_ids = set(cfg["solver"].get(
        "gridConvergenceCaseIds",
        ["r225_linear_coarse", "r225_linear_medium", "r225_linear_fine"],
    ))
    grid = {r.get("meshLevel"): r for r in records if r.get("caseId") in grid_ids}
    grid_delta = None
    if grid.get("medium", {}).get("pressureRecovery") is not None and grid.get("fine", {}).get("pressureRecovery") is not None:
        grid_delta = abs(grid["medium"]["pressureRecovery"] - grid["fine"]["pressureRecovery"])
    grid_pass = grid_delta is not None and grid_delta <= float(cfg["solver"]["pressureRecoveryGridAgreementLimitFraction"])
    result = {
        "phase": cfg.get("phase", 10), "status": "completed" if all(r.get("converged") for r in records) and grid_pass else "partial_or_unconverged",
        "runSource": "one_ephemeral_GCE_Spot_OpenFOAM_worker", "instanceName": args.instance_name,
        "solver": cfg["solver"]["family"], "turbulenceModel": cfg["solver"]["turbulenceModel"],
        "startedAtUtc": started_at, "finishedAtUtc": utc_now(),
        "elapsedSeconds": time.monotonic() - start, "records": records,
        "gridConvergence": {"referenceCaseIds": sorted(grid_ids), "mediumFineAbsoluteRecoveryDifference": grid_delta,
                            "agreementLimit": cfg["solver"]["pressureRecoveryGridAgreementLimitFraction"],
                            "passes": grid_pass},
        "bestGeometryAmongConvergedMediumCases": best,
        "evidenceClass": "OpenFOAM output; converged flag requires residual, mesh, mass-balance and pressure post-processing checks",
    }
    (args.output / "phase10_solver_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    rows = []
    for record in records:
        rows.append({key: record.get(key) for key in (
            "caseId", "bendRadiusM", "contractionProfile", "meshLevel", "meshCells",
            "targetMassFlowKgPerS", "outletMassFlowKgPerS", "massImbalanceFraction", "pressureRecovery",
            "meanlineMassFlowErrorFraction", "meanlineMassFlowPass", "solverCompleted", "residualTargetsPass",
            "meshCheckPass", "massBalancePass", "converged", "status")})
    write_rows(args.output / "phase10_solver_results.csv", rows)
    print(json.dumps({"status": result["status"], "cases": len(records), "best": best, "gridConvergence": result["gridConvergence"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
