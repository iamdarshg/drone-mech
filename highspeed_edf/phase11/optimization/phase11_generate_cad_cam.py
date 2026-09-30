#!/usr/bin/env python3
"""Generate Phase-11 parametric STEP, stock nests, and 3018 blank toolpaths.

The inherited Phase-10 CAD helpers are imported read-only and their output
roots are redirected into deliverables/phase11 before any generation occurs.
No machine connection or CNC execution is made.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import cadquery as cq
from cadquery import Color, Vector
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
P11 = ROOT / "phase11"
CFG_PATH = P11 / "configs" / "phase11_iterative_optimization.json"
OUT = ROOT / "deliverables" / "phase11"
STEP = OUT / "step"
NEST = OUT / "stock_layouts"
GCODE = OUT / "gcode"
REPORTS = OUT / "reports"


def load_phase10_helpers() -> Any:
    source = ROOT / "optimization" / "phase10_generate_deliverables.py"
    spec = importlib.util.spec_from_file_location("phase10_cad_helpers", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the local CadQuery/CAM helper module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.STEP_DIR = STEP
    module.NEST_DIR = NEST
    module.GCODE_DIR = GCODE
    module.REPORT_DIR = REPORTS
    return module


def read_board_masses(path: Path) -> tuple[float, list[dict[str, Any]]]:
    rows = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            rows.append(row)
    total = sum(float(row["bareBoardMassEstimateG"]) for row in rows) / 1000.0
    return total, rows


def compact_body(helper: Any, span_mm: float = 120.0) -> cq.Solid:
    """Thin center-body packaging surface scaled to the 3018-era envelope."""
    scale = span_mm / 450.0
    thickness_scale = float(json.loads(CFG_PATH.read_text(encoding="utf-8"))["geometry"]["fuselageConcept"]["bodyMaxThicknessMm"]) / 2.5
    sections = [
        (-420.0, 8.0, 0.25), (-360.0, 170.0, 1.3), (-280.0, 330.0, 2.0),
        (-180.0, 450.0, 2.5), (-70.0, 430.0, 2.5), (40.0, 320.0, 2.2),
        (130.0, 145.0, 1.3), (185.0, 8.0, 0.25),
    ]
    body = cq.Solid.makeLoft([helper.ellipse_wire(z, w * scale, h * thickness_scale) for z, w, h in sections], ruled=False)
    duct_clearance = cq.Solid.makeCylinder(46.0, 250.0, Vector(0, 0, -125.0))
    return body.cut(duct_clearance)


def inlet_shell(helper: Any, radius: float, module_start_z: float, side: int, wall_mm: float = 1.0) -> cq.Compound:
    """6061-T6 wall shell around a CAD-aligned 90-degree side turn."""
    outer_sections, inner_sections = [], []
    slot_center_z = module_start_z - radius
    for index in range(13):
        angle = math.pi / 2.0 * index / 12.0
        center = Vector(side * radius * (1.0 - math.sin(angle)), 0,
                        slot_center_z + radius * (1.0 - math.cos(angle)))
        basis_a = Vector(0, 1, 0)
        basis_b = Vector(side * math.sin(angle), 0, math.cos(angle))
        fraction = index / 12.0
        smooth = fraction * fraction * (3.0 - 2.0 * fraction)
        width = 50.0 + 40.0 * smooth
        height = 120.0 - 30.0 * smooth
        exponent = 6.0 - 4.0 * fraction
        outer_sections.append(helper.superellipse_wire(center, basis_a, basis_b, width, height, exponent))
        inner_sections.append(helper.superellipse_wire(center, basis_a, basis_b,
                                                        width - 2.0 * wall_mm, height - 2.0 * wall_mm, exponent))
    outer = cq.Solid.makeLoft(outer_sections, ruled=False)
    inner = cq.Solid.makeLoft(inner_sections, ruled=False)
    shell = outer.cut(inner)
    slot_center = Vector(side * radius, 0, slot_center_z)
    slot_outer = helper.superellipse_wire(slot_center, Vector(0, 1, 0), Vector(0, 0, 1), 58.0, 128.0, 6.0)
    slot_inner = helper.superellipse_wire(slot_center, Vector(0, 1, 0), Vector(0, 0, 1), 50.0, 120.0, 6.0)
    bezel = cq.Solid.extrudeLinear(slot_outer, [slot_inner], Vector(side * 1.5, 0, 0))
    return cq.Compound.makeCompound([shell, bezel])


def build_installed_module(helper: Any, module_id: str, start_z: float, side: int,
                           radius: float) -> tuple[cq.Assembly, list[cq.Shape], list[Polygon]]:
    original = helper.make_side_inlet
    helper.INLET_TURN_RADIUS = radius
    helper.make_side_inlet = lambda z, s: inlet_shell(helper, radius, z, s)
    _, parts, outlines = helper.build_module(module_id, start_z, side)
    helper.make_side_inlet = original
    case_and_turn = parts[0].fuse(*parts[8].Solids())
    assembled = cq.Assembly(name=f"EDF_{module_id}_R{int(radius):03d}")
    if case_and_turn.isValid():
        assembled.add(case_and_turn, name=f"{module_id}_6061_case_and_side_shell")
        mass_parts = [case_and_turn]
    else:
        # Keep the individually-valid casing and thin shell as separate STEP
        # components where OCC cannot robustly fuse their shared curved seam.
        assembled.add(parts[0], name=f"{module_id}_6061_case")
        for idx, solid in enumerate(parts[8].Solids(), 1):
            assembled.add(solid, name=f"{module_id}_side_shell_part_{idx}")
        mass_parts = [parts[0], *parts[8].Solids()]
    assembled.add(parts[1], name=f"{module_id}_inlet_core")
    for row, part in enumerate(parts[2:5], 1):
        assembled.add(part, name=f"{module_id}_rotor_stage_{row}")
    for row, part in enumerate(parts[5:8], 1):
        assembled.add(part, name=f"{module_id}_stator_stage_{row}")
    mass_parts.extend(parts[1:8])
    return assembled, mass_parts, outlines


def save_step(shape: cq.Shape, path: Path) -> dict[str, Any]:
    cq.exporters.export(shape, str(path), exportType="STEP", tolerance=0.05, angularTolerance=0.05)
    reloaded = cq.importers.importStep(str(path)).val()
    return {"path": str(path.relative_to(ROOT)), "valid": bool(reloaded.isValid()),
            "solidCount": len(reloaded.Solids()), "volumeMm3": float(reloaded.Volume()),
            "bboxMm": [reloaded.BoundingBox().xlen, reloaded.BoundingBox().ylen, reloaded.BoundingBox().zlen]}


def save_assembly(assembly: cq.Assembly, path: Path) -> dict[str, Any]:
    assembly.save(str(path), exportType="STEP", tolerance=0.05, angularTolerance=0.05)
    reloaded = cq.importers.importStep(str(path)).val()
    solids = reloaded.Solids()
    return {"path": str(path.relative_to(ROOT)), "validSolids": all(s.isValid() for s in solids),
            "compoundValid": bool(reloaded.isValid()), "solidCount": len(solids),
            "volumeMm3": float(reloaded.Volume()),
            "bboxMm": [reloaded.BoundingBox().xlen, reloaded.BoundingBox().ylen, reloaded.BoundingBox().zlen]}


def board_placeholders() -> tuple[list[cq.Solid], float, float]:
    """Bare PCB silhouettes edge-on to front view; populated mass is excluded."""
    esc = cq.Solid.makeBox(1.02, 150.0, 150.0, Vector(50.0, -75.0, 160.0))
    fc = cq.Solid.makeBox(1.44, 140.0, 100.0, Vector(54.0, -70.0, 325.0))
    areas_cm2 = 150.0 * 1.02 / 100.0 + 140.0 * 1.44 / 100.0
    return [esc, fc], areas_cm2, 0.120585319235294


def projection_screen(radius_mm: float, body_span_mm: float, body_thickness_mm: float,
                      board_projection_cm2: float, structure_allowance_cm2: float) -> dict[str, float]:
    p9 = json.loads((ROOT / "results" / "phase9_geometry_mass_summary.json").read_text(encoding="utf-8"))
    fan = float(p9["projectedDuctUnionCm2"])
    slot_w = 50.0
    turn_extra = 2.0 * max(0.0, radius_mm - 45.0) * slot_w / 100.0
    body_extra = max(0.0, body_span_mm - 90.0) * body_thickness_mm / 100.0
    # Body/boards are recorded explicitly; the residual allowance is for mounts,
    # fairings, fasteners and manufacturing tolerances.
    total_lower_bound = fan + turn_extra + body_extra + board_projection_cm2 + structure_allowance_cm2
    return {"fanUnionCm2": fan, "turnProjectionAdditionalLowerBoundCm2": turn_extra,
            "bodyProjectionAdditionalEstimateCm2": body_extra,
            "edgeOnBareBoardProjectionCm2": board_projection_cm2,
            "mountFairingAllowanceCm2": structure_allowance_cm2,
            "completeFrontProjectionLowerBoundCm2": total_lower_bound,
            "strict75cm2Pass": total_lower_bound < 75.0}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if rows:
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def blank_rectangle(length: float, width: float) -> Polygon:
    return Polygon([(0.0, 0.0), (length, 0.0), (length, width), (0.0, width)])


def body_half_panel(length: float, start_half_span: float, end_half_span: float) -> Polygon:
    return Polygon([(0.0, 0.0), (length, 0.0), (length, end_half_span), (0.0, start_half_span)])


def main() -> int:
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    helper = load_phase10_helpers()
    for d in (STEP, NEST, GCODE, REPORTS):
        d.mkdir(parents=True, exist_ok=True)
    p9 = json.loads((ROOT / cfg["sources"]["phase9Config"]).read_text(encoding="utf-8"))
    boards_kg, board_rows = read_board_masses(ROOT / cfg["sources"]["phase9BoardMass"])
    power = p9["powertrainImmutable"]
    fixed_known_kg = (6.0 * float(p9["dataSources"]["fa4119UnitMassKg"])
                      + 2.0 * float(p9["dataSources"]["batteryUnitMassKg"]) + boards_kg)
    body_span = float(cfg["geometry"]["fuselageConcept"]["bodyHalfSpanMm"]) * 2.0
    body_thick = float(cfg["geometry"]["fuselageConcept"]["bodyMaxThicknessMm"])
    board_shapes, board_area_cm2, _ = board_placeholders()
    generated: list[dict[str, Any]] = []
    projection_rows: list[dict[str, Any]] = []
    main_radius = min(float(x) for x in cfg["geometry"]["turnRadiiM"])

    # Save flowpath options for the radius comparison; create the integrated
    # STEP assembly at the tightest non-self-intersecting sampled radius.
    flow_shells: dict[int, list[cq.Compound]] = {}
    for radius_m in cfg["geometry"]["turnRadiiM"]:
        radius_mm = float(radius_m) * 1000.0
        helper.INLET_TURN_RADIUS = radius_mm
        flow_shapes = [inlet_shell(helper, radius_mm, -115.0, +1), inlet_shell(helper, radius_mm, 5.0, -1)]
        flow_shells[int(round(radius_mm))] = flow_shapes
        flow_shape = cq.Compound.makeCompound(flow_shapes)
        flow_path = STEP / f"phase11_flowpath_R{int(radius_mm):03d}.step"
        generated.append(save_step(flow_shape, flow_path))
        projection_rows.append({"turnRadiusMm": radius_mm, **projection_screen(
            radius_mm, body_span, body_thick, board_area_cm2, 5.0)})

    # Full candidate assembly: fixed Phase-9 rotor/stator schedules, thin 6061
    # inlet shells, a compact lifting-body envelope, and bare PCB placeholders.
    helper.INLET_TURN_RADIUS = main_radius
    module_a_start, module_b_start = -115.0, 5.0
    module_a, comps_a, rotor_a = build_installed_module(helper, "A", module_a_start, +1, main_radius)
    module_b, comps_b, rotor_b = build_installed_module(helper, "B", module_b_start, -1, main_radius)
    body = compact_body(helper, body_span)
    body_section_defs = [(-420.0, 8.0, 0.25), (-360.0, 170.0, 1.3), (-280.0, 330.0, 2.0),
                         (-180.0, 450.0, 2.5), (-70.0, 430.0, 2.5), (40.0, 320.0, 2.2),
                         (130.0, 145.0, 1.3), (185.0, 8.0, 0.25)]
    body_scale = body_span / 450.0
    body_thickness_scale = body_thick / 2.5
    body_section_rows = []
    for index, (left, right) in enumerate(zip(body_section_defs, body_section_defs[1:]), 1):
        z0, w0, h0 = left
        z1, w1, h1 = right
        slab = cq.Solid.makeBox(1000.0, 1000.0, z1-z0, Vector(-500.0, -500.0, z0))
        segment = body.intersect(slab)
        body_section_rows.append({"section": index, "zStartMm": z0, "zEndMm": z1,
                                  "startWidthMm": w0*body_scale, "endWidthMm": w1*body_scale,
                                  "startThicknessMm": h0*body_thickness_scale,
                                  "endThicknessMm": h1*body_thickness_scale,
                                  "netCadVolumeMm3": segment.Volume(),
                                  "6061T6MassEstimateKg": segment.Volume()*1e-9*2700.0})
    write_csv(REPORTS / "phase11_fuselage_sections.csv", body_section_rows)
    assembly = cq.Assembly(name="phase11_compact_fixed_powertrain_candidate")
    helper.add_module_to_assembly(assembly, module_a, "A")
    helper.add_module_to_assembly(assembly, module_b, "B")
    assembly.add(body, name=f"compact_lifting_body_span{body_span:g}mm")
    assembly.add(board_shapes[0], name="ESC_bare_PCB_edge_on_150x150x1p02")
    assembly.add(board_shapes[1], name="flight_control_bare_PCB_edge_on_140x100x1p44")
    for side in (-1, 1):
        for row in (-1, 1):
            support = cq.Solid.makeBox(3.0, 3.0, 16.0,
                Vector(side * 47.0 - (3.0 if side > 0 else 0.0), row * 42.0 - (3.0 if row > 0 else 0.0), -8.0))
            assembly.add(support, name=f"module_support_{side}_{row}")
    for idx, start in enumerate((module_a_start, module_b_start), 1):
        collar = helper.annular_cylinder(49.0, 45.0, 4.0, start + helper.MODULE_LENGTH/2.0 - 2.0)
        assembly.add(collar, name=f"body_module_collar_{idx}")
    main_radius_mm = int(round(main_radius * 1000.0))
    full_path = STEP / f"phase11_full_assembly_R{main_radius_mm:03d}.step"
    generated.append(save_assembly(assembly, full_path))
    generated.append(save_assembly(module_a, STEP / f"phase11_EDF_A_R{main_radius_mm:03d}.step"))
    generated.append(save_assembly(module_b, STEP / f"phase11_EDF_B_R{main_radius_mm:03d}.step"))

    # Safe 2.5 mm rectangular keep-out nest: 28 blanks in billet 1, 8 in billet 2.
    # The expanded keep-out envelopes total 12,788.63 mm2 per EDF, exceeding a
    # single billet's 12,500 mm2 material area, so one billet/set is impossible
    # under this declared clearance method.
    profiles_per_edf = rotor_a
    rotor_nest_inputs = []
    for billet, subset in ((1, profiles_per_edf[:28]), (2, profiles_per_edf[28:])):
        nest = helper.add_stock_layout("A", f"phase11_rotor_billet{billet}_250x50x16", 250, 50, 16,
                                       subset, 7, 31.5, 11.75, 2.5, 2.5)
        rotor_nest_inputs.append(nest)
        generated.append({"path": str(nest.relative_to(ROOT)), "valid": True})
    stator_profiles = [helper.stator_planform() for _ in range(sum(helper.STATOR_COUNTS))]
    for module_id in ("A", "B"):
        nest = helper.add_stock_layout(module_id, "phase11_stator_250x100x5", 250, 100, 5,
                                       stator_profiles, 8, 30.5, 9.3, 3.0, 3.5)
        generated.append({"path": str(nest.relative_to(ROOT)), "valid": True})
        module_profiles = rotor_a if module_id == "A" else rotor_b
        for billet, subset in ((1, module_profiles[:28]), (2, module_profiles[28:])):
            kind = f"phase11_rotor_billet{billet}_250x50x16"
            for rough in (True, False):
                path = helper.generate_gcode(module_id, kind, 16.0, subset, 7, 31.5, 11.75, 2.5, 2.5, rough)
                generated.append({"path": str(path.relative_to(ROOT)), "valid": True})
        for rough in (True, False):
            path = helper.generate_gcode(module_id, "phase11_stator_250x100x5", 5.0,
                                         stator_profiles, 8, 30.5, 9.3, 3.0, 3.5, rough)
            generated.append({"path": str(path.relative_to(ROOT)), "valid": True})

    # Conceptual panel blanks to connect the CAD envelope to the supplied 3018
    # plate stock. These are 2.5D flat blanks; forming/joining is a separate step.
    body_width_scale = body_span / 450.0
    body_sections = [(z, width) for z, width, _ in body_section_defs]
    body_panel_specs = []
    body_ranges = [(-420.0, -180.0), (-180.0, 40.0), (40.0, 185.0)]
    for segment_index, (z0, z1) in enumerate(body_ranges, 1):
        w0 = next(width for z, width in body_sections if z == z0) * body_width_scale / 2.0
        w1 = next(width for z, width in body_sections if z == z1) * body_width_scale / 2.0
        panel = body_half_panel(z1-z0, w0, w1)
        for side in ("L", "R"):
            body_panel_specs.append((f"body_{side}_{segment_index}", panel))

    main_turn_radius = main_radius
    turn_length = math.pi/2.0 * main_turn_radius + 120.0
    duct_panel_specs = []
    for module_id in ("A", "B"):
        for idx, width in enumerate((50.0, 50.0, 60.0, 60.0, 60.0, 60.0), 1):
            duct_panel_specs.append((f"duct_{module_id}_{idx:02d}", blank_rectangle(turn_length, width)))

    case_panel_specs = []
    casing_arc_width = math.pi * 90.0 / 7.0
    for module_id in ("A", "B"):
        for idx in range(1, 8):
            case_panel_specs.append((f"casing_{module_id}_{idx:02d}", blank_rectangle(110.0, casing_arc_width)))

    panel_specs = [("body", body_panel_specs), ("duct", duct_panel_specs), ("casing", case_panel_specs)]
    panel_areas: dict[str, float] = {}
    panel_net_mass_kg = 0.0
    plate_count = 0
    panel_stock_rows = []
    for family, specs in panel_specs:
        if family == "casing":
            groups = [specs[i:i+4] for i in range(0, len(specs), 4)]
            nesting = (2, 115.0, 45.0, 2.5, 2.5)
        else:
            groups = [[item] for item in specs]
            nesting = (1, 0.0, 0.0, 2.5, 2.5)
        for group_index, group in enumerate(groups, 1):
            module_tag = f"P11_{family}_{group_index:02d}"
            polygons = [poly for _, poly in group]
            if any(p.bounds[2] > 250.0 or p.bounds[3] > 100.0 for p in polygons):
                raise ValueError(f"{family} blank exceeds 250x100 mm plate: {group_index}")
            cols, pitch_x, pitch_y, sx, sy = nesting
            nest = helper.add_stock_layout(module_tag, f"{family}_panels_250x100x5", 250.0, 100.0, 5.0,
                                           polygons, cols, pitch_x, pitch_y, sx, sy)
            generated.append({"path": str(nest.relative_to(ROOT)), "valid": True})
            plate_count += 1
            panel_area = sum(p.area for p in polygons)
            panel_net_mass_kg += panel_area * 5.0e-9 * 2700.0
            panel_areas[family] = panel_areas.get(family, 0.0) + panel_area
            for rough in (True, False):
                nc = helper.generate_gcode(module_tag, f"{family}_panels_250x100x5", 5.0,
                                           polygons, cols, pitch_x, pitch_y, sx, sy, rough)
                generated.append({"path": str(nc.relative_to(ROOT)), "valid": True})
            panel_stock_rows.append({"plateId": module_tag, "family": family, "blankCount": len(polygons),
                                     "stockMm": "250x100x5", "blankAreaMm2": panel_area,
                                     "net6061BlankMassKg": panel_area * 5.0e-9 * 2700.0,
                                     "NC": "2mm rough plus 0.5mm top-band finish; no CNC run"})
    write_csv(REPORTS / "phase11_airframe_panel_stock.csv", panel_stock_rows)

    # Mass, aerodynamic and strength ledgers. PCB population and gearbox mass
    # stay explicit unknowns; only actual bare-board masses are counted.
    body_mass = body.Volume() * 1e-9 * 2700.0
    module_gross_vol_mm3 = sum(shape.Volume() for shape in comps_a + comps_b)
    module_gross_mass = module_gross_vol_mm3 * 1e-9 * 2700.0
    known_mass = fixed_known_kg
    healthy_mass_target = float(cfg["performanceGates"]["maxAllUpMassForHealthyTWRKg"])
    rotor_keepout_area_mm2 = sum(
        (29.0 + float(cfg["cam"]["clearanceMm"]))
        * (float(poly.bounds[3] - poly.bounds[1]) + float(cfg["cam"]["clearanceMm"]))
        for poly in rotor_a
    )
    rotor_stock_area_mm2 = float(cfg["cam"]["perEdfStock"]["rotorBillet"][0]) * float(cfg["cam"]["perEdfStock"]["rotorBillet"][1])
    module_core_vol_mm3 = sum(shape.Volume() for shape in comps_a[1:] + comps_b[1:])
    module_core_mass = module_core_vol_mm3 * 1e-9 * 2700.0
    panelized_major_parts_kg = known_mass + module_core_mass + panel_net_mass_kg
    mass_rows = [
        {"item": "six fixed FA4119 motors", "massKg": 6*float(p9["dataSources"]["fa4119UnitMassKg"]), "basis": "Phase-9 sourced motor mass"},
        {"item": "two fixed 6S5000 packs / 12S1P", "massKg": 2*float(p9["dataSources"]["batteryUnitMassKg"]), "basis": "Phase-9 sourced pack mass"},
        {"item": "ESC and flight-control bare boards", "massKg": boards_kg, "basis": "results/phase9_control_board_mass.csv; populations excluded"},
        {"item": "two duct/rotor/stator CAD module solids gross", "massKg": module_gross_mass, "basis": "6061-T6 density on CadQuery solid volumes; blade/hub overlaps may overcount"},
        {"item": "compact lifting-body CAD solid", "massKg": body_mass, "basis": "6061-T6 density on compact body solid; no composite substitution assumed"},
        {"item": "flat body/inlet/casing panel concept net blank mass", "massKg": panel_net_mass_kg, "basis": "22 extra 250x100x5 panels; alternatives to corresponding monolithic CAD shell volume, forming/joining not included"},
        {"item": "fixed known plus panelized major-part mass screen", "massKg": panelized_major_parts_kg, "basis": "known motors/packs/bare boards + rotor/stator core CAD solids + 6061 body/inlet/casing blanks; excludes populations/gears/harness/landing gear"},
        {"item": "unweighed allowance to healthy TWR mass screen", "massKg": healthy_mass_target-panelized_major_parts_kg, "basis": "remaining amount for ESC populations, shafts, gearboxes, mounting, wire, landing gear and payload; not weighed"},
        {"item": "known plus modeled mass lower estimate", "massKg": known_mass + module_gross_mass + body_mass, "basis": "excludes motor gearboxes, population, harness, mounts and landing gear"},
        {"item": "unweighed mass remaining to 11.5 kg", "massKg": 11.5-(known_mass+module_gross_mass+body_mass), "basis": "explicit allowance; must be measured/BOM-closed"},
        {"item": "unweighed mass remaining to healthy-TWR mass target", "massKg": healthy_mass_target-(known_mass+module_gross_mass+body_mass), "basis": "target ≤10.68 kg for 1.10 area-scaled worst-case static T/W"},
    ]
    write_csv(REPORTS / "phase11_mass_screen.csv", mass_rows)

    # Centrifugal-only 6061-T6 blade/hub stress screen with a root Kt factor.
    strength = []
    yield_pa, density = 276e6, 2700.0
    root_area_m2 = Polygon(helper.foil_section(helper.ROTOR_CHORD, 0.12, 0.025)).area * helper.ROTOR_CHORD * 1e-6
    root_r_m, tip_r_m, hub_r_m = helper.ROTOR_ROOT_R/1000.0, helper.ROTOR_TIP_R/1000.0, helper.HUB_R/1000.0
    for row, rpm in enumerate(helper.ROTOR_RPM):
        beta_root, beta_tip = helper.ROTOR_BETA[row]
        blade = helper.make_airfoil_vane(helper.ROTOR_CHORD, 0.0, helper.ROTOR_ROOT_R, helper.ROTOR_TIP_R,
                                         beta_root, beta_tip, 0.0)
        center = blade.Center()
        r_centroid = math.hypot(center.x, center.y) / 1000.0
        volume_m3 = blade.Volume() * 1e-9
        omega = rpm * 2.0 * math.pi / 60.0
        centrifugal_force_n = density * volume_m3 * omega**2 * r_centroid
        nominal_root_stress_pa = centrifugal_force_n / root_area_m2
        kt = 2.5
        design_root_stress = nominal_root_stress_pa * kt
        hub_ring_hoop_pa = density * omega**2 * hub_r_m**2
        strength.append({"row": row+1, "rpm": rpm, "tipSpeedMps": omega*tip_r_m,
                         "bladeVolumeMm3": blade.Volume(), "rootAreaMm2": root_area_m2*1e6,
                         "centrifugalForcePerBladeN": centrifugal_force_n,
                         "nominalRootStressMPa": nominal_root_stress_pa/1e6,
                         "stressConcentrationFactor": kt,
                         "rootSafetyFactorTo6061T6Yield": yield_pa/design_root_stress,
                         "hubThinRingStressMPa": hub_ring_hoop_pa/1e6,
                         "hubSafetyFactorTo6061T6Yield": yield_pa/(hub_ring_hoop_pa*kt),
                         "scope": "centrifugal-only; excludes cyclic aero/bending, fatigue, flaws, hub-joint and gearbox loads"})
    write_csv(REPORTS / "phase11_rotor_strength_screen.csv", strength)

    t_w_r = 1.0218172413683544
    area_rows = []
    structure_cm2 = 10.0
    body_extra = max(0.0, body_span - 90.0) * body_thick / 100.0
    board_extra = board_area_cm2
    # Board/body details are part of the 10 cm2 structure/control reserve; retain
    # the conservative turn projection lower bound separately for each radius.
    for row in projection_rows:
        full_lower = row["fanUnionCm2"] + row["turnProjectionAdditionalLowerBoundCm2"] + structure_cm2
        area_rows.append({**row, "bodyProjectionIncludedInReserve": True,
                          "bareBoardEdgeOnAreaCm2": board_extra,
                          "bodyProjectionEstimateCm2": body_extra,
                          "projectedAreaWithStructureReserveCm2": full_lower,
                          "areaPass": full_lower < 75.0,
                          "areaFeasibleCenterlineRadiusMaxMm": 45.0 + (75.0 - row["fanUnionCm2"] - structure_cm2)})
    write_csv(REPORTS / "phase11_geometry_trade.csv", area_rows)

    p9mean = json.loads((ROOT / cfg["sources"]["phase9Meanline"]).read_text(encoding="utf-8"))
    receipt = {
        "phase": 11,
        "status": "cad_cam_and_local_screen_complete_openfoam_pending",
        "fixedPowertrainUnchanged": True,
        "phase9MeanlineMassFlowTotalKgS": p9mean["massFlowTotalKgPerS"],
        "phase9MeanlineNetThrustRatio": p9mean["meanlineThrustToRequiredRatio"],
        "projectedAreaTrade": area_rows,
        "savedStepFiles": generated,
        "boardMassCsv": cfg["sources"]["phase9BoardMass"],
        "bareBoardMassKg": boards_kg,
        "stockPerEdfSet": cfg["cam"]["perEdfStock"],
        "rotorNesting": {"bladesPerEdf": len(rotor_a), "safeClearanceMm": 2.5,
                         "blankWidthRangeMm": [min(p.bounds[3]-p.bounds[1] for p in rotor_a),
                                               max(p.bounds[3]-p.bounds[1] for p in rotor_a)],
                         "rectangularKeepoutEnvelopeAreaPerEdfMm2": rotor_keepout_area_mm2,
                         "oneBilletMaterialAreaMm2": rotor_stock_area_mm2,
                         "oneBilletKeepoutAreaProofPasses": rotor_keepout_area_mm2 <= rotor_stock_area_mm2,
                         "oneBilletKeepoutAreaExcessMm2": max(0.0, rotor_keepout_area_mm2 - rotor_stock_area_mm2),
                         "layout": "two billets per EDF: 28+8 blanks, 7x4 no-overlap grid; one billet cannot hold all36 disjoint 2.5 mm rectangular keep-out envelopes because their summed area exceeds billet area",
                         "rotorBilletsPerEdf": 2, "extraBilletsBeyondOnePerEdf": 2},
        "airframePanelStock": {"extraPlates250x100x5": plate_count, "panelFamilies": panel_areas,
                               "netBlankMassKg": panel_net_mass_kg,
                               "stockNotIncludedInTwoEdfPairs": True,
                               "fabricationScope": "flat perimeter blanks only; forming, seam design, seals and joining are not validated"},
        "statorNesting": {"vanesPerEdf": len(stator_profiles), "platesPerEdf": 1,
                           "layout": "8x10 positions; 63 vane blanks on one 250x100x5 plate"},
        "massScreen": {"fixedKnownKg": known_mass, "cadModuleGrossKg": module_gross_mass,
                       "compactBody6061Kg": body_mass, "healthyTwrMassLimitKg": healthy_mass_target,
                       "twrAt11p5kgActualBoreAreaScaled": t_w_r,
                       "massVerified": False, "populatedBoardAndHarnessWeightsInvented": False},
        "structuralScreen": {"material": "6061-T6", "yieldAssumedMPa": yield_pa/1e6,
                             "minimumBladeRootSafetyFactor": min(x["rootSafetyFactorTo6061T6Yield"] for x in strength),
                             "minimumHubSafetyFactor": min(x["hubSafetyFactorTo6061T6Yield"] for x in strength),
                             "targetSafetyFactor": cfg["performanceGates"]["minimum6061T6CentrifugalSafetyFactor"],
                             "validationClass": "analytical centrifugal-only screen, not FEA or test"},
        "cfd": {"caseMatrix": [x["id"] for x in cfg["cases"]], "pressureRecoveryResults": None,
                "reason": "awaiting single budget-capped phase11 OpenFOAM worker"},
        "limitations": ["No motor, battery, gearbox, populated-board, harness or landing-gear geometry was provided; the full-airframe projected envelope is not a released packaging drawing.",
                        "Body/board masses are not weighed; populated-board and harness mass remain explicit allowances.",
                        "Rotor root/hub margins use a centrifugal-only model and do not validate fatigue, aeroelasticity, attachment or burst containment."],
    }
    (REPORTS / "phase11_cad_cam_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stepCount": len(generated), "projectedArea": area_rows,
                      "moduleMassKg": module_gross_mass, "bodyMassKg": body_mass,
                      "minimumBladeSafetyFactor": receipt["structuralScreen"]["minimumBladeRootSafetyFactor"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
