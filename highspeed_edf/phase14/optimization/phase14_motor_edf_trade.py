"""Sensitivity trade for motor mass/power, EDF diameter, and battery capacity.

All candidates are hypothetical screening points, not vendor-qualified motors.
The model reuses Phase-14's inherited ideal actuator-disk power calibration and
720 km/h bus-power calibration. Geometry-driven shell scaling is explicitly
optimistic and is kept separate from unchanged hardware mass.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


STUDY = Path(__file__).resolve().parents[2]
PHASE = STUDY / "phase14"
CONFIG = PHASE / "configs" / "phase14_coupled_design.json"
RESULTS = PHASE / "results"


def isa_density(altitude_m: float) -> float:
    temperature = 288.15 - 0.0065 * altitude_m
    pressure = 101325.0 * (temperature / 288.15) ** (9.80665 / (287.05 * 0.0065))
    return pressure / (287.05 * temperature)


def thrust_for_disk_power(power_w: float, area_m2: float, rho: float, speed_m_s: float) -> float:
    lo, hi = 0.0, 1000.0
    for _ in range(100):
        vi = (lo + hi) / 2.0
        required = 2.0 * rho * area_m2 * vi * (speed_m_s + vi) ** 2
        if required < power_w:
            lo = vi
        else:
            hi = vi
    vi = (lo + hi) / 2.0
    return 2.0 * rho * area_m2 * vi * (speed_m_s + vi)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    rho = isa_density(cfg["airframe"]["designAltitudeM"])
    motor_count = cfg["powertrain"]["motorCount"]
    duct_count = cfg["airframe"]["ductCount"]
    hub_mm = cfg["airframe"]["hubDiameterMm"]
    base_d_mm = cfg["airframe"]["rotorOuterDiameterMm"]
    baseline_mass = cfg["massBudget"]["inheritedPlannedMassIncludingPayloadKg"]
    base_motor_mass = cfg["powertrain"]["motorMassKgEach"]
    # Phase-13 component ledger: six rotor/hub assemblies + six stator sets.
    base_rotors_kg = 0.3140296610
    base_stators_kg = 0.0536961627
    base_hub_mass_kg = 6.0 * math.pi * ((0.016**2) - (0.002**2)) * 0.016 * 2700.0
    base_blades_kg = base_rotors_kg - base_hub_mass_kg
    base_case_shell_kg = 0.1579638025
    base_inlet_shell_kg = 0.1204715005
    base_battery_mass_kg = cfg["fixedPackaging"]["batteryPackMassKgEach"] * cfg["fixedPackaging"]["batteryPackCount"]
    cost = cfg["costConstraints"]
    known_fa_price = cost["knownMotor"]["unitPriceInr"]
    known_battery_pair_price = cost["knownBattery"]["listedPairPriceInr"]
    base_bus_power_w = cfg["powertrain"]["escBusSoftPowerLimitW"]
    base_static_thrust_n = 1.03955 * 11.5 * 9.80665
    base_bore_mm = base_d_mm - 2.0
    base_area = duct_count * math.pi / 4.0 * ((base_bore_mm / 1000.0) ** 2 - (hub_mm / 1000.0) ** 2)
    base_disk_power_w = base_static_thrust_n**1.5 / math.sqrt(2.0 * rho * base_area)
    base_720_bus_w = 12930.0
    base_cda_m2 = cfg["airframe"]["maximumCdAM2"]
    eta_cal = (0.5 * rho * (720.0 / 3.6) ** 2 * base_cda_m2 * (720.0 / 3.6)) / base_720_bus_w

    motor_cases = [
        ("FA4119_geared_reference", 0.280, 2.195, 0.000, 32),
        ("35_40mm_geared_220g", 0.220, 2.000, 0.000, 32),
        ("35_40mm_geared_180g", 0.180, 1.800, 0.000, 32),
        # Direct-drive cases reserve a larger rotor hub for an inrunner can.
        # These package diameters are explicit sensitivities, not motor CAD.
        ("highspeed_inrunner_direct_220g", 0.220, 2.000, 0.720, 44),
        ("highspeed_inrunner_direct_180g", 0.180, 1.800, 0.720, 40),
        ("highspeed_inrunner_direct_150g", 0.150, 1.600, 0.720, 36),
    ]
    diameters_mm = (90, 80, 70)
    battery_cases = ((5.0, 1.426), (4.0, 1.426 * 4.0 / 5.0), (3.5, 1.426 * 3.5 / 5.0))
    rows = []

    for battery_ah, battery_mass_kg in battery_cases:
        for diameter_mm in diameters_mm:
            diameter_ratio_sq = (diameter_mm / base_d_mm) ** 2
            # Board/battery-driven fuselage mass stays fixed. Duct shell scales
            # with circumference at fixed axial length; inlet shell scales with
            # area. This avoids the unphysical whole-airframe D^2 mass scaling.
            case_saving = base_case_shell_kg * (1.0 - diameter_mm / base_d_mm)
            inlet_saving = base_inlet_shell_kg * (1.0 - diameter_ratio_sq)
            shell_saving = case_saving + inlet_saving
            cda_same = base_cda_m2
            cda_geometric = base_cda_m2 * diameter_ratio_sq
            for motor_case, motor_mass, max_input_per_motor_kw, gearbox_mass_saved_kg, required_hub_mm in motor_cases:
                rotor_tip_r_mm = diameter_mm / 2.0 - 1.4
                rotor_root_r_mm = required_hub_mm / 2.0 - 1.4
                rotor_span_mm = max(0.0, rotor_tip_r_mm - rotor_root_r_mm)
                base_rotor_span_mm = base_d_mm / 2.0 - 1.4 - (hub_mm / 2.0 - 1.4)
                stator_tip_r_mm = diameter_mm / 2.0 - 1.5
                stator_root_r_mm = required_hub_mm / 2.0 + 1.6
                stator_span_mm = max(0.0, stator_tip_r_mm - stator_root_r_mm)
                base_stator_span_mm = base_d_mm / 2.0 - 1.5 - (hub_mm / 2.0 + 1.6)
                hub_mass_kg = base_hub_mass_kg * (required_hub_mm / hub_mm) ** 2
                blade_mass_kg = base_blades_kg * rotor_span_mm / base_rotor_span_mm
                stator_mass_kg = base_stators_kg * stator_span_mm / base_stator_span_mm
                rotor_stator_saving = (
                    base_hub_mass_kg + base_blades_kg + base_stators_kg
                    - hub_mass_kg - blade_mass_kg - stator_mass_kg
                )
                bore_mm = diameter_mm - 2.0
                area = duct_count * math.pi / 4.0 * ((bore_mm / 1000.0) ** 2 - (required_hub_mm / 1000.0) ** 2)
                if area <= 0.0:
                    continue
                motor_saving = motor_count * (base_motor_mass - motor_mass)
                battery_saving = base_battery_mass_kg - battery_mass_kg
                all_up_mass = baseline_mass - motor_saving - shell_saving - rotor_stator_saving - battery_saving - gearbox_mass_saved_kg
                bus_limit_w = min(base_bus_power_w, motor_count * max_input_per_motor_kw * 1000.0)
                motor_unit_price = known_fa_price if motor_case == "FA4119_geared_reference" else cost["alternativeMotorUnitPriceInr"]
                motor_price_status = (
                    "FAIL_OVER_UNIT_CAP" if motor_unit_price is not None and motor_unit_price > cost["motorUnitPriceMaxInr"]
                    else "PASS_LISTED_PRICE" if motor_unit_price is not None
                    else "UNPRICED"
                )
                battery_pair_price = known_battery_pair_price if battery_ah == 5.0 else cost["alternativeBatteryPairPriceInr"]
                battery_price_status = (
                    "FAIL_OVER_PAIR_CAP" if battery_pair_price is not None and battery_pair_price > cost["batteryPairPriceMaxInr"]
                    else "PASS_LISTED_PRICE_SOLD_OUT" if battery_pair_price is not None
                    else "UNPRICED"
                )
                disk_power_w = base_disk_power_w * bus_limit_w / base_bus_power_w
                thrust_0 = thrust_for_disk_power(disk_power_w, area, rho, 0.0)
                thrust_100 = thrust_for_disk_power(disk_power_w, area, rho, 100.0 / 3.6)
                thrust_200 = thrust_for_disk_power(disk_power_w, area, rho, 200.0 / 3.6)
                cruise_power_650_w = 0.5 * rho * (650.0 / 3.6) ** 2 * cda_same * (650.0 / 3.6) / eta_cal
                cruise_power_720_w = 0.5 * rho * (720.0 / 3.6) ** 2 * cda_same * (720.0 / 3.6) / eta_cal
                cruise_650_geometric_w = cruise_power_650_w * diameter_ratio_sq
                cruise_720_geometric_w = cruise_power_720_w * diameter_ratio_sq
                vmax_same_cda = 720.0 * (bus_limit_w / cruise_power_720_w) ** (1.0 / 3.0)
                vmax_geometric_cda = 720.0 * (bus_limit_w / cruise_720_geometric_w) ** (1.0 / 3.0)
                tip_radius_m = (diameter_mm / 2.0 - 1.4) / 1000.0
                baseline_tip_radius_m = (base_d_mm / 2.0 - 1.4) / 1000.0
                rotor_rpm_design = 36360.0
                rotor_tip_speed = 2.0 * math.pi * rotor_rpm_design / 60.0 * tip_radius_m
                same_tip_speed_rpm = rotor_rpm_design * baseline_tip_radius_m / tip_radius_m
                direct_drive_max_e_rpm_four_pairs = same_tip_speed_rpm * 4.0
                rows.append({
                    "motor_case": motor_case,
                    "motor_mass_g_each": round(motor_mass * 1000.0, 1),
                    "motor_input_class_kW_each": max_input_per_motor_kw,
                    "motor_unit_price_inr": motor_unit_price,
                    "motor_unit_cost_gate": motor_price_status,
                    "six_motor_cost_inr_if_listed": None if motor_unit_price is None else motor_count * motor_unit_price,
                    "six_motor_cost_cap_inr": motor_count * cost["motorUnitPriceMaxInr"],
                    "gearbox_mass_saved_kg_assumed": gearbox_mass_saved_kg,
                    "fan_outer_diameter_mm": diameter_mm,
                    "hub_diameter_mm_required_for_motor_can": required_hub_mm,
                    "esc_pcb_fixed_envelope_mm": "150x150x1.6",
                    "flight_board_fixed_envelope_mm": "140x100x1.6",
                    "battery_pair_fixed_envelope_mm": "2x150x50x45 proxy",
                    "battery_Ah": battery_ah,
                    "battery_mass_kg_assumed": round(battery_mass_kg, 3),
                    "battery_pair_price_inr_if_listed": battery_pair_price,
                    "battery_pair_cost_gate": battery_price_status,
                    "battery_pair_cost_cap_inr": cost["batteryPairPriceMaxInr"],
                    "battery_C_at_330A_soft": round(330.0 / battery_ah, 1),
                    "battery_C_at_motor_power_cap_44p4V": round((bus_limit_w / 44.4) / battery_ah, 1),
                    "all_up_mass_kg_estimate": round(all_up_mass, 3),
                    "estimated_mass_saved_vs_phase13_kg": round(baseline_mass - all_up_mass, 3),
                    "annulus_area_m2": round(area, 6),
                    "annulus_area_ratio_vs_90mm": round(area / base_area, 4),
                    "single_duct_projected_disk_cm2": round(math.pi * (diameter_mm / 20.0) ** 2, 2),
                    "r3_tip_speed_m_s_at_inherited_rpm": round(rotor_tip_speed, 1),
                    "r3_rpm_to_recover_90mm_tip_speed": round(same_tip_speed_rpm, 0),
                    "motor_rpm_to_match_tip_speed_at_2p95_ratio": round(same_tip_speed_rpm / 2.95, 0),
                    "direct_drive_eRPM_at_4_pole_pairs": round(direct_drive_max_e_rpm_four_pairs, 0),
                    "direct_drive_within_200keRPM_ESC_target_at_4_pairs": direct_drive_max_e_rpm_four_pairs <= 200000.0,
                    "disk_power_upper_bound_W": round(disk_power_w, 0),
                    "TWR_0kmh_ideal": round(thrust_0 / (all_up_mass * 9.80665), 3),
                    "TWR_100kmh_ideal": round(thrust_100 / (all_up_mass * 9.80665), 3),
                    "TWR_200kmh_ideal": round(thrust_200 / (all_up_mass * 9.80665), 3),
                    "bus_power_cap_W": round(bus_limit_w, 0),
                    "required_bus_power_650_same_CdA_W": round(cruise_power_650_w, 0),
                    "required_bus_power_720_same_CdA_W": round(cruise_power_720_w, 0),
                    "cruise_650_with_same_CdA": cruise_power_650_w <= bus_limit_w,
                    "cruise_720_with_same_CdA": cruise_power_720_w <= bus_limit_w,
                    "power_limited_vmax_same_CdA_kmh": round(vmax_same_cda, 1),
                    "optimistic_vmax_if_CdA_scales_with_D2_kmh": round(vmax_geometric_cda, 1),
                    "model_note": "ideal actuator disk; shell and CdA scaling are sensitivities, not redesigned CAD or measured maps",
                })

    battery_rows = []
    for capacity_ah, mass_kg in battery_cases:
        battery_rows.append({
            "capacity_Ah": capacity_ah,
            "battery_pair_mass_kg_linear_capacity_proxy": round(mass_kg, 3),
            "mass_saved_vs_5Ah_kg": round(base_battery_mass_kg - mass_kg, 3),
            "C_rate_at_214A_650kmh_bus_current": round(214.0 / capacity_ah, 1),
            "C_rate_at_268A_200kmh_TWR_bus_current": round(268.0 / capacity_ah, 1),
            "C_rate_at_330A_soft_limit": round(330.0 / capacity_ah, 1),
            "ideal_energy_time_at_650kmh_s": round(capacity_ah * 44.4 * 3600.0 / 9513.5, 1),
            "battery_envelope_proxy": "150x50x45mm each retained; no battery package-size saving credited",
            "note": "linear mass proxy only; actual pack DCIR, continuous C rating, sag, and thermal data required",
        })

    cost_rows = [
        {
            "item": "FA4119 motor",
            "unit_price_inr_listed": known_fa_price,
            "purchase_quantity": motor_count,
            "extended_price_inr_listed": known_fa_price * motor_count,
            "applicable_cap_inr": cost["motorUnitPriceMaxInr"] if motor_count == 1 else motor_count * cost["motorUnitPriceMaxInr"],
            "cap_basis": "unit price" if motor_count == 1 else "six-motor total implied by unit cap",
            "gate": "FAIL_OVER_CAP",
            "source_or_note": cost["knownMotor"]["source"],
        },
        {
            "item": "Turnigy Rapid 6S5000 battery pair",
            "unit_price_inr_listed": cost["knownBattery"]["listedUnitPriceInr"],
            "purchase_quantity": cfg["fixedPackaging"]["batteryPackCount"],
            "extended_price_inr_listed": known_battery_pair_price,
            "applicable_cap_inr": cost["batteryPairPriceMaxInr"],
            "cap_basis": "pair total",
            "gate": "PASS_LISTED_SOLD_OUT_SHIPPING_TAX_UNSPECIFIED" if known_battery_pair_price <= cost["batteryPairPriceMaxInr"] else "FAIL_OVER_CAP",
            "source_or_note": cost["knownBattery"]["source"],
        },
        {
            "item": "alternative motor candidates",
            "unit_price_inr_listed": None,
            "purchase_quantity": motor_count,
            "extended_price_inr_listed": None,
            "applicable_cap_inr": motor_count * cost["motorUnitPriceMaxInr"],
            "cap_basis": "unit cap <= INR 4,000",
            "gate": "UNPRICED_NOT_A_COST_PASS",
            "source_or_note": "Get dated supplier quote for the selected 12S EDF motor; include required high-speed rotor/shaft hardware.",
        },
        {
            "item": "alternative battery capacity variants",
            "unit_price_inr_listed": None,
            "purchase_quantity": cfg["fixedPackaging"]["batteryPackCount"],
            "extended_price_inr_listed": None,
            "applicable_cap_inr": cost["batteryPairPriceMaxInr"],
            "cap_basis": "pair total <= INR 12,000",
            "gate": "UNPRICED_NOT_A_COST_PASS",
            "source_or_note": "4Ah/3.5Ah mass sensitivities are not priced substitute SKUs; verify actual matched 12S pair dimensions and discharge rating.",
        },
    ]

    cda_rows = []
    base_fan_area_cm2 = math.pi * (base_d_mm / 20.0) ** 2
    inlet_control_reserve_cm2 = 5.52
    cda_projection_cases = (
        ("battery_body_54cm2", 54.0, "projected union = max(fan disk, 54cm2 battery/body cross-section) + reserve"),
        ("battery_body_60cm2", 60.0, "projected union = max(fan disk, 60cm2 battery/body cross-section) + reserve"),
    )
    baseline_power_w = {650: 9513.5, 700: 11882.2, 720: 12930.0}
    for diameter_mm in (90, 85, 80, 75, 70):
        fan_area_cm2 = math.pi * (diameter_mm / 20.0) ** 2
        for case_name, body_cs_cm2, area_basis in cda_projection_cases:
            projected_cm2 = max(fan_area_cm2, body_cs_cm2) + inlet_control_reserve_cm2
            baseline_projected_cm2 = max(base_fan_area_cm2, body_cs_cm2) + inlet_control_reserve_cm2
            area_ratio = projected_cm2 / baseline_projected_cm2
            cda = base_cda_m2 * area_ratio
            cda_rows.append({
                "duct_outer_diameter_mm": diameter_mm,
                "projection_case": case_name,
                "battery_body_cross_section_cm2": round(body_cs_cm2, 3),
                "fan_disk_union_cm2": round(fan_area_cm2, 3),
                "total_projected_union_cm2": round(projected_cm2, 3),
                "area_ratio_vs_90mm_same_case": round(area_ratio, 4),
                "estimated_CdA_m2_constant_Cd": round(cda, 7),
                "bus_power_650kmh_W": round(baseline_power_w[650] * area_ratio, 0),
                "bus_power_700kmh_W": round(baseline_power_w[700] * area_ratio, 0),
                "bus_power_720kmh_W": round(baseline_power_w[720] * area_ratio, 0),
                "power_cap_vmax_10p8kW_kmh": round(720.0 * (10800.0 / (baseline_power_w[720] * area_ratio)) ** (1.0 / 3.0), 1),
                "power_cap_vmax_12kW_kmh": round(720.0 * (12000.0 / (baseline_power_w[720] * area_ratio)) ** (1.0 / 3.0), 1),
                "area_basis": area_basis,
                "motor_size_CdA_effect": "no additional reduction credited: motor silhouette is inside the coincident fan disk; boards and battery packages remain fixed",
                "evidence_limit": "constant-Cd geometric estimate only; smaller-EDF inlet/nozzle, skin-friction, and fan-map CFD/rig data absent",
            })

    reference = next(row for row in rows if row["motor_case"] == "FA4119_geared_reference" and row["fan_outer_diameter_mm"] == 90 and row["battery_Ah"] == 5.0)
    direct90 = next(row for row in rows if row["motor_case"] == "highspeed_inrunner_direct_180g" and row["fan_outer_diameter_mm"] == 90 and row["battery_Ah"] == 5.0)
    compact80 = next(row for row in rows if row["motor_case"] == "highspeed_inrunner_direct_180g" and row["fan_outer_diameter_mm"] == 80 and row["battery_Ah"] == 5.0)
    small70 = next(row for row in rows if row["motor_case"] == "highspeed_inrunner_direct_180g" and row["fan_outer_diameter_mm"] == 70 and row["battery_Ah"] == 5.0)
    assert abs(float(reference["annulus_area_m2"]) - 0.0105558) < 1e-6, reference
    assert float(direct90["TWR_200kmh_ideal"]) > 1.0, direct90
    assert float(compact80["TWR_200kmh_ideal"]) < float(direct90["TWR_200kmh_ideal"]), compact80
    assert float(small70["TWR_200kmh_ideal"]) < 1.0, small70
    cda80 = next(row for row in cda_rows if row["duct_outer_diameter_mm"] == 80 and row["projection_case"] == "battery_body_54cm2")
    assert 0.00076 < float(cda80["estimated_CdA_m2_constant_Cd"]) < 0.00079, cda80
    assert float(cda80["bus_power_720kmh_W"]) < 10800.0, cda80

    write_csv(RESULTS / "phase14_motor_edf_battery_trade.csv", rows)
    write_csv(RESULTS / "phase14_battery_trade.csv", battery_rows)
    write_csv(RESULTS / "phase14_cda_scale_trade.csv", cda_rows)
    write_csv(RESULTS / "phase14_cost_gate.csv", cost_rows)
    print(json.dumps({
        "candidateCount": len(rows),
        "batteryCandidates": len(battery_rows),
        "cdaScaleCandidates": len(cda_rows),
        "baselineMassKg": baseline_mass,
        "baselineAnnulusAreaM2": round(base_area, 6),
        "phase13PropulsionSubsystemMassKg": round(1.68 + 0.72 + 0.314029661 + 0.053696163 + 0.157963803 + 0.120471501, 3),
        "batteryPairMassKg": base_battery_mass_kg,
        "bareBoardsAndSpreadersMassKg": round(cfg["fixedPackaging"]["combinedBareBoardMassKg"] + cfg["fixedPackaging"]["populatedBoardAndConnectorsAllowanceKg"] + cfg["fixedPackaging"]["boardHeatSpreaderMassKg"], 3),
        "fixedBoardEnvelopesMm": {
            "esc": cfg["fixedPackaging"]["escPcbMm"],
            "flightControl": cfg["fixedPackaging"]["flightControlPcbMm"],
            "batteryEach": cfg["fixedPackaging"]["batteryPackMmEach"],
        },
        "edfBladePartCount": sum(cfg["stock"]["rotorBladesPerRow"]),
        "edfStatorPartCount": 2 * sum(cfg["stock"]["statorVanesPerDuct"]),
    }, indent=2))


if __name__ == "__main__":
    main()
