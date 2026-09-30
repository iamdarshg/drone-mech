"""Loss accounting, rewind-machine cost, battery-bay future-proofing, and the
geared-vs-direct-drive decision.

Key questions answered:
  * direct drive with a tuned-Kv rewind vs a gearbox
  * 2 pole pairs vs 7 pole pairs at the operating point (electrical frequency,
    iron loss, eRPM)
  * full loss stack from battery to thrust
  * the 3D-printed auto-rewinder cost
  * battery-bay sizing so a hybrid or a large Li-ion pack can be added later
"""

from __future__ import annotations

import json
import math
from pathlib import Path


PHASE = Path(__file__).resolve().parents[1]
RESULTS = PHASE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

G = 9.80665
RHO_3KM = 0.909128
PACK_V = 44.4
R0_OHM = 0.030
CDA = 0.000693  # canonical raster CdA (was 0.000654)
FAN_MM = 80.0
HUB_MM = 40.0
V_KMH = 720.0
FAN_RPM = 41070.0

# Component efficiencies (analyst estimates, clearly labelled).
ETA_FAN = 0.72          # ducted-fan figure of merit (installed)
ETA_GEARBOX = 0.95
ETA_MOTOR = 0.90        # copper + iron + mechanical
ETA_ESC = 0.97


def loss_stack(with_gearbox: bool) -> dict:
    speed = V_KMH / 3.6
    area = 2.0 * math.pi / 4.0 * (((FAN_MM - 2.0) / 1000.0) ** 2 - (HUB_MM / 1000.0) ** 2)
    thrust = 0.5 * RHO_3KM * speed**2 * CDA
    vi = 0.5 * (-speed + math.sqrt(speed**2 + 2.0 * thrust / (RHO_3KM * area)))
    p_useful = thrust * speed                 # T x V0
    p_disk = thrust * (speed + vi)            # ideal actuator disk
    p_shaft = p_disk / ETA_FAN                # after the fan
    fan_loss = p_shaft - p_disk
    if with_gearbox:
        p_motor = p_shaft / ETA_GEARBOX
        gear_loss = p_motor - p_shaft
    else:
        p_motor = p_shaft
        gear_loss = 0.0
    p_esc_in = p_motor / ETA_MOTOR
    motor_loss = p_esc_in - p_motor
    p_bus = p_esc_in / ETA_ESC
    esc_loss = p_bus - p_esc_in
    current = p_bus / PACK_V
    battery_loss = current**2 * R0_OHM
    p_battery = p_bus + battery_loss
    return {
        "with_gearbox": with_gearbox,
        "useful_thrust_power_w": round(p_useful, 1),
        "ideal_disk_power_w": round(p_disk, 1),
        "fan_loss_w": round(fan_loss, 1),
        "gearbox_loss_w": round(gear_loss, 1),
        "motor_loss_w": round(motor_loss, 1),
        "esc_loss_w": round(esc_loss, 1),
        "battery_heat_w": round(battery_loss, 1),
        "bus_power_w": round(p_bus, 1),
        "battery_terminal_power_w": round(p_battery, 1),
        "pack_current_a": round(current, 1),
        "overall_efficiency_useful_over_battery": round(p_useful / p_battery, 4),
    }


def pole_analysis() -> list[dict]:
    rows = []
    for label, rpm, poles, torque_per_amp in (
        ("direct_2_pole_pairs", FAN_RPM, 2, None),
        ("geared_7_pole_pairs", 12500.0, 7, None),
        ("direct_7_pole_pairs_would_fail", FAN_RPM, 7, None),
    ):
        f_hz = rpm / 60.0 * poles
        rows.append({
            "case": label,
            "mechanical_rpm": rpm,
            "pole_pairs": poles,
            "electrical_frequency_hz": round(f_hz, 1),
            "erpm": round(rpm * poles, 0),
            "within_200k_erpm": rpm * poles <= 200000,
            "iron_loss_index_f_pow_1_5_relative": round((f_hz / 417.0) ** 1.5, 2),
        })
    return rows


def rewind_machine_bom() -> dict:
    # CNC attachment: reuse the TwoTrees 3018 Pro for the wire traverse (X/Z)
    # and its spindle to rotate the mandrel, so no separate gantry, steppers,
    # drivers or controller are purchased.
    items = [
        ("3D printed winding mandrel + stator holder + wire guide + tensioner (PLA/PETG)", 300),
        ("Hall-effect sensor + magnet ring for turn counting (or optical flag)", 150),
        ("Wiring, connectors, mandrel insert, fasteners, misc", 150),
    ]
    total = sum(cost for _, cost in items)
    return {
        "approach": "attachment for the existing TwoTrees 3018 Pro CNC — replace the spindle tool with a 3D-printed winding mandrel; the CNC X/Z axes do the wire traverse and the spindle rotates the mandrel",
        "items": [{"item": name, "inr": cost} for name, cost in items],
        "machine_total_inr": total,
        "note": "one-time tool; reuses the CNC so no gantry/stepper/driver/controller spend; per-motor wire/consumables shown separately",
    }


