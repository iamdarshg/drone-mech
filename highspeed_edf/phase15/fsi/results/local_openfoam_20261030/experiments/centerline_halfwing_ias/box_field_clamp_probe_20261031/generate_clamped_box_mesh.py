#!/usr/bin/env python3
"""Reproduce the nominal 3.5 mm Box-sizing probe whose request was clamped."""
from __future__ import annotations
import hashlib
import importlib.util
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / "highspeed_edf/phase15/optimization/phase15_fsi_casegen.py").is_file())
SOURCE = REPO / "highspeed_edf/phase15/optimization/phase15_fsi_casegen.py"
sys.path.insert(0, str(SOURCE.parent))
import gmsh

spec = importlib.util.spec_from_file_location("phase15_fsi_casegen", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load source generator: {SOURCE}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def centerline_wing(thickness_mm: float):
    x0, x1 = 0.0, 260e-3
    chord0, chord1 = 425e-3, 305e-3
    le0 = -270e-3
    le1 = (-270.0 + 260.0 * math.tan(math.radians(25.0))) / 1000.0
    t0 = min(thickness_mm / 1000.0, 0.10 * chord0)
    t1 = min(thickness_mm / 1000.0, 0.10 * chord1)
    w0 = mod.naca_section(x0, le0, chord0, t0)
    w1 = mod.naca_section(x1, le1, chord1, t1)
    created = gmsh.model.occ.addThruSections([w0, w1], makeSolid=True, makeRuled=False)
    gmsh.model.occ.synchronize()
    vols = [tag for dim, tag in created if dim == 3]
    if len(vols) != 1:
        raise RuntimeError(f"Expected one wing volume, got {created}")
    dims = {"xRootM": x0, "xTipM": x1, "rootChordM": chord0, "tipChordM": chord1,
            "rootLeadingEdgeZM": le0, "tipLeadingEdgeZM": le1,
            "rootThicknessM": t0, "tipThicknessM": t1}
    return vols[0], dims


mod.wing_volume = centerline_wing
source_set_mesh_fields = mod.set_mesh_fields

def nominal_box_fields(surface_tags: list[int], min_size: float, max_size: float) -> None:
    source_set_mesh_fields(surface_tags, min_size, max_size)
    gmsh.option.setNumber("Mesh.OptimizeNetgen", 0)
    box = gmsh.model.mesh.field.add("Box")
    for key, value in (("VIn", 0.0035), ("VOut", max_size),
                       ("XMin", 0.060), ("XMax", 0.280),
                       ("YMin", -0.060), ("YMax", 0.060),
                       ("ZMin", -0.260), ("ZMax", -0.105)):
        gmsh.model.mesh.field.setNumber(box, key, value)
    minimum = gmsh.model.mesh.field.add("Min")
    # The source set_mesh_fields() creates Distance then Threshold, so field 2 is
    # the base threshold field. This exact probe failed to lower Mesh.MeshSizeMin.
    gmsh.model.mesh.field.setNumbers(minimum, "FieldsList", [2, box])
    gmsh.model.mesh.field.setAsBackgroundMesh(minimum)

mod.set_mesh_fields = nominal_box_fields
mesh_path = HERE / "wing_nominal_box_clamped.msh"
gmsh.initialize()
try:
    gmsh.option.setNumber("General.Terminal", 1)
    gmsh.option.setNumber("General.NumThreads", 1)
    gmsh.model.add("centerline_halfwing_30mm_le_box_nominal")
    wing, dims = mod.wing_volume(30.0)
    summary = mod.fluid_mesh(mesh_path, wing, dims)
    actual_min = gmsh.option.getNumber("Mesh.MeshSizeMin")
finally:
    gmsh.finalize()
print({"mesh": str(mesh_path.relative_to(REPO)), "summary": summary,
       "requestedBoxVInM": 0.0035, "MeshMeshSizeMinM": actual_min,
       "meshSHA256": hashlib.sha256(mesh_path.read_bytes()).hexdigest()})
