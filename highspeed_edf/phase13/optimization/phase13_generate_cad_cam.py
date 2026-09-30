#!/usr/bin/env python3
"""Generate Phase-13 EDF / airframe STEP and offline GRBL CAM deliverables.

Phase 12 is imported as a read-only geometry/CAM library. All writes are
redirected to deliverables/phase13; no CFD, cloud worker, network service, or
CNC controller is invoked.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import cadquery as cq
from cadquery import Color, Vector
from shapely.affinity import translate as shp_translate
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[2]
P12_SCRIPT = ROOT / "deliverables" / "phase12" / "phase12_generate.py"
OUT = ROOT / "deliverables" / "phase13"
STEP_DIR = OUT / "step"
NEST_DIR = OUT / "stock_layouts"
NC_DIR = OUT / "gcode"
REPORT_DIR = OUT / "reports"
CONFIG_DIR = OUT / "configs"
for directory in (STEP_DIR, NEST_DIR, NC_DIR, REPORT_DIR, CONFIG_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# Prevent import bytecode from changing the preserved Phase-12 directory.
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("phase12_readonly_cadcam", P12_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load the preserved Phase-12 CAD/CAM helpers")
p12 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p12)
p12.OUT = OUT
p12.STEP_DIR = STEP_DIR
p12.NEST_DIR = NEST_DIR
p12.NC_DIR = NC_DIR
p12.REPORT_DIR = REPORT_DIR
p12.CONFIG_DIR = CONFIG_DIR

# Frozen installation and machine inputs.
RADIUS_MM = 30.0
MOTOR_SOFT_RPM = 12500.0
GEAR_RATIOS = (2.35, 2.65, 2.95)
DESIGN_RPM = (29375.0, 33125.0, 36360.0)
PROOF_RPM = tuple(1.25 * MOTOR_SOFT_RPM * ratio for ratio in GEAR_RATIOS)
ROOT_THICKNESS_RATIO = 0.20
TIP_THICKNESS_RATIO = 0.12
ROOT_INSERTION_MM = 2.0
ROOT_BLEND_SPAN_FRACTION = 0.24
YIELD_6061_T6_MPA = 276.0
AL_DENSITY_KG_M3 = 2700.0
ALL_UP_BUDGET_KG = 10.5
FIXED_MOTOR_MASS_KG = 1.680
FIXED_BATTERY_MASS_KG = 1.426
BARE_PCB_MASS_KG = 0.12058531923529413
BOARD_POPULATION_KG = 0.200
GEARBOX_ALLOWANCE_KG = 0.720
HARNESS_ALLOWANCE_KG = 0.250
MOUNT_ALLOWANCE_KG = 0.350
LANDING_GEAR_ALLOWANCE_KG = 0.400
PAYLOAD_ALLOWANCE_KG = 2.000
SPREADER_MASS_KG = 0.08235

# Redirect the shared helpers onto the revised root-loft geometry.
p12.ROTOR_ROOT_R = p12.HUB_R - ROOT_INSERTION_MM
p12.ROTOR_SPAN = p12.ROTOR_TIP_R - p12.ROTOR_ROOT_R
p12.ROTOR_ROOT_BLEND_SPAN = p12.ROTOR_SPAN * ROOT_BLEND_SPAN_FRACTION
p12.INLET_RADII = (RADIUS_MM,)
p12.INITIAL_RADIUS = RADIUS_MM


def make_phase13_rotor(row: int, zcentre: float) -> cq.Solid:
    """Fused hub/blade rotor with a thick, smoothly lofted, inserted root."""
    count = p12.ROTOR_COUNTS[row]
    hub = cq.Solid.makeCylinder(p12.HUB_R, p12.ROTOR_CHORD,
                                Vector(0, 0, zcentre - p12.ROTOR_CHORD / 2.0))
    bore = cq.Solid.makeCylinder(4.0, p12.ROTOR_CHORD + 2.0,
                                 Vector(0, 0, zcentre - p12.ROTOR_CHORD / 2.0 - 1.0))
    hub = hub.cut(bore)
    beta0, beta1 = p12.ROTOR_BETA[row]
    blades = [p12.make_vane(p12.ROTOR_CHORD, 2.0 * math.pi * i / count,
                            p12.ROTOR_ROOT_R, p12.ROTOR_TIP_R, beta0, beta1,
                            zcentre, ROOT_THICKNESS_RATIO, TIP_THICKNESS_RATIO)
              for i in range(count)]
    rotor = hub.fuse(*blades)
    if not rotor.isValid() or len(rotor.Solids()) != 1:
        raise RuntimeError(f"R{row + 1} fused rotor root/hub is not one valid solid")
    return rotor


p12.make_rotor = make_phase13_rotor


def make_phase13_rotor_blank(row: int) -> Polygon:
    """2-D blank envelope for the strengthened 20%-thick root loft."""
    beta0, beta1 = p12.ROTOR_BETA[row]
    top: list[tuple[float, float]] = []
    bottom: list[tuple[float, float]] = []
    for i in range(41):
        u = i / 40.0
        x = p12.ROTOR_SPAN * u
        beta = math.radians(beta0 + (beta1 - beta0) * u)
        thickness = ROOT_THICKNESS_RATIO + (TIP_THICKNESS_RATIO - ROOT_THICKNESS_RATIO) * min(
            1.0, u / ROOT_BLEND_SPAN_FRACTION)
        width = 16.0 * abs(math.sin(beta)) + 0.30 * 16.0 * thickness * math.cos(beta)
        width = min(12.4, max(5.5, width))
        centre = 0.35 * math.sin(math.pi * u) + 0.2 * u
        top.append((x, centre + width / 2.0))
        bottom.append((x, centre - width / 2.0))
    polygon = Polygon(top + list(reversed(bottom)))
    return shp_translate(polygon, yoff=-polygon.bounds[1])


def make_board_and_spreader_envelopes() -> list[tuple[str, cq.Shape, float, tuple[float, float, float]]]:
    """Non-overlapping PCB/spreader packages in the side cooling bay."""
    esc = cq.Workplane("XY").box(150.0, 1.6, 150.0).translate((0, 52.0, 220.0)).val()
    fc = cq.Workplane("XY").box(140.0, 1.6, 100.0).translate((0, 52.0, 345.0)).val()
    esc_sink = cq.Workplane("XY").box(150.0, 1.0, 150.0).translate((0, 54.2, 220.0)).val()
    fc_sink = cq.Workplane("XY").box(100.0, 1.0, 80.0).translate((0, 54.2, 345.0)).val()
    return [
        ("ESC_PCB_150x150x1p6_bare", esc, 0.0701629936219608, (150.0, 150.0, 1.6)),
        ("flight_PCB_140x100x1p6_bare", fc, 0.05042232561333333, (140.0, 100.0, 1.6)),
        ("ESC_Al_spreader_150x150x1_estimated", esc_sink, 0.06075, (150.0, 150.0, 1.0)),
        ("flight_Al_spreader_100x80x1_estimated", fc_sink, 0.02160, (100.0, 80.0, 1.0)),
    ]


def make_lifting_body_shell() -> cq.Shape:
    """Thin, lofted 120 mm-span lifting-body skin with two EDF clearances."""
    # x lateral station, section thickness in y, section chord in z.
    sections = [(-60.0, 1.5, 24.0), (-50.0, 3.0, 56.0),
                (-30.0, 4.5, 100.0), (0.0, 5.0, 120.0),
                (30.0, 4.5, 100.0), (50.0, 3.0, 56.0),
                (60.0, 1.5, 24.0)]
    outer_wires = [p12.ellipse_wire_x(x, thickness, chord).translate(Vector(0, 0, 85.0))
                   for x, thickness, chord in sections]
    inner_wires = [p12.ellipse_wire_x(x, max(0.35, thickness - 0.6), max(2.0, chord - 1.2))
                   .translate(Vector(0, 0, 85.0)) for x, thickness, chord in sections]
    outer = cq.Solid.makeLoft(outer_wires, ruled=False)
    inner = cq.Solid.makeLoft(inner_wires, ruled=False)
    shell = outer.cut(inner)
    # Keep the two 90/88/32 mm fan barrels clear through the lifting-body skin.
    for start in p12.MODULE_STARTS:
        clearance = cq.Solid.makeCylinder(46.0, p12.MODULE_LENGTH + 2.0,
                                          Vector(0, 0, start - 1.0))
        shell = shell.cut(clearance)
    if not shell.isValid():
        raise RuntimeError("Lifting-body shell/EDF-clearance boolean is invalid")
    return shell


def make_cooling_channel() -> cq.Shape:
    """Open-ended side-bay cooling tunnel envelope, forward inlet to aft outlet."""
    outer = cq.Solid.makeBox(150.0, 8.0, 250.0, Vector(-75.0, 49.0, 145.0))
    # Oversize through-Z and Y dimensions leave open inlet/outlet and wash faces.
    void = cq.Solid.makeBox(146.0, 8.2, 252.0, Vector(-73.0, 48.9, 144.0))
    channel = outer.cut(void)
    if not channel.isValid():
        raise RuntimeError("Cooling channel guide geometry is invalid")
    return channel


def make_board_supports() -> list[cq.Shape]:
    return [
        cq.Solid.makeBox(2.0, 2.0, 250.0, Vector(x, 48.0, 145.0))
        for x in (-74.0, 72.0)
    ] + [
        cq.Solid.makeBox(140.0, 2.0, 2.0, Vector(-70.0, 48.0, z))
        for z in (145.0, 393.0)
    ]


def projected_union_cm2(boards: list[tuple[str, cq.Shape, float, tuple[float, float, float]]]) -> tuple[float, Any]:
    pieces: list[Any] = [Point(0, 0).buffer(45.0, quad_segs=96), p12.body_outer_projection(),
                         box(-25.0, -22.5, 25.0, 22.5), Point(0, 0).buffer(20.5, quad_segs=48)]
    for side in (+1, -1):
        _, sections = p12.make_inlet_branch(0.0, side, RADIUS_MM)
        pieces.extend(sections)
        pieces.append(box(min(side * RADIUS_MM, side * (RADIUS_MM + 1.0)), -14.5,
                          max(side * RADIUS_MM, side * (RADIUS_MM + 1.0)), 14.5))
    # The PCB/spreader silhouettes and cooling tunnel rails are included in the
    # exact 2-D union; the two axial EDF sets share the same planform silhouette.
    pieces.extend((box(-75.0, 51.2, 75.0, 52.8),
                   box(-70.0, 51.2, 70.0, 52.8),
                   box(-75.0, 53.7, 75.0, 54.7),
                   box(-50.0, 53.7, 50.0, 54.7),
                   box(-75.0, 49.0, -73.0, 57.0),
                   box(73.0, 49.0, 75.0, 57.0)))
    union = unary_union(pieces)
    return union.area / 100.0, union


def add_assembly_children(target: cq.Assembly, source: cq.Assembly, prefix: str = "") -> None:
    for child in source.children:
        target.add(child.obj, name=f"{prefix}{child.name}", loc=child.loc,
                   color=child.color)


def build_phase13_module(name: str, start: float) -> tuple[cq.Assembly, list[cq.Shape]]:
    module, shapes, _ = p12.build_base_module(name, start)
    installed = cq.Assembly(name=f"Phase13_EDF_{name}_3R3S_R030_90OD_88bore_32hub")
    add_assembly_children(installed, module)
    for side in (+1, -1):
        branch, _ = p12.make_inlet_branch(start, side, RADIUS_MM)
        installed.add(branch, name=f"{name}_split_slot_{side:+d}_25x120_R030")
        shapes.append(branch)
    return installed, shapes


def build_full_assembly(modules: list[cq.Assembly], body: cq.Shape, lift: cq.Shape,
                        batteries: list[cq.Shape], boards: list[tuple[str, cq.Shape, float, tuple[float, float, float]]],
                        cooling: cq.Shape, supports: list[cq.Shape]) -> cq.Assembly:
    assembly = cq.Assembly(name="Phase13_R030_fixed_powertrain_full_airframe")
    for module, label in zip(modules, ("EDF_A_", "EDF_B_")):
        add_assembly_children(assembly, module, label)
    assembly.add(body, name="PLA_CF_battery_fuselage_panels")
    assembly.add(lift, name="PLA_CF_lofted_lifting_body_shell_span120_clearance_bores")
    for idx, (zcentre, battery) in enumerate(zip((-337.5, -177.5), batteries), 1):
        assembly.add(battery, name=f"Turnigy_Rapid_6S5000_{idx}_12S1P_proxy_150x50x45_Z{zcentre:g}",
                     color=Color(0.75, 0.18, 0.16, 0.55))
    for name, shape, _mass, _dims in boards:
        assembly.add(shape, name=name, color=Color(0.12, 0.40, 0.78, 0.55))
    assembly.add(cooling, name="cooling_route_forward_inlet_z145_to_aft_outlet_z395_open_tunnel",
                 color=Color(0.25, 0.72, 0.82, 0.35))
    for idx, support in enumerate(supports, 1):
        assembly.add(support, name=f"cooling_bay_board_support_{idx:02d}")
    return assembly


def export_assembly(assembly: cq.Assembly, path: Path) -> None:
    assembly.save(str(path), exportType="STEP", tolerance=0.05, angularTolerance=0.05)


def rename_generated(path: Path, prefix: str = "phase13_") -> Path:
    if path.name.startswith("phase12_"):
        name = prefix + path.name[len("phase12_"):]
    elif path.name.startswith("channel_") or path.name.startswith("EDF_"):
        name = prefix + path.name
    else:
        name = path.name
    target = path.with_name(name)
    if path != target:
        path.replace(target)
    return target


def add_tool_number_and_phase(path: Path, tool_number: int, tool_diameter: float,
                              operation: str) -> None:
    text = path.read_text(encoding="ascii")
    text = text.replace("Phase12", "Phase13")
    first, *rest = text.splitlines()
    header = [first, f"(CAM TOOL T{tool_number}: {tool_diameter:g} mm carbide {operation})"]
    text = "\n".join(header + rest) + "\n"
    text = text.replace("Install 2.0 mm carbide rougher", "Manual change to T1 2.0 mm carbide rougher")
    text = text.replace("Install 0.5 mm carbide finisher", "Manual change to T2 0.5 mm carbide finisher")
    text = text.replace("Install 0.5 mm long-flute finisher", "Manual change to T2 0.5 mm long-flute finisher")
    text = text.replace("(Rough S8000 F50 plunge F8;", "(Rough S8000 F40 plunge F8;")
    text = text.replace(" F50.0", " F40.0")
    path.write_text(text, encoding="ascii", newline="\n")


def parse_nc_and_validate(path: Path, stock: tuple[float, float, float],
                          cam_x: tuple[float, float] | None, expected_tool: int,
                          expected_diameter: float) -> dict[str, Any]:
    text = path.read_text(encoding="ascii")
    if "G54" not in text or "M3 S8000" not in text or "M0" not in text or "M30" not in text:
        raise ValueError(f"{path.name}: missing G54/spindle/manual-change/end block")
    tool_declarations = re.findall(r"CAM TOOL T(\d+):\s*([\d.]+)\s*mm", text)
    if tool_declarations != [(str(expected_tool), f"{expected_diameter:g}")]:
        raise ValueError(f"{path.name}: unexpected CAM tool declaration {tool_declarations}")
    x_limit, y_limit, thickness = stock
    values: dict[str, list[float]] = {"X": [], "Y": [], "Z": []}
    motion_count = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        code = line.split("(", 1)[0]
        if not code.strip():
            continue
        words = re.findall(r"(?<![A-Z])([XYZ])\s*(-?\d+(?:\.\d+)?)", code, flags=re.IGNORECASE)
        for axis, raw in words:
            value = float(raw)
            values[axis.upper()].append(value)
            if axis.upper() == "X":
                if value < -1e-6 or value > x_limit + 1e-6:
                    raise ValueError(f"{path.name}:{line_number}: X{value} outside {x_limit}mm stock")
                if cam_x and not cam_x[0] - 1e-6 <= value <= cam_x[1] + 1e-6:
                    raise ValueError(f"{path.name}:{line_number}: X{value} enters clamp margin")
            elif axis.upper() == "Y" and not -1e-6 <= value <= y_limit + 1e-6:
                raise ValueError(f"{path.name}:{line_number}: Y{value} outside {y_limit}mm stock")
            elif axis.upper() == "Z" and not -thickness - 1e-6 <= value <= 5.0 + 1e-6:
                raise ValueError(f"{path.name}:{line_number}: Z{value} exceeds stock/retract bound")
        if re.search(r"\bG[01]\b", code, re.IGNORECASE):
            motion_count += 1
    if not all(values[axis] for axis in values):
        raise ValueError(f"{path.name}: no coordinate words found for X/Y/Z")
    min_z = min(values["Z"])
    max_z = max(values["Z"])
    return {"file": path.name, "toolNumber": expected_tool, "toolDiameterMm": expected_diameter,
            "stockMm": list(stock), "camXBoundsMm": list(cam_x) if cam_x else [0.0, x_limit],
            "minXmm": min(values["X"]), "maxXmm": max(values["X"]),
            "minYmm": min(values["Y"]), "maxYmm": max(values["Y"]),
            "minZmm": min_z, "maxZmm": max_z, "coordinateWordCount": sum(map(len, values.values())),
            "linearMotionBlocks": motion_count, "allCoordinatesInsideStock": True,
            "depthInsideStock": True, "G54": True, "spindle8000": True,
            "manualToolChange": True, "cncRun": False}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def step_reimport_audit(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        shape = cq.importers.importStep(str(path)).val()
        solids = shape.Solids()
        valid_solids = all(s.isValid() and s.Volume() > 0.0 for s in solids)
        if not solids or not shape.isValid() or not valid_solids:
            raise ValueError(f"STEP re-import validation failed: {path.name}")
        bbox = shape.BoundingBox()
        rows.append({"file": path.name, "validCompound": bool(shape.isValid()),
                     "solidCount": len(solids), "allSolidsValidAndPositiveVolume": valid_solids,
                     "volumeMm3": shape.Volume(), "bboxXmm": bbox.xlen,
                     "bboxYmm": bbox.ylen, "bboxZmm": bbox.zlen,
                     "reimported": True})
    return rows


def build_outputs() -> dict[str, Any]:
    # Force the selected R30 only; alternatives remain traceable in Phase 12.
    p12.INLET_RADII = (RADIUS_MM,)
    body = p12.make_body_shell()
    lift_shell = make_lifting_body_shell()
    batteries = [p12.make_battery_envelope(-337.5), p12.make_battery_envelope(-177.5)]
    boards = make_board_and_spreader_envelopes()
    cooling = make_cooling_channel()
    supports = make_board_supports()
    modules_and_parts = [build_phase13_module("A", p12.MODULE_STARTS[0]),
                         build_phase13_module("B", p12.MODULE_STARTS[1])]
    modules = [item[0] for item in modules_and_parts]
    module_solids = [shape for _module, shapes in modules_and_parts for shape in shapes]
    full = build_full_assembly(modules, body, lift_shell, batteries, boards, cooling, supports)

    step_paths: list[Path] = []
    full_path = STEP_DIR / "phase13_full_assembly_R030.step"
    export_assembly(full, full_path)
    step_paths.append(full_path)
    for module, name in zip(modules, ("A", "B")):
        path = STEP_DIR / f"phase13_EDF_{name}_R030.step"
        export_assembly(module, path)
        step_paths.append(path)
    inlet_assy = cq.Assembly(name="Phase13_R030_four_slot_split_inlet_pending_pressure_recovery")
    for module_name, start in zip(("A", "B"), p12.MODULE_STARTS):
        for side in (+1, -1):
            branch, _ = p12.make_inlet_branch(start, side, RADIUS_MM)
            inlet_assy.add(branch, name=f"{module_name}_slot_{side:+d}_25x120_R030")
    inlet_path = STEP_DIR / "phase13_split_inlet_R030_4x25x120.step"
    export_assembly(inlet_assy, inlet_path)
    step_paths.append(inlet_path)

    # One rotor row and hub per motor/ESC channel; 25 mm clamps reserved at
    # both billet ends, and one complete 63-vane stator set per EDF plate.
    rotor_profiles = [make_phase13_rotor_blank(row) for row in range(3)]
    nc_paths: list[tuple[Path, int, float, tuple[float, float, float], tuple[float, float] | None]] = []
    channel = 0
    for module_index, module_name in enumerate(("A", "B")):
        for row in range(3):
            channel += 1
            stock_path = p12.add_stock_layout_billet(channel, row, rotor_profiles[row])
            step_paths.append(rename_generated(stock_path))
            for rough, tool_number, diameter in ((True, 1, 2.0), (False, 2, 0.5)):
                nc = p12.write_rotor_nc(channel, row, rotor_profiles[row], rough)
                nc = rename_generated(nc)
                add_tool_number_and_phase(nc, tool_number, diameter,
                                          "rougher" if rough else "top-band finisher")
                nc_paths.append((nc, tool_number, diameter, (300.0, 50.0, 16.0), (25.0, 275.0)))
        stator_profile = p12.stator_blank()
        stator_path = p12.add_stock_layout_stator(module_name, stator_profile)
        step_paths.append(rename_generated(stator_path))
        for rough, tool_number, diameter in ((True, 1, 2.0), (False, 2, 0.5)):
            nc = p12.write_stator_nc(module_name, stator_profile, rough)
            nc = rename_generated(nc)
            add_tool_number_and_phase(nc, tool_number, diameter,
                                      "rougher" if rough else "finish cutter")
            nc_paths.append((nc, tool_number, diameter, (250.0, 100.0, 5.0), None))

    area_cm2, area_union = projected_union_cm2(boards)
    if area_cm2 >= 75.0:
        raise ValueError(f"Phase-13 installed projected-area union {area_cm2:.4f} cm2 fails strict <75 gate")

    # CAD volume-based rotor/stator metal mass, using the revised fused-root B-reps.
    rotor_shapes = [p12.make_rotor(row, start + p12.ROTOR_Z[row])
                    for start in p12.MODULE_STARTS for row in range(3)]
    stator_shapes = [p12.make_stator(row, start + p12.STATOR_Z[row])
                     for start in p12.MODULE_STARTS for row in range(3)]
    rotor_mass_kg = sum(shape.Volume() for shape in rotor_shapes) * AL_DENSITY_KG_M3 * 1e-9
    stator_mass_kg = sum(shape.Volume() for shape in stator_shapes) * AL_DENSITY_KG_M3 * 1e-9
    rotor_fit = []
    for row in range(3):
        shape = rotor_shapes[row]
        bbox = shape.BoundingBox()
        max_diameter = max(bbox.xlen, bbox.ylen)
        rotor_fit.append({"maxPlanarEnvelopeMm": max_diameter,
                          "axialThicknessMm": bbox.zlen,
                          "diametralClearanceTo88mmBoreMm": 88.0 - max_diameter})
        if max_diameter > 88.0 or bbox.zlen > 16.0 + 0.01:
            raise ValueError(f"R{row + 1} rotor exceeds 88mm bore or 16mm billet thickness")

    # Split the old aggregate laminate/core estimate into auditable airframe,
    # fan-case, and inlet ledgers rather than hiding inlet mass in a shell total.
    body_surface_mm2 = p12.shape_lateral_area(body)
    body_surface_mm2 += sum(face.Area() for face in lift_shell.Faces())
    case_surface_mm2 = 2.0 * math.pi * (45.0 + 44.0) * p12.MODULE_LENGTH * len(p12.MODULE_STARTS)
    inlet_surface_mm2 = 0.0
    for start in p12.MODULE_STARTS:
        for side in (+1, -1):
            branch, _ = p12.make_inlet_branch(start, side, RADIUS_MM)
            inlet_surface_mm2 += p12.shape_lateral_area(branch)
    skin_factor_kg_m2 = 0.300 * (1.0 + 0.80)

    def composite_and_pla(surface_mm2: float) -> tuple[float, float]:
        outer_inner_area_m2 = surface_mm2 * 1e-6
        composite = outer_inner_area_m2 * skin_factor_kg_m2
        mid_surface_m2 = outer_inner_area_m2 / 2.0
        pla = mid_surface_m2 * 0.0012 * p12.PLA_DENSITY_KG_M3
        return composite, pla

    body_cf_kg, body_pla_kg = composite_and_pla(body_surface_mm2)
    case_cf_kg, case_pla_kg = composite_and_pla(case_surface_mm2)
    inlet_cf_kg, inlet_pla_kg = composite_and_pla(inlet_surface_mm2)

    components: list[dict[str, Any]] = [
        {"component": "Six stock FA4119 KV350 motors", "massKg": FIXED_MOTOR_MASS_KG,
         "basis": "sourced fixed motor mass 6 x 0.280 kg", "cgXmm": 0, "cgYmm": 0, "cgZmm": 122},
        {"component": "Two Turnigy Rapid 6S5000 packs in series, 12S1P 5Ah", "massKg": FIXED_BATTERY_MASS_KG,
         "basis": "sourced 2 x 0.713 kg; 150x50x45 mm package dimensions remain a proxy",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": -257.5},
        {"component": "ESC and flight-control bare PCBs", "massKg": BARE_PCB_MASS_KG,
         "basis": "results/phase9_control_board_mass.csv; population excluded",
         "cgXmm": 0, "cgYmm": 52, "cgZmm": 272.2},
        {"component": "Remaining populated-board parts, connectors and solder", "massKg": BOARD_POPULATION_KG,
         "basis": "explicit analyst allowance beyond bare PCB source mass",
         "cgXmm": 0, "cgYmm": 52, "cgZmm": 270},
        {"component": "Aluminium board heat spreaders", "massKg": SPREADER_MASS_KG,
         "basis": "Phase-12 dimension/material estimate retained; two separate spreaders",
         "cgXmm": 0, "cgYmm": 54.2, "cgZmm": 270},
        {"component": "Six 6061-T6 fused rotors and hubs", "massKg": rotor_mass_kg,
         "basis": "Phase-13 CadQuery fused-solid volumes x 2700 kg/m3",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": 122},
        {"component": "Six 6061-T6 stator sets and rails", "massKg": stator_mass_kg,
         "basis": "Phase-13 CadQuery solid volumes x 2700 kg/m3",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": 122},
        {"component": "Six fixed-ratio gearboxes", "massKg": GEARBOX_ALLOWANCE_KG,
         "basis": "explicit analyst allowance 6 x 0.120 kg; gear ratios unchanged",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": 122},
        {"component": "Power, phase, sensor and control harness", "massKg": HARNESS_ALLOWANCE_KG,
         "basis": "explicit analyst allowance including service loops/connectors",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": 110},
        {"component": "PLA/CF fuselage and lifting-body shells", "massKg": body_pla_kg + body_cf_kg,
         "basis": f"CAD surface split {body_surface_mm2/1e6:.5f} m2; PLA core + 200gsm CF/100gsm glass per face and 0.8 resin:fibre",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": 0},
        {"component": "PLA/CF fan casing shells", "massKg": case_pla_kg + case_cf_kg,
         "basis": f"CAD surface {case_surface_mm2/1e6:.5f} m2; same documented laminate/core schedule",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": 122},
        {"component": "PLA/CF four R30 split-inlet branches and lips", "massKg": inlet_pla_kg + inlet_cf_kg,
         "basis": f"CAD surface {inlet_surface_mm2/1e6:.5f} m2; same documented laminate/core schedule",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": 122},
        {"component": "Mounts, clamps, fasteners and cooling-bay support allowance", "massKg": MOUNT_ALLOWANCE_KG,
         "basis": "explicit analyst allowance; motor/shaft outline dimensions are not sourced",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": 80},
        {"component": "Landing gear allowance", "massKg": LANDING_GEAR_ALLOWANCE_KG,
         "basis": "explicit analyst allowance; detailed gear geometry not supplied",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": -40},
        {"component": "Payload allowance", "massKg": PAYLOAD_ALLOWANCE_KG,
         "basis": "design payload allocation; not an installed/verified payload",
         "cgXmm": 0, "cgYmm": 0, "cgZmm": -50},
    ]
    modeled_and_payload_mass = sum(item["massKg"] for item in components)
    budget_reserve_kg = ALL_UP_BUDGET_KG - modeled_and_payload_mass
    if budget_reserve_kg < 0.0:
        raise ValueError(f"Mass plan exceeds 10.5kg design budget by {-budget_reserve_kg:.3f}kg")
    moments = [sum(item["massKg"] * item[f"cg{axis}mm"] for item in components)
               for axis in ("X", "Y", "Z")]
    cg = tuple(moment / modeled_and_payload_mass for moment in moments)
    mass_rows = [dict(item, massClass=("sourced" if item["component"].startswith((
        "Six stock", "Two Turnigy", "ESC and flight-control")) else "CAD-calculated" if
        "CadQuery" in item["basis"] or item["component"].startswith(("PLA/CF", "Six 6061"))
        else "analyst allowance")) for item in components]
    mass_rows.append({"component": "Unallocated growth/design reserve to 10.5kg ceiling",
                      "massKg": budget_reserve_kg,
                      "basis": "budget headroom; not a physical component, excluded from CG",
                      "cgXmm": "", "cgYmm": "", "cgZmm": "", "massClass": "budget reserve"})
    mass_rows.append({"component": "TOTAL PLANNED MASS INCLUDING PAYLOAD", "massKg": modeled_and_payload_mass,
                      "basis": "sourced masses + CAD volumes + explicit engineering/payload allowances",
                      "cgXmm": cg[0], "cgYmm": cg[1], "cgZmm": cg[2], "massClass": "not weighed"})
    mass_rows.append({"component": "10.5kg ALL-UP DESIGN CEILING", "massKg": ALL_UP_BUDGET_KG,
                      "basis": f"planned mass plus {budget_reserve_kg:.4f} kg unallocated reserve",
                      "cgXmm": "", "cgYmm": "", "cgZmm": "", "massClass": "design budget"})

    # Conservative centrifugal-only scaling at 1.25x each unchanged gear-derived limit.
    phase12_fos_at_26p5 = (4.138870102493788, 3.254552972237892, 2.626093423732173)
    reference_root_area_mm2 = 26.5
    reference_section = Polygon(p12.naca4(p12.ROTOR_CHORD, 0.12, 0.025)).area
    thick_root_section = Polygon(p12.naca4(p12.ROTOR_CHORD, ROOT_THICKNESS_RATIO, 0.025)).area
    root_area_mm2 = 20.96066560429954 * thick_root_section / reference_section
    strength_rows = []
    for row, ratio in enumerate(GEAR_RATIOS):
        soft_rpm = MOTOR_SOFT_RPM * ratio
        proof_rpm = 1.25 * soft_rpm
        fos = phase12_fos_at_26p5[row] * root_area_mm2 / reference_root_area_mm2
        strength_rows.append({"rotorRow": f"R{row + 1}", "fixedGearRatio": ratio,
                              "motorSoftLimitRpm": MOTOR_SOFT_RPM,
                              "gearDerivedMaximumRotorRpm": soft_rpm,
                              "proofSpeedRpm_1p25x": proof_rpm,
                              "designRotorRpmUnchanged": DESIGN_RPM[row],
                              "rootSectionThicknessRatio": ROOT_THICKNESS_RATIO,
                              "nominalTipSectionThicknessRatio": TIP_THICKNESS_RATIO,
                              "rootInsertionIntoHubMm": ROOT_INSERTION_MM,
                              "rootBlendLengthMm": p12.ROTOR_ROOT_BLEND_SPAN,
                              "rootAreaPhase13Mm2": root_area_mm2,
                              "cadRotorMaxPlanarEnvelopeMm": rotor_fit[row]["maxPlanarEnvelopeMm"],
                              "cadRotorAxialThicknessMm": rotor_fit[row]["axialThicknessMm"],
                              "diametralClearanceTo88mmBoreMm": rotor_fit[row]["diametralClearanceTo88mmBoreMm"],
                              "yield6061T6MPa": YIELD_6061_T6_MPA,
                              "centrifugalOnlyFOSAtProofSpeed": fos,
                              "targetFOS": 3.0, "pass": fos >= 3.0,
                              "scope": "Phase-12 centrifugal reference stress scaled by RPM^2 and NACA root area; Kt=2.5 retained; excludes aero bending, fatigue, joint flaws and burst test"})
    if min(row["centrifugalOnlyFOSAtProofSpeed"] for row in strength_rows) < 3.0:
        raise ValueError("Strengthened rotor root does not reach 3.0 centrifugal-only FOS")

    # Component placement / CG and battery separation evidence.
    layout_rows = [
        {"item": "ESC PCB + population", "centreXmm": 0, "centreYmm": 52, "centreZmm": 220,
         "envelopeMm": "150 X x 1.6 Y x 150 Z; Z145..295", "notes": "Side-bay board, forward cooling inlet at Z145"},
        {"item": "Flight-control PCB + population", "centreXmm": 0, "centreYmm": 52, "centreZmm": 345,
         "envelopeMm": "140 X x 1.6 Y x 100 Z; Z295..395", "notes": "No overlap with ESC PCB; aft cooling outlet at Z395"},
        {"item": "ESC aluminium spreader", "centreXmm": 0, "centreYmm": 54.2, "centreZmm": 220,
         "envelopeMm": "150 X x 1 Y x 150 Z", "notes": "0.6mm nominal PCB/spreader stand-off"},
        {"item": "Flight aluminium spreader", "centreXmm": 0, "centreYmm": 54.2, "centreZmm": 345,
         "envelopeMm": "100 X x 1 Y x 80 Z", "notes": "0.6mm nominal PCB/spreader stand-off"},
        {"item": "Battery 1", "centreXmm": 0, "centreYmm": 0, "centreZmm": -337.5,
         "envelopeMm": "50 X x 45 Y x 150 Z proxy; Z-412.5..-262.5", "notes": "0.713kg sourced; verify physical pack dims"},
        {"item": "Battery 2", "centreXmm": 0, "centreYmm": 0, "centreZmm": -177.5,
         "envelopeMm": "50 X x 45 Y x 150 Z proxy; Z-252.5..-102.5", "notes": "0.713kg sourced; series wiring; 10mm axial bay gap"},
        {"item": "Cooling route", "centreXmm": 0, "centreYmm": 53, "centreZmm": 270,
         "envelopeMm": "150 X x 8 Y x 250 Z; Z145..395", "notes": "Forward inlet Z145; washes PCBs/spreaders; aft outlet Z395"},
    ]

    body_section_rows = []
    for i, (x, thickness, chord) in enumerate([
        (-60.0, 1.5, 24.0), (-50.0, 3.0, 56.0), (-30.0, 4.5, 100.0),
        (0.0, 5.0, 120.0), (30.0, 4.5, 100.0), (50.0, 3.0, 56.0), (60.0, 1.5, 24.0)], 1):
        body_section_rows.append({"section": i, "lateralStationXmm": x,
                                  "outerSectionThicknessYmm": thickness,
                                  "outerChordZmm": chord, "skinNominalMm": 0.30,
                                  "construction": "1.2mm PLA cellular core + carbon/glass layup; CAD section is envelope"})

    # Make stock STEP nests and 16 NC programs, one rough and finish file per stock.
    step_audit_rows = step_reimport_audit(step_paths)
    nc_audit_rows = [parse_nc_and_validate(path, stock, cam_x, tool, diameter)
                     for path, tool, diameter, stock, cam_x in nc_paths]
    write_csv(REPORT_DIR / "phase13_mass_cg_budget.csv", mass_rows)
    write_csv(REPORT_DIR / "phase13_rotor_strength_screen.csv", strength_rows)
    write_csv(REPORT_DIR / "phase13_cg_layout.csv", layout_rows)
    write_csv(REPORT_DIR / "phase13_lifting_body_sections.csv", body_section_rows)
    write_csv(REPORT_DIR / "phase13_nc_validation.csv", nc_audit_rows)
    write_csv(REPORT_DIR / "phase13_step_reimport_validation.csv", step_audit_rows)

    # Preserve the distinction between detailed CAD union and conservative
    # generic-structure reserve bound used by the Phase-12 packaging gate.
    fan_area = math.pi * 45.0**2 / 100.0
    conservative_bound_cm2 = fan_area + 10.0
    if conservative_bound_cm2 >= 75.0:
        raise ValueError("R30 conservative reserve-aware area bound failed")
    area_record = {"selection": "R30 packaging start; CFD/pressure recovery pending",
                   "geometryOnlyProjectedAreaUnionCm2": area_cm2,
                   "fanSilhouetteUnionCm2": fan_area,
                   "phase12GenericStructureReserveCm2": 10.0,
                   "conservativeReserveAwareBoundCm2": conservative_bound_cm2,
                   "strict75GatePass": area_cm2 < 75.0 and conservative_bound_cm2 < 75.0,
                   "slots": {"count": 4, "eachMm": [25.0, 120.0]},
                   "rotorODmm": 90.0, "boreMm": 88.0, "hubMm": 32.0,
                   "pressureRecovery": None, "aerodynamicWinner": None}
    config = {
        "phase": 13,
        "status": "CAD_CAM_complete_R030_pressure_recovery_pending",
        "supersedes": "none; additive revision based on deliverables/phase12; old phase files remain authoritative history",
        "fixedPowertrainImmutable": {
            "motors": "six stock FA4119 KV350, 0.280kg each, 1.680kg total",
            "batteries": "two Turnigy Rapid 6S5000 in series; 12S1P/5Ah; 0.713kg each; 1.426kg total",
            "gearRatios": list(GEAR_RATIOS), "motorSoftLimitRpm": MOTOR_SOFT_RPM,
            "currentVoltageEscAndRPMLimits": "unchanged from Phase 9/12; no powertrain changes",
            "rotorDesignRpm": list(DESIGN_RPM), "maximumGearDerivedRotorRpm": [MOTOR_SOFT_RPM * r for r in GEAR_RATIOS]},
        "fan": {"sets": 2, "motorsPerSet": 3, "rotorODmm": 90.0, "boreMm": 88.0,
                "hubMm": 32.0, "rotorRowsPerSet": 3, "statorRowsPerSet": 3,
                "projectedAreaUnionCm2": area_cm2},
        "inlet": {"selectedRadiusMm": RADIUS_MM, "status": "pending pressure recovery; packaging start only",
                  "slotsPerSet": 2, "totalSlots": 4, "slotMm": [25.0, 120.0],
                  "validPressureRecovery": None, "winnerClaim": False},
        "rotorRoot": {"rootRadialStartMm": p12.ROTOR_ROOT_R,
                      "rootInsertionInto32mmHubMm": ROOT_INSERTION_MM,
                      "rootAirfoilThicknessRatio": ROOT_THICKNESS_RATIO,
                      "tipThicknessRatio": TIP_THICKNESS_RATIO,
                      "smoothThicknessTransitionFirst24PercentSpan": True,
                      "minimumCentrifugalOnlyFOSAt1p25xFixedGearDerivedRpm": min(
                          row["centrifugalOnlyFOSAtProofSpeed"] for row in strength_rows),
                      "targetFOS": 3.0, "scope": "analytical only; structural FEA and spin test not performed"},
        "projectedArea": area_record,
        "massBudget": {"measuredOrSourcedMassKg": FIXED_MOTOR_MASS_KG + FIXED_BATTERY_MASS_KG + BARE_PCB_MASS_KG,
                       "calculatedAndExplicitAllowancesIncludingPayloadKg": modeled_and_payload_mass,
                       "payloadAllowanceKg": PAYLOAD_ALLOWANCE_KG,
                       "unallocatedReserveKg": budget_reserve_kg,
                       "allUpDesignBudgetKg": ALL_UP_BUDGET_KG,
                       "cgIncludingPayloadMmXYZ": list(cg), "physicalWeighingComplete": False,
                       "cgDatum": {"X": "lateral", "Y": "vertical", "Z": "flight axis", "units": "mm"}},
        "stockAndMachine": {"rotorBillets": 6, "rotorBilletMm": [300, 50, 16],
                            "rotorUse": "one billet per motor/ESC; CAM X25..275, reserve 25mm clamp ends",
                            "statorPlates": 2, "statorPlateMm": [250, 100, 5],
                            "statorSets": "one 63-stator set per EDF plate",
                            "machine": "TwoTrees 3018 Pro / GRBL; 300x180x40mm nominal; ER11; spindle 7-9krpm",
                            "cam": "S8000; G54 lower-left stock XY; Z0 top; T1 2mm carbide rough; T2 0.5mm carbide finish",
                            "roughFeedsMmMin": {"cut": 40, "plunge": 8},
                            "finishFeedsMmMin": {"cut": 20, "plunge": 5},
                            "cncRun": False},
        "evidence": {"phase12Root": "deliverables/phase12 preserved",
                     "phase10PressureRecovery": "null; solver aborted before iteration",
                     "phase11PressureRecovery": "null; solver aborted at initialization",
                     "phase12PressureRecovery": "null; local preflight only; no launch",
                     "phase13CfdRun": False, "stepReimportSolidValidationCount": len(step_audit_rows),
                     "ncFilesValidated": len(nc_audit_rows)},
        "generatedFiles": {"step": [str(p.relative_to(OUT)) for p in step_paths],
                           "gcode": [row["file"] for row in nc_audit_rows],
                           "reports": ["reports/phase13_cad_cam_report.md",
                                       "reports/phase13_mass_cg_budget.csv",
                                       "reports/phase13_rotor_strength_screen.csv",
                                       "reports/phase13_cg_layout.csv",
                                       "reports/phase13_lifting_body_sections.csv",
                                       "reports/phase13_nc_validation.csv",
                                       "reports/phase13_step_reimport_validation.csv"]}}
    (CONFIG_DIR / "phase13_fixed_powertrain_design.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8")

    write_report(config, mass_rows, strength_rows, area_record, nc_audit_rows,
                 step_audit_rows, body_section_rows, layout_rows, rotor_mass_kg, stator_mass_kg,
                 (body_cf_kg, body_pla_kg, case_cf_kg, case_pla_kg, inlet_cf_kg, inlet_pla_kg),
                 cg, modeled_and_payload_mass, budget_reserve_kg, rotor_fit)
    manifest = {"phase": 13, "files": config["generatedFiles"],
                "stepCount": len(step_paths), "gcodeCount": len(nc_audit_rows),
                "stepReimportPass": all(row["validCompound"] and row["allSolidsValidAndPositiveVolume"]
                                         for row in step_audit_rows),
                "ncCoordinateToolDepthPass": all(row["allCoordinatesInsideStock"] and row["depthInsideStock"]
                                                  for row in nc_audit_rows),
                "cncRun": False, "openfoamRun": False, "gcpRun": False}
    (REPORT_DIR / "phase13_generation_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"stepCount": len(step_paths), "gcodeCount": len(nc_audit_rows),
            "projectedAreaUnionCm2": area_cm2, "conservativeAreaBoundCm2": conservative_bound_cm2,
            "rotorMassKg": rotor_mass_kg, "statorMassKg": stator_mass_kg,
            "calculatedMassIncludingPayloadKg": modeled_and_payload_mass,
            "budgetReserveKg": budget_reserve_kg, "cgMm": list(cg),
            "minimumFOS": min(row["centrifugalOnlyFOSAtProofSpeed"] for row in strength_rows),
            "stepReimportPass": len(step_audit_rows) == len(step_paths),
            "ncFilesValidated": len(nc_audit_rows)}


def write_report(config: dict[str, Any], mass_rows: list[dict[str, Any]],
                 strength_rows: list[dict[str, Any]], area: dict[str, Any],
                 nc_rows: list[dict[str, Any]], step_rows: list[dict[str, Any]],
                 body_sections: list[dict[str, Any]], layout_rows: list[dict[str, Any]],
                 rotor_mass: float, stator_mass: float, material_split: tuple[float, ...],
                 cg: tuple[float, float, float], planned_mass: float, reserve: float,
                 rotor_fit: list[dict[str, float]]) -> None:
    body_cf, body_pla, case_cf, case_pla, inlet_cf, inlet_pla = material_split
    min_fos = min(row["centrifugalOnlyFOSAtProofSpeed"] for row in strength_rows)
    report = f"""# Phase 13 — fixed-powertrain R30 EDF CAD/CAM and airframe revision

