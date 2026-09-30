"""Phase-14 multivariable screening trade.

Sweeps fan diameter, hub/motor package, motor power/mass/price class, battery
capacity, variable-bypass benefit, auxiliary-inlet benefit, and fan figure of
merit against the 1.0 TWR ceiling speed of 180 km/h and the 650-720 km/h cruise
targets.

Physics and calibration
-----------------------
Forward-thrust uses the same ideal actuator-disk relation as Phase 14:
    mdot = rho*A*(V0+vi)
    T    = 2*rho*A*vi*(V0+vi)
    P    = 2*rho*A*vi*(V0+vi)^2
The reference bus power (13.17 kW) maps to the reference ideal-disk power
(9162.7 W) that reproduces the inherited 117.24 N static / 11.5 kg TWR=1.03955
screen. Other candidates scale ideal-disk power with their bus-power cap.

Low-speed multipliers
---------------------
* Variable bypass: Phase-2 reduced-order sweep found beta=0.5 best at 100 km/h
  (0.66 kW vs 0.99 kW serial for equal thrust) and beta=0 at >=200 km/h. At
  equal power that is about (0.99/0.66)^(2/3)=1.30x thrust. Modeled as 1.30x
  up to 100 km/h tapering linearly to 1.00x at 200 km/h.
* Auxiliary inlets: an explicit, unverified sensitivity, 0/10/20% extra
  low-speed thrust, tapering to zero at 200 km/h. No credit is taken above
  200 km/h, so there is no high-speed CdA penalty in this screen.
* Fan figure of merit: ideal-disk thrust is an upper bound; a realistic
  installed fan is screened at FOM 0.72 (and ideal 1.00 reported separately).

Everything here is a screening estimate. No measured motor, fan, inlet,
nozzle, battery, or CFD data exists behind these numbers.
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
RESULTS.mkdir(parents=True, exist_ok=True)

G = 9.80665
BASE_BUS_POWER_W = 13170.0
BASE_DISK_POWER_W = 9162.7
BASE_MASS_KG = 8.1487740311
BASE_D_M = 0.090
BASE_HUB_M = 0.032
BASE_CDA_M2 = 0.0009
BASE_FAN_AREA_CM2 = math.pi * (BASE_D_M * 100.0 / 2.0) ** 2
# Corrected frontal-area model (user correction): the external silhouette is
# battery/body dominated, NOT board dominated. The 150x150 ESC and 140x100
# flight boards set the minimum INTERNAL bay volume, not the frontal area.
# Two 136x44x64 mm packs side by side are about 88x64 mm; with rounding a
# ~54 cm^2 body cross-section is retained. Projected area is the UNION of the
# fan disk and the body cross-section, plus an inlet/control reserve calibrated
# so the 90 mm reference reproduces the Phase-13 69.14 cm^2 union.
BODY_CROSS_SECTION_CASES_CM2 = ((54.0, "battery_body_54cm2"), (60.0, "battery_body_60cm2"))
INLET_CONTROL_RESERVE_CM2 = 5.52
REFERENCE_CRUISE_POWER_W = {650: 9513.5, 700: 11882.2, 720: 12930.0}
R3_DESIGN_RPM_90MM = 36360.0
BASE_TIP_RADIUS_M = (BASE_D_M / 2.0) - 0.0014

FANS_MM = (90, 85, 80, 75, 70)
# name, motor mass kg, continuous bus input W per motor, hub mm, gearbox mass saved kg, unit price INR
MOTOR_CASES = (
    ("FA4119_geared", 0.280, 2195.0, 32, 0.0, 4500, "Flycci FA4119 KV350; priced, over INR 4000 cap"),
    ("220g_geared", 0.220, 2000.0, 32, 0.0, None, "hypothetical 2.0 kW/channel geared class; unpriced"),
    ("180g_geared", 0.180, 1800.0, 32, 0.0, None, "hypothetical 1.8 kW/channel geared class; unpriced"),
    ("220g_direct", 0.220, 2000.0, 44, 0.72, None, "hypothetical 2.0 kW/channel direct-drive class; unpriced"),
    ("180g_direct", 0.180, 1800.0, 40, 0.72, None, "hypothetical 1.8 kW/channel direct-drive class; unpriced"),
    ("150g_direct", 0.150, 1600.0, 36, 0.72, None, "hypothetical 1.6 kW/channel direct-drive class; unpriced"),
)
# Ah, pair mass kg, pair price INR (None = unpriced sensitivity)
BATTERY_CASES = ((5.0, 1.426, 10800), (4.0, 1.141, None), (3.5, 0.998, None))
AUX_CASES = ((0.0, "closed_flush"), (0.10, "modest_aux_inlet"), (0.20, "generous_aux_inlet"))
FOMS = ((1.00, "ideal_upper_bound"), (0.72, "installed_realistic_screen"))


def isa(altitude_m: float) -> tuple[float, float]:
    """Return (density kg/m^3, speed of sound m/s) for the ISA troposphere."""
    temperature = 288.15 - 0.0065 * altitude_m
    pressure = 101325.0 * (temperature / 288.15) ** (9.80665 / (287.05 * 0.0065))
    rho = pressure / (287.05 * temperature)
    sound = math.sqrt(1.4 * 287.05 * temperature)
    return rho, sound


def disk_vi(power_w: float, rho: float, area_m2: float, speed_m_s: float) -> float:
    if power_w <= 0.0 or area_m2 <= 0.0:
        return 0.0
    lo, hi = 0.0, 2000.0
    for _ in range(120):
        vi = (lo + hi) / 2.0
        required = 2.0 * rho * area_m2 * vi * (speed_m_s + vi) ** 2
        if required < power_w:
            lo = vi
        else:
            hi = vi
    return (lo + hi) / 2.0


def disk_thrust(power_w: float, rho: float, area_m2: float, speed_m_s: float) -> float:
    vi = disk_vi(power_w, rho, area_m2, speed_m_s)
    return 2.0 * rho * area_m2 * vi * (speed_m_s + vi)


def vbr_multiplier(speed_kmh: float) -> float:
    if speed_kmh <= 100.0:
        return 1.30
    if speed_kmh >= 200.0:
        return 1.00
    return 1.30 - 0.30 * (speed_kmh - 100.0) / 100.0


def aux_multiplier(speed_kmh: float, aux_fraction: float) -> float:
    if speed_kmh >= 200.0:
        return 1.0
    if speed_kmh <= 180.0:
        return 1.0 + aux_fraction
    return 1.0 + aux_fraction * (200.0 - speed_kmh) / 20.0


def low_speed_multiplier(speed_kmh: float, aux_fraction: float) -> float:
    """Additive excess so the two gains are not silently compounded."""
    return 1.0 + (vbr_multiplier(speed_kmh) - 1.0) + (aux_multiplier(speed_kmh, aux_fraction) - 1.0)


def projected_area_cm2(diameter_mm: float, body_cross_section_cm2: float) -> float:
    """Union of the coincident fan disk and the battery/body cross-section.

    Below roughly an 80 mm fan the body cross-section dominates and projected
    area (so CdA) stops falling with fan diameter.
    """
    fan_disk_cm2 = math.pi * (diameter_mm / 20.0) ** 2
    return max(fan_disk_cm2, body_cross_section_cm2) + INLET_CONTROL_RESERVE_CM2


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cost = cfg["costConstraints"]
    duct_count = cfg["airframe"]["ductCount"]
    motor_count = cfg["powertrain"]["motorCount"]
    battery_count = cfg["fixedPackaging"]["batteryPackCount"]
    base_hub_mass_kg = motor_count * math.pi * ((0.016**2) - (0.002**2)) * 0.016 * 2700.0
    base_rotor_kg = 0.3140296610
    base_stator_kg = 0.0536961627
    base_blades_kg = base_rotor_kg - base_hub_mass_kg
    base_case_shell_kg = 0.1579638025
    base_inlet_shell_kg = 0.1204715005
    base_rotor_span_mm = BASE_D_M * 1000.0 / 2.0 - 1.4 - (cfg["airframe"]["hubDiameterMm"] / 2.0 - 1.4)
    base_stator_span_mm = BASE_D_M * 1000.0 / 2.0 - 1.5 - (cfg["airframe"]["hubDiameterMm"] / 2.0 + 1.6)
    aux_door_mass_kg = 0.05
    trajectory_speeds_kmh = (0, 90, 180)
    rho_sl, sound_sl = isa(0.0)
    rho_3k, sound_3k = isa(3000.0)

    rows = []
    for fan_mm in FANS_MM:
        bore_mm = fan_mm - 2.0
        fan_area_cm2 = math.pi * (fan_mm / 20.0) ** 2
        for body_cs_cm2, area_case in BODY_CROSS_SECTION_CASES_CM2:
            cda = BASE_CDA_M2 * projected_area_cm2(fan_mm, body_cs_cm2) / projected_area_cm2(BASE_D_M * 1000.0, body_cs_cm2)
            for motor_name, motor_mass, motor_power_w, hub_mm, gearbox_saved_kg, motor_price, motor_note in MOTOR_CASES:
                area_m2 = duct_count * math.pi / 4.0 * ((bore_mm / 1000.0) ** 2 - (hub_mm / 1000.0) ** 2)
                if area_m2 <= 0.0:
                    continue
                rotor_tip_r = fan_mm / 2.0 - 1.4
                rotor_root_r = hub_mm / 2.0 - 1.4
                stator_tip_r = fan_mm / 2.0 - 1.5
                stator_root_r = hub_mm / 2.0 + 1.6
                hub_mass_kg = base_hub_mass_kg * (hub_mm / cfg["airframe"]["hubDiameterMm"]) ** 2
                blade_mass_kg = base_blades_kg * max(0.0, rotor_tip_r - rotor_root_r) / base_rotor_span_mm
                stator_mass_kg = base_stator_kg * max(0.0, stator_tip_r - stator_root_r) / base_stator_span_mm
                case_saving = base_case_shell_kg * (1.0 - fan_mm / (BASE_D_M * 1000.0))
                inlet_saving = base_inlet_shell_kg * (1.0 - (fan_mm / (BASE_D_M * 1000.0)) ** 2)
                rotor_stator_mass_kg = hub_mass_kg + blade_mass_kg + stator_mass_kg
                base_rotor_stator_mass_kg = base_rotor_kg + base_stator_kg
                bus_limit_w = min(BASE_BUS_POWER_W, motor_count * motor_power_w)
                ideal_disk_power_w = BASE_DISK_POWER_W * bus_limit_w / BASE_BUS_POWER_W
                # Tip speed / RPM to preserve the reference R3 tip speed.
                rpm_same_tip = R3_DESIGN_RPM_90MM * BASE_TIP_RADIUS_M / (rotor_tip_r / 1000.0)
                tip_speed_m_s = 2.0 * math.pi * rpm_same_tip / 60.0 * (rotor_tip_r / 1000.0)
                tip_mach = tip_speed_m_s / sound_3k
                for battery_ah, battery_mass_kg, battery_price in BATTERY_CASES:
                    for aux_fraction, aux_label in AUX_CASES:
                        for fom, fom_label in FOMS:
                            mass_kg = (
                                BASE_MASS_KG
                                - motor_count * (cfg["powertrain"]["motorMassKgEach"] - motor_mass)
                                - gearbox_saved_kg
                                - case_saving
                                - inlet_saving
                                - (base_rotor_stator_mass_kg - rotor_stator_mass_kg)
                                - (cfg["fixedPackaging"]["batteryPackMassKgEach"] * battery_count - battery_mass_kg)
                                + (aux_door_mass_kg if aux_fraction > 0.0 else 0.0)
                            )
                            # Low-speed TWR at sea level (takeoff/low-speed) and 3 km.
                            twr = {}
                            for speed_kmh in trajectory_speeds_kmh:
                                mult = low_speed_multiplier(speed_kmh, aux_fraction) * fom
                                v_sl = speed_kmh / 3.6
                                v_3k = speed_kmh / 3.6
                                twr[(speed_kmh, "sea_level")] = disk_thrust(ideal_disk_power_w, rho_sl, area_m2, v_sl) * mult / (mass_kg * G)
                                twr[(speed_kmh, "3000m")] = disk_thrust(ideal_disk_power_w, rho_3k, area_m2, v_3k) * mult / (mass_kg * G)
                            # Required bus power for TWR=1 at 180 km/h, sea level.
                            required_thrust_n = mass_kg * G / (low_speed_multiplier(180.0, aux_fraction) * fom)
                            vi_req = 0.5 * (-(180.0 / 3.6) + math.sqrt((180.0 / 3.6) ** 2 + 2.0 * required_thrust_n / (rho_sl * area_m2)))
                            disk_power_req = 2.0 * rho_sl * area_m2 * vi_req * ((180.0 / 3.6) + vi_req) ** 2
                            bus_power_req_180 = disk_power_req * BASE_BUS_POWER_W / BASE_DISK_POWER_W
                            cruise = {s: REFERENCE_CRUISE_POWER_W[s] * cda / BASE_CDA_M2 for s in REFERENCE_CRUISE_POWER_W}
                            vmax = 720.0 * (bus_limit_w / cruise[720]) ** (1.0 / 3.0)
                            motor_price_status = (
                                "FAIL_OVER_UNIT_CAP" if motor_price is not None and motor_price > cost["motorUnitPriceMaxInr"]
                                else "PASS_LISTED_PRICE" if motor_price is not None
                                else "UNPRICED"
                            )
                            battery_price_status = (
                                "FAIL_OVER_PAIR_CAP" if battery_price is not None and battery_price > cost["batteryPairPriceMaxInr"]
                                else "PASS_LISTED_SOLD_OUT" if battery_price is not None
                                else "UNPRICED"
                            )
                            rows.append({
                                "fan_outer_diameter_mm": fan_mm,
                                "hub_diameter_mm": hub_mm,
                                "projection_case": area_case,
                                "motor_class": motor_name,
                                "motor_mass_g": round(motor_mass * 1000.0, 1),
                                "motor_bus_input_kW_each": round(motor_power_w / 1000.0, 3),
                                "motor_unit_price_inr": motor_price,
                                "motor_cost_gate": motor_price_status,
                                "six_motor_cost_inr": None if motor_price is None else motor_count * motor_price,
                                "six_motor_cost_cap_inr": motor_count * cost["motorUnitPriceMaxInr"],
                                "battery_Ah": battery_ah,
                                "battery_pair_price_inr": battery_price,
                                "battery_cost_gate": battery_price_status,
                                "aux_inlet_case": aux_label,
                                "aux_fraction": aux_fraction,
                                "fan_figure_of_merit": fom,
                                "fom_case": fom_label,
                                "estimated_CdA_m2": round(cda, 7),
                                "annulus_area_m2": round(area_m2, 6),
                                "estimated_all_up_mass_kg": round(mass_kg, 3),
                                "bus_power_cap_W": round(bus_limit_w, 0),
                                "required_bus_power_TWR1_180kmh_W": round(bus_power_req_180, 0),
                                "bus_power_surplus_for_TWR1_180kmh_W": round(bus_limit_w - bus_power_req_180, 0),
                                "TWR_0_sea_level": round(twr[(0, "sea_level")], 3),
                                "TWR_90_sea_level": round(twr[(90, "sea_level")], 3),
                                "TWR_180_sea_level": round(twr[(180, "sea_level")], 3),
                                "TWR_180_3000m": round(twr[(180, "3000m")], 3),
                                "low_speed_TWR_gate_sea_level": "PASS" if min(twr[(s, "sea_level")] for s in trajectory_speeds_kmh) >= cfg["airframe"]["lowSpeedTwrMinimum"] else "FAIL",
                                "cruise_power_650kmh_W": round(cruise[650], 0),
                                "cruise_power_700kmh_W": round(cruise[700], 0),
                                "cruise_power_720kmh_W": round(cruise[720], 0),
                                "cruise_650_affordable": cruise[650] <= bus_limit_w,
                                "cruise_700_affordable": cruise[700] <= bus_limit_w,
                                "cruise_720_affordable": cruise[720] <= bus_limit_w,
                                "power_limited_vmax_kmh": round(vmax, 1),
                                "r3_rpm_to_preserve_reference_tip_speed": round(rpm_same_tip, 0),
                                "r3_tip_speed_m_s": round(tip_speed_m_s, 1),
                                "r3_tip_mach_at_3000m": round(tip_mach, 3),
                                "direct_drive_eRPM_at_4_pole_pairs": round(rpm_same_tip * 4.0, 0),
                                "within_200k_eRPM_esc_target_at_4_pairs": rpm_same_tip * 4.0 <= 200000.0,
                                "motor_note": motor_note,
                            })

    def cost_pass(row: dict) -> bool:
        return row["motor_cost_gate"] == "PASS_LISTED_PRICE" and row["battery_cost_gate"] == "PASS_LISTED_SOLD_OUT"
    affordable_low_speed_power = [
        r for r in rows
        if r["low_speed_TWR_gate_sea_level"] == "PASS"
        and r["cruise_720_affordable"]
        and r["fan_figure_of_merit"] == 0.72
        and r["aux_fraction"] == 0.0
    ]
    priced_low_speed_power = [r for r in affordable_low_speed_power if cost_pass(r)]
    best_by_mass = min(rows, key=lambda r: r["estimated_all_up_mass_kg"])
    summary = {
        "phase": 14,
        "model": "multivariable ideal actuator-disk screen with variable-bypass, auxiliary-inlet, FOM, altitude, cost, and 180km/h TWR gate",
        "rowCount": len(rows),
        "dimensionsSwept": {
            "fanOuterDiameterMm": list(FANS_MM),
            "motorClasses": [m[0] for m in MOTOR_CASES],
            "batteryAh": [b[0] for b in BATTERY_CASES],
            "auxInletFractions": [a[0] for a in AUX_CASES],
            "fanFigureOfMerit": [f[0] for f in FOMS],
            "projectionCases": [label for _, label in BODY_CROSS_SECTION_CASES_CM2],
            "projectedAreaRule": "max(fan_disk_union, battery_body_cross_section) + inlet_control_reserve",
            "boardsDefineInternalVolumeNotFrontalArea": True,
            "escInternalVolumeMm": [150, 150, 1.6],
            "flightControlInternalVolumeMm": [140, 100, 1.6],
        },
        "variablesModeled": [
            "fan diameter and hub diameter",
            "projected-area CdA scaling (constant reference Cd)",
            "motor mass, continuous bus input, gearbox removal, and price",
            "battery capacity mass and price proxy",
            "variable-bypass low-speed thrust multiplier from Phase-2 beta anchors",
            "auxiliary-inlet low-speed thrust sensitivity with flush-close above 180 km/h",
            "fan figure of merit 0.72 vs ideal 1.00",
            "sea-level and 3000 m ISA density and speed of sound",
            "tip Mach, eRPM, and 200 keRPM ESC limit",
        ],
        "variablesNotModeled": [
            "measured fan/motor/ESC maps",
            "inlet pressure recovery and spillage drag",
            "nozzle area matching and exit-loss maps",
            "Reynolds-dependent skin friction and drag rise",
            "structural, fatigue, flutter, and containment limits",
            "actuator/control effectiveness",
            "manufacturing tolerance and cost of fabricated parts",
        ],
        "lowSpeedTwrGate": {
            "minimum": cfg["airframe"]["lowSpeedTwrMinimum"],
            "upToKmh": cfg["airframe"]["lowSpeedTwrLimitKmh"],
            "altitudeForGate": "sea level",
            "note": "3 km TWR is reported separately but the low-speed gate is evaluated at sea level",
        },
        "counts": {
            "lowSpeedAndCruisePassNoAuxFom072": len(affordable_low_speed_power),
            "ofWhichListedPricePass": len(priced_low_speed_power),
        },
        "lightestCandidate": {
            "description": (
                f"{best_by_mass['fan_outer_diameter_mm']} mm fan, {best_by_mass['motor_class']}, "
                f"{best_by_mass['battery_Ah']} Ah, aux {best_by_mass['aux_fraction']}, FOM {best_by_mass['fan_figure_of_merit']}"
            ),
            "massKg": best_by_mass["estimated_all_up_mass_kg"],
            "TWR180seaLevel": best_by_mass["TWR_180_sea_level"],
            "vmaxKmh": best_by_mass["power_limited_vmax_kmh"],
        },
        "costGatesInr": {
            "motorUnitMax": cost["motorUnitPriceMaxInr"],
            "batteryPairMax": cost["batteryPairPriceMaxInr"],
            "knownMotorStatus": cost["knownMotor"]["status"],
            "knownBatteryStatus": cost["knownBattery"]["status"],
        },
        "newCloudSpendUsd": 0,
    }

    with (RESULTS / "phase14_multivariable_trade.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (RESULTS / "phase14_multivariable_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    assert len(rows) > 0
    assert any(r["low_speed_TWR_gate_sea_level"] == "PASS" for r in rows)
    assert summary["counts"]["lowSpeedAndCruisePassNoAuxFom072"] >= 1
    assert best_by_mass["estimated_all_up_mass_kg"] < BASE_MASS_KG
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
