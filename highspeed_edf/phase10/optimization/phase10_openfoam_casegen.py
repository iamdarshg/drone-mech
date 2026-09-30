#!/usr/bin/env python3
"""Generate the phase-10 Gmsh side-duct mesh and rhoSimpleFoam inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STUDY = Path(__file__).resolve().parents[2]
P10 = STUDY / "phase10"
CONFIG = P10 / "configs" / "phase10_openfoam_study.json"
TEMPLATES = P10 / "templates" / "openfoam"
GAMMA, R_AIR = 1.4, 287.05


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def isa(h: float) -> tuple[float, float, float]:
    t = 288.15 - 0.0065 * h
    p = 101325.0 * (t / 288.15) ** (9.80665 / (R_AIR * 0.0065))
    return t, p, p / (R_AIR * t)


def flux(m: float, p0: float, t0: float) -> float:
    z = 1.0 + 0.5 * (GAMMA - 1.0) * m * m
    return p0 / math.sqrt(t0) * math.sqrt(GAMMA / R_AIR) * m * z ** (-(GAMMA + 1.0) / (2.0 * (GAMMA - 1.0)))


def mach_for_flux(target: float, p0: float, t0: float) -> float:
    if target >= flux(1.0, p0, t0):
        raise ValueError("flow exceeds the ideal choked mass-flux limit")
    lo, hi = 1e-10, 0.999999
    for _ in range(90):
        m = (lo + hi) / 2.0
        if flux(m, p0, t0) < target:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2.0


def derive(cfg: dict[str, Any]) -> dict[str, Any]:
    p9 = json.loads((STUDY / cfg["geometrySource"]["phase9Config"]).read_text(encoding="utf-8"))
    design = json.loads((STUDY / cfg["geometrySource"]["candidateState"]).read_text(encoding="utf-8"))
    meanline = json.loads((STUDY / cfg["geometrySource"]["phase9Meanline"]).read_text(encoding="utf-8"))
    geo, op = p9["geometry"], cfg["operatingPoint"]
    ts, ps, rho = isa(float(op["altitudeM"]))
    u = float(op["flightSpeedKmh"]) / 3.6
    a = math.sqrt(GAMMA * R_AIR * ts)
    m = u / a
    t0 = ts * (1.0 + 0.5 * (GAMMA - 1.0) * m * m)
    p0 = ps * (1.0 + 0.5 * (GAMMA - 1.0) * m * m) ** (GAMMA / (GAMMA - 1.0))
    nduct = int(geo["ductCount"])
    od, hd = float(geo["ductOuterDiameterM"]), float(geo["hubDiameterM"])
    ann = math.pi / 4.0 * (od * od - hd * hd)
    slot = float(geo["sideIntakeSlots"]["widthMm"]) * float(geo["sideIntakeSlots"]["lengthMm"]) * 1e-6
    mdot = float(meanline["massFlowTotalKgPerS"]) / nduct
    mf_ann = mdot / ann
    mf_slot = mdot / slot
    mf_critical = flux(1.0, p0, t0)
    min_m = mach_for_flux(mf_slot, p0, t0)
    p_target0 = p0 * float(op["targetTotalPressureRecovery"])
    mout = mach_for_flux(mf_ann, p_target0, t0)

    def static(p_total: float, t_total: float, ma: float) -> tuple[float, float]:
        f = 1.0 + 0.5 * (GAMMA - 1.0) * ma * ma
        return p_total / f ** (GAMMA / (GAMMA - 1.0)), t_total / f

    pin, tin = static(p0, t0, min_m)
    pout, tout = static(p_target0, t0, mout)
    rhoin = pin / (R_AIR * tin)
    return {
        "sourceHashes": {
            "phase9ConfigSha256": sha256(STUDY / cfg["geometrySource"]["phase9Config"]),
            "candidateStateSha256": sha256(STUDY / cfg["geometrySource"]["candidateState"]),
            "phase9MeanlineSha256": sha256(STUDY / cfg["geometrySource"]["phase9Meanline"]),
        },
        "candidate": {
            "allUpMassKg": float(design["allUpMassTargetKg"]), "ductCount": nduct,
            "outerDiameterM": od, "hubDiameterM": hd,
            "slotWidthM": float(geo["sideIntakeSlots"]["widthMm"]) / 1000.0,
            "slotLengthM": float(geo["sideIntakeSlots"]["lengthMm"]) / 1000.0,
            "declaredSlotToAnnulusAreaRatio": float(geo["slotToFanAnnulusAreaRatio"]),
        },
        "freestream": {
            "altitudeM": float(op["altitudeM"]), "speedMPerS": u,
            "staticTemperatureK": ts, "staticPressurePa": ps, "densityKgPerM3": rho,
            "mach": m, "soundSpeedMPerS": a, "totalTemperatureK": t0, "totalPressurePa": p0,
        },
        "perDuct": {
            "meanlineMassFlowKgPerS": mdot, "slotAreaM2": slot, "annulusAreaM2": ann,
            "slotToAnnulusAreaRatio": slot / ann, "areaContractionFraction": 1.0 - ann / slot,
            "slotCaptureMassFlowAtConfiguredFractionKgPerS": rho * u * slot * float(op["flightCaptureFraction"]),
            "captureFractionNeededForMeanlineFlow": mdot / (rho * u * slot),
            "annulusMassFluxKgPerM2S": mf_ann,
            "idealChokedMassFlowLimitKgPerS": mf_critical * ann,
            "fractionOfIdealChokedLimit": mf_ann / mf_critical,
            "inletMachAtMeanlineFlow": min_m,
            "inletStaticPressureAtMeanlineFlowPa": pin,
            "inletStaticTemperatureAtMeanlineFlowK": tin,
            "inletVolumetricFlowAtMeanlineFlowM3PerS": mdot / rhoin,
            "outletMachAtTargetRecovery": mout,
            "outletStaticPressureAtTargetRecoveryPa": pout,
            "outletStaticTemperatureAtTargetRecoveryK": tout,
            "targetTotalPressureRecovery": float(op["targetTotalPressureRecovery"]),
        },
    }


def fill_templates(case_dir: Path, case: dict[str, Any], state: dict[str, Any]) -> None:
    flow, free = state["perDuct"], state["freestream"]
    q = float(flow["inletVolumetricFlowAtMeanlineFlowM3PerS"])
    u = q / float(flow["slotAreaM2"])
    k = max(1.5 * (0.05 * u) ** 2, 1e-5)
    omega = max(math.sqrt(k) / (0.09**0.25 * 0.07 * (state["candidate"]["outerDiameterM"] - state["candidate"]["hubDiameterM"])), 1.0)
    substitutions = {
        "@P_OUT@": f"{flow['outletStaticPressureAtTargetRecoveryPa']:.10g}",
        "@P0@": f"{free['totalPressurePa']:.10g}",
        "@P_IN@": f"{flow['inletStaticPressureAtMeanlineFlowPa']:.10g}",
        "@U_IN@": f"{u:.10g}", "@Q_IN@": f"{q:.10g}",
        "@T_OUT@": f"{flow['outletStaticTemperatureAtTargetRecoveryK']:.10g}",
        "@T0@": f"{free['totalTemperatureK']:.10g}",
        "@T_IN@": f"{flow['inletStaticTemperatureAtMeanlineFlowK']:.10g}",
        "@K_IN@": f"{k:.10g}", "@OMEGA_IN@": f"{omega:.10g}",
    }
    for source in TEMPLATES.rglob("*"):
        if source.is_file():
            relative = source.relative_to(TEMPLATES)
            target = case_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            text = source.read_text(encoding="utf-8")
            for key, value in substitutions.items():
                text = text.replace(key, value)
            target.write_text(text, encoding="utf-8")
    (case_dir / "case.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")


def profile_wire(gmsh: Any, a: float, b: float, exponent: float, x: float, y_center: float, count: int = 48) -> int:
    occ = gmsh.model.occ
    pts = []
    power = 2.0 / exponent
    for i in range(count):
        angle = 2.0 * math.pi * i / count
        c, s = math.cos(angle), math.sin(angle)
        pts.append(occ.addPoint(x, y_center + a * math.copysign(abs(c) ** power, c), b * math.copysign(abs(s) ** power, s)))
    lines = [occ.addLine(pts[i], pts[(i + 1) % count]) for i in range(count)]
    return occ.addWire(lines, checkClosed=True)


def make_mesh(root: Path, case: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    import gmsh

    r, w, h = case["bendRadiusM"], case["slotWidthM"], case["slotLengthM"]
    length, ro, ri, hmax = case["transitionLengthM"], case["outerDiameterM"] / 2, case["hubDiameterM"] / 2, case["maxCellSizeM"]
    gmsh.initialize()
    try:
        for option, value in (("General.Terminal", 0), ("Mesh.MshFileVersion", 2.2),
                              ("Mesh.ElementOrder", 1), ("Mesh.MeshSizeMin", hmax * 0.45),
                              ("Mesh.MeshSizeMax", hmax), ("Mesh.MeshSizeFromCurvature", 1),
                              ("Mesh.Algorithm3D", 1), ("Mesh.Optimize", 1)):
            gmsh.option.setNumber(option, value)
        gmsh.model.add(case["caseId"])
        occ = gmsh.model.occ
        corners = [(r-w/2, 0, -h/2), (r+w/2, 0, -h/2), (r+w/2, 0, h/2), (r-w/2, 0, h/2)]
        points = [occ.addPoint(*point) for point in corners]
        edges = [occ.addLine(points[i], points[(i+1) % 4]) for i in range(4)]
        face = occ.addPlaneSurface([occ.addWire(edges, checkClosed=True)])
        swept = occ.revolve([(2, face)], 0, 0, 0, 0, 0, 1, math.pi/2)
        elbow = [tag for dim, tag in swept if dim == 3]
        if len(elbow) != 1:
            raise RuntimeError(f"elbow sweep volume count={elbow}")

        sections = []
        for i in range(5):
            f = i / 4
            name = case["contractionProfile"]
            t = f if name == "linear" else (0.5 - 0.5 * math.cos(math.pi*f) if name == "cosine" else f**0.58)
            a = w/2 * (1-t) + ro*t
            b = h/2 * (1-t) + ro*t
            n = 12*(1-t) + 2*t
            sections.append(profile_wire(gmsh, a, b, n, -length*f, r))
        loft = occ.addThruSections(sections, makeSolid=True, makeRuled=True)
        transition = [tag for dim, tag in loft if dim == 3]
        if len(transition) != 1:
            raise RuntimeError(f"transition loft volume count={transition}")
        fused, _ = occ.fuse([(3, elbow[0])], [(3, transition[0])], removeObject=True, removeTool=True)
        fused = [tag for dim, tag in fused if dim == 3]
        if len(fused) != 1:
            raise RuntimeError(f"fused duct volume count={fused}")
        hub = occ.addCone(-length, r, 0, length, 0, 0, ri, 0.001)
        cut, _ = occ.cut([(3, fused[0])], [(3, hub)], removeObject=True, removeTool=True)
        fluid = [tag for dim, tag in cut if dim == 3]
        if len(fluid) != 1:
            raise RuntimeError(f"fluid volume count after hub subtraction={fluid}")
        occ.synchronize()
        volume = occ.getMass(3, fluid[0])
        faces = [tag for dim, tag in gmsh.model.getBoundary([(3, fluid[0])], combined=False, oriented=False) if dim == 2]
        inlet, outlet, walls = [], [], []
        for face_tag in faces:
            bb = gmsh.model.getBoundingBox(2, face_tag)
            if abs(bb[1]) < 2e-6 and abs(bb[4]) < 2e-6:
                inlet.append(face_tag)
            elif abs(bb[0] + length) < 2e-6 and abs(bb[3] + length) < 2e-6:
                outlet.append(face_tag)
            else:
                walls.append(face_tag)
        if not inlet or not outlet or not walls:
            raise RuntimeError(f"boundary tags missing (inlet={inlet}, outlet={outlet}, walls={len(walls)})")
        gmsh.model.addPhysicalGroup(3, fluid, 1)
        gmsh.model.setPhysicalName(3, 1, "fluid")
        for tag, name, members in ((11, "inlet", inlet), (12, "outlet", outlet), (13, "walls", walls)):
            gmsh.model.addPhysicalGroup(2, members, tag)
            gmsh.model.setPhysicalName(2, tag, name)
        gmsh.model.mesh.generate(3)
        node_tags, _, _ = gmsh.model.mesh.getNodes()
        _, elements, _ = gmsh.model.mesh.getElements(3)
        cells = sum(len(e) for e in elements)
        if cells < int(cfg["mesh"]["meshAcceptance"]["minimumCells"]):
            raise RuntimeError(f"mesh cell count {cells} is below minimum")
        gmsh.write(str(root / "mesh.msh"))
        return {"fluidVolumeM3": volume, "nodeCount": len(node_tags), "tetraCellCount": cells,
                "physicalSurfaces": {"inlet": len(inlet), "outlet": len(outlet), "walls": len(walls)}}
    finally:
        gmsh.finalize()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate(only_case: str | None = None, preflight_only: bool = False) -> dict[str, Any]:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    state = derive(cfg)
    items = [row for row in cfg["caseMatrix"] if only_case is None or row["caseId"] == only_case]
    if only_case and not items:
        raise ValueError(f"unknown case ID: {only_case}")
    rows = []
    for item in items:
        case = {**item,
                "slotWidthM": state["candidate"]["slotWidthM"], "slotLengthM": state["candidate"]["slotLengthM"],
                "outerDiameterM": state["candidate"]["outerDiameterM"], "hubDiameterM": state["candidate"]["hubDiameterM"],
                "transitionLengthM": float(cfg["geometry"]["transitionLengthM"]),
                "maxCellSizeM": float(cfg["mesh"]["levels"][item["meshLevel"]]["maxCellSizeM"]),
                "totalTemperatureK": state["freestream"]["totalTemperatureK"],
                "totalPressurePa": state["freestream"]["totalPressurePa"],
                "targetMassFlowKgPerS": state["perDuct"]["meanlineMassFlowKgPerS"],
                "targetRecovery": state["perDuct"]["targetTotalPressureRecovery"]}
        dest = P10 / "cases" / item["caseId"]
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        fill_templates(dest, case, state)
        meshdata = {"meshStatus": "not-generated"} if preflight_only else make_mesh(dest, case, cfg)
        (dest / "case.json").write_text(json.dumps({**case, "meshEvidence": meshdata}, indent=2) + "\n", encoding="utf-8")
        rows.append({"case_id": case["caseId"], "bend_radius_mm": case["bendRadiusM"]*1000,
                     "contraction_profile": case["contractionProfile"], "mesh_level": case["meshLevel"],
                     "max_cell_size_mm": case["maxCellSizeM"]*1000,
                     "mesh_cells": meshdata.get("tetraCellCount"), "mesh_nodes": meshdata.get("nodeCount"),
                     "target_mdot_per_duct_kg_s": case["targetMassFlowKgPerS"],
                     "solver_status": "prepared_not_run", "pressure_recovery": ""})
    if only_case is None:
        (P10 / "results").mkdir(parents=True, exist_ok=True)
        write_csv(P10 / "results" / "phase10_case_matrix.csv", rows)
        counts = [int(r["mesh_cells"]) for r in rows if r["mesh_cells"] is not None]
        ratio_ok = math.isclose(state["perDuct"]["slotToAnnulusAreaRatio"], state["candidate"]["declaredSlotToAnnulusAreaRatio"], rel_tol=0.01)
        choke_ok = state["perDuct"]["meanlineMassFlowKgPerS"] < state["perDuct"]["idealChokedMassFlowLimitKgPerS"]
        preflight = {"phase": 10, "generatedAtUtc": datetime.now(UTC).isoformat(),
                     "status": "meshed_solver_pending" if not preflight_only else "analytic_preflight_only",
                     "evidenceClass": "case inputs and Gmsh mesh only; pressure recovery is null until solver evidence is received",
                     **state, "geometryChecks": {"slotRatioMatchesPhase9": ratio_ok, "meanlineFlowBelowIdealChoke": choke_ok,
                                                 "allPass": ratio_ok and choke_ok},
                     "meshSummary": {"caseCount": len(rows), "totalTetraCells": sum(counts) if counts else None,
                                     "minimumCells": min(counts) if counts else None, "maximumCells": max(counts) if counts else None,
                                     "gridConvergenceCases": ["r225_linear_coarse", "r225_linear_medium", "r225_linear_fine"]},
                     "cases": rows}
        (P10 / "results" / "phase10_preflight.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
        (P10 / "results" / "phase10_run_plan.json").write_text(json.dumps({
            "phase": 10, "status": "prepared_not_submitted", "configSha256": sha256(CONFIG),
            "sourceHashes": state["sourceHashes"], "caseIds": [r["case_id"] for r in rows],
            "budget": cfg["executionBudget"], "instanceWillLaunch": False}, indent=2) + "\n", encoding="utf-8")
    return {"state": state, "cases": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-case")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    out = generate(args.only_case, args.preflight_only)
    print(json.dumps({"caseCount": len(out["cases"]), "caseIds": [x["case_id"] for x in out["cases"]], "perDuct": out["state"]["perDuct"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
