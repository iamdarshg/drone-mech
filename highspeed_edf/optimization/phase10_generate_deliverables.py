"""Generate the Phase-10 fixed-powertrain EDF/fuselage CAD and CAM package.

All dimensions are millimetres. The model is deliberately a local, offline
CadQuery build: it does not call aerodynamic/cloud solvers and never opens a
CNC connection.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import cadquery as cq
from cadquery import Color, Vector
from shapely.affinity import translate as shp_translate
from shapely.geometry import Polygon


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables" / "phase10"
STEP_DIR = OUT / "step"
NEST_DIR = OUT / "stock_layouts"
GCODE_DIR = OUT / "gcode"
REPORT_DIR = OUT / "reports"

for directory in (STEP_DIR, NEST_DIR, GCODE_DIR, REPORT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

DUCT_OD = 90.0
DUCT_ID = 88.0
HUB_OD = 32.0
HUB_R = HUB_OD / 2.0
ROTOR_TIP_R = 43.6
ROTOR_ROOT_R = 14.6
ROTOR_SPAN = ROTOR_TIP_R - ROTOR_ROOT_R  # 29.0 mm; 1.4 mm is embedded in hub
ROTOR_CHORD = 16.0
STATOR_CHORD = 8.0
ROTOR_COUNTS = (13, 12, 11)
STATOR_COUNTS = (23, 21, 19)
ROTOR_RPM = (29375.0, 33125.0, 36360.0)
ROTOR_Z = (12.0, 48.0, 84.0)
STATOR_Z = (30.0, 66.0, 102.0)
MODULE_LENGTH = 110.0
INLET_TURN_RADIUS = 225.0
SLOT_Y = 50.0
SLOT_AXIAL = 120.0

ROTOR_BETA = ((-30.0, -19.0), (-33.3, -21.5), (-36.0, -23.7))
STATOR_BETA = ((16.3, -5.0), (18.5, -6.0), (20.4, -6.9))


def foil_section(chord: float, thickness: float = 0.12, camber: float = 0.02,
                 camber_pos: float = 0.40, samples: int = 20) -> list[tuple[float, float]]:
    """Closed NACA 4-digit-like section, normalized to 0..1 chord."""
    xs = [(1.0 - math.cos(math.pi * i / samples)) / 2.0 for i in range(samples + 1)]

    def yt(x: float) -> float:
        return 5.0 * thickness * (
            0.2969 * math.sqrt(max(x, 0.0)) - 0.1260 * x - 0.3516 * x * x
            + 0.2843 * x**3 - 0.1015 * x**4
        )

    def yc(x: float) -> float:
        if not camber:
            return 0.0
        if x < camber_pos:
            return camber / camber_pos**2 * (2.0 * camber_pos * x - x * x)
        return camber / (1.0 - camber_pos) ** 2 * (
            (1.0 - 2.0 * camber_pos) + 2.0 * camber_pos * x - x * x
        )

    upper = [(x, chord * (yc(x) + yt(x))) for x in xs]
    lower = [(x, chord * (yc(x) - yt(x))) for x in reversed(xs)]
    return upper + lower


def make_airfoil_vane(
    chord: float,
    theta: float,
    r_root: float,
    r_tip: float,
    beta_root: float,
    beta_tip: float,
    axial_center: float,
    camber: float = 0.025,
) -> cq.Solid:
    """Create a lofted, twisted airfoil vane around the EDF's Z axis."""
    sections = []
    foil = foil_section(chord, 0.12, camber)
    stations = (0.0, 0.28, 0.58, 0.82, 1.0)
    for u in stations:
        radius = r_root + (r_tip - r_root) * u
        beta = math.radians(beta_root + (beta_tip - beta_root) * u)
        radial = (math.cos(theta), math.sin(theta))
        tangent = (-math.sin(theta), math.cos(theta))
        sweep = 0.8 * math.sin(math.pi * u)
        points = []
        for x, y in foil:
            # Chord lies mostly on the axial (Z) direction; the small tangential
            # component is the design metal angle used by the 720 km/h screen.
            axial = axial_center + (x - 0.5) * chord * math.cos(beta) - y * math.sin(beta)
            tan = (x - 0.5) * chord * math.sin(beta) + y * math.cos(beta) + sweep
            px = radius * radial[0] + tan * tangent[0]
            py = radius * radial[1] + tan * tangent[1]
            points.append(Vector(px, py, axial))
        sections.append(cq.Wire.makePolygon(points, close=True))
    return cq.Solid.makeLoft(sections, ruled=False)


