"""Generate bounded preCICE/OpenFOAM/CalculiX wing-sector FSI candidates.

The candidate geometry is regenerated from the Phase-15 wing station schedule
(not copied from the old 90 mm layout).  Gmsh creates independent fluid and
solid meshes with named coupling/root patches; the MSH2 solid mesh is translated
to a CalculiX input deck.  This is a component aeroelastic screen, not a whole
aircraft/rotating-EDF simulation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import gmsh


ROOT = Path(__file__).resolve().parents[1]
EDF_ROOT = ROOT.parent
GEOM_ROOT = EDF_ROOT / "deliverables" / "phase15_geometry"
OUT = ROOT / "fsi"
CASES = OUT / "cases"
REPORTS = OUT / "reports"
RHO_AIR = 0.909
P_STATIC = 70_100.0
T_STATIC = 268.65
U_FLIGHT = 200.0
AOA_DEG = 0.5
TURBULENCE_INTENSITY = 0.01
K_INLET = 1.5 * (TURBULENCE_INTENSITY * U_FLIGHT) ** 2
OMEGA_INLET = 180.0
GAMMA = 1.4
R_AIR = 287.05
CP_AIR = 1004.685
NU_AIR = 1.62e-5
E_EQ = 1.0e10
NU_SOLID = 0.30
RHO_SOLID = 150.0
COUPLING_DT = 1.0e-5
COUPLING_WINDOWS = 100


def naca_section(x_local: float, le_z: float, chord: float,
                 max_thickness: float, samples: int = 32) -> int:
    """Create a closed NACA-00-like wire in a plane of constant lateral X."""
    tc = max_thickness / chord
    xs = [(1.0 - math.cos(math.pi * i / samples)) / 2.0 for i in range(samples + 1)]

    def thickness(x: float) -> float:
        return chord * 5.0 * tc * (
            0.2969 * math.sqrt(max(0.0, x)) - 0.1260 * x - 0.3516 * x * x
            + 0.2843 * x**3 - 0.1015 * x**4
        )

    alpha = math.radians(AOA_DEG)
    profile = [(x, thickness(x) + (0.25 - x) * chord * math.tan(alpha)) for x in xs]
    profile.extend((x, -thickness(x) + (0.25 - x) * chord * math.tan(alpha))
                   for x in reversed(xs[1:-1]))
    point_tags = [gmsh.model.occ.addPoint(x_local, chord_y, le_z + x * chord)
                  for x, chord_y in profile]
    edges = [gmsh.model.occ.addLine(point_tags[i], point_tags[(i + 1) % len(point_tags)])
             for i in range(len(point_tags))]
    return gmsh.model.occ.addWire(edges, checkClosed=True)


def wing_volume(thickness_mm: float) -> tuple[int, dict[str, float]]:
    """Create the outboard panel between x=80.33 and 260 mm from the master wing."""
    x0, x1 = 80.33e-3, 260.0e-3
    f0, f1 = x0 / 0.260, 1.0
    chord0 = (425.0 + (305.0 - 425.0) * f0) / 1000.0
    chord1 = 305.0e-3
    le0 = (-270.0 + x0 * 1000.0 * math.tan(math.radians(25.0))) / 1000.0
    le1 = (-270.0 + 260.0 * math.tan(math.radians(25.0))) / 1000.0
    t0 = min(thickness_mm / 1000.0, 0.10 * chord0)
    t1 = min(thickness_mm / 1000.0, 0.10 * chord1)
    w0 = naca_section(x0, le0, chord0, t0)
    w1 = naca_section(x1, le1, chord1, t1)
    volume = gmsh.model.occ.addThruSections([w0, w1], makeSolid=True, makeRuled=False)
    gmsh.model.occ.synchronize()
    vols = [tag for dim, tag in volume if dim == 3]
    if len(vols) != 1:
        raise RuntimeError(f"candidate wing loft did not make one solid: {volume}")
    return vols[0], {
        "xRootM": x0, "xTipM": x1, "rootChordM": chord0, "tipChordM": chord1,
        "rootLeadingEdgeZM": le0, "tipLeadingEdgeZM": le1,
        "rootThicknessM": t0, "tipThicknessM": t1,
    }


def add_phys(dim: int, entities: list[int], tag: int, name: str) -> None:
    if not entities:
        raise RuntimeError(f"empty physical group: {name}")
    gmsh.model.addPhysicalGroup(dim, sorted(set(entities)), tag)
    gmsh.model.setPhysicalName(dim, tag, name)


def boundary_tags(volume: int) -> list[int]:
    return sorted({tag for dim, tag in gmsh.model.getBoundary(
        [(3, volume)], combined=False, oriented=False, recursive=False) if dim == 2})


def surface_center(surface: int) -> tuple[float, float, float]:
    c = gmsh.model.occ.getCenterOfMass(2, surface)
    return float(c[0]), float(c[1]), float(c[2])


def bbox2(surface: int) -> tuple[float, float, float, float, float, float]:
    return tuple(float(x) for x in gmsh.model.getBoundingBox(2, surface))


def set_mesh_fields(surface_tags: list[int], min_size: float, max_size: float) -> None:
    gmsh.option.setNumber("Mesh.MeshSizeMin", min_size)
    gmsh.option.setNumber("Mesh.MeshSizeMax", max_size)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 8)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1)
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.option.setNumber("Mesh.Algorithm3D", 1)
    gmsh.option.setNumber("Mesh.Optimize", 1)
    gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.option.setNumber("Mesh.SaveAll", 0)
    distance = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(distance, "FacesList", surface_tags)
    gmsh.model.mesh.field.setNumber(distance, "Sampling", 80)
    threshold = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(threshold, "InField", distance)
    gmsh.model.mesh.field.setNumber(threshold, "SizeMin", min_size)
    gmsh.model.mesh.field.setNumber(threshold, "SizeMax", max_size)
    gmsh.model.mesh.field.setNumber(threshold, "DistMin", 0.025)
    gmsh.model.mesh.field.setNumber(threshold, "DistMax", 0.30)
    gmsh.model.mesh.field.setAsBackgroundMesh(threshold)


def fluid_mesh(path: Path, wing_tag: int, dimensions: dict[str, float]) -> dict[str, Any]:
    # The half-wing is an outboard sector of the 520 mm, 25-degree-swept CAD wing.
    x0, x1 = dimensions["xRootM"], dimensions["xTipM"]
    z_le0, z_le1 = dimensions["rootLeadingEdgeZM"], dimensions["tipLeadingEdgeZM"]
    chord0, chord1 = dimensions["rootChordM"], dimensions["tipChordM"]
    y_max = max(dimensions["rootThicknessM"], dimensions["tipThicknessM"]) / 2
    z_min = min(z_le0, z_le1) - 1.0 * chord0
    z_max = max(z_le0 + chord0, z_le1 + chord1) + 3.0 * chord0
    x_min, x_max = x0 - 1.25 * chord0, x1 + 1.25 * chord0
    y_min, y_max = -max(0.35, 2.0 * y_max), max(0.35, 2.0 * y_max)

    box_tag = gmsh.model.occ.addBox(x_min, y_min, z_min,
                                    x_max - x_min, y_max - y_min, z_max - z_min)
    gmsh.model.occ.synchronize()
    gmsh.model.occ.fragment([(3, box_tag)], [(3, wing_tag)], removeObject=True, removeTool=False)
    gmsh.model.occ.synchronize()
    volumes = [tag for dim, tag in gmsh.model.getEntities(3)]
    mass_by_volume = {tag: float(gmsh.model.occ.getMass(3, tag)) for tag in volumes}
    fluid_tag = max(volumes, key=mass_by_volume.get)
    solid_tag = min(volumes, key=mass_by_volume.get)
    f_bounds = boundary_tags(fluid_tag)
    s_bounds = boundary_tags(solid_tag)
    shared = set(f_bounds).intersection(s_bounds)
    fsi, root, inlet, outlet, farfield = [], [], [], [], []
    root_x = x0
    for surf in sorted(shared):
        bb = bbox2(surf)
        if abs(bb[0] - root_x) < 2e-6 and abs(bb[3] - root_x) < 2e-6:
            root.append(surf)
        else:
            fsi.append(surf)
    if not fsi or not root:
        raise RuntimeError(f"fluid/wing interface classification failed: fsi={len(fsi)} root={len(root)}")
    for surf in sorted(set(f_bounds) - shared):
        bb = bbox2(surf)
        if abs(bb[2] - z_min) < 2e-6 and abs(bb[5] - z_min) < 2e-6:
            inlet.append(surf)
        elif abs(bb[2] - z_max) < 2e-6 and abs(bb[5] - z_max) < 2e-6:
            outlet.append(surf)
        else:
            farfield.append(surf)
    if not inlet or not outlet or not farfield:
        raise RuntimeError(f"farfield patch classification failed: inlet={len(inlet)} outlet={len(outlet)} far={len(farfield)}")

    add_phys(3, [fluid_tag], 1, "fluid")
    add_phys(2, inlet, 11, "inlet")
    add_phys(2, outlet, 12, "outlet")
    add_phys(2, farfield, 13, "farfield")
    add_phys(2, fsi, 14, "fsi")
    add_phys(2, root, 15, "rootWall")
    set_mesh_fields(fsi + root, 0.012, 0.12)
    gmsh.model.mesh.generate(3)
    gmsh.write(str(path))
    elements = gmsh.model.mesh.getElements(3, fluid_tag)
    cell_count = sum(len(block) for block in elements[1])
    return {"mesh": path.name, "fluidCells": int(cell_count), "fluidVolumeM3": mass_by_volume[fluid_tag],
            "wingVolumeM3": mass_by_volume[solid_tag], "patchFaceCounts": {
                "fsi": len(fsi), "rootWall": len(root), "inlet": len(inlet),
                "outlet": len(outlet), "farfield": len(farfield)},
            "domainM": {"xMin": x_min, "xMax": x_max, "yMin": y_min, "yMax": y_max,
                        "zMin": z_min, "zMax": z_max}}


def solid_mesh(path: Path, thickness_mm: float) -> dict[str, Any]:
    gmsh.model.add(f"structural_{thickness_mm:g}mm")
    solid_tag, dims = wing_volume(thickness_mm)
    surfaces = boundary_tags(solid_tag)
    root, fsi = [], []
    for surf in surfaces:
        bb = bbox2(surf)
        if abs(bb[0] - dims["xRootM"]) < 2e-6 and abs(bb[3] - dims["xRootM"]) < 2e-6:
            root.append(surf)
        else:
            fsi.append(surf)
    add_phys(3, [solid_tag], 1, "wingSolid")
    add_phys(2, fsi, 14, "fsi")
    add_phys(2, root, 15, "root")
    step_path = path.with_suffix(".step")
    gmsh.write(str(step_path))
    set_mesh_fields(fsi + root, 0.009, 0.018)
    gmsh.model.mesh.generate(3)
    gmsh.write(str(path))
    elements = gmsh.model.mesh.getElements(3, solid_tag)
    node_count = len(gmsh.model.mesh.getNodes()[0])
    cell_count = sum(len(block) for block in elements[1])
    return {"mesh": path.name, "candidateStep": step_path.name,
            "solidNodes": int(node_count), "solidElements": int(cell_count),
            "couplingSurfaceEntities": len(fsi), "rootSurfaceEntities": len(root),
            "wingVolumeM3": float(gmsh.model.occ.getMass(3, solid_tag))}


def parse_msh2(path: Path) -> tuple[dict[int, tuple[float, float, float]], dict[tuple[int, int], list[list[int]]], dict[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    physical_names: dict[int, str] = {}
    nodes: dict[int, tuple[float, float, float]] = {}
    cells: dict[tuple[int, int], list[list[int]]] = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line == "$PhysicalNames":
            count = int(lines[i + 1].strip())
            for raw in lines[i + 2:i + 2 + count]:
                dim, tag, name = raw.split(maxsplit=2)
                physical_names[int(tag)] = name.strip().strip('"')
            i += count + 3
        elif line == "$Nodes":
            count = int(lines[i + 1].strip())
            for raw in lines[i + 2:i + 2 + count]:
                cols = raw.split()
                nodes[int(cols[0])] = (float(cols[1]), float(cols[2]), float(cols[3]))
            i += count + 3
        elif line == "$Elements":
            count = int(lines[i + 1].strip())
            for raw in lines[i + 2:i + 2 + count]:
                cols = [int(x) for x in raw.split()]
                elm_type, ntag = cols[1], cols[2]
                tags = cols[3:3 + ntag]
                conn = cols[3 + ntag:]
                physical_tag = tags[0] if tags else 0
                key = (elm_type, physical_tag)
                cells.setdefault(key, []).append(conn)
            i += count + 3
        else:
            i += 1
    if not nodes or not cells:
        raise RuntimeError(f"empty or unreadable MSH2 file {path}")
    return nodes, cells, physical_names


def write_calculix(mesh_path: Path, inp_path: Path, thickness_mm: float) -> dict[str, Any]:
    nodes, cells, names = parse_msh2(mesh_path)
    tag_by_name = {tag: name.lower() for tag, name in names.items()}
    tets = [conn for (etype, ptag), block in cells.items() if etype == 4 for conn in block]
    iface_triangles = [conn for (etype, ptag), block in cells.items()
                       if etype == 2 and tag_by_name.get(ptag) == "fsi" for conn in block]
    root_triangles = [conn for (etype, ptag), block in cells.items()
                      if etype == 2 and tag_by_name.get(ptag) == "root" for conn in block]
    if not tets or not iface_triangles or not root_triangles:
        raise RuntimeError(f"CalculiX MSH sets missing: tets={len(tets)} fsi={len(iface_triangles)} root={len(root_triangles)} tags={names}")
    iface_nodes = sorted({n for conn in iface_triangles for n in conn})
    root_nodes = sorted({n for conn in root_triangles for n in conn})
    tip_x = max(p[0] for p in nodes.values())
    all_tip_nodes = [n for n, p in nodes.items() if abs(p[0] - tip_x) < 1e-7]
    tip_le = (-270.0 + 260.0 * math.tan(math.radians(25.0))) / 1000.0
    tip_chord = 0.305
    tip_tc = min(thickness_mm / 1000.0, 0.10 * tip_chord) / tip_chord
    chord_mid = 0.5
    y_mid = tip_chord * 5.0 * tip_tc * (
        0.2969 * math.sqrt(chord_mid) - 0.1260 * chord_mid - 0.3516 * chord_mid**2
        + 0.2843 * chord_mid**3 - 0.1015 * chord_mid**4
    )
    z_mid = tip_le + chord_mid * tip_chord
    tip_nodes = [min(all_tip_nodes, key=lambda n: (nodes[n][1] - y_mid)**2 +
                      (nodes[n][2] - z_mid)**2)] if all_tip_nodes else []
    if not tip_nodes:
        raise RuntimeError("no tip nodes found in structural mesh")

    lines = ["*HEADING", f"Phase-15 FSI solid candidate, max thickness {thickness_mm:g} mm",
             "*NODE"]
    lines.extend(f"{n}, {p[0]:.12g}, {p[1]:.12g}, {p[2]:.12g}" for n, p in sorted(nodes.items()))
    lines.append("*ELEMENT, TYPE=C3D4, ELSET=EALL")
    lines.extend(f"{i}, " + ", ".join(str(n) for n in conn[:4]) for i, conn in enumerate(tets, start=1))
    # The CalculiX-preCICE adapter prefixes configured patch names with "N"
    # (nodes-mesh), so emit both the raw and N-prefixed aliases.
    set_definitions = (
        ("IFACE", iface_nodes), ("NIFACE", iface_nodes), ("NIFACEN", iface_nodes),
        ("ROOT", root_nodes), ("NROOT", root_nodes), ("NROOTN", root_nodes),
        ("TIP", tip_nodes), ("NTIP", tip_nodes),
    )
    for name, ids in set_definitions:
        lines.append(f"*NSET, NSET={name}")
        if name in ("TIP", "NTIP"):
            lines.append(", ".join(str(n) for n in ids))
        else:
            lines.extend(", ".join(str(n) for n in ids[j:j + 16]) for j in range(0, len(ids), 16))
    lines += [
        "*MATERIAL, NAME=CF_LAMINATE_EQUIVALENT",
        "*ELASTIC",
        f"{E_EQ:.9g}, {NU_SOLID:.8g}",
        "*DENSITY",
        f"{RHO_SOLID:.8g}",
        "*SOLID SECTION, ELSET=EALL, MATERIAL=CF_LAMINATE_EQUIVALENT",
        ",",
        "*STEP, INC=1000000",
        "*DYNAMIC, ALPHA=0.0, DIRECT",
        f"{COUPLING_DT:.9g}, {COUPLING_DT * COUPLING_WINDOWS:.9g}",
        "*BOUNDARY",
        "ROOT, 1, 3, 0.0",
        "*CLOAD",
        "IFACE, 1, 0.0",
        "IFACE, 2, 0.0",
        "IFACE, 3, 0.0",
        "*NODE PRINT, NSET=TIP",
        "U",
        "*NODE FILE",
        "U",
        "*EL FILE",
        "S, E",
        "*END STEP",
        "",
    ]
    inp_path.write_text("\n".join(lines), encoding="utf-8")
    return {"calculixInput": inp_path.name, "nodes": len(nodes), "tetrahedra": len(tets),
            "fsiNodes": len(iface_nodes), "rootNodes": len(root_nodes), "tipNodes": len(tip_nodes),
            "youngsModulusPa": E_EQ, "poissonRatio": NU_SOLID, "densityKgM3": RHO_SOLID}


def foam_file(cls: str, location: str, object_name: str, body: str) -> str:
    return ("FoamFile\n{\n version 2.0;\n format ascii;\n"
            f" class {cls};\n location \"{location}\";\n object {object_name};\n}}\n\n{body}\n")


def foam_case(case: Path, fluid_mesh_name: str, variant_id: str) -> None:
    system = case / "system"
    constant = case / "constant"
    zero = case / "0"
    for d in (system, constant, zero):
        d.mkdir(parents=True, exist_ok=True)
    (system / "controlDict").write_text(foam_file("dictionary", "system", "controlDict", f"""