## Disposition and traceability

Phase 13 is an additive revision under `deliverables/phase13`; Phase 12 and its results remain unchanged. The selected inlet is **R30 as a packaging start only**. Phase-10/11 OpenFOAM solver receipts have null pressure recovery (zero solver iterations), and Phase 12 is local preflight-only with no cloud launch. Therefore pressure recovery is **pending**, there is no CFD ranking, and R30 is not described as an aerodynamic optimum. No solver/GCP job or CNC operation was run.

The fixed installation is unchanged: six stock FA4119 KV350 motors (three per EDF set), two Turnigy Rapid 6S5000 packs in series (12S1P, 5Ah), fixed gear ratios 2.35/2.65/2.95, and all existing current, ESC, voltage and RPM limits. Rotor design speeds remain 29,375/33,125/36,360rpm. Each of two EDFs retains a 90mm OD, 88mm bore, 32mm hub, three rotor rows and three stator rows. There are two 25×120mm side-inlet slots per EDF, four total.

## Installed projected area

The exact geometry silhouette union, including both coincident fan disks, selected R30 split-turn inlet outlines/lips, board/spreader silhouettes, cooling-bay rails, motor/battery proxies and body envelope, is **{area['geometryOnlyProjectedAreaUnionCm2']:.3f}cm²**. The strict installed-area gate is `<75cm²`: **PASS**. The Phase-12 reserve-aware R30 upper screen (fan disk union + 10cm² generic structure reserve, no R30 outboard turn protrusion) is **{area['conservativeReserveAwareBoundCm2']:.3f}cm²**, also below 75cm². Keep this conservative reserve in place until dimensioned motor mounts and physical enclosures replace the package proxies.

