#!/usr/bin/env python3
"""Build Phase-13 local Gmsh meshes and OpenFOAM rhoSimpleFoam cases."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gmsh

PHASE = Path(__file__).resolve().parents[1]
EDF_ROOT = PHASE.parent
CONFIG = PHASE / "configs" / "phase13_split_inlet_recovery.json"
TEMPLATES = PHASE / "templates" / "openfoam"
UTC = timezone.utc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_path(relative: str) -> Path:
    path = EDF_ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(f"required Phase-13 source is missing: {path}")
    return path


def isa(altitude_m: float, gas_r: float) -> tuple[float, float, float]:
    temperature = 288.15 - 0.0065 * altitude_m
    pressure = 101325.0 * (temperature / 288.15) ** (9.80665 / (gas_r * 0.0065))
    return temperature, pressure, pressure / (gas_r * temperature)


def compressible_mass_flux(mach: float, total_pressure: float, total_temperature: float,
                           gamma: float, gas_r: float) -> float:
    f = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
    return (total_pressure / math.sqrt(total_temperature) * math.sqrt(gamma / gas_r)
            * mach * f ** (-(gamma + 1.0) / (2.0 * (gamma - 1.0))))


def mach_for_flux(target_flux: float, total_pressure: float, total_temperature: float,
                  gamma: float, gas_r: float) -> float:
    if target_flux <= 0.0 or target_flux >= compressible_mass_flux(
            1.0, total_pressure, total_temperature, gamma, gas_r):
        raise ValueError("requested inlet mass flux must be positive and below ideal choking")
    low, high = 1e-9, 0.999999
    for _ in range(90):
        mid = 0.5 * (low + high)
        if compressible_mass_flux(mid, total_pressure, total_temperature, gamma, gas_r) < target_flux:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def static_state(total_pressure: float, total_temperature: float, mach: float,
                 gamma: float) -> tuple[float, float]:
    factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
    return total_pressure / factor ** (gamma / (gamma - 1.0)), total_temperature / factor


def derive(cfg: dict[str, Any]) -> dict[str, Any]:
    phase9_config_path = source_path(cfg["sources"]["phase9Config"])
    meanline_path = source_path(cfg["sources"]["phase9Meanline"])
    areas_path = source_path(cfg["sources"]["phase12FrontAreaVariants"])
    phase9 = json.loads(phase9_config_path.read_text(encoding="utf-8"))
    meanline = json.loads(meanline_path.read_text(encoding="utf-8"))
    with areas_path.open(newline="", encoding="utf-8") as stream:
        area_rows = list(csv.DictReader(stream))

    op, geom = cfg["operatingPoint"], cfg["geometry"]
    gamma = float(op["gamma"])
    gas_r = float(op["gasConstantJPerKgK"])
    static_t, static_p, density = isa(float(op["altitudeM"]), gas_r)
    speed = float(op["speedKmh"]) / 3.6
    flight_mach = speed / math.sqrt(gamma * gas_r * static_t)
    total_t = static_t * (1.0 + 0.5 * (gamma - 1.0) * flight_mach**2)
    total_p = static_p * (1.0 + 0.5 * (gamma - 1.0) * flight_mach**2) ** (
        gamma / (gamma - 1.0)
    )

    ducts = int(geom["ductCount"])
    slots_per_duct = int(geom["slotsPerDuct"])
    branch_count = ducts * slots_per_duct
    branch_mdot = float(meanline["massFlowTotalKgPerS"]) / branch_count
    duct_area = math.pi / 4.0 * (
        float(geom["ductOuterDiameterM"])**2 - float(geom["hubDiameterM"])**2
    )
    branch_area = duct_area / slots_per_duct
    slot_area = float(geom["slotWidthM"]) * float(geom["slotLengthM"])
    inlet_mach = mach_for_flux(branch_mdot / slot_area, total_p, total_t, gamma, gas_r)
    inlet_p, inlet_t = static_state(total_p, total_t, inlet_mach, gamma)
    inlet_rho = inlet_p / (gas_r * inlet_t)
    inlet_speed = branch_mdot / (inlet_rho * slot_area)

    area_by_radius: dict[int, dict[str, Any]] = {}
    area_limit = float(cfg["projectedAreaGate"]["maximumCm2"])
    for row in area_rows:
        radius = int(round(float(row["radiusMm"])))
        area = float(row["frontProjectedAreaCm2"])
        pass_gate = area <= area_limit
        recorded_pass = row["gate75Pass"].strip().lower() == "true"
        if radius in area_by_radius or area <= 0.0 or pass_gate != recorded_pass:
            raise ValueError(f"Phase-12 CAD projected-area report is invalid at R{radius:03d}")
        area_by_radius[radius] = {
            "radiusMm": radius,
            "completeProjectedAreaCm2": area,
            "areaGatePass": pass_gate,
            "initialVariant": row["initialVariant"].strip().lower() == "true",
            "recoveryEvidence": row["recoveryEvidence"],
        }

    variants = []
    for item in cfg["cases"]:
        radius_mm = int(round(float(item["turnRadiusM"]) * 1000.0))
        area = area_by_radius.get(radius_mm)
        if area is None or not area["areaGatePass"]:
            raise ValueError(f"R{radius_mm:03d} is missing authoritative CAD area below 75 cm2")
        variants.append({**area, "caseId": item["id"]})

    powertrain = phase9["powertrainImmutable"]
    return {
        "sourceHashes": {
            "phase9Config": sha256(phase9_config_path),
            "phase9Meanline": sha256(meanline_path),
            "phase12FrontAreaVariants": sha256(areas_path),
            "phase13Config": sha256(CONFIG),
        },
        "powertrain": {
            "batteryConfiguration": cfg["fixedPowertrain"]["batteryConfiguration"],
            "phase9BatteryDescription": powertrain["battery"],
            "motor": powertrain["motor"],
            "immutable": True,
        },
        "freestream": {
            "altitudeM": float(op["altitudeM"]),
            "speedMps": speed,
            "staticTemperatureK": static_t,
            "staticPressurePa": static_p,
            "densityKgM3": density,
            "mach": flight_mach,
            "totalTemperatureK": total_t,
            "totalPressurePa": total_p,
        },
        "branch": {
            "branchesTotal": branch_count,
            "massFlowKgS": branch_mdot,
            "slotAreaM2": slot_area,
            "branchOutletAreaM2": branch_area,
            "inletMassFluxKgM2S": branch_mdot / slot_area,
            "inletMachAtTargetFlow": inlet_mach,
            "inletStaticPressurePa": inlet_p,
            "inletStaticTemperatureK": inlet_t,
            "inletDensityKgM3": inlet_rho,
            "inletSpeedMs": inlet_speed,
            "inletVelocityVectorMs": [-inlet_speed, 0.0, 0.0],
            "outletStaticPressurePa": static_p,
        },
        "annulus": {
            "perDuctAreaM2": duct_area,
            "perDuctAreaCm2": duct_area * 1.0e4,
            "perBranchAreaM2": branch_area,
            "perBranchAreaCm2": branch_area * 1.0e4,
            "halfAnnulusAnalyticAreaM2": 0.5 * math.pi * (
                (float(geom["ductOuterDiameterM"]) / 2.0)**2
                - (float(geom["hubDiameterM"]) / 2.0)**2
            ),
        },
        "projectedArea": {
            "maximumCm2": area_limit,
            "source": cfg["sources"]["phase12FrontAreaVariants"],
            "variants": variants,
        },
        "geometry": geom,
    }


def rectangle_profile(width: float, height: float, n: int = 32) -> list[tuple[float, float]]:
    """Rectangle loop split into aligned right- and left-half paths."""
    if n % 8:
        raise ValueError("rectangle profile point count must be divisible by eight")
    quarter, half_top = n // 4, n // 8
    sides = (
        (0.0, height / 2.0, width / 2.0, height / 2.0, half_top),
        (width / 2.0, height / 2.0, width / 2.0, -height / 2.0, quarter),
        (width / 2.0, -height / 2.0, -width / 2.0, -height / 2.0, quarter),
        (-width / 2.0, -height / 2.0, -width / 2.0, height / 2.0, quarter),
        (-width / 2.0, height / 2.0, 0.0, height / 2.0, half_top),
    )
    points: list[tuple[float, float]] = []
    for x0, y0, x1, y1, count in sides:
        for i in range(count):
            fraction = i / count
            points.append((x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction))
    return points


def half_annulus_profile(outer_radius: float, inner_radius: float,
                         n: int = 32) -> list[tuple[float, float]]:
    """Right semicircular annulus; the diameter is the splitter face at x=0."""
    if n % 8 or not 0.0 < inner_radius < outer_radius:
        raise ValueError("invalid half-annulus profile dimensions")
    half = n // 2
    points: list[tuple[float, float]] = []
    for i in range(half):
        angle = math.pi * i / (half - 1)
        points.append((outer_radius * math.sin(angle), outer_radius * math.cos(angle)))
    for i in range(half):
        angle = math.pi - math.pi * i / (half - 1)
        points.append((inner_radius * math.sin(angle), inner_radius * math.cos(angle)))
    return points


def polygon_area(points: list[tuple[float, float]]) -> float:
    return abs(sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    ) / 2.0)


def add_section_wire(occ: Any, z: float, points: list[tuple[float, float]]) -> int:
    point_tags = [occ.addPoint(x, y, z) for x, y in points]
    edge_tags = [occ.addLine(point_tags[i], point_tags[(i + 1) % len(point_tags)])
                 for i in range(len(point_tags))]
    return occ.addWire(edge_tags, checkClosed=True)


def build_mesh(case_dir: Path, case: dict[str, Any], state: dict[str, Any],
               cfg: dict[str, Any]) -> dict[str, Any]:
    radius = float(case["turnRadiusM"])
    geom = state["geometry"]
    slot_width = float(geom["slotWidthM"])
    slot_length = float(geom["slotLengthM"])
    radial_height = float(geom["splitTurnHeightM"])
    transition = float(geom["transitionLengthM"])
    outer_r = float(geom["ductOuterDiameterM"]) / 2.0
    inner_r = float(geom["hubDiameterM"]) / 2.0
    outlet_profile = half_annulus_profile(outer_r, inner_r)
    if not math.isclose(slot_width, radial_height, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("slot width and bend-plane height must agree for the Phase-13 sweep")
    # The slot span lies on global y and its bend-plane width on global z.
    inlet_profile = rectangle_profile(slot_length, slot_width)
    inlet_area = polygon_area(inlet_profile)
    outlet_area = polygon_area(outlet_profile)
    analytic_outlet_area = state["annulus"]["halfAnnulusAnalyticAreaM2"]
    outlet_area_error = abs(outlet_area - analytic_outlet_area) / analytic_outlet_area
    if not math.isclose(inlet_area, slot_width * slot_length, rel_tol=1e-10):
        raise ValueError("slot polygon does not preserve the 25x120 mm opening")
    if outlet_area_error > float(cfg["mesh"]["maximumOutletAreaErrorFraction"]):
        raise ValueError(f"polygonal half-annulus error {outlet_area_error:.3%} exceeds its gate")

    size = float(cfg["mesh"]["targetSizeM"])
    gmsh.initialize()
    try:
        for key, value in (
            ("General.Terminal", 0),
            ("General.NumThreads", 2),
            ("Mesh.MshFileVersion", 2.2),
            ("Mesh.ElementOrder", 1),
            ("Mesh.MeshSizeMin", size * 0.75),
            ("Mesh.MeshSizeMax", size),
            ("Mesh.MeshSizeFromCurvature", 1),
            ("Mesh.Algorithm3D", 10),
            ("Mesh.Optimize", 0),
        ):
            gmsh.option.setNumber(key, value)
        gmsh.model.add(case["caseId"])
        occ = gmsh.model.occ

        # Inlet plane x=R; spanwise dimension is 120 mm and bend-plane height is 25 mm.
        inlet_points = [occ.addPoint(radius, span, height) for span, height in inlet_profile]
        inlet_edges = [occ.addLine(inlet_points[i], inlet_points[(i + 1) % len(inlet_points)])
                       for i in range(len(inlet_points))]
        inlet_face = occ.addPlaneSurface([occ.addWire(inlet_edges, checkClosed=True)])

        # Centerline runs from (R,0,0) to (0,0,R), turning about a y-parallel axis.
        swept = occ.revolve([(2, inlet_face)], radius, 0.0, radius,
                            0.0, 1.0, 0.0, math.pi / 2.0)
        elbow_volumes = [tag for dim, tag in swept if dim == 3]
        if len(elbow_volumes) != 1:
            raise RuntimeError(f"quarter-turn sweep did not make exactly one volume: {elbow_volumes}")
        elbow_volume = elbow_volumes[0]

        sections = []
        for index in range(5):
            fraction = index / 4.0
            smooth = fraction * fraction * (3.0 - 2.0 * fraction)
            rect = rectangle_profile(radial_height, slot_length)
            profile = [
                (a * (1.0 - smooth) + b * smooth,
                 c * (1.0 - smooth) + d * smooth)
                for (a, c), (b, d) in zip(rect, outlet_profile)
            ]
            sections.append(add_section_wire(occ, radius + transition * fraction, profile))
        loft_result = occ.addThruSections(sections, makeSolid=True, makeRuled=True)
        loft_volumes = [tag for dim, tag in loft_result if dim == 3]
        if len(loft_volumes) != 1:
            raise RuntimeError(f"smoothstep transition did not make exactly one volume: {loft_volumes}")
        fused, _ = occ.fuse([(3, elbow_volume)], [(3, loft_volumes[0])],
                            removeObject=True, removeTool=True)
        fluid_volumes = [tag for dim, tag in fused if dim == 3]
        if len(fluid_volumes) != 1:
            raise RuntimeError(f"elbow/loft did not fuse into one fluid volume: {fluid_volumes}")
        fluid = fluid_volumes[0]
        occ.synchronize()
        fluid_volume = occ.getMass(3, fluid)
        if not math.isfinite(fluid_volume) or fluid_volume <= 0.0:
            raise RuntimeError(f"invalid fluid volume {fluid_volume}")

        faces = [tag for dim, tag in gmsh.model.getBoundary(
            [(3, fluid)], combined=False, oriented=False
        ) if dim == 2]
        inlet_faces: list[int] = []
        outlet_faces: list[int] = []
        walls: list[int] = []
        outlet_z = radius + transition
        for face in faces:
            bounds = gmsh.model.getBoundingBox(2, face)
            if abs(bounds[0] - radius) < 2e-6 and abs(bounds[3] - radius) < 2e-6:
                inlet_faces.append(face)
            elif abs(bounds[2] - outlet_z) < 2e-6 and abs(bounds[5] - outlet_z) < 2e-6:
                outlet_faces.append(face)
            else:
                walls.append(face)
        if not inlet_faces or not outlet_faces or not walls:
            raise RuntimeError(
                "missing physical boundary surfaces: "
                f"inlet/outlet/walls={len(inlet_faces)}/{len(outlet_faces)}/{len(walls)}"
            )

        gmsh.model.addPhysicalGroup(3, [fluid], 1)
        gmsh.model.setPhysicalName(3, 1, "fluid")
        for tag, name, entities in (
            (11, "inlet", inlet_faces), (12, "outlet", outlet_faces), (13, "walls", walls)
        ):
            gmsh.model.addPhysicalGroup(2, entities, tag)
            gmsh.model.setPhysicalName(2, tag, name)

        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.optimize("Relocate3D")
        gmsh.model.mesh.optimize("Netgen")
        nodes, _, _ = gmsh.model.mesh.getNodes()
        element_types, element_tags, _ = gmsh.model.mesh.getElements(3)
        volume_cells = sum(len(tags) for tags in element_tags)
        tetra_tags = [int(tag) for kind, tags in zip(element_types, element_tags)
                      if gmsh.model.mesh.getElementProperties(kind)[0].lower().startswith("tetra")
                      for tag in tags]
        qualities = [float(value) for value in gmsh.model.mesh.getElementQualities(
            tetra_tags, "minSICN"
        )] if tetra_tags else []
        if volume_cells < int(cfg["mesh"]["minimumCells"]):
            raise RuntimeError(f"mesh has {volume_cells} cells; minimum is {cfg['mesh']['minimumCells']}")
        if not qualities or min(qualities) < float(cfg["mesh"]["minimumSICN"]):
            raise RuntimeError(
                f"mesh minSICN {min(qualities) if qualities else None} fails "
                f"{cfg['mesh']['minimumSICN']} quality gate"
            )
        gmsh.write(str(case_dir / "mesh.msh"))
        return {
            "nodes": len(nodes),
            "volumeCells": volume_cells,
            "tetraCells": len(tetra_tags),
            "minSICN": min(qualities),
            "meanSICN": sum(qualities) / len(qualities),
            "cellsSICNBelow0p05": sum(q < 0.05 for q in qualities),
            "fluidVolumeM3": fluid_volume,
            "inletSectionAreaM2": inlet_area,
            "outletSectionAreaM2": outlet_area,
            "outletSectionAnalyticAreaM2": analytic_outlet_area,
            "outletSectionAreaErrorFraction": outlet_area_error,
            "inletSectionDimensionsMm": [slot_width * 1000.0, slot_length * 1000.0],
            "outletSection": "semicircular annulus, 90 mm OD / 32 mm ID",
            "geometryShapeChecks": {
                "singleFusedFluidVolume": True,
                "positiveFluidVolume": True,
                "matchingSlotAndTurnHeight": True,
                "smoothstepSectionCorrespondence": len(inlet_profile) == len(outlet_profile),
                "physicalFaceCounts": {
                    "inlet": len(inlet_faces), "outlet": len(outlet_faces), "walls": len(walls)
                },
            },
        }
    finally:
        gmsh.finalize()


def dictionary_preflight(case_dir: Path) -> dict[str, Any]:
    required = [
        "0/p", "0/U", "0/T", "0/k", "0/omega", "0/nut", "0/alphat",
        "constant/thermophysicalProperties", "constant/turbulenceProperties",
        "system/controlDict", "system/fvSchemes", "system/fvSolution",
        "system/changeDictionaryDict", "system/meshQualityDict",
    ]
    missing = [relative for relative in required if not (case_dir / relative).is_file()]
    braces: dict[str, int] = {}
    texts: dict[str, str] = {}
    for relative in required:
        path = case_dir / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        texts[relative] = text
        stripped = re.sub(r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"])*\"", "", text,
                          flags=re.M | re.S)
        braces[relative] = stripped.count("{") - stripped.count("}")
    change = texts.get("system/changeDictionaryDict", "")
    direct_wall_fix = bool(re.search(
        r"dictionaryReplacement\s*\{\s*boundary\s*\{\s*walls\s*\{\s*type\s+wall\s*;",
        change, flags=re.S,
    ))
    pressure = texts.get("0/p", "")
    velocity = texts.get("0/U", "")
    pressure_bc = (
        bool(re.search(r"inlet\s*\{\s*type\s+fixedValue\s*;", pressure, flags=re.S))
        and bool(re.search(r"outlet\s*\{\s*type\s+fixedValue\s*;", pressure, flags=re.S))
        and "totalPressure" not in pressure
    )
    velocity_bc = bool(re.search(
        r"inlet\s*\{\s*type\s+fixedValue\s*;", velocity, flags=re.S
    )) and "pressureInletOutletVelocity" in velocity
    unresolved = sorted({token for text in texts.values()
                         for token in re.findall(r"@[A-Z0-9_]+@", text)})
    return {
        "allRequiredFilesPresent": not missing,
        "missing": missing,
        "braceBalance": braces,
        "allBracesBalanced": all(value == 0 for value in braces.values()),
        "directWallPatchTypeReplacementValid": direct_wall_fix,
        "pressureBoundaryConditionsUseStaticPressureNotTargetRecovery": pressure_bc,
        "fixedInletVelocityAndPressureOutletVelocityConditionsPresent": velocity_bc,
        "unresolvedTemplateTokens": unresolved,
    }


def write_case(case_item: dict[str, Any], state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    case_id = case_item["id"]
    case_dir = PHASE / "cases" / case_id
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True)
    branch = state["branch"]
    freestream = state["freestream"]
    rho = branch["inletDensityKgM3"]
    speed = branch["inletSpeedMs"]
    turbulence_intensity = 0.05
    length_scale = 0.07 * float(cfg["geometry"]["slotWidthM"])
    kinetic = max(1.5 * (turbulence_intensity * speed) ** 2, 1e-5)
    omega = math.sqrt(kinetic) / (0.09**0.25 * length_scale)
    substitutions = {
        "@P_IN@": f"{branch['inletStaticPressurePa']:.10g}",
        "@P_OUT_STATIC@": f"{branch['outletStaticPressurePa']:.10g}",
        "@P_INITIAL@": f"{0.5 * (branch['inletStaticPressurePa'] + branch['outletStaticPressurePa']):.10g}",
        "@U_IN_X@": f"{-speed:.10g}",
        "@U_OUT_INITIAL@": "0",
        "@T_IN@": f"{branch['inletStaticTemperatureK']:.10g}",
        "@T_INITIAL@": f"{0.5 * (branch['inletStaticTemperatureK'] + freestream['staticTemperatureK']):.10g}",
        "@K_IN@": f"{kinetic:.10g}",
        "@OMEGA_IN@": f"{omega:.10g}",
    }
    for source in TEMPLATES.rglob("*"):
        if not source.is_file():
            continue
        target = case_dir / source.relative_to(TEMPLATES)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8")
        for key, value in substitutions.items():
            text = text.replace(key, value)
        target.write_text(text, encoding="utf-8")

    projected = next(
        item for item in state["projectedArea"]["variants"]
        if item["caseId"] == case_id
    )
    case = {
        **case_item,
        "caseId": case_id,
        "radiusMm": float(case_item["turnRadiusM"]) * 1000.0,
        "targetMassFlowKgPerS": branch["massFlowKgS"],
        "targetBranchCount": state["branch"]["branchesTotal"],
        "inletVelocityMagnitudeMs": speed,
        "inletStaticPressurePa": branch["inletStaticPressurePa"],
        "inletStaticTemperatureK": branch["inletStaticTemperatureK"],
        "outletStaticPressurePa": branch["outletStaticPressurePa"],
        "freestreamTotalPressurePa": freestream["totalPressurePa"],
        "completeProjectedAreaCm2": projected["completeProjectedAreaCm2"],
        "projectedAreaGatePass": projected["areaGatePass"],
        "turbulenceInitialK": kinetic,
        "turbulenceInitialOmega": omega,
    }
    mesh = build_mesh(case_dir, case, state, cfg)
    syntax = dictionary_preflight(case_dir)
    static_ok = (
        syntax["allRequiredFilesPresent"] and syntax["allBracesBalanced"]
        and syntax["directWallPatchTypeReplacementValid"]
        and syntax["pressureBoundaryConditionsUseStaticPressureNotTargetRecovery"]
        and syntax["fixedInletVelocityAndPressureOutletVelocityConditionsPresent"]
        and not syntax["unresolvedTemplateTokens"]
    )
    if not static_ok:
        raise RuntimeError(f"static OpenFOAM dictionary preflight failed for {case_id}: {syntax}")
    case["meshEvidence"] = mesh
    case["dictionaryPreflight"] = syntax
    (case_dir / "case.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
    return {
        "caseId": case_id,
        "turnRadiusMm": case["radiusMm"],
        "transitionProfile": case["transitionProfile"],
        "meshLevel": case["meshLevel"],
        "nodes": mesh["nodes"],
        "volumeCells": mesh["volumeCells"],
        "tetraCells": mesh["tetraCells"],
        "minSICN": mesh["minSICN"],
        "outletSectionAreaErrorFraction": mesh["outletSectionAreaErrorFraction"],
        "fluidVolumeM3": mesh["fluidVolumeM3"],
        "physicalFaceCounts": mesh["geometryShapeChecks"]["physicalFaceCounts"],
        "completeProjectedAreaCm2": case["completeProjectedAreaCm2"],
        "projectedAreaGatePass": case["projectedAreaGatePass"],
        "localOpenFOAMCheckMesh": None,
        "localDictionaryStaticCheckPass": static_ok,
        "remoteCheckMeshStatus": "required_before_solver",
        "solverStatus": "prepared_not_run",
        "pressureRecovery": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-case")
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    selected = [item for item in cfg["cases"] if not args.only_case or item["id"] == args.only_case]
    if args.only_case and not selected:
        raise ValueError(f"unknown Phase-13 case: {args.only_case}")
    if not TEMPLATES.is_dir():
        raise FileNotFoundError(f"Phase-13 OpenFOAM templates are missing: {TEMPLATES}")
    state = derive(cfg)
    rows = [write_case(item, state, cfg) for item in selected]

    results = PHASE / "results"
    results.mkdir(parents=True, exist_ok=True)
    if not args.only_case:
        with (results / "phase13_case_matrix.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        checkmesh_available = bool(shutil.which("checkMesh"))
        cost = cfg["cloudBudget"]
        local_geometry_pass = all(
            row["projectedAreaGatePass"] and row["minSICN"] >= cfg["mesh"]["minimumSICN"]
            and row["volumeCells"] >= cfg["mesh"]["minimumCells"]
            and row["localDictionaryStaticCheckPass"]
            for row in rows
        )
        preflight = {
            "phase": 13,
            "createdAtUtc": datetime.now(UTC).isoformat(),
            "status": "local-gmsh-and-dictionary-preflight-remote-checkmesh-required",
            "evidenceClass": "Local geometry/mesh and lexical dictionary validation; no local OpenFOAM checkMesh or CFD claim",
            "sources": state,
            "cases": rows,
            "localToolAvailability": {
                "gmshPython": gmsh.__version__,
                "checkMeshOnPath": checkmesh_available,
            },
            "launchGate": {
                "localGmshGeometryAndShapeChecksPass": local_geometry_pass,
                "localStaticDictionaryChecksPass": all(row["localDictionaryStaticCheckPass"] for row in rows),
                "localCheckMeshRequired": False,
                "remoteCheckMeshRequired": True,
                "remoteCheckMeshRunnerMustGateSolver": True,
                "allCompleteCadProjectionsBelow75Cm2": all(row["projectedAreaGatePass"] for row in rows),
                "maximumNewConservativeEstimateUsd": cost["aggregateEstimateUsd"],
                "cumulativeConservativeEstimateUsd": cost["priorEstimatedEnvelopeUsd"] + cost["aggregateEstimateUsd"],
                "withinApprovedNewAndTotalEstimates": (
                    cost["aggregateEstimateUsd"] <= cost["approvedNewEnvelopeUsd"]
                    and cost["priorEstimatedEnvelopeUsd"] + cost["aggregateEstimateUsd"]
                    <= cost["approvedTotalEnvelopeUsd"]
                ),
                "launchPermittedAfterCloudBillingAndResourcePreflight": False,
                "pendingGates": [
                    "single-Spot-VM billing/resource configuration preflight",
                    "remote gmshToFoam, direct wall-patch changeDictionary, and real checkMesh",
                ],
            },
            "costPlan": cost,
        }
        (results / "phase13_preflight.json").write_text(
            json.dumps(preflight, indent=2) + "\n", encoding="utf-8"
        )
        cost_plan = {
            "phase": 13,
            "status": "bounded-conservative-estimate-awaiting-cloud-preflight",
            "approvedRemainingNewEnvelopeUsd": cost["approvedNewEnvelopeUsd"],
            "priorPhase10And11EnvelopeEstimateUsd": cost["priorEstimatedEnvelopeUsd"],
            "computeMaximumUsd": cost["computeMaximumUsd"],
            "ancillaryAllowanceUsd": cost["ancillaryAllowanceUsd"],
            "newConservativeEstimateUsd": cost["aggregateEstimateUsd"],
            "cumulativeConservativeEstimateUsd": cost["priorEstimatedEnvelopeUsd"] + cost["aggregateEstimateUsd"],
            "approvedTotalEnvelopeUsd": cost["approvedTotalEnvelopeUsd"],
            "maximumInstanceCount": cost["maxInstancesTotal"],
            "machineType": cost["machineType"],
            "provisioningModel": cost["provisioningModel"],
            "maximumLifetimeSeconds": cost["maxRunDurationSeconds"],
            "terminationAction": cost["terminationAction"],
            "bootDiskGb": cost["bootDiskGb"],
            "bootDiskAutoDelete": cost["bootDiskAutoDelete"],
            "calculation": cost["calculation"],
            "actualBillingAmountUsd": None,
        }
        (results / "phase13_cost_plan.json").write_text(
            json.dumps(cost_plan, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({"state": state, "cases": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