application rhoPimpleFoam;
startFrom startTime;
startTime 0;
stopAt endTime;
endTime {COUPLING_DT * COUPLING_WINDOWS:.9g};
deltaT {COUPLING_DT:.9g};
adjustTimeStep no;
writeControl adjustableRunTime;
writeInterval 0.0005;
purgeWrite 0;
writeFormat ascii;
writePrecision 8;
writeCompression off;
timeFormat general;
timePrecision 8;
runTimeModifiable true;
libs ("libpreciceAdapterFunctionObject.so");
functions
{{
  preCICE_Adapter {{ type preciceAdapterFunctionObject; errors strict; }}
  wingForces
  {{
    type forces; libs ("libforces.so"); patches (fsi);
    p p; U U; rho rho; rhoInf {RHO_AIR};
    CofR (0 0 0); writeControl timeStep; writeInterval 1;
  }}
}}
"""), encoding="utf-8")
    (system / "preciceDict").write_text(foam_file("dictionary", "system", "preciceDict", """
preciceConfig "../precice-config.xml";
participant Fluid;
modules (FSI);
interfaces
{
  Interface1
  {
    mesh Fluid-Mesh;
    patches (fsi);
    locations faceCenters;
    readData (Displacement);
    writeData (Force);
  }
};
"""), encoding="utf-8")
    (system / "fvSchemes").write_text(foam_file("dictionary", "system", "fvSchemes", """
