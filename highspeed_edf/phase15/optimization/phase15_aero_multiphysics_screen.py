"""Run a bounded candidate screen through Aero Multiphysics Workbench.

Invoke with the workbench Python environment and its package roots on sys.path.
Results are explicitly analytical; they provide a workbench-owned candidate
record and do not replace the later native OpenFOAM/preCICE/CalculiX FSI run.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any


PHASE = Path(__file__).resolve().parents[1]
RESULTS = PHASE / "fsi" / "reports"
RESULTS.mkdir(parents=True, exist_ok=True)


def load_workbench(root: Path):
    sys.path[:0] = [str(path) for path in (root / "packages").glob("*") if path.is_dir()]
    sys.path.insert(0, str(root / "solvers"))
    from aeroworkbench_vehicle_systems import coupled_optimizer as co
    return co


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--workbench-root", required=True)
    args = parser.parse_args()
    workbench_root = Path(args.workbench_root).resolve()
    co = load_workbench(workbench_root)
    commit_probe = subprocess.run(["git", "-C", str(workbench_root), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=False)
    workbench_commit = commit_probe.stdout.strip() if commit_probe.returncode == 0 else None

    stock = (
        co.ManufacturingProfile("bar_16x50", 16.0, 50.0, "6061-T6", "cnc"),
        co.ManufacturingProfile("sheet_5x250x120", 5.0, 120.0, "6061-T6", "cnc"),
        co.ManufacturingProfile("sheet_5x300x120", 5.0, 120.0, "6061-T6", "cnc"),
    )
    motor = co.MotorInput(44.4, 60.0, 43.0, 47_000.0, 41_000.0, 0.90)
    battery = co.BatteryInput(44.4, 360.0)
    rows: list[dict[str, Any]] = []
    candidates = []
    for thickness_mm in (30.0, 36.0):
        design = co.CoupledDesign(
            fuselage_width_m=0.186,
            fuselage_height_m=0.088,
            inlet_diameter_m=0.082,
            blade_chord_m=0.016,
            blade_pitch_deg=30.0,
            body_length_m=0.640,
            body_superellipse_exponent=2.6,
            lifting_body_planform_area_m2=0.19,
            lifting_body_span_m=0.520,
            lifting_body_taper_ratio=305.0 / 425.0,
            lifting_body_thickness_ratio=thickness_mm / 365.0,
            lifting_body_sweep_deg=25.0,
            lifting_body_tip_twist_deg=0.0,
            propulsor_hub_ratio=0.50,
            blade_count=12.0,
            stator_count=21.0,
            rotor_axial_spacing_m=0.036,
        )
        request = co.CoupledOptimizationRequest(
            initial=design,
            motor=motor,
            battery=battery,
            aircraft_mass_kg=6.541,
            wing_area_m2=0.19,
            air_density_kg_m3=0.909,
            airframe_family="lifting_body",
            body_role="lifting_body",
            propulsion_adapter="ideal_edf",
            propulsion_family="edf",
            propulsor_placement="tractor",
            propulsor_ducted=True,
            propulsor_stator=True,
            target_speed_kmh=720.0,
            required_speed_kmh=650.0,
            minimum_thrust_to_weight=1.0,
            maximum_tip_mach=0.80,
            manufacturing_profiles=stock,
            preferred_stock_profile="bar_16x50",
            max_iterations=4,
        )
        evaluated = co.evaluate_coupled_design(request, design)
        candidate = {
            "id": f"wing_t{int(thickness_mm):02d}mm",
            "maxThicknessMm": thickness_mm,
            "workbenchFidelity": evaluated.fidelity,
            "feasible": evaluated.feasible,
            "frontalAreaM2": evaluated.frontal_area_m2,
            "thrustToWeight": evaluated.thrust_to_weight,
            "tipMach": evaluated.propulsor_tip_mach,
            "gates": dict(evaluated.gates),
            "gateMargins": dict(evaluated.gate_margins),
            "geometry": evaluated.airframe_geometry.canonical_payload(),
            "inputHash": evaluated.provenance.inputs_hash,
            "nativeSolverEvidence": False,
        }
        candidates.append(candidate)
        rows.append({key: candidate[key] for key in (
            "id", "maxThicknessMm", "workbenchFidelity", "feasible", "frontalAreaM2",
            "thrustToWeight", "tipMach", "inputHash", "nativeSolverEvidence")})

    handoff = PHASE / "results" / "phase15_low_cost_handoff.json"
    payload = {
        "workbench": "aero-multiphysics-workbench",
        "workbenchRoot": str(workbench_root),
        "workbenchCoupledOptimizerModule": "aeroworkbench_vehicle_systems.coupled_optimizer",
        "workbenchCommit": workbench_commit,
        "handoffSha256": hashlib.sha256(handoff.read_bytes()).hexdigest() if handoff.exists() else None,
        "status": "SCREENED; FSI candidates passed to native OpenFOAM/preCICE/CalculiX workflow",
        "physicsSource": "analytical ideal-annular-actuator-disk screening; no high-cost SLSQP promotion",
        "highCostOptimizerAttempt": {
            "status": "NOT_CONVERGED_WITHIN_600S",
            "solver": "Aero Multiphysics Workbench OpenMDAO/SLSQP coupled optimizer",
            "observedMessages": ["Iteration limit reached", "Positive directional derivative for linesearch"],
            "candidatePromoted": False,
        },
        "candidates": candidates,
        "promotedGeometry": None,
        "promotionPolicy": "No candidate is promoted by this analytical stage; native coupled response, mesh gates, structural limits and manufacturability are required.",
    }
    (RESULTS / "phase15_aero_multiphysics_candidates.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with (RESULTS / "phase15_aero_multiphysics_candidates.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"status": payload["status"],
                      "candidateCount": len(candidates),
                      "fidelities": [c["workbenchFidelity"] for c in candidates],
                      "nativeSolverEvidence": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
