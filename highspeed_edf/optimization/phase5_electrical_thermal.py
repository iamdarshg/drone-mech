#!/usr/bin/env python3
"""Local Phase-5 pack/motor/ESC/thermal screen using Phase-3 meanline loads.

PyBaMM's generic Thevenin model is parameter-overridden as a pack-equivalent
Thevenin circuit with an analyst-selected LiPo OCV curve and resistance range.
It is not a Turnigy-identified cell model or a governed native_solver result.
Motor/ESC losses use the Phase-3 efficiency assumptions until FA4119 maps and
Rev-B channel loss measurements are supplied.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
import sys
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def interpolate(x: float, xs: list[float], ys: list[float]) -> float:
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            f = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] * (1 - f) + ys[i + 1] * f
    return ys[-1]


def solve_pack_current(power_w: float, voc_v: float, resistance_ohm: float) -> tuple[float | None, float, float]:
    discriminant = voc_v * voc_v - 4.0 * resistance_ohm * power_w
    if discriminant < 0.0:
        return None, 0.0, voc_v * voc_v / (4.0 * resistance_ohm)
    current = (voc_v - math.sqrt(discriminant)) / (2.0 * resistance_ohm)
    voltage = voc_v - current * resistance_ohm
    return current, voltage, voc_v * voc_v / (4.0 * resistance_ohm)


def thermal_transient(power_w: float, rth: float, cth: float, duration_s: float, ambient_c: float) -> float:
    tau = rth * cth
    if tau <= 0:
        return ambient_c
    return ambient_c + power_w * rth * (1.0 - math.exp(-duration_s / tau))


def run_pybamm_case(
    pybamm: Any,
    *,
    power_w: float,
    r0_pack_ohm: float,
    duration_s: float,
    config: dict[str, Any],
    initial_temperature_k: float,
    ambient_temperature_k: float,
) -> dict[str, Any]:
    import numpy as np

    pybamm.set_logging_level("ERROR")
    pack = config["battery"]
    ecm = pack
    thermal = pack["temperature"]
    model = pybamm.equivalent_circuit.Thevenin(
        options={
            "calculate discharge energy": "false",
            "diffusion element": "false",
            "operating mode": "power",
            "number of rc elements": 1,
        }
    )
    params = model.default_parameter_values.copy()
    soc_axis = np.asarray([float(row[0]) for row in pack["ocvPackCurveSocVoltage"]])
    voltage_axis = np.asarray([float(row[1]) for row in pack["ocvPackCurveSocVoltage"]])
    params.update(
        {
            "Initial SoC": float(pack["initialSoc"]),
            "Initial temperature [K]": initial_temperature_k,
            "Ambient temperature [K]": ambient_temperature_k,
            "Cell capacity [A.h]": float(pack["capacityAh"]),
            "Nominal cell capacity [A.h]": float(pack["capacityAh"]),
            "Upper voltage cut-off [V]": float(pack["fullyChargedVoltageV"]),
            "Lower voltage cut-off [V]": float(pack["lowerVoltageCutoffV"]),
            "Open-circuit voltage [V]": lambda soc: pybamm.Interpolant(
                soc_axis, voltage_axis, soc, name="assumed-12S-LiPo-pack-OCV"
            ),
            "R0 [Ohm]": r0_pack_ohm,
            "R1 [Ohm]": ecm["r1FractionOfR0"] * r0_pack_ohm,
            "C1 [F]": float(ecm["rcTimeConstantSeconds"])
            / (ecm["r1FractionOfR0"] * r0_pack_ohm),
            "Cell thermal mass [J/K]": thermal["packThermalCapacityJPerK"],
            "Cell-jig heat transfer coefficient [W/K]": thermal["cellToJigConductanceWPerK"],
            "Jig thermal mass [J/K]": thermal["jigThermalCapacityJPerK"],
            "Jig-air heat transfer coefficient [W/K]": thermal["jigToAirConductanceWPerK"],
            "Element-1 initial overpotential [V]": 0.0,
            "Entropic change [V/K]": 0.0,
        },
        check_already_exists=False,
    )
    experiment = pybamm.Experiment(
        [pybamm.step.power(power_w, duration=duration_s)]
    )
    sim = pybamm.Simulation(model, parameter_values=params, experiment=experiment)
    solution = sim.solve()
    voltage = [float(x) for x in solution["Battery voltage [V]"].entries]
    current = [float(x) for x in solution["Current [A]"].entries]
    times = [float(x) for x in solution["Time [s]"].entries]
    soc = [float(x) for x in solution["SoC"].entries]
    cell_temp = [float(x) for x in solution["Cell temperature [K]"].entries]
    jig_temp = [float(x) for x in solution["Jig temperature [K]"].entries]
    cutoff = float(pack["lowerVoltageCutoffV"])
    crossing = None
    crossing_index = None
    for index, val in enumerate(voltage):
        if val <= cutoff:
            crossing = times[index]
            crossing_index = index
            break
    if crossing_index is not None:
        voltage = voltage[: crossing_index + 1]
        current = current[: crossing_index + 1]
        times = times[: crossing_index + 1]
        soc = soc[: crossing_index + 1]
        cell_temp = cell_temp[: crossing_index + 1]
        jig_temp = jig_temp[: crossing_index + 1]
    return {
        "solved_duration_s": times[-1],
        "voltage_start_v": voltage[0],
        "voltage_end_v": voltage[-1],
        "minimum_voltage_v": min(voltage),
        "peak_pack_current_a": max(current),
        "soc_start": soc[0],
        "soc_end": soc[-1],
        "pack_delivered_ah": (soc[0] - soc[-1]) * float(pack["capacityAh"]),
                "cutoff_voltage_v": cutoff,
                "first_sample_at_or_below_cutoff_s": crossing,
        "pack_temperature_start_k": cell_temp[0],
        "pack_temperature_end_k": cell_temp[-1],
        "jig_temperature_end_k": jig_temp[-1],
        "pybamm_version": importlib.metadata.version("pybamm"),
        "source_class": "PyBaMM Thevenin reduced-order with analyst OCV/R0/R1/thermal overrides",
    }


def main() -> None:
    study = Path(__file__).resolve().parents[1]
    workbench = Path(r"D:\CodeProjects\aero-multiphysics-workbench")
    sys.path.insert(0, str(workbench))
    for package in (workbench / "packages").glob("*"):
        if package.is_dir():
            sys.path.insert(0, str(package))
    import pybamm
    from aeroworkbench_thermal import ThermalNetwork

    cfg_path = study / "configs" / "phase5_model.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    phase3 = read_csv(study / "results" / "phase3_operating_summary.csv")
    phase3_rows = read_csv(study / "results" / "phase3_meanline_rows.csv")
    speeds = {int(row["speed_kmh"]): row for row in phase3}
    rows_by_speed: dict[int, list[dict[str, str]]] = {}
    for row in phase3_rows:
        rows_by_speed.setdefault(int(row["speed_kmh"]), []).append(row)

    motor_cfg = cfg["motorDrive"]
    battery_cfg = cfg["battery"]
    num_motors = 6
    max_battery_current = {
        "soft": num_motors * float(motor_cfg["batteryCurrentSoftAperChannel"]),
        "initial_hard": num_motors * float(motor_cfg["batteryCurrentInitialHardAperChannel"]),
        "provisional_short": num_motors * float(motor_cfg["batteryCurrentProvisionalShortAperChannel"]),
    }
    pack_power_rows: list[dict[str, Any]] = []
    motor_rows: list[dict[str, Any]] = []
    thermal_rows: list[dict[str, Any]] = []
    drive_eta = float(motor_cfg["motorEfficiencyAssumed"]) * float(motor_cfg["escEfficiencyAssumed"]) * float(motor_cfg["fixedGearboxEfficiencyAssumed"])
    voc_axis_x = [float(row[0]) for row in battery_cfg["ocvPackCurveSocVoltage"]]
    voc_axis_y = [float(row[1]) for row in battery_cfg["ocvPackCurveSocVoltage"]]
    soc0 = float(battery_cfg["initialSoc"])
    voc_initial = interpolate(soc0, voc_axis_x, voc_axis_y)

    for speed_kmh, point in sorted(speeds.items()):
        bus_power = float(point["electrical_power_estimate_w"])
        aero_shaft = float(point["shaft_power_estimate_w"])
        pack_resistances = battery_cfg["packR0SensitivityOhm"]
        for rpack in pack_resistances:
            current, terminal_v, pmax = solve_pack_current(bus_power, voc_initial, float(rpack))
            pack_power_rows.append(
                {
                    "speed_kmh": speed_kmh,
                    "altitude_m": cfg["altitudeM"],
                    "cdA_reference_m2": cfg["designCdAReferenceM2"],
                    "phase3_bus_power_w": bus_power,
                    "phase3_aero_shaft_power_w": aero_shaft,
                    "initial_soc_assumed": soc0,
                    "pack_open_circuit_voltage_v_from_assumed_ocv": voc_initial,
                    "pack_r0_assumed_ohm": rpack,
                    "constant_power_current_solution_a": current,
                    "terminal_voltage_at_start_v": terminal_v,
                    "pack_resistive_heat_w_at_start": current * current * float(rpack) if current is not None else None,
                    "pack_max_power_at_initial_ocv_w": pmax,
                    "power_has_constant_power_solution": current is not None,
                    "aggregate_current_soft_limit_a": max_battery_current["soft"],
                    "aggregate_current_initial_hard_limit_a": max_battery_current["initial_hard"],
                    "aggregate_current_provisional_short_limit_a": max_battery_current["provisional_short"],
                    "pack_current_c_rate": current / float(battery_cfg["capacityAh"]) if current is not None else None,
                    "within_450A_provisional_current_cap": current is not None and current <= max_battery_current["provisional_short"],
                    "evidence_class": "analytical Thevenin power balance; OCV and R0 are assumed sensitivities",
                }
            )
        for row in rows_by_speed[speed_kmh]:
            if row["row_kind"] != "rotor":
                continue
            torque = float(row["motor_torque_nm"])
            phase_current_est = torque / float(motor_cfg["KtIdealFromKvNmPerA"])
            channel_bus_power = float(row["electrical_power_per_channel_w_assumed"])
            channel_current = channel_bus_power / float(battery_cfg["nominalVoltageV"])
            motor_rows.append(
                {
                    "speed_kmh": speed_kmh,
                    "rotor_id": row["row_id"],
                    "rotor_rpm": row["rotor_rpm"],
                    "motor_rpm": row["motor_rpm"],
                    "motor_electrical_rpm": float(row["motor_rpm"]) * int(motor_cfg["polePairs"]),
                    "motor_torque_nm_from_meanline_and_gear": torque,
                    "ideal_kt_from_350kv_nm_per_a": motor_cfg["KtIdealFromKvNmPerA"],
                    "equivalent_torque_current_a_from_ideal_kv": phase_current_est,
                    "esc_phase_current_continuous_limit_a_rms": motor_cfg["escPhaseCurrentContinuousARms"],
                    "esc_phase_current_burst_limit_a_rms": motor_cfg["escPhaseCurrentBurstARms"],
                    "phase_current_exceeds_60a_continuous_estimate": phase_current_est > float(motor_cfg["escPhaseCurrentContinuousARms"]),
                    "phase_current_exceeds_90a_burst_estimate": phase_current_est > float(motor_cfg["escPhaseCurrentBurstARms"]),
                    "channel_bus_power_w_assumed": channel_bus_power,
                    "channel_battery_current_at_44_4v_no_sag_a": channel_current,
                    "fa4119_published_reference_power_w": motor_cfg["motorReferenceElectricalPowerW"],
                    "exceeds_published_power_point_not_a_rating": channel_bus_power > float(motor_cfg["motorReferenceElectricalPowerW"]),
                    "source_class": "Phase-3 meanline load + assumed efficiency chain; Kt inferred ideally from Kv",
                }
            )

        # Steady thermal network for the three heat-producing subsystem types,
        # repeated across the six mirrored motor cells.
        for ambient_c in (45.0, float(battery_cfg["temperature"]["ambient3kmC"])):
            for motor_rth in motor_cfg.get("motorThetaKPerWRange", cfg["simulation"]["thermalRC"]["motorThetaKPerWRange"]):
                network = ThermalNetwork(ambient_c=float(ambient_c))
                component_loss = {"motor": 0.0, "esc": 0.0, "gearbox": 0.0}
                for row in rows_by_speed[speed_kmh]:
                    if row["row_kind"] != "rotor":
                        continue
                    # Phase-3's aero shaft scalar covers the two matching ducts;
                    # divide by two for the per-channel representative node.
                    p_aero = float(row["aero_shaft_power_all_ducts_w"]) / 2.0
                    p_motor_shaft = float(row["motor_shaft_power_per_channel_w"])
                    p_motor_electric = p_motor_shaft / float(motor_cfg["motorEfficiencyAssumed"])
                    p_bus_ch = p_motor_electric / float(motor_cfg["escEfficiencyAssumed"])
                    component_loss["gearbox"] += 2.0 * (p_motor_shaft - p_aero)
                    component_loss["motor"] += 2.0 * (p_motor_electric - p_motor_shaft)
                    component_loss["esc"] += 2.0 * (p_bus_ch - p_motor_electric)
                    stage = row["row_id"]
                    winding, case = f"winding_{stage}", f"motor_case_{stage}"
                    esc_j, esc_case = f"esc_junction_{stage}", f"esc_case_{stage}"
                    gear = f"gearbox_{stage}"
                    network.connect(winding, case, 0.10)
                    network.connect(case, "ambient", float(motor_rth))
                    network.add_load(winding, p_motor_electric - p_motor_shaft)
                    network.connect(esc_j, esc_case, 0.10)
                    network.connect(esc_case, "ambient", 0.45)
                    network.add_load(esc_j, p_bus_ch - p_motor_electric)
                    network.connect(gear, "ambient", 0.30)
                    network.add_load(gear, p_motor_shaft - p_aero)
                tr = network.solve()
                tmap = dict(tr.temperatures_c)
                winding_temps = [v for key, v in tmap.items() if key.startswith("winding_")]
                esc_temps = [v for key, v in tmap.items() if key.startswith("esc_junction_")]
                thermal_rows.append(
                    {
                        "speed_kmh": speed_kmh,
                        "ambient_c": ambient_c,
                        "motor_case_to_air_rth_assumed_k_w": motor_rth,
                        "motor_heat_total_w_assumed": component_loss["motor"],
                        "esc_heat_total_w_assumed": component_loss["esc"],
                        "gearbox_heat_total_w_assumed": component_loss["gearbox"],
                        "max_winding_temp_steady_c_thermal_network": max(winding_temps, default=None),
                        "max_esc_junction_temp_steady_c_thermal_network": max(esc_temps, default=None),
                        "network_energy_residual_w": tr.energy_residual_w,
                        "converged": tr.converged,
                        "source_class": "workbench ThermalNetwork with analyst-set node resistances; steady state only",
                    }
                )

    pybamm_rows: list[dict[str, Any]] = []
    for speed_kmh in cfg["simulation"]["runPyBaMMForSpeedsKmh"]:
        bus_power = float(speeds[int(speed_kmh)]["electrical_power_estimate_w"])
        for rpack in battery_cfg["packR0SensitivityOhm"]:
            for duration in cfg["simulation"]["dischargeDurationsS"]:
                record: dict[str, Any] = {
                    "speed_kmh": speed_kmh,
                    "altitude_m": cfg["altitudeM"],
                    "phase3_constant_bus_power_w": bus_power,
                    "pack_r0_assumed_ohm": rpack,
                    "duration_requested_s": duration,
                    "initial_soc_assumed": soc0,
                    "initial_temperature_c_assumed": float(battery_cfg["temperature"]["initialC"]),
                    "ambient_temperature_c_assumed": float(battery_cfg["temperature"]["ambient3kmC"]),
                }
                try:
                    sim_result = run_pybamm_case(
                        pybamm,
                        power_w=bus_power,
                        r0_pack_ohm=float(rpack),
                        duration_s=float(duration),
                        config=cfg,
                        initial_temperature_k=float(battery_cfg["temperature"]["initialC"]) + 273.15,
                        ambient_temperature_k=float(battery_cfg["temperature"]["ambient3kmC"]) + 273.15,
                    )
                    record.update(sim_result)
                    if sim_result["solved_duration_s"] < float(duration) - 1e-6:
                        record["model_run_state"] = "voltage_cutoff_before_requested_duration"
                    else:
                        record["model_run_state"] = "completed"
                except Exception as exc:  # actual solver/model failure or no-power root
                    record["model_run_state"] = "failed_or_infeasible"
                    record["error"] = f"{type(exc).__name__}:{exc}"
                    record["source_class"] = "PyBaMM attempted with analyst pack overrides; no replacement result"
                pybamm_rows.append(record)

    results_dir = study / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    write_csv(results_dir / "phase5_pack_power_envelope.csv", pack_power_rows)
    write_csv(results_dir / "phase5_motor_drive_loads.csv", motor_rows)
    write_csv(results_dir / "phase5_thermal_steady_bounds.csv", thermal_rows)
    write_csv(results_dir / "phase5_pybamm_runs.csv", pybamm_rows)
    config_hash = hashlib.sha256(cfg_path.read_bytes()).hexdigest()
    summary = {
        "phase": 5,
        "sourceClass": "application-specific reduced-order; PyBaMM library simulation and workbench thermal network",
        "pybammVersion": importlib.metadata.version("pybamm"),
        "configSha256": config_hash,
        "gcpJobs": [],
        "nativeSolverRuns": [],
        "powerPoints": len(pack_power_rows),
        "motorRows": len(motor_rows),
        "thermalScenarios": len(thermal_rows),
        "pybammRuns": len(pybamm_rows),
        "pybammCompleted": sum(row.get("model_run_state") == "completed" for row in pybamm_rows),
        "pybammCutoffTerminated": sum(
            row.get("model_run_state") == "voltage_cutoff_before_requested_duration"
            for row in pybamm_rows
        ),
        "pybammFailedOrInfeasible": sum(
            row.get("model_run_state") == "failed_or_infeasible" for row in pybamm_rows
        ),
        "limits": {
            "turnigyPackR0IsAssumed": True,
            "turnigyOcvCurveIsAssumed": True,
            "fa4119MotorEfficiencyAndKtAreAssumed": True,
            "droneArmBatteryCurrentLimitsAreDecisionRecordValues": True,
            "noGcpSpend": True,
            "noElmerGeometryJob": "no application motor/ESC/battery thermal mesh or measured boundary data exists yet",
        },
    }
    (results_dir / "phase5_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_report(study, cfg, pack_power_rows, motor_rows, thermal_rows, pybamm_rows, summary)
    print(f"Phase 5 local screening complete: {summary['pybammCompleted']}/{len(pybamm_rows)} PyBaMM cases solved")


def write_report(
    study: Path,
    cfg: dict[str, Any],
    pack_rows: list[dict[str, Any]],
    motor_rows: list[dict[str, Any]],
    thermal_rows: list[dict[str, Any]],
    pybamm_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    points = [row for row in pack_rows if row["speed_kmh"] in (500, 600, 650, 700)]
    best_resistance = 0.01
    battery_by_speed = {int(row["speed_kmh"]): row for row in points if row["pack_r0_assumed_ohm"] == best_resistance}
    motor_summary = []
    for speed in (500, 600, 650, 700):
        rows = [r for r in motor_rows if int(r["speed_kmh"]) == speed]
        motor_summary.append((speed, max(r["channel_battery_current_at_44_4v_no_sag_a"] for r in rows), max(r["equivalent_torque_current_a_from_ideal_kv"] for r in rows), max(r["channel_bus_power_w_assumed"] for r in rows)))
    text = [
        "# Phase 5 battery, motor, ESC and thermal screen",
        "",
        f"**Evidence:** local PyBaMM {summary['pybammVersion']} Thevenin-model simulations with application parameter overrides, plus the workbench ThermalNetwork. No GCP, native EM or Elmer job was run. OCV, pack R0/R1/thermal mass, FA4119 Kt/efficiency, gearbox and ESC loss assumptions are explicitly analyst sensitivities—not measured Turnigy/FA4119 maps.",
        "",
        "## Phase-3 load -> electrical/pack envelope at 3 km ISA",
        "",
        "| Speed | System bus power | Pack current at initial OCV, 10 mΩ | Loaded voltage | Ohmic pack heat | C-rate | 450 A (75 A/channel) cap? |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for speed in (500, 600, 650, 700):
        row = battery_by_speed[speed]
        cur = row["constant_power_current_solution_a"]
        text.append(
            f"| {speed} km/h | {row['phase3_bus_power_w']/1000:.2f} kW | {cur if cur is not None else float('nan'):.0f} A | {row['terminal_voltage_at_start_v']:.1f} V | {row['pack_resistive_heat_w_at_start']/1000:.2f} kW | {row['pack_current_c_rate']:.1f}C | {'yes' if row['within_450A_provisional_current_cap'] else 'NO'} |"
        )
    text += [
        "",
        "At 700 km/h the selected reference point asks for more than the current provisional six-channel battery-current ceiling even at the optimistic 10 mΩ pack assumption. At higher assumed R0 values, the constant-power source equation may have no solution or demands >100C; see `phase5_pack_power_envelope.csv`.",
        "",
        "## Stage-specific FA4119/ESC current screen",
        "",
        "| Speed | Max battery current/channel at 44.4 V, no sag | Max Kt-derived torque-current estimate | Max per-channel bus power |",
        "|---:|---:|---:|---:|",
    ]
    for speed, ibat, iphase, pch in motor_summary:
        text.append(f"| {speed} km/h | {ibat:.1f} A | {iphase:.1f} A | {pch/1000:.2f} kW |")
    text += [
        "",
        "The Kt-derived current is a convention-sensitive ideal estimate from 350 Kv, not an independently measured FOC phase current. The six-channel drone-arm hardware contract is 60 A RMS phase continuous / 90 A RMS phase burst; the FA4119 decision record separately gives 55 A soft battery-current rollback, 60–65 A initial hard battery current, and 70–75 A provisional short current with no validated duration. Do not compare battery amps and phase RMS amps as if they were the same limit.",
        "",
        "The FA4119 published 3.47 kW / 74 A / 11,256 rpm result is for an HQ 13x9 prop; it is a comparison point, not a qualified EDF continuous rating. Phase-3 channel loads at high speed approach/exceed this point and exceed the provisional current targets.",
        "",
        "## Custom-parameter PyBaMM discharge",
        "",
        "The Thevenin model is configured as one equivalent 12S pack with 5 Ah capacity, a generic analyst OCV curve, pack-level R0=10/20/30 mΩ, assumed R1=20% of R0 with 5 s time constant, and initial SOC=95%. It simulates fixed-power bursts for 600/650/700 km/h over 5/10/20/30 s. These results are useful sensitivity data, not a Turnigy-identified cell model.",
        "",
        "| Speed | R0 (mΩ) | Requested / solved | End pack voltage | End SOC | Peak pack current | End pack temp | Model status |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in pybamm_rows:
        if int(row["speed_kmh"]) != 700 or int(row["duration_requested_s"]) not in (10, 30):
            continue
        if "voltage_end_v" in row:
            duration_text = f"{float(row['duration_requested_s']):g} / {float(row['solved_duration_s']):.1f} s"
            text.append(f"| 700 | {float(row['pack_r0_assumed_ohm'])*1000:.0f} | {duration_text} | {row['voltage_end_v']:.1f} V | {row['soc_end']:.3f} | {row['peak_pack_current_a']:.0f} A | {row['pack_temperature_end_k']-273.15:.1f} °C | {row['model_run_state']} |")
        else:
            text.append(f"| 700 | {float(row['pack_r0_assumed_ohm'])*1000:.0f} | {row['duration_requested_s']} s | — | — | — | — | {row['model_run_state']} |")
    text += [
        "",
        "## Motor/ESC/gearbox heat sensitivity",
        "",
        "Motor, ESC and gearbox steady temperatures are computed with the workbench thermal RC network under assumed component-to-air thermal resistances. Heat totals count both mirrored ducts while the reported temperatures are representative per-channel nodes. The workbench solver's strict convergence flag is false for these cases, although its energy residual is about 2.4e-5 W; treat temperatures as indicative screening estimates, not certified equilibria. See `phase5_thermal_steady_bounds.csv`; these are not a substitute for Elmer with application geometry and measured convection/contact data.",
        "",
        "## Phase 5 disposition",
        "",
        "- **Pack-limited:** the 12S 5 Ah series pair has nominal energy 222 Wh; at 700 km/h the requested electrical power is not achievable under the six-channel 75 A provisional current cap for the tested pack-R0 envelope. Even under the 100C label, duration and voltage sag are not validated.",
        "- **Motor/ESC-limited:** FA4119 shaft/current losses and Rev-B phase current do not close at the current high-speed load estimate. The selected motor's actual resistance, inductance, Kv, phase-current convention, thermal resistance and efficiency map require first-article dyno data.",
        "- **Thermal:** battery peak heat and motor/ESC/gearbox temperature are highly sensitive to unmeasured pack R0, thermal capacity and cooling resistance. Passive duct-air cooling/cooling drag are not yet coupled.",
        "- **GCP spend:** $0.00 for this pass. A GCP PyBaMM job would not improve the answer without a Turnigy OCV/DCIR/thermal data set. An Elmer job is not justified before motor/ESC/battery CAD and boundary conditions exist.",
        "",
        "Requested workbench capability, for owner review: allow a versioned custom PyBaMM Thevenin parameter set / inline parameter payload and lift the generic participant's 100 A discharge-current limit for pack-level high-C discharge studies, with tests and explicit parameter provenance. The current application-side override is retained here and not added to the shared repository.",
        "",
        f"PyBaMM full-duration runs: {summary['pybammCompleted']}/{summary['pybammRuns']}; {summary['pybammCutoffTerminated']} ended at voltage cutoff before requested duration; infeasible/solver failures and their errors are preserved in `phase5_pybamm_runs.csv`.",
    ]
    (study / "reports" / "phase5-electrical-thermal.md").write_text("\n".join(text) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
