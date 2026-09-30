"""High-time-cost benchmark: strongly coupled generative airframe + EDF design.

Consumes the low-cost benchmark handoff, then drives the aero-multiphysics
workbench coupled optimizer (`aeroworkbench_vehicle_systems.coupled_optimizer`)
to generate a coupled lofted body + EDF design around the selected fixed motor
and battery. It then derives a fabrication package: what to print, how much
carbon-fibre fabric to buy, expected mass, flight regime, and performance.

Run it in the workbench environment, for example:

    uv run --no-sync --directory D:\\CodeProjects\\aero-multiphysics-workbench\\services\\api \
      python D:\\CodeProjects\\drone-mech\\highspeed_edf\\phase15\\optimization\\phase15_high_cost_generative.py

Every number is an analytical/generative screening result. Native CFD/FEA is
not run.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


PHASE = Path(__file__).resolve().parents[1]
RESULTS = PHASE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
HANDOFF = RESULTS / "phase15_low_cost_handoff.json"

PAYLOAD_KG = 1.0
DESIGN_MASS_KG = 7.0  # 6 motors + battery + airframe + 1 kg payload, from the low-cost screen
CRUISE_ALTITUDE_M = 3000.0
RHO_3KM = 0.909128


def import_workbench():
    from aeroworkbench_vehicle_systems import coupled_optimizer as co  # type: ignore

    return co


def build_request(co):
    profiles = (
        co.ManufacturingProfile(profile_id="bar_16x50", width_mm=16.0, height_mm=50.0, material="6061-T6", process="cnc"),
        co.ManufacturingProfile(profile_id="sheet_5x250x120", width_mm=5.0, height_mm=120.0, material="6061-T6", process="cnc"),
        co.ManufacturingProfile(profile_id="sheet_5x300x120", width_mm=5.0, height_mm=120.0, material="6061-T6", process="cnc"),
    )
    initial = co.CoupledDesign(
        fuselage_width_m=0.085,
        fuselage_height_m=0.070,
        inlet_diameter_m=0.080,
        blade_chord_m=0.016,
        blade_pitch_deg=28.0,
        body_length_m=0.55,
        body_superellipse_exponent=2.6,
        lifting_body_planform_area_m2=0.19,
        lifting_body_span_m=0.52,
        lifting_body_taper_ratio=0.25,
        lifting_body_thickness_ratio=0.10,
        lifting_body_sweep_deg=38.0,
        propulsor_hub_ratio=0.50,
        blade_count=12.0,
        stator_count=21.0,
        blade_root_fillet_m=0.002,
        rotor_axial_spacing_m=0.036,
    )
    motor = co.MotorInput(
        voltage_v=44.4,
        current_limit_a=65.0,
        operating_current_a=43.0,
        rpm_limit=45000.0,
        operating_rpm=36000.0,
        efficiency=0.92,
    )
    battery = co.BatteryInput(voltage_v=44.4, current_limit_a=330.0)
    request = co.CoupledOptimizationRequest(
        initial=initial,
        motor=motor,
        battery=battery,
        aircraft_mass_kg=DESIGN_MASS_KG,
        wing_area_m2=0.19,
        air_density_kg_m3=RHO_3KM,
        airframe_family="lifting_body",
        body_role="lifting_body",
        propulsion_adapter="ideal_edf",
        propulsion_family="edf",
        propulsor_placement="tractor",
        propulsor_ducted=True,
        propulsor_stator=True,
        target_speed_kmh=720.0,
        required_speed_kmh=650.0,
        minimum_thrust_to_weight=1.0,
        maximum_tip_mach=0.80,
        manufacturing_profiles=profiles,
        preferred_stock_profile="bar_16x50",
        variable_bounds={
            "fuselage_width_m": (0.075, 0.11),
            "fuselage_height_m": (0.060, 0.10),
            "inlet_diameter_m": (0.070, 0.092),
            "blade_chord_m": (0.012, 0.020),
            "blade_pitch_deg": (18.0, 40.0),
            "body_length_m": (0.40, 0.75),
            "lifting_body_planform_area_m2": (0.13, 0.30),
            "lifting_body_sweep_deg": (20.0, 55.0),
            "propulsor_hub_ratio": (0.40, 0.60),
        },
        discrete_values={"blade_count": (10.0, 11.0, 12.0, 13.0), "stator_count": (17.0, 19.0, 21.0, 23.0)},
        max_iterations=60,
    )
    return request, initial


def fabrication_package(design, evaluation) -> dict:
    body_area = math.pi * 0.5 * (design.fuselage_width_m + design.fuselage_height_m) * design.body_length_m
    lifting_area = 2.0 * design.lifting_body_planform_area_m2
    duct_area = 2.0 * math.pi * design.inlet_diameter_m * 0.110
    shell_area = body_area + lifting_area + duct_area
    cf_area_m2 = shell_area
    glass_area_m2 = shell_area
    # 200 gsm CF + 100 gsm glass per face, resin:fibre 0.8.
    cf_fabric_kg = cf_area_m2 * 0.200 * 1.8
    glass_fabric_kg = glass_area_m2 * 0.100 * 1.8
    core_volume_l = shell_area * 0.0012 * 1000.0
    return {
        "printedParts": [
            "lifting-body / fuselage shell master (PLA core, then CF-wrapped)",
            "2x EDF duct casing shells",
            "4x inlet transition branch shells",
            "inlet fairing / auxiliary-inlet door frames (2 per EDF)",
            "control-vane brackets and servo mounts (6 effectors)",
            "ESC / flight-board tray and heat-spreader mounts",
            "battery retention cradles",
            "landing-gear/skid mounts",
        ],
        "printedPlaVolumeLitresEstimate": round(core_volume_l, 3),
        "outerShellAreaM2": round(shell_area, 3),
        "carbonFibreFabricM2ToBuy": round(cf_area_m2 * 1.25, 3),
        "glassFabricM2ToBuy": round(glass_area_m2 * 1.25, 3),
        "carbonFibreFabricKgEstimate": round(cf_fabric_kg, 3),
        "glassFabricKgEstimate": round(glass_fabric_kg, 3),
        "note": "1.25x cut allowance; 200gsm CF + 100gsm glass per face, resin:fibre 0.8; coupons and weighing still required",
    }


def main() -> None:
    co = import_workbench()
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8")) if HANDOFF.exists() else {}
    request, initial = build_request(co)
    result = co.optimize_airframe_edf(request)
    chosen = result.design or initial
    evaluation = result.evaluation or co.evaluate_coupled_design(request, chosen)
    package = fabrication_package(chosen, evaluation)
    report = {
        "phase": 15,
        "benchmark": "high_time_cost",
        "lowCostHandoff": handoff.get("bestCombo") or handoff.get("bestAvailableIfGatesIgnored"),
        "optimizerStatus": result.status,
        "feasible": result.feasible,
        "converged": result.converged,
        "evaluations": result.evaluations,
        "detail": result.detail,
        "payloadKg": PAYLOAD_KG,
        "coupledDesign": {
            "fuselageWidthM": chosen.fuselage_width_m,
            "fuselageHeightM": chosen.fuselage_height_m,
            "inletDiameterM": chosen.inlet_diameter_m,
            "hubRatio": chosen.propulsor_hub_ratio,
            "bladeCount": chosen.blade_count,
            "statorCount": chosen.stator_count,
            "bladeChordM": chosen.blade_chord_m,
            "bladePitchDeg": chosen.blade_pitch_deg,
            "bodyLengthM": chosen.body_length_m,
            "liftingBodyPlanformAreaM2": chosen.lifting_body_planform_area_m2,
            "liftingBodySweepDeg": chosen.lifting_body_sweep_deg,
        },
        "evaluation": {
            "frontalAreaM2": round(getattr(evaluation, "frontal_area_m2", float("nan")), 5),
            "thrustToWeight": round(getattr(evaluation, "thrust_to_weight", float("nan")), 3),
            "tipMach": round(getattr(evaluation, "propulsor_tip_mach", float("nan")), 3),
            "fidelity": getattr(evaluation, "fidelity", None),
            "gates": dict(getattr(evaluation, "gates", {}) or {}),
            "gateMargins": {k: round(v, 4) for k, v in dict(getattr(evaluation, "gate_margins", {}) or {}).items()},
        },
        "fabrication": package,
        "flightRegime": {
            "cruiseSpeedKmh": 650.0,
            "designSpeedKmh": 720.0,
            "cruiseAltitudeM": CRUISE_ALTITUDE_M,
            "lowSpeedControlToKmh": 180.0,
            "note": "screening regime only; no native CFD/FEA and no measured map",
        },
        "newCloudSpendUsd": 0,
    }
    (RESULTS / "phase15_high_cost_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
