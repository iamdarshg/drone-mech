#!/usr/bin/env python3
"""Source-pinned analytical hinge-torque sensitivity screen; not an aero qualification."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PHASE = ROOT / "highspeed_edf" / "phase15"
PINS = PHASE / "servo_screen" / "source_pins.json"
OUT = PHASE / "servo_screen"
COEFFICIENTS = (0.01, 0.05, 0.10, 0.20)  # illustrative sensitivity values, never inferred from geometry
VECTOR_VELOCITY_RATIOS = (1.0, 2.0, 4.0)  # local-vane / aircraft freestream; jet state is unknown
P0_PA = 101325.0
T0_K = 288.15
ISA_LAPSE_K_M = 0.0065
G0_M_S2 = 9.80665
GAMMA_AIR = 1.4
R_AIR = 287.05
KGF_CM_NM = 0.0980665


def check_pins() -> dict:
    pins = json.loads(PINS.read_text())
    for source in pins["sources"]:
        path = ROOT / source["path"]
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if sha != source["sha256"]:
            raise ValueError(f"Source SHA-256 drift: {source['path']} expected {source['sha256']} got {sha}")
        if git_blob(raw) != source["git_blob"]:
            raise ValueError(f"Git blob drift: {source['path']}")
    return pins


def git_blob(raw: bytes) -> str:
    import hashlib as _hashlib
    return _hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def geometry_constants(source_path: Path) -> dict:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    wanted = {"ELEVON_SPAN", "ELEVON_CHORD", "FIN_HEIGHT", "FIN_CHORD", "VANE_SIZE", "VANE_RING_RADIUS", "SERVO_ENVELOPE", "SERVO_MASS_KG"}
    values: dict = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            key = node.targets[0].id
            if key in wanted:
                values[key] = ast.literal_eval(node.value)
    missing = wanted - values.keys()
    if missing:
        raise ValueError(f"Missing geometry constants: {sorted(missing)}")
    return values


def hinge_torque(q_pa: float, area_m2: float, reference_chord_m: float, coefficient: float) -> float:
    """Absolute hinge-axis torque magnitude from Ch = H/(q*S*c)."""
    if q_pa < 0 or area_m2 <= 0 or reference_chord_m <= 0 or coefficient < 0:
        raise ValueError("q, area, reference chord, and coefficient must be nonnegative; geometry must be positive")
    return q_pa * area_m2 * reference_chord_m * coefficient


def load_inputs(pins: dict) -> tuple[dict, list[int], list[int], dict]:
    src = {item["role"]: ROOT / item["path"] for item in pins["sources"]}
    g = geometry_constants(src["geometry"])
    control_config = json.loads(src["control_contract"].read_text(encoding="utf-8"))
    with (src["speed_envelope"]).open(newline="", encoding="utf-8") as handle:
        anchors = sorted({int(float(row["speed_kmh"])) for row in csv.DictReader(handle) if float(row["speed_kmh"]) > 0})
    speeds = sorted(set(range(50, 901, 50)) | set(anchors))
    return g, speeds, [int(x) for x in anchors], control_config


def isa_atmosphere(altitude_m: float) -> tuple[float, float, float]:
    """Return (temperature K, static pressure Pa, density kg/m3) in ISA troposphere."""
    temperature = T0_K - ISA_LAPSE_K_M * altitude_m
    pressure = P0_PA * (temperature / T0_K) ** (G0_M_S2 / (R_AIR * ISA_LAPSE_K_M))
    density = pressure / (R_AIR * temperature)
    return temperature, pressure, density


def cas_to_mach(ias_m_s: float, static_pressure_pa: float) -> float:
    """CAS≈IAS: convert sea-level calibrated impact pressure to Mach at ambient static pressure."""
    sea_level_sound = math.sqrt(GAMMA_AIR * R_AIR * T0_K)
    sea_level_mach = ias_m_s / sea_level_sound
    impact_pressure = P0_PA * ((1.0 + 0.2 * sea_level_mach ** 2) ** 3.5 - 1.0)
    mach = math.sqrt(5.0 * ((1.0 + impact_pressure / static_pressure_pa) ** (2.0 / 7.0) - 1.0))
    if mach >= 1.0:
        raise ValueError("This screen uses the subsonic pitot relation; input exceeds its supported Mach range")
    return mach


def surface_definitions(g: dict) -> list[dict]:
    elevon_area = g["ELEVON_SPAN"] / 1000 * g["ELEVON_CHORD"] / 1000
    rudder_area = (g["FIN_HEIGHT"] - 1.0) / 1000 * (g["FIN_CHORD"] * 0.30) / 1000
    vane_area = g["VANE_SIZE"][0] / 1000 * g["VANE_SIZE"][1] / 1000
    return [
        {"id": f"elevon_{side}", "kind": "elevon", "area_m2": elevon_area,
         "reference_chord_m": g["ELEVON_CHORD"] / 1000, "velocity_ratio": 1.0,
         "count": 1, "geometry_basis": "CAD ELEVON_SPAN × ELEVON_CHORD; rectangle envelope"}
        for side in ("left", "right")
    ] + [{"id": "rudder_right", "kind": "rudder", "area_m2": rudder_area,
          "reference_chord_m": g["FIN_CHORD"] * 0.30 / 1000, "velocity_ratio": 1.0,
          "count": 1, "geometry_basis": "CAD rudder relief rectangle (FIN_HEIGHT−1) × 0.30 FIN_CHORD"}] + [
        {"id": f"vector_vane_{name}", "kind": "vector_vane", "area_m2": vane_area,
         "reference_chord_m": g["VANE_SIZE"][0] / 1000, "velocity_ratio": ratio,
         "count": 1, "geometry_basis": "CAD vane rectangle; chord set to 30 mm blade dimension"}
        for name in ("A1", "A2", "B1", "B2") for ratio in VECTOR_VELOCITY_RATIOS
    ]


def generate() -> tuple[list[dict], dict]:
    pins = check_pins()
    g, speeds, anchors, control_config = load_inputs(pins)
    design_altitude = float(control_config["airframe"]["designAltitudeM"])
    reserve_factor = float(control_config["control"]["strongMinimumReserveRatio"])
    surfaces = surface_definitions(g)
    rows = []
    environments = (("sea_level", 0.0), ("primary_design_altitude", design_altitude))
    atmosphere = {name: isa_atmosphere(alt) for name, alt in environments}
    for speed in speeds:
        ias = speed / 3.6
        for environment, altitude in environments:
            temperature, pressure, density = atmosphere[environment]
            mach = cas_to_mach(ias, pressure)
            tas = mach * math.sqrt(GAMMA_AIR * R_AIR * temperature)
            q = 0.5 * GAMMA_AIR * pressure * mach ** 2
            for surface in surfaces:
                local_q = q * surface["velocity_ratio"] ** 2
                for ch in COEFFICIENTS:
                    torque = hinge_torque(local_q, surface["area_m2"], surface["reference_chord_m"], ch)
                    rows.append({
                    "indicated_airspeed_kmh": speed, "phase14_anchor_ias": speed in anchors,
                    "environment": environment, "altitude_m": altitude,
                    "static_pressure_pa": pressure, "temperature_k": temperature, "density_kg_m3": density,
                    "tas_m_s": tas, "freestream_mach": mach, "freestream_q_pa": q,
                    "surface": surface["id"], "surface_kind": surface["kind"],
                    "area_m2": surface["area_m2"], "reference_chord_m": surface["reference_chord_m"],
                    "local_velocity_ratio": surface["velocity_ratio"], "local_q_pa": local_q,
                    "hinge_coefficient_scenario": ch,
                    "hinge_torque_nm": torque,
                    "hinge_torque_kgf_cm": torque / KGF_CM_NM,
                    "screen_required_torque_nm_at_control_reserve": torque * reserve_factor,
                    "screen_required_torque_kgf_cm_at_control_reserve": torque * reserve_factor / KGF_CM_NM,
                    "source_geometry_basis": surface["geometry_basis"],
                    "interpretation": "illustrative |Ch| scenario, not measured/predicted coefficient; absolute hinge-axis torque only"
                    })
    summary = {
        "status": "ANALYTICAL SENSITIVITY ONLY — NOT A SERVO ADEQUACY OR FLIGHT-SAFETY DETERMINATION",
        "source_commit": pins["source_commit"],
        "source_pins": pins["sources"],
        "indicated_speeds_kmh": speeds,
        "phase14_anchor_ias_kmh": anchors,
        "airspeed_convention": "Requested speed is treated as indicated airspeed (IAS); CAS≈IAS is an explicit ideal instrument/calibration assumption.",
        "pitot_conversion": "Subsonic compressible impact-pressure relation: compute sea-level calibrated qc from IAS, then solve qc/p=(1+0.2M²)^3.5−1 at ambient static pressure.",
        "dynamic_pressure": "q=0.5*gamma*p*M^2; TAS=M*sqrt(gamma*R*T). No incompressible rho*V^2/2 approximation is used for q.",
        "environments": {name: {"altitude_m": alt, "temperature_k": atmosphere[name][0], "static_pressure_pa": atmosphere[name][1], "density_kg_m3": atmosphere[name][2]} for name, alt in environments},
        "mach_note": "Freestream Mach follows compressible IAS-to-Mach conversion. Ch variation with Mach is still unknown and not modeled.",
        "coefficient_scenarios": list(COEFFICIENTS),
        "coefficient_warning": "Analyst-selected sensitivity values only. No Ch is asserted or inferred. Replace with measured/validated CFD hinge coefficients over deflection, Mach, Reynolds number and installation flow.",
        "vector_vane_velocity_ratio_scenarios": list(VECTOR_VELOCITY_RATIOS),
        "reserve_factor": reserve_factor,
        "reserve_basis": "Phase-14 strong control-authority band minimum reserve ratio; applied as a screening factor, not a servo design standard.",
        "actual_servo_comparison": "BLOCKED: design sources specify generic 23x12x29 mm / 25 g servo envelopes only; no make/model, rated output torque at supply voltage, voltage/current/thermal duty, speed, or verified linkage ratio is selected.",
        "servo_placeholder_envelope_mm": g["SERVO_ENVELOPE"],
        "servo_placeholder_mass_kg": g["SERVO_MASS_KG"],
        "actuator_count": 7,
        "known_interface_gate": "Phase-14 control contract listed 6 channels; Phase-15 CAD has 4 vanes + 2 elevons + 1 rudder = 7 actuator positions; seventh channel unresolved.",
        "surface_geometry_caveats": [
            "Areas/chords are planform-envelope measurements from CAD parameters, not aerodynamic effective areas.",
            "Elevon includes taper/sweep in CAD; rectangular area envelope is used; mean aerodynamic chord and hinge line integration are not extracted.",
            "Rudder is a simplified rectangular CAD plate; actual canted/hinged aero and gaps are not modeled.",
            "Vector vane q scenarios use the same freestream density for every velocity-ratio case and scale only velocity by ratios 1, 2, 4 (thus q by 1, 4, 16); this is a hypothetical sensitivity, not jet-flow physics or a prediction of exit density/velocity. At zero freestream speed this method cannot represent powered static jet load.",
            "Torque values are at hinge axis; servo-shaft demand requires actual horn/linkage kinematics, friction, stiffness, backlash, and load sharing, which are not specified.",
            "No dynamic rate/inertia, hinge moment variation with deflection, aeroelastic effects, transient gusts, control loads, or actuator thermal derating are included."
        ],
        "rows": len(rows)
    }
    return rows, summary


def write_outputs() -> None:
    rows, summary = generate()
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "servo_hinge_torque_sensitivity.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    (OUT / "servo_hinge_torque_sensitivity.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase-15 servo torque feasibility screen",
        "",
        "**Result: servo adequacy is undetermined.** The source design contains no selected servo product or rated torque. The CAD's 23×12×29 mm, 25 g item is an analyst envelope placeholder, not a servo datasheet. There is consequently no valid actual-servo margin comparison and no manufacturer torque sheet to cite for a selected unit.",
        "",
        "The input speeds are indicated airspeeds (IAS), per the clarified design convention; this executable explicitly assumes CAS≈IAS with ideal instrument calibration. It computes hinge-axis torque sensitivities at all Phase-14 speed anchors and every 50 km/h from 50 through 900 km/h for both sea level and the primary altitude from the pinned Phase-14 airframe configuration. A subsonic compressible pitot relation converts IAS to Mach and TAS at each pressure altitude, and dynamic pressure is computed as `q = 0.5 γ p M²`. The 3,000 m density is derived from the ISA atmosphere and is close to the pinned Phase-14 0.90913 kg/m³ input. It evaluates `H = q S c Ch` at |Ch| = 0.01, 0.05, 0.10, and 0.20. These are illustrative analyst-selected sensitivity values, not literature-derived bounds, not measured coefficients, and not predictions. The 1.5 multiplier is borrowed from the Phase-14 strong control-authority reserve requirement as a display-only demand reserve; it is not a servo design standard.",
        "",
        "Elevons and rudder use freestream dynamic pressure. For each vector vane, the output includes local-vane/freestream velocity ratios of 1, 2, and 4, so vane dynamic pressure scales by 1, 4, and 16 while retaining the same freestream density. This velocity-only adjustment is a hypothetical sensitivity, not jet-flow physics: actual jet velocity, density, swirl, pressure, and vane incidence are unknown. Powered static vane loading is not represented by freestream scaling. Outputs are absolute hinge-axis torques; converting these to required servo output torque needs linkage ratios and losses that are absent from the design.",
        "",
        "## Example envelope results",
        "",
        "At |Ch|=0.20 and the Phase-14 1.5 reserve, primary-altitude hinge-axis torque demand rises from 50 to 900 km/h IAS. Vector vane is shown at local-velocity ratio 1; actual jet scenario can be higher or lower.",
        "",
        "| Surface | 50 IAS, primary altitude (kgf·cm) | 900 IAS, primary altitude (kgf·cm) | 900 IAS, sea level (kgf·cm) |",
        "|---|---:|---:|---:|"
    ]
    for name in ("elevon_left", "elevon_right", "rudder_right", "vector_vane_A1", "vector_vane_A2", "vector_vane_B1", "vector_vane_B2"):
        lo = next(r for r in rows if r["surface"] == name and r["indicated_airspeed_kmh"] == 50 and r["environment"] == "primary_design_altitude" and r["hinge_coefficient_scenario"] == 0.2 and r["local_velocity_ratio"] == 1.0)
        hi = next(r for r in rows if r["surface"] == name and r["indicated_airspeed_kmh"] == 900 and r["environment"] == "primary_design_altitude" and r["hinge_coefficient_scenario"] == 0.2 and r["local_velocity_ratio"] == 1.0)
        sea = next(r for r in rows if r["surface"] == name and r["indicated_airspeed_kmh"] == 900 and r["environment"] == "sea_level" and r["hinge_coefficient_scenario"] == 0.2 and r["local_velocity_ratio"] == 1.0)
        lines.append(f"| {name} | {lo['screen_required_torque_kgf_cm_at_control_reserve']:.3f} | {hi['screen_required_torque_kgf_cm_at_control_reserve']:.3f} | {sea['screen_required_torque_kgf_cm_at_control_reserve']:.3f} |")
    lines += [
        "",
        "These values are not pass/fail points: coefficient sensitivity dominates the range, local vane flow is unknown, and no servo rating or linkage ratio exists. The pitot conversion accounts for compressibility in the IAS-to-Mach and q conversion, but compressibility-dependent hinge coefficients are not modeled. CAS≈IAS itself is only an ideal calibration assumption; real instrument position error and installation corrections are absent. At 900 km/h IAS, the conversion gives Mach 0.862 and TAS about 1,019 km/h at 3,000 m, versus Mach 0.735 at sea level. The requested maximum remains subsonic, but compressibility is material.",
        "",
        "## Reproduction and source limits",
        "",
        "Run `python highspeed_edf/phase15/optimization/phase15_servo_torque_screen.py`. The script validates SHA-256 and Git blob pins before reading the CAD constants and Phase-14 speed anchors; `source_pins.json` records exact revision/blob IDs and source URLs. Full rows and assumptions are in the adjacent CSV and JSON.",
        "",
        "No external servo manufacturer source applies because no actuator make/model was selected. No hinge coefficient is imported from a generic airfoil report: the whole coefficient range is exposed as a parameter sensitivity. The standard-atmosphere and pitot equations are conventional analytical relations; NASA context URLs, source input values, and exact local design inputs are recorded in `source_pins.json`.",
        "",
        "**Not a qualification:** this analytical screen does not validate control authority, aeroelastic stability, structural strength, actuator response, wiring/power, failure modes, or flight safety. The seven actuator positions versus six allocated channels is an independent unresolved control-interface issue."
    ]
    (OUT / "servo_torque_feasibility_screen.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate pins and print row count without writing outputs")
    args = parser.parse_args()
    if args.check:
        rows, summary = generate()
        print(f"OK: {summary['rows']} sensitivity rows; {len(summary['indicated_speeds_kmh'])} speeds; servo rating comparison {summary['actual_servo_comparison'].split(':')[0]}")
    else:
        write_outputs()
