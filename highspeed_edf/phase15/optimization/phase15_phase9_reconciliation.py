"""Reconcile the Phase-9 (~12.9 kW) and the loss-model (~3.9 kW) cruise powers.

Phase-1/9 model (optimization/phase1_feasibility.py):
    mdot = rho * V0 * A * capture_fraction          # FIXED by the inlet area
    Vj   = V0 + thrust / mdot                       # jet velocity forced
    solve pr so the nozzle expands to ambient
    work = mdot * cp * (Tt_out - Tt_in)
    electrical = work / (eta_motor * eta_esc)
  with inlet recovery 0.98, nozzle recovery 0.98, compressor eta 0.82.

Momentum/actuator-disk lower bound:
    P = T*V0 + T^2 / (2*mdot)   == 0.5*mdot*(Vj^2 - V0^2)

At M=0.6 the fan's useful pressure rise is only ~1-2% of the freestream TOTAL
pressure, so a 2% inlet + 2% nozzle total-pressure loss dominates and the
required pressure ratio (and work) explodes. This script sweeps the recovery
and efficiency assumptions to show the true sensitivity and the resulting range.
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
CP = 1004.685
GAMMA = 1.4
EXPONENT = (GAMMA - 1.0) / GAMMA
R = 287.05
ALT = 3000.0


def isa(altitude_m: float) -> tuple[float, float, float]:
    t = 288.15 - 0.0065 * altitude_m
    p = 101325.0 * (t / 288.15) ** (9.80665 / (287.05 * 0.0065))
    return p, t, p / (287.05 * t)


def cycle_case(thrust_n: float, speed_m_s: float, mdot: float, recovery_in: float,
               recovery_noz: float, eta_c: float, eta_motor: float, eta_esc: float) -> dict:
    p_amb, t_amb, rho = isa(ALT)
    t_total_in = t_amb + speed_m_s**2 / (2.0 * CP)
    p_total_fs = p_amb * (t_total_in / t_amb) ** (GAMMA / (GAMMA - 1.0))
    p_face = p_total_fs * recovery_in
    required_vj = speed_m_s + thrust_n / mdot

    def exit_speed(pr: float) -> float:
        t_total_out = t_total_in * (1.0 + (pr**EXPONENT - 1.0) / eta_c)
        p_noz = p_face * pr * recovery_noz
        if p_noz <= p_amb:
            return 0.0
        t_static = t_total_out * (p_amb / p_noz) ** EXPONENT
        return math.sqrt(max(0.0, 2.0 * CP * (t_total_out - t_static)))

    lo, hi = 1.0, 8.0
    for _ in range(120):
        mid = 0.5 * (lo + hi)
        if exit_speed(mid) < required_vj:
            lo = mid
        else:
            hi = mid
    pr = 0.5 * (lo + hi)
    t_total_out = t_total_in * (1.0 + (pr**EXPONENT - 1.0) / eta_c)
    shaft = mdot * CP * (t_total_out - t_total_in)
    electrical = shaft / (eta_motor * eta_esc)
    ideal_momentum = thrust_n * speed_m_s + thrust_n**2 / (2.0 * mdot)
    return {
        "inlet_recovery": recovery_in,
        "nozzle_recovery": recovery_noz,
        "compressor_eta": eta_c,
        "required_pr": round(pr, 4),
        "required_jet_velocity_m_s": round(required_vj, 2),
        "shaft_power_w": round(shaft, 0),
        "electrical_power_w": round(electrical, 0),
        "ideal_momentum_power_w": round(ideal_momentum, 0),
        "overpower_factor_vs_ideal": round(electrical / ideal_momentum, 2),
        "propulsive_efficiency": round(thrust_n * speed_m_s / electrical, 3),
    }


def main() -> None:
    speed = 720.0 / 3.6
    cda = 0.000693  # canonical raster CdA (was 0.000654)
    p_amb, t_amb, rho = isa(ALT)
    thrust = 0.5 * rho * speed**2 * cda
    fan_mm, hub_mm = 80.0, 40.0
    annulus = 2.0 * math.pi / 4.0 * (((fan_mm - 2.0) / 1000.0) ** 2 - (hub_mm / 1000.0) ** 2)
    capture_fraction = 0.85
    mdot = rho * speed * annulus * capture_fraction

    # Phase-9 stated basis and a set of better/worse inlets.
    cases = [
        ("phase9_basis", 0.98, 0.98, 0.82),
        ("good_inlet", 0.99, 0.99, 0.86),
        ("very_good_inlet", 0.995, 0.995, 0.90),
        ("clean_idealised", 1.0, 1.0, 1.0),
        ("poor_inlet", 0.97, 0.97, 0.80),
    ]
    rows = []
    for label, rin, rnoz, eta in cases:
        case = cycle_case(thrust, speed, mdot, rin, rnoz, eta, 0.92, 0.97)
        case["case"] = label
        rows.append(case)

    # Range sensitivity on the two bounding power levels.
    def range_km(bus_power_w: float, capacity_ah: float = 1.6) -> float:
        energy_wh = capacity_ah * 44.4 * 0.85
        time_h = energy_wh / bus_power_w
        return 720.0 * time_h  # km/h * h = km at 720 km/h

    summary = {
        "phase": 15,
        "question": "why is Phase-9 ~12.9 kW when the momentum/loss model gives ~3.9 kW?",
        "operatingPoint": {
            "speedKmh": 720.0, "altitudeM": ALT, "cdaM2": cda,
            "thrustN": round(thrust, 2), "massFlowKgS": round(mdot, 4),
            "annulusM2": round(annulus, 6), "captureFraction": capture_fraction,
            "freestreamTotalPressurePa": round(p_amb * (1 + 0.2 * (speed / math.sqrt(GAMMA * R * t_amb)) ** 2) ** 3.5, 0),
        },
        "explanation": (
            "At M=0.6 the freestream TOTAL pressure is ~1.28x ambient, but the fan only needs to add "
            "~1-2% of that total pressure to make thrust. A 2% inlet loss plus a 2% nozzle loss is therefore "
            "the same order as the useful pressure rise, so the fan must work several times harder. Phase-9 "
            "used inlet 0.98, nozzle 0.98, compressor eta 0.82, which lands at ~10 kW shaft / ~13 kW electrical. "
            "The momentum/actuator-disk model ignores those recovery losses, giving ~3.4 kW."
        ),
        "sensitivityCases": rows,
        "rangeAt1p6AhSprint": {
            "at_phase9_12p9kW_km": round(range_km(12930.0), 1),
            "at_10kW_km": round(range_km(10000.0), 1),
            "at_6kW_km": round(range_km(6000.0), 1),
            "at_lossmodel_3p9kW_km": round(range_km(3869.6), 1),
        },
        "realisticConvention": (
            "Industry practice sizes an electrically-driven fan on measured thrust-vs-airspeed maps, not on an "
            "idealised compressor cycle. NOTE: the phase9_basis row of THIS model computes 7.9 kW, not the "
            "12.93 kW of the original Phase-9 run; the difference is the smaller 80 mm annulus and mass flow "
            "used here. The defensible envelope for this duct is therefore roughly 4-10.5 kW electrical at "
            "720 km/h (2.7 kW ideal floor), with the original 12.93 kW as a higher-mass-flow bound."
        ),
        "newCloudSpendUsd": 0,
    }
    with (RESULTS / "phase15_phase9_reconciliation.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (RESULTS / "phase15_phase9_reconciliation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
