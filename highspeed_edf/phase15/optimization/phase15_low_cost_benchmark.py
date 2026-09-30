"""Low-time-cost benchmark: rank purchasable motor x battery combos.

Scores every motor/battery pair from the research dataset for
  * flight time at the 650 km/h cruise (primary objective),
  * efficiency (propulsive power / electrical power at cruise),
  * flight performance (low-speed TWR and power-limited top speed),
subject to the hard gates: 12S, TWR>=1.0 to 180 km/h, >=650 km/h, and the INR
motor/battery cost caps.

Physics reuses the Phase-14 calibrated ideal-disk screen. Everything is a
screening estimate; no measured maps exist. The winning combo is written to a
JSON file that the high-cost generative benchmark consumes.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


PHASE = Path(__file__).resolve().parents[1]
CONFIG = PHASE / "configs" / "phase15_sourcing.json"
RESULTS = PHASE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

G = 9.80665
BASE_BUS_POWER_W = 13170.0
BASE_DISK_POWER_W = 9162.7
BASE_CDA_M2 = 0.0009
REFERENCE_CRUISE_650_W = 9513.5
R3_DESIGN_RPM_90MM = 36360.0
BASE_TIP_RADIUS_M = 0.045 - 0.0014
BODY_CROSS_SECTION_CM2 = 54.0
INLET_CONTROL_RESERVE_CM2 = 5.52
FAN_MM = 80.0  # CdA-saturation sweet spot from the Phase-14 union model
HUB_MM_BY_POLE = 40.0
# User correction: the duct is a PASS-THROUGH, not a solid frontal face. The
# through-flow area must not be counted as frontal area; only the solid parts
# (body/battery block, hub seen through the duct, inlet lips, control surfaces,
# duct wall thickness if external) count. Frontal area is therefore set mostly
# by the battery/body block and is nearly independent of fan diameter.
BATTERY_BLOCK_CM2 = 56.3   # two 136x44x64 packs side by side, unrounded
DUCT_WALL_THICKNESS_MM = 2.0


def isa(altitude_m: float) -> tuple[float, float]:
    temperature = 288.15 - 0.0065 * altitude_m
    pressure = 101325.0 * (temperature / 288.15) ** (9.80665 / (287.05 * 0.0065))
    return pressure / (287.05 * temperature), math.sqrt(1.4 * 287.05 * temperature)


def disk_thrust(power_w: float, rho: float, area_m2: float, speed_m_s: float) -> float:
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


def projected_area_cm2(diameter_mm: float) -> float:
    return max(math.pi * (diameter_mm / 20.0) ** 2, BODY_CROSS_SECTION_CM2) + INLET_CONTROL_RESERVE_CM2


def cda_for_fan(diameter_mm: float) -> float:
    # Canonical CdA from the corrected raster frontal-area model
    # (80 mm / 40 mm hub / front inlet / 30 mm wing): 0.000693 m2.
    # The previous union approximation returned a different value for the same
    # layout; this now matches phase15_range_and_cost, losses and reconciliation.
    del diameter_mm
    return 0.000693


WING_AREA_M2 = 0.19
ASPECT_RATIO = 1.5
OSWALD = 0.7


def required_electrical_w(speed_kmh: float, rho: float, area_m2: float, cda: float, mass_kg: float) -> float:
    """Electrical power for level flight: parasite + induced drag, then ideal disk."""
    speed = speed_kmh / 3.6
    if speed <= 0.0:
        return math.inf
    q = 0.5 * rho * speed**2
    weight = mass_kg * G
    parasite = q * cda
    induced = weight**2 / (q * WING_AREA_M2 * math.pi * ASPECT_RATIO * OSWALD)
    thrust = parasite + induced
    vi = 0.5 * (-speed + math.sqrt(speed**2 + 2.0 * thrust / (rho * area_m2)))
    disk_power = thrust * (speed + vi)
    return disk_power * (BASE_BUS_POWER_W / BASE_DISK_POWER_W)


def endurance_sweep(usable_energy_wh: float, rho: float, area_m2: float, cda: float, mass_kg: float, power_cap_w: float) -> tuple[float, float]:
    best_minutes, best_speed = 0.0, 0.0
    for speed_kmh in range(70, 721, 5):
        electrical = required_electrical_w(speed_kmh, rho, area_m2, cda, mass_kg)
        if electrical <= 0.0 or not math.isfinite(electrical) or electrical > power_cap_w:
            continue
        minutes = usable_energy_wh / electrical * 60.0
        if minutes > best_minutes:
            best_minutes, best_speed = minutes, float(speed_kmh)
    return best_minutes, best_speed


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    mission = cfg["missionAssumptions"]
    fixed = cfg["knownFixedAirframeMassKg"]
    payload_kg = mission["payloadKg"]
    rho_3k, _ = isa(mission["cruiseAltitudeM"])
    rho_sl, _ = isa(0.0)
    # Non-propulsion, non-battery residual, restated to a 1 kg payload.
    residual_kg = fixed["phase13TotalIncluding2kgPayloadKg"] - fixed["phase13SixMotorsKg"] - fixed["phase13BatteryPairKg"]
    other_kg = residual_kg - 2.0 + payload_kg
    area_m2 = 2.0 * math.pi / 4.0 * (((FAN_MM - 2.0) / 1000.0) ** 2 - (HUB_MM_BY_POLE / 1000.0) ** 2)
    cda = cda_for_fan(FAN_MM)
    cruise_v = mission["cruiseSpeedKmh"] / 3.6
    cruise_propulsive_w = 0.5 * rho_3k * cruise_v**2 * cda * cruise_v
    eta_cal = 0.253121  # Phase-14 aggregate calibration
    cruise_bus_w = cruise_propulsive_w / eta_cal
    top_speed_cda_cap = cda

    rows = []
    for motor in cfg["motors"]:
        for battery in cfg["batteries"]:
            motor_count = 6
            mass_kg = motor_count * motor["massKg"] + 2 * battery["massKgPerPack"] + other_kg
            motor_current_cap_a = math.inf if motor["maxPowerW"] is None else motor["maxPowerW"] / mission["nominalPackVoltageV"]
            battery_current_cap_a = battery["capacityAhPerString"] * battery["cContinuous"]
            bus_current_cap_a = min(6 * motor_current_cap_a, battery_current_cap_a, 330.0)
            bus_power_cap_w = bus_current_cap_a * mission["nominalPackVoltageV"]
            usable_bus_power_w = min(bus_power_cap_w, motor_count * (motor["maxPowerW"] or 0.0), BASE_BUS_POWER_W)
            usable_energy_wh = battery["capacityAhPerString"] * mission["nominalPackVoltageV"] * mission["usableEnergyFraction"]
            flight_time_s = usable_energy_wh * 3600.0 / cruise_bus_w if cruise_bus_w > 0 else 0.0
            # Low-speed TWR at 180 km/h sea level with the variable-bypass (1.06x) gain and FOM 0.72.
            low_mult = 1.06 * 0.72
            disk_power_w = BASE_DISK_POWER_W * usable_bus_power_w / BASE_BUS_POWER_W
            twr_180 = disk_thrust(disk_power_w, rho_sl, area_m2, 180.0 / 3.6) * low_mult / (mass_kg * G)
            # 12,930 W is the calibrated 720 km/h bus power; 12930/9513.5 = 1.359.
            top_speed_kmh = 720.0 * (usable_bus_power_w / (REFERENCE_CRUISE_650_W * 1.359 * top_speed_cda_cap / BASE_CDA_M2)) ** (1.0 / 3.0) if usable_bus_power_w > 0 else 0.0
            rpm_same_tip = R3_DESIGN_RPM_90MM * BASE_TIP_RADIUS_M / ((FAN_MM / 2.0 - 1.4) / 1000.0)
            erpm = rpm_same_tip * motor["polePairs"]
            hub_ok = HUB_MM_BY_POLE <= 44.0
            in_stock = motor["inStock"] is True and battery["inStock"] is True
            motor_cap_ok = motor["priceInr"] is not None and motor["priceInr"] <= cfg["costCaps"]["motorUnitMaxInr"]
            battery_cap_ok = battery["priceInrFor12s"] is not None and battery["priceInrFor12s"] <= cfg["costCaps"]["batteryPairMaxInr"]
            gates = {
                "in_stock": in_stock,
                "motor_under_unit_cap": motor_cap_ok,
                "battery_under_pair_cap": battery_cap_ok,
                "twr_ge_1_to_180": twr_180 >= 1.0,
                "top_speed_ge_650": top_speed_kmh >= 650.0,
                "erpm_within_200k": erpm <= 200000.0,
            }
            rows.append({
                "motor_id": motor["id"],
                "battery_id": battery["id"],
                "motor_supplier": motor["supplier"],
                "battery_supplier": battery["supplier"],
                "motor_price_inr": motor["priceInr"],
                "battery_pair_price_inr": battery["priceInrFor12s"],
                "propulsion_cost_inr": (None if motor["priceInr"] is None or battery["priceInrFor12s"] is None else 6 * motor["priceInr"] + battery["priceInrFor12s"]),
                "estimated_mass_kg": round(mass_kg, 3),
                "usable_bus_power_W": round(usable_bus_power_w, 0),
                "bus_current_cap_a": round(bus_current_cap_a, 0),
                "cruise_bus_power_650_W": round(cruise_bus_w, 0),
                "flight_time_min_at_650kmh": round(flight_time_s / 60.0, 2),
                "max_endurance_min": round(endurance_sweep(usable_energy_wh, rho_3k, area_m2, cda, mass_kg, bus_power_cap_w)[0], 2),
                "max_endurance_speed_kmh": endurance_sweep(usable_energy_wh, rho_3k, area_m2, cda, mass_kg, bus_power_cap_w)[1],
                "low_speed_TWR_180_sea_level": round(twr_180, 3),
                "power_limited_top_speed_kmh": round(top_speed_kmh, 1),
                "erpm_at_80mm": round(erpm, 0),
                "all_gates_pass": all(gates.values()),
                "gate_detail": ";".join(name for name, ok in gates.items() if not ok) or "PASS",
            })

    rows.sort(key=lambda r: (r["all_gates_pass"], r["flight_time_min_at_650kmh"]), reverse=True)
    passing = [r for r in rows if r["all_gates_pass"]]

    with (RESULTS / "phase15_low_cost_ranking.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    best = passing[0] if passing else None
    handoff = {
        "phase": 15,
        "benchmark": "low_time_cost",
        "objective": "maximize flight time subject to 12S, TWR>=1.0 to 180 km/h, >=650 km/h, and INR cost caps",
        "fanMm": FAN_MM,
        "hubMm": HUB_MM_BY_POLE,
        "cdaM2": round(cda, 7),
        "payloadKg": payload_kg,
        "candidateCount": len(rows),
        "gatesPassingCount": len(passing),
        "bestCombo": best,
        "bestAvailableIfGatesIgnored": rows[0],
        "note": "If no combo passes every gate (expected from the live listings), bestCombo is null and the high-cost benchmark must be run on the best physically-credible combo with the cost gate explicitly waived.",
    }
    (RESULTS / "phase15_low_cost_handoff.json").write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "candidateCount": len(rows),
        "gatesPassingCount": len(passing),
        "bestIfGatesIgnored": rows[0],
        "best": best,
    }, indent=2))


if __name__ == "__main__":
    main()