def annular_cylinder(ro: float, ri: float, length: float, z0: float) -> cq.Solid:
    outer = cq.Solid.makeCylinder(ro, length, Vector(0, 0, z0), Vector(0, 0, 1))
    inner = cq.Solid.makeCylinder(ri, length, Vector(0, 0, z0), Vector(0, 0, 1))
    return outer.cut(inner)


def make_rotor_stage(row: int, z0: float) -> tuple[cq.Compound, list[Polygon]]:
    count = ROTOR_COUNTS[row]
    beta_root, beta_tip = ROTOR_BETA[row]
    hub = cq.Solid.makeCylinder(HUB_R, ROTOR_CHORD, Vector(0, 0, z0 - ROTOR_CHORD / 2))
    shaft = cq.Solid.makeCylinder(4.0, ROTOR_CHORD + 2.0,
                                  Vector(0, 0, z0 - ROTOR_CHORD / 2 - 1.0))
    hub = hub.cut(shaft)
    blades = [
        make_airfoil_vane(ROTOR_CHORD, 2.0 * math.pi * i / count,
                          ROTOR_ROOT_R, ROTOR_TIP_R, beta_root, beta_tip, z0)
        for i in range(count)
    ]
    # Individual blade solids overlap the hub by 1.4 mm at the root. This is a
    # deliberate assembly socket allowance, not an interference-free production fit.
    return cq.Compound.makeCompound([hub, *blades]), rotor_planform(row)


def make_stator_stage(row: int, z0: float) -> cq.Compound:
    count = STATOR_COUNTS[row]
    beta_root, beta_tip = STATOR_BETA[row]
    vanes = [
        make_airfoil_vane(STATOR_CHORD, 2.0 * math.pi * i / count,
                          17.6, 43.5, beta_root, beta_tip, z0, camber=0.015)
        for i in range(count)
    ]
    # Fixed inner and tip rails support the stator vanes and keep the airflow
    # annulus separated from the rotating 32 mm hub and the 88 mm duct bore.
    vanes.append(annular_cylinder(17.6, 16.8, STATOR_CHORD, z0 - STATOR_CHORD / 2))
    vanes.append(annular_cylinder(44.0, 43.45, STATOR_CHORD, z0 - STATOR_CHORD / 2))
    return cq.Compound.makeCompound(vanes)


def superellipse_wire(center: Vector, basis_a: Vector, basis_b: Vector,
                      width: float, height: float, exponent: float,
                      points: int = 48) -> cq.Wire:
    coords = []
    power = 2.0 / exponent
    for i in range(points):
        angle = 2.0 * math.pi * i / points
        ca, sa = math.cos(angle), math.sin(angle)
        a = math.copysign(abs(ca) ** power, ca) * width / 2.0
        b = math.copysign(abs(sa) ** power, sa) * height / 2.0
        coords.append(center + basis_a.multiply(a) + basis_b.multiply(b))
    return cq.Wire.makePolygon(coords, close=True)


def circle_wire(center: Vector, basis_a: Vector, basis_b: Vector,
                radius: float, points: int = 48) -> cq.Wire:
    coords = []
    for i in range(points):
        angle = 2.0 * math.pi * i / points
        coords.append(center + basis_a.multiply(radius * math.cos(angle))
                      + basis_b.multiply(radius * math.sin(angle)))
    return cq.Wire.makePolygon(coords, close=True)