## Rotor-root reinforcement and strength screen

Each rotor is a fused one-solid hub/blade B-rep. The root now starts at radius {p12.ROTOR_ROOT_R:.1f}mm, inserts {ROOT_INSERTION_MM:.1f}mm into the 32mm hub, and uses a 20% thick root airfoil lofting smoothly to the nominal 12% section over the first {p12.ROTOR_ROOT_BLEND_SPAN:.2f}mm ({ROOT_BLEND_SPAN_FRACTION:.0%} of span). This replaces Phase 12's 16% root loft and separate blade/hub compounds. The strengthened CAD rotor OD remains within the 88mm bore and the planform nest retains the 16mm billet thickness.

Proof speed is 1.25× the maximum fixed gear-derived rotor RPM at the unchanged 12,500rpm motor soft-limit basis: R1 {PROOF_RPM[0]:.2f}, R2 {PROOF_RPM[1]:.2f}, R3 {PROOF_RPM[2]:.2f}rpm. The Phase-12 centrifugal root stress reference (Kt=2.5, 6061-T6 yield 276MPa) is area-scaled by the actual NACA root-section area ratio. The smallest centrifugal-only FOS is **{min_fos:.3f}** (target ≥3.0). This is an analytical screen, not an FEA, fatigue, aero-bending, joint, burst-containment or spin-test qualification.

