"""Sub-INR-4000 motor path (rewind) and max-range calculation.

Part 1: motors <= INR 4000 at robu.in. The only physical route is to buy a
cheaper 6S-class motor and rewind it for 12S. A rewind changes Kv and turn
count, NOT pole count, and it costs extra, so it only stays under the ceiling if
the rewind materials are cheap. drone-arm's own decision record budgets
~INR 1750/motor for copper+Nomex+varnish+thermistors; a bare-wire DIY rewind is
cheaper. Both cases are shown.

Part 2: range vs speed. Range = speed * time, time = energy / electrical power,
with power from parasite + induced drag through the ideal-disk model. Reports
the max-range speed and distance for the accepted LiPo pack and for the
higher-energy Li-ion packs the user asked about.
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
BASE_BUS_POWER_W = 13170.0
BASE_DISK_POWER_W = 9162.7
PACK_V = 44.4
WING_AREA_M2 = 0.19
ASPECT_RATIO = 1.5
OSWALD = 0.7
CDA = 0.000693  # canonical: 80 mm / 40 mm hub / front inlet / 30 mm wing (raster model)
RESIDUAL_AIRFRAME_KG = 5.0427740311 - 2.0 + 1.0
MOTOR_COUNT = 6

# Motors <= INR 4000 (6S-class) that require a rewind to suit 12S.
REWIND_MOTORS = [
    ("tarot_3115_900kv", 3109, 0.112, "in stock, 6S, 31x15 stator"),
    ("rocket_3670_4pole_1550kv", 3409, 0.29, "in stock, 4-6S, 4-pole, 36x70 can"),
    ("qpt_3115_900kv", 3879, 0.121, "out of stock, 6S, 1700 W"),
]
REWIND_MATERIAL_CASES = (
    ("diy_bare_wire", 500, "bare magnet wire + minimal consumables, self-wound"),
    ("decision_record_full", 1750, "copper + Nomex + varnish + thermistors + consumables per drone-arm"),
)

# Batteries: id, 12S price INR, capacity Ah, continuous C, energy Wh (12S), current cap A
BATTERIES = [
    ("bonka_1600_150c", 10638, 1.6, 150, 0),
    ("pro_range_4200_35c", 11958, 4.2, 35, 0),
    ("liion_prange_p50b_6s1p_5000_12c", 11658, 5.0, 12, 0),
    ("liion_prange_nmc_6s2p_10000_3c", 12278, 10.0, 3, 0),
    ("liion_samsung_6s2p_10000_9c", 16478, 10.0, 9, 0),
]
BATTERY_VOLTAGE = 44.4


def drag_n(speed_m_s: float, mass_kg: float) -> float:
    q = 0.5 * RHO_3KM * speed_m_s**2
    parasite = q * CDA
    induced = (mass_kg * G) ** 2 / (q * WING_AREA_M2 * math.pi * ASPECT_RATIO * OSWALD)
    return parasite + induced


def electrical_power_w(speed_kmh: float, mass_kg: float, area_m2: float) -> float:
    speed = speed_kmh / 3.6
    if speed <= 0:
        return math.inf
    thrust = drag_n(speed, mass_kg)
    vi = 0.5 * (-speed + math.sqrt(speed**2 + 2.0 * thrust / (RHO_3KM * area_m2)))
    disk = thrust * (speed + vi)
    return disk * (BASE_BUS_POWER_W / BASE_DISK_POWER_W)


def main() -> None:
    motor_mass = 0.29  # rewound Rocket 3670 class
    fan_mm, hub_mm = 80.0, 40.0
    area_m2 = 2.0 * math.pi / 4.0 * (((fan_mm - 2.0) / 1000.0) ** 2 - (hub_mm / 1000.0) ** 2)

    motor_rows = []
    for motor_id, price, mass, note in REWIND_MOTORS:
        for material_case, material_cost, material_note in REWIND_MATERIAL_CASES:
            total = price + material_cost
            motor_rows.append({
                "motor_id": motor_id,
                "note": note,
                "motor_price_inr": price,
                "rewind_material_inr": material_cost,
                "rewind_case": material_case,
                "total_unit_inr": total,
                "under_4000": total <= 4000,
                "six_motor_inr": MOTOR_COUNT * total,
                "material_note": material_note,
            })

    range_rows = []
    for battery_id, price, ah, c_cont, _ in BATTERIES:
        energy_wh = ah * BATTERY_VOLTAGE * 0.85
        # A 12S string is 12 cells, not 6: use x12 (sourced per-pack masses preferred).
        mass_kg = MOTOR_COUNT * motor_mass + (ah * 0.0125 * 12) + RESIDUAL_AIRFRAME_KG
        current_cap_a = min(ah * c_cont, 360.0)
        power_cap_w = current_cap_a * BATTERY_VOLTAGE
        best_range_km, best_speed = 0.0, 0.0
        for speed_kmh in range(60, 721, 5):
            power_w = electrical_power_w(speed_kmh, mass_kg, area_m2)
            if power_w > power_cap_w:
                continue
            time_h = energy_wh / power_w
            distance_km = (speed_kmh) * time_h
            if distance_km > best_range_km:
                best_range_km, best_speed = distance_km, float(speed_kmh)
        range_rows.append({
            "battery_id": battery_id,
            "battery_pair_price_inr": price,
            "capacity_ah": ah,
            "continuous_C": c_cont,
            "usable_energy_wh": round(energy_wh, 1),
            "current_cap_a": round(current_cap_a, 0),
            "power_cap_w": round(power_cap_w, 0),
            "under_12000": price <= 12000,
            "max_range_km": round(best_range_km, 2),
            "max_range_speed_kmh": best_speed,
            "note": "range = speed x energy / electrical power, parasite+induced drag, ideal disk",
        })

    with (RESULTS / "phase15_rewind_motor_costs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(motor_rows[0]))
        writer.writeheader()
        writer.writerows(motor_rows)
    with (RESULTS / "phase15_range.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(range_rows[0]))
        writer.writeheader()
        writer.writerows(range_rows)

    best_range = max(range_rows, key=lambda r: r["max_range_km"])
    best_value = min((r for r in range_rows if r["under_12000"]), key=lambda r: -r["max_range_km"])
    summary = {
        "phase": 15,
        "part1_motors_under_4000": {
            "robuCheapest12sMotorInr": 4499,
            "robuCheapest12sMotor": "FLYCCI FA4119 350KV",
            "finding": "no stock 12S motor <= INR 4000; only route is to rewind a cheaper 6S-class motor",
            "rewindCheapestTotalInr": min(r["total_unit_inr"] for r in motor_rows),
            "rewindCheapestUnder4000": [r for r in motor_rows if r["under_4000"]],
        },
        "part2_range": {
            "cdaM2": CDA,
            "fanMm": fan_mm,
            "batteries": range_rows,
            "bestRange": best_range,
            "bestValueUnder12000": best_value,
        },
        "newCloudSpendUsd": 0,
    }
    (RESULTS / "phase15_range_and_cost.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