def make_side_inlet(module_start_z: float, side: int) -> cq.Compound:
    """Quarter-turn, 225 mm centreline-radius slot-to-annulus transition."""
    r = INLET_TURN_RADIUS
    slot_center_z = module_start_z - r
    outer_wires = []
    core_wires = []
    for idx in range(13):
        a = (math.pi / 2.0) * idx / 12.0
        center = Vector(side * r * (1.0 - math.sin(a)), 0,
                        slot_center_z + r * (1.0 - math.cos(a)))
        tangent = Vector(-side * math.cos(a), 0, math.sin(a))
        basis_a = Vector(0, 1, 0)
        basis_b = Vector(side * math.sin(a), 0, math.cos(a))
        station_fraction = idx / 12.0
        smooth = station_fraction * station_fraction * (3.0 - 2.0 * station_fraction)
        width = 50.0 + 40.0 * smooth
        height = 120.0 - 30.0 * smooth
        exponent = 6.0 - 4.0 * (idx / 12.0)
        outer_wires.append(superellipse_wire(center, basis_a, basis_b,
                                             width, height, exponent))
        core_radius = 0.8 + 14.7 * smooth
        core_wires.append(circle_wire(center, basis_a, basis_b, core_radius))
    outer = cq.Solid.makeLoft(outer_wires, ruled=False)
    core = cq.Solid.makeLoft(core_wires, ruled=False)
    duct = outer.cut(core)

    # A thin rounded rectangular side-slot bezel records the exact 50 x 120 opening.
    slot_center = Vector(side * r, 0, slot_center_z)
    slot_outer = superellipse_wire(slot_center, Vector(0, 1, 0), Vector(0, 0, 1),
                                   58.0, 128.0, 6.0)
    slot_inner = superellipse_wire(slot_center, Vector(0, 1, 0), Vector(0, 0, 1),
                                   50.0, 120.0, 6.0)
    bezel = cq.Solid.extrudeLinear(slot_outer, [slot_inner], Vector(side * 1.5, 0, 0))
    return cq.Compound.makeCompound([duct, bezel])


def ellipse_wire(z: float, width: float, thickness: float, points: int = 64) -> cq.Wire:
    verts = [Vector((width / 2.0) * math.cos(2.0 * math.pi * i / points),
                    (thickness / 2.0) * math.sin(2.0 * math.pi * i / points), z)
             for i in range(points)]
    return cq.Wire.makePolygon(verts, close=True)


def make_lifting_body() -> cq.Solid:
    """Thin lenticular lifting-body envelope; structural/aero validation excluded."""
    sections = [
        (-420.0, 8.0, 0.25), (-360.0, 170.0, 1.3), (-280.0, 330.0, 2.0),
        (-180.0, 450.0, 2.5), (-70.0, 430.0, 2.5), (40.0, 320.0, 2.2),
        (130.0, 145.0, 1.3), (185.0, 8.0, 0.25),
    ]
    body = cq.Solid.makeLoft([ellipse_wire(z, w, h) for z, w, h in sections], ruled=False)
    # Clear the two coaxial EDF casings through the thin lifting-body skin.
    clearance = cq.Solid.makeCylinder(46.0, 250.0, Vector(0, 0, -125.0))
    return body.cut(clearance)


def build_module(module_id: str, module_start_z: float, side: int) -> tuple[cq.Assembly, list[cq.Shape], list[Polygon]]:
    assembly = cq.Assembly(name=f"EDF_{module_id}_three_rotor_three_stator")
    components: list[cq.Shape] = []
    rotor_layout: list[Polygon] = []
    case = annular_cylinder(DUCT_OD / 2.0, DUCT_ID / 2.0, MODULE_LENGTH, module_start_z)
    assembly.add(case, name=f"{module_id}_duct_case_OD90_ID88_L110")
    components.append(case)
    inlet_nose = cq.Solid.makeCylinder(15.5, 4.0, Vector(0, 0, module_start_z))
    assembly.add(inlet_nose, name=f"{module_id}_stationary_inlet_core_to_R1")
    components.append(inlet_nose)
    for row, local_z in enumerate(ROTOR_Z):
        z = module_start_z + local_z
        rotor, outlines = make_rotor_stage(row, z)
        assembly.add(rotor, name=f"{module_id}_R{row + 1}_N{ROTOR_COUNTS[row]}_RPM{int(ROTOR_RPM[row])}")
        components.append(rotor)
        rotor_layout.extend(outlines)
    for row, local_z in enumerate(STATOR_Z):
        stator = make_stator_stage(row, module_start_z + local_z)
        assembly.add(stator, name=f"{module_id}_S{row + 1}_N{STATOR_COUNTS[row]}_C8")
        components.append(stator)
    inlet = make_side_inlet(module_start_z, side)
    assembly.add(inlet, name=f"{module_id}_side_slot_50x120_R225_transition")
    components.append(inlet)
    return assembly, components, rotor_layout