| Row | Gear-derived maximum rpm | 1.25× proof rpm | Phase-13 root area (mm²) | Centrifugal-only FOS | Gate |
|---|---:|---:|---:|---:|---|
"""
    for row in strength_rows:
        report += (f"| {row['rotorRow']} | {row['gearDerivedMaximumRotorRpm']:.0f} | "
                   f"{row['proofSpeedRpm_1p25x']:.2f} | {row['rootAreaPhase13Mm2']:.2f} | "
                   f"{row['centrifugalOnlyFOSAtProofSpeed']:.3f} | PASS |\n")
    report += f"""
## Mass budget and CG

The **sourced mass subtotal is {config['massBudget']['measuredOrSourcedMassKg']:.3f}kg**: motors 1.680kg, battery pair 1.426kg, bare ESC/flight PCBs 0.120585kg from `results/phase9_control_board_mass.csv`. Rotor/stator values below are computed from Phase-13 solid volumes; remaining values are individually identified estimates/allowances.

| Component | Mass (kg) | Evidence/basis |
|---|---:|---|
"""
    for row in mass_rows:
        report += f"| {row['component']} | {float(row['massKg']):.4f} | {row['basis']} |\n"
    report += f"""

**Planned loaded mass including the 2.0kg payload allocation: {planned_mass:.3f}kg.** CG including that payload is (X,Y,Z)=({cg[0]:.1f}, {cg[1]:.1f}, {cg[2]:.1f})mm in the lateral/vertical/flight-axis datum; the nonphysical {reserve:.3f}kg budget reserve is excluded from CG. The design ceiling is 10.5kg. Against the Phase-9 area-scaled 3km static T/W screen of 1.03955 at 11.5kg, inverse-mass scaling gives approximately **{1.0395516612139422*11.5/10.5:.3f} at 10.5kg**. This is an analytical low-speed margin screen, not installed-thrust or flight evidence.

