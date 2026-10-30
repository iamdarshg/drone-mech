#!/usr/bin/env python3
"""Regenerate the two fixed-wing rhoPimpleFoam inputs from the tracked source case."""
import argparse, hashlib, json, math, os, re, shutil, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SOURCE = REPO / "highspeed_edf/phase15/fsi/cases/wing_t30mm/fluid"
STEP = REPO / "highspeed_edf/phase15/fsi/cases/wing_t30mm/solid/wing.step"

def replace_patch(text, patch, body):
    return re.sub(r"(" + patch + r"\s*\{).*?(\})", lambda m: m.group(1) + " " + body + " " + m.group(2), text, flags=re.S)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True, help="new directory for generated cases and mesh logs")
    ap.add_argument("--openfoam-root", default=os.environ.get("OPENFOAM_ROOT"), help="root where Debian packages were extracted; expects usr/bin and usr/lib")
    args = ap.parse_args()
    if not args.openfoam_root:
        ap.error("set OPENFOAM_ROOT or pass --openfoam-root")
    foam = Path(args.openfoam_root).resolve()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update({"WM_PROJECT_DIR": str(foam / "usr/share/openfoam"), "FOAM_LIBBIN": str(foam / "usr/lib"), "FOAM_APPBIN": str(foam / "usr/bin")})
    env["LD_LIBRARY_PATH"] = str(foam / "usr/lib") + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    logs = out / "logs"; logs.mkdir()
    for kmh in (700, 900):
        p0, p, t0, t, R, gamma = 101325.0, 70108.0, 288.15, 268.65, 287.05, 1.4
        cas = kmh / 3.6
        mcas = cas / math.sqrt(gamma * R * t0)
        qc = p0 * ((1 + (gamma - 1) / 2 * mcas**2) ** (gamma / (gamma - 1)) - 1)
        mach = math.sqrt(2 / (gamma - 1) * ((1 + qc / p) ** ((gamma - 1) / gamma) - 1))
        tas = mach * math.sqrt(gamma * R * t)
        case = out / f"ias{kmh}"
        shutil.copytree(SOURCE, case)
        with (logs / f"gmshToFoam_ias{kmh}.log").open("w") as f:
            subprocess.run([str(foam / "usr/bin/gmshToFoam"), "wing.msh"], cwd=case, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
        (case / "system/controlDict").write_text('''FoamFile { version 2.0; format ascii; class dictionary; location "system"; object controlDict; }
application rhoPimpleFoam;
startFrom startTime; startTime 0; stopAt endTime; endTime 0.004;
deltaT 1e-5; adjustTimeStep yes; maxCo 0.4; maxDeltaT 2e-5;
writeControl timeStep; writeInterval 100; purgeWrite 0; writeFormat ascii; writePrecision 10; writeCompression off; timeFormat general; timePrecision 8; runTimeModifiable false;
''')
        (case / "system/preciceDict").unlink(missing_ok=True)
        (case / "constant/dynamicMeshDict").unlink(missing_ok=True)
        (case / "system/fvSolution").write_text('''FoamFile { version 2.0; format ascii; class dictionary; location "system"; object fvSolution; }
solvers
{
 p { solver GAMG; tolerance 1e-7; relTol 0.05; smoother GaussSeidel; }
 pFinal { $p; relTol 0; }
 pcorr { solver PCG; preconditioner DIC; tolerance 1e-6; relTol 0; }
 pcorrFinal { $pcorr; }
 rho { solver PCG; preconditioner DIC; tolerance 1e-7; relTol 0; }
 rhoFinal { $rho; }
 "(U|h|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-7; relTol 0.1; }
 "(U|h|k|omega)Final" { $U; relTol 0; }
}
PIMPLE { nOuterCorrectors 2; nCorrectors 2; nNonOrthogonalCorrectors 1; momentumPredictor yes; }
relaxationFactors { fields { p 0.3; } equations { U 0.5; h 0.5; k 0.5; omega 0.5; } }
''')
        fs = (case / "system/fvSchemes").read_text().replace("div(phi,U) bounded Gauss linearUpwind grad(U);", "div(phi,U) bounded Gauss upwind;")
        fs += "\nwallDist { method meshWave; }\n"
        (case / "system/fvSchemes").write_text(fs)
        boundary = case / "constant/polyMesh/boundary"
        b = boundary.read_text()
        b = re.sub(r"(\bfsi\s*\{\s*type\s+)patch;", r"\1wall;", b)
        b = re.sub(r"(\brootWall\s*\{\s*type\s+)patch;", r"\1symmetryPlane;", b)
        boundary.write_text(b)
        wall = {"U":"type noSlip;", "p":"type zeroGradient;", "T":"type zeroGradient;", "rho":"type zeroGradient;", "h":"type zeroGradient;", "k":f"type kqRWallFunction; value uniform {1.5*(.01*tas)**2};", "omega":"type omegaWallFunction; value uniform 180;", "nut":"type nutkWallFunction; value uniform 0;", "alphat":"type compressible::alphatWallFunction; value uniform 0;"}
        for name, body in wall.items():
            path = case / "0" / name
            if not path.exists():
                continue
            s = path.read_text()
            s = replace_patch(s, "fsi", body)
            s = replace_patch(s, "rootWall", "type symmetryPlane;")
            if name == "U":
                s = re.sub(r"internalField uniform \(0 0 [^)]*\);", f"internalField uniform (0 0 {tas:.12g});", s)
                s = re.sub(r"(value uniform \(0 0 )[^)]*(\);)", rf"\g<1>{tas:.12g}\g<2>", s)
                s = re.sub(r"(freestreamValue uniform \(0 0 )[^)]*(\);)", rf"\g<1>{tas:.12g}\g<2>", s)
            if name == "k":
                k = 1.5 * (.01 * tas)**2
                s = s.replace("internalField uniform 6.0;", f"internalField uniform {k:.12g};").replace("value uniform 6.0;", f"value uniform {k:.12g};").replace("inletValue uniform 6.0;", f"inletValue uniform {k:.12g};")
            path.write_text(s)
        manifest = {"case":f"ias{kmh}", "sourceMeshSHA256":hashlib.sha256((SOURCE/"wing.msh").read_bytes()).hexdigest(), "sourceGeometrySHA256":hashlib.sha256(STEP.read_bytes()).hexdigest(), "solver":"rhoPimpleFoam OpenFOAM 1912.200626-3+b1", "scope":"Fixed Phase-15 outboard wing sector; static mesh, no preCICE, no rotating EDF, not full aircraft", "iasCasKmh":kmh, "altitudeM":3000, "pStaticPa":p, "tStaticK":t, "impactPressurePa":qc, "mach":mach, "tasMps":tas, "aoaDeg":0.5, "endTimeSeconds":0.004, "maxCourant":0.4}
        (case / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        for tool in ("checkMesh", "rhoPimpleFoam"):
            argv = [str(foam / "usr/bin" / tool), "-case", str(case)]
            if tool == "rhoPimpleFoam": argv.append("-dry-run")
            with (logs / f"{tool}_ias{kmh}.log").open("w") as f:
                subprocess.run(argv, cwd=case, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
    print(out)

if __name__ == "__main__": main()