def rotor_planform(row: int) -> list[Polygon]:
    """2.5D CNC blank outline: 29 mm radial envelope, swept/cambered projection."""
    beta_root, beta_tip = ROTOR_BETA[row]
    coords_upper = []
    coords_lower = []
    for i in range(25):
        u = i / 24.0
        x = ROTOR_SPAN * u
        beta = math.radians(beta_root + (beta_tip - beta_root) * u)
        chord_projection = ROTOR_CHORD * abs(math.sin(beta))
        foil_projection = 0.12 * ROTOR_CHORD * math.cos(beta)
        width = max(5.2, chord_projection + 0.12 * foil_projection)
        width = min(width, 9.0)
        center = 0.015 * x + 0.25 * math.sin(math.pi * u)
        coords_upper.append((x, center + width / 2.0))
        coords_lower.append((x, center - width / 2.0))
    outline = coords_upper + list(reversed(coords_lower))
    profile = Polygon(outline)
    profile = shp_translate(profile, yoff=-profile.bounds[1])
    # Every row contributes its specified individual blanks to the stock nest.
    return [profile for _ in range(ROTOR_COUNTS[row])]


def stator_planform() -> Polygon:
    points_top = []
    points_bottom = []
    span = 27.0  # supported gaspath span; remaining stock envelope is root engagement
    for i in range(25):
        u = i / 24.0
        x = span * u
        beta = math.radians(18.0 - 24.0 * u)
        projected = STATOR_CHORD * abs(math.sin(beta)) + 1.2
        width = min(7.5, max(2.5, projected))
        center = 0.025 * x + 0.25 * math.sin(math.pi * u)
        points_top.append((x, center + width / 2.0))
        points_bottom.append((x, center - width / 2.0))
    profile = Polygon(points_top + list(reversed(points_bottom)))
    return shp_translate(profile, yoff=-profile.bounds[1])


def add_stock_layout(module_id: str, stock_kind: str, stock_x: float, stock_y: float,
                     thickness: float, profiles: list[Polygon], cols: int,
                     pitch_x: float, pitch_y: float, start_x: float, start_y: float,
                     z_lift: float = 0.0) -> Path:
    name = f"{module_id}_{stock_kind}_stock_nest.step"
    assembly = cq.Assembly(name=f"{module_id}_{stock_kind}_nest")
    stock = cq.Workplane("XY").box(stock_x, stock_y, thickness,
                                     centered=(False, False, False)).val()
    assembly.add(stock, name=f"raw_stock_{stock_x:g}x{stock_y:g}x{thickness:g}",
                 color=Color(0.60, 0.67, 0.72, 0.18))
    for index, profile in enumerate(profiles):
        row, col = divmod(index, cols)
        placed = shp_translate(profile, xoff=start_x + col * pitch_x,
                               yoff=start_y + row * pitch_y)
        points = [Vector(x, y, z_lift) for x, y in list(placed.exterior.coords)[:-1]]
        blank = cq.Workplane("XY").polyline([(p.x, p.y) for p in points]).close().extrude(thickness).val()
        assembly.add(blank, name=f"{module_id}_{stock_kind}_blank_{index + 1:02d}",
                     color=Color(0.90, 0.47, 0.15, 0.85))
    path = NEST_DIR / name
    assembly.save(str(path), exportType="STEP", tolerance=0.05, angularTolerance=0.05)
    return path


def profile_path(profile: Polygon, xoff: float, yoff: float, tool_offset: float) -> list[tuple[float, float]]:
    buffered = profile.buffer(tool_offset, quad_segs=2, join_style="round")
    if buffered.geom_type == "MultiPolygon":
        buffered = max(buffered.geoms, key=lambda p: p.area)
    coords = list(buffered.exterior.coords)[:-1]
    # Remove very short segments to keep NC manageable while retaining the swept profile.
    simplified = [coords[0]]
    for point in coords[1:]:
        if math.dist(point, simplified[-1]) >= 0.8:
            simplified.append(point)
    if math.dist(simplified[-1], simplified[0]) < 0.8 and len(simplified) > 3:
        simplified.pop()
    return [(x + xoff, y + yoff) for x, y in simplified]


def contour_with_tabs(points: list[tuple[float, float]],
                      tab_count: int = 3, tab_width: float = 2.0) -> list[tuple[float, float, bool]]:
    ring = points + [points[0]]
    lengths = [math.dist(ring[i], ring[i + 1]) for i in range(len(points))]
    total = sum(lengths)
    tabs = [((i + 0.31) * total / tab_count, tab_width) for i in range(tab_count)]

    def in_tab(distance: float) -> bool:
        return any(abs(((distance - center + total / 2.0) % total) - total / 2.0) <= width / 2.0
                   for center, width in tabs)

    out: list[tuple[float, float, bool]] = []
    cursor = 0.0
    for i, length in enumerate(lengths):
        start, end = ring[i], ring[i + 1]
        cuts = [0.0, length]
        for center, width in tabs:
            for boundary in (center - width / 2.0, center + width / 2.0):
                local = boundary - cursor
                if 1e-5 < local < length - 1e-5:
                    cuts.append(local)
        cuts = sorted(set(cuts))
        for j, local in enumerate(cuts):
            if j == len(cuts) - 1:
                continue
            mid = cursor + (local + cuts[j + 1]) / 2.0
            t = local / length
            point = (start[0] + (end[0] - start[0]) * t,
                     start[1] + (end[1] - start[1]) * t)
            flag = in_tab(mid)
            if not out or math.dist((out[-1][0], out[-1][1]), point) > 1e-6:
                out.append((point[0], point[1], flag))
        cursor += length
    return out


