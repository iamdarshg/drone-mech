#!/usr/bin/env python3
"""DM-G4 derived quantities from dm_g4_post.py output.
 alpha sweep (elevons 0): CL_alpha, Cm_alpha (per deg, least squares), CL0, Cm0, neutral-point estimate
   x_np - x_ref = -Cm_alpha/CL_alpha * cbar (along +z aft, relative to the datum origin);
 symmetric elevon (+/-10, alpha 0): Cm_delta, CL_delta per deg, pitch moment per 10 deg in N m;
 differential (L+10/R-10): Cl_roll and roll moment in N m; hinge moments and Ch_delta, Ch_alpha.
Comparison with the spec control budget (PHASE15_CONTROL_SURFACES section 2: elevon moment 0.1 N m at
45 km/h, 0.4 N m at 90 km/h) and servo torque 0.3-0.8-2.0 N m.
usage: dm_g4_derivatives.py <post.json> <out.json>"""
import json, sys
import numpy as np
P = json.load(open(sys.argv[1]))["cases"]; S, C, B = 0.19, 0.365, 0.52; out = {}
def get(ias, a, v):
    return P.get(f"IAS{ias}_a{a}_{v}")
for ias in (50, 60):
    pts = [(c["alpha_deg"], c["CL"], c["Cm_pitch_about_x"], c["CD"]) for k, c in P.items()
           if k.startswith(f"IAS{ias}_") and k.endswith("_d0") and "CL" in c]
    if len(pts) >= 2:
        a, cl, cm, cd = map(np.array, zip(*sorted(pts)))
        lin = np.abs(a) <= 8
        pa = np.polyfit(a[lin], cl[lin], 1); pm = np.polyfit(a[lin], cm[lin], 1)
        out[f"IAS{ias}"] = {"alphas": a.tolist(), "CL": cl.tolist(), "CD": cd.tolist(), "Cm": cm.tolist(),
            "CL_alpha_per_deg": round(pa[0], 5), "CL0": round(pa[1], 4), "Cm_alpha_per_deg": round(pm[0], 6), "Cm0": round(pm[1], 5),
            "static_margin_note": "Cm_alpha<0 => statically stable about the datum origin",
            "neutral_point_aft_of_datum_mm": round(-pm[0] / pa[0] * C * 1000, 1) if pa[0] else None,
            "L_over_D_max": round(float(np.max(cl / cd)), 2)}
    up, dn, d0 = get(ias, 0, "s+10"), get(ias, 0, "s-10"), get(ias, 0, "d0")
    if up and dn and "CL" in up and "CL" in dn:
        q = up["q_Pa"]; cmd = (up["Cm_pitch_about_x"] - dn["Cm_pitch_about_x"]) / 20; cld = (up["CL"] - dn["CL"]) / 20
        chd = ((up["Ch_L"] + up["Ch_R"]) / 2 - (dn["Ch_L"] + dn["Ch_R"]) / 2) / 20
        out.setdefault(f"IAS{ias}", {}).update({"Cm_delta_per_deg": round(cmd, 6), "CL_delta_per_deg": round(cld, 6),
            "pitch_moment_per_10deg_both_elevons_Nm": round(cmd * 10 * q * S * C, 4),
            "Ch_delta_per_deg": round(chd, 5),
            "hinge_moment_at_+10_Nm": [up["hinge_L_Nm"], up["hinge_R_Nm"]], "hinge_moment_at_-10_Nm": [dn["hinge_L_Nm"], dn["hinge_R_Nm"]],
            "q_Pa": q})
    df = get(ias, 0, "diff")
    if df and "CL" in df:
        q = df["q_Pa"]
        out.setdefault(f"IAS{ias}", {}).update({"Cl_roll_diff10": df["Cl_roll_about_z"], "roll_moment_diff10_Nm": round(df["Cl_roll_about_z"] * q * S * B, 4),
            "roll_sign_note": "moment about +z (aft); +Mz = right wing up = roll LEFT"})
    s20 = get(ias, 0, "s+20")
    if s20 and up and d0 and "CL" in s20:
        out.setdefault(f"IAS{ias}", {}).update({"Cm_at_0_10_20deg": [d0["Cm_pitch_about_x"], up["Cm_pitch_about_x"], s20["Cm_pitch_about_x"]],
            "hinge_at_20_Nm": [s20["hinge_L_Nm"], s20["hinge_R_Nm"]]})
out["spec_control_budget"] = {"elevon_moment_Nm": {"45 km/h": 0.1, "90 km/h": 0.4}, "servo_torque_Nm": [0.3, 0.8, 2.0],
                              "hinge_moment_at_720_Nm": [0.05, 0.20, 0.45]}
json.dump(out, open(sys.argv[2], "w"), indent=1); print(json.dumps(out, indent=1))