### Explicit layout and cooling route

- Two battery envelopes (150×50×45mm packaging proxies) occupy the central bay at Z=-337.5 and -177.5mm. The adjacent axial faces leave a 10mm separation; the sourced mass is 0.713kg per pack. Verify the actual pack dimensions and retainable wiring bend radius before fit release.
- ESC PCB center is (0,52,220)mm with 150×150×1.6mm outline, Z145..295mm. Flight PCB is centered at (0,52,345)mm with 140×100×1.6mm outline, Z295..395mm. Their axial envelopes meet without overlap. The separate spreaders are at Y=54.2mm; the layout table records the dimensions and 0.6mm nominal stand-off.
- Cooling route is a dedicated open-ended side-bay tunnel, forward inlet at Z=145mm, wash over the board/spreader bay along the flight axis, and aft outlet at Z=395mm. Two side rails form the airflow guide; the propulsion inlets remain four independent 25×120mm slots. Verify pressure loss, sealing, fan interaction, and board thermal performance on hardware.
- The added hollow lofted lifting-body shell spans 120mm, has 1.5–5mm outer section thickness and 24–120mm chord sections, and is trimmed for both EDF casings. Section stations are in `phase13_lifting_body_sections.csv`. The central pod, nose/tail panels, side rails, and fan cases remain separately identifiable STEP bodies.