def generate_gcode(module_id: str, stock_kind: str, thickness: float,
                   profiles: list[Polygon], cols: int, pitch_x: float, pitch_y: float,
                   start_x: float, start_y: float, rough: bool) -> Path:
    if "rotor" in stock_kind:
        stepdown, feed, plunge = 0.20, 55.0, 12.0
        finish_depth, tool = 0.50, 0.5 if not rough else 2.0
    else:
        stepdown, feed, plunge = 0.25, 60.0, 14.0
        finish_depth, tool = 0.50, 0.5 if not rough else 2.0

    operation = "2mm_rough" if rough else "0p5mm_finish_top_0p5mm"
    path = GCODE_DIR / f"edf_{module_id}_{stock_kind}_{operation}.nc"
    lines = [
        f"(Phase-10 {module_id} {stock_kind} {operation})",
        "(GRBL 3-axis; offline generated only; CNC was not run.)",
        "(G54 XY origin = stock lower-left; Z0 = stock top; units mm.)",
        ("(Stock = 250 x 50 x 16 mm billet.)" if "rotor" in stock_kind
         else "(Stock = 250 x 100 x 5 mm plate.)"),
        "(775 spindle set conservatively to 7000 rpm; 2-flute carbide.)",
        "(Stock alloy/material was not specified; verify material/tool chipload before use.)",
        "(Do not use these paths on carbon-fibre or unknown abrasive/composite stock.)",
        "(No ATC: install and measure tool manually at the M0 prompt.)",
        "(Clamp stock flat; keep clamps outside all 2 mm cutter paths.)",
        "(Dry-run above stock with spindle disabled before cutting.)",
        "G21 G17 G90 G94 G54",
        "G40 G49 G80",
        "G0 Z5.000",
    ]
    if rough:
        lines.extend([
            "M5",
            "M0 (Install 2.0 mm 2-flute carbide rougher; set G54 Z0 on stock top)",
            ("(Rotor billet: cutter must have >=18 mm usable flute/neck reach; otherwise do not cut through.)"
             if "rotor" in stock_kind else
             "(Plate: cutter must have >=6 mm usable flute/neck reach; verify clamps and spoilboard.)"),
            ("(2 mm rough: F55 mm/min, plunge F12, 0.20 mm stepdown, 0.25 mm radial allowance.)"
             if "rotor" in stock_kind else
             "(2 mm rough: F60 mm/min, plunge F14, 0.25 mm stepdown, 0.25 mm radial allowance.)"),
            "(Final through-pass leaves 1 mm tall tabs; remove parts and tabs by hand after routing.)",
            "M3 S7000",
            "G4 P3",
        ])
        depths = []
        z = stepdown
        while z < thickness - 1e-8:
            depths.append(-z)
            z += stepdown
        depths.append(-thickness)
        for depth in depths:
            lines.append(f"(Rough profile pass Z{depth:.3f}; 1.0 mm tabs on final pass)")
            for index, _profile in enumerate(profiles):
                row, col = divmod(index, cols)
                points = profile_path(_profile, start_x + col * pitch_x,
                                      start_y + row * pitch_y, 1.25)
                path_with_tabs = contour_with_tabs(points)
                if not path_with_tabs:
                    continue
                sx, sy, _ = path_with_tabs[0]
                lines.extend([f"G0 X{sx:.3f} Y{sy:.3f}", "G0 Z1.000",
                              f"G1 Z{depth:.3f} F{plunge:.1f}"])
                for x, y, tab in path_with_tabs[1:]:
                    z_cmd = depth + 1.0 if depth <= -thickness + 1e-7 and tab else depth
                    lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z_cmd:.3f} F{feed:.1f}")
                x, y, tab = path_with_tabs[0]
                z_cmd = depth + 1.0 if depth <= -thickness + 1e-7 and tab else depth
                lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z_cmd:.3f} F{feed:.1f}")
                lines.append("G0 Z1.000")
    else:
        lines.extend([
            "M5",
            "M0 (Install 0.5 mm 2-flute carbide finisher; re-touch G54 Z0)",
            "M3 S7000",
            "G4 P3",
            "(F20 mm/min; 0.10 mm Z stepdown; shallow finish band only: Z-0.1 to Z-0.5.)",
            "(This is not a full-thickness wall finish; rough-side allowance remains below Z-0.5.)",
        ])
        depths = (-0.10, -0.20, -0.30, -0.40, -finish_depth)
        for depth in depths:
            for index, _profile in enumerate(profiles):
                row, col = divmod(index, cols)
                points = profile_path(_profile, start_x + col * pitch_x,
                                      start_y + row * pitch_y, 0.25)
                if len(points) < 3:
                    continue
                sx, sy = points[0]
                lines.extend([f"G0 X{sx:.3f} Y{sy:.3f}", "G0 Z1.000",
                              f"G1 Z{depth:.3f} F6.0"])
                for x, y in points[1:] + [points[0]]:
                    lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{depth:.3f} F20.0")
                lines.append("G0 Z1.000")
    lines.extend(["M5", "G0 Z5.000", "M30", ""])
    path.write_text("\n".join(lines), encoding="ascii", newline="\n")
    return path


