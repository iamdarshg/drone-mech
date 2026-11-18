#!/usr/bin/env python3
"""DM-G4 post-processing: averaged forces/moments over the last N iterations of each case,
coefficients in wind axes, elevon hinge moments, convergence (std over window, drift between
the two halves of the window), y+ summary. Reference: S=0.19 m^2, c=0.365 m, b=0.52 m (spec
nominal), moments about the datum origin (fan plane, nominal CG). q uses rho_3km * TAS^2/2.
usage: dm_g4_post.py <cases_root> <out.json> [window=300]
Each case dir name: IAS<v>_a<alpha>_L<dL>_R<dR>; needs case.json {U,alpha,rho,Se,ce}."""
import json, math, sys
from pathlib import Path
import numpy as np
root, outp = Path(sys.argv[1]), Path(sys.argv[2]); W = int(sys.argv[3]) if len(sys.argv) > 3 else 300
S, CBAR, B = 0.19, 0.365, 0.52
def load(dat):
    rows = []
    for line in open(dat):
        if line.startswith("#") or not line.strip(): continue
        rows.append([float(v) for v in line.replace("(", " ").replace(")", " ").split()])
    a = np.array(rows); return a[:, 0], a[:, 1:4]   # time, total (x,y,z)
def win(t, v):
    n = min(W, len(t)); x = v[-n:]; h = n // 2
    return x.mean(0), x.std(0), (x[h:].mean(0) - x[:h].mean(0))
res = {"reference": {"S_m2": S, "cbar_m": CBAR, "b_m": B, "moment_ref": "datum origin (0,0,0)", "window_iters": W}, "cases": {}}
for c in sorted(p for p in root.iterdir() if (p / "case.json").exists()):
    meta = json.load(open(c / "case.json")); U, a, rho = meta["U"], math.radians(meta["alpha"]), meta["rho"]
    q = 0.5 * rho * U * U
    lift = np.array([0, math.cos(a), -math.sin(a)]); drag = np.array([0, math.sin(a), math.cos(a)])
    r = {"q_Pa": round(q, 2), "alpha_deg": meta["alpha"], "dL": meta["dL"], "dR": meta["dR"]}
    try:
        t, F = load(next((c / "postProcessing/forcesAll").glob("*/force.dat")))
        _, M = load(next((c / "postProcessing/forcesAll").glob("*/moment.dat")))
    except StopIteration:
        r["error"] = "no force output"; res["cases"][c.name] = r; continue
    Fm, Fs, Fd = win(t, F); Mm, Ms, Md = win(t, M)
    r["iterations"] = int(t[-1])
    r["CL"] = round(float(Fm @ lift) / (q * S), 4); r["CD"] = round(float(Fm @ drag) / (q * S), 5)
    r["Cm_pitch_about_x"] = round(float(Mm[0]) / (q * S * CBAR), 5)   # +x moment: nose-up for flow along +z? sign noted in report
    r["Cl_roll_about_z"] = round(float(Mm[2]) / (q * S * B), 5)
    r["Cn_yaw_about_y"] = round(float(Mm[1]) / (q * S * B), 5)
    r["CY_side_x"] = round(float(Fm[0]) / (q * S), 5)
    r["conv"] = {"CL_std": round(float(Fs @ np.abs(lift)) / (q * S), 5), "CL_halfdrift": round(float(Fd @ lift) / (q * S), 5),
                 "Cm_std": round(float(Ms[0]) / (q * S * CBAR), 5), "Cm_halfdrift": round(float(Md[0]) / (q * S * CBAR), 5)}
    for s in "LR":
        try:
            _, H = load(next((c / f"postProcessing/hinge{s}").glob("*/moment.dat")))
            Hm, Hs, Hd = win(t, H)
            r[f"hinge_{s}_Nm"] = round(float(Hm[0]), 5); r[f"hinge_{s}_std_Nm"] = round(float(Hs[0]), 5)
            r[f"Ch_{s}"] = round(float(Hm[0]) / (q * meta["Se"] * meta["ce"]), 4)
        except StopIteration:
            r[f"hinge_{s}_Nm"] = None
    lg = c / "log.simpleFoam"
    if lg.exists():
        txt = lg.read_text(errors="ignore"); r["converged_residualControl"] = "SIMPLE solution converged" in txt
        r["fatal"] = "FOAM FATAL" in txt
    res["cases"][c.name] = r; print(c.name, json.dumps(r))
outp.write_text(json.dumps(res, indent=1) + "\n")