ddtSchemes { default Euler; }
gradSchemes { default cellLimited Gauss linear 1; }
divSchemes
{
 default none;
 div(phi,U) bounded Gauss linearUpwind grad(U);
 div(phi,h) bounded Gauss upwind;
 div(phi,k) bounded Gauss upwind;
 div(phi,omega) bounded Gauss upwind;
 div((muEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
"""), encoding="utf-8")
    (system / "fvSolution").write_text(foam_file("dictionary", "system", "fvSolution", """
solvers
{
 p { solver GAMG; tolerance 1e-7; relTol 0.05; smoother GaussSeidel; }
 pFinal { $p; relTol 0; }
 "(U|h|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-7; relTol 0.1; }
}
PIMPLE { nOuterCorrectors 1; nCorrectors 2; nNonOrthogonalCorrectors 0; }
relaxationFactors { fields { p 0.3; } equations { U 0.5; h 0.5; k 0.5; omega 0.5; } }
"""), encoding="utf-8")
    (constant / "dynamicMeshDict").write_text(foam_file("dictionary", "constant", "dynamicMeshDict", """
dynamicFvMesh dynamicMotionSolverFvMesh;
motionSolverLibs ("libfvMotionSolvers.so");
motionSolver displacementLaplacian;
displacementLaplacianCoeffs { diffusivity quadratic inverseDistance (fsi); }
"""), encoding="utf-8")
    (constant / "thermophysicalProperties").write_text(foam_file("dictionary", "constant", "thermophysicalProperties", """
thermoType
{
 type hePsiThermo; mixture pureMixture; transport sutherland; thermo hConst;
 equationOfState perfectGas; specie specie; energy sensibleEnthalpy;
}
mixture
{
 specie { nMoles 1; molWeight 28.965; }
 thermodynamics { Cp 1004.685; Hf 0; }
 transport { As 1.458e-6; Ts 110.4; }
}
"""), encoding="utf-8")
    (constant / "turbulenceProperties").write_text(foam_file("dictionary", "constant", "turbulenceProperties", """
simulationType RAS;
RAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }
"""), encoding="utf-8")

    bc = {
        "inlet": {
            "U": f"type fixedValue; value uniform (0 0 {U_FLIGHT});",
            "p": "type zeroGradient;", "T": f"type fixedValue; value uniform {T_STATIC};",
            "h": f"type fixedValue; value uniform {CP_AIR*T_STATIC};",
            "k": f"type fixedValue; value uniform {K_INLET};", "omega": f"type fixedValue; value uniform {OMEGA_INLET};",
            "nut": "type calculated; value uniform 0;", "alphat": "type calculated; value uniform 0;",
            "rho": f"type calculated; value uniform {RHO_AIR};",
        },
        "outlet": {
            "U": f"type pressureInletOutletVelocity; value uniform (0 0 {U_FLIGHT});",
            "p": f"type fixedValue; value uniform {P_STATIC};", "T": "type zeroGradient;",
            "h": "type zeroGradient;", "k": f"type inletOutlet; inletValue uniform {K_INLET}; value uniform {K_INLET};",
            "omega": f"type inletOutlet; inletValue uniform {OMEGA_INLET}; value uniform {OMEGA_INLET};",
            "nut": "type calculated; value uniform 0;", "alphat": "type calculated; value uniform 0;",
            "rho": f"type calculated; value uniform {RHO_AIR};",
        },
        "farfield": {
            "U": f"type freestream; freestreamValue uniform (0 0 {U_FLIGHT}); value uniform (0 0 {U_FLIGHT});",
            "p": "type freestreamPressure; freestreamValue uniform 70100; value uniform 70100;",
            "T": f"type fixedValue; value uniform {T_STATIC};",
            "h": f"type fixedValue; value uniform {CP_AIR*T_STATIC};",
            "k": f"type fixedValue; value uniform {K_INLET};", "omega": f"type fixedValue; value uniform {OMEGA_INLET};",
            "nut": "type calculated; value uniform 0;", "alphat": "type calculated; value uniform 0;",
            "rho": f"type calculated; value uniform {RHO_AIR};",
        },
        "fsi": {
            "U": "type movingWallVelocity; value uniform (0 0 0);",
            "p": "type zeroGradient;", "T": "type zeroGradient;", "h": "type zeroGradient;",
            "k": f"type kqRWallFunction; value uniform {K_INLET};",
            "omega": f"type omegaWallFunction; value uniform {OMEGA_INLET};",
            "nut": "type nutkWallFunction; value uniform 0;",
            "alphat": "type compressible::alphatWallFunction; value uniform 0;",
            "rho": f"type calculated; value uniform {RHO_AIR};",
        },
        "rootWall": {
            "U": "type noSlip;", "p": "type zeroGradient;", "T": "type zeroGradient;", "h": "type zeroGradient;",
            "k": f"type kqRWallFunction; value uniform {K_INLET};",
            "omega": f"type omegaWallFunction; value uniform {OMEGA_INLET};",
            "nut": "type nutkWallFunction; value uniform 0;",
            "alphat": "type compressible::alphatWallFunction; value uniform 0;",
            "rho": f"type calculated; value uniform {RHO_AIR};",
        },
    }
    dims = {
        "U": ("volVectorField", "[0 1 -1 0 0 0 0]", f"uniform (0 0 {U_FLIGHT})"),
        "p": ("volScalarField", "[1 -1 -2 0 0 0 0]", f"uniform {P_STATIC}"),
        "T": ("volScalarField", "[0 0 0 1 0 0 0]", f"uniform {T_STATIC}"),
        "h": ("volScalarField", "[0 2 -2 0 0 0 0]", f"uniform {CP_AIR*T_STATIC}"),
        "k": ("volScalarField", "[0 2 -2 0 0 0 0]", f"uniform {K_INLET}"),
        "omega": ("volScalarField", "[0 0 -1 0 0 0 0]", f"uniform {OMEGA_INLET}"),
        "nut": ("volScalarField", "[0 2 -1 0 0 0 0]", "uniform 0"),
        "alphat": ("volScalarField", "[1 -1 -1 0 0 0 0]", "uniform 0"),
        "rho": ("volScalarField", "[1 -3 0 0 0 0 0]", f"uniform {RHO_AIR}"),
    }
    for name, (cls, dimension, initial) in dims.items():
        bfields = "\n".join(f"  {patch} {{ {vals[name]} }}" for patch, vals in bc.items())
        (zero / name).write_text(foam_file(cls, "0", name,
            f"dimensions {dimension};\ninternalField {initial};\nboundaryField\n{{\n{bfields}\n}}"), encoding="utf-8")
    point_bcs = "\n".join(f"  {patch} {{ type fixedValue; value uniform (0 0 0); }}" for patch in bc)
    (zero / "pointDisplacement").write_text(foam_file("pointVectorField", "0", "pointDisplacement",
        f"dimensions [0 1 0 0 0 0 0];\ninternalField uniform (0 0 0);\nboundaryField\n{{\n{point_bcs}\n}}"), encoding="utf-8")
    (case / "candidate.json").write_text(json.dumps({"candidate": variant_id,
        "sourceGeometry": "Phase-15 nominal wing section schedule; outboard sector x=80.33..260 mm",
        "thicknessVariantMm": variant_id.replace("t", ""), "flowSpeedMps": U_FLIGHT,
        "altitudeM": 3000, "angleOfAttackDeg": AOA_DEG,
        "machEstimate": U_FLIGHT / math.sqrt(GAMMA*R_AIR*T_STATIC),
        "dynamicPressurePa": 0.5*RHO_AIR*U_FLIGHT**2, "solver": "rhoPimpleFoam", "coupling": "preCICE FSI"}, indent=2) + "\n", encoding="utf-8")


def build_candidate(thickness_mm: float) -> dict[str, Any]:
    case_id = f"wing_t{int(thickness_mm):02d}mm"
    root = CASES / case_id
    fluid = root / "fluid"
    solid = root / "solid"
    fluid.mkdir(parents=True, exist_ok=True)
    solid.mkdir(parents=True, exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.model.add(f"fluid_{case_id}")
        wing_tag, dim = wing_volume(thickness_mm)
        fluid_result = fluid_mesh(fluid / "wing.msh", wing_tag, dim)
        gmsh.clear()
        gmsh.model.add(f"solid_{case_id}")
        solid_result = solid_mesh(solid / "wing.msh", thickness_mm)
    finally:
        gmsh.finalize()
    solid_result.update(write_calculix(solid / "wing.msh", solid / "wing.inp", thickness_mm))
    foam_case(fluid, "wing.msh", case_id)
    precice_config = f'''<?xml version="1.0" encoding="UTF-8"?>
<precice-configuration xmlns:data="https://precice.org/data"
  xmlns:mapping="https://precice.org/mapping"
  xmlns:m2n="https://precice.org/m2n"
  xmlns:coupling-scheme="https://precice.org/coupling-scheme"
  xmlns:acceleration="https://precice.org/acceleration">
  <log><sink filter="%Severity% > info and %Rank% = 0" format="---[precice] %Severity% %Message%" enabled="true" /></log>
  <data:vector name="Force" />
  <data:vector name="Displacement" />
  <mesh name="Fluid-Mesh" dimensions="3">
    <use-data name="Force" /><use-data name="Displacement" />
  </mesh>
  <mesh name="Solid-Mesh" dimensions="3">
    <use-data name="Force" /><use-data name="Displacement" />
  </mesh>
  <participant name="Fluid">
    <provide-mesh name="Fluid-Mesh" />
    <receive-mesh name="Solid-Mesh" from="Solid" />
    <write-data name="Force" mesh="Fluid-Mesh" />
    <read-data name="Displacement" mesh="Fluid-Mesh" />
    <mapping:nearest-neighbor direction="write" from="Fluid-Mesh" to="Solid-Mesh" constraint="conservative" />
    <mapping:nearest-neighbor direction="read" from="Solid-Mesh" to="Fluid-Mesh" constraint="consistent" />
  </participant>
  <participant name="Solid">
    <provide-mesh name="Solid-Mesh" />
    <receive-mesh name="Fluid-Mesh" from="Fluid" />
    <write-data name="Displacement" mesh="Solid-Mesh" />
    <read-data name="Force" mesh="Solid-Mesh" />
    <watch-point mesh="Solid-Mesh" name="WingTip" coordinate="0.26;0.015;0.0" />
  </participant>
  <m2n:sockets acceptor="Fluid" connector="Solid" exchange-directory="." />
  <coupling-scheme:parallel-implicit>
    <time-window-size value="{COUPLING_DT:.9g}" />
    <max-time value="{COUPLING_DT * COUPLING_WINDOWS:.9g}" />
    <participants first="Fluid" second="Solid" />
    <exchange data="Force" mesh="Solid-Mesh" from="Fluid" to="Solid" />
    <exchange data="Displacement" mesh="Solid-Mesh" from="Solid" to="Fluid" />
    <max-iterations value="6" />
    <min-iterations value="2" />
    <relative-convergence-measure limit="5e-3" data="Displacement" mesh="Solid-Mesh" />
    <acceleration:IQN-ILS>
      <data name="Displacement" mesh="Solid-Mesh" />
      <filter type="QR2" limit="1e-2" />
      <initial-relaxation value="0.5" />
      <max-used-iterations value="30" />
      <time-windows-reused value="5" />
    </acceleration:IQN-ILS>
  </coupling-scheme:parallel-implicit>
</precice-configuration>
'''
    (root / "precice-config.xml").write_text(precice_config, encoding="utf-8")
    (solid / "config.yml").write_text(
        "participants:\n"
        "    Solid:\n"
        "        interfaces:\n"
        "        - nodes-mesh: Solid-Mesh\n"
        "          patch: IFACE\n"
        "          read-data: [Force]\n"
        "          write-data: [Displacement]\n"
        "precice-config-file: ../precice-config.xml\n",
        encoding="utf-8",
    )
    return {"candidate": case_id, "maxThicknessMm": thickness_mm,
            "fluid": fluid_result, "solid": solid_result,
            "effectiveMaterial": {"E_Pa": E_EQ, "nu": NU_SOLID, "rhoKgM3": RHO_SOLID,
                                  "basis": "Equivalent isotropic stiffness seed for 1.2 mm CF wrap over light core; sweep uncertainty before design release"}}


def main() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    workbench_path = REPORTS / "phase15_aero_multiphysics_candidates.json"
    if not workbench_path.is_file():
        raise FileNotFoundError("run phase15_aero_multiphysics_screen.py before generating FSI cases")
    workbench_screen = json.loads(workbench_path.read_text(encoding="utf-8"))
    wb_by_id = {item["id"]: item for item in workbench_screen.get("candidates", [])}
    thicknesses = (30.0, 36.0)
    for thickness in thicknesses:
        key = f"wing_t{int(thickness):02d}mm"
        if key not in wb_by_id:
            raise ValueError(f"Aero Multiphysics screen is missing FSI candidate {key}")
    results = [build_candidate(t) for t in thicknesses]
    (REPORTS / "phase15_fsi_casegen.json").write_text(json.dumps({
        "study": "Phase-15 wing-sector OpenFOAM-preCICE-CalculiX FSI candidate sweep",
        "evidenceClass": "meshed and prepared; no solver has run yet",
        "candidateSource": "Aero Multiphysics Workbench coupled airframe/EDF candidate screen",
        "workbenchCandidateScreenSha256": hashlib.sha256(workbench_path.read_bytes()).hexdigest(),
        "workbenchFidelity": sorted({item.get("workbenchFidelity", "unknown")
                                      for item in workbench_screen.get("candidates", [])}),
        "workbenchNativeSolverEvidence": False,
        "candidates": results,
        "limitations": [
            "Isolated outboard wing sector only; does not include fuselage, EDF jets, actuator loads, motor dynamics or full-aircraft aeroelastic modes.",
            "200 m/s at 3 km is the 720 km/h design point; local fluid Mach is about 0.61 and the density/thermo inputs remain ISA assumptions.",
            "Equivalent isotropic composite stiffness is a sensitivity assumption; the actual laminate schedule, orthotropic constants and joint stiffness are not sourced.",
            "The two motor-can envelopes and seventh-servo/PWM incompatibility in the airframe audit are outside this wing-sector FSI model.",
        ],
    }, indent=2) + "\n", encoding="utf-8")
    with (REPORTS / "phase15_fsi_candidates.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["candidate", "maxThicknessMm", "fluidCells", "solidElements", "fsiNodes", "rootNodes", "E_Pa", "rhoKgM3"])
        for item in results:
            writer.writerow([item["candidate"], item["maxThicknessMm"], item["fluid"]["fluidCells"],
                             item["solid"]["solidElements"], item["solid"]["fsiNodes"],
                             item["solid"]["rootNodes"], E_EQ, RHO_SOLID])
    print(json.dumps({"candidateCount": len(results), "caseRoot": str(CASES),
                      "fluidCells": [r["fluid"]["fluidCells"] for r in results],
                      "solidElements": [r["solid"]["solidElements"] for r in results]}, indent=2))


if __name__ == "__main__":
    main()
