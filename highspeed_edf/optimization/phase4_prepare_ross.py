#!/usr/bin/env python3
"""Build and validate governed ROSS Campbell inputs; does not submit jobs."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def main() -> None:
    study = Path(__file__).resolve().parents[1]
    workbench = Path(r"D:\CodeProjects\aero-multiphysics-workbench")
    sys.path.insert(0, str(workbench))
    sys.path.insert(0, str(workbench / "solvers"))
    for package in (workbench / "packages").glob("*"):
        if package.is_dir():
            sys.path.insert(0, str(package))
    from aeroworkbench_dynamics import normalize_forcing_lines, normalize_rotor_model

    assumptions_path = study / "configs" / "phase4_ross_assumptions.json"
    phase3_path = study / "results" / "phase3_meanline_rows.csv"
    assumptions = json.loads(assumptions_path.read_text(encoding="utf-8"))
    with phase3_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rotor_rows = {
        row["row_id"]: row for row in rows if row["row_kind"] == "rotor" and row["speed_kmh"] == "700"
    }
    phase3_config = json.loads((study / "configs" / "phase3_meanline.json").read_text(encoding="utf-8"))
    rotor_defs = phase3_config["rotorRows"]
    stator_defs = {row["id"]: row for row in phase3_config["statorRows"]}
    shaft = assumptions["shaft"]
    disk = assumptions["equivalentFanDisk"]
    bearing = assumptions["bearings"]
    effects = assumptions["effects"]
    all_jobs: list[dict[str, Any]] = []
    for definition in rotor_defs:
        row_id = definition["id"]
        blade = int(definition["bladeCount"])
        vane = int(stator_defs[definition["statorId"]]["vaneCount"])
        rotor_rpm = float(rotor_rows[row_id]["rotor_rpm"])
        shaft_segments = [
            {
                "length_m": float(shaft["lengthM"]) / int(shaft["segments"]),
                "outer_diameter_m": float(shaft["outerDiameterM"]),
                "inner_diameter_m": 0.0,
            }
            for _ in range(int(shaft["segments"]))
        ]
        forcings = [
            {"source": "highspeed-edf-phase4", "label": "1x rotation", "order": 1, "speed_dependence": "order", "harmonic_family": "synchronous"},
            {"source": "highspeed-edf-phase4", "label": f"{row_id} rotor blade passing", "order": blade, "speed_dependence": "order", "harmonic_family": "blade-passing"},
            {"source": "highspeed-edf-phase4", "label": f"{row_id} stator passing", "order": vane, "speed_dependence": "order", "harmonic_family": "stator-passing"},
            {"source": "drone-arm-FA4119-14pole", "label": "electrical fundamental", "order": 7, "speed_dependence": "order", "harmonic_family": "electrical"},
            {"source": "drone-arm-FA4119-14pole", "label": "electrical sixth harmonic/torque-ripple proxy", "order": 42, "speed_dependence": "order", "harmonic_family": "torque-ripple"},
            {"source": "drone-arm-controller-PWM", "label": "PWM 20 kHz", "frequency_hz": 20000, "speed_dependence": "fixed", "harmonic_family": "switching"},
            {"source": "drone-arm-controller-PWM", "label": "PWM 40 kHz", "frequency_hz": 40000, "speed_dependence": "fixed", "harmonic_family": "switching"},
        ]
        model: dict[str, Any] = {
            "analysis": "campbell",
            "material": {
                "name": shaft["material"],
                "youngs_modulus_pa": shaft["youngsModulusPa"],
                "shear_modulus_pa": shaft["shearModulusPa"],
                "density_kg_m3": shaft["densityKgM3"],
                "poisson_ratio": 0.3,
            },
            "segments": shaft_segments,
            "disks": [{
                "position": int(disk["positionNode"]),
                "outer_diameter_m": disk["outerDiameterM"],
                "inner_diameter_m": disk["innerDiameterM"],
                "width_m": disk["nominalWidthM"],
            }],
            "bearings": [
                {
                    "node": node,
                    "kxx": bearing["nominalRadialStiffnessNPerM"],
                    "kyy": bearing["nominalRadialStiffnessNPerM"],
                    "cxx": bearing["nominalRadialDampingNsPerM"],
                    "cyy": bearing["nominalRadialDampingNsPerM"],
                }
                for node in bearing["positions"]
            ],
            "max_speed_rpm": rotor_rpm,
            "gyroscopic": effects["gyroscopic"],
            "shear_effects": effects["shearEffects"],
            "rotary_inertia": effects["rotaryInertia"],
            "forcings": forcings,
            "forcing_warning_margin_hz": effects["forcingWarningMarginHz"],
            "forcing_critical_margin_hz": effects["forcingCriticalMarginHz"],
        }
        normalized = normalize_rotor_model(model)
        normalized_forcings = normalize_forcing_lines(forcings)
        all_jobs.append({
            "jobId": f"phase4-{row_id.lower()}-campbell",
            "participantId": "rotor-campbell",
            "designRow": row_id,
            "maxSpeedRpm": rotor_rpm,
            "forcingsDeclared": len(normalized_forcings),
            "model": normalized.canonical_payload(),
            "forcings": [line.canonical_payload() for line in normalized_forcings],
            "inputs": {
                **normalized.canonical_payload(),
                "forcings": [line.canonical_payload() for line in normalized_forcings],
                "forcing_warning_margin_hz": effects["forcingWarningMarginHz"],
                "forcing_critical_margin_hz": effects["forcingCriticalMarginHz"],
            },
            "requestTemplate": {
                "participant_id": "rotor-campbell",
                "analysis": "campbell",
                "inputsKey": "inputs",
                "deferred": True,
            },
            "assumptions": [
                shaft["basis"],
                disk["materialApproximation"],
                bearing["basis"],
                "one rotor per stage represents left/right symmetric ducts; installation coupling omitted",
            ],
            "gcpEstimatedComputeShareUsd": assumptions["gcpPlan"]["plannedMaximumComputeCostUsd"] / len(rotor_defs),
        })
    plan = {
        "studyId": "highspeed-edf",
        "phase": 4,
        "status": "prepared-validated-not-submitted",
        "evidenceClass": "application-specific ROSS input plan; assumptions remain unverified",
        "gcpBrief": {
            "what": "Three governed ROSS Campbell cases, one representative EDF rotor per stage (R1/R2/R3), run sequentially on one ephemeral GCE Spot worker with order/fixed forcing lines",
            "why": "Locate forward critical speeds and separation from synchronous, blade/stator-pass, electrical and PWM excitations before geometry freeze",
            "referenceMachineRateUsdPerHour": assumptions["gcpPlan"]["providerNeutralReferenceRateUsdPerHour"],
            "maximumWorkerLifetimeSeconds": assumptions["gcpPlan"]["maximumWorkerLifetimeSeconds"],
            "plannedMaximumComputeCostUsdTotal": assumptions["gcpPlan"]["plannedMaximumComputeCostUsd"],
            "targetTotalSpendUsd": assumptions["gcpPlan"]["targetTotalSpendUsd"],
            "hardTotalSpendUsd": assumptions["gcpPlan"]["hardTotalSpendUsd"],
            "estimatedTotalSpendUsd": assumptions["gcpPlan"]["estimatedTotalSpendUsd"],
            "gpu": False,
            "estimateQualification": "one Spot VM reused for all cases; 20-minute lifetime cap; actual regional GCP billing receipt is authoritative",
            "decisionUnlocked": "whether each rotor/RPM schedule requires RPM exclusion zones, a stiffness/mass/spacing change, or a higher-fidelity forced response",
        },
        "jobs": all_jobs,
        "gcpJobsSubmitted": [],
        "limitations": [
            "FA4119 selected motor document does not specify output shaft geometry or bearings; motor shaft itself is not modeled.",
            "Shaft 6 mm x 60 mm, 2 mm steel-equivalent rotor disk, and bearing support values are assumptions.",
            "Bearing stiffness/damping, blade mass distribution, hub material, gear mesh and bearing characteristic frequencies are unknown.",
            "ROSS Campbell participant reports critical speeds and forcing margins; it does not currently publish a full Campbell plot artifact.",
            "Do not interpret any result as validation of blade stress, containment, gear mesh dynamics, or gearbox coupled modes.",
        ],
        "environmentGate": {
            "gcloudOperatorAuth": "active and project configured; existing US-CENTRAL1 evidence bucket is visible",
            "executionPath": "one ephemeral GCE Spot VM; app runner uses NativeJobManager local executor on the worker",
            "gcpBatchExecutor": "unprovisioned in workbench; this plan does not invoke it",
            "submissionStatus": "not submitted yet; revised cents-budget worker plan pending",
        },
        "inputHashes": {
            "rossAssumptionsSha256": hashlib.sha256(assumptions_path.read_bytes()).hexdigest(),
            "phase3ConfigSha256": hashlib.sha256((study / "configs" / "phase3_meanline.json").read_bytes()).hexdigest(),
        },
    }
    path = study / "results" / "phase4_ross_job_plan.json"
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared and schema-validated {len(all_jobs)} ROSS jobs (not submitted): {path}")


if __name__ == "__main__":
    main()
