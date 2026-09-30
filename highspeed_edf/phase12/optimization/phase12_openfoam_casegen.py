#!/usr/bin/env python3
"""Generate local Gmsh/OpenFOAM preflight cases for the four-slot split turn."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gmsh

ROOT = Path(__file__).resolve().parents[2]
P12 = ROOT / "phase12"
CONFIG = P12 / "configs" / "phase12_split_inlet_sweep.json"
TEMPLATES = P12 / "templates" / "openfoam"
GAMMA, R_AIR = 1.4, 287.05
UTC = timezone.utc


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def isa(h: float) -> tuple[float, float, float]:
    t = 288.15 - 0.0065 * h
    p = 101325.0 * (t / 288.15) ** (9.80665 / (R_AIR * 0.0065))
    return t, p, p / (R_AIR * t)


def flux(m: float, p0: float, t0: float) -> float:
    f = 1.0 + 0.5 * (GAMMA - 1.0) * m * m
    return p0 / math.sqrt(t0) * math.sqrt(GAMMA / R_AIR) * m * f ** (-(GAMMA + 1.0) / (2.0 * (GAMMA - 1.0)))


def mach_for_flux(target: float, p0: float, t0: float) -> float:
    if target >= flux(1.0, p0, t0):
        raise ValueError("requested branch flow reaches ideal choke")
    lo, hi = 1e-9, 0.999999
    for _ in range(85):
        mid = 0.5 * (lo + hi)
        if flux(mid, p0, t0) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def derive(cfg: dict[str, Any]) -> dict[str, Any]:
    p9cfg = json.loads((ROOT / cfg["sources"]["phase9Config"]).read_text(encoding="utf-8"))
    meanline = json.loads((ROOT / cfg["sources"]["phase9Meanline"]).read_text(encoding="utf-8"))
    area_path = ROOT / cfg["sources"]["phase12FrontAreaVariants"]
    with area_path.open(newline="", encoding="utf-8") as stream:
        area_rows = list(csv.DictReader(stream))
    area_by_radius: dict[int, dict[str, Any]] = {}
    area_limit = float(cfg["projectedAreaGate"]["maximumCm2"])
    for row in area_rows:
        radius = int(round(float(row["radiusMm"])))
        area = float(row["frontProjectedAreaCm2"])
        if radius in area_by_radius or area <= 0.0:
            raise ValueError(f"invalid/duplicate Phase-12 CAD area row for R{radius:03d}")
        recorded_pass = row["gate75Pass"].strip().lower() == "true"
        computed_pass = area <= area_limit
        if recorded_pass != computed_pass:
            raise ValueError(f"CAD area gate disagrees with configured {area_limit:g} cm2 limit at R{radius:03d}")
        area_by_radius[radius] = {"radiusMm": radius, "frontProjectedAreaCm2": area,
                                  "areaGatePass": computed_pass,
                                  "initialVariant": row["initialVariant"].strip().lower() == "true",
                                  "recoveryEvidence": row["recoveryEvidence"]}
    if not area_by_radius:
        raise ValueError("Phase-12 CAD front-area report contains no variants")
    op, geom = cfg["operatingPoint"], cfg["geometry"]
    t, p, rho = isa(float(op["altitudeM"]))
    speed = float(op["speedKmh"]) / 3.6
    ma = speed / math.sqrt(GAMMA * R_AIR * t)
    t0 = t * (1.0 + 0.5 * (GAMMA-1.0)*ma*ma)
    p0 = p * (1.0 + 0.5 * (GAMMA-1.0)*ma*ma) ** (GAMMA/(GAMMA-1.0))
    duct_area = math.pi/4.0 * (float(geom["ductOuterDiameterM"])**2 - float(geom["hubDiameterM"])**2)
    branch_area = 0.5 * duct_area
    slot_area = float(geom["slotWidthM"]) * float(geom["slotLengthM"])
    mdot_branch = float(meanline["massFlowTotalKgPerS"]) / int(geom["ductCount"]) / int(geom["slotsPerDuct"])
    in_mflux, out_mflux = mdot_branch/slot_area, mdot_branch/branch_area
    inlet_ma = mach_for_flux(in_mflux, p0, t0)
    target_recovery = float(op["targetTotalPressureRecovery"])
    outlet_total_p = target_recovery*p0
    outlet_ma = mach_for_flux(out_mflux, outlet_total_p, t0)

    def static(pt: float, tt: float, m: float) -> tuple[float,float]:
        f = 1.0+0.5*(GAMMA-1.0)*m*m
        return pt/f**(GAMMA/(GAMMA-1.0)), tt/f

    pin,tin=static(p0,t0,inlet_ma)
    pout,tout=static(outlet_total_p,t0,outlet_ma)
    rhoin=pin/(R_AIR*tin)
    d_eq=math.sqrt(4.0*branch_area/math.pi)
    return {
        "sourceHashes": {
            "phase9Config": sha256(ROOT/cfg["sources"]["phase9Config"]),
            "phase9Meanline": sha256(ROOT/cfg["sources"]["phase9Meanline"]),
            "phase12FrontAreaVariants": sha256(area_path),
        },
        "freestream": {"altitudeM":float(op["altitudeM"]),"speedMps":speed,"staticTemperatureK":t,
                       "staticPressurePa":p,"densityKgM3":rho,"mach":ma,
                       "totalTemperatureK":t0,"totalPressurePa":p0},
        "branch": {"branchesTotal":int(geom["ductCount"])*int(geom["slotsPerDuct"]),
                   "massFlowKgS":mdot_branch,"slotAreaM2":slot_area,"branchOutletAreaM2":branch_area,
                   "equivalentRoundOutletDiameterM":d_eq,"slotToBranchAreaRatio":slot_area/branch_area,
                   "inletMachAtTargetFlow":inlet_ma,"inletStaticPressurePa":pin,"inletStaticTemperatureK":tin,
                   "inletVolumeFlowM3S":mdot_branch/rhoin,"outletMachAtTargetRecovery":outlet_ma,
                   "outletStaticPressurePa":pout,"outletStaticTemperatureK":tout,
                   "idealChokedBranchFlowKgS":flux(1.0,p0,t0)*branch_area,
                   "targetRecovery":target_recovery},
        "annulus": {"perDuctAreaM2":duct_area,"perDuctAreaCm2":duct_area*1e4,
                    "perBranchAreaM2":branch_area,"perBranchAreaCm2":branch_area*1e4},
        "projectedArea": {"maximumCm2": area_limit,
                          "source": cfg["sources"]["phase12FrontAreaVariants"],
                          "variants": [area_by_radius[r] for r in sorted(area_by_radius)]},
        "geometry": geom,
        "referenceCandidate": {"slotToAnnulusAreaRatioPhase9":float(p9cfg["geometry"]["slotToFanAnnulusAreaRatio"])}
    }


def rectangle_profile(width: float, height: float, n: int=32) -> list[tuple[float,float]]:
    """Closed rectangle loop, starting at top-centre and proceeding down its right side."""
    if n % 8:
        raise ValueError("rectangle profile point count must be divisible by eight")
    quarter=n//4; half_top=n//8; pts=[]
    sides=((0.0,height/2.0,width/2.0,height/2.0,half_top),
           (width/2.0,height/2.0,width/2.0,-height/2.0,quarter),
           (width/2.0,-height/2.0,-width/2.0,-height/2.0,quarter),
           (-width/2.0,-height/2.0,-width/2.0,height/2.0,quarter),
           (-width/2.0,height/2.0,0.0,height/2.0,half_top))
    for x0,y0,x1,y1,count in sides:
        for i in range(count):
            f=i/count
            pts.append((x0+(x1-x0)*f,y0+(y1-y0)*f))
    return pts


def half_annulus_profile(outer_radius: float, inner_radius: float,
                         n: int=32) -> list[tuple[float,float]]:
    """One semicircular annulus with its split face on x=0."""
    if n % 8 or not 0.0 < inner_radius < outer_radius:
        raise ValueError("invalid half-annulus profile dimensions")
    half=n//2; pts=[]
    for i in range(half):
        angle=math.pi*i/(half-1)
        pts.append((outer_radius*math.sin(angle),outer_radius*math.cos(angle)))
    for i in range(half):
        angle=math.pi-math.pi*i/(half-1)
        pts.append((inner_radius*math.sin(angle),inner_radius*math.cos(angle)))
    return pts


def polygon_area(points: list[tuple[float,float]]) -> float:
    return abs(sum(points[i][0]*points[(i+1)%len(points)][1]
                   - points[(i+1)%len(points)][0]*points[i][1]
                   for i in range(len(points)))/2.0)


def add_section_wire(occ: Any, z: float, points: list[tuple[float,float]]) -> int:
    pts=[occ.addPoint(x,y,z) for x,y in points]
    edges=[occ.addLine(pts[i],pts[(i+1)%len(pts)]) for i in range(len(pts))]
    return occ.addWire(edges,checkClosed=True)


def build_mesh(case_dir: Path, case: dict[str, Any], state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    radius=float(case["turnRadiusM"])
    slot_width=float(state["geometry"]["slotWidthM"])
    slot_length=float(state["geometry"]["slotLengthM"])
    radial_h=float(state["geometry"]["splitTurnHeightMm"])/1000.0
    transition=float(state["geometry"]["transitionLengthM"])
    reqarea=float(state["annulus"]["perBranchAreaM2"])
    outer_r=float(state["geometry"]["ductOuterDiameterM"])/2.0
    inner_r=float(state["geometry"]["hubDiameterM"])/2.0
    outlet_profile=half_annulus_profile(outer_r,inner_r)
    if not math.isclose(slot_width,radial_h,rel_tol=0.0,abs_tol=1e-9):
        raise ValueError("slot width and split-turn radial height must agree for this Phase-12 passage model")
    # The 120 mm slot length is the spanwise section dimension; the 25 mm
    # width/turn height lies in the bend plane and remains below every radius.
    inlet_profile=rectangle_profile(slot_length,radial_h)
    inlet_area=slot_width*slot_length
    outlet_analytic_area=0.5*math.pi*(outer_r*outer_r-inner_r*inner_r)
    outlet_area=polygon_area(outlet_profile)
    outlet_area_error=abs(outlet_area-reqarea)/reqarea
    if not math.isclose(outlet_analytic_area,reqarea,rel_tol=1e-10,abs_tol=1e-12):
        raise ValueError(f"half-annulus analytic area {outlet_analytic_area} does not match derived branch area {reqarea}")
    if outlet_area_error>0.01:
        raise ValueError(f"polygonal half-annulus area error {outlet_area_error:.3%} exceeds 1.0%")
    hmax=float(cfg["mesh"]["levels"][case["meshLevel"]])
    gmsh.initialize()
    try:
        for key,val in (("General.Terminal",0),("General.NumThreads",int(cfg["mesh"].get("threads",2))),
                        ("Mesh.MshFileVersion",2.2),("Mesh.ElementOrder",1),
                        ("Mesh.MeshSizeMin",hmax*0.75),("Mesh.MeshSizeMax",hmax),
                        ("Mesh.MeshSizeFromCurvature",1),("Mesh.Algorithm3D",10),("Mesh.Optimize",0)):
            gmsh.option.setNumber(key,val)
        gmsh.model.add(case["caseId"])
        occ=gmsh.model.occ
        inlet=[occ.addPoint(radius,y,z) for y,z in inlet_profile]
        inlet_edges=[occ.addLine(inlet[i],inlet[(i+1)%len(inlet)]) for i in range(len(inlet))]
        inlet_face=occ.addPlaneSurface([occ.addWire(inlet_edges,checkClosed=True)])
        # Centerline begins at (R,0,0), turns in the x-z plane, and exits +z.
        swept=occ.revolve([(2,inlet_face)],radius,0,radius,0,1,0,math.pi/2.0)
        print(f"{case['caseId']}: elbow generated",flush=True)
        elbow=[tag for dim,tag in swept if dim==3]
        if len(elbow)!=1: raise RuntimeError(f"elbow sweep returned {elbow}")
        elbow_mass=occ.getMass(3,elbow[0])
        sections=[]
        for j in range(5):
            f=j/4.0
            if case["transitionProfile"]=="linear":
                t=f
            elif case["transitionProfile"]=="smoothstep":
                t=f*f*(3.0-2.0*f)
            else:
                raise ValueError(f"unsupported transition profile {case['transitionProfile']!r}")
            rect=rectangle_profile(radial_h,slot_length)
            profile=[(a*(1.0-t)+b*t,c*(1.0-t)+d*t)
                     for (a,c),(b,d) in zip(rect,outlet_profile)]
            sections.append(add_section_wire(occ,radius+transition*f,profile))
        loft=occ.addThruSections(sections,makeSolid=True,makeRuled=True)
        print(f"{case['caseId']}: transition loft generated",flush=True)
        lvol=[tag for dim,tag in loft if dim==3]
        if len(lvol)!=1: raise RuntimeError(f"transition loft returned {lvol}")
        loft_mass=occ.getMass(3,lvol[0])
        fused,_=occ.fuse([(3,elbow[0])],[(3,lvol[0])],removeObject=True,removeTool=True)
        print(f"{case['caseId']}: branch fused",flush=True)
        fluid=[tag for dim,tag in fused if dim==3]
        if len(fluid)!=1: raise RuntimeError(f"fused branch returned {fluid}; elbowM={elbow_mass}; loftM={loft_mass}; fused={fused}")
        occ.synchronize()
        faces=[tag for dim,tag in gmsh.model.getBoundary([(3,fluid[0])],combined=False,oriented=False) if dim==2]
        inlet_faces=[]; outlet_faces=[]; walls=[]; z_out=radius+transition
        for face in faces:
            b=gmsh.model.getBoundingBox(2,face)
            if abs(b[0]-radius)<2e-6 and abs(b[3]-radius)<2e-6: inlet_faces.append(face)
            elif abs(b[2]-z_out)<2e-6 and abs(b[5]-z_out)<2e-6: outlet_faces.append(face)
            else: walls.append(face)
        if not inlet_faces or not outlet_faces or not walls:
            boxes=[gmsh.model.getBoundingBox(2,face) for face in faces]
            raw_boundary=gmsh.model.getBoundary([(3,fluid[0])],combined=False,oriented=False)
            surf_entities=gmsh.model.getEntities(2)
            surf_boxes=[gmsh.model.getBoundingBox(2,t) for d,t in surf_entities]
            raise RuntimeError(f"missing inlet/outlet/wall physical patches: {len(inlet_faces)}/{len(outlet_faces)}/{len(walls)}; elbowMass={elbow_mass}; loftMass={loft_mass}; fused={fused}; fluid={fluid}; volumeMass={occ.getMass(3,fluid[0])}; volumeBox={gmsh.model.getBoundingBox(3,fluid[0])}; volumeEntities={gmsh.model.getEntities(3)}; boundary={raw_boundary}; allSurfaces={surf_entities}; surfaceBoxes={surf_boxes}; boxes={boxes}")
        gmsh.model.addPhysicalGroup(3,[fluid[0]],1); gmsh.model.setPhysicalName(3,1,"fluid")
        for tag,name,entities in ((11,"inlet",inlet_faces),(12,"outlet",outlet_faces),(13,"walls",walls)):
            gmsh.model.addPhysicalGroup(2,entities,tag); gmsh.model.setPhysicalName(2,tag,name)
        gmsh.model.mesh.generate(3)
        print(f"{case['caseId']}: tetra mesh generated",flush=True)
        gmsh.model.mesh.optimize("Relocate3D")
        gmsh.model.mesh.optimize("Netgen")
        nodes,_,_=gmsh.model.mesh.getNodes()
        _,groups,_=gmsh.model.mesh.getElements(3)
        elem=[int(t) for group in groups for t in group]
        q=[float(x) for x in gmsh.model.mesh.getElementQualities(elem,"minSICN")] if elem else []
        gmsh.write(str(case_dir/"mesh.msh"))
        return {"nodes":len(nodes),"tetraCells":len(elem),"minSICN":min(q) if q else None,
                "cellsSICNBelow0p05":sum(x<0.05 for x in q),
                "fluidVolumeM3":occ.getMass(3,fluid[0]),
                "inletSectionAreaM2":inlet_area,"outletSectionAreaM2":outlet_area,
                "outletSectionAnalyticAreaM2":outlet_analytic_area,
                "outletSectionAreaErrorFraction":outlet_area_error,
                "inletSectionDimensionsMm":[slot_width*1000.0,slot_length*1000.0],
                "outletSection":"semicircular annulus, OD 90 mm / ID 32 mm",
                "physicalFaceCounts":{"inlet":len(inlet_faces),"outlet":len(outlet_faces),"walls":len(walls)}}
    finally:
        gmsh.finalize()


def dictionary_syntax_preflight(case_dir: Path) -> dict[str, Any]:
    required=["0/p","0/U","0/T","0/k","0/omega","0/nut","0/alphat",
              "constant/thermophysicalProperties","constant/turbulenceProperties",
              "system/controlDict","system/fvSchemes","system/fvSolution","system/changeDictionaryDict"]
    missing=[rel for rel in required if not (case_dir/rel).is_file()]
    brace_balance={}
    for rel in required:
        path=case_dir/rel
        if not path.is_file(): continue
        text=path.read_text(encoding="utf-8",errors="replace")
        # Static lexical check only; a real OpenFOAM parser/checkMesh remains mandatory.
        stripped=re.sub(r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"])*\"", "", text, flags=re.M|re.S)
        brace_balance[rel]=stripped.count("{")-stripped.count("}")
    change_dict=(case_dir/"system/changeDictionaryDict").read_text(encoding="utf-8")
    direct_wall_replacement=bool(re.search(
        r"dictionaryReplacement\s*\{\s*boundary\s*\{\s*walls\s*\{\s*type\s+wall\s*;",
        change_dict, flags=re.S))
    return {"allRequiredFilesPresent":not missing,"missing":missing,
            "braceBalance":brace_balance,"allBracesBalanced":all(v==0 for v in brace_balance.values()),
            "wallPatchDictionaryReplacementValid": direct_wall_replacement}


def prepare(only_case: str|None=None) -> dict[str,Any]:
    cfg=json.loads(CONFIG.read_text(encoding="utf-8")); state=derive(cfg)
    if not TEMPLATES.is_dir():
        raise FileNotFoundError(f"Phase-12-owned OpenFOAM templates are missing: {TEMPLATES}")
    selected=[c for c in cfg["cases"] if only_case is None or c["id"]==only_case]
    if only_case and not selected: raise ValueError(f"unknown case id {only_case}")
    rows=[]
    for item in selected:
        case_id=item["id"]; dest=P12/"cases"/case_id
        if dest.exists(): shutil.rmtree(dest)
        dest.mkdir(parents=True)
        case={**item,"caseId":case_id,"targetMassFlowKgPerS":state["branch"]["massFlowKgS"],
              "targetRecovery":state["branch"]["targetRecovery"],
              "totalPressurePa":state["freestream"]["totalPressurePa"],
              "totalTemperatureK":state["freestream"]["totalTemperatureK"],
              "turnRadiusMm":item["turnRadiusM"]*1000.0,
              "slotWidthM":state["geometry"]["slotWidthM"],"slotLengthM":state["geometry"]["slotLengthM"]}
        pin,tin=state["branch"]["inletStaticPressurePa"],state["branch"]["inletStaticTemperatureK"]
        pout,tout=state["branch"]["outletStaticPressurePa"],state["branch"]["outletStaticTemperatureK"]
        uin=state["branch"]["inletVolumeFlowM3S"]/state["branch"]["slotAreaM2"]
        substitutions={"@P_OUT@":f"{pout:.10g}","@P0@":f"{state['freestream']['totalPressurePa']:.10g}",
                       "@P_IN@":f"{pin:.10g}","@U_IN@":f"{uin:.10g}","@Q_IN@":f"{state['branch']['inletVolumeFlowM3S']:.10g}",
                       "@T_OUT@":f"{tout:.10g}","@T0@":f"{state['freestream']['totalTemperatureK']:.10g}","@T_IN@":f"{tin:.10g}"}
        kin=max(1.5*(0.05*uin)**2,1e-5); omega=math.sqrt(kin)/(0.09**0.25*0.07*0.058)
        substitutions["@K_IN@"],substitutions["@OMEGA_IN@"]=f"{kin:.10g}",f"{omega:.10g}"
        for source in TEMPLATES.rglob("*"):
            if not source.is_file():continue
            destfile=dest/source.relative_to(TEMPLATES);destfile.parent.mkdir(parents=True,exist_ok=True)
            text=source.read_text(encoding="utf-8")
            for key,value in substitutions.items():text=text.replace(key,value)
            if destfile.as_posix().endswith("/0/U"):
                text=text.replace(f"(0 {substitutions['@U_IN@']} 0)",f"(-{substitutions['@U_IN@']} 0 0)")
            destfile.write_text(text,encoding="utf-8")
        mesh=build_mesh(dest,case,state,cfg)
        syntax=dictionary_syntax_preflight(dest)
        case["meshEvidence"],case["syntaxPreflight"]=mesh,syntax
        (dest/"case.json").write_text(json.dumps(case,indent=2)+"\n",encoding="utf-8")
        rows.append({"caseId":case_id,"turnRadiusMm":case["turnRadiusMm"],"meshLevel":case["meshLevel"],
                     "cells":mesh["tetraCells"],"minSICN":mesh["minSICN"],"localOpenFOAMCheckMesh":None,
                      "localDictionaryStaticCheck":syntax["allRequiredFilesPresent"] and syntax["allBracesBalanced"] and syntax["wallPatchDictionaryReplacementValid"],
                      "frontProjectedAreaCm2":next(v["frontProjectedAreaCm2"] for v in state["projectedArea"]["variants"] if v["radiusMm"]==round(case["turnRadiusMm"])),
                      "frontAreaGatePass":next(v["areaGatePass"] for v in state["projectedArea"]["variants"] if v["radiusMm"]==round(case["turnRadiusMm"])),
                     "solverStatus":"prepared_not_run","pressureRecovery":None})
    if only_case is None:
        result=P12/"results";result.mkdir(parents=True,exist_ok=True)
        with (result/"phase12_case_matrix.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        checkmesh=shutil.which("checkMesh")
        wsl_checkmesh=None
        if shutil.which("wsl.exe"):
            try:
                q=subprocess.run(["wsl.exe","-d","Ubuntu-24.04","--exec","bash","-lc","command -v checkMesh"],
                                capture_output=True,text=True,timeout=15)
                wsl_checkmesh=q.stdout.strip() if q.returncode==0 and q.stdout.strip() else None
            except Exception:
                wsl_checkmesh=None
        fits=[]
        area_by_radius={v["radiusMm"]:v for v in state["projectedArea"]["variants"]}
        for item in cfg["cases"]:
            rmm=int(round(float(item["turnRadiusM"])*1000.0))
            area=area_by_radius.get(rmm)
            if area is None:
                raise ValueError(f"No authoritative Phase-12 CAD area for configured R{rmm:03d} case")
            fits.append({"caseId":item["id"],"turnRadiusMm":rmm,
                         "frontProjectedAreaCm2":area["frontProjectedAreaCm2"],
                         "areaGatePass":area["areaGatePass"],
                         "areaSource":cfg["sources"]["phase12FrontAreaVariants"]})
        preflight={"phase":12,"createdAtUtc":datetime.now(UTC).isoformat(),
                    "status":"local-mesh-preflight-remote-checkmesh-required","evidenceClass":"Gmsh geometry/mesh plus static dictionary lexical check; not OpenFOAM checkMesh or CFD",
                   "sources":state,"cases":rows,"frontProjectionScreen":fits,
                   "localToolAvailability":{"gmshPython":True,"checkMeshOnPath":bool(checkmesh),"checkMeshViaWsl":wsl_checkmesh,
                                            "dockerDaemon":False},
                    "launchGate":{"realLocalCheckMeshRequired":False,"remoteCheckMeshRequired":True,
                                  "remoteCheckMeshRunnerAvailable":False,"solverSyntaxOpenFoamParserPassed":False,
                                  "cadAreaPassingGeometryCount":sum(bool(x["areaGatePass"]) for x in state["projectedArea"]["variants"]),
                                  "configuredCasesPassingCadAreaGate":sum(bool(x["areaGatePass"]) for x in fits),
                                  "caseGeometryMatchesPublishedCAD":False,"launchPermitted":False,
                                  "reasons":["Current Gmsh inlet cross-section is 25x25 mm, not the published 25x120 mm CAD slot.",
                                              "Current Gmsh outlet is an equivalent-area circle; published CAD branch exits are split half-annulus sections.",
                                              "Phase-12 bounded remote checkMesh/solver runner is not yet available."]},
                   "costPlan":cfg["cloudBudget"]}
        (result/"phase12_preflight.json").write_text(json.dumps(preflight,indent=2)+"\n",encoding="utf-8")
    return {"state":state,"cases":rows}


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--only-case")
    args=ap.parse_args();out=prepare(args.only_case)
    print(json.dumps({"cases":out["cases"],"branch":out["state"]["branch"]},indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
