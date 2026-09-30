#!/usr/bin/env python3
"""Run Phase 6 geometry scheduling and Phase 7 system-closure screens."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


STUDY = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run() -> None:
    config_path = STUDY / "configs" / "phase6_7_system_closure.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    cfg6, cfg7 = config["phase6"], config["phase7"]
    results = STUDY / "results"
    core_rows = read_csv(results / "phase3_core_area_schedule_sensitivity.csv")
    summary_rows = read_csv(results / "phase3_operating_summary.csv")
    motor_rows = read_csv(results / "phase5_motor_drive_loads.csv")
    pack_rows = read_csv(results / "phase5_pack_power_envelope.csv")
    ross_rows = read_csv(results / "phase4_ross_review.csv")

    casing = float(cfg6["casingDiameterM"])
    hub = float(cfg6["hubDiameterM"])
    available_annulus = math.pi / 4.0 * (casing**2 - hub**2)
    core_schedule: list[dict[str, Any]] = []
    area_margins: list[dict[str, Any]] = []
    core_diameter = {
        int(float(row["speed_kmh"])): float(row["candidate_core_tip_diameter_m"])
        for row in core_rows
    }
    min_area = min(float(row["area_required_for_re_50000_m2"]) for row in core_rows)
    max_area = max(float(row["area_required_for_re_50000_m2"]) for row in core_rows)

    for row in sorted(core_rows, key=lambda r: float(r["speed_kmh"])):
        speed = int(float(row["speed_kmh"]))
        target_area = float(row["area_required_for_re_50000_m2"])
        actual_area = math.pi / 4.0 * (core_diameter[speed] ** 2 - hub**2)
        remaining = available_annulus - actual_area
        core_schedule.append(
            {
                "speed_kmh": speed,
                "stator_reynolds_target": cfg6["statorReynoldsFloor"],
                "uniform_annulus_reynolds": float(row["current_uniform_annulus_reynolds"]),
                "core_area_re_for_floor_m2": target_area,
                "reconstructed_core_area_m2": actual_area,
                "core_outer_diameter_m": core_diameter[speed],
                "core_area_fraction_of_available_annulus": actual_area / available_annulus,
                "remaining_bypass_annulus_area_m2": remaining,
                "remaining_bypass_area_fraction": remaining / available_annulus,
                "axial_velocity_for_re_floor_m_s": float(row["required_axial_velocity_m_s"]),
                "full_80mm_envelope_fit": 0.0 < actual_area < available_annulus,
                "source_class": "Phase-3 ideal-gas continuity sensitivity; no local-loss or bypass-map validation",
            }
        )
        for margin in cfg6["coreAreaMarginFractions"]:
            margin = float(margin)
            enlarged_area = target_area * (1.0 + margin)
            outer_d2 = hub**2 + 4.0 * enlarged_area / math.pi
            outer_d = math.sqrt(outer_d2) if outer_d2 >= 0.0 else float("nan")
            fit = enlarged_area < available_annulus
            area_margins.append(
                {
                    "speed_kmh": speed,
                    "core_flow_area_margin_fraction": margin,
                    "required_core_area_m2": enlarged_area,
                    "required_core_outer_diameter_m": outer_d,
                    "remaining_bypass_annulus_area_m2": max(0.0, available_annulus - enlarged_area),
                    "remaining_bypass_area_fraction": max(0.0, available_annulus - enlarged_area) / available_annulus,
                    "fits_80mm_casing_32mm_hub": fit,
                    "status": "geometrically_possible_screen_only" if fit else "NO_ROOM_FOR_CORE_AND_BYPASS",
                    "source_class": "analyst area-margin sensitivity; not a calibrated loss allowance",
                }
            )

    def by_speed(rows: list[dict[str, str]], key: str = "speed_kmh") -> dict[int, list[dict[str, str]]]:
        grouped: dict[int, list[dict[str, str]]] = {}
        for row in rows:
            grouped.setdefault(int(float(row[key])), []).append(row)
        return grouped

    summaries = {int(row["speed_kmh"]): row for row in summary_rows}
    motors = by_speed(motor_rows)
    packs = {
        int(row["speed_kmh"]): row
        for row in pack_rows
        if math.isclose(float(row["pack_r0_assumed_ohm"]), float(cfg7["packR0AssumptionOhm"]))
    }
    ross = {row["stage"]: row for row in ross_rows}
    first_critical = max(float(row["first_critical_rpm"]) for row in ross.values())
    integrated: list[dict[str, Any]] = []
    for speed, summary in sorted(summaries.items()):
        stage_motors = motors[speed]
        pack = packs[speed]
        rpm_values = [float(x) for x in json.loads(summary["motor_rpm_schedule"])]
        max_battery_channel = max(float(row["channel_battery_current_at_44_4v_no_sag_a"]) for row in stage_motors)
        max_phase_estimate = max(float(row["equivalent_torque_current_a_from_ideal_kv"]) for row in stage_motors)
        pack_current = float(pack["constant_power_current_solution_a"] or "inf")
        limits = {
            "pack_soft_current": pack_current <= 6.0 * float(cfg7["softBatteryCurrentAperChannel"]),
            "motor_soft_battery_current": max_battery_channel <= float(cfg7["softBatteryCurrentAperChannel"]),
            "esc_continuous_phase_current_estimate": max_phase_estimate <= float(cfg7["escContinuousPhaseCurrentARms"]),
            "motor_soft_rpm": max(rpm_values) <= float(cfg7["motorSoftRpm"]),
            "startup_resonance_resolved": bool(cfg7["rotordynamicStartupCrossingResolved"])
            or min(rpm_values) > first_critical,
            "75cm2_frontal_area_verified": bool(cfg7["geometryMeasured"]),
        }
        reasons = [name for name, passes in limits.items() if not passes]
        power_kw = float(summary["electrical_power_estimate_w"]) / 1000.0
        endurance = {
            f"ideal_duration_at_{int(float(fraction)*100)}pct_usable_energy_s":
                3600.0 * float(cfg7["batteryNominalEnergyWh"]) * float(fraction) / (power_kw * 1000.0)
            for fraction in cfg7["usableEnergyFractions"]
        }
        integrated.append(
            {
                "speed_kmh": speed,
                "phase3_system_bus_power_w": float(summary["electrical_power_estimate_w"]),
                "phase3_pack_current_at_10mohm_a": pack_current,
                "pack_current_soft_330a_pass": limits["pack_soft_current"],
                "max_motor_battery_current_no_sag_a": max_battery_channel,
                "motor_soft_55a_pass": limits["motor_soft_battery_current"],
                "max_ideal_kv_phase_current_estimate_a": max_phase_estimate,
                "esc_continuous_60a_estimate_pass": limits["esc_continuous_phase_current_estimate"],
                "max_motor_rpm": max(rpm_values),
                "motor_soft_12500rpm_pass": limits["motor_soft_rpm"],
                "motor_hard_13500rpm_pass": max(rpm_values) <= float(cfg7["motorHardRpm"]),
                "startup_critical_rpm": first_critical,
                "startup_resonance_resolved": limits["startup_resonance_resolved"],
                **endurance,
                "all_screened_gates_pass": not reasons,
                "failed_or_unverified_gates": ";".join(reasons),
                "source_class": "integrated screen using Phase-3 analytical loads, Phase-4 ROSS results, Phase-5 assumptions",
            }
        )

    write_csv(results / "phase6_core_bypass_schedule.csv", core_schedule)
    write_csv(results / "phase6_area_margin_sensitivity.csv", area_margins)
    write_csv(results / "phase7_integrated_speed_envelope.csv", integrated)
    make_report(
        config=config,
        core_rows=core_schedule,
        margins=area_margins,
        integrated=integrated,
        available_annulus=available_annulus,
        min_area=min_area,
        max_area=max_area,
        first_critical=first_critical,
        summary_rows=summary_rows,
    )
    print(
        "Phases 6-7 complete: "
        f"{len(core_schedule)} geometry points, {len(area_margins)} margin cases, "
        f"{len(integrated)} integrated speeds; zero cloud jobs."
    )


def make_report(
    *, config: dict[str, Any], core_rows: list[dict[str, Any]], margins: list[dict[str, Any]],
    integrated: list[dict[str, Any]], available_annulus: float, min_area: float, max_area: float,
    first_critical: float, summary_rows: list[dict[str, str]],
) -> None:
    cp = Path(__file__).resolve().parents[1]
    hash_value = hashlib.sha256((cp / "configs" / "phase6_7_system_closure.json").read_bytes()).hexdigest()
    tight = next(row for row in margins if row["speed_kmh"] == 700 and row["core_flow_area_margin_fraction"] == 0.1)
    core_endpoints = (core_rows[0], core_rows[-1])
    max_power = max(float(row["electrical_power_estimate_w"]) for row in summary_rows)
    text = [
        "# Phases 6–7: variable-area schedule and integrated system closure",
        "",
        "**Scope:** application-specific analytical post-processing of Phase-3 meanline/area sensitivities, Phase-4 ROSS results, and Phase-5 electrical/thermal assumptions. No CFD, physical geometry, native solver job, or GCP job was run. All findings remain screening results.",
        "",
        f"Configuration SHA-256: `{hash_value}`. Cloud spend: **$0.00**.",
        "",
        "## Phase 6 — core-annulus / bypass-area schedule",
        "",
        f"The 80 mm casing / 32 mm hub provides {available_annulus*1e6:.0f} mm² of annulus area. Phase 3 sized the core area to meet the 50,000 stator-Reynolds floor in an ideal continuity model: {min_area*1e6:.0f}→{max_area*1e6:.0f} mm² from 500 to 700 km/h. This corresponds to a {core_endpoints[0]['core_outer_diameter_m']*1000:.1f}→{core_endpoints[1]['core_outer_diameter_m']*1000:.1f} mm core outer diameter, leaving progressively less annulus for bypass flow.",
        "",
        "| Speed | Core OD | Core area / available annulus | Remaining geometric bypass annulus | Axial velocity at Re floor |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in core_rows:
        text.append(
            f"| {row['speed_kmh']} km/h | {row['core_outer_diameter_m']*1000:.1f} mm | {row['core_area_fraction_of_available_annulus']*100:.1f}% | {row['remaining_bypass_area_fraction']*100:.1f}% | {row['axial_velocity_for_re_floor_m_s']:.1f} m/s |"
        )
    text += [
        "",
        f"A 10% core-area margin at 700 km/h requires {tight['required_core_outer_diameter_m']*1000:.1f} mm core OD and leaves only {tight['remaining_bypass_area_fraction']*100:.1f}% of the casing annulus. A 15% margin exceeds available annulus area and cannot coexist with an open bypass path at this hub/casing size. These margins are sensitivity cases, not measured contraction-loss allowances.",
        "",
        "The table describes core/bypass annulus area allocation only. It does not determine nozzle throat areas, pressure matching, bypass flow fraction, actuation forces, stability, or the passive cam/spring geometry. The area schedule is a candidate command curve for follow-on mechanism design, not a validated variable-bypass solution.",
        "",
        "Detailed outputs: `results/phase6_core_bypass_schedule.csv` and `results/phase6_area_margin_sensitivity.csv`.",
        "",
        "## Phase 7 — integrated electrical, speed, and readiness screen",
        "",
        "| Speed | Bus power | Pack current (10 mΩ) | Max motor current/channel | Max ideal-Kv phase-current estimate | Max motor rpm | Ideal energy duration (70–90% of 222 Wh) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in integrated:
        durations = [row[f"ideal_duration_at_{pct}pct_usable_energy_s"] for pct in (70, 80, 90)]
        text.append(
            f"| {row['speed_kmh']} km/h | {row['phase3_system_bus_power_w']/1000:.2f} kW | {row['phase3_pack_current_at_10mohm_a']:.0f} A | {row['max_motor_battery_current_no_sag_a']:.1f} A | {row['max_ideal_kv_phase_current_estimate_a']:.1f} A | {row['max_motor_rpm']:.0f} rpm | {durations[0]:.0f}–{durations[-1]:.0f} s |"
        )
    text += [
        "",
        f"The duration figures are ideal energy ceilings at constant Phase-3 power; they ignore voltage sag/cutoff, thermal derating, reserve, and any mass increase. The current Phase-3 bus demand reaches {max_power/1000:.2f} kW. At the 600 km/h baseline the pack-current estimate is already near the 330 A six-channel soft threshold, while the highest channel exceeds its soft current and the ideal-Kv phase-current estimate exceeds the assumed 60 A RMS continuous ESC limit.",
        "",
        "The ideal-Kv-derived phase-current values are convention-sensitive torque-current estimates, not measured ESC phase RMS currents. Their comparison with the 60 A RMS contract is an early warning screen only; it requires confirmation from the ESC/motor current convention and first-article telemetry.",
        "",
        f"Every sampled speed fails at least one conservative readiness gate. The lowest sampled point, 500 km/h, is the least demanding electrical case but still has a {max(row['max_ideal_kv_phase_current_estimate_a'] for row in integrated if row['speed_kmh']==500):.1f} A ideal-Kv phase-current estimate and an unresolved startup crossing of the approximately {first_critical:.0f} rpm ROSS first critical. At 700 km/h, requested bus power is {max_power/1000:.2f} kW, pack current exceeds the provisional six-channel short-current cap in the 10 mΩ screen, and the Phase-5 cutoff cases terminate before requested burst duration.",
        "",
        "The 75 cm² projected-frontal-area checkpoint remains unverified: it is an assumed requirement checkpoint, not a measured CAD projection. CdA remains a separate Phase-2 analogue input. No user-specified mission duration/range was available, so the table is not a range estimate.",
        "",
        "### Readiness disposition",
        "",
        "- **Not ready for hardware release or flight validation.** No sampled speed clears the combined soft-current, continuous phase-current, motor soft-RPM, startup-resonance, and geometry-verification gates.",
        "- **Dominant closure items:** validate stator Reynolds assumptions and core/bypass split; provide actual CAD frontal area and duct/actuator mass; resolve rotor startup critical crossing; measure battery pack OCV/DCIR/pulse thermal response; dyno-test motor/ESC torque-speed and loss maps; define a mission profile.",
        "- **Cost:** local post-processing only, no cloud spend.",
        "",
        "Detailed speed gates and endurance ceilings: `results/phase7_integrated_speed_envelope.csv`.",
    ]
    (cp / "reports" / "phase6-7-system-closure.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    manifest = {
        "phases": [6, 7],
        "configSha256": hash_value,
        "phase6GeometryPoints": len(core_rows),
        "phase6AreaMarginCases": len(margins),
        "phase7IntegratedSpeeds": len(integrated),
        "combinedGatePassSpeeds": sum(bool(row["all_screened_gates_pass"]) for row in integrated),
        "cloudJobs": [],
        "cloudCostUsd": 0.0,
        "evidenceClass": "application-specific analytical post-processing",
    }
    (cp / "results" / "phase6_7_summary.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
