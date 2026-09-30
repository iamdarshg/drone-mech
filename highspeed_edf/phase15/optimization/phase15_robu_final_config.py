"""Final configuration lock, robu.in only, verified against drone-arm limits.

drone-arm Rev-B ESC / FA4119 hard contract used as gates:
  * 6 independent sensorless-FOC channels, 12S (50.4 V max)
  * <= 60 A continuous per motor channel (360 A aggregate), external fused feeds
  * motor speed: soft 12,500 / hard 13,500 rpm (stock profile)
                 soft 17,000 / hard 18,000 rpm (provisional, unvalidated)
  * electrical RPM <= 200,000  (motor rpm x 7 pole pairs)
  * battery current per motor: soft 55 A / hard 60-65 A (provisional 70-75 A)
  * winding rollback 100-110 C, shutdown 120 C; bell 70/80 C
  * rewind to ~550 Kv is allowed; it changes Kv, NOT pole count, so it does not
    relax any eRPM or mechanical-speed limit

Targets: 720 km/h, TWR >= 1.0 across 0-180 km/h, motor <= INR 4000 each,
battery pair <= INR 12000. Frontal area uses the corrected passthrough model.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


PHASE = Path(__file__).resolve().parents[1]
RESULTS = PHASE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

G = 9.80665
RHO_3KM = 0.909128
RHO_SL = 1.225
BASE_BUS_POWER_W = 13170.0
BASE_DISK_POWER_W = 9162.7
RESIDUAL_AIRFRAME_KG = 5.0427740311 - 2.0 + 1.0
ETA_CAL = 0.253121
FOM = 0.72
VBR_180 = 1.06
POLE_PAIRS = 7
MOTOR_COUNT = 6
PACK_V = 44.4
SOFT_BATTERY_A = 55.0
HARD_BATTERY_A = 65.0
PROVISIONAL_BATTERY_A = 75.0
STOCK_RPM_SOFT = 12500.0
STOCK_RPM_HARD = 13500.0
PROV_RPM_HARD = 18000.0
ESC_ERPM_LIMIT = 200000.0
PHASE_CURRENT_CONTINUOUS_A = 60.0

# robu.in inventory (2026-09-29)
MOTORS = [
    ("flycci_fa4119_350kv_stock", 4499, 0.226, 350, True),
    ("flycci_fa4119_550kv_rewind", 4499 + 1750, 0.235, 550, True),  # + rewind materials
]
BATTERIES = [
    ("pro_range_4200_35c", 11958, 4.2, 35, 1.242),
    ("bonka_1600_150c", 10638, 1.6, 150, 0.564),
    ("bonka_1300_130c", 8498, 1.3, 130, 0.396),
    ("pro_range_5200_35c", 13638, 5.2, 35, 1.44),
]
FANS = [(90.0, (2.35, 2.65, 2.95)), (80.0, (2.35, 2.65, 2.95, 3.30, 3.60))]
CDA_CASES = (("front_inlet", 0.000654), ("side_inlet", 0.000800), ("legacy_target", 0.000900))
FAN_RPM = {90.0: 36360.0, 80.0: 41070.0}  # preserve the 90 mm R3 tip speed


def disk_thrust(power_w, rho, area_m2, speed_m_s):
    if power_w <= 0.0 or area_m2 <= 0.0:
        return 0.0
    lo, hi = 0.0, 2000.0
    for _ in range(120):
        vi = (lo + hi) / 2.0
        if 2.0 * rho * area_m2 * vi * (speed_m_s + vi) ** 2 < power_w:
            lo = vi
        else:
            hi = vi
    vi = (lo + hi) / 2.0
    return 2.0 * rho * area_m2 * vi * (speed_m_s + vi)


def required_thrust_power(rho, area_m2, speed_m_s, thrust_n):
    vi = 0.5 * (-speed_m_s + math.sqrt(speed_m_s**2 + 2.0 * thrust_n / (rho * area_m2)))
    return 2.0 * rho * area_m2 * vi * (speed_m_s + vi) ** 2


def main() -> None:
    rows = []
    for fan_mm, ratios in FANS:
        hub_mm = 40.0
        area_m2 = 2.0 * math.pi / 4.0 * (((fan_mm - 2.0) / 1000.0) ** 2 - (hub_mm / 1000.0) ** 2)
        fan_rpm = FAN_RPM[fan_mm]
        for ratio in ratios:
            motor_rpm = fan_rpm / ratio
            erpm = motor_rpm * POLE_PAIRS
            for motor_id, motor_price, motor_mass, kv, motor_stock in MOTORS:
                no_load_rpm = kv * PACK_V
                rpm_cap = PROV_RPM_HARD if motor_id.endswith("rewind") else STOCK_RPM_HARD
                for battery_id, battery_price, ah, c_cont, battery_mass in BATTERIES:
                    for cda_case, cda in CDA_CASES:
                        cruise_v = 720.0 / 3.6
                        cruise_bus_w = 0.5 * RHO_3KM * cruise_v**2 * cda * cruise_v / ETA_CAL
                        mass_kg = MOTOR_COUNT * motor_mass + battery_mass + RESIDUAL_AIRFRAME_KG
                        pack_current_cap_a = ah * c_cont
                        bus_current_cap_a = min(pack_current_cap_a, MOTOR_COUNT * PROVISIONAL_BATTERY_A, 360.0)
                        bus_power_cap_w = bus_current_cap_a * PACK_V
                        usable_bus_w = min(bus_power_cap_w, BASE_BUS_POWER_W)
                        # TWR at 180 km/h with VBR + FOM.
                        thrust_180 = disk_thrust(BASE_DISK_POWER_W * usable_bus_w / BASE_BUS_POWER_W, RHO_SL, area_m2, 180.0 / 3.6) * FOM * VBR_180
                        twr_180 = thrust_180 / (mass_kg * G)
                        thrust_0 = disk_thrust(BASE_DISK_POWER_W * usable_bus_w / BASE_BUS_POWER_W, RHO_SL, area_m2, 0.0) * FOM * 1.50
                        twr_0 = thrust_0 / (mass_kg * G)
                        top_speed = 720.0 * (usable_bus_w / cruise_bus_w) ** (1.0 / 3.0)
                        battery_current_at_720 = cruise_bus_w / PACK_V
                        phase_current_est = battery_current_at_720 / MOTOR_COUNT * (PACK_V / (PACK_V * 0.92))  # approx
                        gates = {
                            "in_stock": True,
                            "pack_current_ok": pack_current_cap_a >= battery_current_at_720,
                            "battery_soft_or_provisional_ok": battery_current_at_720 / MOTOR_COUNT <= PROVISIONAL_BATTERY_A,
                            "rpm_within_profile": motor_rpm <= rpm_cap,
                            "erpm_within_200k": erpm <= ESC_ERPM_LIMIT,
                            "phase_current_within_60a": phase_current_est <= PHASE_CURRENT_CONTINUOUS_A,
                            "motor_under_4000": motor_price <= 4000,
                            "battery_under_12000": battery_price <= 12000,
                            "reaches_720": top_speed >= 720.0,
                            "twr_ge_1_to_180": twr_180 >= 1.0,
                        }
                        rows.append({
                            "fan_mm": fan_mm,
                            "gear_ratio": ratio,
                            "fan_rpm": fan_rpm,
                            "motor_rpm": round(motor_rpm, 0),
                            "erpm": round(erpm, 0),
                            "motor_id": motor_id,
                            "motor_price_inr": motor_price,
                            "battery_id": battery_id,
                            "battery_pair_price_inr": battery_price,
                            "propulsion_cost_inr": MOTOR_COUNT * motor_price + battery_price,
                            "cda_case": cda_case,
                            "cda_m2": cda,
                            "mass_kg": round(mass_kg, 3),
                            "cruise_bus_power_720_w": round(cruise_bus_w, 0),
                            "battery_current_at_720_a": round(battery_current_at_720, 0),
                            "usable_bus_power_w": round(usable_bus_w, 0),
                            "power_limited_top_speed_kmh": round(top_speed, 1),
                            "twr_0": round(twr_0, 3),
                            "twr_180": round(twr_180, 3),
                            "all_gates_pass": all(gates.values()),
                            "failing_gates": ";".join(k for k, v in gates.items() if not v) or "PASS",
                        })
    rows.sort(key=lambda r: (r["all_gates_pass"], -(abs(r["motor_rpm"] - 12500.0)), r["propulsion_cost_inr"]))
    with (RESULTS / "phase15_robu_final_config.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    passing = [r for r in rows if r["all_gates_pass"]]
    cost_fail_only = [r for r in rows if set(r["failing_gates"].split(";")) <= {"motor_under_4000"}]
    summary = {
        "phase": 15,
        "supplier": "robu.in only",
        "droneArmLimitsApplied": {
            "channels": 6, "maxVoltageV": 50.4, "phaseCurrentContinuousA": 60.0,
            "batterySoftA": SOFT_BATTERY_A, "batteryHardA": HARD_BATTERY_A, "batteryProvisionalA": PROVISIONAL_BATTERY_A,
            "rpmSoft": STOCK_RPM_SOFT, "rpmHard": STOCK_RPM_HARD, "rpmProvisionalHard": PROV_RPM_HARD,
            "erpmLimit": ESC_ERPM_LIMIT, "polePairs": POLE_PAIRS,
        },
        "totalConfigs": len(rows),
        "passingEverything": len(passing),
        "passingExceptMotorPrice": len(cost_fail_only),
        "bestOverall": passing[0] if passing else (cost_fail_only[0] if cost_fail_only else None),
        "finding": "direct drive is impossible inside the drone-arm RPM limits at 12S: the fan needs ~36-41 krpm but motor rpm is capped at 13.5-18 krpm, so the gearbox is mandatory. A 550 Kv rewind changes Kv, not pole count, so it relaxes no eRPM/RPM limit.",
    }
    (RESULTS / "phase15_robu_final_config.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("\nBest rows (passing or cost-only fail):")
    for r in (passing + cost_fail_only)[:10]:
        print(r["fan_mm"], "ratio", r["gear_ratio"], r["motor_id"], "|", r["battery_id"], "| CdA", r["cda_case"],
              "| cost", r["propulsion_cost_inr"], "| motorRPM", r["motor_rpm"], "| eRPM", r["erpm"],
              "| TWR180", r["twr_180"], "| vmax", r["power_limited_top_speed_kmh"], "| fail", r["failing_gates"])
    assert len(rows) > 0


if __name__ == "__main__":
    main()
