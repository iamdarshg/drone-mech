#!/usr/bin/env python3
"""DM-G7 CG / mass / inertia closure from CAD positions.
Spec masses (PHASE15_DESIGN_SPEC section 16, nominal) are distributed over the CAD solids of each row by
volume; rows with no CAD solid are placed at stated proxy locations. Outputs CG (datum: X lateral,
Y vertical, Z aft+, origin at fan plane) vs the spec window, the inertia tensor about the CG (replaces
the spec's 'uniform-body estimate'), the payload position needed to put the CG mid-window, and a physics
check of the structure rows (CAD volume / OML area x density) against the spec row masses.
usage: dm_g7_mass_cg.py <solid_props.json> <oml_wrap_mm.stl> <out.json>"""
import json, re, sys
import numpy as np
props = json.load(open(sys.argv[1])); out = sys.argv[3]
ROWS = [  # (row, nominal kg, min kg, max kg, regex on solid base name)
    ("motors", 1.68, 0.72, 1.68, r"^motor_[AB]_R\d"),
    ("battery", 0.56, 0.45, 0.75, r"^Bonka_6S"),
    ("esc_flight_pcbs", 0.40, 0.30, 0.55, r"^(esc_|flight_control|fc_100|flight_6ch|board_isolator)"),
    ("rotors_hubs_stators", 0.37, 0.30, 0.45, r"^duct_[AB]_(rotor|stator)_"),
    ("duct_inlet_composites", 0.28, 0.20, 0.40, r"^duct_[AB]_(82OD|side_inlet|separate_nozzle|rotor_containment|vector_vane_bearing)"),
    ("lifting_body_shell", 0.27, 0.20, 0.38, r"^(lifting_wing|fuselage_battery_bay_shell|canted_tail_fin|single_right_fin_rudder|elevon_(left|right)_40|wing_center_joiner|twin_carbon_tail)"),
    ("actuators", 0.18, 0.10, 0.30, r"^servo_mount_"),
    ("mounts_clamps_fasteners", 0.25, 0.15, 0.40, r"^(six_hot_side_motor_carrier|battery_service_hatch|battery_sliding_rails|battery_retention|fuselage_internal_bay|elevon_pushrod|duct_[AB]_vector_vane_\d)"),
    ("landing_gear", 0.40, 0.25, 0.60, r"^twin_landing_skids"),
]
PROXY = [  # rows without CAD solids: placed at the volume centroid of a named group (assumption, stated)
    ("harness_connectors_fuses", 0.25, 0.15, 0.40, "esc_flight_pcbs"),
    ("avionics", 0.20, 0.12, 0.30, "esc_flight_pcbs"),
    ("payload", 1.00, 0.80, 1.20, "battery"),
]
assigned = {}; rows = {}; unassigned = []
for s in props:
    hit = [r for r in ROWS if re.search(r[4], s["base"])]
    if not hit: unassigned.append(s["base"]); continue
    rows.setdefault(hit[0][0], []).append(s)
def group_centroid(ss):
    v = np.array([s["volume_mm3"] for s in ss]); c = np.array([s["centroid_mm"] for s in ss]); return (v[:, None] * c).sum(0) / v.sum()
pts = []  # (mass kg, centroid mm, inertia about own centroid kg mm^2, label)
rec = {"rows": {}, "unassigned_solids": sorted(set(unassigned))}
for name, nom, lo, hi, _ in ROWS:
    ss = rows.get(name, []); V = sum(s["volume_mm3"] for s in ss)
    rec["rows"][name] = {"spec_nominal_kg": nom, "cad_solids": len(ss), "cad_volume_cm3": round(V / 1000, 1),
                         "centroid_mm": np.round(group_centroid(ss), 2).tolist() if ss else None}
    for s in ss:
        m = nom * s["volume_mm3"] / V; rho = m / s["volume_mm3"]   # kg/mm^3 within the row
        I = np.array(s["inertia_unit_density_mm5"]).reshape(3, 3) * rho
        pts.append((m, np.array(s["centroid_mm"]), I, name))
