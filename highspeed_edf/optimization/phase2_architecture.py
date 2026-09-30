#!/usr/bin/env python3
"""Phase-2 local architecture/VBR screening; no native solver execution.

The calculation is a two-stream, ideal-fully-expanded-nozzle cycle screen. It
compares a no-bypass three-rotor serial path with a fan plus two core rotors and
adjustable bypass split. It does not constitute fan/core maps, a passive-nozzle
mechanism design, CFD, or a validated gearbox/motor model.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def isa(altitude_m: float, gas_constant: float) -> tuple[float, float, float]:
    t = 288.15 - 0.0065 * altitude_m
    p = 101325.0 * (t / 288.15) ** (9.80665 / (gas_constant * 0.0065))
    return t, p, p / (gas_constant * t)


def nozzle_speed(pt: float, tt: float, pamb: float, cp: float, gamma: float) -> tuple[float, float]:
    if pt <= pamb:
        return 0.0, tt
    exp = (gamma - 1.0) / gamma
    ts = tt * (pamb / pt) ** exp
    velocity = math.sqrt(max(0.0, 2.0 * cp * (tt - ts)))
    return velocity, ts


def evaluate(
    *,
    speed: float,
    cda: float,
    beta: float,
    fan_pr: float,
    core_pr: float,
    density: float,
    pressure: float,
    temperature: float,
    area: float,
    capture: float,
    cp: float,
    gamma: float,
    rgas: float,
    recovery: float,
    compressor_eta: float,
    nozzle_recovery: float,
    drive_eta: float,
    gearbox_eta: float,
) -> dict[str, float]:
    exp = (gamma - 1.0) / gamma
    tt0 = temperature + speed * speed / (2.0 * cp)
    pt0 = pressure * (tt0 / temperature) ** (gamma / (gamma - 1.0))
    pt_fan_in = pt0 * recovery
    mdot = density * speed * area * capture
    thrust_required = 0.5 * density * speed * speed * cda
    tt_fan_out = tt0 * (1.0 + (fan_pr**exp - 1.0) / compressor_eta)
    pt_fan_out = pt_fan_in * fan_pr
    core_mass = mdot * (1.0 - beta)
    bypass_mass = mdot * beta
    tt_core_out = tt_fan_out * (1.0 + (core_pr**exp - 1.0) / compressor_eta)
    pt_core_out = pt_fan_out * core_pr
    vb, tsb = nozzle_speed(pt_fan_out * nozzle_recovery, tt_fan_out, pressure, cp, gamma)
    vc, tsc = nozzle_speed(pt_core_out * nozzle_recovery, tt_core_out, pressure, cp, gamma)
    thrust = bypass_mass * (vb - speed) + core_mass * (vc - speed)
    fan_power = mdot * cp * (tt_fan_out - tt0)
    core_power = core_mass * cp * (tt_core_out - tt_fan_out)
    compressor_shaft = fan_power + core_power
    electrical = compressor_shaft / (drive_eta * gearbox_eta)
    rho_b = pressure / (rgas * tsb) if tsb > 0 else 0.0
    rho_c = pressure / (rgas * tsc) if tsc > 0 else 0.0
    area_b = bypass_mass / (rho_b * vb) if vb > 0 and rho_b > 0 else 0.0
    area_c = core_mass / (rho_c * vc) if vc > 0 and rho_c > 0 else 0.0
    return {
        "mass_flow_kg_s": mdot,
        "bypass_mass_flow_kg_s": bypass_mass,
        "core_mass_flow_kg_s": core_mass,
        "required_thrust_n": thrust_required,
        "calculated_thrust_n": thrust,
        "bypass_exit_velocity_m_s": vb,
        "core_exit_velocity_m_s": vc,
        "bypass_nozzle_area_total_m2": area_b,
        "core_nozzle_area_total_m2": area_c,
        "fan_pressure_ratio": fan_pr,
        "core_pressure_ratio": core_pr,
        "overall_core_pressure_ratio": fan_pr * core_pr,
        "fan_shaft_power_w": fan_power,
        "core_shaft_power_w": core_power,
        "compressor_shaft_power_w": compressor_shaft,
        "electrical_input_power_w": electrical,
        "useful_thrust_power_w": thrust_required * speed,
        "jet_velocity_m_s_mass_weighted": bypass_mass * vb / mdot + core_mass * vc / mdot,
    }


def run() -> None:
    study = Path(__file__).resolve().parents[1]
    workbench = Path(r"D:\CodeProjects\aero-multiphysics-workbench")
    sys.path.insert(0, str(workbench))
    sys.path.insert(0, str(workbench / "solvers"))
    for package_dir in (workbench / "packages").glob("*"):
        if package_dir.is_dir():
            sys.path.insert(0, str(package_dir))
    from aeroworkbench_turbomachinery.cycle.gas import AIR  # type: ignore[import-not-found]

    config_path = study / "configs" / "phase2_architecture.json"
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    req_path = study / "requirements" / "requirements_r2.yaml"
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError("PyYAML is required to load requirements_r2.yaml") from e
    req = yaml.safe_load(req_path.read_text(encoding="utf-8"))
    ducts = int(req["aircraft"]["ducts"])
    diameter = float(req["aircraft"]["nominal_fan_diameter_m"])
    hub = float(req["propulsion"]["baseline_hub_diameter_mm"]) / 1000.0
    swept_area = ducts * math.pi / 4.0 * (diameter * diameter - hub * hub)
    gas = AIR
    t, p, rho = isa(float(cfg["operatingAltitudeM"]), gas.r_j_kg_k)
    exp = (gas.gamma - 1.0) / gas.gamma
    drive_eta = float(cfg["motorEfficiency"]) * float(cfg["escEfficiency"])
    capture = float(req["screening_assumptions"]["inlet_capture_area_fraction"])
    eta_c = float(cfg["compressorIsentropicEfficiency"])
    gear_eta = float(cfg["gearboxEfficiency"])
    nozz_eta = float(cfg["nozzleTotalPressureRecovery"])
    recovery = float(cfg["inletRecovery"])
    fan_start, fan_stop, fan_step = [float(x) for x in cfg["fanPressureRatioRange"]]
    fan_count = int(round((fan_stop - fan_start) / fan_step))
    fan_prs = [fan_start + i * fan_step for i in range(fan_count + 1)]
    core_min, core_max = [float(x) for x in cfg["corePressureRatioRange"]]
    sweep: list[dict[str, Any]] = []
    best_rows: list[dict[str, Any]] = []
    for speed_kmh in cfg["speedsKmh"]:
        speed = float(speed_kmh) / 3.6
        mach = speed / math.sqrt(gas.gamma * gas.r_j_kg_k * t)
        for cda in cfg["cdAComparisonM2"]:
            point_bests: list[dict[str, Any]] = []
            for beta in cfg["bypassFractions"]:
                if 1.0 - float(beta) < float(cfg["minimumCoreMassFraction"]):
                    continue
                best = None
                for p_fan in fan_prs:
                    at_core_min = evaluate(
                        speed=speed,
                        cda=float(cda),
                        beta=float(beta),
                        fan_pr=p_fan,
                        core_pr=core_min,
                        density=rho,
                        pressure=p,
                        temperature=t,
                        area=swept_area,
                        capture=capture,
                        cp=gas.cp_j_kg_k,
                        gamma=gas.gamma,
                        rgas=gas.r_j_kg_k,
                        recovery=recovery,
                        compressor_eta=eta_c,
                        nozzle_recovery=nozz_eta,
                        drive_eta=drive_eta,
                        gearbox_eta=gear_eta,
                    )
                    at_core_max = evaluate(
                        speed=speed,
                        cda=float(cda),
                        beta=float(beta),
                        fan_pr=p_fan,
                        core_pr=core_max,
                        density=rho,
                        pressure=p,
                        temperature=t,
                        area=swept_area,
                        capture=capture,
                        cp=gas.cp_j_kg_k,
                        gamma=gas.gamma,
                        rgas=gas.r_j_kg_k,
                        recovery=recovery,
                        compressor_eta=eta_c,
                        nozzle_recovery=nozz_eta,
                        drive_eta=drive_eta,
                        gearbox_eta=gear_eta,
                    )
                    required = at_core_min["required_thrust_n"]
                    if at_core_min["calculated_thrust_n"] >= required:
                        candidate = at_core_min
                    elif at_core_max["calculated_thrust_n"] < required:
                        continue
                    else:
                        lo, hi = core_min, core_max
                        candidate = at_core_max
                        for _ in range(42):
                            mid = 0.5 * (lo + hi)
                            candidate = evaluate(
                            speed=speed,
                            cda=float(cda),
                            beta=float(beta),
                            fan_pr=p_fan,
                            core_pr=mid,
                            density=rho,
                            pressure=p,
                            temperature=t,
                            area=swept_area,
                            capture=capture,
                            cp=gas.cp_j_kg_k,
                            gamma=gas.gamma,
                            rgas=gas.r_j_kg_k,
                            recovery=recovery,
                            compressor_eta=eta_c,
                            nozzle_recovery=nozz_eta,
                            drive_eta=drive_eta,
                            gearbox_eta=gear_eta,
                        )
                            if candidate["calculated_thrust_n"] >= required:
                                hi = mid
                            else:
                                lo = mid
                        candidate = evaluate(
                            speed=speed,
                            cda=float(cda),
                            beta=float(beta),
                            fan_pr=p_fan,
                            core_pr=hi,
                            density=rho,
                            pressure=p,
                            temperature=t,
                            area=swept_area,
                            capture=capture,
                            cp=gas.cp_j_kg_k,
                            gamma=gas.gamma,
                            rgas=gas.r_j_kg_k,
                            recovery=recovery,
                            compressor_eta=eta_c,
                            nozzle_recovery=nozz_eta,
                            drive_eta=drive_eta,
                            gearbox_eta=gear_eta,
                        )
                    if best is None or candidate["electrical_input_power_w"] < best["electrical_input_power_w"]:
                        best = candidate
                if best is not None:
                    row: dict[str, Any] = {
                        "altitude_m": cfg["operatingAltitudeM"],
                        "speed_kmh": speed_kmh,
                        "mach": mach,
                        "cdA_m2": cda,
                        "bypass_fraction": beta,
                        "gearbox_efficiency_assumed": gear_eta,
                        **best,
                        "source_class": "reduced-order two-stream cycle grid; fan/core maps and nozzle areas assumed idealized",
                    }
                    point_bests.append(row)
                    sweep.append(row)
            if point_bests:
                serial = min(point_bests, key=lambda row: row["electrical_input_power_w"])
                vbr_best = min(point_bests, key=lambda row: (row["electrical_input_power_w"], -row["bypass_fraction"]))
                no_bypass = min(
                    (row for row in point_bests if float(row["bypass_fraction"]) == 0.0),
                    key=lambda row: row["electrical_input_power_w"],
                    default=None,
                )
                if no_bypass is not None:
                    best_rows.append(
                        {
                            "altitude_m": cfg["operatingAltitudeM"],
                            "speed_kmh": speed_kmh,
                            "mach": mach,
                            "cdA_m2": cda,
                            "serial_three_rotor_power_w": no_bypass["electrical_input_power_w"],
                            "vbr_min_power_w": vbr_best["electrical_input_power_w"],
                            "optimal_bypass_fraction": vbr_best["bypass_fraction"],
                            "fan_pr": vbr_best["fan_pressure_ratio"],
                            "core_pr": vbr_best["core_pressure_ratio"],
                            "overall_core_pr": vbr_best["overall_core_pressure_ratio"],
                            "mass_flow_kg_s": vbr_best["mass_flow_kg_s"],
                            "required_thrust_n": vbr_best["required_thrust_n"],
                            "achieved_thrust_n": vbr_best["calculated_thrust_n"],
                            "bypass_nozzle_area_total_m2": vbr_best["bypass_nozzle_area_total_m2"],
                            "core_nozzle_area_total_m2": vbr_best["core_nozzle_area_total_m2"],
                            "compressor_shaft_power_w": vbr_best["compressor_shaft_power_w"],
                            "power_delta_vs_serial_w": no_bypass["electrical_input_power_w"] - vbr_best["electrical_input_power_w"],
                            "source_class": "reduced-order grid result; candidates use assumed efficiencies and separate fully-expanded nozzles",
                        }
                    )

    results = study / "results"
    write_csv(results / "phase2_bypass_sweep.csv", sweep)
    write_csv(results / "phase2_architecture_comparison.csv", best_rows)
    # Translate the rotor loading screen into fixed overdrive ratios at the motor hard RPM.
    ratio_rows = []
    mean_radius = ((diameter / 2.0) + (hub / 2.0)) / 2.0
    psi = [0.4, 0.5, 0.6]
    for row in best_rows:
        if float(row["cdA_m2"]) != 0.00315:
            continue
        specific_work = float(row["compressor_shaft_power_w"]) / float(row["mass_flow_kg_s"])
        for loading in psi:
            mean_u = math.sqrt(specific_work / (3.0 * loading))
            required_rpm = mean_u / (2.0 * math.pi * mean_radius) * 60.0
            ratio_rows.append(
                {
                    "speed_kmh": row["speed_kmh"],
                    "cdA_m2": row["cdA_m2"],
                    "optimal_bypass_fraction": row["optimal_bypass_fraction"],
                    "specific_work_j_kg": specific_work,
                    "assumed_loading_coefficient": loading,
                    "equal_three_rotor_rpm": required_rpm,
                    "fixed_ratio_at_13500_motor_rpm": required_rpm / float(cfg["motorOperatingHardRpm"]),
                    "ratio_2_3_output_rpm": 2.3 * float(cfg["motorOperatingHardRpm"]),
                    "ratio_2_6_output_rpm": 2.6 * float(cfg["motorOperatingHardRpm"]),
                    "ratio_2_9_output_rpm": 2.9 * float(cfg["motorOperatingHardRpm"]),
                    "source_class": "work-balance kinematic screen; common fan mean radius optimistic for core rotors",
                }
            )
    write_csv(results / "phase2_fixed_gear_screen.csv", ratio_rows)

    stage_rows: list[dict[str, Any]] = []
    ref = next(
        row for row in best_rows
        if row["speed_kmh"] == 700 and math.isclose(float(row["cdA_m2"]), 0.00315)
    )
    overall_pr = float(ref["overall_core_pr"])
    specific_work = float(ref["compressor_shaft_power_w"]) / float(ref["mass_flow_kg_s"])
    for n_rows in (1, 2, 3, 4):
        row_work = specific_work / n_rows
        u_mean = math.sqrt(row_work / 0.5)
        rpm = u_mean / (2.0 * math.pi * mean_radius) * 60.0
        stage_rows.append(
            {
                "speed_kmh": 700,
                "altitude_m": cfg["operatingAltitudeM"],
                "cdA_m2": 0.00315,
                "total_pressure_ratio": overall_pr,
                "pressure_adding_rotor_rows": n_rows,
                "equal_stage_pressure_ratio": overall_pr ** (1.0 / n_rows),
                "equal_specific_work_per_row_j_kg": row_work,
                "rpm_at_loading_psi_0_5": rpm,
                "fixed_overdrive_at_motor_13500rpm": rpm / float(cfg["motorOperatingHardRpm"]),
                "ideal_cycle_power_change_vs_other_stage_counts_w": 0.0,
                "source_class": "equal-work thermodynamic distribution; common radius; assumed psi=0.5; stage efficiencies held equal",
            }
        )
    write_csv(results / "phase2_stage_count_screen.csv", stage_rows)

    best_gearbox_bus_cap = 20_655.0  # 50.4 V open circuit, 10 mOhm assumed string, 450 A provisional aggregate
    for row in best_rows:
        row["within_75A_best_case_bus_cap"] = row["vbr_min_power_w"] <= best_gearbox_bus_cap
    write_csv(results / "phase2_architecture_comparison.csv", best_rows)
    summary = {
        "phase": 2,
        "evidenceClass": "reduced-order analytical screening",
        "atmosphere": {"altitudeM": cfg["operatingAltitudeM"], "temperatureK": t, "pressurePa": p, "densityKgM3": rho},
        "geometryCheckpoint": {
            "projectedFrontalAreaMaxCm2": 75,
            "mustBeDerivedSeparatelyFromCdA": True,
            "activeRequirementRevision": 2,
        },
        "architectureCandidates": [
            {"id": "A", "label": "three serial work-adding rotor rows", "motorsPerDuct": 3, "stages": 3, "servoCountPropulsion": 0, "screenedAs": "bypass fraction 0.0"},
            {"id": "B", "label": "front fan + two core rotor rows + variable bypass", "motorsPerDuct": 3, "stages": 3, "servoCountPropulsion": 0, "screenedAs": "bypass split grid 0.0-0.8"},
            {"id": "C", "label": "contra-rotating fan pair + one core rotor", "motorsPerDuct": 3, "stages": 2, "servoCountPropulsion": 0, "status": "thermodynamically comparable only; swirl/rotordynamics not screened"},
            {"id": "D", "label": "fan + three core stages, one motor drives tandem pair", "motorsPerDuct": 3, "stages": 4, "servoCountPropulsion": 0, "status": "shaft split not closed; mechanical risk candidate only"},
        ],
        "gearbox": {"fixedRatios": cfg["fixedGearRatios"], "efficiencyAssumed": gear_eta, "motorHardRpm": cfg["motorOperatingHardRpm"]},
        "stageCountScreen": stage_rows,
        "bypassConstraints": {
            "minimumCoreMassFractionAssumed": cfg["minimumCoreMassFraction"],
            "minimumCorePressureRatioAssumed": cfg["minimumCoreCompressorPressureRatio"],
        },
        "maximumProvisionalBusPowerW": best_gearbox_bus_cap,
        "gcpJobs": [],
        "nativeSolvers": [],
        "knownMissingPhysics": ["real fan/core maps", "nozzle flow capacity/choking", "mechanical variable-nozzle map", "frontal geometry", "installed inlet/interference losses", "motor torque-speed/loss maps", "gearbox mass and life"],
        "requirementsSha256": hashlib.sha256(req_path.read_bytes()).hexdigest(),
        "configSha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    }
    (results / "phase2_architecture_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_report(study, summary, best_rows, ratio_rows)
    print(f"Phase 2 screening complete: {len(sweep)} bypass operating points, {len(best_rows)} comparison points")


def write_report(study: Path, summary: dict[str, Any], comparisons: list[dict[str, Any]], ratios: list[dict[str, Any]]) -> None:
    focus = [row for row in comparisons if row["cdA_m2"] == 0.00315]
    text = [
        "# Phase 2 architecture screening",
        "",
        "**Evidence class:** reduced-order analytical screening. No native solver or GCP job was run.",
        "",
        "## Requirement checkpoint",
        "",
        "Active requirements revision 2 records projected frontal area ≤75 cm², lower preferred. This is distinct from the CdA values used as propulsion operating points; the frontal-area ceiling does not imply CdA without a geometry-specific drag coefficient and reference convention.",
        "",
        "## VBR comparison at 3 km ISA, CdA=0.00315 m²",
        "",
        "| Speed | Serial three-row electric input | Best VBR input | Best bypass fraction | Fan PR | Core PR | Rotor speed at ψ=0.5 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in focus:
        screen = next((r for r in ratios if r["speed_kmh"] == row["speed_kmh"] and r["assumed_loading_coefficient"] == 0.5), None)
        rpm = "n/a" if screen is None else f"{screen['equal_three_rotor_rpm']:.0f} rpm"
        text.append(
            f"| {row['speed_kmh']} km/h | {row['serial_three_rotor_power_w']/1000:.2f} kW | {row['vbr_min_power_w']/1000:.2f} kW | {row['optimal_bypass_fraction']:.2f} | {row['fan_pr']:.3f} | {row['core_pr']:.3f} | {rpm} |"
        )
    text += [
        "",
        "Bypass fraction is defined as bypass mass flow / total captured mass flow. The two exits are modeled as separate, ideally expanded nozzles. The grid minimizes electrical input while meeting the momentum-thrust target, subject to assumed minimum core flow and core pressure rise so the core motors are not numerically unloaded. It does not model mixer/nozzle maps, static capture, flow separation, or actual variable-nozzle kinematics. Interpret the optimizer's bypass schedule as a hypothesis for Phase 3, not a selected hardware schedule. Static T/W remains the Phase-1 actuator-disk bound and is not improved by this split model.",
        "",
        "## Fixed overdrive and stage layouts",
        "",
        "For the 3-rotor equal-work screen, `phase2_fixed_gear_screen.csv` gives rotor RPM and required gear ratio at the motor's 13,500 rpm initial hard limit. A fixed ratio transmits the independent motor RPM schedule; it does not add shaft power. A 95% gear efficiency is an explicit screening assumption. Counter-rotating fan pair and a fourth tandem stage remain candidates but are not aerodynamically distinguished by this reduced cycle model.",
        "",
        "`phase2_stage_count_screen.csv` divides the same total PR/work over one to four rotor rows. With stage efficiency held equal, total cycle power is identical by construction; the result is a loading/rotor-speed trade only. For the 700 km/h point, the 3-row option is the natural one-motor-per-rotor mapping; 2-stage/3-motor contra-rotation and a 4th tandem stage need mechanical closure before a fair comparison.",
        "",
        "## Candidate disposition",
        "",
        "- **A — serial three-row:** baseline, no bypass branch; easiest baseline to compare/bench.",
        "- **B — fan + two core rows + VBR:** retain as a low-speed-control/operating-range candidate, not as a proven efficiency winner. In the present sweep the high-speed optimizer closes the bypass branch (β=0) at 600–700 km/h; at 500 km/h its gain is negligible. The low-speed results are not a static-thrust validation. Do not add the mechanical bypass device until actual component maps show worthwhile low-speed authority or drag benefit.",
        "- **C — contra-rotating fan pair + core:** retained for a later meanline/rotordynamics comparison; zero-D power alone cannot credit swirl recovery.",
        "- **D — four pressure-adding rows / three motors:** no extra stage accepted yet; motor-to-tandem shaft allocation and packaging must close first.",
        "",
        "No architecture is declared validated or converged. The 75 cm² projected frontal checkpoint is carried forward; actual aircraft geometry and `CdA(V)` still need VLM/VSPAERO and installed-flow validation."
    ]
    report = study / "reports" / "phase2-architecture.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(text) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
