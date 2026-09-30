#!/usr/bin/env python3
"""Build Phase-11 CAD-aligned Gmsh cases for the compact side-turn sweep."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gmsh

ROOT = Path(__file__).resolve().parents[2]
P11 = ROOT / "phase11"
CFG_PATH = P11 / "configs" / "phase11_iterative_optimization.json"
P10_TEMPLATE = ROOT / "phase10" / "templates" / "openfoam"
RHO_AIR, GAMMA = 287.05, 1.4
UTC = timezone.utc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def isa(h: float) -> tuple[float, float, float]:
    t = 288.15 - 0.0065 * h
    p = 101325.0 * (t / 288.15) ** (9.80665 / (RHO_AIR * 0.0065))
    return t, p, p / (RHO_AIR * t)


def mass_flux(mach: float, p0: float, t0: float) -> float:
    f = 1.0 + 0.5 * (GAMMA - 1.0) * mach * mach
    return p0 / math.sqrt(t0) * math.sqrt(GAMMA / RHO_AIR) * mach ** (1.0 - 0.0) * f ** (-(GAMMA + 1.0) / (2.0 * (GAMMA - 1.0)))


def solve_mach(target: float, p0: float, t0: float) -> float:
    if target >= mass_flux(1.0, p0, t0):
        raise ValueError("requested mass flow reaches the ideal choking limit")
    lo, hi = 1e-10, 0.999999
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if mass_flux(mid, p0, t0) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def derive(cfg: dict[str, Any]) -> dict[str, Any]:
    p9_cfg = json.loads((ROOT / cfg["sources"]["phase9Config"]).read_text(encoding="utf-8"))
    meanline = json.loads((ROOT / cfg["sources"]["phase9Meanline"]).read_text(encoding="utf-8"))
    op, geo = cfg["operatingPoint"], cfg["geometry"]
    ts, ps, rho = isa(float(op["altitudeM"]))
    u = float(op["speedKmh"]) / 3.6
    mach = u / math.sqrt(GAMMA * RHO_AIR * ts)
    t0 = ts * (1.0 + 0.5 * (GAMMA - 1.0) * mach * mach)
    p0 = ps * (1.0 + 0.5 * (GAMMA - 1.0) * mach * mach) ** (GAMMA / (GAMMA - 1.0))
    count = int(geo["ductCount"])
    od, bore, hub = map(float, (geo["outerDiameterM"], geo["boreDiameterM"], geo["hubDiameterM"]))
    annulus = math.pi / 4.0 * (bore * bore - hub * hub)
    slot = float(geo["slotWidthM"]) * float(geo["slotLengthM"])
    mdot = float(meanline["massFlowTotalKgPerS"]) / count
    mflux_in, mflux_out = mdot / slot, mdot / annulus
    minlet = solve_mach(mflux_in, p0, t0)
    p0_target = p0 * float(op["targetTotalPressureRecovery"])
    mout = solve_mach(mflux_out, p0_target, t0)

    def static(pt: float, tt: float, m: float) -> tuple[float, float]:
        f = 1.0 + 0.5 * (GAMMA - 1.0) * m * m
        return pt / f ** (GAMMA / (GAMMA - 1.0)), tt / f

    pin, tin = static(p0, t0, minlet)
    pout, tout = static(p0_target, t0, mout)
    rhoin = pin / (RHO_AIR * tin)
    # The 90 mm duct projections are coincident from Phase 9's axial stagger,
    # so their front-view union is one circle, not a sum of two circles.
    p9_area = math.pi * (od / 2.0) ** 2 * 1e4
    return {
        "freestream": {"staticTemperatureK": ts, "staticPressurePa": ps, "densityKgM3": rho,
                       "speedMps": u, "mach": mach, "totalTemperatureK": t0, "totalPressurePa": p0},
        "branch": {"massFlowKgS": mdot, "slotAreaM2": slot, "annulusAreaM2": annulus,
                   "slotToAnnulusAreaRatio": slot / annulus, "inletMach": minlet,
                   "inletStaticPressurePa": pin, "inletStaticTemperatureK": tin,
                   "inletVolumeFlowM3S": mdot / rhoin, "outletMachAtTargetRecovery": mout,
                   "outletStaticPressurePa": pout, "outletStaticTemperatureK": tout,
                   "idealChokedMassFlowKgS": mass_flux(1.0, p0, t0) * annulus},
        "geometry": {"ductCount": count, "outerDiameterM": od, "boreDiameterM": bore,
                     "hubDiameterM": hub, "slotWidthM": float(geo["slotWidthM"]),
                     "slotLengthM": float(geo["slotLengthM"]),
                     "declaredSlotToAnnulusAreaRatio": float(p9_cfg["geometry"]["slotToFanAnnulusAreaRatio"])},
        "projectedArea": {"fanUnionCm2": p9_area,
                          "structureAllowanceCm2": float(p9_cfg["geometry"]["projectedStructureAllowanceCm2"]),
                          "slotWidthMm": float(geo["slotWidthM"]) * 1000.0},
        "sourceHashes": {key: sha256(ROOT / cfg["sources"][key]) for key in ("phase9Config", "phase9Meanline")}
    }


def rounded_wire(occ: Any, center_z: float, half_x: float, half_y: float, exponent: float,
                n: int = 48, phase: float = 0.0) -> int:
    pts = []
    power = 2.0 / exponent
    for i in range(n):
        a = 2.0 * math.pi * i / n + phase
        c, s = math.cos(a), math.sin(a)
        x = half_x * math.copysign(abs(c) ** power, c)
        y = half_y * math.copysign(abs(s) ** power, s)
        pts.append(occ.addPoint(x, y, center_z))
    edges = [occ.addLine(pts[i], pts[(i + 1) % n]) for i in range(n)]
    return occ.addWire(edges, checkClosed=True)


def make_case_mesh(case_dir: Path, case: dict[str, Any], state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    r = float(case["turnRadiusM"])
    slot_w, slot_l = float(state["geometry"]["slotWidthM"]), float(state["geometry"]["slotLengthM"])
    annulus_ro = float(state["geometry"]["boreDiameterM"]) / 2.0
    hub_r = float(state["geometry"]["hubDiameterM"]) / 2.0
    transition = float(cfg["geometry"]["transitionLengthM"])
    hmax = float(cfg["mesh"]["meshLevels"][case["meshLevel"]]["maxCellSizeM"])
    gmsh.initialize()
    try:
        for key, val in (("General.Terminal", 0), ("Mesh.MshFileVersion", 2.2), ("Mesh.ElementOrder", 1),
                         ("Mesh.MeshSizeMin", hmax * 0.75), ("Mesh.MeshSizeMax", hmax),
                         ("Mesh.MeshSizeFromCurvature", 1), ("Mesh.Algorithm3D", 10), ("Mesh.Optimize", 1)):
            gmsh.option.setNumber(key, val)
        gmsh.model.add(case["caseId"])
        occ = gmsh.model.occ

        # Slot plane is x=R. Its 120 mm axial dimension is radial in the turn
        # plane, so R>60 mm is the non-self-intersection bound for this topology.
        # Use the same rounded 48-edge perimeter at both sides of the elbow/loft
        # seam to avoid the sliver tets caused by the former 4-to-48 edge fuse.
        nsec = 48
        inletExponent = 6.0
        power = 2.0 / inletExponent
        inlet_pts = []
        for i in range(nsec):
            a = 2.0 * math.pi * i / nsec
            c, s = math.cos(a), math.sin(a)
            y = -slot_w/2 * math.copysign(abs(c) ** power, c)
            z = slot_l/2 * math.copysign(abs(s) ** power, s)
            inlet_pts.append(occ.addPoint(r, y, z))
        inlet_edges = [occ.addLine(inlet_pts[i], inlet_pts[(i + 1) % nsec]) for i in range(nsec)]
        inlet_face = occ.addPlaneSurface([occ.addWire(inlet_edges, checkClosed=True)])
        # Rotate about the lateral y-axis through (R,0,R): flow enters -x and
        # exits +z on the fan axis, matching the Phase-10 CadQuery bend layout.
        swept = occ.revolve([(2, inlet_face)], r, 0, r, 0, 1, 0, math.pi/2)
        elbow = [tag for dim, tag in swept if dim == 3]
        if len(elbow) != 1:
            raise RuntimeError(f"sweep returned {elbow}")

        wires = []
        profile = case["transitionProfile"]
        for i in range(5):
            f = i / 4.0
            t = f if profile == "linear" else 0.5 - 0.5 * math.cos(math.pi*f)
            hx = slot_l/2 * (1-t) + annulus_ro * t
            hy = slot_w/2 * (1-t) + annulus_ro * t
            exponent = 12.0 * (1-t) + 2.0*t
            exponent = 6.0 * (1.0-t) + 2.0*t
            wires.append(rounded_wire(occ, r + transition*f, hx, hy, exponent, phase=-math.pi/2))
        loft = occ.addThruSections(wires, makeSolid=True, makeRuled=True)
        loft_vol = [tag for dim, tag in loft if dim == 3]
        if len(loft_vol) != 1:
            raise RuntimeError(f"loft returned {loft_vol}")
        fused, _ = occ.fuse([(3, elbow[0])], [(3, loft_vol[0])], removeObject=True, removeTool=True)
        vols = [tag for dim, tag in fused if dim == 3]
        if len(vols) != 1:
            raise RuntimeError(f"fuse returned {vols}")
        hub = occ.addCone(0, 0, r, 0, 0, transition, 0.012, hub_r)
        cut, _ = occ.cut([(3, vols[0])], [(3, hub)], removeObject=True, removeTool=True)
        fluid = [tag for dim, tag in cut if dim == 3]
        if len(fluid) != 1:
            raise RuntimeError(f"hub cut returned {fluid}")
        occ.synchronize()

        faces = [tag for dim, tag in gmsh.model.getBoundary([(3, fluid[0])], combined=False, oriented=False) if dim == 2]
        inlet, outlet, walls = [], [], []
        z_out = r + transition
        tol = 2e-6
        for face in faces:
            bb = gmsh.model.getBoundingBox(2, face)
            if abs(bb[0]-r) < tol and abs(bb[3]-r) < tol:
                inlet.append(face)
            elif abs(bb[2]-z_out) < tol and abs(bb[5]-z_out) < tol:
                outlet.append(face)
            else:
                walls.append(face)
        if not inlet or not outlet or not walls:
            raise RuntimeError(f"missing physical patches: inlet={inlet}, outlet={outlet}, walls={len(walls)}")
        gmsh.model.addPhysicalGroup(3, fluid, 1)
        gmsh.model.setPhysicalName(3, 1, "fluid")
        for tag, name, entities in ((11, "inlet", inlet), (12, "outlet", outlet), (13, "walls", walls)):
            gmsh.model.addPhysicalGroup(2, entities, tag)
            gmsh.model.setPhysicalName(2, tag, name)
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.optimize("Relocate3D")
        gmsh.model.mesh.optimize("Netgen")
        node_tags, node_xyz, _ = gmsh.model.mesh.getNodes()
        element_types, element_groups, connectivity_groups = gmsh.model.mesh.getElements(3)
        cell_tags = [tag for group in element_groups for tag in group]
        quality = [float(q) for q in gmsh.model.mesh.getElementQualities(cell_tags, "minSICN")] if cell_tags else []
        sorted_quality = sorted(quality)
        min_quality_point = None
        if quality:
            worst_index = min(range(len(quality)), key=quality.__getitem__)
            cumulative = 0
            for tags, connectivity in zip(element_groups, connectivity_groups):
                if worst_index < cumulative + len(tags):
                    node_ids = connectivity[(worst_index-cumulative)*4:(worst_index-cumulative+1)*4]
                    coords_by_tag = {int(node_tags[i]): node_xyz[3*i:3*i+3] for i in range(len(node_tags))}
                    points = [coords_by_tag[int(tag)] for tag in node_ids]
                    min_quality_point = [sum(p[d] for p in points)/len(points) for d in range(3)]
                    break
                cumulative += len(tags)
        gmsh.write(str(case_dir / "mesh.msh"))
        return {"nodeCount": len(node_tags), "tetraCellCount": len(cell_tags),
                "minSICN": min(quality) if quality else None,
                "p10SICN": sorted_quality[int(0.10*(len(sorted_quality)-1))] if sorted_quality else None,
                "cellsSICNBelow0p05": sum(q < 0.05 for q in quality),
                "minQualityCellCentroidM": min_quality_point,
                "physicalFaceCounts": {"inlet": len(inlet), "outlet": len(outlet), "walls": len(walls)}}
    finally:
        gmsh.finalize()


def prepare_cases(only_case: str | None = None) -> dict[str, Any]:
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    state = derive(cfg)
    p11_templates = P11 / "templates" / "openfoam"
    if p11_templates.exists():
        shutil.rmtree(p11_templates)
    shutil.copytree(ROOT / "phase10" / "templates" / "openfoam", p11_templates)
    cases = [case for case in cfg["cases"] if only_case is None or case["id"] == only_case]
    if only_case and not cases:
        raise ValueError(f"Unknown case {only_case}")
    rows = []
    for item in cases:
        case_dir = P11 / "cases" / item["id"]
        if case_dir.exists():
            shutil.rmtree(case_dir)
        case_dir.mkdir(parents=True)
        case = {**item,
                "caseId": item["id"],
                "slotWidthM": state["geometry"]["slotWidthM"],
                "slotLengthM": state["geometry"]["slotLengthM"],
                "outerDiameterM": state["geometry"]["outerDiameterM"],
                "boreDiameterM": state["geometry"]["boreDiameterM"],
                "hubDiameterM": state["geometry"]["hubDiameterM"],
                "transitionLengthM": cfg["geometry"]["transitionLengthM"],
                "maxCellSizeM": cfg["mesh"]["meshLevels"][item["meshLevel"]]["maxCellSizeM"],
                "totalPressurePa": state["freestream"]["totalPressurePa"],
                "totalTemperatureK": state["freestream"]["totalTemperatureK"],
                "targetMassFlowKgPerS": state["branch"]["massFlowKgS"],
                "targetRecovery": cfg["operatingPoint"]["targetTotalPressureRecovery"],
                "maxCellSizeM": cfg["mesh"]["meshLevels"][item["meshLevel"]]["maxCellSizeM"]}
        substitutions = {
            "@P_OUT@": f"{state['branch']['outletStaticPressurePa']:.10g}",
            "@P0@": f"{state['freestream']['totalPressurePa']:.10g}",
            "@P_IN@": f"{state['branch']['inletStaticPressurePa']:.10g}",
            "@U_IN@": f"{state['branch']['inletVolumeFlowM3S']/state['branch']['slotAreaM2']:.10g}",
            "@Q_IN@": f"{state['branch']['inletVolumeFlowM3S']:.10g}",
            "@T_OUT@": f"{state['branch']['outletStaticTemperatureK']:.10g}",
            "@T0@": f"{state['freestream']['totalTemperatureK']:.10g}",
            "@T_IN@": f"{state['branch']['inletStaticTemperatureK']:.10g}",
        }
        u_in = state["branch"]["inletVolumeFlowM3S"] / state["branch"]["slotAreaM2"]
        k = max(1.5 * (0.05*u_in)**2, 1e-5)
        omega = math.sqrt(k) / (0.09**0.25 * 0.07 * (state["geometry"]["boreDiameterM"]-state["geometry"]["hubDiameterM"]))
        substitutions["@K_IN@"] = f"{k:.10g}"
        substitutions["@OMEGA_IN@"] = f"{omega:.10g}"
        for src in p11_templates.rglob("*"):
            if not src.is_file():
                continue
            dst = case_dir / src.relative_to(p11_templates)
            dst.parent.mkdir(parents=True, exist_ok=True)
            text = src.read_text(encoding="utf-8")
            for key, value in substitutions.items():
                text = text.replace(key, value)
            # Flight flow enters from the positive side toward the centerline (-x).
            if dst.as_posix().endswith("/0/U"):
                text = text.replace(f"(0 {substitutions['@U_IN@']} 0)", f"(-{substitutions['@U_IN@']} 0 0)")
            dst.write_text(text, encoding="utf-8")
        mesh = make_case_mesh(case_dir, case, state, cfg)
        case["meshEvidence"] = mesh
        (case_dir / "case.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
        rows.append({"caseId": item["id"], "turnRadiusMm": item["turnRadiusM"]*1000.0,
                     "profile": item["transitionProfile"], "meshLevel": item["meshLevel"],
                     "cellSizeMm": case["maxCellSizeM"]*1000.0, "cells": mesh["tetraCellCount"],
                     "minSICN": mesh["minSICN"], "solverStatus": "prepared_not_run",
                     "pressureRecovery": None})
    if only_case is None:
        out = P11 / "results"
        out.mkdir(parents=True, exist_ok=True)
        with (out / "phase11_case_matrix.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        radius_limit_for_area = 45.0 + (float(cfg["geometry"]["projectedAreaGateCm2"])
            - state["projectedArea"]["fanUnionCm2"] - state["projectedArea"]["structureAllowanceCm2"])
        min_turn_radius = float(cfg["geometry"]["slotLengthM"]) * 500.0
        gates = []
        for item in cfg["cases"]:
            extra = max(0.0, (float(item["turnRadiusM"])*1000.0 - 45.0) * 2.0 * 50.0 / 100.0)
            full_lb = state["projectedArea"]["fanUnionCm2"] + state["projectedArea"]["structureAllowanceCm2"] + extra
            gates.append({"caseId": item["id"], "radiusMm": item["turnRadiusM"]*1000.0,
                          "projectedAreaLowerBoundCm2": full_lb, "projectedAreaPass": full_lb < 75.0,
                          "selfIntersectionRadiusPass": item["turnRadiusM"]*1000.0 > min_turn_radius})
        preflight = {"phase": 11, "createdAtUtc": datetime.now(UTC).isoformat(),
                     "status": "meshed_cloud_solver_pending", "sourceHashes": state["sourceHashes"],
                     "freestream": state["freestream"], "branch": state["branch"],
                     "geometryChecks": gates,
                     "projectedAreaRadiusMaximumMm": radius_limit_for_area,
                     "geometricMinimumTurnRadiusMm": min_turn_radius,
                     "areaVsTurnFeasibility": "No current full-height single-quarter-turn radius satisfies both constraints; topology/cross-section must change.",
                     "cases": rows,
                     "totalMeshCells": sum(x["cells"] for x in rows)}
        (out / "phase11_preflight.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
    return {"state": state, "cases": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-case")
    args = parser.parse_args()
    result = prepare_cases(args.only_case)
    print(json.dumps({"caseCount": len(result["cases"]), "cases": result["cases"],
                      "freestream": result["state"]["freestream"], "branch": result["state"]["branch"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