for name, nom, lo, hi, at in PROXY:
    c = group_centroid(rows[at]); pts.append((nom, c, np.zeros((3, 3)), name))
    rec["rows"][name] = {"spec_nominal_kg": nom, "cad_solids": 0, "placed_at": f"centroid of {at}", "centroid_mm": np.round(c, 2).tolist()}
def cg_inertia(pts):
    M = sum(p[0] for p in pts); C = sum(p[0] * p[1] for p in pts) / M; I = np.zeros((3, 3))
    for m, c, Io, _ in pts:
        d = c - C; I += Io + m * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    return M, C, I
M, C, I = cg_inertia(pts)
rec["total_mass_kg_excl_reserve"] = round(M, 3)
rec["cg_mm"] = {"x_lateral": round(C[0], 2), "y_vertical": round(C[1], 2), "z_longitudinal": round(C[2], 2)}
rec["spec_window_mm"] = {"z_longitudinal": [-5, 15], "x_lateral": [-3, 3], "y_vertical": [-5, 10]}
rec["cg_in_window"] = {"z": -5 <= C[2] <= 15, "x": -3 <= C[0] <= 3, "y": -5 <= C[1] <= 10}
Ikg = I * 1e-6  # kg m^2
rec["inertia_about_cg_kg_m2"] = {"Ixx_pitch(about X lateral)": round(Ikg[0, 0], 4), "Iyy_yaw(about Y vertical)": round(Ikg[1, 1], 4),
                                 "Izz_roll(about Z)": round(Ikg[2, 2], 4), "Ixy": round(Ikg[0, 1], 5), "Ixz": round(Ikg[0, 2], 5), "Iyz": round(Ikg[1, 2], 5)}
rec["spec_inertia_kg_m2(uniform-body estimate)"] = {"pitch": [0.15, 0.20, 0.25], "yaw": [0.20, 0.25, 0.35], "roll": [0.025, 0.03, 0.08]}
# payload z needed for CG z = 5 mm (mid window), payload on the centreline at the battery-bay height
others = [p for p in pts if p[3] != "payload"]; Mo = sum(p[0] for p in others); Zo = sum(p[0] * p[1][2] for p in others) / Mo
rec["cg_z_without_payload_mm"] = round(Zo, 2)
rec["payload_z_for_cg_5mm"] = round((5 * (Mo + 1.0) - Mo * Zo) / 1.0, 1)
rec["battery_z_shift_for_cg_5mm_with_payload_at_bay"] = round((5 - C[2]) * M / 0.56, 1)
# structure physics check
import trimesh
w = trimesh.load(sys.argv[2]); A = w.area / 1e6  # m^2 (wrap of the whole OML, incl. ducts/tail)
rec["structure_check"] = {"oml_wrap_area_m2": round(A, 4),
    "composite_shell_mass_kg_at_t_0.8_1.2_2.0mm_rho1.5": [round(A * t * 1e-3 * 1500, 3) for t in (0.8, 1.2, 2.0)],
    "lifting_body_cad_volume_cm3": rec["rows"]["lifting_body_shell"]["cad_volume_cm3"],
    "lifting_body_as_PLA_kg_at_infill_10_20_100pct(rho1.24)": [round(rec["rows"]["lifting_body_shell"]["cad_volume_cm3"] * 1.24e-3 * f, 3) for f in (0.10, 0.20, 1.0)],
    "spec_rows_lifting_body_plus_ducts_kg": 0.27 + 0.28}
J = lambda o: o.item() if hasattr(o, "item") else str(o)
json.dump(rec, open(out, "w"), indent=1, default=J); print(json.dumps({k: rec[k] for k in ("total_mass_kg_excl_reserve", "cg_mm", "cg_in_window", "inertia_about_cg_kg_m2", "cg_z_without_payload_mm", "payload_z_for_cg_5mm", "battery_z_shift_for_cg_5mm_with_payload_at_bay", "structure_check", "unassigned_solids")}, indent=1, default=J))
