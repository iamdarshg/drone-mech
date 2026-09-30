"""Close Phase-14 analytical and stock-nesting screens using only stdlib."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


STUDY = Path(__file__).resolve().parents[2]
PHASE = STUDY / "phase14"
CONFIG = PHASE / "configs" / "phase14_coupled_design.json"
RESULTS = PHASE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


def isa_density(altitude_m: float) -> float:
    """ISA troposphere density, sufficient for a first-order power screen."""
    temperature = 288.15 - 0.0065 * altitude_m
    pressure = 101325.0 * (temperature / 288.15) ** (9.80665 / (287.05 * 0.0065))
    return pressure / (287.05 * temperature)


def grid_capacity(
    length_mm: float,
    width_mm: float,
    blank_length_mm: float,
    blank_width_mm: float,
    edge_margin_mm: float,
    gap_mm: float,
) -> tuple[int, int, int]:
    usable_length = length_mm - 2.0 * edge_margin_mm
    usable_width = width_mm - 2.0 * edge_margin_mm
    along = math.floor((usable_length + gap_mm) / (blank_length_mm + gap_mm))
    across = math.floor((usable_width + gap_mm) / (blank_width_mm + gap_mm))
    return along, across, along * across


def stock_rows(cfg: dict) -> tuple[list[dict], dict]:
    stock = cfg["stock"]
    bar_l, bar_w, bar_t = stock["oneBarMm"]
    sheet_a_l, sheet_a_w, sheet_t = stock["sheetAmm"]
    sheet_b_l, sheet_b_w, _ = stock["sheetBmm"]
    density = stock["densityKgM3"]
    blank_l, blank_w = stock["profileBlankEnvelopeMm"]
    clearance = stock["profileBlankClearanceMm"]
    edge = stock["profileBlankEdgeMarginMm"]
    rows = []

    for name, length, width in (("sheet_A", sheet_a_l, sheet_a_w), ("sheet_B", sheet_b_l, sheet_b_w)):
        along, across, capacity = grid_capacity(length, width, blank_l, blank_w, edge, clearance)
        rows.append({
            "stock": name,
            "stock_mm": f"{length}x{width}x{sheet_t}",
            "nest": f"{along}x{across}",
            "capacity_blanks": capacity,
            "stator_vanes": 63,
            "rotor_blades": 33 if name == "sheet_A" else 39,
            "required_blanks": 96 if name == "sheet_A" else 102,
            "remaining_positions": capacity - (96 if name == "sheet_A" else 102),
            "disposition": "nominal rectangular blank-grid fit; 3D milling, tabs, retention and CAM simulation not validated",
        })

    usable_bar_l = bar_l - 2.0 * stock["barEndClampMarginMm"]
    pitch = stock["hubBlankDiameterMm"] + stock["hubBlankClearanceMm"]
    hub_count_capacity = math.floor((usable_bar_l + stock["hubBlankClearanceMm"]) / pitch)
    bar_mass = bar_l * bar_w * bar_t * 1e-9 * density
    sheet_a_mass = sheet_a_l * sheet_a_w * sheet_t * 1e-9 * density
    sheet_b_mass = stock["sheetBmm"][0] * sheet_b_w * stock["sheetBmm"][2] * 1e-9 * density
    blank_count = sum(stock["rotorBladesPerRow"]) + 2 * sum(stock["statorVanesPerDuct"])
    total_capacity = sum(row["capacity_blanks"] for row in rows)
    rows.append({
        "stock": "bar_hub_nest",
        "stock_mm": f"{bar_l}x{bar_w}x{bar_t}",
        "nest": f"six_hubs_pitch_{pitch:g}mm",
        "capacity_blanks": hub_count_capacity,
        "stator_vanes": 0,
        "rotor_blades": 0,
        "required_blanks": cfg["powertrain"]["motorCount"],
        "remaining_positions": hub_count_capacity - cfg["powertrain"]["motorCount"],
        "disposition": "six 32mm hub blanks fit in 250mm between clamp reserves; hub machining/shaft interface not released",
    })
    summary = {
        "rawStockMassKg": round(bar_mass + sheet_a_mass + sheet_b_mass, 6),
        "barMassKg": round(bar_mass, 6),
        "sheetAMassKg": round(sheet_a_mass, 6),
        "sheetBMassKg": round(sheet_b_mass, 6),
        "requiredSheetBlanks": blank_count,
        "sheetBlankCapacity": total_capacity,
        "sheetBlankMargin": total_capacity - blank_count,
        "hubCapacity": hub_count_capacity,
        "hubRequired": cfg["powertrain"]["motorCount"],
        "stockNestAnalyticalPass": total_capacity >= blank_count and hub_count_capacity >= cfg["powertrain"]["motorCount"],
    }
    return rows, summary


def envelope_rows(cfg: dict) -> tuple[list[dict], dict]:
    rho = isa_density(cfg["airframe"]["designAltitudeM"])
    cda = cfg["airframe"]["maximumCdAM2"]
    duct_count = cfg["airframe"]["ductCount"]
    bore_m = cfg["airframe"]["rotorBoreMm"] / 1000.0
    hub_m = cfg["airframe"]["hubDiameterMm"] / 1000.0
    disk_area = duct_count * math.pi / 4.0 * (bore_m**2 - hub_m**2)
    reference_speed = 720.0 / 3.6
    reference_drag = 0.5 * rho * reference_speed**2 * cda
    reference_bus_power = 12930.0
    eta_aggregate = reference_drag * reference_speed / reference_bus_power
    soft_limit = cfg["powertrain"]["escBusSoftPowerLimitW"]
    baseline_mass = 11.5
    design_mass = cfg["airframe"]["allUpMassTargetKg"]
    baseline_twr = 1.03955
    static_thrust = baseline_twr * baseline_mass * 9.80665
    ideal_disk_power_w = static_thrust**1.5 / math.sqrt(2.0 * rho * disk_area)

    def disk_power_for_thrust(speed_m_s: float, thrust_n: float) -> float:
        vi = 0.5 * (-speed_m_s + math.sqrt(speed_m_s**2 + 2.0 * thrust_n / (rho * disk_area)))
        return 2.0 * rho * disk_area * vi * (speed_m_s + vi) ** 2

    def ideal_forward_thrust(speed_m_s: float) -> float:
        """Fixed-power ideal actuator-disk upper bound, including freestream."""
        if speed_m_s <= 0.0:
            return static_thrust
        lo, hi = 0.0, 1000.0
        for _ in range(100):
            vi = (lo + hi) / 2.0
            disk_power = 2.0 * rho * disk_area * vi * (speed_m_s + vi) ** 2
            if disk_power < ideal_disk_power_w:
                lo = vi
            else:
                hi = vi
        vi = (lo + hi) / 2.0
        return 2.0 * rho * disk_area * vi * (speed_m_s + vi)

    speeds = (0, 50, 100, 150, 200, 500, 650, 700, 720)
    rows = []
    for speed_kmh in speeds:
        speed = speed_kmh / 3.6
        q = 0.5 * rho * speed**2
        drag = q * cda
        propulsive_power = drag * speed
        bus_power = propulsive_power / eta_aggregate if speed else 0.0
        forward_thrust = ideal_forward_thrust(speed)
        rows.append({
            "speed_kmh": speed_kmh,
            "density_kg_m3": round(rho, 5),
            "dynamic_pressure_pa": round(q, 2),
            "cdA_m2": cda,
            "drag_N": round(drag, 3),
            "drag_power_W": round(propulsive_power, 1),
            "estimated_bus_power_W": round(bus_power, 1),
            "soft_bus_power_margin_W": round(soft_limit - bus_power, 1),
            "ideal_available_net_thrust_N": round(forward_thrust, 3),
            "ideal_twr_at_design_mass": round(forward_thrust / (design_mass * 9.80665), 4),
            "mass_limit_for_twr_1_kg": round(forward_thrust / 9.80665, 3),
            "power_screen": "not applicable: static/low-speed map missing" if speed_kmh == 0 else (
                "analytical screen only" if bus_power <= soft_limit else "screen exceeds inherited soft cap"
            ),
            "thrust_to_weight_status": "ideal actuator-disk upper bound only; installed fan map and inlet/nozzle losses omitted" if speed_kmh <= 200 else "not a T/W qualification point",
        })

    low_speed_rows = [row for row in rows if row["speed_kmh"] <= 200]
    minimum_low_speed_twr = min(low_speed_rows, key=lambda row: row["ideal_twr_at_design_mass"])
    thrust_for_twr_one_at_200_n = design_mass * 9.80665
    ideal_disk_power_for_twr_one_at_200_w = disk_power_for_thrust(200.0 / 3.6, thrust_for_twr_one_at_200_n)
    bus_power_for_twr_one_at_200_w = ideal_disk_power_for_twr_one_at_200_w * soft_limit / ideal_disk_power_w
    summary = {
        "isaDensityAtAltitudeKgM3": round(rho, 6),
        "effectiveAnnulusDiskAreaM2": round(disk_area, 7),
        "aggregatePropulsiveEfficiencyCalibrated": round(eta_aggregate, 6),
        "calibrationBasis": "Phase-9 12.93kW bus estimate at 720km/h and CdA=0.00090m2; analyst model calibration, not a measured efficiency",
        "staticThrustDerivedFromInheritedTwrN": round(static_thrust, 3),
        "idealDiskPowerCalibratedFromStaticThrustW": round(ideal_disk_power_w, 1),
        "staticTwrAtDesignMass": round(static_thrust / (design_mass * 9.80665), 4),
        "staticTwrAt11p5kg": round(static_thrust / (baseline_mass * 9.80665), 4),
        "minimumIdealTwr0To200AtDesignMass": minimum_low_speed_twr["ideal_twr_at_design_mass"],
        "minimumTwrSpeedKmh0To200": minimum_low_speed_twr["speed_kmh"],
        "maximumIdealMassForTwr1Throughout0To200Kg": round(min(row["mass_limit_for_twr_1_kg"] for row in low_speed_rows), 3),
        "idealDiskPowerForTwr1At200AtDesignMassW": round(ideal_disk_power_for_twr_one_at_200_w, 1),
        "estimatedBusPowerForTwr1At200AtDesignMassW": round(bus_power_for_twr_one_at_200_w, 1),
        "estimatedBusPowerPerMotorForTwr1At200W": round(bus_power_for_twr_one_at_200_w / cfg["powertrain"]["motorCount"], 1),
        "powerRequirementCaveat": "same drive-efficiency scaling as inherited static screen; ideal disk only, no installed-system losses",
        "twrClaimStatus": "fixed-power ideal actuator-disk upper-bound; installed fan map, inlet/nozzle losses, and measured mass remain open",
        "powerAt650W": next(row["estimated_bus_power_W"] for row in rows if row["speed_kmh"] == 650),
        "powerAt700W": next(row["estimated_bus_power_W"] for row in rows if row["speed_kmh"] == 700),
        "powerAt720W": next(row["estimated_bus_power_W"] for row in rows if row["speed_kmh"] == 720),
        "softPowerCapW": soft_limit,
    }
    return rows, summary


def control_rows(cfg: dict) -> list[dict]:
    p = cfg["powertrain"]
    c = cfg["control"]
    return [
        {"domain": "ESC supply", "frozen_requirement": "6 independent motor channels; 12S LiPo", "numeric_limit": "50.4V maximum", "reference_disposition": "Rev-B power stage basis matches voltage; qualification open"},
        {"domain": "ESC phase current", "frozen_requirement": "continuous per motor channel", "numeric_limit": f"{p['escPhaseCurrentContinuousArms']} Arms", "reference_disposition": "Rev-B design basis states 60A; board route/thermal/bench qualification open"},
        {"domain": "ESC phase burst", "frozen_requirement": "burst per motor channel", "numeric_limit": f"{p['escPhaseCurrentBurstArms']} Arms; duration not credited until validated", "reference_disposition": "Rev-B design requires physical qualification"},
        {"domain": "Battery current", "frozen_requirement": "soft / hard / provisional short limits per motor", "numeric_limit": f"{p['batteryCurrentSoftAperMotor']}A / {p['batteryCurrentHardAperMotor']}A / {p['batteryCurrentProvisionalShortAperMotor']}A", "reference_disposition": "keep distinct from phase RMS current"},
        {"domain": "Motor speed", "frozen_requirement": "soft rollback / hard shutdown", "numeric_limit": f"{p['motorRpmSoft']}rpm / {p['motorRpmHard']}rpm = {p['motorRpmSoft']*p['polePairs']} / {p['motorRpmHard']*p['polePairs']} eRPM", "reference_disposition": "FA4119 7 pole-pair mapping; firmware and dyno proof required"},
        {"domain": "Motor thermal", "frozen_requirement": "independent winding and bell/magnet-region temperature telemetry for every channel", "numeric_limit": "windings: 100-110C rollback, 120C shutdown; bell: 70C warning, 80C shutdown", "reference_disposition": "UNMET: Rev-B cell has one local PCB NTC; external motor sensor interfaces are not specified"},
        {"domain": "ESC command path", "frozen_requirement": "six independent torque/thrust setpoints and per-channel telemetry", "numeric_limit": "CAN-FD; design target >=1kHz command/telemetry scheduling", "reference_disposition": "CAN-FD topology exists; protocol, firmware, timing and fault-injection are open"},
        {"domain": "Surface/vector actuators", "frozen_requirement": "2 elevons + 4 independently actuated exit vanes", "numeric_limit": f"6 channels; >= {c['actuatorCommandUpdateHzMinimum']}Hz updates; <= {c['commandToActuatorLatencyMsMaximum']}ms latency", "reference_disposition": "UNMET interface contract: main-board PWM pins exist, but servo power, position feedback and validated safe-state interface are unspecified"},
        {"domain": "Actuator feedback", "frozen_requirement": "each actuator position observable for jam/stale detection", "numeric_limit": f">= {c['positionFeedbackHzMinimum']}Hz; stale by {c['positionFeedbackStaleMsMaximum']}ms", "reference_disposition": "UNMET: no actuator feedback channel is identified in the main-board contract"},
        {"domain": "Control authority", "frozen_requirement": "strong 0-500km/h; medium 500-700km/h", "numeric_limit": f"strong reserve >= {c['strongMinimumReserveRatio']}x, medium reserve >= {c['mediumMinimumReserveRatio']}x", "reference_disposition": "system target frozen; proof requires identified mass/inertia, aero derivatives, efflux map and actuator dynamics"},
    ]


def matrix_rank(matrix: list[list[float]], tolerance: float = 1e-9) -> int:
    values = [row[:] for row in matrix]
    row_count = len(values)
    column_count = len(values[0]) if values else 0
    rank = 0
    for column in range(column_count):
        if rank >= row_count:
            break
        pivot = max(range(rank, row_count), key=lambda row: abs(values[row][column]))
        if abs(values[pivot][column]) <= tolerance:
            continue
        values[rank], values[pivot] = values[pivot], values[rank]
        pivot_value = values[rank][column]
        values[rank] = [value / pivot_value for value in values[rank]]
        for row in range(row_count):
            if row != rank:
                factor = values[row][column]
                values[row] = [a - factor * b for a, b in zip(values[row], values[rank], strict=True)]
        rank += 1
    return rank


def vector_vane_allocation_rank(cfg: dict) -> int:
    """Rank of idealized pitch/yaw/roll moments for four tangential vanes."""
    arm = cfg["control"]["vectorVaneAxialMomentArmM"]
    radius = cfg["control"]["vectorVaneRingRadiusM"]
    columns = []
    for theta in (math.pi / 4.0, 3.0 * math.pi / 4.0, 5.0 * math.pi / 4.0, 7.0 * math.pi / 4.0):
        # Tangential vane force creates roll through the ring radius and pitch /
        # yaw through the aft axial moment arm. Magnitudes are not modeled.
        columns.append((radius, -arm * math.cos(theta), -arm * math.sin(theta)))
    rows = [[columns[column][row] for column in range(len(columns))] for row in range(3)]
    return matrix_rank(rows)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    stocks, stock_summary = stock_rows(cfg)
    envelope, envelope_summary = envelope_rows(cfg)
    controls = control_rows(cfg)
    allocation_rank = vector_vane_allocation_rank(cfg)
    mass_growth_allowance = (
        cfg["airframe"]["allUpMassTargetKg"]
        - cfg["massBudget"]["inheritedPlannedMassIncludingPayloadKg"]
    )

    assert stock_summary["stockNestAnalyticalPass"], stock_summary
    assert envelope_summary["minimumIdealTwr0To200AtDesignMass"] >= 1.0, envelope_summary
    assert envelope_summary["powerAt650W"] < envelope_summary["softPowerCapW"]
    assert envelope_summary["powerAt700W"] < envelope_summary["softPowerCapW"]
    assert envelope_summary["powerAt720W"] < envelope_summary["softPowerCapW"]
    assert allocation_rank == 3, allocation_rank
    assert mass_growth_allowance > 0.0, mass_growth_allowance

    write_csv(RESULTS / "phase14_stock_nesting.csv", stocks)
    write_csv(RESULTS / "phase14_speed_envelope.csv", envelope)
    write_csv(RESULTS / "phase14_control_requirements.csv", controls)
    summary = {
        "phase": 14,
        "status": cfg["status"],
        "stock": stock_summary,
        "performance": envelope_summary,
        "control": {
            "actuatorCount": len(cfg["control"]["actuators"]),
            "actuators": cfg["control"]["actuators"],
            "authorityBandsKmh": cfg["control"]["controlAuthorityBandsKmh"],
            "controlMomentReserveRatios": {
                "strong": cfg["control"]["strongMinimumReserveRatio"],
                "medium": cfg["control"]["mediumMinimumReserveRatio"],
            },
            "idealizedFourVaneMomentMatrixRank": allocation_rank,
            "rankInterpretation": "geometric controllability only; aerodynamic force magnitude, vane hinge loads, and actuator dynamics are not modeled",
            "proofStatus": "not modeled; requires flight-dynamics/control-allocation/actuator model and test correlation",
        },
        "massBudget": {
            "inheritedPhase13PlannedMassIncludingPayloadKg": cfg["massBudget"]["inheritedPlannedMassIncludingPayloadKg"],
            "phase14AllUpTargetKg": cfg["airframe"]["allUpMassTargetKg"],
            "growthAllowanceForActuatorsAndMassGrowthKg": round(mass_growth_allowance, 6),
        },
        "limitations": cfg["evidencePolicy"]["doNotClaim"],
        "newCloudSpendUsd": cfg["evidencePolicy"]["cloudSpendUsd"],
    }
    (RESULTS / "phase14_closure_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
