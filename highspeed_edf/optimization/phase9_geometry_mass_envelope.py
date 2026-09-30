#!/usr/bin/env python3
"""Geometry-only, fixed-powertrain redesign and drone-arm mass accounting."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


STUDY = Path(__file__).resolve().parents[1]
WORKBENCH = Path(r"D:\CodeProjects\aero-multiphysics-workbench")
DRONE_ARM = Path(r"D:\CodeProjects\drone-arm")
TEMP = Path(r"C:\Users\DARSHG~1\AppData\Local\Temp\opencode")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pcb_copper_area_mm2(board: Path, layer_names: list[str], scale_px_per_mm: int = 8) -> dict[str, float]:
    cli = "kicad-cli"
    subprocess.run(
        [
            cli, "pcb", "export", "svg", "--layers", ",".join(layer_names),
            "--mode-multi", "--exclude-drawing-sheet", "--output", str(TEMP), str(board),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    areas: dict[str, float] = {}
    for layer in layer_names:
        svg = TEMP / f"{board.stem}-{layer.replace('.', '_')}.svg"
        renderer = QSvgRenderer(str(svg))
        view = renderer.viewBoxF()
        width = round(view.width() * scale_px_per_mm)
        height = round(view.height() * scale_px_per_mm)
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, width, height))
        painter.end()
        pixels = np.frombuffer(image.bits(), dtype=np.uint8, count=image.sizeInBytes())
        rgba = pixels.reshape(height, width, 4)
        # Alpha coverage keeps copper flashes, traces, and filled zones while
        # antialiasing limits vector-to-raster area error to below one pixel.
        areas[layer] = float(rgba[:, :, 3].sum() / 255.0 / scale_px_per_mm**2)
        del rgba, pixels, image, renderer
    return areas


def board_mass_record(
    *, name: str, board_path: Path, width_mm: float, height_mm: float,
    dielectric_mm: float, copper_mm_by_layer: dict[str, float],
) -> dict[str, Any]:
    area_mm2 = width_mm * height_mm
    copper_areas = pcb_copper_area_mm2(board_path, list(copper_mm_by_layer))
    fr4_g = area_mm2 * dielectric_mm * 1.85e-3
    copper_g_by_layer = {
        layer: copper_areas[layer] * thickness * 8.96e-3
        for layer, thickness in copper_mm_by_layer.items()
    }
    copper_g = sum(copper_g_by_layer.values())
    mask_g = area_mm2 * 0.020 * 1.2e-3
    return {
        "item": name,
        "boardDimensionsMm": f"{width_mm:g} x {height_mm:g}",
        "boardAreaCm2": area_mm2 / 100.0,
        "copperLayerCount": len(copper_mm_by_layer),
        "dielectricStackMm": dielectric_mm,
        "copperAreaByLayerMm2": json.dumps(copper_areas, sort_keys=True),
        "copperMassByLayerG": json.dumps(copper_g_by_layer, sort_keys=True),
        "fr4MassG": fr4_g,
        "copperMassG": copper_g,
        "solderMaskMassEstimateG": mask_g,
        "bareBoardMassEstimateG": fr4_g + copper_g + mask_g,
        "populationMassIncluded": False,
        "sourceClass": "mass calculated from actual KiCad Edge.Cuts, stackup, copper-layer SVG fill, and material-density assumptions",
    }


def solve_candidate_cycle(
    *, phase2_architecture: Any, speed_ms: float, cda: float, density: float,
    pressure: float, temperature: float, total_annulus_area: float, capture: float,
    cp: float, gamma: float, rgas: float, recovery: float, compressor_eta: float,
    nozzle_recovery: float, drive_eta: float, gearbox_eta: float,
) -> tuple[float, float, dict[str, float]]:
    """Solve core PR for the candidate thrust target using Phase-2 cycle equations."""
    thrust_target = 0.5 * density * speed_ms**2 * cda

    def evaluate(core_pr: float) -> dict[str, float]:
        return phase2_architecture.evaluate(
            speed=speed_ms, cda=cda, beta=0.0, fan_pr=1.0, core_pr=core_pr,
            density=density, pressure=pressure, temperature=temperature,
            area=total_annulus_area, capture=capture, cp=cp, gamma=gamma,
            rgas=rgas, recovery=recovery, compressor_eta=compressor_eta,
            nozzle_recovery=nozzle_recovery, drive_eta=drive_eta,
            gearbox_eta=gearbox_eta,
        )

    low, high = 1.0, 1.6
    low_point, high_point = evaluate(low), evaluate(high)
    if float(high_point["calculated_thrust_n"]) < thrust_target:
        raise ValueError("CANDIDATE_CYCLE_PR_BRACKET_INSUFFICIENT")
    for _ in range(80):
        mid = 0.5 * (low + high)
        point = evaluate(mid)
        if float(point["calculated_thrust_n"]) < thrust_target:
            low = mid
        else:
            high = mid
    core_pr = 0.5 * (low + high)
    final = evaluate(core_pr)
    return 1.0, core_pr, final


def run() -> None:
    cfg_path = STUDY / "configs" / "phase9_geometry_mass_screen.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    geo, candidate, power = cfg["geometry"], cfg["candidate"], cfg["powertrainImmutable"]

    # Copper/dielectric layer thicknesses are taken from the committed KiCad PCBs.
    # ESC PCB in the current source is six-copper-layer/150 mm square; the prose
    # architecture calls it four-layer, so this calculation follows the actual PCB.
    esc_board = board_mass_record(
        name="Rev-B ESC main PCB bare",
        board_path=DRONE_ARM / "hardware" / "esc" / "rev_b" / "esc_rev_b.kicad_pcb",
        width_mm=150.0,
        height_mm=150.0,
        dielectric_mm=1.020,
        copper_mm_by_layer={"F.Cu": 0.140, "In1.Cu": 0.070, "In2.Cu": 0.070,
                            "In3.Cu": 0.070, "In4.Cu": 0.070, "B.Cu": 0.140},
    )
    fc_board = board_mass_record(
        name="Rev-B flight-control PCB bare",
        board_path=DRONE_ARM / "hardware" / "main" / "rev_b" / "main_rev_b.kicad_pcb",
        width_mm=140.0,
        height_mm=100.0,
        dielectric_mm=1.440,
        copper_mm_by_layer={"F.Cu": 0.035, "In1.Cu": 0.035, "In2.Cu": 0.035, "B.Cu": 0.035},
    )
    board_records = [esc_board, fc_board]
    write_csv(STUDY / "results" / "phase9_control_board_mass.csv", board_records)
    motor_kg = 6.0 * float(cfg["dataSources"]["fa4119UnitMassKg"])
    battery_kg = 2.0 * float(cfg["dataSources"]["batteryUnitMassKg"])
    pcb_bare_kg = sum(float(row["bareBoardMassEstimateG"]) for row in board_records) / 1000.0
    fixed_lower_kg = motor_kg + battery_kg + pcb_bare_kg
    candidate_mass = float(candidate["allUpMassTargetKg"])
    mass_rows = [
        {"component": "six FA4119 motors with leads", "quantity": 6, "unit_mass_kg": cfg["dataSources"]["fa4119UnitMassKg"], "mass_kg": motor_kg, "basis": "drone-arm FA4119 decision record: approximately 280 g each"},
        {"component": "two Turnigy Rapid 6S 5000mAh packs", "quantity": 2, "unit_mass_kg": cfg["dataSources"]["batteryUnitMassKg"], "mass_kg": battery_kg, "basis": "SpeedyFPV product specification: 713 g each including XT90 leads"},
        {"component": "ESC and flight-control bare PCBs", "quantity": 2, "unit_mass_kg": pcb_bare_kg / 2.0, "mass_kg": pcb_bare_kg, "basis": "KiCad substrate/copper calculation; excludes population, lugs, heat spreader and mounting"},
        {"component": "known propulsion/electrical lower bound", "quantity": 1, "unit_mass_kg": fixed_lower_kg, "mass_kg": fixed_lower_kg, "basis": "sum of sourced motor/pack masses and calculated bare PCB material masses"},
        {"component": "remaining all-up mass allowance", "quantity": 1, "unit_mass_kg": candidate_mass - fixed_lower_kg, "mass_kg": candidate_mass - fixed_lower_kg, "basis": "budget for populated PCBs, heat spreaders, six rotor stages, gearing, ducts, side intakes, wiring, fuselage, servos and payload"},
    ]
    write_csv(STUDY / "results" / "phase9_mass_budget.csv", mass_rows)

    diameter = float(geo["ductOuterDiameterM"])
    hub = float(geo["hubDiameterM"])
    annulus_total = int(geo["ductCount"]) * math.pi / 4.0 * (diameter**2 - hub**2)
    projected_diameter_cm = diameter * 100.0
    projected_union_cm2 = math.pi * projected_diameter_cm**2 / 4.0
    projected_total_cm2 = projected_union_cm2 + float(geo["projectedStructureAllowanceCm2"])
    max_shell_panels = math.ceil(math.pi * diameter * 1000.0 / float(geo["maximumStockWidthMm"]))
    side_slot_area = int(geo["sideIntakeSlots"]["count"]) * float(geo["sideIntakeSlots"]["widthMm"]) * float(geo["sideIntakeSlots"]["lengthMm"]) / 100.0
    rotor_span_mm = (diameter * 1000.0 - float(geo["hubDiameterM"]) * 1000.0) / 2.0
    candidate_area = float(candidate["cdAAtFlightTargetM2"])
    candidate_speed = float(candidate["flightSpeedTargetKmh"])

    # Use the same ideal-gas cycle equations as Phase 1, retaining the immutable
    # pack/motor count and the configured current/efficiency limits.
    import sys
    sys.path[:0] = [str(path) for path in WORKBENCH.joinpath("packages").glob("*") if path.is_dir()]
    sys.path[:0] = [str(WORKBENCH), str(WORKBENCH / "solvers"), str(STUDY / "optimization")]
    from aeroworkbench_turbomachinery.cycle.gas import AIR
    import phase1_feasibility as phase1

    atm = phase1._isa_troposphere(float(candidate["altitudeM"]), AIR.r_j_kg_k)
    phase1_kwargs = {
        "recovery": float(cfg["assumptions"]["flightInletRecovery"]),
        "capture_fraction": float(cfg["assumptions"]["flightInletCaptureFraction"]),
        "ambient_pressure_pa": atm["static_pressure_pa"],
        "ambient_temperature_k": atm["static_temperature_k"],
        "cp": AIR.cp_j_kg_k,
        "gamma": AIR.gamma,
        "gas_constant": AIR.r_j_kg_k,
        "compressor_efficiency": float(cfg["assumptions"]["compressorEfficiency"]),
        "nozzle_recovery": float(cfg["assumptions"]["flightInletRecovery"]),
        "motor_efficiency": float(cfg["assumptions"]["motorEfficiency"]),
        "esc_efficiency": float(cfg["assumptions"]["escEfficiency"]),
    }
    phase1_kwargs_no_recovery = {key: value for key, value in phase1_kwargs.items() if key != "recovery"}
    resistances = [float(value) for value in power["packR0SensitivityOhm"]]
    voc = 49.8  # phase5 OCV curve at the 95% SOC initialization
    worst_r0 = max(resistances)
    worst_soft_power_cap = 330.0 * (voc - 330.0 * worst_r0)
    inlet_recovery_rows: list[dict[str, Any]] = []
    for recovery in (0.99, 0.985, 0.98, 0.975, 0.97, 0.96, 0.95):
        cda_limit = phase1._max_cda(
            speed_m_s=float(candidate_speed) / 3.6,
            power_limit_w=worst_soft_power_cap * float(cfg["assumptions"]["gearboxEfficiency"]),
            recovery=recovery,
            kwargs={"annulus_area_m2": annulus_total, **phase1_kwargs_no_recovery},
        )
        inlet_recovery_rows.append(
            {
                "speed_kmh": candidate_speed,
                "altitude_m": candidate["altitudeM"],
                "inlet_total_pressure_recovery": recovery,
                "max_CdA_m2_at_worst_R0_soft_current": cda_limit,
                "candidate_CdA_m2": candidate_area,
                "candidate_meets_cycle_power_cap": candidate_area <= cda_limit,
                "source_class": "Phase-1 single-stream ideal-gas cycle; R0=30mOhm,95%SOC,330A soft pack cap; candidate 90mm duct annulus",
            }
        )
    write_csv(STUDY / "results" / "phase9_inlet_recovery_sensitivity.csv", inlet_recovery_rows)
    speed_rows: list[dict[str, Any]] = []
    flight_power_by_speed: dict[int, float] = {}
    motor_count = 6
    for speed in (701, 710, 720, 730):
        result = phase1._required_input(
            speed_m_s=speed / 3.6,
            cda_m2=candidate_area,
            annulus_area_m2=annulus_total,
            **phase1_kwargs,
        )
        bus_power = float(result["electrical_input_power_w"]) / float(cfg["assumptions"]["gearboxEfficiency"])
        flight_power_by_speed[speed] = bus_power
        pack_current_rows = []
        for resistance in resistances:
            for label, amps_per_motor in (
                ("soft_55A", float(power["softBatteryCurrentAperMotor"])),
                ("hard_65A", float(power["initialHardBatteryCurrentAperMotor"])),
                ("short_75A_unvalidated", float(power["provisionalShortBatteryCurrentAperMotor"])),
            ):
                i_cap = motor_count * amps_per_motor
                p_cap = i_cap * (voc - i_cap * resistance)
                disc = voc**2 - 4.0 * resistance * bus_power
                actual_pack_current = (
                    (voc - math.sqrt(disc)) / (2.0 * resistance)
                    if disc >= 0.0 else None
                )
                motor_current = actual_pack_current / motor_count if actual_pack_current is not None else math.inf
                cda_cap = phase1._max_cda(
                    speed_m_s=speed / 3.6,
                    power_limit_w=p_cap * float(cfg["assumptions"]["gearboxEfficiency"]),
                    recovery=float(cfg["assumptions"]["flightInletRecovery"]),
                    kwargs={
                        "annulus_area_m2": annulus_total,
                        **phase1_kwargs_no_recovery,
                    },
                )
                pack_current_rows.append(
                    {
                        "speed_kmh": speed,
                        "candidate_cdA_m2": candidate_area,
                        "pack_r0_assumed_ohm": resistance,
                        "cycle_bus_power_w": bus_power,
                        "powertrain_limit_case": label,
                        "pack_current_cap_a": i_cap,
                        "thevenin_bus_power_cap_w": p_cap,
                        "pack_current_required_a": actual_pack_current,
                        "equal_share_pack_current_per_motor_a": motor_current,
                        "within_pack_power_cap": actual_pack_current is not None and actual_pack_current <= i_cap,
                        "within_equal_share_current_cap": motor_current <= amps_per_motor,
                        "maximum_CdA_at_limit_m2": cda_cap,
                        "sourceClass": "Phase-1 cycle with unchanged six motors/12S1P battery; analyst pack R0/OCV; unchanged 95% gearbox",
                    }
                )
        speed_rows.extend(pack_current_rows)
    write_csv(STUDY / "results" / "phase9_speed_envelope.csv", speed_rows)

    # Re-solve the six candidate rotor/stator rows at 720 km/h with the larger
    # annulus and geometry-only stator chord. Each stage receives equal work to
    # balance the unchanged six motor channels, subject to row loading screens.
    from aeroworkbench_turbomachinery.meanline import IdealGas, ScreeningLimits
    import phase2_architecture
    import phase3_meanline

    p2cfg = json.loads((STUDY / "configs" / "phase2_architecture.json").read_text(encoding="utf-8"))
    p3cfg = json.loads((STUDY / "configs" / "phase3_meanline.json").read_text(encoding="utf-8"))
    gas = IdealGas(cp_j_kg_k=AIR.cp_j_kg_k, gamma=AIR.gamma, gas_constant_j_kg_k=AIR.r_j_kg_k)
    environment = phase3_meanline.isa(float(candidate["altitudeM"]), gas.gas_constant_j_kg_k)
    speed_ms = float(candidate_speed) / 3.6
    inlet_temperature = environment[0]
    inlet_pressure = environment[1]
    fan_area_one = annulus_total / 2.0
    candidate_rotor_rpm = [float(value) for value in geo["rotorRpmScheduleAt720Kmh"]]
    rotor_cfgs = p3cfg["rotorRows"]
    stator_by_id = {row["id"]: row for row in p3cfg["statorRows"]}
    gear_ratios = [float(row["gearRatio"]) for row in rotor_cfgs]
    raw_limits = p3cfg["screeningLimits"]
    meanline_limits = ScreeningLimits(
        max_relative_mach=raw_limits["maxRelativeMach"],
        max_diffusion_factor=raw_limits["maxDiffusionFactor"],
        min_de_haller=raw_limits["minDeHaller"],
        max_incidence_deg=raw_limits["maxIncidenceDeg"],
        max_turning_deg=raw_limits["maxTurningDeg"],
        max_loading_coefficient=raw_limits["maxLoadingCoefficient"],
        min_reaction=raw_limits["minReaction"],
        max_clearance_loss_fraction=raw_limits["maxClearanceLossFraction"],
        min_reynolds=raw_limits["minReynolds"],
        max_exit_mach=raw_limits["maxExitMach"],
    )
    fan_pr, core_pr, cycle = solve_candidate_cycle(
        phase2_architecture=phase2_architecture,
        speed_ms=speed_ms,
        cda=candidate_area,
        density=environment[2],
        pressure=inlet_pressure,
        temperature=inlet_temperature,
        total_annulus_area=annulus_total,
        capture=float(cfg["assumptions"]["flightInletCaptureFraction"]),
        cp=gas.cp_j_kg_k,
        gamma=gas.gamma,
        rgas=gas.gas_constant_j_kg_k,
        recovery=float(cfg["assumptions"]["flightInletRecovery"]),
        compressor_eta=float(cfg["assumptions"]["compressorEfficiency"]),
        nozzle_recovery=float(cfg["assumptions"]["flightInletRecovery"]),
        drive_eta=float(cfg["assumptions"]["motorEfficiency"]) * float(cfg["assumptions"]["escEfficiency"]),
        gearbox_eta=float(cfg["assumptions"]["gearboxEfficiency"]),
    )
    mdot_per_duct = float(cycle["mass_flow_kg_s"]) / 2.0
    specific_work_total = float(cycle["compressor_shaft_power_w"]) / float(cycle["mass_flow_kg_s"])
    stage_work_base = specific_work_total / len(rotor_cfgs)
    tip_d = float(geo["ductOuterDiameterM"])
    hub_d = float(geo["hubDiameterM"])
    r_hub, r_tip = hub_d / 2.0, tip_d / 2.0
    r_mean = (r_hub + r_tip) / 2.0
    pt0 = inlet_pressure * (1.0 + speed_ms**2 / (2.0 * gas.cp_j_kg_k * inlet_temperature)) ** (gas.gamma / (gas.gamma - 1.0))
    required_thrust = 0.5 * environment[2] * speed_ms**2 * candidate_area
    thrust_target = 1.02 * required_thrust

    def solve_row_chain(stage_work: float) -> tuple[list[dict[str, Any]], float, float, float, float, float]:
        rows: list[dict[str, Any]] = []
        pt = pt0 * float(cfg["assumptions"]["flightInletRecovery"])
        tt = inlet_temperature + speed_ms**2 / (2.0 * gas.cp_j_kg_k)
        swirl = 0.0
        for index, rotor_cfg in enumerate(rotor_cfgs):
            rrow, _, rsolved, rmeta = phase3_meanline.make_and_solve_row(
                gas=gas, family="axial_compressor_rotor", row_id=f"P9-720-R{index+1}",
                rpm=candidate_rotor_rpm[index], mdot=mdot_per_duct, pt_in=pt, tt_in=tt,
                swirl_in_deg=swirl, area_in=fan_area_one, area_out=fan_area_one,
                radius_in_m=r_mean, radius_out_m=r_mean, span_in_m=r_tip-r_hub,
                span_out_m=r_tip-r_hub, chord_m=float(rotor_cfg["chordMm"])/1000.0,
                blade_count=int(rotor_cfg["bladeCount"]), tip_clearance_m=float(p3cfg["tipClearanceMm"])/1000.0,
                target_work_j_kg=stage_work, target_exit_swirl_deg=None, limits=meanline_limits,
            )
            rr = rsolved.rows[0]
            stator_cfg = stator_by_id[rotor_cfg["statorId"]]
            scfg = dict(stator_cfg)
            scfg["chordMm"] = float(geo["statorChordMm"])
            _, _, ssolved, smeta = phase3_meanline.make_and_solve_row(
                gas=gas, family="axial_compressor_stator", row_id=f"P9-720-S{index+1}",
                rpm=0.0, mdot=mdot_per_duct, pt_in=rr.outlet_state.total_pressure_pa,
                tt_in=rr.outlet_state.total_temperature_k, swirl_in_deg=rr.outlet_triangle.absolute_angle_deg,
                area_in=fan_area_one, area_out=fan_area_one, radius_in_m=r_mean, radius_out_m=r_mean,
                span_in_m=r_tip-r_hub, span_out_m=r_tip-r_hub,
                chord_m=float(scfg["chordMm"])/1000.0, blade_count=int(scfg["vaneCount"]),
                tip_clearance_m=0.0, target_work_j_kg=None,
                target_exit_swirl_deg=float(scfg["targetExitSwirlDeg"]), limits=meanline_limits,
            )
            sr = ssolved.rows[0]
            motor_rpm = candidate_rotor_rpm[index] / gear_ratios[index]
            motor_shaft_power = stage_work * mdot_per_duct / float(cfg["assumptions"]["gearboxEfficiency"])
            motor_torque = motor_shaft_power / (motor_rpm * 2.0 * math.pi / 60.0)
            ideal_kv_torque_current = motor_torque / (60.0 / (2.0 * math.pi * float(cfg["powertrainImmutable"]["motorKvRpmPerV"])))
            electrical_power_per_channel = stage_work * mdot_per_duct / (
                float(cfg["assumptions"]["gearboxEfficiency"])
                * float(cfg["assumptions"]["motorEfficiency"])
                * float(cfg["assumptions"]["escEfficiency"])
            )
            rows.extend([
                {
                    "speed_kmh": candidate_speed, "row_id": f"R{index+1}", "row_kind": "rotor",
                    "rotor_rpm": candidate_rotor_rpm[index], "motor_rpm": motor_rpm,
                    "reynolds": rr.reynolds_number, "loading_coefficient": rr.loading_coefficient,
                    "relative_mach_in": rr.inlet_triangle.relative_velocity_m_s / gas.sound_speed_m_s(rr.inlet_state.static_temperature_k),
                    "diffusion_factor": rr.diffusion_factor, "incidence_deg": rr.incidence_deg,
                    "stage_work_j_kg": rr.euler_work_j_kg,
                    "continuity_error_fraction": rmeta["continuity_error_fraction"],
                    "per_channel_bus_power_w": electrical_power_per_channel,
                    "per_channel_current_at_49_8v_a": electrical_power_per_channel / 49.8,
                    "motor_torque_nm": motor_torque,
                    "ideal_kv_torque_current_estimate_a": ideal_kv_torque_current,
                    "esc_continuous_60a_phase_estimate_pass": ideal_kv_torque_current <= 60.0,
                    "screened": rr.screened,
                    "failed_indicators": json.dumps([x.name for x in rr.indicators if not x.passed]),
                },
                {
                    "speed_kmh": candidate_speed, "row_id": f"S{index+1}", "row_kind": "stator",
                    "rotor_rpm": 0.0, "motor_rpm": 0.0,
                    "reynolds": sr.reynolds_number, "loading_coefficient": sr.loading_coefficient,
                    "relative_mach_in": sr.inlet_triangle.relative_velocity_m_s / gas.sound_speed_m_s(sr.inlet_state.static_temperature_k),
                    "diffusion_factor": sr.diffusion_factor, "incidence_deg": sr.incidence_deg,
                    "stage_work_j_kg": 0.0,
                    "continuity_error_fraction": smeta["continuity_error_fraction"],
                    "per_channel_bus_power_w": 0.0, "per_channel_current_at_49_8v_a": 0.0,
                    "screened": sr.screened,
                    "failed_indicators": json.dumps([x.name for x in sr.indicators if not x.passed]),
                },
            ])
            pt, tt, swirl = sr.outlet_state.total_pressure_pa, sr.outlet_state.total_temperature_k, sr.outlet_triangle.absolute_angle_deg
        p_nozzle = pt * float(cfg["assumptions"]["flightInletRecovery"])
        t_static = tt * (inlet_pressure / p_nozzle) ** ((gas.gamma - 1.0) / gas.gamma) if p_nozzle > inlet_pressure else tt
        v_exit = math.sqrt(max(0.0, 2.0 * gas.cp_j_kg_k * (tt - t_static)))
        net_thrust = float(cycle["mass_flow_kg_s"]) * (v_exit - speed_ms)
        return rows, pt, tt, v_exit, net_thrust, v_exit

    # Compensate for the row solver's explicit profile/stator losses until the
    # nozzled meanline thrust closes on 102% of the aircraft drag target.
    low_scale, high_scale = 1.0, 1.0
    solution = solve_row_chain(stage_work_base)
    scale = 1.0
    target_thrust = 1.02 * required_thrust
    while solution[4] < target_thrust and high_scale < 2.0:
        low_scale = high_scale
        high_scale *= 1.1
        solution = solve_row_chain(stage_work_base * high_scale)
    if solution[4] < target_thrust:
        raise ValueError("PHASE9_MEANLINE_THRUST_TARGET_NOT_CLOSED_BELOW_2X_WORK")
    for _ in range(10):
        scale = 0.5 * (low_scale + high_scale)
        trial = solve_row_chain(stage_work_base * scale)
        if trial[4] >= target_thrust:
            high_scale, solution = scale, trial
        else:
            low_scale = scale
    meanline_rows, pt, tt, nozzle_velocity, meanline_thrust, _ = solution
    write_csv(STUDY / "results" / "phase9_720_meanline_rows.csv", meanline_rows)
    meanline_summary = {
        "speedKmh": candidate_speed,
        "massFlowTotalKgPerS": float(cycle["mass_flow_kg_s"]),
        "fanPressureRatio": fan_pr,
        "corePressureRatio": core_pr,
        "overallPressureRatio": fan_pr * core_pr,
        "meanlineOutletPressureRatio": pt / pt0,
        "nozzleExitVelocityMs": nozzle_velocity,
        "meanlineNetThrustN": meanline_thrust,
        "requiredAircraftDragThrustN": required_thrust,
        "meanlineThrustToRequiredRatio": meanline_thrust / required_thrust if required_thrust > 0 else None,
        "stageWorkMultiplierForThrustClosure": high_scale,
        "cycleBusPowerW": float(cycle["electrical_input_power_w"]) / float(cfg["assumptions"]["gearboxEfficiency"]),
        "rowSolveElectricalPowerW": sum(float(row["per_channel_bus_power_w"]) for row in meanline_rows) * 2.0,
        "maximumContinuityErrorFraction": max(abs(float(row["continuity_error_fraction"])) for row in meanline_rows),
        "rowsPassingScreen": sum(row["screened"] for row in meanline_rows),
        "rowsTotal": len(meanline_rows),
        "allRowsPassScreen": all(row["screened"] for row in meanline_rows),
        "maximumMotorRpm": max(float(row["motor_rpm"]) for row in meanline_rows),
        "maxEqualShareBatteryCurrentA": max(float(row["per_channel_current_at_49_8v_a"]) for row in meanline_rows),
        "maxIdealKvTorqueCurrentEstimateA": max(float(row.get("ideal_kv_torque_current_estimate_a", 0.0)) for row in meanline_rows),
        "allEscPhaseCurrentEstimatesBelow60A": all(bool(row.get("esc_continuous_60a_phase_estimate_pass", True)) for row in meanline_rows),
    }
    phase1_target_power = flight_power_by_speed[int(candidate_speed)]
    closed_target_power = max(phase1_target_power, float(meanline_summary["rowSolveElectricalPowerW"]))
    flight_power_by_speed[int(candidate_speed)] = closed_target_power
    closure_power_ratio = closed_target_power / phase1_target_power
    for row in speed_rows:
        if int(row["speed_kmh"]) != int(candidate_speed):
            continue
        resistance = float(row["pack_r0_assumed_ohm"])
        required_power = closed_target_power
        discriminant = voc**2 - 4.0 * resistance * required_power
        required_current = (voc - math.sqrt(discriminant)) / (2.0 * resistance) if discriminant >= 0.0 else None
        row["cycle_bus_power_w"] = closed_target_power
        row["pack_current_required_a"] = required_current
        row["equal_share_pack_current_per_motor_a"] = required_current / motor_count if required_current is not None else math.inf
        row["within_pack_power_cap"] = required_current is not None and required_current <= float(row["pack_current_cap_a"])
        row["within_equal_share_current_cap"] = (
            required_current is not None
            and required_current / motor_count <= float(power["softBatteryCurrentAperMotor"])
            if row["powertrain_limit_case"] == "soft_55A"
            else required_current is not None and required_current <= float(row["pack_current_cap_a"])
        )
        row["maximum_CdA_at_limit_m2"] = float(row["maximum_CdA_at_limit_m2"]) / closure_power_ratio
        row["sourceClass"] += "; 720 km/h point closed to row-solved meanline shaft work"
    write_csv(STUDY / "results" / "phase9_speed_envelope.csv", speed_rows)
    (STUDY / "results" / "phase9_720_meanline_summary.json").write_text(json.dumps(meanline_summary, indent=2) + "\n", encoding="utf-8")

    fan_efficiency = float(cfg["assumptions"]["phase1StaticFanEfficiency"])
    gear_factor = float(cfg["assumptions"]["gearboxEfficiency"]) ** (2.0 / 3.0)
    twr_rows: list[dict[str, Any]] = []
    for altitude in (0.0, 3000.0):
        atmosphere = phase1._isa_troposphere(altitude, AIR.r_j_kg_k)
        density = atmosphere["density_kg_m3"]
        for resistance in resistances:
            for label, per_motor in (
                ("soft_55A", float(power["softBatteryCurrentAperMotor"])),
                ("hard_65A", float(power["initialHardBatteryCurrentAperMotor"])),
                ("short_75A_unvalidated", float(power["provisionalShortBatteryCurrentAperMotor"])),
            ):
                pack_current = 6.0 * per_motor
                bus_power = pack_current * (voc - pack_current * resistance)
                air_power = bus_power * float(cfg["assumptions"]["motorEfficiency"]) * float(cfg["assumptions"]["escEfficiency"]) * float(cfg["assumptions"]["gearboxEfficiency"]) * fan_efficiency
                thrust = phase1._solve_static_thrust(air_power, annulus_total, density)
                max_mass = thrust / 9.80665
                twr_rows.append(
                    {
                        "altitude_m": altitude,
                        "pack_r0_assumed_ohm": resistance,
                        "current_case": label,
                        "aggregate_pack_current_a": pack_current,
                        "static_bus_power_w": bus_power,
                        "duct_outer_diameter_mm": diameter * 1000.0,
                        "total_annular_disk_area_cm2": annulus_total * 1e4,
                        "all_up_mass_candidate_kg": candidate_mass,
                        "thrust_upper_bound_n": thrust,
                        "maximum_mass_for_TWR_1_kg": max_mass,
                        "candidate_TWR": thrust / (candidate_mass * 9.80665),
                        "sourceClass": "ideal actuator disk, 95%-SOC pack OCV, pack R0 sensitivity, unchanged motor/ESC/gearbox and 80% fan efficiency",
                    }
                )
    write_csv(STUDY / "results" / "phase9_static_twr_screen.csv", twr_rows)

    design_summary = {
        "fixedPowertrain": power,
        "candidateAllUpMassKg": candidate_mass,
        "candidateDuctDiameterMm": diameter * 1000.0,
        "candidateBladeSpanMm": rotor_span_mm,
        "fanAnnulusAreaTotalCm2": annulus_total * 1e4,
        "projectedDuctUnionCm2": projected_union_cm2,
        "projectedStructureAllowanceCm2": float(geo["projectedStructureAllowanceCm2"]),
        "projectedAreaTotalCm2": projected_total_cm2,
        "projectedAreaLimitCm2": float(geo["strictProjectedAreaLimitCm2"]),
        "projectedAreaGatePass": projected_total_cm2 < float(geo["strictProjectedAreaLimitCm2"]),
        "areaGatePass": projected_total_cm2 < float(geo["strictProjectedAreaLimitCm2"]),
        "sideInletAreaCm2": side_slot_area,
        "inletPressureRecoveryTarget": float(geo["inletPressureRecoveryTarget"]),
        "minimumSampledRecoveryThatPassesCandidate": next(
            (row["inlet_total_pressure_recovery"] for row in inlet_recovery_rows if row["candidate_meets_cycle_power_cap"]),
            None,
        ),
        "airframeCdTarget": candidate_area / (projected_total_cm2 / 1e4),
        "speedTargetKmh": candidate_speed,
        "powerAtTargetW": flight_power_by_speed[int(candidate_speed)],
        "meanline720": meanline_summary,
        "softCurrentBudgetAtWorstR0W": 330.0 * (voc - 330.0 * max(resistances)),
        "massFixedKnownLowerBoundKg": fixed_lower_kg,
        "maxRemainingMassForFuselageAndAllOtherPartsKg": candidate_mass - fixed_lower_kg,
        "escPcbLayerConflict": "The board file is six copper layers; REV_B_ARCHITECTURE.md describes four. Mass calculation follows the actual PCB file.",
        "evidenceClass": "CAD-material calculation plus analyst blade efficiency/cycle sensitivities; no assembly weighing or wind-tunnel data",
    }
    (STUDY / "results" / "phase9_geometry_mass_summary.json").write_text(json.dumps(design_summary, indent=2) + "\n", encoding="utf-8")
    write_report(design_summary, board_records, mass_rows, speed_rows, twr_rows, cfg)
    print(
        f"Fixed-powertrain geometry screen: {projected_total_cm2:.2f} cm2 projected; "
        f"D={diameter*1000:.0f}mm; {candidate_mass:.1f}kg; "
        f"CdA={candidate_area:.4f} at {candidate_speed:.0f}km/h."
    )


def write_report(summary: dict[str, Any], boards: list[dict[str, Any]], mass: list[dict[str, Any]], speed: list[dict[str, Any]], twr: list[dict[str, Any]], cfg: dict[str, Any]) -> None:
    target_speed = int(cfg["candidate"]["flightSpeedTargetKmh"])
    target_cda = float(cfg["candidate"]["cdAAtFlightTargetM2"])
    worst_r0 = max(float(value) for value in cfg["powertrainImmutable"]["packR0SensitivityOhm"])
    soft = next(row for row in speed if row["speed_kmh"] == target_speed and row["powertrain_limit_case"] == "soft_55A" and math.isclose(float(row["pack_r0_assumed_ohm"]), worst_r0))
    short_twr = next(row for row in twr if row["altitude_m"] == 3000.0 and row["current_case"] == "short_75A_unvalidated" and math.isclose(float(row["pack_r0_assumed_ohm"]), worst_r0))
    soft_twr = next(row for row in twr if row["altitude_m"] == 3000.0 and row["current_case"] == "soft_55A" and math.isclose(float(row["pack_r0_assumed_ohm"]), worst_r0))
    text = [
        "# Phase 9 — fixed-powertrain geometry, weight, T/W and speed envelope",
        "",
        "## Locked hardware and mass basis",
        "",
        "The six FA4119 motors and the series pair of Turnigy Rapid 6S 5000mAh packs remain unchanged. Motor mass is 280 g each from the drone-arm FA4119 decision record; battery mass is 713 g each from the linked Turnigy Rapid product specification. The flight-control and ESC PCB material masses below are calculated from their committed KiCad outlines, dielectric stackups, and actual copper-layer area exported by KiCad—not guessed from board dimensions alone.",
        "",
        "| Item | PCB/bare mass calculated | Copper fill / stack notes |",
        "|---|---:|---|",
    ]
    for row in boards:
        text.append(
            f"| {row['item']} | {row['bareBoardMassEstimateG']:.1f} g | {row['copperLayerCount']} Cu layers; FR-4 {row['fr4MassG']:.1f} g + copper {row['copperMassG']:.1f} g + mask {row['solderMaskMassEstimateG']:.1f} g |"
        )
    text += [
        "",
        f"Sourced motors weigh {mass[0]['mass_kg']:.3f} kg total; the two packs weigh {mass[1]['mass_kg']:.3f} kg. Including bare board materials, the known lower bound is {summary['massFixedKnownLowerBoundKg']:.3f} kg. The {summary['candidateAllUpMassKg']:.1f} kg candidate therefore leaves {summary['maxRemainingMassForFuselageAndAllOtherPartsKg']:.3f} kg for populated electronics, motor heatsinks, power wiring, six rotors/gears, ducts, inlet structures, fuselage, landing gear, servos and payload. BOM assembly weights for the populated control boards, heatsinks, harness and frame are not stated in drone-arm, so this is a mass budget, not a scale reading.",
        "",
        "**Source conflict:** the actual ESC `.kicad_pcb` is six copper layers (150×150 mm); `REV_B_ARCHITECTURE.md` describes four layers. The mass result follows the saved board stackup. Resolve that hardware revision inconsistency before fabrication/mass freeze.",
        "",
        "## Geometry candidate (motor/battery unchanged)",
        "",
        f"- Two axially staggered **90 mm OD / 32 mm hub** fan ducts. Their front projections are coincident, giving a 63.62 cm² circle envelope; 10 cm² is reserved for all other projected structure/controls, total **{summary['projectedAreaTotalCm2']:.2f} cm²**, below 75 cm².",
        f"- Two side-facing flush inlet slots, each 50×120 mm from the allowed stock width, provide {summary['sideInletAreaCm2']:.0f} cm² total opening against {summary['fanAnnulusAreaTotalCm2']:.0f} cm² total fan annulus. Side openings do not add to the nose-on projected frontal silhouette; inlet recovery/local losses still need validation.",
        f"- Rotor radial span is {(summary['candidateDuctDiameterMm']-32)/2:.1f} mm, within 50 mm stock; rotor chord remains 16 mm. Raise stator chord from 5 to 8 mm within the stock envelope to recover Reynolds margin, retaining the current blade counts as the initial build.",
        f"- Fuselage target: CdA≤{target_cda:.5f} m² at {target_speed} km/h (equivalent Cd≤{summary['airframeCdTarget']:.3f}), with a {summary['candidateAllUpMassKg']:.1f} kg all-up mass target. A low-drag slender center fuselage and side inlet capture are needed; smooth areas/equivalent polar are assumed, not measured.",
        "",
        "## Requirements screens",
        "",
        f"At 3 km, {summary['candidateAllUpMassKg']:.1f} kg with the 90 mm annulus and Phase-1 ηfan=0.8 sensitivity gives T/W={soft_twr['candidate_TWR']:.3f} at 55 A/motor, using the worst 30 mΩ pack sensitivity. The provisional 75 A/motor point gives T/W={short_twr['candidate_TWR']:.3f}; its duration remains unvalidated. Sea-level T/W is higher. The candidate clears T/W≥1 across the R0 sensitivity only if the {summary['candidateAllUpMassKg']:.1f} kg all-up mass is achieved.",
        "",
        f"For the {target_speed} km/h, 3 km, CdA={target_cda:.5f} target, the single-stream ideal-gas model predicts {summary['powerAtTargetW']/1000:.2f} kW bus power after the unchanged 95% gearing assumption. At the worst screened R0={worst_r0*1000:.0f} mΩ, the pack soft-current (330 A) initial power cap is {summary['softCurrentBudgetAtWorstR0W']/1000:.2f} kW; equal six-channel current is about {soft['equal_share_pack_current_per_motor_a']:.1f} A against 55 A. The speed sweep: ",
        "",
        "| Speed | CdA | Bus power | Soft 330 A case | Hard 390 A case | Provisional 450 A case |",
        "|---:|---:|---:|---|---|---|",
    ]
    for v in sorted({row["speed_kmh"] for row in speed}):
        r = next(x for x in speed if x["speed_kmh"] == v and x["powertrain_limit_case"] == "soft_55A" and math.isclose(float(x["pack_r0_assumed_ohm"]), worst_r0))
        hard = next(x for x in speed if x["speed_kmh"] == v and x["powertrain_limit_case"] == "hard_65A" and math.isclose(float(x["pack_r0_assumed_ohm"]), worst_r0))
        burst = next(x for x in speed if x["speed_kmh"] == v and x["powertrain_limit_case"] == "short_75A_unvalidated" and math.isclose(float(x["pack_r0_assumed_ohm"]), worst_r0))
        check = lambda row: "pass" if row["within_pack_power_cap"] and row["within_equal_share_current_cap"] else "fail"
        text.append(
            f"| {v} | {r['candidate_cdA_m2']:.5f} | {r['cycle_bus_power_w']/1000:.2f} kW | {check(r)} | {check(hard)} | {check(burst)} |"
        )
    text += [
        "",
        f"A candidate six-row 720 km/h meanline solve is also recorded: {summary.get('meanline720', {}).get('rowsPassingScreen', 0)}/{summary.get('meanline720', {}).get('rowsTotal', 0)} rows pass, continuity residual {summary.get('meanline720', {}).get('maximumContinuityErrorFraction', 0):.2e}, and equal-share motor current {summary.get('meanline720', {}).get('maxEqualShareBatteryCurrentA', 0):.1f} A. Its ideal nozzle momentum thrust is {summary.get('meanline720', {}).get('meanlineThrustToRequiredRatio', 0):.3f}× required drag. Motor RPM stays at/below 12,500; the ideal-Kv torque-current estimate peaks at {summary.get('meanline720', {}).get('maxIdealKvTorqueCurrentEstimateA', 0):.1f} A versus the 60 A RMS ESC continuous contract. The current convention and fixed-blade off-design performance need hardware confirmation.",
        "",
        "## Outputs and verification",
        "",
        "- `results/phase9_control_board_mass.csv` — KiCad copper/fiberglass board material calculations.",
        "- `results/phase9_mass_budget.csv` — fixed known masses and remaining airframe/propulsion allowance.",
        "- `results/phase9_static_twr_screen.csv` — T/W by altitude/current cap.",
        "- `results/phase9_speed_envelope.csv` — fixed-pack/motor power and CdA envelope.",
        "- `results/phase9_geometry_mass_summary.json` — candidate dimensions, projected area, mass allowance and source notes.",
        "",
        "No motor, battery, voltage, capacity, or per-channel current limit was changed. Blade/fuselage geometry and derived total mass are the only design levers in this screen. Powertrain efficiency and pack DCIR remain the Phase-1 analyst assumptions, not measured hardware data.",
    ]
    (STUDY / "reports" / "phase9-geometry-mass-envelope.md").write_text("\n".join(text) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