## Materials, composite and payload allowances

The ledger separately carries {body_cf+case_cf+inlet_cf:.3f}kg carbon/glass/resin laminate and {body_pla+case_pla+inlet_pla:.3f}kg PLA core across fuselage/lifting shell, EDF casing and four split-inlet branches. Layup estimate: one 200gsm carbon ply plus one 100gsm glass ply per face, resin:fibre mass ratio 0.8, 1.2mm printed-PLA core, 2700kg/m³ Al and 1240kg/m³ PLA assumptions. These are not weighed coupons. Six gearboxes (0.720kg), board population/connectors (0.200kg), spreaders (0.08235kg), harness (0.250kg), mounts (0.350kg), landing gear (0.400kg) and payload (2.000kg) are explicit allowances, not sourced mass facts. Remaining {reserve:.3f}kg is unallocated mass growth/design reserve beneath the 10.5kg ceiling.

## Stock, machine and CAM

- Six 300×50×16mm 6061-T6 billets; one rotor row/hub per motor/ESC channel. Billet ends X0..25 and X275..300 are reserved for clamps; all cutting coordinates are checked within CAM X25..275 and Y0..50.
- Two 250×100×5mm 6061-T6 plates; one 63-stator set (23/21/19) per EDF. Both nests fit the stock envelope.
- Machine basis: TwoTrees 3018 Pro / GRBL, nominal 300×180×40mm, ER11, spindle 7–9krpm. Programs use S8000, G54 lower-left stock XY and top-face Z0, T1 2mm carbide roughing and T2 0.5mm carbide finishing. Conservative programmed feeds are rough F40/F8 plunge and finish F20/F5 plunge (mm/min). Rotor roughing reaches Z-16 in 0.2mm layers; 0.5mm rotor finish is limited to the top 0.5mm band. Stator 0.5mm finish uses full-depth edge passes with long-flute tooling called out in the NC comments.
- Every NC file was parsed: all X/Y/Z words remain within declared stock and travel depth; rotor clamp margins are clear; G54, S8000, tool declaration, manual-change stop, and program end are present. Validation counts and extents are in `phase13_nc_validation.csv`. This is offline CAM input, not machine-release code; confirm fixtures, flute reach, tabs, workholding, and toolpaths in CAM before any future operation.
- All {len(step_rows)} STEP outputs were reimported; {sum(row['solidCount'] for row in step_rows)} reimported solids were individually checked valid with positive volume. Per-file validity and bounding boxes are in `phase13_step_reimport_validation.csv`.

