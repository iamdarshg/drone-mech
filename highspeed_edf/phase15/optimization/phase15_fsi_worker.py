#!/usr/bin/env python3
"""Run the pre-generated Phase-15 OpenFOAM/preCICE/CalculiX cases on one VM."""

from __future__ import annotations

import argparse
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


def now() -> str:
    return datetime.now(UTC).isoformat()


def run_logged(command: list[str], cwd: Path, env: dict[str, str],
               timeout: int, log: Path) -> dict[str, Any]:
    start = time.monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=timeout, check=False)
        log.write_text((result.stdout or "") + "\n--- STDERR ---\n" +
                       (result.stderr or ""), encoding="utf-8", errors="replace")
        return {"returnCode": result.returncode,
                "elapsedSeconds": round(time.monotonic() - start, 3),
                "timedOut": False}
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        log.write_text(stdout + "\n--- STDERR ---\n" + stderr + "\nTIMEOUT\n",
                       encoding="utf-8", errors="replace")
        return {"returnCode": None, "elapsedSeconds": round(time.monotonic() - start, 3),
                "timedOut": True}


def terminate(process: subprocess.Popen, grace_s: int = 8) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, AttributeError):
        process.terminate()
    try:
        process.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, AttributeError):
            process.kill()
        process.wait()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def parse_tip_displacements(path: Path) -> dict[str, float] | None:
    """Read the final CalculiX *NODE PRINT table for the NSET=TIP nodes."""
    text = read_text(path)
    rows: list[tuple[float, float, float]] = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 4 or not fields[0].isdigit():
            continue
        try:
            values = [float(v.replace("D", "E")) for v in fields[1:4]]
        except ValueError:
            continue
        rows.append((values[0], values[1], values[2]))
    if not rows:
        return None
    max_abs = max(math.sqrt(x*x + y*y + z*z) for x, y, z in rows)
    mean = tuple(sum(row[i] for row in rows) / len(rows) for i in range(3))
    return {"tipNodeCount": len(rows), "maxTipDisplacementM": max_abs,
            "meanTipDxM": mean[0], "meanTipDyM": mean[1], "meanTipDzM": mean[2]}


