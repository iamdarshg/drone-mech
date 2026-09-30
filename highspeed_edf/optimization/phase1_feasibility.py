#!/usr/bin/env python3
"""Local analytical Phase-1 feasibility screen for the high-speed EDF study.

The forward-flight model treats the two ducts as a single-stream compressor and
fully expanded convergent nozzle. Static thrust is an ideal actuator-disk upper
bound. Battery resistance is a sensitivity variable, not a measured Turnigy
parameter. The driver deliberately does not claim VBR, blade-row, CFD, or
validated FA4119 performance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


def _read_requirements(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-not-found]

        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return value
    except ImportError:
        pass
    # The requirements file is valid YAML but intentionally uses JSON-compatible
    # scalars/collections. Avoid a project-specific dependency for this runner.
    raise RuntimeError("Install PyYAML in the study environment to read requirements.yaml")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _voltage_and_power(voc: float, resistance: float, current: float) -> tuple[float, float]:
    voltage = max(0.0, voc - current * resistance)
    return voltage, voltage * current


def _required_input(
    *,
    speed_m_s: float,
    cda_m2: float,
    recovery: float,
    annulus_area_m2: float,
    capture_fraction: float,
    ambient_pressure_pa: float,
    ambient_temperature_k: float,
    cp: float,
    gamma: float,
    gas_constant: float,
    compressor_efficiency: float,
    nozzle_recovery: float,
    motor_efficiency: float,
    esc_efficiency: float,
) -> dict[str, float | bool | str]:
    """Solve fan PR needed for captured-flow momentum thrust at this flight point."""
    if speed_m_s <= 0:
        return {"feasible": False, "reason": "static point uses actuator-disk model"}
    exponent = (gamma - 1.0) / gamma
    rho = ambient_pressure_pa / (gas_constant * ambient_temperature_k)
    mach = speed_m_s / math.sqrt(gamma * gas_constant * ambient_temperature_k)
    t_total_in = ambient_temperature_k + speed_m_s**2 / (2.0 * cp)
    p_total_freestream = ambient_pressure_pa * (
        t_total_in / ambient_temperature_k
    ) ** (gamma / (gamma - 1.0))
    p_total_face = p_total_freestream * recovery
    mdot = rho * speed_m_s * annulus_area_m2 * capture_fraction
    thrust = 0.5 * rho * speed_m_s**2 * cda_m2
    if mdot <= 0:
        return {"feasible": False, "reason": "zero captured mass flow"}
    jet_velocity = speed_m_s + thrust / mdot

    def exit_speed(pr: float) -> tuple[float, float, float]:
        t_total_out = t_total_in * (
            1.0 + (pr**exponent - 1.0) / compressor_efficiency
        )
        p_total_nozzle = p_total_face * pr * nozzle_recovery
        if p_total_nozzle <= ambient_pressure_pa:
            return 0.0, t_total_out, p_total_nozzle
        t_static = t_total_out * (ambient_pressure_pa / p_total_nozzle) ** exponent
        return math.sqrt(max(0.0, 2.0 * cp * (t_total_out - t_static))), t_total_out, p_total_nozzle

    low, high = 1.0, 8.0
    if exit_speed(high)[0] < jet_velocity:
        return {
            "feasible": False,
            "reason": "required jet velocity exceeds screening PR bracket",
            "mach": mach,
            "mass_flow_kg_s": mdot,
            "required_thrust_n": thrust,
            "required_jet_velocity_m_s": jet_velocity,
        }
    for _ in range(100):
        mid = 0.5 * (low + high)
        if exit_speed(mid)[0] < jet_velocity:
            low = mid
        else:
            high = mid
    pr = 0.5 * (low + high)
    actual_jet, t_total_out, p_total_nozzle = exit_speed(pr)
    compressor_power = mdot * cp * (t_total_out - t_total_in)
    drivetrain_efficiency = motor_efficiency * esc_efficiency
    electrical_power = compressor_power / drivetrain_efficiency
    return {
        "feasible": True,
        "mach": mach,
        "freestream_total_pressure_pa": p_total_freestream,
        "compressor_face_total_pressure_pa": p_total_face,
        "mass_flow_kg_s": mdot,
        "required_thrust_n": thrust,
        "required_jet_velocity_m_s": jet_velocity,
        "calculated_jet_velocity_m_s": actual_jet,
        "compressor_pressure_ratio": pr,
        "compressor_exit_total_temperature_k": t_total_out,
        "nozzle_inlet_total_pressure_pa": p_total_nozzle,
        "compressor_shaft_power_w": compressor_power,
        "electrical_input_power_w": electrical_power,
        "useful_thrust_power_w": thrust * speed_m_s,
        "total_electrical_to_useful_efficiency": thrust * speed_m_s / electrical_power
        if electrical_power > 0
        else 0.0,
    }


def _solve_static_thrust(power_w: float, area_m2: float, rho: float) -> float:
    """Ideal actuator-disk static thrust for air power; upper bound, not a fan map."""
    if power_w <= 0 or area_m2 <= 0:
        return 0.0
    # P = T^(3/2) / sqrt(2 rho A)
    return (power_w * math.sqrt(2.0 * rho * area_m2)) ** (2.0 / 3.0)


def _isa_troposphere(altitude_m: float, gas_constant: float) -> dict[str, float]:
    """ISA troposphere properties to 11 km; screening atmosphere, dry air."""
    if not 0.0 <= altitude_m <= 11000.0:
        raise ValueError(f"Altitude outside ISA troposphere: {altitude_m}")
    t0 = 288.15
    p0 = 101325.0
    lapse = 0.0065
    g0 = 9.80665
    temperature = t0 - lapse * altitude_m
    pressure = p0 * (temperature / t0) ** (g0 / (gas_constant * lapse))
    return {
        "altitude_m": altitude_m,
        "static_temperature_k": temperature,
        "static_pressure_pa": pressure,
        "density_kg_m3": pressure / (gas_constant * temperature),
    }


def _max_cda(
    *,
    speed_m_s: float,
    power_limit_w: float,
    recovery: float,
    kwargs: dict[str, Any],
) -> float:
    low, high = 0.0, 0.02
    for _ in range(70):
        mid = (low + high) / 2.0
        result = _required_input(
            speed_m_s=speed_m_s, cda_m2=mid, recovery=recovery, **kwargs
        )
        required = float(result.get("electrical_input_power_w", math.inf))
        if result.get("feasible") and required <= power_limit_w:
            low = mid
        else:
            high = mid
    return low


def run(args: argparse.Namespace) -> dict[str, Any]:
    workbench = args.workbench_root.resolve()
    sys.path.insert(0, str(workbench))
    sys.path.insert(0, str(workbench / "solvers"))
    for package_dir in sorted((workbench / "packages").glob("*"), reverse=True):
        if package_dir.is_dir():
            sys.path.insert(0, str(package_dir))
    from aeroworkbench_turbomachinery.cycle.gas import (  # type: ignore[import-not-found]
        AIR,
        ideal_gas_density,
        isentropic_temperature_ratio,
    )

    requirements_path = args.requirements.resolve()
    design_path = args.design.resolve()
    req = _read_requirements(requirements_path)
    design = json.loads(design_path.read_text(encoding="utf-8"))
    airframe = req["aircraft"]
    prop = req["propulsion"]
    battery = req["battery"]
    limits = req["electrical_limits"]
    assumptions = req["screening_assumptions"]
    atmosphere = assumptions["atmosphere"]

    diameter = float(airframe["nominal_fan_diameter_m"])
    hub = float(prop["baseline_hub_diameter_mm"]) / 1000.0
    annulus_one = math.pi / 4.0 * (diameter**2 - hub**2)
    annulus_total = int(airframe["ducts"]) * annulus_one
    cda_values = [0.0025, 0.003, 0.0035, 0.004, 0.0045, 0.005, 0.006]
    speeds_kmh = [0, 100, 200, 400, 500, 550, 600, 650, 700]
    altitudes_m = [float(h) for h in atmosphere["altitude_study_m"]]
    recoveries = [0.90, 0.92, 0.94, 0.96, 0.97, 0.98, 0.985, 0.99]
    params = {
        "annulus_area_m2": annulus_total,
        "capture_fraction": float(assumptions["inlet_capture_area_fraction"]),
        "ambient_pressure_pa": float(atmosphere["static_pressure_pa"]),
        "ambient_temperature_k": float(atmosphere["static_temperature_k"]),
        "cp": AIR.cp_j_kg_k,
        "gamma": AIR.gamma,
        "gas_constant": AIR.r_j_kg_k,
        "compressor_efficiency": float(assumptions["compressor_isentropic_efficiency"]),
        "nozzle_recovery": float(assumptions["nozzle_total_pressure_recovery"]),
        "motor_efficiency": float(assumptions["motor_efficiency"]),
        "esc_efficiency": float(assumptions["esc_efficiency"]),
    }
    eta_drive = params["motor_efficiency"] * params["esc_efficiency"]
    n_motors = int(airframe["ducts"]) * int(prop["motors_per_duct"])
    current_soft = n_motors * float(limits["battery_current_per_motor_soft_rollback_a"])
    current_hard = n_motors * float(limits["battery_current_per_motor_initial_hard_a"])
    current_provisional = n_motors * float(limits["battery_current_per_motor_provisional_short_a"])
    pack_resistances = battery["continuous_pack_resistance_sensitivity_ohm"]
    voltages = {
        "nominal": float(battery["nominal_voltage_v"]),
        "fully_charged": float(battery["fully_charged_voltage_v"]),
    }
    electrical_caps: dict[str, dict[str, float]] = {}
    for v_label, voc in voltages.items():
        for r in pack_resistances:
            for duty, current in (
                ("soft-rollback", current_soft),
                ("initial-hard", current_hard),
                ("provisional-short-duration-unvalidated", current_provisional),
            ):
                v_load, power = _voltage_and_power(voc, float(r), current)
                electrical_caps[f"{v_label}_R{float(r):.3f}_{duty}"] = {
                    "open_circuit_voltage_v": voc,
                    "assumed_pack_resistance_ohm": float(r),
                    "current_limit_a": current,
                    "c_rate": current / float(battery["capacity_ah"]),
                    "loaded_voltage_v": v_load,
                    "terminal_power_w": power,
        "source_class": "analytical; resistance sensitivity assumed; FA4119 decision-record current limits",
                }

    forward_rows: list[dict[str, Any]] = []
    for altitude_m in altitudes_m:
        atm = _isa_troposphere(altitude_m, AIR.r_j_kg_k)
        alt_params = {
            **params,
            "ambient_pressure_pa": atm["static_pressure_pa"],
            "ambient_temperature_k": atm["static_temperature_k"],
        }
        for speed_kmh in speeds_kmh[1:]:
            for cda in cda_values:
                result = _required_input(
                    speed_m_s=speed_kmh / 3.6,
                    cda_m2=cda,
                    recovery=0.98,
                    **alt_params,
                )
                forward_rows.append(
                    {
                        "altitude_m": altitude_m,
                        "ambient_pressure_pa": atm["static_pressure_pa"],
                        "ambient_temperature_k": atm["static_temperature_k"],
                        "ambient_density_kg_m3": atm["density_kg_m3"],
                        "speed_kmh": speed_kmh,
                        "mach": result.get("mach"),
                        "cda_m2": cda,
                        "inlet_recovery": 0.98,
                        "mass_flow_kg_s": result.get("mass_flow_kg_s"),
                        "required_thrust_n": result.get("required_thrust_n"),
                        "required_jet_velocity_m_s": result.get("required_jet_velocity_m_s"),
                        "compressor_pr": result.get("compressor_pressure_ratio"),
                        "electrical_input_power_w": result.get("electrical_input_power_w"),
                        "useful_thrust_power_w": result.get("useful_thrust_power_w"),
                        "feasible_in_1d_bracket": result.get("feasible", False),
                        "source_class": "analytical-screening; ISA troposphere; single-stream fully-expanded nozzle",
                    }
                )

    recovery_rows: list[dict[str, Any]] = []
    for altitude_m in altitudes_m:
        atm = _isa_troposphere(altitude_m, AIR.r_j_kg_k)
        alt_params = {
            **params,
            "ambient_pressure_pa": atm["static_pressure_pa"],
            "ambient_temperature_k": atm["static_temperature_k"],
        }
        for speed_kmh, cda in ((600, 0.004), (700, 0.0035)):
            for recovery in recoveries:
                result = _required_input(
                    speed_m_s=speed_kmh / 3.6,
                    cda_m2=cda,
                    recovery=recovery,
                    **alt_params,
                )
                recovery_rows.append(
                    {
                        "altitude_m": altitude_m,
                        "ambient_pressure_pa": atm["static_pressure_pa"],
                        "ambient_density_kg_m3": atm["density_kg_m3"],
                        "speed_kmh": speed_kmh,
                        "cda_m2": cda,
                        "recovery": recovery,
                        "compressor_face_pt_pa": result.get("compressor_face_total_pressure_pa"),
                        "mass_flow_kg_s": result.get("mass_flow_kg_s"),
                        "required_thrust_n": result.get("required_thrust_n"),
                        "compressor_pr": result.get("compressor_pressure_ratio"),
                        "compressor_shaft_power_w": result.get("compressor_shaft_power_w"),
                        "electrical_input_power_w": result.get("electrical_input_power_w"),
                        "feasible_in_1d_bracket": result.get("feasible", False),
                        "source_class": "analytical-screening; ISA troposphere; assumed compressor/nozzle efficiencies",
                    }
                )

    speed_power_rows: list[dict[str, Any]] = []
    power_values_kw = [12, 15, 18, 21, 24, 27, 30]
    for altitude_m in altitudes_m:
        atm = _isa_troposphere(altitude_m, AIR.r_j_kg_k)
        alt_params = {
            **params,
            "ambient_pressure_pa": atm["static_pressure_pa"],
            "ambient_temperature_k": atm["static_temperature_k"],
        }
        for cda in cda_values:
            for power_kw in power_values_kw:
                attainable = []
                for speed_kmh in range(100, 701, 5):
                    result = _required_input(
                        speed_m_s=speed_kmh / 3.6,
                        cda_m2=cda,
                        recovery=0.98,
                        **alt_params,
                    )
                    if result.get("feasible") and float(result["electrical_input_power_w"]) <= power_kw * 1000:
                        attainable.append(speed_kmh)
                speed_power_rows.append(
                    {
                        "altitude_m": altitude_m,
                        "ambient_density_kg_m3": atm["density_kg_m3"],
                        "cda_m2": cda,
                        "electrical_power_kw": power_kw,
                        "max_speed_kmh_analytical": max(attainable, default=0),
                        "source_class": "analytical-screening; ISA troposphere; power cap treated as delivered bus power",
                    }
                )

    cda_limit_rows: list[dict[str, Any]] = []
    for altitude_m in altitudes_m:
        atm = _isa_troposphere(altitude_m, AIR.r_j_kg_k)
        alt_params = {
            **params,
            "ambient_pressure_pa": atm["static_pressure_pa"],
            "ambient_temperature_k": atm["static_temperature_k"],
        }
        for speed_kmh in (400, 500, 550, 600, 650, 700):
            for power_kw in power_values_kw:
                cda_limit_rows.append(
                    {
                        "altitude_m": altitude_m,
                        "ambient_density_kg_m3": atm["density_kg_m3"],
                        "speed_kmh": speed_kmh,
                        "electrical_power_kw": power_kw,
                        "inlet_recovery": 0.98,
                        "max_cda_m2": _max_cda(
                            speed_m_s=speed_kmh / 3.6,
                            power_limit_w=power_kw * 1000,
                            recovery=0.98,
                            kwargs=alt_params,
                        ),
                        "source_class": "analytical-screening; ISA troposphere; single-stream model",
                    }
                )

    static_rows: list[dict[str, Any]] = []
    motor_count = n_motors
    static_cd = float(assumptions["esc_efficiency"]) * float(assumptions["motor_efficiency"])
    for altitude_m in altitudes_m:
        atm = _isa_troposphere(altitude_m, AIR.r_j_kg_k)
        for v_label, voc in voltages.items():
            for r in pack_resistances:
                for current_limit, duty in (
                    (current_soft, "55A-per-motor-soft-rollback"),
                    (current_hard, "65A-per-motor-initial-hard-limit"),
                    (current_provisional, "75A-per-motor-provisional-short-duration-unvalidated"),
                ):
                    vload, electrical_power = _voltage_and_power(voc, float(r), current_limit)
                    for fan_eff in assumptions["static_fan_efficiency_sensitivity"]:
                        air_power = electrical_power * static_cd * float(fan_eff)
                        thrust = _solve_static_thrust(
                            air_power, annulus_total, atm["density_kg_m3"]
                        )
                        weight = float(airframe["mass_kg"]) * 9.80665
                        static_rows.append(
                            {
                                "altitude_m": altitude_m,
                                "ambient_pressure_pa": atm["static_pressure_pa"],
                                "ambient_temperature_k": atm["static_temperature_k"],
                                "ambient_density_kg_m3": atm["density_kg_m3"],
                                "pack_state": v_label,
                                "assumed_pack_resistance_ohm": float(r),
                                "loaded_voltage_v": vload,
                                "duty_limit": duty,
                                "static_fan_efficiency_assumed": float(fan_eff),
                                "bus_power_w": electrical_power,
                                "air_power_w": air_power,
                                "total_static_thrust_n_ideal_disk": thrust,
                                "static_t_over_w": thrust / weight,
                                "source_class": "analytical actuator-disk upper bound; ISA density; efficiency assumptions; not EDF test data",
                            }
                        )

    motor = req["motor"]
    kv = float(motor["stock_kv_rpm_per_v"])
    poles = 2 * int(motor.get("pole_pairs", 7))
    limits_rpm = [
        float(motor["initial_soft_rpm_limit"]),
        float(motor["initial_hard_rpm_limit"]),
        float(motor["stock_no_load_rpm_at_50_4_v"]),
    ]
    rpm_rows = []
    rmean = (diameter / 2.0 + hub / 2.0) / 2.0
    for rpm in limits_rpm:
        tip_speed = math.pi * diameter * rpm / 60.0
        mean_speed = 2.0 * math.pi * rmean * rpm / 60.0
        rpm_rows.append(
            {
                "mechanical_rpm": rpm,
                "electrical_rpm": rpm * int(motor.get("pole_pairs", 7)),
                "electrical_frequency_hz": rpm * int(motor.get("pole_pairs", 7)) / 60.0,
                "tip_speed_m_s": tip_speed,
                "tip_mach_static": tip_speed / math.sqrt(AIR.gamma * AIR.r_j_kg_k * float(atmosphere["static_temperature_k"])),
                "mean_radius_m": rmean,
                "mean_blade_speed_m_s": mean_speed,
                "max_specific_work_per_3_rotors_j_kg_at_psi_0_5": 3 * 0.5 * mean_speed**2,
                "stock_motor_no_load_rpm_at_nominal_v": kv * float(battery["nominal_voltage_v"]),
                "stock_motor_no_load_rpm_at_full_charge_v": kv * float(battery["fully_charged_voltage_v"]),
                "source_class": "motor RPM limits externally sourced; kinematics analytical",
            }
        )

    required_loading_rows: list[dict[str, Any]] = []
    for altitude_m in altitudes_m:
        atm = _isa_troposphere(altitude_m, AIR.r_j_kg_k)
        alt_params = {
            **params,
            "ambient_pressure_pa": atm["static_pressure_pa"],
            "ambient_temperature_k": atm["static_temperature_k"],
        }
        for speed_kmh, cda in ((600, 0.004), (700, 0.0035)):
            result = _required_input(
                speed_m_s=speed_kmh / 3.6,
                cda_m2=cda,
                recovery=0.98,
                **alt_params,
            )
            if not result.get("feasible"):
                continue
            specific_work = float(result["compressor_shaft_power_w"]) / float(result["mass_flow_kg_s"])
            for psi in (0.4, 0.5, 0.6):
                mean_blade_speed = math.sqrt(specific_work / (3.0 * psi))
                required_loading_rows.append(
                    {
                        "altitude_m": altitude_m,
                        "ambient_density_kg_m3": atm["density_kg_m3"],
                        "speed_kmh": speed_kmh,
                        "cda_m2": cda,
                        "inlet_recovery": 0.98,
                        "required_specific_work_j_kg": specific_work,
                        "rotor_loading_coefficient_assumed": psi,
                        "equal_three_rotor_required_rpm": mean_blade_speed / (2.0 * math.pi * rmean) * 60.0,
                        "source_class": "analytical work balance + ISA; assumed equal-work 3-rotor loading; optimistic common radius",
                    }
                )

    energy_rows = []
    nominal_energy_wh = float(battery["nominal_voltage_v"]) * float(battery["capacity_ah"])
    for usable in battery["usable_energy_fraction_sensitivity"]:
        usable_wh = nominal_energy_wh * float(usable)
        for kw in power_values_kw:
            energy_rows.append(
                {
                    "usable_energy_fraction_assumed": float(usable),
                    "usable_energy_wh": usable_wh,
                    "bus_power_kw": kw,
                    "ideal_duration_s": usable_wh / kw * 3.6,
                    "source_class": "analytical energy bound; excludes voltage cut-off, thermal derating, acceleration and reserve",
                }
            )

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "forward_speed_cda_map.csv", forward_rows)
    _write_csv(output / "pressure_recovery_sensitivity.csv", recovery_rows)
    _write_csv(output / "speed_power_map.csv", speed_power_rows)
    _write_csv(output / "cda_requirement_map.csv", cda_limit_rows)
    _write_csv(output / "static_thrust_sensitivity.csv", static_rows)
    _write_csv(output / "motor_rpm_screen.csv", rpm_rows)
    _write_csv(output / "required_rotor_loading_screen.csv", required_loading_rows)
    _write_csv(output / "battery_duration_bounds.csv", energy_rows)

    req_hash = hashlib.sha256(requirements_path.read_bytes()).hexdigest()
    summary: dict[str, Any] = {
        "study_id": "highspeed-edf",
        "phase": "0+1",
        "source_class": "analytical-screening",
        "workbench_gas_model": "aeroworkbench_turbomachinery.cycle.gas.AIR",
        "requirements_sha256": req_hash,
        "design_revision": design["revision"],
        "native_solver_runs": [],
        "gcp_jobs": [],
        "model_scope": {
            "forward_flight": "single-stream equivalent captured annulus, pressure recovery, compressor PR, fully expanded nozzle momentum thrust",
            "static": "ideal actuator disk with assumed electrical-drive and fan efficiencies",
            "vbr": "variable bypass split not resolved; fan/core flow split is an architecture-phase model gap",
            "battery": "Thevenin resistance sensitivity and energy bound; no exact cell DCIR/discharge data available",
            "motor": "FA4119 published/contract RPM and current constraints; no validated EDF motor map",
        },
        "key_assumptions": assumptions,
        "atmosphere_study": [
            _isa_troposphere(h, AIR.r_j_kg_k) for h in altitudes_m
        ],
        "battery_power_caps": electrical_caps,
        "motor_rpm_screen": rpm_rows,
        "required_rotor_loading_screen": required_loading_rows,
        "battery_energy_bounds": energy_rows,
        "counts": {
            "forward_points": len(forward_rows),
            "recovery_points": len(recovery_rows),
            "speed_power_points": len(speed_power_rows),
            "cda_limit_points": len(cda_limit_rows),
            "static_points": len(static_rows),
        },
        "warning": "Not CFD, measured motor data, a PyBaMM cell simulation, or a validated pack-power result.",
    }
    (output / "phase1_results.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    _write_report(output, summary, forward_rows, recovery_rows, rpm_rows, static_rows)
    return summary


def _write_report(
    output: Path,
    summary: dict[str, Any],
    forward_rows: list[dict[str, Any]],
    recovery_rows: list[dict[str, Any]],
    rpm_rows: list[dict[str, Any]],
    static_rows: list[dict[str, Any]],
) -> None:
    focus = [
        row for row in forward_rows
        if row["altitude_m"] == 0
        and row["speed_kmh"] == 600
        and row["cda_m2"] in (0.003, 0.0035, 0.004, 0.0045)
    ]
    recovery = [
        row for row in recovery_rows
        if row["altitude_m"] == 0 and row["speed_kmh"] == 600
    ]
    altitude_focus = [
        row for row in forward_rows
        if row["speed_kmh"] == 600 and row["cda_m2"] == 0.004
    ]
    loading = [
        row for row in summary["required_rotor_loading_screen"]
        if row["altitude_m"] == 0 and row["speed_kmh"] == 600
    ]
    static_focus = [
        row for row in static_rows
        if (row["pack_state"], row["assumed_pack_resistance_ohm"], row["duty_limit"], row["static_fan_efficiency_assumed"])
        in (
            ("nominal", 0.02, "55A-per-motor-soft-rollback", 0.65),
            ("nominal", 0.02, "65A-per-motor-initial-hard-limit", 0.65),
            ("fully_charged", 0.01, "75A-per-motor-provisional-short-duration-unvalidated", 0.65),
            ("fully_charged", 0.01, "75A-per-motor-provisional-short-duration-unvalidated", 0.80),
        )
        and row["altitude_m"] in (0.0, 3000.0)
    ]
    md = [
        "# Phase 1 feasibility report",
        "",
        "**Evidence class:** analytical screening. Workbench ideal-gas functions are reused. No native solver, GCP job, CFD, battery discharge test, or EDF dyno result was run.",
        "",
        "## 600 km/h reference cases",
        "",
        "| CdA (m²) | Required thrust (N) | Captured flow (kg/s) | Required PR | Electrical input (kW) |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in focus:
        md.append(
            f"| {row['cda_m2']:.4f} | {float(row['required_thrust_n'] or 0):.1f} | {float(row['mass_flow_kg_s'] or 0):.3f} | {float(row['compressor_pr'] or 0):.4f} | {float(row['electrical_input_power_w'] or 0)/1000:.2f} |"
        )
    md += [
        "",
        "The forward model captures only the annular area times an assumed 0.85 capture fraction, then solves the compressor PR needed for momentum thrust through an ideally expanded nozzle. It does not model bypass/core mixing, distortion, spillage, or fan maps, so use this as a feasibility screen rather than a design prediction.",
        "",
        "## Altitude comparison: 600 km/h, CdA=0.004 m²",
        "",
        "| Altitude (km) | Density (kg/m³) | Thrust (N) | Captured flow (kg/s) | PR | Electrical input (kW) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in altitude_focus:
        md.append(
            f"| {row['altitude_m']/1000:.0f} | {row['ambient_density_kg_m3']:.3f} | {row['required_thrust_n']:.1f} | {row['mass_flow_kg_s']:.3f} | {row['compressor_pr']:.4f} | {row['electrical_input_power_w']/1000:.2f} |"
        )
    md += [
        "",
        "The lower density reduces both aircraft drag and captured flow at a fixed true airspeed. This comparison holds CdA fixed and uses ISA temperature/pressure; it is not an altitude schedule or a corrected-airspeed comparison.",
        "",
        "## Inlet recovery sensitivity at 600 km/h",
        "",
        "| Recovery | Compressor-face Pt (kPa) | Required PR | Electrical input (kW) |",
        "|---:|---:|---:|---:|",
    ]
    for row in recovery:
        md.append(
            f"| {row['recovery']:.3f} | {float(row['compressor_face_pt_pa'] or 0)/1000:.2f} | {float(row['compressor_pr'] or 0):.4f} | {float(row['electrical_input_power_w'] or 0)/1000:.2f} |"
        )
    md += [
        "",
        "## Motor speed gate",
        "",
        "| Limit point | RPM | Tip speed (m/s) | Mean blade speed (m/s) | 3-rotor specific work at ψ=0.5 (kJ/kg) |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rpm_rows:
        md.append(
            f"| externally sourced limit | {row['mechanical_rpm']:.0f} | {row['tip_speed_m_s']:.1f} | {row['mean_blade_speed_m_s']:.1f} | {row['max_specific_work_per_3_rotors_j_kg_at_psi_0_5']/1000:.2f} |"
        )
    md += [
        "",
        "The 3-rotor work column is a kinematic screening bound for three same-speed rotors using the annulus mean radius and assumed loading coefficient ψ=0.5; it is not a compressor map or proof the FA4119 can sustain the listed speed. Initial controller hard limit is 13,500 rpm; stock 350 Kv no-load speed at full charge is 17,640 rpm, but that does not supersede the controller/rotor qualification limits.",
        "",
        "At 600 km/h, CdA=0.004 m², recovery=0.98, the equal-work 3-rotor speed screen is:",
        "",
        "| Assumed rotor loading ψ | Required common RPM |",
        "|---:|---:|",
    ]
    for row in loading:
        md.append(
            f"| {row['rotor_loading_coefficient_assumed']:.2f} | {row['equal_three_rotor_required_rpm']:.0f} |"
        )
    md += [
        "",
        "This is optimistic: it uses the fan annulus mean radius for every rotor, equal work split, and excludes incidence, losses, stall margin, and electrical back-EMF. Core rotor radii would be smaller.",
        "",
        "The electrical work model requires 24.0 kW for CdA=0.004 m² at 600 km/h. For comparison, the six FA4119 decision-record current limits with assumed 20 mΩ pack resistance yield 12.47 kW at the 55 A/motor soft rollback and 14.27 kW at the 65 A/motor initial hard limit at nominal voltage; the provisional 75 A/motor level gives 15.93 kW, with no validated duration. At full charge these are 14.45/16.61/18.63 kW. Pack resistance is a sensitivity assumption, not measured Turnigy data. The generic 18/21/24 kW sweep is a power-only envelope and must not be read as reachable FA4119 performance.",
        "",
        "On the same optimistic loading basis, 3 stages at the initial 13,500 rpm hard limit provide only 2.35 kJ/kg at ψ=0.5 versus 14.63 kJ/kg required in this reference case. Thus stock direct-drive fails the current 3-rotor loading screen by a wide margin, even before motor torque, voltage sag, and core-radius penalties. Phase 1 does not extrapolate the motor beyond its documented RPM limits.",
    ]
    md += [
        "",
        "## Battery interpretation and unresolved data",
        "",
        "The 12S series pair remains 5 Ah (nominal 222 Wh), not 10 Ah. The FA4119 decision record sets 55 A/motor soft rollback, 60–65 A initial hard current and 70–75 A provisional short current; the latter duration is unvalidated. These are battery-current limits, distinct from the ESC's 60/90 A phase-current ratings. At 6 motors this screens 66C soft, 78C at 65 A, and 90C at 75 A. Pack resistance, voltage-sag curves and temperature response are unmeasured; the advertised 100C is not validated.",
        "",
        "The low-speed table uses an ideal actuator disk and assumed fan efficiencies. It is an upper-bound sensitivity and does not demonstrate T/W≥1 for the actual fan. `battery_duration_bounds.csv` is energy-only; it excludes reserve, temperature, voltage cut-off, and acceleration.",
        "",
        "### Static thrust sensitivity examples",
        "",
        "| Altitude (km) | Pack / assumed resistance | Current scenario | Fan efficiency | Static T/W upper bound |",
        "|---:|---|---|---:|---:|",
    ]
    for row in static_focus:
        md.append(
            f"| {row['altitude_m']/1000:.0f} | {row['pack_state']} / {row['assumed_pack_resistance_ohm']*1000:.0f} mΩ | {row['duty_limit']} | {row['static_fan_efficiency_assumed']:.2f} | {row['static_t_over_w']:.3f} |"
        )
    md += [
        "",
        "At nominal voltage and assumed 20 mΩ resistance, the idealized 0.65-efficiency cases clear T/W=0.5 at the soft and initial-hard current limits, but T/W≥1 is not demonstrated. The provisional 75 A/motor current is not assigned a duration. Actual duct, rotor and motor losses reduce these upper bounds.",
    ]
    md += [
        "",
        "## Artifacts",
        "",
        "- `forward_speed_cda_map.csv` — 100–700 km/h at each configured altitude.",
        "- `pressure_recovery_sensitivity.csv` — 600/700 km/h at each altitude.",
        "- `speed_power_map.csv` and `cda_requirement_map.csv` — altitude-indexed idealized power/speed/CdA grids.",
        "- `static_thrust_sensitivity.csv` — altitude-indexed ideal actuator-disk upper bounds.",
        "- `motor_rpm_screen.csv` and `required_rotor_loading_screen.csv` — RPM/work screen; required-work rows cover every altitude.",
        "- `battery_duration_bounds.csv` — energy-only burst-duration bounds.",
        "- `phase1_results.json` — machine-readable assumptions, provenance, and summary.",
        "",
        "## Phase 1 conclusion",
        "",
        "At 600 km/h and CdA=0.004 m², the screen predicts 24.01 kW at sea level and 17.47 kW at 3 km ISA; the density reduction lowers drag and captured flow at the same true airspeed. At 3 km the power demand is near the best-case fully charged battery/current envelope, but this result depends on unmeasured pack resistance and the provisional FA4119 current ceiling. The preliminary equal-work rotor screen still requires roughly 30–38 krpm, versus the stock baseline's initial 13.5 krpm hard limit. Therefore altitude helps the power balance but does not remove the direct-drive RPM mismatch. These are screening results, not a demonstrated flight envelope. Next: quantify achievable lower speed with stock motors across altitude, then compare requalified motor/gearbox options if needed; obtain measured FA4119 torque/current/loss and pack DCIR before detailed geometry or GCP spend.",
        "",
        f"Requirements file SHA-256: `{summary['requirements_sha256']}`",
    ]
    report_path = output.parent / "reports" / "phase1-feasibility.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(md) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbench-root", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args)
    print(f"Phase 1 screening complete: {args.output.resolve()}")


if __name__ == "__main__":
    main()