def add_module_to_assembly(target: cq.Assembly, module: cq.Assembly, prefix: str) -> None:
    for child in module.children:
        target.add(child.obj, name=f"{prefix}_{child.name}", loc=child.loc, color=child.color)


def export_step(assembly: cq.Assembly, path: Path) -> None:
    assembly.save(str(path), exportType="STEP", tolerance=0.05, angularTolerance=0.05)


def write_manifest(files: Iterable[Path]) -> None:
    manifest = {
        "phase": 10,
        "powertrainImmutable": {
            "motors": "6 x stock Flycci FA4119 KV350",
            "battery": "2 x Turnigy Rapid 6S 5000mAh in series; 12S1P; 5Ah",
        },
        "nominalGeometry": {
            "ductOuterDiameterMm": DUCT_OD,
            "ductBoreMm": DUCT_ID,
            "hubDiameterMm": HUB_OD,
            "nominalBladeSpanMm": ROTOR_SPAN,
            "rotorChordMm": ROTOR_CHORD,
            "statorChordMm": STATOR_CHORD,
            "rotorCountsPerModule": list(ROTOR_COUNTS),
            "statorCountsPerModule": list(STATOR_COUNTS),
            "rotorRpm720Kmh": list(ROTOR_RPM),
            "slotMm": [SLOT_Y, SLOT_AXIAL],
            "sideTurnRadiusMm": INLET_TURN_RADIUS,
        },
        "camOutputs": [str(p.relative_to(ROOT)) for p in files],
        "cutStockNesting": {
            "perEdfSet": {
                "rotorBlanks": 36,
                "rotorBilletMm": [250, 50, 16],
                "rotorBilletsPerEdf": 2,
                "rotorNest": "Each billet uses a 6 x 4 no-overlap keep-out grid; 24 blanks in billet 1 and 12 in billet 2 per EDF.",
                "statorVanes": sum(STATOR_COUNTS),
                "statorPlateMm": [250, 100, 5],
                "statorNest": "8 columns x 10 rows; 63 of 80 positions used",
            },
            "bothEdfs": "2 plates plus 4 billets: two plate/billet pairs plus two additional rotor billets",
            "unprovidedMachinedParts": [
                "3 rotor hub assemblies per EDF (8 mm bore is a provisional interface)",
                "90 mm casing rings and row support details",
                "side-inlet elbow shells and fuselage/lifting-body structure",
            ],
        },
        "ncProcess": {
            "controller": "GRBL; no CNC execution",
            "machine": "TwoTrees 3018 Pro nominal 300 x 180 x 40 mm; ER11 775 spindle",
            "spindleRpm": 7000,
            "roughToolMm": 2.0,
            "roughStepdownMm": {"rotorBillet": 0.20, "statorPlate": 0.25},
            "finishToolMm": 0.5,
            "finishDepthMm": 0.5,
            "workOffset": "G54; XY stock lower-left; Z0 stock top",
            "finishScope": "top 0.5 mm perimeter band only; 0.5 mm cutter is not used through stock thickness",
        },
    }
    (REPORT_DIR / "phase10_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    generated: list[Path] = []
    module_a_start = -115.0
    module_b_start = 5.0
    module_a, comp_a, rotor_profiles_a = build_module("A", module_a_start, +1)
    module_b, comp_b, rotor_profiles_b = build_module("B", module_b_start, -1)

    # Installed-position module configurations include their own mirrored inlet transition.
    a_step = STEP_DIR / "phase10_edf_A_configuration.step"
    b_step = STEP_DIR / "phase10_edf_B_configuration.step"
    export_step(module_a, a_step)
    export_step(module_b, b_step)
    generated.extend((a_step, b_step))

    body = make_lifting_body()
    assembly = cq.Assembly(name="phase10_fixed_powertrain_full_airframe")
    add_module_to_assembly(assembly, module_a, "A")
    add_module_to_assembly(assembly, module_b, "B")
    assembly.add(body, name="thin_lenticular_lifting_body_interface_450mm_span")
    # Interface collars are external printed/composite parts, not cut from the two stock sizes.
    for idx, start in enumerate((module_a_start, module_b_start), 1):
        collar = annular_cylinder(49.0, 45.0, 4.0, start + MODULE_LENGTH / 2.0 - 2.0)
        assembly.add(collar, name=f"body_to_EDF_interface_collar_{idx}")
    assembly_step = STEP_DIR / "phase10_full_assembly.step"
    export_step(assembly, assembly_step)
    generated.append(assembly_step)

    # Stock layouts are exact dimensional cut envelopes for the two supported NC blank sets.
    rotor_profiles = rotor_profiles_a + rotor_profiles_b
    stator_profile = stator_planform()
    stator_profiles = [stator_profile for _ in range(sum(STATOR_COUNTS))]
    rotor_billet_layouts: list[tuple[str, list[Polygon]]] = []
    for module_id, rotor_profiles_module in (("A", rotor_profiles_a), ("B", rotor_profiles_b)):
        for billet_index in (1, 2):
            billet_profiles = (rotor_profiles_module[:24] if billet_index == 1
                               else rotor_profiles_module[24:])
            rotor_billet_layouts.append((f"{module_id}_billet{billet_index}", billet_profiles))
            rotor_nest = add_stock_layout(
                module_id, f"rotor_billet{billet_index}_250x50x16", 250.0, 50.0, 16.0,
                billet_profiles, 6, 31.5, 10.7, 4.0, 3.0
            )
            generated.append(rotor_nest)
        stator_nest = add_stock_layout(module_id, "stator_250x100x5", 250.0, 100.0, 5.0,
                                       stator_profiles, 8, 30.5, 9.3, 3.0, 3.5)
        generated.append(stator_nest)

        for billet_name, billet_profiles in [entry for entry in rotor_billet_layouts if entry[0].startswith(module_id)]:
            kind = f"rotor_{billet_name.split('_')[-1]}_250x50x16"
            generated.append(generate_gcode(module_id, kind, 16.0, billet_profiles,
                                            6, 31.5, 10.7, 4.0, 3.0, True))
            generated.append(generate_gcode(module_id, kind, 16.0, billet_profiles,
                                            6, 31.5, 10.7, 4.0, 3.0, False))
        kind = "stator_vanes_250x100x5"
        generated.append(generate_gcode(module_id, kind, 5.0, stator_profiles,
                                        8, 30.5, 9.3, 3.0, 3.5, True))
        generated.append(generate_gcode(module_id, kind, 5.0, stator_profiles,
                                        8, 30.5, 9.3, 3.0, 3.5, False))

    # Simple numerical checks that are written alongside—not substituted for—the CAD.
    duct_union_cm2 = math.pi * (DUCT_OD / 20.0) ** 2
    phase9_area = duct_union_cm2 + 10.0
    inlet_area_cm2 = 2.0 * SLOT_Y * SLOT_AXIAL / 100.0
    fan_annulus_actual_cm2_per_edf = math.pi * ((DUCT_ID / 20.0) ** 2 - (HUB_OD / 20.0) ** 2)
    transition_projection_extra_lower_bound_cm2 = 2.0 * max(
        0.0, (INLET_TURN_RADIUS - DUCT_OD / 2.0) * SLOT_Y / 100.0
    )
    installed_area_lower_bound_cm2 = duct_union_cm2 + transition_projection_extra_lower_bound_cm2
    phase9_reserve_plus_transitions_cm2 = phase9_area + transition_projection_extra_lower_bound_cm2
    actual_total_annulus_cm2 = 2.0 * fan_annulus_actual_cm2_per_edf
    phase9_total_annulus_cm2 = 2.0 * math.pi * ((DUCT_OD / 20.0) ** 2 - (HUB_OD / 20.0) ** 2)
    area_only_twr_sensitivity = 1.0395516612139422 * (actual_total_annulus_cm2 / phase9_total_annulus_cm2) ** (1.0 / 3.0)
    rotor_planform_area_per_edf_mm2 = sum(profile.area for profile in rotor_profiles_a)
    audit = {
        "fixedPowertrain": "unchanged; six FA4119 KV350 motors and 12S1P 5Ah series battery",
        "nominalCandidateProjectedAreaCm2": phase9_area,
        "nominalCandidateAreaGatePass": phase9_area < 75.0,
        "inletTransitionFrontProjectionAdditionalLowerBoundCm2": transition_projection_extra_lower_bound_cm2,
        "fullInstalledProjectedAreaLowerBoundExcludingBodyCm2": installed_area_lower_bound_cm2,
        "phase9TenCm2ReservePlusTransitionEnvelopeCm2": phase9_reserve_plus_transitions_cm2,
        "fullInstalledProjectedAreaGatePass": False,
        "projectedAreaDisposition": "Phase-9 73.62 cm2 gate excludes the R225 side-transition packaging; conservative projected footprint exceeds 75 cm2.",
        "ductOuterDiameterMm": DUCT_OD,
        "ductInnerDiameterMm": DUCT_ID,
        "hubDiameterMm": HUB_OD,
        "rotorNominalSpanMm": ROTOR_SPAN,
        "rotorActiveSpanWithinHubToTipMm": ROTOR_TIP_R - HUB_R,
        "rotorTipClearanceMm": DUCT_ID / 2.0 - ROTOR_TIP_R,
        "fanAnnulusAreaActualCm2PerEdf": fan_annulus_actual_cm2_per_edf,
        "phase9AnnulusAreaAssumedCm2PerEdf": math.pi * ((DUCT_OD / 20.0) ** 2 - (HUB_OD / 20.0) ** 2),
        "areaOnlyStaticTwrSensitivityAt3km11p5kg": area_only_twr_sensitivity,
        "areaOnlyStaticTwrSensitivityBasis": "Phase-9 worst-R0 static T/W scaled by (actual annulus/Phase-9 annulus)^(1/3); not a replacement thrust solve.",
        "slotTotalAreaCm2": inlet_area_cm2,
        "stockPairNesting": {
            "rotorProfilesPerEdf": 36,
            "rotorBlankArrayCapacityPerBillet": 24,
            "rotorBilletsPerEdf": 2,
            "rotorBilletsRequiredBothEdfs": 4,
            "rotorPlanformAreaPerEdfMm2": rotor_planform_area_per_edf_mm2,
            "combinedRotorPlanformAreaOnePairMm2": 2.0 * rotor_planform_area_per_edf_mm2,
            "oneBilletMaterialAreaMm2": 250.0 * 50.0,
            "statorVanesPerEdf": sum(STATOR_COUNTS),
            "statorBlankArrayCapacityPerPlate": 80,
            "statorPlatesRequiredBothEdfs": 2,
            "onePairForBothEdfs": False,
            "buyTwoPairsTotal": False,
            "recommendedPurchase": "2 x 250x100x5 plates and 4 x 250x50x16 billets (two pairs plus two additional billets)",
            "nestingBasis": "Each rotor billet uses a 6x4 profile keep-out grid with 2.5 mm clearance between 29x8.2 mm blank envelopes; 24 blanks are placed in billet 1 and 12 in billet 2 per EDF. Each stator plate uses an 8x10 array for 63 vanes.",
        },
        "massAndAerodynamics": {
            "allUpMassTargetKg": 11.5,
            "massVerified": False,
            "cdA720TargetM2": 0.0009,
            "cdAVerified": False,
            "note": "The existing Phase-9 values are analytical screens; CAD has no measured mass, blade-row rig result, CFD result, or wind-tunnel drag evidence.",
        },
        "generatedFiles": [str(p.relative_to(ROOT)) for p in generated],
    }
    (REPORT_DIR / "phase10_geometry_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    write_manifest(generated)
    print(json.dumps({"generated": len(generated),
                      "step": sum(p.suffix.lower() == ".step" for p in generated),
                      "gcode": sum(p.suffix.lower() == ".nc" for p in generated),
                      "audit": str((REPORT_DIR / "phase10_geometry_audit.json").relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