def coupled_run(fluid: Path, solid: Path, env: dict[str, str], timeout_s: int,
                output_logs: Path) -> dict[str, Any]:
    fluid_log = output_logs / "rhoPimpleFoam.log"
    solid_log = output_logs / "ccx_preCICE.log"
    start = time.monotonic()
    with fluid_log.open("w", encoding="utf-8", errors="replace") as f_log:
        fluid_proc = subprocess.Popen(["rhoPimpleFoam"], cwd=fluid, env=env,
                                      stdout=f_log, stderr=subprocess.STDOUT,
                                      start_new_session=True)
        time.sleep(1.0)
        with solid_log.open("w", encoding="utf-8", errors="replace") as s_log:
            try:
                solid_proc = subprocess.Popen(
                    ["ccx_preCICE", "-i", "wing", "-precice-participant", "Solid"],
                    cwd=solid, env=env, stdout=s_log, stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except OSError as exc:
                terminate(fluid_proc)
                return {"status": "solid_start_failed", "error": str(exc),
                        "elapsedSeconds": round(time.monotonic() - start, 3)}

            timed_out = False
            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                fluid_rc, solid_rc = fluid_proc.poll(), solid_proc.poll()
                if fluid_rc is not None and solid_rc is not None:
                    break
                # An early nonzero exit in either solver leaves its peer blocked
                # in preCICE. Stop the peer rather than burning the full VM window.
                if fluid_rc not in (None, 0) or solid_rc not in (None, 0):
                    time.sleep(3.0)
                    if fluid_proc.poll() is None:
                        terminate(fluid_proc)
                    if solid_proc.poll() is None:
                        terminate(solid_proc)
                    break
                time.sleep(1.0)
            else:
                timed_out = True
                terminate(fluid_proc)
                terminate(solid_proc)
            fluid_rc, solid_rc = fluid_proc.poll(), solid_proc.poll()
    fluid_text, solid_text = read_text(fluid_log), read_text(solid_log)
    precice_markers = ["converged", "Converged", "completed", "Completed"]
    coupling_evidence = sum(fluid_text.count(marker) + solid_text.count(marker)
                            for marker in precice_markers)
    completed = (not timed_out and fluid_rc == 0 and solid_rc == 0
                 and "End" in fluid_text and coupling_evidence > 0)
    return {
        "status": "coupled_solvers_completed" if completed else
                 ("coupled_run_timeout" if timed_out else "coupled_solver_failed_or_not_converged"),
        "fluidReturnCode": fluid_rc, "solidReturnCode": solid_rc,
        "timedOut": timed_out, "elapsedSeconds": round(time.monotonic() - start, 3),
        "fluidReachedEnd": "End" in fluid_text,
        "preCICECompletionLogMarkers": coupling_evidence,
        "fluidLog": str(fluid_log.name), "solidLog": str(solid_log.name),
    }


def run_candidate(case_root: Path, output: Path, env: dict[str, str],
                  timeout_s: int) -> dict[str, Any]:
    candidate = case_root.name
    fluid, solid = case_root / "fluid", case_root / "solid"
    logs = output / candidate
    logs.mkdir(parents=True, exist_ok=True)
    mesh = run_logged(["gmshToFoam", "wing.msh"], fluid, env, 180,
                      logs / "gmshToFoam.log")
    if mesh["returnCode"] != 0 or mesh["timedOut"]:
        return {"candidate": candidate, "status": "gmshToFoam_failed", "meshConversion": mesh}
    # gmshToFoam tags every physical surface as a generic "patch"; wall
    # functions require the coupled wall (fsi) and the fixed root to be "wall".
    boundary_path = fluid / "constant" / "polyMesh" / "boundary"
    boundary_text = boundary_path.read_text(encoding="utf-8", errors="replace")
    boundary_text = re.sub(r"((?:\bfsi\b|\brootWall\b)\s*\{[^}]*?type\s+)patch\s*;",
                           r"\1wall;", boundary_text)
    boundary_path.write_text(boundary_text, encoding="utf-8")
    wall_types_set = {
        name: (re.search(rf"\b{name}\b\s*\{{[^}}]*?type\s+(\w+)\s*;", boundary_text, re.S) or [None, None])[1]
        for name in ("fsi", "rootWall")
    }
    if any(value != "wall" for value in wall_types_set.values()):
        return {"candidate": candidate, "status": "boundary_type_rewrite_failed",
                "meshConversion": mesh, "wallTypes": wall_types_set}
    check = run_logged(["checkMesh"], fluid, env, 180, logs / "checkMesh.log")
    check_text = read_text(logs / "checkMesh.log")
    check_pass = (check["returnCode"] == 0 and not check["timedOut"]
                  and "Mesh OK." in check_text
                  and not re.search(r"Failed\s+[1-9]\d*\s+mesh checks", check_text, re.I))
    if not check_pass:
        return {"candidate": candidate, "status": "remote_checkMesh_failed",
                "meshConversion": mesh, "checkMesh": check,
                "meshOkTextPresent": "Mesh OK." in check_text}

    coupled = coupled_run(fluid, solid, env, timeout_s, logs)
    tip = parse_tip_displacements(solid / "wing.dat")
    forces_files = sorted(fluid.glob("postProcessing/wingForces/*/forces.dat"))
    force_tail = read_text(forces_files[-1]).splitlines()[-1] if forces_files and read_text(forces_files[-1]).splitlines() else None
    preCICE_logs = [p for p in (fluid / "precice-Fluid.log", solid / "precice-Solid.log") if p.exists()]
    for path in (solid / "wing.dat", *forces_files, *preCICE_logs):
        if path.is_file():
            dest = logs / path.name
            if path.resolve() != dest.resolve():
                shutil.copy2(path, dest)
    return {"candidate": candidate, "status": coupled["status"],
            "meshConversion": mesh, "checkMesh": {**check, "passed": check_pass},
            "coupling": coupled, "tipDisplacement": tip,
            "forceHistoryLastLine": force_tail,
            "preciceLogFiles": [p.name for p in preCICE_logs]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-root", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--candidate-timeout-seconds", type=int, default=500)
    args = ap.parse_args()
    case_root, output = Path(args.case_root), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    for executable in ("gmshToFoam", "checkMesh", "rhoPimpleFoam", "ccx_preCICE"):
        if shutil.which(executable, path=env.get("PATH")) is None:
            raise RuntimeError(f"required FSI executable missing: {executable}")
    candidates = sorted(p for p in case_root.iterdir() if p.is_dir() and (p / "precice-config.xml").is_file())
    if not candidates:
        raise RuntimeError(f"no prepared candidate cases under {case_root}")
    results = []
    for candidate in candidates:
        print(f"FSI candidate start: {candidate.name}", flush=True)
        result = run_candidate(candidate, output, env, args.candidate_timeout_seconds)
        results.append(result)
        (output / f"{candidate.name}_receipt.json").write_text(json.dumps(result, indent=2) + "\n",
                                                                encoding="utf-8")
        print(json.dumps({"candidate": candidate.name, "status": result["status"]}), flush=True)
    all_complete = all(row["status"] == "coupled_solvers_completed" for row in results)
    receipt = {
        "phase": 15, "study": "GCP rhoPimpleFoam + preCICE + CalculiX wing-sector aeroelastic FSI",
        "generatedAtUtc": now(), "status": "all_candidates_completed" if all_complete else "one_or_more_candidates_incomplete",
        "evidenceClass": "coupled solver run receipt; component-only, geometry/material assumptions in casegen report",
        "candidateResults": results,
        "limitations": [
            "This is an isolated outboard wing-sector model, not the complete twin-EDF aircraft or rotor-jet interaction.",
            "Flow speed is 200 m/s (720 km/h) at the 3 km ISA density; turbulence wall resolution and y+ require additional assessment.",
            "The isotropic 10 GPa stiffness and 150 kg/m^3 density are equivalent laminate/core assumptions, not measured coupon properties.",
            "The local Mach is about 0.61; the compressible rhoPimpleFoam run is still a coarse unsteady RANS screening mesh.",
        ],
    }
    (output / "phase15_fsi_worker_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0 if all_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
