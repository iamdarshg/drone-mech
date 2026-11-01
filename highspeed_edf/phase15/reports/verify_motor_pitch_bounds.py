#!/usr/bin/env python3
"""Audit Phase-15 coaxial motor/rotor axial bounds in the pinned native STEP.

This reads the STEP with CadQuery/OpenCascade and writes a JSON bounds receipt.
It verifies model placement only; it does not establish real motor geometry,
physical collision, shaft fit, bearing arrangement, or a feasible drivetrain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import subprocess
import threading
import time

import cadquery as cq
import OCP

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
STEP = REPO / "highspeed_edf/deliverables/phase15_geometry/step/phase15_airframe_full_assembly.step"
GENERATOR = REPO / "highspeed_edf/phase15/optimization/phase15_generate_geometry.py"
EXPECTED_STEP = "9b83f3bfa5ea261c2055152c9fdd2147b9e16819634715c3c4ae23b45deae772"
EXPECTED_GENERATOR = "53353da1c6f46d8cd9df7431209946869c0984908b269fb94d01f25a1cfabd47"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def constant(source: str, name: str) -> str:
    match = re.search(rf"(?m)^{name}\s*=\s*([^#\n]+)", source)
    if not match:
        raise RuntimeError(f"Missing source constant {name}")
    return match.group(1).strip()


def parse_number(source: str, name: str) -> float:
    return float(constant(source, name))


def parse_tuple(source: str, name: str) -> list[float]:
    text = constant(source, name)
    return [float(v) for v in re.findall(r"[-+]?\d+(?:\.\d*)?", text)]


def interval_overlap(a: list[float], b: list[float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def _rss_kib(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (FileNotFoundError, ProcessLookupError, ValueError):
        pass
    return 0


def bounded_common_volume(left_name: str, right_name: str, *, left_dz: float, label: str,
                          timeout_s: float = 600.0, rss_limit_mib: int = 3072) -> dict:
    """Run one OCCT common in a fresh interpreter with wall-clock/RSS guards."""
    command = [sys.executable, str(Path(__file__).resolve()), "--boolean-task",
               "--left", left_name, "--right", right_name, "--left-dz", str(left_dz)]
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1)
    started = time.monotonic()
    deadline = started + timeout_s
    peak_rss_kib = 0
    status = "completed"
    output_chunks: list[str] = []
    reader = threading.Thread(target=lambda: output_chunks.append(child.stdout.read()), daemon=True)
    reader.start()
    while child.poll() is None:
        rss = _rss_kib(child.pid)
        peak_rss_kib = max(peak_rss_kib, rss)
        if rss > rss_limit_mib * 1024:
            status = "memory_limit_exceeded"
            child.terminate()
            break
        if time.monotonic() >= deadline:
            status = "timeout"
            child.terminate()
            break
        time.sleep(0.25)
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
    elapsed = time.monotonic() - started
    reader.join(timeout=5)
    output = "".join(output_chunks)
    result = None
    for line in reversed(output.splitlines()):
        try:
            result = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    record = {"label": label, "status": status, "elapsedSeconds": round(elapsed, 3),
              "wallClockLimitSeconds": timeout_s, "rssLimitMiB": rss_limit_mib,
              "observedPeakChildRssMiB": round(peak_rss_kib / 1024, 2), "exitCode": child.returncode}
    if status == "completed" and child.returncode == 0 and result and result.get("ok"):
        record["volumeMm3"] = result["volumeMm3"]
        record["stepSha256"] = result["stepSha256"]
    elif result and not result.get("ok"):
        record["status"] = "boolean_error"
        record["error"] = result.get("error")
    else:
        record["error"] = "No successful fresh-interpreter BRep common result was returned before process exit/guard termination."
        record["capturedOutputTail"] = output[-1200:]
    print(json.dumps({"nozzleBoolean": record}), flush=True)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "motor_pitch_bounds_20261101.json")
    parser.add_argument("--boolean-task", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--left", help=argparse.SUPPRESS)
    parser.add_argument("--right", help=argparse.SUPPRESS)
    parser.add_argument("--left-dz", type=float, default=0.0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.boolean_task:
        if not args.left or not args.right:
            parser.error("--boolean-task requires --left and --right")
        task_step_sha = sha256(STEP)
        if task_step_sha != EXPECTED_STEP:
            parser.error(f"STEP SHA mismatch: {task_step_sha}")
        task_assembly = cq.Assembly.importStep(str(STEP))
        task_indexed = {child.name: child.obj for child in task_assembly.children}
        left = task_indexed[args.left]
        if args.left_dz:
            left = left.translate(cq.Vector(0, 0, args.left_dz))
        right = task_indexed[args.right]
        try:
            print(json.dumps({"ok": True, "volumeMm3": float(left.intersect(right).Volume()),
                              "stepSha256": task_step_sha}), flush=True)
            return 0
        except BaseException as exc:
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                              "stepSha256": task_step_sha}), flush=True)
            return 2
    try:
        output_path = args.output.resolve().relative_to(REPO).as_posix()
    except ValueError:
        output_path = args.output.name
    step_sha = sha256(STEP)
    generator_sha = sha256(GENERATOR)
    if step_sha != EXPECTED_STEP:
        parser.error(f"STEP SHA mismatch: expected {EXPECTED_STEP}, got {step_sha}")
    if generator_sha != EXPECTED_GENERATOR:
        parser.error(f"generator SHA mismatch: expected {EXPECTED_GENERATOR}, got {generator_sha}")

    generator = GENERATOR.read_text(encoding="utf-8")
    rotor_z = parse_tuple(generator, "ROTOR_Z")
    stator_z = parse_tuple(generator, "STATOR_Z")
    rotor_chord = parse_number(generator, "ROTOR_CHORD")
    can_diameter = parse_number(generator, "MOTOR_CAN_D")
    can_length = parse_number(generator, "MOTOR_CAN_LENGTH")
    source = {
        "step": {"path": STEP.relative_to(REPO).as_posix(), "sha256": step_sha},
        "generator": {"path": GENERATOR.relative_to(REPO).as_posix(), "sha256": generator_sha},
        "cadqueryVersion": cq.__version__,
        "openCascadePythonVersion": OCP.__version__,
        "sourceConstants": {"ROTOR_Z_mm": rotor_z, "STATOR_Z_mm": stator_z, "ROTOR_CHORD_mm": rotor_chord,
                            "MOTOR_CAN_D_mm": can_diameter, "MOTOR_CAN_LENGTH_mm": can_length},
        "additionalAxialGeometry": "Generator constructs a 2.5 mm radius, 8 mm long coaxial cylinder from can_start−8 to can_start, fused to the 42 mm can. This 8 mm pilot/stub is included in each exported motor component BRep.",
    }

    assembly = cq.Assembly.importStep(str(STEP))
    indexed = {child.name: child.obj for child in assembly.children}
    motors = {}
    rotors = {}
    stators = {}
    for name, shape in indexed.items():
        if name.startswith(("motor_A_R", "motor_B_R")):
            bb = shape.BoundingBox()
            motors[name] = {
                "solids": len(shape.Solids()), "valid": bool(shape.isValid()),
                "boundsMm": {"x": [bb.xmin, bb.xmax], "y": [bb.ymin, bb.ymax], "z": [bb.zmin, bb.zmax]},
                "bboxExtentMm": [bb.xlen, bb.ylen, bb.zlen],
            }
        elif name.startswith(("duct_A_rotor_R", "duct_B_rotor_R")):
            bb = shape.BoundingBox()
            rotors[name] = {
                "solids": len(shape.Solids()), "valid": bool(shape.isValid()),
                "boundsMm": {"x": [bb.xmin, bb.xmax], "y": [bb.ymin, bb.ymax], "z": [bb.zmin, bb.zmax]},
            }
        elif name.startswith(("duct_A_stator_S", "duct_B_stator_S")):
            bb = shape.BoundingBox()
            stators[name] = {
                "solids": len(shape.Solids()), "valid": bool(shape.isValid()),
                "boundsMm": {"x": [bb.xmin, bb.xmax], "y": [bb.ymin, bb.ymax], "z": [bb.zmin, bb.zmax]},
            }
    if len(motors) != 6 or len(rotors) != 6 or len(stators) != 6:
        raise RuntimeError(f"Expected six motor, six rotor, and six stator assembly nodes, found {len(motors)}, {len(rotors)}, {len(stators)}")
    if any(not x["valid"] or x["solids"] != 1 for x in motors.values()):
        raise RuntimeError("A motor envelope is not one valid solid")

    pitch = rotor_z[1] - rotor_z[0]
    if any(abs((rotor_z[i + 1] - rotor_z[i]) - pitch) > 1e-8 for i in range(len(rotor_z) - 1)):
        raise RuntimeError("Rotor stations are not uniformly spaced")
    body_intervals = [[z + rotor_chord / 2, z + rotor_chord / 2 + can_length] for z in rotor_z]
    envelope_intervals = []
    for row, z in enumerate(rotor_z, start=1):
        a_name = next(n for n in motors if n.startswith(f"motor_A_R{row}_"))
        b_name = next(n for n in motors if n.startswith(f"motor_B_R{row}_"))
        for name in (a_name, b_name):
            bb = motors[name]["boundsMm"]["z"]
            envelope_intervals.append(bb)
    pair_rows = []
    motor_intersections = {"A": [], "B": []}
    for duct in ("A", "B"):
        for row0, row1 in ((0, 1), (1, 2), (0, 2)):
            n0 = next(n for n in indexed if n.startswith(f"motor_{duct}_R{row0 + 1}_"))
            n1 = next(n for n in indexed if n.startswith(f"motor_{duct}_R{row1 + 1}_"))
            v = float(indexed[n0].intersect(indexed[n1]).Volume())
            motor_intersections[duct].append({"pair": f"R{row0 + 1}-R{row1 + 1}", "commonBRepVolumeMm3": v})
    for row in range(2):
        pair_rows.append({
            "ductRowPair": f"R{row + 1}-R{row + 2}",
            "rotorStationPitchMm": rotor_z[row + 1] - rotor_z[row],
            "principalCanBodyIntervalsMm": [body_intervals[row], body_intervals[row + 1]],
            "principalCanBodyOverlapMm": interval_overlap(body_intervals[row], body_intervals[row + 1]),
            "fullMotorComponentIntervalsPerDuctMm": {
                "A": [motors[f"motor_A_R{row + 1}_3670_42x72_envelope"]["boundsMm"]["z"], motors[f"motor_A_R{row + 2}_3670_42x72_envelope"]["boundsMm"]["z"]],
                "B": [motors[f"motor_B_R{row + 1}_3670_42x72_envelope"]["boundsMm"]["z"], motors[f"motor_B_R{row + 2}_3670_42x72_envelope"]["boundsMm"]["z"]],
            },
            "fullMotorComponentBBoxOverlapMm": {
                "A": interval_overlap(motors[f"motor_A_R{row + 1}_3670_42x72_envelope"]["boundsMm"]["z"], motors[f"motor_A_R{row + 2}_3670_42x72_envelope"]["boundsMm"]["z"]),
                "B": interval_overlap(motors[f"motor_B_R{row + 1}_3670_42x72_envelope"]["boundsMm"]["z"], motors[f"motor_B_R{row + 2}_3670_42x72_envelope"]["boundsMm"]["z"]),
            },
            "fullMotorComponentCommonBRepVolumeMm3": {
                duct: next(r["commonBRepVolumeMm3"] for r in motor_intersections[duct] if r["pair"] == f"R{row + 1}-R{row + 2}")
                for duct in ("A", "B")
            },
        })

    by_duct = {}
    for duct in ("A", "B"):
        by_duct[duct] = {}
        for row in range(1, 4):
            name = next(n for n in motors if n.startswith(f"motor_{duct}_R{row}_"))
            by_duct[duct][f"R{row}"] = motors[name]["boundsMm"]["z"]
    min_envelope_extent = max(v["bboxExtentMm"][2] for v in motors.values())
    candidate_pitch = min_envelope_extent
    candidate_r3_shift = 2 * (candidate_pitch - pitch)
    nozzle_names = [n for n in indexed if n == "duct_A_separate_nozzle_and_exit_lip"]
    nozzle = indexed[nozzle_names[0]]
    nozzle_bb = nozzle.BoundingBox()
    candidate_nozzle_stages = []
    nozzle_boolean_guard_records = []
    for row in range(3):
        shift = row * (candidate_pitch - pitch)
        for stage_kind, names in (("rotor", rotors), ("stator", stators)):
            name = next(n for n in names if n.startswith(f"duct_A_{stage_kind}_R{row + 1}" if stage_kind == "rotor" else f"duct_A_stator_S{row + 1}"))
            moved = indexed[name].translate(cq.Vector(0, 0, shift))
            bb = moved.BoundingBox()
            z_overlap = interval_overlap([bb.zmin, bb.zmax], [nozzle_bb.zmin, nozzle_bb.zmax])
            if z_overlap > 0:
                boolean_record = bounded_common_volume(
                    name, "duct_A_separate_nozzle_and_exit_lip", left_dz=shift,
                    label=f"duct_A_{stage_kind}_R{row + 1}_vs_existing_nozzle",
                    timeout_s=600.0, rss_limit_mib=3072,
                )
                nozzle_boolean_guard_records.append(boolean_record)
                exact_common = boolean_record.get("volumeMm3")
            else:
                exact_common = 0.0
                nozzle_boolean_guard_records.append({
                    "label": f"duct_A_{stage_kind}_R{row + 1}_vs_existing_nozzle",
                    "status": "not_run_bbox_disjoint", "elapsedSeconds": 0.0,
                    "wallClockLimitSeconds": 600.0, "rssLimitMiB": 3072,
                    "observedPeakChildRssMiB": 0.0,
                })
            candidate_nozzle_stages.append({
                "stage": stage_kind, "row": row + 1, "sourceComponent": name,
                "axialShiftMm": shift, "movedZBoundsMm": [bb.zmin, bb.zmax],
                "nozzleZBoundsMm": [nozzle_bb.zmin, nozzle_bb.zmax],
                "axialBBoxOverlapMm": z_overlap,
                "commonBRepVolumeWithNozzleMm3": exact_common,
                "commonBRepGuardStatus": boolean_record["status"] if z_overlap > 0 else "not_run_bbox_disjoint",
            })
    candidate_nozzle_check = {
        "counterfactualUniformPitchMm": candidate_pitch,
        "R3ShiftMmFromCurrentR1Anchor": candidate_r3_shift,
        "currentNozzleBRepZBoundsMm": [nozzle_bb.zmin, nozzle_bb.zmax],
        "movedStages": candidate_nozzle_stages,
        "interpretation": "At the counterfactual 80 mm pitch, later rotor/stator rows occupy the same axial interval as the current nozzle BRep. The listed BRep common volumes screen only solid intersection. A zero result does not show aerodynamic compatibility, adequate clearance under load, thermal expansion, or an acceptable nozzle/rotor arrangement.",
    }
    receipt = {
        "schemaVersion": 1,
        "audit": "Phase-15 motor/rotor axial STEP bounds audit",
        "disposition": "BLOCKED_CURRENT_36MM_PITCH_EXCEEDS_NATIVE_STEP_MOTOR_ENVELOPE",
        "scope": "Native BRep placement/bounding-box comparison only. This does not certify real motor dimensions, physical collision, shaft fit, drivetrain feasibility, CFD, strength, or aircraft readiness.",
        "source": source,
        "motorComponents": motors,
        "rotorComponents": rotors,
        "stations": {
            "rotorStationOriginsMm": rotor_z,
            "rotorPitchesMm": [rotor_z[i + 1] - rotor_z[i] for i in range(len(rotor_z) - 1)],
            "motorComponentIntervalsByDuctMm": by_duct,
            "principalCanBodyIntervalsMm": body_intervals,
            "principalCanBodyOverlapForAdjacentStationsMm": [interval_overlap(body_intervals[i], body_intervals[i + 1]) for i in range(2)],
            "fullComponentBBoxOverlapForAdjacentStationsByDuctMm": {d: [interval_overlap(by_duct[d][f"R{i}"], by_duct[d][f"R{i+1}"]) for i in range(1, 3)] for d in ("A", "B")},
            "minimumCenterPitchForNoPrincipalCanBodyBBoxOverlapMm": can_length,
            "minimumCenterPitchForNoFullMotorComponentBBoxOverlapMm": min_envelope_extent,
            "increaseNeededFromCurrentPitchToSeparateFullMotorComponentBBoxesMm": min_envelope_extent - pitch,
            "thirdRotorShiftIfPitchChangedUniformlyFromR1AnchorMm": 2 * (min_envelope_extent - pitch),
            "currentContinuousDuctTubeZIntervalMm": [0.0, 110.0],
            "currentNozzleZIntervalMm": [110.0, 245.0],
            "rotorSolidZBoundsMm": {n: row["boundsMm"]["z"] for n, row in rotors.items()},
            "statorSolidZBoundsMm": {n: row["boundsMm"]["z"] for n, row in stators.items()},
            "counterfactualR3NozzleStationCheck": candidate_nozzle_check,
        },
        "adjacentStationPairs": pair_rows,
        "pairwiseMotorCommonVolumesByDuct": motor_intersections,
        "nozzleBooleanGuard": {"perBooleanTimeoutSeconds": 600, "perBooleanChildRssLimitMiB": 3072,
                                "records": nozzle_boolean_guard_records},
        "interpretation": [
            "The named 42x72 motor can body is 72 mm long, but each exported motor component BRep includes an 8 mm radius-2.5 mm coaxial pilot/stub, so its native Z bounding extent is 80 mm.",
            "At the current 36 mm rotor pitch, principal can bodies overlap by 36 mm; full component bounding intervals overlap by 44 mm between adjacent rows. The nonadjacent R1/R3 full intervals overlap by 8 mm from the stub extension.",
            "A uniform 80 mm pitch is the smallest axial pitch that separates the full component bounding intervals in this model, requiring +44 mm per inter-row pitch and shifting R3 +88 mm if R1 stays fixed. Later rotor/stator rows then occupy the current 110..245 mm nozzle axial interval; the nozzle BRep intersection check is reported separately and does not validate the changed flowpath.",
            "No smaller sourced motor/drive package or authoritative motor drawing is present in the repository. Translating only the motor envelopes would require an unmodeled shaft/gear arrangement and is not an evidence-backed compatibility fix.",
        ],
        "outputPath": output_path,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stepSha256": step_sha, "generatorSha256": generator_sha,
                      "motorNodeCount": len(motors), "rotorNodeCount": len(rotors),
                      "currentPitchMm": pitch, "canBodyOverlapMm": receipt["stations"]["principalCanBodyOverlapForAdjacentStationsMm"],
                      "fullEnvelopeOverlapMm": receipt["stations"]["fullComponentBBoxOverlapForAdjacentStationsByDuctMm"],
                      "minimumNoEnvelopeOverlapPitchMm": min_envelope_extent,
                      "thirdRotorShiftMm": receipt["stations"]["thirdRotorShiftIfPitchChangedUniformlyFromR1AnchorMm"],
                      "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
