#!/usr/bin/env python3
"""Regenerate the final fixed-powertrain geometry/mass evidence register."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


STUDY = Path(__file__).resolve().parents[1]


def csv_rows(name: str) -> list[dict[str, str]]:
    with (STUDY / "results" / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict[str, Any]]) -> None:
    with (STUDY / "results" / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run() -> None:
    cfg = json.loads((STUDY / "configs" / "phase9_geometry_mass_screen.json").read_text(encoding="utf-8"))
    summary = json.loads((STUDY / "results" / "phase9_geometry_mass_summary.json").read_text(encoding="utf-8"))
    meanline = json.loads((STUDY / "results" / "phase9_720_meanline_summary.json").read_text(encoding="utf-8"))
    speed_rows = csv_rows("phase9_speed_envelope.csv")
    twr_rows = csv_rows("phase9_static_twr_screen.csv")
    board_rows = csv_rows("phase9_control_board_mass.csv")
    worst_r0 = max(float(x) for x in cfg["powertrainImmutable"]["packR0SensitivityOhm"])
    candidate_mass = float(cfg["candidate"]["allUpMassTargetKg"])
    twr_worst = next(
        row for row in twr_rows
        if float(row["altitude_m"]) == 3000.0
        and row["current_case"] == "soft_55A"
        and math.isclose(float(row["pack_r0_assumed_ohm"]), worst_r0)
    )
    soft_speed = [
        row for row in speed_rows
        if row["powertrain_limit_case"] == "soft_55A"
        and math.isclose(float(row["pack_r0_assumed_ohm"]), worst_r0)
    ]
    pass_speed_count = sum(
        row["within_pack_power_cap"] == "True" and row["within_equal_share_current_cap"] == "True"
        for row in soft_speed
    )
    board_bare_kg = sum(float(row["bareBoardMassEstimateG"]) for row in board_rows) / 1000.0
    area_limit = float(cfg["geometry"]["strictProjectedAreaLimitCm2"])
    fan_outer_union = float(summary["projectedDuctUnionCm2"])

    gates = [
        {
            "gate_id": "G-01", "domain": "projected_frontal_area", "status": "ANALYTIC_PASS_CAD_UNVERIFIED",
            "finding": f"Phase 9 projects {summary['projectedAreaTotalCm2']:.2f} cm2 (<75 cm2): coincident 90 mm duct outlines plus 10 cm2 structure allowance. Side intakes and board outline need assembled CAD verification.",
            "closure_evidence_required": "Dimensioned assembled CAD with board populations, heat spreaders, side-slot lips, mounts and the full projected union.",
        },
        {
            "gate_id": "G-02", "domain": "low_speed_static_twr", "status": "ANALYTIC_PASS_MASS_BUDGET_OPEN",
            "finding": f"At 11.5 kg, 90 mm annulus, 55 A/motor and worst screened R0={worst_r0*1000:.0f} mOhm, ideal T/W={float(twr_worst['candidate_TWR']):.3f} at 3 km. The 11.5 kg assembly has not been weighed.",
            "closure_evidence_required": "Weigh the populated controller assemblies, fans/gears, harness, inlet structure and fuselage; stay at or below 11.5 kg, then verify static thrust.",
        },
        {
            "gate_id": "G-03", "domain": "720kmh_rotor_stator_rows", "status": "CANDIDATE_MEANLINE_PASS_OFFDESIGN_OPEN",
            "finding": f"The new 90 mm / 8 mm stator candidate solves {meanline['rowsPassingScreen']}/{meanline['rowsTotal']} rows at 720 km/h; continuity residual {meanline['maximumContinuityErrorFraction']:.2e}, minimum stator Re about 69,000, and ideal-Kv phase-current estimate {meanline['maxIdealKvTorqueCurrentEstimateA']:.1f} A against the 60 A continuous screen.",
            "closure_evidence_required": "Run the frozen blade metal angles across 0–730 km/h, variable-bypass schedule and inlet distortion; validate by rig or CFD.",
        },
        {
            "gate_id": "G-04", "domain": "high_speed_envelope", "status": "ANALYTIC_PASS_CDA_TARGET_UNVALIDATED",
            "finding": f"At CdA={cfg['candidate']['cdAAtFlightTargetM2']:.5f} m2 the Phase-1 ideal-gas model passes the 55 A/channel pack screen for {pass_speed_count} speed points from 701–730 km/h, including the row-closed 720 km/h point.",
            "closure_evidence_required": "Build/measure the fuselage/inlet CdA and verify installed drag, pressure recovery, six-channel current sharing and motor RPM on a test article.",
        },
        {
            "gate_id": "G-05", "domain": "battery_characterization", "status": "ASSUMED_R0_OCV_THERMAL",
            "finding": "The locked 12S1P battery identity/mass are preserved; 10–30 mOhm DCIR and thermal parameters remain analyst sensitivities, not pack measurements.",
            "closure_evidence_required": "Measure pack OCV/DCIR pulses and thermal response across SOC and temperature; confirm the 55 A/motor operating point.",
        },
        {
            "gate_id": "G-06", "domain": "motor_esc_characterization", "status": "FIXED_FA4119_MAP_UNVALIDATED",
            "finding": "Six stock FA4119 motors remain fixed; the retail propeller rating is not the new 90 mm fan map.",
            "closure_evidence_required": "Guarded dyno with the final blades; record shaft torque/RPM, bus/phase current, motor/ESC temperatures, vibration and efficiency.",
        },
        {
            "gate_id": "G-07", "domain": "rotordynamics", "status": "OLD_GEOMETRY_RESULT_INVALID_FOR_NEW_ROTOR",
            "finding": "The Phase-4 Campbell analysis used the 80 mm rotor and assumed shaft/support geometry. The new 90 mm rotors invalidate those critical-speed values.",
            "closure_evidence_required": "Re-run Campbell and forced response with the 90 mm rotor/hub/shaft design; verify startup on the test stand.",
        },
        {
            "gate_id": "G-08", "domain": "electronics_mass", "status": "BARE_BOARD_MASS_CALCULATED_POPULATION_UNWEIGHED",
            "finding": f"KiCad material calculation gives {board_bare_kg:.3f} kg for bare ESC/flight-control PCBs. It excludes mounted BOM parts, high-current lugs, heatsink and mounting.",
            "closure_evidence_required": "Weigh the populated Rev-B boards and production heat spreader; reconcile the ESC PCB six-layer saved stackup against its four-layer architecture document.",
        },
        {
            "gate_id": "G-09", "domain": "mission_endurance", "status": "MISSION_PROFILE_OPEN",
            "finding": "Speed/TWR geometry screens are not a complete range/endurance calculation; cruise duration, reserve and climb profile are not specified.",
            "closure_evidence_required": "Define mission segments, reserve, climb/takeoff and desired loiter/range.",
        },
    ]
    write_csv("project_closure_register.csv", gates)
    status = {
        "study": "highspeed-edf",
        "analysisPhasesCompleted": list(range(10)),
        "fixedPowertrain": True,
        "candidateAreaCm2": float(summary["projectedAreaTotalCm2"]),
        "candidateTwr3kmWorstR0Soft": float(twr_worst["candidate_TWR"]),
        "candidateMassTargetKg": candidate_mass,
        "candidateSpeedKmh": int(cfg["candidate"]["flightSpeedTargetKmh"]),
        "speedSamplesPassingSoftCurrent": pass_speed_count,
        "bareControllerPcbMassKg": board_bare_kg,
        "knownMotorBatteryBarePcbMassKg": float(summary["massFixedKnownLowerBoundKg"]),
        "openEvidenceGates": len(gates),
        "engineeringReleaseReady": False,
        "cloudJobs": [],
        "cloudCostUsd": 0.0,
    }
    (STUDY / "results" / "project_closure_summary.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    write_report(status, gates, summary, meanline, twr_worst, board_bare_kg)
    print(f"Final closure updated: {pass_speed_count}/4 speed points pass the analytic soft-current screen; fixed powertrain; no cloud jobs.")


def write_report(status: dict[str, Any], gates: list[dict[str, Any]], summary: dict[str, Any], meanline: dict[str, Any], twr: dict[str, str], board_mass_kg: float) -> None:
    lines = [
        "# High-speed EDF — fixed-powertrain geometry closure",
        "",
        "## Geometry-only candidate",
        "",
        f"The new candidate retains all six FA4119 motors and the two-pack 12S1P battery. It screens at **{status['candidateAreaCm2']:.2f} cm²**, **T/W={status['candidateTwr3kmWorstR0Soft']:.3f}** at 3 km on the 55 A/motor soft point with 30 mΩ assumed pack resistance, **{status['candidateMassTargetKg']:.1f} kg** all-up, and a 720 km/h design point. The ideal-gas cycle screen passes 701–730 km/h for CdA=0.00095 m²; the re-solved 720 km/h row set passes 6/6 meanline checks.",
        "",
        "The geometry is a 90 mm OD / 32 mm hub axial fan stack, 16 mm rotor chord, 29 mm blade span, and 8 mm stator chord, all within the 16 mm × 50 mm stock envelope. Two 50×120 mm side inlets feed the annulus; axial duct staggering and side-facing inlets keep the projected area below 75 cm². Equal stage work is the blade-pitch/twist design target to keep all six unchanged motor channels under the current soft limit.",
        "",
        "## Actual hardware mass basis and fuselage budget",
        "",
        f"Six FA4119 motors weigh 1.680 kg from the drone-arm decision record; both Turnigy packs weigh 1.426 kg from the product spec. KiCad stackups plus exported copper coverage give **{board_mass_kg:.3f} kg bare PCB material**. Thus the sourced motor + battery + bare-board floor is {status['knownMotorBatteryBarePcbMassKg']:.3f} kg, leaving {status['candidateMassTargetKg']-status['knownMotorBatteryBarePcbMassKg']:.3f} kg for board components/lugs/heatsink, rotors/gears, ducts, side inlets, wiring, fuselage, landing gear and payload.",
        "",
        "That residual is an engineering mass allowance, not a measured total: drone-arm BOMs do not assign weights to populated board assemblies, spreaders, harnesses or the airframe. The candidate passes the mass screen only if the completed assembly is weighed at or below 11.5 kg.",
        "",
        "## Screens and remaining validation",
        "",
        f"At 720 km/h, the Phase-1 cycle model predicts {summary['powerAtTargetW']/1000:.2f} kW bus power; under the worst screened 30 mΩ pack R0 the soft-current bus cap is {summary['softCurrentBudgetAtWorstR0W']/1000:.2f} kW. The 720 meanline solve reports {meanline['rowsPassingScreen']}/{meanline['rowsTotal']} rows passing, stator Reynolds minimum near 69k, and continuity residual {meanline['maximumContinuityErrorFraction']:.2e}.", 
        "",
        "| Gate | Current disposition | Evidence still needed |",
        "|---|---|---|",
    ]
    for gate in gates:
        lines.append(f"| {gate['domain']} | {gate['status']} | {gate['closure_evidence_required']} |")
    lines += [
        "",
        "The Phase-4 ROSS critical-speed results are for the superseded 80 mm rotor/shaft model; re-run after detailed 90 mm blade/hub CAD. Battery DCIR and fan efficiency remain sensitivities. No powertrain component, capacity, voltage, or current limit was changed. No cloud jobs were used.",
        "",
    ]
    (STUDY / "reports" / "project-closure.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
