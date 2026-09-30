#!/usr/bin/env python3
"""Application-specific Phase-3 axial compressor meanline screening.

Calls the workbench row-matching meanline solver sequentially so each rotor can
have an independently selected RPM. This is analytical meanline only; it is not
3-D CFD, S1/S2 throughflow, a fan map, or a validated variable-bypass solution.
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


def isa(altitude_m: float, rgas: float) -> tuple[float, float, float]:
    t = 288.15 - 0.0065 * altitude_m
    p = 101325.0 * (t / 288.15) ** (9.80665 / (rgas * 0.0065))
    return t, p, p / (rgas * t)


def workbench_paths() -> Path:
    root = Path(r"D:\CodeProjects\aero-multiphysics-workbench")
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "solvers"))
    for item in (root / "packages").glob("*"):
        if item.is_dir():
            sys.path.insert(0, str(item))
    return root


def local_state_for_axial_velocity(
    *, gas: Any, pt: float, tt: float, mdot: float, area: float,
    swirl_deg: float, limit: float,
) -> tuple[float, Any]:
    """Find Vm satisfying mdot = rho(Vm,Vtheta)*Vm*A at a total state."""
    from aeroworkbench_turbomachinery.meanline import solve_triangle, state_from_total

    tan_swirl = math.tan(math.radians(swirl_deg))

    def residual(vm: float) -> tuple[float, Any]:
        vt = vm * tan_swirl
        triangle = solve_triangle(
            station_id="continuity-probe",
            blade_speed_m_s=0.0,
            axial_velocity_m_s=vm,
            tangential_velocity_m_s=vt,
        )
        state = state_from_total(
            gas=gas,
            total_temperature_k=tt,
            total_pressure_pa=pt,
            mass_flow_kg_s=mdot,
            velocity_m_s=triangle.absolute_velocity_m_s,
        )
        return state.density_kg_m3 * vm * area - mdot, state

    lo, hi = 0.1, min(25.0, limit)
    flo, _ = residual(lo)
    fhi, _ = residual(hi)
    # Increase Vm only until the rising, subsonic mass-flow branch crosses the
    # requested flow; do not bracket beyond the compressible mass-flux peak.
    while fhi < 0.0 and hi < limit:
        lo, flo = hi, fhi
        hi = min(hi * 1.25, limit)
        fhi, _ = residual(hi)
    if flo >= 0 or fhi <= 0:
        raise ValueError(f"CONTINUITY_ROOT_NOT_BRACKETED:{flo:.6g}:{fhi:.6g}")
    state = None
    for _ in range(70):
        mid = 0.5 * (lo + hi)
        fm, state = residual(mid)
        if abs(fm) < max(1e-8, mdot * 1e-8):
            return mid, state
        if fm > 0:
            hi = mid
        else:
            lo = mid
    assert state is not None
    return 0.5 * (lo + hi), state


def make_and_solve_row(
    *, gas: Any, family: str, row_id: str, rpm: float, mdot: float,
    pt_in: float, tt_in: float, swirl_in_deg: float,
    area_in: float, area_out: float,
    radius_in_m: float, radius_out_m: float,
    span_in_m: float, span_out_m: float,
    chord_m: float, blade_count: int,
    tip_clearance_m: float, target_work_j_kg: float | None,
    target_exit_swirl_deg: float | None, limits: Any,
) -> tuple[Any, Any, Any, dict[str, float]]:
    from aeroworkbench_turbomachinery.meanline import (
        MeanlineRow,
        StageDesign,
        carter_deviation_deg,
        solve_throughflow,
        solve_triangle,
        state_from_total,
    )

    rotating = family == "axial_compressor_rotor"
    r_mean = 0.5 * (radius_in_m + radius_out_m)
    span = 0.5 * (span_in_m + span_out_m)
    circumference = 2.0 * math.pi * r_mean
    solidity = blade_count * chord_m / circumference
    max_vm = 0.86 * math.sqrt(2.0 * gas.cp_j_kg_k * tt_in)
    vm_in, inlet_state = local_state_for_axial_velocity(
        gas=gas, pt=pt_in, tt=tt_in, mdot=mdot, area=area_in,
        swirl_deg=swirl_in_deg, limit=max_vm,
    )
    omega = rpm * 2.0 * math.pi / 60.0 if rotating else 0.0
    blade_speed_in = omega * radius_in_m
    blade_speed_out = omega * radius_out_m
    inlet_triangle = solve_triangle(
        station_id=f"{row_id}:in",
        blade_speed_m_s=blade_speed_in,
        axial_velocity_m_s=vm_in,
        tangential_velocity_m_s=vm_in * math.tan(math.radians(swirl_in_deg)),
    )
    incoming_frame_angle = (
        inlet_triangle.relative_angle_deg if rotating else inlet_triangle.absolute_angle_deg
    )
    vm_out = vm_in
    solved = None
    row = None
    # Iterate the axial velocity at row exit to close annulus continuity while
    # preserving the requested Euler work or stator exit swirl.
    for _ in range(60):
        if rotating:
            assert target_work_j_kg is not None
            vt_in = inlet_triangle.tangential_velocity_m_s
            vt_out = (target_work_j_kg + blade_speed_in * vt_in) / blade_speed_out
            outgoing_frame_angle = math.degrees(math.atan2(vt_out - blade_speed_out, vm_out))
        else:
            assert target_exit_swirl_deg is not None
            vt_out = vm_out * math.tan(math.radians(target_exit_swirl_deg))
            outgoing_frame_angle = math.degrees(math.atan2(vt_out, vm_out))
        camber = max(1.0, abs(outgoing_frame_angle - incoming_frame_angle))
        stagger = 0.5 * (incoming_frame_angle + outgoing_frame_angle)
        deviation = carter_deviation_deg(
            camber_deg=camber, stagger_deg=stagger, solidity=solidity
        )
        row = MeanlineRow(
            row_family=family,
            mean_radius_in_m=radius_in_m,
            mean_radius_out_m=radius_out_m,
            meridional_velocity_in_m_s=vm_in,
            meridional_velocity_out_m_s=vm_out,
            inlet_metal_angle_deg=incoming_frame_angle,
            exit_metal_angle_deg=outgoing_frame_angle - deviation.value,
            stagger_deg=stagger,
            camber_deg=camber,
            solidity=solidity,
            chord_m=chord_m,
            span_m=span,
            blade_count=blade_count,
            tip_clearance_m=tip_clearance_m,
            recovery_efficiency=0.85,
        )
        stage = StageDesign(
            gas=gas,
            inlet_total_temperature_k=tt_in,
            inlet_total_pressure_pa=pt_in,
            mass_flow_kg_s=mdot,
            rotational_speed_rpm=rpm if rotating else 0.0,
            rows=(row,),
            name=row_id,
            inlet_swirl_angle_deg=swirl_in_deg,
        )
        solved = solve_throughflow(stage, fidelity="analytical", limits=limits)
        row_result = solved.rows[0]
        vm_required = mdot / (row_result.outlet_state.density_kg_m3 * area_out)
        if abs(vm_required - vm_out) < 1e-5:
            break
        vm_out = 0.5 * (vm_out + vm_required)
    if solved is None or row is None:
        raise RuntimeError(f"ROW_SOLVE_EMPTY:{row_id}")
    row_result = solved.rows[0]
    continuity_error = (
        row_result.outlet_state.density_kg_m3
        * row_result.outlet_triangle.axial_velocity_m_s
        * area_out
        - mdot
    ) / mdot
    return row, stage, solved, {
        "continuity_error_fraction": continuity_error,
        "mean_radius_m": r_mean,
        "annulus_area_in_m2": area_in,
        "annulus_area_out_m2": area_out,
        "blade_pitch_m": circumference / blade_count,
        "solidity": solidity,
        "rotor_rpm": rpm if rotating else 0.0,
    }


def stator_contraction_sensitivity(
    *,
    gas: Any,
    total_pressure_pa: float,
    total_temperature_k: float,
    swirl_deg: float,
    mass_flow_kg_s: float,
    chord_m: float,
    viscosity_pa_s: float,
    hub_radius_m: float,
    original_area_m2: float,
    speed_kmh: int,
    candidate_core_area_m2: float | None = None,
) -> dict[str, float]:
    """Estimate stator Reynolds floor area and a fixed-core-area velocity check."""
    from aeroworkbench_turbomachinery.meanline import state_from_total

    limit_vm = 0.95 * gas.sound_speed_m_s(total_temperature_k)

    def at_vm(vm: float) -> tuple[float, Any, float]:
        vt = vm * math.tan(math.radians(swirl_deg))
        velocity = math.hypot(vm, vt)
        state = state_from_total(
            gas=gas,
            total_temperature_k=total_temperature_k,
            total_pressure_pa=total_pressure_pa,
            mass_flow_kg_s=mass_flow_kg_s,
            velocity_m_s=velocity,
        )
        reynolds = state.density_kg_m3 * velocity * chord_m / viscosity_pa_s
        return reynolds, state, velocity

    low, high = 0.1, limit_vm
    if at_vm(high)[0] < 50_000:
        raise ValueError(f"STATOR_REYNOLDS_TARGET_NOT_REACHED:{speed_kmh}")
    for _ in range(70):
        mid = 0.5 * (low + high)
        if at_vm(mid)[0] < 50_000:
            low = mid
        else:
            high = mid
    required_vm = high
    required_re, required_state, required_abs_velocity = at_vm(required_vm)
    required_area = mass_flow_kg_s / (required_state.density_kg_m3 * required_vm)
    if candidate_core_area_m2 is None:
        candidate_core_area_m2 = required_area
    current_vm, current_state = local_state_for_axial_velocity(
        gas=gas,
        pt=total_pressure_pa,
        tt=total_temperature_k,
        mdot=mass_flow_kg_s,
        area=original_area_m2,
        swirl_deg=swirl_deg,
        limit=limit_vm,
    )
    current_velocity = math.hypot(
        current_vm, current_vm * math.tan(math.radians(swirl_deg))
    )
    current_re = current_state.density_kg_m3 * current_velocity * chord_m / viscosity_pa_s
    try:
        candidate_vm, candidate_state = local_state_for_axial_velocity(
            gas=gas,
            pt=total_pressure_pa,
            tt=total_temperature_k,
            mdot=mass_flow_kg_s,
            area=candidate_core_area_m2,
            swirl_deg=swirl_deg,
            limit=limit_vm,
        )
        candidate_status = "continuity-root-found"
    except ValueError:
        return {
            "speed_kmh": float(speed_kmh),
            "stator_inlet_total_pressure_pa": total_pressure_pa,
            "stator_inlet_total_temperature_k": total_temperature_k,
            "stator_inlet_swirl_deg": swirl_deg,
            "mass_flow_per_duct_kg_s": mass_flow_kg_s,
            "current_uniform_annulus_area_m2": original_area_m2,
            "current_uniform_annulus_reynolds": current_re,
            "area_required_for_re_50000_m2": required_area,
            "required_axial_velocity_m_s": required_vm,
            "required_absolute_velocity_m_s": required_abs_velocity,
            "required_static_density_kg_m3": required_state.density_kg_m3,
            "candidate_fixed_core_area_m2": candidate_core_area_m2,
            "candidate_fixed_core_reynolds": None,
            "candidate_fixed_core_axial_velocity_m_s": None,
            "candidate_core_tip_diameter_m": 2.0 * math.sqrt(hub_radius_m * hub_radius_m + candidate_core_area_m2 / math.pi),
            "candidate_core_mean_radius_m": 0.5 * (hub_radius_m + math.sqrt(hub_radius_m * hub_radius_m + candidate_core_area_m2 / math.pi)),
            "core_area_fraction_vs_fan": candidate_core_area_m2 / original_area_m2,
            "candidate_status": "no subsonic continuity root: fixed core area is flow-capacity limited",
            "source_class": "analytical continuity/ideal-gas contraction sensitivity; no local-loss allowance",
        }
    candidate_re = candidate_state.density_kg_m3 * math.hypot(
        candidate_vm,
        candidate_vm * math.tan(math.radians(swirl_deg)),
    ) * chord_m / viscosity_pa_s
    outer_radius = math.sqrt(hub_radius_m * hub_radius_m + candidate_core_area_m2 / math.pi)
    return {
        "speed_kmh": float(speed_kmh),
        "stator_inlet_total_pressure_pa": total_pressure_pa,
        "stator_inlet_total_temperature_k": total_temperature_k,
        "stator_inlet_swirl_deg": swirl_deg,
        "mass_flow_per_duct_kg_s": mass_flow_kg_s,
        "current_uniform_annulus_area_m2": original_area_m2,
        "current_uniform_annulus_reynolds": current_re,
        "area_required_for_re_50000_m2": required_area,
        "required_axial_velocity_m_s": required_vm,
        "required_absolute_velocity_m_s": required_abs_velocity,
        "required_static_density_kg_m3": required_state.density_kg_m3,
        "candidate_fixed_core_area_m2": candidate_core_area_m2,
        "candidate_fixed_core_reynolds": candidate_re,
        "candidate_fixed_core_axial_velocity_m_s": candidate_vm,
        "candidate_status": candidate_status,
        "candidate_core_tip_diameter_m": 2.0 * outer_radius,
        "candidate_core_mean_radius_m": 0.5 * (hub_radius_m + outer_radius),
        "core_area_fraction_vs_fan": candidate_core_area_m2 / original_area_m2,
        "source_class": "analytical continuity/ideal-gas contraction sensitivity; no local-loss allowance",
    }


def main() -> None:
    import yaml

    workbench_paths()
    from aeroworkbench_turbomachinery.meanline import IdealGas, ScreeningLimits, synthesize_geometry

    study = Path(__file__).resolve().parents[1]
    cfg_path = study / "configs" / "phase3_meanline.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    req_path = study / "requirements" / "requirements_r2.yaml"
    req = yaml.safe_load(req_path.read_text(encoding="utf-8"))
    phase2_path = study / "results" / "phase2_architecture_comparison.csv"
    with phase2_path.open(newline="", encoding="utf-8") as f:
        phase2 = list(csv.DictReader(f))
    phase2_lookup = {
        (int(float(row["speed_kmh"])), float(row["cdA_m2"])): row
        for row in phase2
    }
    gas = IdealGas(cp_j_kg_k=1005.0, gamma=1.4, gas_constant_j_kg_k=287.05)
    t_amb, p_amb, rho_amb = isa(float(cfg["altitudeM"]), gas.gas_constant_j_kg_k)
    atmosphere_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    row_rows: list[dict[str, Any]] = []
    geometry_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    d = float(cfg["tipDiameterMm"]) / 1000.0
    hub_d = float(cfg["hubDiameterMm"]) / 1000.0
    r_hub, r_tip = hub_d / 2.0, d / 2.0
    mean_radius = 0.5 * (r_hub + r_tip)
    area_one = math.pi / 4.0 * (d * d - hub_d * hub_d)
    raw_limits = cfg["screeningLimits"]
    limits = ScreeningLimits(
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
    motor_hard = float(req["motor"]["initial_hard_rpm_limit"])
    gear_ratios = [float(row["gearRatio"]) for row in cfg["rotorRows"]]
    rotor_rows_cfg = cfg["rotorRows"]
    stator_by_id = {row["id"]: row for row in cfg["statorRows"]}
    n_ducts = int(req["aircraft"]["ducts"])
    eta_motor = float(req["screening_assumptions"]["motor_efficiency"])
    eta_esc = float(req["screening_assumptions"]["esc_efficiency"])
    eta_gear = float(cfg.get("gearboxEfficiency", 0.95))
    vbus_nominal = float(req["battery"]["nominal_voltage_v"])

    for speed_kmh in cfg["speedsKmh"]:
        speed = float(speed_kmh) / 3.6
        phase2 = phase2_lookup[(int(speed_kmh), float(cfg["cdAReferenceM2"]))]
        mdot_total = float(phase2["mass_flow_kg_s"])
        mdot = mdot_total / int(req["aircraft"]["ducts"])
        target_specific_work = float(phase2["compressor_shaft_power_w"]) / mdot_total
        rotor_rpm = [float(x) for x in cfg["rotorSpeedScheduleRpm"][str(speed_kmh)]]
        motor_rpm = [rpm / ratio for rpm, ratio in zip(rotor_rpm, gear_ratios, strict=True)]
        total_rotor_u2 = sum((2.0 * math.pi * mean_radius * rpm / 60.0) ** 2 for rpm in rotor_rpm)
        stage_work = [
            target_specific_work
            * (2.0 * math.pi * mean_radius * rpm / 60.0) ** 2
            / total_rotor_u2
            for rpm in rotor_rpm
        ]
        t_total_in = t_amb + speed * speed / (2.0 * gas.cp_j_kg_k)
        p_total_in = p_amb * (t_total_in / t_amb) ** (gas.gamma / (gas.gamma - 1.0))
        p_total_in *= float(cfg["inletRecovery"])
        vax, state_in = local_state_for_axial_velocity(
            gas=gas,
            pt=p_total_in,
            tt=t_total_in,
            mdot=mdot,
            area=area_one,
            swirl_deg=0.0,
            limit=0.86 * math.sqrt(2.0 * gas.cp_j_kg_k * t_total_in),
        )
        station_number = 2  # station 0 freestream, station 1 inlet/compressor face
        station_rows.append(
            station_record(
                speed_kmh, station_number, "compressor-face", p_total_in, t_total_in,
                state_in, vax, 0.0, mdot, area_one, d, hub_d,
            )
        )
        pt, tt, swirl = p_total_in, t_total_in, 0.0
        phase_rows: list[dict[str, Any]] = []
        stage_loss_p = 0.0
        for index, rotor_cfg in enumerate(rotor_rows_cfg):
            stage_meta: list[tuple[str, str, Any, Any, Any, dict[str, float]]] = []
            rrow, rstage, rresult, rmeta = make_and_solve_row(
                gas=gas,
                family="axial_compressor_rotor",
                row_id=f"{speed_kmh}-R{index+1}",
                rpm=rotor_rpm[index],
                mdot=mdot,
                pt_in=pt,
                tt_in=tt,
                swirl_in_deg=swirl,
                area_in=area_one,
                area_out=area_one,
                radius_in_m=mean_radius,
                radius_out_m=mean_radius,
                span_in_m=r_tip - r_hub,
                span_out_m=r_tip - r_hub,
                chord_m=float(rotor_cfg["chordMm"]) / 1000.0,
                blade_count=int(rotor_cfg["bladeCount"]),
                tip_clearance_m=float(cfg["tipClearanceMm"]) / 1000.0,
                target_work_j_kg=stage_work[index],
                target_exit_swirl_deg=None,
                limits=limits,
            )
            stage_meta.append((rotor_cfg["id"], "rotor", rrow, rstage, rresult, rmeta))
            rotor_result = rresult.rows[0]
            pt, tt = rotor_result.outlet_state.total_pressure_pa, rotor_result.outlet_state.total_temperature_k
            swirl = rotor_result.outlet_triangle.absolute_angle_deg
            stator_cfg = stator_by_id[rotor_cfg["statorId"]]
            srow, sstage, sresult, smeta = make_and_solve_row(
                gas=gas,
                family="axial_compressor_stator",
                row_id=f"{speed_kmh}-{stator_cfg['id']}",
                rpm=0.0,
                mdot=mdot,
                pt_in=pt,
                tt_in=tt,
                swirl_in_deg=swirl,
                area_in=area_one,
                area_out=area_one,
                radius_in_m=mean_radius,
                radius_out_m=mean_radius,
                span_in_m=r_tip - r_hub,
                span_out_m=r_tip - r_hub,
                chord_m=float(stator_cfg["chordMm"]) / 1000.0,
                blade_count=int(stator_cfg["vaneCount"]),
                tip_clearance_m=0.0,
                target_work_j_kg=None,
                target_exit_swirl_deg=float(stator_cfg["targetExitSwirlDeg"]),
                limits=limits,
            )
            stage_meta.append((stator_cfg["id"], "stator", srow, sstage, sresult, smeta))
            stator_result = sresult.rows[0]
            pt, tt = stator_result.outlet_state.total_pressure_pa, stator_result.outlet_state.total_temperature_k
            swirl = stator_result.outlet_triangle.absolute_angle_deg

            for row_id, row_kind, design_row, stage_design, result, meta in stage_meta:
                rr = result.rows[0]
                stage_loss_p += rr.total_pressure_loss_pa
                indications = {indicator.name: indicator for indicator in rr.indicators}
                row_record = {
                    "speed_kmh": speed_kmh,
                    "row_id": row_id,
                    "row_kind": row_kind,
                    "row_family": rr.row_family,
                    "rotor_rpm": meta["rotor_rpm"],
                    "motor_rpm": meta["rotor_rpm"] / gear_ratios[index] if row_kind == "rotor" else 0.0,
                    "gear_ratio": gear_ratios[index] if row_kind == "rotor" else 1.0,
                    "mean_radius_m": meta["mean_radius_m"],
                    "tip_speed_m_s": 2.0 * math.pi * meta["mean_radius_m"] * meta["rotor_rpm"] / 60.0 if row_kind == "rotor" else 0.0,
                    "blade_count": design_row.blade_count,
                    "chord_m": design_row.chord_m,
                    "solidity": meta["solidity"],
                    "incidence_deg": rr.incidence_deg,
                    "deviation_deg": rr.deviation_deg,
                    "diffusion_factor": rr.diffusion_factor,
                    "de_haller": rr.outlet_triangle.relative_velocity_m_s / rr.inlet_triangle.relative_velocity_m_s
                    if rr.inlet_triangle.relative_velocity_m_s > 0
                    else 0.0,
                    "loading_coefficient": rr.loading_coefficient,
                    "reaction": rr.reaction,
                    "absolute_mach_in": rr.inlet_triangle.absolute_velocity_m_s / gas.sound_speed_m_s(rr.inlet_state.static_temperature_k),
                    "relative_mach_in": rr.inlet_triangle.relative_velocity_m_s / gas.sound_speed_m_s(rr.inlet_state.static_temperature_k),
                    "relative_mach_out": rr.outlet_triangle.relative_velocity_m_s / gas.sound_speed_m_s(rr.outlet_state.static_temperature_k),
                    "reynolds": rr.reynolds_number,
                    "euler_work_j_kg": rr.euler_work_j_kg,
                    "stage_pressure_ratio": rr.outlet_state.total_pressure_pa / rr.inlet_state.total_pressure_pa,
                    "total_temperature_rise_k": rr.outlet_state.total_temperature_k - rr.inlet_state.total_temperature_k,
                    "stage_isen_efficiency": (
                        rr.inlet_state.total_temperature_k
                        * ((rr.outlet_state.total_pressure_pa / rr.inlet_state.total_pressure_pa) ** ((gas.gamma - 1.0) / gas.gamma) - 1.0)
                        / (rr.outlet_state.total_temperature_k - rr.inlet_state.total_temperature_k)
                        if row_kind == "rotor" and rr.outlet_state.total_temperature_k > rr.inlet_state.total_temperature_k
                        else None
                    ),
                    "aero_shaft_power_all_ducts_w": rr.euler_work_j_kg * mdot * n_ducts,
                    "motor_shaft_power_per_channel_w": (
                        rr.euler_work_j_kg * mdot / eta_gear if row_kind == "rotor" else 0.0
                    ),
                    "motor_torque_nm": (
                        (rr.euler_work_j_kg * mdot / eta_gear)
                        / ((meta["rotor_rpm"] / gear_ratios[index]) * 2.0 * math.pi / 60.0)
                        if row_kind == "rotor" and meta["rotor_rpm"] > 0
                        else 0.0
                    ),
                    "electrical_power_per_channel_w_assumed": (
                        rr.euler_work_j_kg * mdot / (eta_gear * eta_motor * eta_esc)
                        if row_kind == "rotor" else 0.0
                    ),
                    "battery_current_per_channel_a_at_nominal_bus_no_sag": (
                        rr.euler_work_j_kg * mdot / (eta_gear * eta_motor * eta_esc * vbus_nominal)
                        if row_kind == "rotor" else 0.0
                    ),
                    "total_pressure_loss_pa": rr.total_pressure_loss_pa,
                    "screened": rr.screened,
                    "validity_passed": result.validity.passed,
                    "continuity_error_fraction": meta["continuity_error_fraction"],
                    "failed_indicators": json.dumps([ind.name for ind in rr.indicators if not ind.passed]),
                    "row_indicators_json": json.dumps([ind.canonical() for ind in rr.indicators]),
                    "source_class": "workbench analytical meanline row-matching",
                }
                row_rows.append(row_record)
                # Two station records at every row face, preserving total/static state and velocity triangle.
                station_rows.append(
                    station_record(
                        speed_kmh, station_number + 1, f"{row_id}-exit",
                        rr.outlet_state.total_pressure_pa, rr.outlet_state.total_temperature_k,
                        rr.outlet_state, rr.outlet_triangle.axial_velocity_m_s,
                        rr.outlet_triangle.tangential_velocity_m_s, mdot, area_one, d, hub_d,
                        blade_speed_m_s=(2.0 * math.pi * mean_radius * rotor_rpm[index] / 60.0)
                        if row_kind == "rotor" else 0.0,
                    )
                )
                station_number += 1
                geo = synthesize_geometry(stage_design, result)
                geometry_rows.append({"speed_kmh": speed_kmh, "row_id": row_id, **geo.targets[0].canonical()})
                phase_rows.append(row_record)

        total_work = sum(float(row["euler_work_j_kg"]) for row in phase_rows)
        shaft_power = total_work * mdot * n_ducts
        motor_electrical_power = shaft_power / (eta_motor * eta_esc * eta_gear)
        failed_indicator_counts: dict[str, int] = {}
        for row in phase_rows:
            for name in json.loads(row["failed_indicators"]):
                failed_indicator_counts[name] = failed_indicator_counts.get(name, 0) + 1
        channel_currents = [
            float(row["battery_current_per_channel_a_at_nominal_bus_no_sag"])
            for row in phase_rows if row["row_kind"] == "rotor"
        ]
        meanline_pr = pt / p_total_in
        target_pr = float(phase2["overall_core_pr"])
        failed_rows = [row for row in phase_rows if not row["screened"]]
        summary_rows.append(
            {
                "speed_kmh": speed_kmh,
                "altitude_m": cfg["altitudeM"],
                "cdA_reference_m2": cfg["cdAReferenceM2"],
                "mass_flow_total_kg_s": mdot * int(req["aircraft"]["ducts"]),
                "mass_flow_per_duct_kg_s": mdot,
                "target_specific_work_j_kg": target_specific_work,
                "meanline_euler_work_j_kg": total_work,
                "phase2_target_total_pr": target_pr,
                "meanline_total_pressure_ratio": meanline_pr,
                "target_fan_pressure_ratio": float(phase2["fan_pr"]),
                "target_core_pressure_ratio": float(phase2["core_pr"]),
                "rotor_rpm_schedule": json.dumps(rotor_rpm),
                "motor_rpm_schedule": json.dumps(motor_rpm),
                "fixed_gear_ratios": json.dumps(gear_ratios),
                "shaft_power_estimate_w": shaft_power,
                "electrical_power_estimate_w": motor_electrical_power,
                "motor_channel_currents_a_at_44_4v_no_sag": json.dumps(channel_currents),
                "maximum_motor_channel_current_a_at_44_4v_no_sag": max(channel_currents),
                "motor_channels_above_provisional_75a": sum(current > 75.0 for current in channel_currents),
                "cumulated_row_total_pressure_loss_pa": stage_loss_p,
                "rows_screened": len(phase_rows) - len(failed_rows),
                "row_count": len(phase_rows),
                "all_rows_pass_screening": not failed_rows,
                "failed_indicator_counts": json.dumps(failed_indicator_counts, sort_keys=True),
                "validity": all(bool(row["validity_passed"]) for row in phase_rows),
                "source_class": "sequential workbench analytical meanline; app-specific work/RPM allocation",
            }
        )
        candidate_rows.append(
            {
                "speed_kmh": speed_kmh,
                "motor_rpm": json.dumps(motor_rpm),
                "rotor_rpm": json.dumps(rotor_rpm),
                "work_split_by_rotor": json.dumps([work / target_specific_work for work in stage_work]),
                "station_ids_last": station_number,
            }
        )

    # Follow-up geometry sensitivity: shrink the core annulus after R1 enough
    # that the 5 mm S1 vane reaches the solver's declared Re >= 50k floor at
    # the worst (lowest-speed, lowest-throughflow) point. This is a sizing bound,
    # not yet a complete contracted-geometry row solve.
    s1_chord_m = float(stator_by_id["S1"]["chordMm"]) / 1000.0
    s1_exit_stations = {
        int(row["speed_kmh"]): row
        for row in station_rows
        if row["station_label"].endswith("R1-exit")
    }
    contraction_at_each_speed: list[dict[str, Any]] = []
    for speed_kmh in cfg["speedsKmh"]:
        station = s1_exit_stations[int(speed_kmh)]
        contraction_at_each_speed.append(
            stator_contraction_sensitivity(
                gas=gas,
                total_pressure_pa=float(station["Pt_Pa"]),
                total_temperature_k=float(station["Tt_K"]),
                swirl_deg=float(station["swirl_angle_deg"]),
                mass_flow_kg_s=float(station["mass_flow_kg_s_per_duct"]),
                chord_m=s1_chord_m,
                viscosity_pa_s=1.8e-5,
                hub_radius_m=r_hub,
                original_area_m2=area_one,
                speed_kmh=int(speed_kmh),
            )
        )
    core_area_candidate = min(row["area_required_for_re_50000_m2"] for row in contraction_at_each_speed)
    fixed_core_sensitivity: list[dict[str, Any]] = []
    core_outer_radius = math.sqrt(r_hub * r_hub + core_area_candidate / math.pi)
    core_mean_radius = 0.5 * (r_hub + core_outer_radius)
    for speed_kmh in cfg["speedsKmh"]:
        station = s1_exit_stations[int(speed_kmh)]
        record = stator_contraction_sensitivity(
            gas=gas,
            total_pressure_pa=float(station["Pt_Pa"]),
            total_temperature_k=float(station["Tt_K"]),
            swirl_deg=float(station["swirl_angle_deg"]),
            mass_flow_kg_s=float(station["mass_flow_kg_s_per_duct"]),
            chord_m=s1_chord_m,
            viscosity_pa_s=1.8e-5,
            hub_radius_m=r_hub,
            original_area_m2=area_one,
            speed_kmh=int(speed_kmh),
            candidate_core_area_m2=core_area_candidate,
        )
        rpm_original = [float(x) for x in cfg["rotorSpeedScheduleRpm"][str(speed_kmh)]]
        required_core_rpms = [
            rpm_original[j] * mean_radius / core_mean_radius for j in (1, 2)
        ]
        record.update(
            {
                "core_area_candidate_sized_at_worst_speed_m2": core_area_candidate,
                "core_tip_diameter_candidate_m": 2.0 * core_outer_radius,
                "core_mean_radius_candidate_m": core_mean_radius,
                "R2_R3_rpm_to_preserve_U": json.dumps(required_core_rpms),
                "R2_R3_required_fixed_ratio_at_motor_hard_rpm": json.dumps(
                    [rpm / motor_hard for rpm in required_core_rpms]
                ),
            }
        )
        fixed_core_sensitivity.append(record)

    results = study / "results"
    write_csv(results / "phase3_meanline_rows.csv", row_rows)
    write_csv(results / "phase3_station_audit.csv", station_rows)
    write_csv(results / "phase3_geometry_targets.csv", geometry_rows)
    write_csv(results / "phase3_operating_summary.csv", summary_rows)
    write_csv(results / "phase3_schedule.csv", candidate_rows)
    write_csv(results / "phase3_core_area_schedule_sensitivity.csv", contraction_at_each_speed)
    write_csv(results / "phase3_core_contraction_sensitivity.csv", fixed_core_sensitivity)
    req_path = study / "requirements" / "requirements_r2.yaml"
    summary_json = {
        "phase": 3,
        "sourceClass": "analytical meanline; workbench library; no CFD/native solver",
        "referenceProjectFrontalAreaMaxCm2": 75,
        "frontalAreaCdASeparated": True,
        "altitudeM": cfg["altitudeM"],
        "rpmAndGearSchedule": candidate_rows,
        "operatingSummary": summary_rows,
        "statorCoreAreaScheduleSensitivity": contraction_at_each_speed,
        "fixedCoreAreaFlowCapacitySensitivity": fixed_core_sensitivity,
        "allMeanlineRowsPassScreening": all(r["all_rows_pass_screening"] for r in summary_rows),
        "requirementsSha256": hashlib.sha256(req_path.read_bytes()).hexdigest(),
        "configSha256": hashlib.sha256(cfg_path.read_bytes()).hexdigest(),
        "knownLimitations": [
            "One-dimensional row-matching meanline; not S1/S2 streamline throughflow.",
            "Each rotor-stator pair is solved sequentially to support independent rotor RPMs.",
            "Fixed hub and casing radii used; meridional continuity is closed by solved axial velocity.",
            "Equal target loading based on U squared; variable reaction/spanwise twist not optimized.",
            "No bypass split included in this baseline meanline chain; Phase 2 showed beta=0 at 600-700 km/h in its simplified model.",
            "Motor, gearbox, battery and thermal models are coupling estimates, not hardware maps.",
        ],
        "gcpJobs": [],
        "nativeSolvers": [],
    }
    (results / "phase3_meanline_summary.json").write_text(json.dumps(summary_json, indent=2) + "\n", encoding="utf-8")
    write_report(study, summary_rows, row_rows, contraction_at_each_speed, fixed_core_sensitivity)
    print(f"Phase 3 meanline screening complete: {len(row_rows)} rows across {len(summary_rows)} flight points")


def station_record(
    speed_kmh: int,
    station: int,
    label: str,
    pt: float,
    tt: float,
    state: Any,
    vm: float,
    vt: float,
    mdot: float,
    area: float,
    diameter: float,
    hub_diameter: float,
    blade_speed_m_s: float = 0.0,
) -> dict[str, Any]:
    velocity = math.hypot(vm, vt)
    relative_velocity = math.hypot(vm, vt - blade_speed_m_s)
    mach = velocity / math.sqrt(1.4 * 287.05 * state.static_temperature_k)
    swirl = math.degrees(math.atan2(vt, vm))
    return {
        "speed_kmh": speed_kmh,
        "station": station,
        "station_label": label,
        "Pt_Pa": pt,
        "Ps_Pa": state.static_pressure_pa,
        "Tt_K": tt,
        "Ts_K": state.static_temperature_k,
        "Mach": mach,
        "V_absolute_m_s": velocity,
        "Vm_m_s": vm,
        "Vtheta_m_s": vt,
        "W_relative_m_s": relative_velocity,
        "density_kg_m3": state.density_kg_m3,
        "mass_flow_kg_s_per_duct": mdot,
        "annulus_area_m2": area,
        "hub_diameter_m": hub_diameter,
        "tip_diameter_m": diameter,
        "swirl_angle_deg": swirl,
        "source_class": "workbench analytical meanline station state",
    }


def write_report(
    study: Path,
    summaries: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    core_area_schedule: list[dict[str, Any]],
    core_sensitivity: list[dict[str, Any]],
) -> None:
    text = [
        "# Phase 3 meanline screening",
        "",
        "**Evidence class:** workbench analytical meanline row matching. No native solver, CFD, GCP job, or physical measurement was used.",
        "",
        "The 75 cm² projected-frontal-area checkpoint is recorded in requirements revision 2 and kept separate from CdA. The aerodynamic operation points below use CdA=0.00315 m² as a separate Phase 2 reference input.",
        "",
        "## Three-rotor serial axial candidate, 3 km ISA",
        "",
        "| Speed | Target work (kJ/kg) | Meanline work (kJ/kg) | Target PR | Meanline PR | Rotor RPM R1/R2/R3 | Rows passing custom screening | Max motor current at 44.4 V, no sag | Electrical estimate with assumed 95% gear (kW) |",
        "|---:|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for summary in summaries:
        rows_ok = f"{summary['rows_screened']}/{summary['row_count']}"
        rpms = "/".join(str(int(x)) for x in json.loads(summary["rotor_rpm_schedule"]))
        text.append(
            f"| {summary['speed_kmh']} | {summary['target_specific_work_j_kg']/1000:.2f} | {summary['meanline_euler_work_j_kg']/1000:.2f} | {summary['phase2_target_total_pr']:.4f} | {summary['meanline_total_pressure_ratio']:.4f} | {rpms} | {rows_ok} | {summary['maximum_motor_channel_current_a_at_44_4v_no_sag']:.1f} A | {summary['electrical_power_estimate_w']/1000:.2f} |"
        )
    failed = [row for row in rows if not row["screened"] or not row["validity_passed"]]
    text += [
        "",
        f"There are {len(failed)} row records failing at least one declared screening indicator or correlation-validity gate; in this candidate all 15 failures are stator Reynolds numbers below the declared 50,000 floor (range about 31,000–44,000). Rotor diffusion, incidence, relative-Mach and loading screens pass at the updated RPM schedule. See `phase3_meanline_rows.csv` for per-row detail. A screen failure is a rejection warning, not proof of physical failure; a pass is not validation.",
        "",
        "The motor-current column divides each rotor's calculated electrical load by 44.4 V and assumes no pack sag. Compare it to the 55 A soft / 65 A initial hard / 75 A provisional per-motor limits; actual loaded current will be higher as voltage sags. The provisional 75 A limit has no established run duration.",
        "",
        "At 600 km/h the highest stage current estimate already exceeds the 65 A initial hard limit; at 650/700 km/h the highest channels exceed the provisional 75 A limit even before battery sag. 700 km/h also asks about 22.1 kW bus input in this candidate, over the current 20.66 kW best-case provisional pack/current screen.",
        "",
        "## Station continuity and total-pressure tracking",
        "",
        "`phase3_station_audit.csv` records compressor-face plus each rotor/stator exit with Pt, Ps, Tt, Ts, Mach, V, density, mdot, annulus area, and swirl. The candidate holds 32 mm hub / 80 mm casing, solving the required axial velocity from continuity at each face.",
        "",
        "## Stator Reynolds / variable core-annulus sensitivity",
        "",
        "The uniform 80 mm annulus puts all stators below the workbench's 50k Reynolds screening floor. A lossless continuity sensitivity sizes a smaller core annulus at each speed to bring the 5 mm S1 stator to Re≈50k:",
        "",
        "| Speed | Uniform S1 Re | Core area for Re≈50k (m²/duct) | Equivalent core outer diameter, 32 mm hub | Core area / fan annulus |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in core_area_schedule:
        text.append(
            f"| {row['speed_kmh']:.0f} km/h | {row['current_uniform_annulus_reynolds']:.0f} | {row['area_required_for_re_50000_m2']:.6f} | {row['candidate_core_tip_diameter_m']*1000:.1f} mm | {row['core_area_fraction_vs_fan']:.3f} |"
        )
    text += [
        "",
        "A fixed annulus at the 500 km/h minimum area (0.00263 m²) has no subsonic continuity solution at 550–700 km/h for the captured mass flow. The first architecture-sensitive path to investigate is therefore a mechanically scheduled core annulus/splitter area that opens with speed (about 0.00263→0.00367 m² per duct from 500→700 in this idealized estimate), corresponding to roughly 66.1→75.5 mm outer core diameter with the current 32 mm hub, while preserving the 80 mm fan envelope. This is a sizing target, not a validated passive mechanism. Core-radius contraction also raises the required R2/R3 RPM/gear ratios; the per-speed schedule and fixed-area flow-capacity sensitivity are saved in `phase3_core_area_schedule_sensitivity.csv` and `phase3_core_contraction_sensitivity.csv`.",
    ]
    text += [
        "",
        "## Design interpretation",
        "",
        "- The work split is assigned proportional to each rotor's U² to target approximately equal loading coefficient, with R1 slower and the rear rotors faster.",
        "- Stage 3 (S3) targets zero exit swirl; S1/S2 are also initially deswirled as a conservative first baseline. Their residual-swirl schedule remains an optimization variable.",
        "- Each motor is independently scheduled through its fixed stage gearbox. The fixed 95% gear efficiency is assumed, not measured.",
        "- The current meanline baseline is one common stream through three rotors and three stators. Core-annulus contraction is a sensitivity only; it has not yet been re-solved through all six rows. Bypass remains unmatched in this meanline chain.",
        "- Rotor chords are 16/15/14 mm and stator chords are 5 mm, within revision-2 geometric limits. Blade counts are 13/12/11 rotors and 23/21/19 stators.",
        "",
        "## Phase 3 gate",
        "",
        "Do not accept the candidate unless its rows meet user screening targets (especially Reynolds validity, diffusion, de Haller, relative Mach, incidence, and loading) across the speed range, and electrical channels remain within current limits. The workbench solver is meanline row matching, not S1/S2 or CFD; spanwise twist/radial equilibrium and true annulus blockage are absent. Next iteration should implement the speed-dependent core annulus profile in the application model, re-solve all rows, and co-optimize rotor work/RPM and gear ratios while preserving the 75 cm² projected-area checkpoint.",
    ]
    target = study / "reports" / "phase3-meanline.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(text) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