### Fit and non-fitting geometry screen

No NC cutting-coordinate or stator-plate-nesting non-fit was found: all six rotor programs stay inside X25..275/Y0..50 on their 300×50×16mm billets, and both stator nests/programs stay within 250×100×5mm plates. The raw rotor billet length equals the machine's full nominal 300mm X travel, leaving **zero machine-envelope allowance** for fixture overhang or travel tolerance; actual clamp/workholding fit is not demonstrated and needs a machine-specific setup check. The revised rotor maximum planar B-rep envelope is {max(item['maxPlanarEnvelopeMm'] for item in rotor_fit):.3f}mm against the 88mm bore, leaving {min(item['diametralClearanceTo88mmBoreMm'] for item in rotor_fit):.3f}mm diametral CAD clearance; axial blade/hub thickness remains {max(item['axialThicknessMm'] for item in rotor_fit):.3f}mm against the 16mm billet. These are nominal model clearances without runout/tolerance allowance. No sourced FA4119 shaft/gearbox outline is available, and battery dimensions remain a 150×50×45mm proxy; those physical package fits are **not verified** and are the remaining fit unknowns.

## Deliverables

The STEP assembly, two EDF sets, R30 four-slot inlet, six rotor-billet nests, two stator-plate nests, and 16 NC programs are indexed by `reports/phase13_generation_manifest.json`. Design values and immutability declarations are in `configs/phase13_fixed_powertrain_design.json`. The assembly is a packaging/production concept; motor shaft and gearbox CAD are unavailable, and detailed fit, structural FEA, pressure recovery, thermal test, mass weighing, and flight validation remain open.
"""
    (REPORT_DIR / "phase13_cad_cam_report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(build_outputs(), indent=2))