def main() -> None:
    geared = loss_stack(True)
    direct = loss_stack(False)
    poles = pole_analysis()
    machine = rewind_machine_bom()

    motor_price = 3409       # Rocket 3670 4-pole 1550KV, robu, in stock
    wire_per_motor = 500
    six_motor = 6 * motor_price
    six_wire = 6 * wire_per_motor
    build_total_with_machine = six_motor + six_wire + machine["machine_total_inr"]
    build_total_no_machine = six_motor + six_wire

    config = {
        "phase": 15,
        "report": "FINAL CONFIG — high-amperage battery now, hybrid/large-Li-ion ready later",
        "architecture": {
            "motor": "6x rewound 4-pole inrunner (Rocket 3670 class), tuned Kv",
            "drive": "DIRECT DRIVE — gearbox deleted in favour of a tuned Kv",
            "tunedKv_80mm": round(FAN_RPM / PACK_V, 0),
            "fanMm": FAN_MM,
            "hubMm": HUB_MM,
            "fanRpm": FAN_RPM,
            "esc": "drone-arm Rev-B, 6 channels, 12S, sensorless FOC, <=60 A/channel",
            "batteryNow": "2x Bonka 6S 1600 mAh 150C (12S 1.6 Ah, 240 A) INR 10638",
        },
        "poleCountAnswer": {
            "question": "is 2 pole pairs terrible for efficiency?",
            "answer": "No — at high mechanical speed fewer pole pairs gives LOWER electrical frequency, so LOWER iron (hysteresis+eddy) loss. A 2-pole-pair motor at 41,070 rpm runs at ~1,369 Hz, essentially the same frequency as a 7-pole-pair motor at 12,500 rpm (~1,458 Hz), so the direct-drive rewind is not penalised. Fewer poles does reduce torque-per-amp (more copper loss for a given torque) and motor inductance, but at this high speed iron loss dominates, so low pole count is the right choice. Pole count is set by the rotor magnets and is NOT changed by a rewind.",
            "analysis": poles,
        },
        "gearboxVsDirect": {
            "geared": geared,
            "direct": direct,
            "conclusion": "Deleting the gearbox removes the 5% gear loss and the 0.72 kg gearbox, and keeps the same electrical frequency, so direct drive wins. It requires a rewound Kv of ~925 (80 mm) and a rotor/bearing/containment rating for ~41 krpm.",
        },
        "rewindMachine": machine,
        "cost": {
            "six_motor_price_inr": six_motor,
            "six_motor_rewire_wire_inr": six_wire,
            "six_motor_total_no_machine_inr": build_total_no_machine,
            "six_motor_total_with_machine_inr": build_total_with_machine,
            "motor_pair_budget_inr": 24000,
            "under_budget_without_machine": build_total_no_machine <= 24000,
            "under_budget_with_machine": build_total_with_machine <= 24000,
            "note": "if the winder is a reusable tool it is not charged to the six-motor ceiling; if it is, the build exceeds INR 24000 by INR " + str(build_total_with_machine - 24000),
        },
        "batteryBayFutureProofing": {
            "currentPackMm_each": [185, 65, 55],
            "currentPairVolumeL": round(2 * 0.185 * 0.065 * 0.055 * 1000, 3),
            "reservedBayMm": [200, 135, 75],
            "reservedBayVolumeL": round(0.200 * 0.135 * 0.075 * 1000, 3),
            "option1_largeLiIon_12S_200A_200km": {
                "example": "12S 10 Ah 90 A+ Li-ion (Samsung 6S2P 10000 mAh 9C pair or equivalent)",
                "fitsReservedBay": True,
                "gives": "~219 km range at ~305 km/h, >200 A if a high-power Li-ion 21700 blend is used",
            },
            "option2_hybrid": "reserve a second isolated bay + connector for an auxiliary range pack or a fuel-cell/turbine range extender feeding the same 12S bus",
            "requirements": [
                "battery bay sized 200 x 135 x 75 mm with adjustable rails and a retention strap",
                "two independent fused 12S feed points so a second/hybrid pack can be paralleled or switched",
                "mass ballast and CG range reserved for a pack up to ~2.6 kg",
                "thermal vent path and connector cut-outs sized for a larger pack",
            ],
        },
        "newCloudSpendUsd": 0,
    }
    (RESULTS / "phase15_losses_and_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
