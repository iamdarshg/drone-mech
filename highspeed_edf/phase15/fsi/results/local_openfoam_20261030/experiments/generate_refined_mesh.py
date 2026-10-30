"""Rebuild the isolated 2x Phase-15 wing-sector mesh experiment."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = next(
    parent for parent in HERE.parents
    if (parent / "highspeed_edf/phase15/optimization/phase15_fsi_casegen.py").is_file()
)
SOURCE = REPO / "highspeed_edf/phase15/optimization/phase15_fsi_casegen.py"
BASE_MESH = REPO / "highspeed_edf/phase15/fsi/cases/wing_t30mm/fluid/wing.msh"
OUT = HERE / "mesh_refine2x"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


try:
    import gmsh
except ImportError as exc:
    raise SystemExit(
        "Python Gmsh is required. Install the recorded runtime with "
        "`python3 -m pip install --target /tmp/phase15-gmsh gmsh==4.15.2`, "
        "then run with `PYTHONPATH=/tmp/phase15-gmsh`."
    ) from exc

spec = importlib.util.spec_from_file_location("phase15_fsi_casegen", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load Phase-15 generator: {SOURCE}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
FLUID_CASE = OUT / "cases/wing_t30mm/fluid"
FLUID_CASE.mkdir(parents=True, exist_ok=True)

# Preserve the source generator's Gmsh algorithms, curvature sampling,
# optimization, and distance thresholds. Halve only its 12/120 mm target sizes.
source_set_mesh_fields = mod.set_mesh_fields

def refined_mesh_fields(surface_tags: list[int], min_size: float, max_size: float) -> None:
    source_set_mesh_fields(surface_tags, min_size / 2, max_size / 2)
    # Gmsh 4.13.1 in the pinned Python wheel was built without Netgen optimizer.
    mod.gmsh.option.setNumber("Mesh.OptimizeNetgen", 0)

mod.set_mesh_fields = refined_mesh_fields
mod.gmsh.initialize()
try:
    mod.gmsh.option.setNumber("General.Terminal", 0)
    mod.gmsh.option.setNumber("General.NumThreads", 1)
    mod.gmsh.model.add("fluid_wing_t30mm")
    wing_tag, dimensions = mod.wing_volume(30.0)
    fluid_result = mod.fluid_mesh(FLUID_CASE / "wing.msh", wing_tag, dimensions)
finally:
    mod.gmsh.finalize()
result = {"candidate": "wing_t30mm", "maxThicknessMm": 30.0, "fluid": fluid_result}
mesh = FLUID_CASE / "wing.msh"
(OUT / "generator_result.json").write_text(json.dumps(result, indent=2) + "\n")

# Record both the Python binding and the actual linked Gmsh runtime. The wheel
# used here provides gmsh.py 4.15.2 backed by libgmsh 4.13.1.
gmsh.initialize()
try:
    gmsh_runtime = gmsh.option.getString("General.Version")
finally:
    gmsh.finalize()
provenance = {
    "python": platform.python_version(),
    "gmshPythonBinding": gmsh.__version__,
    "gmshSharedLibrarySoname": gmsh.lib._name,
    "gmshRuntime": gmsh_runtime,
    "netgenOptimizer": "disabled; unavailable in the recorded Gmsh runtime",
    "phase15Generator": str(SOURCE.relative_to(REPO)),
    "phase15GeneratorSha256": sha256(SOURCE),
    "regenerationScript": str(Path(__file__).resolve().relative_to(REPO)),
    "regenerationScriptSha256": sha256(Path(__file__).resolve()),
    "trackedBaseMesh": str(BASE_MESH.relative_to(REPO)),
    "trackedBaseMeshSha256": sha256(BASE_MESH),
    "refinedFluidMesh": str(mesh.relative_to(REPO)),
    "refinedFluidMeshSha256": sha256(mesh),
    "fluidCells": result["fluid"]["fluidCells"],
    "fluidVolumeM3": result["fluid"]["fluidVolumeM3"],
    "wingVolumeM3": result["fluid"]["wingVolumeM3"],
    "domainM": result["fluid"]["domainM"],
    "refinement": "same Phase-15 30 mm wing and farfield; MeshSizeMin/Max halved from 0.012/0.12 m to 0.006/0.06 m",
}
(OUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
print(json.dumps(provenance, indent=2))
