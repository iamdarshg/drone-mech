#!/usr/bin/env python3
"""Isolated-duct RANS worker (incompressible simpleFoam + kOmegaSST).

Measures internal total-pressure loss / recovery through a parametric diffusing
duct. Scope: INTERNAL duct loss only (geometry-controlled); NOT installed inlet
recovery (which needs external + internal flow).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

HDR = "FoamFile {{ version 2.0; format ascii; class {cls}; location \"{loc}\"; object {obj}; }}\n"


def run(args, cwd, log, timeout=300, env=None):
    start = time.monotonic()
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env, check=False)
        log.write_text((r.stdout or "") + "\n--- STDERR ---\n" + (r.stderr or ""), encoding="utf-8", errors="replace")
        return {"rc": r.returncode, "elapsed": round(time.monotonic() - start, 1)}
    except subprocess.TimeoutExpired:
        log.write_text("TIMEOUT\n", encoding="utf-8")
        return {"rc": None, "elapsed": round(time.monotonic() - start, 1), "timeout": True}
    except OSError as exc:
        log.write_text(f"EXECUTION ERROR: {exc}\n", encoding="utf-8")
        return {"rc": None, "elapsed": round(time.monotonic() - start, 1), "error": str(exc)}


def write_case(case: Path, r_in: float, r_out: float, length: float, mesh: float, uin: float) -> None:
    for d in ("system", "constant", "0"):
        (case / d).mkdir(parents=True, exist_ok=True)

    (case / "duct.geo").write_text(
        'SetFactory("OpenCASCADE");\n'
        f'Cone(1) = {{0,0,0, 0,0,{length}, {r_in}, {r_out}}};\n'
        'Physical Volume("internal") = {1};\n'
        f'eps = 1e-6; rmax = {max(r_in, r_out)};\n'
        'inlet[] = Surface In BoundingBox {-rmax-eps,-rmax-eps,-eps, rmax+eps,rmax+eps,eps};\n'
        f'outlet[] = Surface In BoundingBox {{-rmax-eps,-rmax-eps,{length}-eps, rmax+eps,rmax+eps,{length}+eps}};\n'
        'walls[] = Surface{:};\n'
        'walls[] -= {inlet[], outlet[]};\n'
        'Physical Surface("inlet") = {inlet[]};\n'
        'Physical Surface("walls") = {walls[]};\n'
        'Physical Surface("outlet") = {outlet[]};\n'
        f'Mesh.CharacteristicLengthMax = {mesh};\nMesh.CharacteristicLengthMin = {mesh};\nMesh.Optimize = 1;\n',
        encoding="utf-8")

    (case / "system" / "controlDict").write_text(HDR.format(cls="dictionary", loc="system", obj="controlDict") + f"""
application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         400;
deltaT          1;
writeControl    timeStep;
writeInterval   400;
purgeWrite      0;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
functions
{{
    inletPt {{ type surfaceFieldValue; libs ("libfieldFunctionObjects.so"); fields (p U); operation areaAverage; regionType patch; name inlet; writeFields false; writeToFile true; log false; }}
    outletPt {{ type surfaceFieldValue; libs ("libfieldFunctionObjects.so"); fields (p U); operation areaAverage; regionType patch; name outlet; writeFields false; writeToFile true; log false; }}
}}
""", encoding="utf-8")

    (case / "system" / "fvSchemes").write_text(HDR.format(cls="dictionary", loc="system", obj="fvSchemes") + """
ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; grad(U) cellLimited Gauss linear 1; }
divSchemes
{
    default none;
    div(phi,U)      Gauss linearUpwind grad(U);
    div(phi,k)      Gauss upwind;
    div(phi,omega)  Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
wallDist        { method meshWave; }
fluxRequired    { default no; p; }
""", encoding="utf-8")

    (case / "system" / "fvSolution").write_text(HDR.format(cls="dictionary", loc="system", obj="fvSolution") + """
solvers
{
    p       { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.01; }
    "(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.01; }
}
SIMPLE
{
    momentumPredictor no;
    nOuterCorrectors 1;
    nCorrectors     2;
    nNonOrthogonalCorrectors 1;
    pMinFactor      0.2;
    pMaxFactor      2.0;
}
relaxationFactors
{
    fields { p 0.3; }
    equations { U 0.7; k 0.7; omega 0.7; }
}
""", encoding="utf-8")

    (case / "constant" / "transportProperties").write_text(HDR.format(cls="dictionary", loc="constant", obj="transportProperties") + "transportModel  Newtonian;\nnu              1.5e-05;\n", encoding="utf-8")
    (case / "constant" / "turbulenceProperties").write_text(HDR.format(cls="dictionary", loc="constant", obj="turbulenceProperties") + "simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }\n", encoding="utf-8")

    fields = {
        "p": ("volScalarField [0 2 -2 0 0 0 0]", "uniform 0", "inlet { type zeroGradient; } outlet { type fixedValue; value uniform 0; } walls { type zeroGradient; }"),
        "U": ("volVectorField [0 1 -1 0 0 0 0]", f"uniform (0 0 {uin})", f"inlet {{ type fixedValue; value uniform (0 0 {uin}); }} outlet {{ type inletOutlet; inletValue uniform (0 0 {uin}); value uniform (0 0 {uin}); }} walls {{ type noSlip; }}"),
        "k": ("volScalarField [0 2 -2 0 0 0 0]", "uniform 0.24", "inlet { type fixedValue; value uniform 0.24; } outlet { type inletOutlet; inletValue uniform 0.24; value uniform 0.24; } walls { type zeroGradient; }"),
        "omega": ("volScalarField [0 0 -1 0 0 0 0]", "uniform 100", "inlet { type fixedValue; value uniform 100; } outlet { type inletOutlet; inletValue uniform 100; value uniform 100; } walls { type zeroGradient; }"),
        "nut": ("volScalarField [0 2 -1 0 0 0 0]", "uniform 0", "inlet { type calculated; value uniform 0; } outlet { type calculated; value uniform 0; } walls { type zeroGradient; }"),
    }
    for name, (clsdim, internal, bf) in fields.items():
        cls, dims = clsdim.split(" ", 1)
        (case / "0" / name).write_text(
            HDR.format(cls=cls, loc="0", obj=name) + f"dimensions {dims};\ninternalField {internal};\nboundaryField {{ {bf} }}\n",
            encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--work", default="/opt/phase15/work")
    ap.add_argument("--run-budget-seconds", type=int, default=360)
    ap.add_argument("--mesh", choices=("tetra", "prism"), default="tetra",
                    help="Prism is an experimental layered mesh; all mesh and flow gates still apply")
    args = ap.parse_args()

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    work = Path(args.work); work.mkdir(parents=True, exist_ok=True)
    case = work / "duct"
    if case.exists():
        raise SystemExit(f"Refusing to reuse existing case {case}; choose a fresh --work directory")
    case.mkdir(parents=True)
    logs = out / "logs"; logs.mkdir(exist_ok=True)
    env = dict(os.environ)

    r_in, r_out, length, uin = 0.030, 0.039, 0.120, 178.0
    write_case(case, r_in, r_out, length, 0.005, uin)
    ev = {"case": {"r_in": r_in, "r_out": r_out, "length": length, "u_in": uin, "mesh": args.mesh}, "steps": {}}
    ev["steps"]["gmsh"] = run(["gmsh", "duct.geo", "-3", "-format", "msh2", "-o", "duct.msh"], case, logs / "gmsh.log", 240, env)
    required_steps = ["gmsh", "gmshToFoam", "checkMesh"]
    if args.mesh == "prism":
        prism_script = Path(__file__).resolve().with_name("prism_duct_mesh.py")
        ev["steps"]["prismMesh"] = run([sys.executable, str(prism_script), "duct.msh", "duct_prism.msh",
                                         "--r-in", str(r_in), "--r-out", str(r_out), "--length", str(length)],
                                        case, logs / "prismMesh.log", 120, env)
        required_steps.append("prismMesh")
        if ev["steps"]["prismMesh"]["rc"] == 0:
            (case / "duct_prism.msh").replace(case / "duct.msh")
    ev["steps"]["gmshToFoam"] = run(["gmshToFoam", "duct.msh"], case, logs / "gmshToFoam.log", 180, env)
    ev["steps"]["checkMesh"] = run(["checkMesh", "-allTopology", "-allGeometry"], case, logs / "checkMesh.log", 120, env)
    mesh_log = (logs / "checkMesh.log").read_text(encoding="utf-8", errors="replace")
    if any(ev["steps"][key]["rc"] != 0 for key in required_steps) or "Mesh OK." not in mesh_log:
        res = {"phase": 15, "study": "isolated duct internal-loss RANS (incompressible)",
               "scope": "INTERNAL duct loss only; not installed inlet recovery", "evidence": ev,
               "inletTotalPressure": None, "outletTotalPressure": None, "internalRecovery": None,
               "status": "blocked-mesh"}
        (out / "phase15_inlet_result.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(res, indent=2))
        return
    ev["steps"]["simpleFoam"] = run(["simpleFoam"], case, logs / "solver.log", args.run_budget_seconds, env)

    def last(p: Path):
        if not p.exists():
            return None
        v = []
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                v.append([float(x) for x in re.findall(NUMBER, s)])
        return v[-1] if v else None

    def find(prefix):
        for p in list(case.rglob("surfaceFieldValue.dat")):
            if prefix in str(p.parent).lower():
                return p
        return None

    def pt(vals):
        if not vals or len(vals) < 5:
            return None
        p, ux, uy, uz = vals[1], vals[2], vals[3], vals[4]
        return p + 0.5 * (ux * ux + uy * uy + uz * uz)

    fi, fo = find("inletpt"), find("outletpt")
    pt_in = pt(last(fi)) if fi else None
    pt_out = pt(last(fo)) if fo else None
    rec = (pt_out / pt_in) if (pt_in and pt_out) else None
    solver_ok = ev["steps"]["simpleFoam"]["rc"] == 0
    if not solver_ok:
        pt_in = pt_out = rec = None
    res = {"phase": 15, "study": "isolated duct internal-loss RANS (incompressible)",
           "scope": "INTERNAL duct loss only; not installed inlet recovery",
           "evidence": ev, "inletTotalPressure": pt_in, "outletTotalPressure": pt_out,
           "internalRecovery": round(rec, 5) if rec else None,
           "status": "solver-failed" if not solver_ok else ("diagnostic-unvalidated" if rec else "no-recovery-extracted"),
           "limitations": "Incompressible isolated-duct estimate; boundary conditions, flux balance, convergence, and total-pressure recovery have not been validated."}
    (out / "phase15_inlet_result.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
