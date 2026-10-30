"""Native STEP and KiCad source adapters for issue #14.

STEP geometry is read by pinned CadQuery/OCP. KiCad board outlines are read
with pcbnew from the installed KiCad Python, so Edge.Cuts is the authority.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import re
import subprocess
import sys
import os
import ast
import csv
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def import_step(path: Path) -> dict:
    """Round-trip one STEP file into OCP, returning per-solid native data."""
    import cadquery as cq
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    shape = cq.importers.importStep(str(path)).val()
    solids = shape.Solids()
    records = []
    for index, solid in enumerate(solids):
        bb = solid.BoundingBox()
        records.append({
            "solid_index": index,
            "valid_brep": bool(BRepCheck_Analyzer(solid.wrapped).IsValid()),
            "volume_mm3": float(solid.Volume()),
            "bbox_mm": [float(bb.xmin), float(bb.ymin), float(bb.zmin),
                        float(bb.xmax), float(bb.ymax), float(bb.zmax)],
        })
    return {"path": str(path), "sha256": sha256(path), "solid_count": len(records),
            "solids": records,
            "valid": bool(records) and all(x["valid_brep"] and x["volume_mm3"] > 0 for x in records)}


def import_all_step(step_dir: Path) -> dict:
    files = sorted([p for p in step_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".step", ".stp")])
    results, errors = [], []
    for path in files:
        try:
            results.append(import_step(path))
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    try:
        tool_versions = {name: importlib.metadata.version(name) for name in ("cadquery", "cadquery-ocp")}
    except importlib.metadata.PackageNotFoundError as exc:
        tool_versions = {"error": str(exc)}
    status = "PASS" if len(files) == 81 and not errors and all(x["valid"] for x in results) else "FAIL"
    if errors and any("ModuleNotFoundError" in x["error"] or "ImportError" in x["error"] for x in errors):
        status = "BLOCKED"
    return {"adapter": "CadQuery/OCP STEP import", "tool_versions": tool_versions,
            "python_executable": sys.executable,
            "expected_file_count": 81, "file_count": len(files), "imported_count": len(results),
            "valid_count": sum(bool(x["valid"]) for x in results), "errors": errors,
            "files": results, "status": status}


_PCBNEW_READER = r'''import json, pcbnew, sys
b=pcbnew.LoadBoard(sys.argv[1]); mm=pcbnew.ToMM
edges=[]; holes=[]
for d in b.GetDrawings():
 if d.GetLayer()==pcbnew.Edge_Cuts:
  s=d.GetShape()
  if s==pcbnew.SHAPE_T_SEGMENT:
   edges.append({"kind":"segment","start":[mm(d.GetStart().x),mm(d.GetStart().y)],"end":[mm(d.GetEnd().x),mm(d.GetEnd().y)]})
  elif s==pcbnew.SHAPE_T_ARC:
   edges.append({"kind":"arc","start":[mm(d.GetStart().x),mm(d.GetStart().y)],"end":[mm(d.GetEnd().x),mm(d.GetEnd().y)],"center":[mm(d.GetCenter().x),mm(d.GetCenter().y)],"radius_mm":mm(d.GetRadius())})
  elif s==pcbnew.SHAPE_T_CIRCLE:
   edges.append({"kind":"circle","center":[mm(d.GetCenter().x),mm(d.GetCenter().y)],"radius_mm":mm(d.GetRadius())})
for f in b.GetFootprints():
 for p in f.Pads():
  if p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH and p.GetDrillSize().x>0:
   holes.append({"ref":f"{f.GetReference()}:{p.GetNumber()}","center":[mm(p.GetPosition().x),mm(p.GetPosition().y)],"drill_mm":[mm(p.GetDrillSize().x),mm(p.GetDrillSize().y)]})
if not edges: raise RuntimeError("no Edge.Cuts graphics")
xs=[]; ys=[]
for e in edges:
 for p in (e.get("start"),e.get("end"),e.get("center")):
  if p: xs.append(p[0]); ys.append(p[1])
print(json.dumps({"board":sys.argv[1],"version":pcbnew.GetBuildVersion(),"edge_cuts":edges,"holes":holes,"edge_graphic_count":len(edges),"edge_bbox_mm":[min(xs),min(ys),max(xs),max(ys)],"width_mm":max(xs)-min(xs),"height_mm":max(ys)-min(ys)}))
'''


def import_kicad_board(path: Path, python: str = "/usr/bin/python3") -> dict:
    proc = subprocess.run([python, "-c", _PCBNEW_READER, str(path)], text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise RuntimeError(f"pcbnew extraction failed (exit {proc.returncode}): {proc.stderr.strip()}")
    result = json.loads(proc.stdout)
    result["sha256"] = sha256(path)
    result["command"] = [python, "-c", "<pcbnew Edge.Cuts extraction>", str(path)]
    result["status"] = "PASS" if result["edge_graphic_count"] > 0 else "FAIL"
    return result


def board_placeholder_comparison(board_data: dict, placeholder: tuple[float, float]) -> dict:
    actual = (board_data["width_mm"], board_data["height_mm"])
    delta = [actual[i] - placeholder[i] for i in range(2)]
    return {"actual_edge_cuts_mm": list(actual), "cad_placeholder_mm": list(placeholder),
            "difference_mm": delta, "status": "PASS" if all(abs(x) < 0.05 for x in delta) else "FAIL"}


def validate_pcb_sha(actual: str, pinned: str) -> dict:
    return {"actual_sha256": actual, "pinned_sha256": pinned,
            "status": "PASS" if actual == pinned else "FAIL",
            "errors": [] if actual == pinned else ["native PCB source SHA differs from pinned reference"]}


def validate_cad_datum(parameter_register: Path) -> dict:
    try:
        obj = json.loads(parameter_register.read_text())
        datum = obj["datum"]
        good = (datum.get("units") == "mm" and datum.get("x") == "lateral"
                and datum.get("y") == "vertical" and datum.get("z") == "aft"
                and float(datum.get("fanPlaneZmm")) == 0.0)
        return {"status": "PASS" if good else "FAIL", "measured": datum,
                "errors": [] if good else ["CAD datum must be lateral/vertical/aft in mm with fan plane z=0"]}
    except Exception as exc:
        return {"status": "FAIL", "measured": None, "errors": [f"invalid CAD datum register: {type(exc).__name__}: {exc}"]}


def aabb_intersection_volume(a: list[float], b: list[float]) -> float:
    spans = [min(a[i+3], b[i+3]) - max(a[i], b[i]) for i in range(3)]
    return math.prod(max(0.0, span) for span in spans)


def motor_bbox_collision(motors: list[dict], min_required_clearance_mm: float = 0) -> dict:
    """Measure imported motor solids with OCC Boolean and exact surface distance."""
    import cadquery as cq
    pairs = []
    for i, left in enumerate(motors):
        for right in motors[i+1:]:
            sa = cq.importers.importStep(left["path"]).val().Solids()[0]
            sb = cq.importers.importStep(right["path"]).val().Solids()[0]
            exact = float(sa.intersect(sb).Volume())
            distance = sa.distance(sb)
            clearance = 0.0 if exact > 1e-6 else float(distance)
            la = left["solids"][0]["bbox_mm"]
            rb = right["solids"][0]["bbox_mm"]
            axial_envelope_overlap = max(0.0, min(la[5], rb[5]) - max(la[2], rb[2]))
            axial_pitch = abs((la[2] + la[5] - rb[2] - rb[5]) / 2.0)
            # The STEP envelope is a 72 mm cylindrical can fused to an 8 mm
            # rear shaft; separate can overlap from the total bounding envelope.
            can_z = lambda bb: (bb[2] + 8.0, bb[2] + 8.0 + 72.0)
            lcan, rcan = can_z(la), can_z(rb)
            motor_can_overlap = max(0.0, min(lcan[1], rcan[1]) - max(lcan[0], rcan[0]))
            pairs.append({"left": Path(left["path"]).name, "right": Path(right["path"]).name,
                          "exact_intersection_mm3": exact, "measured_clearance_mm": clearance,
                          "axial_envelope_overlap_mm": axial_envelope_overlap,
                          "motor_can_overlap_mm": motor_can_overlap,
                          "shaft_length_assumption_mm": 8.0, "motor_can_length_mm": 72.0,
                          "axial_center_pitch_mm": axial_pitch,
                          "required_clearance_mm": min_required_clearance_mm,
                          "collides": exact > 1e-6,
                          "clearance_fails": clearance < min_required_clearance_mm})
    collisions = [p for p in pairs if p["collides"]]
    clearance_failures = [p for p in pairs if p["clearance_fails"]]
    return {"pairs_checked": len(pairs), "collisions": collisions,
            "clearance_failures": clearance_failures, "pairs": pairs,
            "status": "FAIL" if collisions or clearance_failures else "PASS"}


def recalculate_mass_cg(geometry_dir: Path, source_csv: Path, density_source: Path) -> dict:
    """Recompute component volumes and centres from native STEP solids.

    Source CSV is consulted only for explicit material/density selection and
    documented mass overrides/point mass; STEP volume and centre are reimported.
    """
    tree = ast.parse(density_source.read_text())
    densities = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MATERIAL_DENSITY_KG_M3" for t in node.targets):
            densities = ast.literal_eval(node.value)
            break
    if not densities:
        return {"status": "BLOCKED", "errors": [f"material density map is unavailable in {density_source}"]}
    rows = list(csv.DictReader(source_csv.open(newline="")))
    if not any(row.get("component") == "payload_point_mass" for row in rows):
        return {"status": "FAIL", "errors": ["required 1 kg payload point mass is omitted from mass source"]}
    total = mx = my = mz = 0.0
    components, blocked_inputs = [], []
    for row in rows:
        name = row["component"]
        if name == "payload_point_mass":
            mass = float(row["massKg"])
            center = [float(row[k]) for k in ("cgXmm", "cgYmm", "cgZmm")]
            volume = 0.0
            basis = "source point mass; not geometrized"
        else:
            step = geometry_dir / "step" / f"{name}.step"
            if not step.is_file():
                return {"status": "BLOCKED", "errors": [f"native STEP for mass component is absent: {step}"]}
            try:
                import cadquery as cq
                shape = cq.importers.importStep(str(step)).val()
                volume = float(shape.Volume())
                c = cq.Shape.centerOfMass(shape)
                center = [float(c.x), float(c.y), float(c.z)]
            except Exception as exc:
                return {"status": "FAIL", "errors": [f"STEP import failed for mass component {name}: {type(exc).__name__}: {exc}"]}
            material = row["material"]
            if "mass override" in row["basis"]:
                mass = float(row["massKg"])
                basis = "sourced/analyst mass override; native STEP volume and CG used"
                blocked_inputs.append(name)
            else:
                if material not in densities:
                    return {"status": "BLOCKED", "errors": [f"no sourced density for material {material!r} ({name})"]}
                mass = volume * float(densities[material]) / 1e9
                basis = f"native STEP volume × source density {densities[material]} kg/m^3"
            if volume <= 0:
                return {"status": "FAIL", "errors": [f"native solid volume is non-positive: {name}: {volume} mm^3"]}
        components.append({"component": name, "material": row["material"], "volume_mm3": volume,
                           "mass_kg": mass, "center_mm": center, "basis": basis})
        total += mass
        mx += mass * center[0]
        my += mass * center[1]
        mz += mass * center[2]
    cg = [mx / total, my / total, mz / total] if total else [None, None, None]
    return {"status": "BLOCKED" if blocked_inputs else "PASS", "total_mass_kg": total, "cg_mm": cg,
            "component_count": len(components), "components_using_mass_override": blocked_inputs,
            "assumptions": ["payload point mass and analyst/sourced mass overrides are retained from source CSV"],
            "components": components,
            "errors": (["mass/CG arithmetic recomputed from native STEP volumes and centers, but mass overrides remain assumptions: " + ", ".join(blocked_inputs)] if blocked_inputs else [])}


def _load_step_shapes(paths: list[Path]):
    import cadquery as cq
    return {p.stem: cq.importers.importStep(str(p)).val() for p in paths}


def boolean_interference(left_path: Path, right_path: Path, tolerance_mm3: float = 1e-6) -> dict:
    """Exact OCC common-volume test over every imported solid pair."""
    left = _load_step_shapes([left_path])[left_path.stem].Solids()
    right = _load_step_shapes([right_path])[right_path.stem].Solids()
    pairs = []
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            volume = float(a.intersect(b).Volume())
            if volume > tolerance_mm3:
                pairs.append({"left_solid": i, "right_solid": j, "intersection_volume_mm3": volume})
    return {"left_path": str(left_path), "right_path": str(right_path),
            "left_solid_count": len(left), "right_solid_count": len(right),
            "intersections": pairs, "status": "FAIL" if pairs else "PASS"}


def battery_bay_fit(geometry_dir: Path, generator_path: Path) -> dict:
    """Test reimported battery envelopes against the source-defined reserved bay."""
    tree = ast.parse(generator_path.read_text())
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("BATTERY_BAY", "BATTERY_Z_CENTRE", "BATTERY_PACK"):
                    values[target.id] = ast.literal_eval(node.value)
    if set(values) != {"BATTERY_BAY", "BATTERY_Z_CENTRE", "BATTERY_PACK"}:
        return {"status": "BLOCKED", "errors": ["source geometry lacks typed BATTERY_BAY, BATTERY_PACK or BATTERY_Z_CENTRE"]}
    zlen, xlen, ylen = map(float, values["BATTERY_BAY"])
    pack_x, pack_y, pack_z = map(float, values["BATTERY_PACK"])
    zcenter = float(values["BATTERY_Z_CENTRE"])
    bay = {"xmin": -xlen/2, "xmax": xlen/2, "ymin": -ylen/2, "ymax": ylen/2,
           "zmin": zcenter-zlen/2, "zmax": zcenter+zlen/2}
    shell_path = geometry_dir / "step" / "fuselage_battery_bay_shell.step"
    if not shell_path.is_file():
        return {"status": "BLOCKED", "errors": [f"native battery bay shell STEP missing: {shell_path}"]}
    import cadquery as cq
    shell = cq.importers.importStep(str(shell_path)).val()
    shell_bb = shell.BoundingBox()
    shell_bounds = {"xmin": shell_bb.xmin, "xmax": shell_bb.xmax, "ymin": shell_bb.ymin,
                    "ymax": shell_bb.ymax, "zmin": shell_bb.zmin, "zmax": shell_bb.zmax}
    shell_spans_reserved_bay = all(shell_bounds[k] <= bay[k]+1e-5 if k.endswith("min") else shell_bounds[k] >= bay[k]-1e-5 for k in bay)
    names = ["Bonka_6S_1600_pack_1_185x65x55", "Bonka_6S_1600_pack_2_185x65x55"]
    measurements, fit = [], True
    for name in names:
        path = geometry_dir / "step" / f"{name}.step"
        if not path.is_file():
            return {"status": "BLOCKED", "errors": [f"native battery STEP missing: {path}"]}
        import cadquery as cq
        shape = cq.importers.importStep(str(path)).val()
        bb = shape.BoundingBox()
        bounds = {"xmin": bb.xmin, "xmax": bb.xmax, "ymin": bb.ymin, "ymax": bb.ymax,
                  "zmin": bb.zmin, "zmax": bb.zmax}
        inside = all(bounds[k] >= bay[k]-1e-5 if k.endswith("min") else bounds[k] <= bay[k]+1e-5 for k in bounds)
        fit &= inside
        measurements.append({"path": str(path), "bbox_mm": bounds, "within_reserved_bay": inside})
    expected_dims = {"pack_x_mm": pack_x, "pack_y_mm": pack_y, "pack_z_mm": pack_z}
    status = "PASS" if fit and shell_spans_reserved_bay else "FAIL"
    errors = []
    if not fit:
        errors.append("native battery envelope exceeds reserved bay")
    if not shell_spans_reserved_bay:
        errors.append("native fuselage battery-bay shell BBox does not span the reserved bay envelope")
    return {"status": status, "reserved_bay_mm": {"x": xlen, "y": ylen, "z": zlen},
            "reserved_bay_bounds_mm": bay, "source_declared_pack_mm": expected_dims,
            "native_shell_path": str(shell_path), "native_shell_bbox_mm": shell_bounds,
            "native_shell_spans_reserved_bay": shell_spans_reserved_bay,
            "packs": measurements, "errors": errors}


def connector_access_screen(geometry_dir: Path) -> dict:
    """Report native connector-envelope geometry and overlap with body shell.

    Mating connector, cable bend and hand-tool envelopes are absent, so this is
    a measured obstruction screen and remains BLOCKED for access qualification.
    """
    p = geometry_dir / "step"
    connectors = _load_step_shapes([p / "esc_battery_motor_temp_and_CAN_connectors.step"])["esc_battery_motor_temp_and_CAN_connectors"]
    body = _load_step_shapes([p / "fuselage_battery_bay_shell.step"])["fuselage_battery_bay_shell"]
    overlaps = []
    for i, connector in enumerate(connectors.Solids()):
        for j, shell in enumerate(body.Solids()):
            volume = float(connector.intersect(shell).Volume())
            if volume > 1e-6:
                overlaps.append({"connector_solid": i, "body_shell_solid": j, "intersection_volume_mm3": volume})
    return {"status": "BLOCKED", "connector_solid_count": len(connectors.Solids()),
            "body_shell_solid_count": len(body.Solids()), "body_intersections": overlaps,
            "missing_inputs": ["mating plug solids", "cable bend radius/route", "tool and finger access envelope"],
            "errors": ["connector access cannot be qualified without mating and service envelopes"]}


def inspect_materials(generator_path: Path, mass_csv: Path) -> dict:
    """Inspect declared material properties and identify absent physical evidence."""
    tree=ast.parse(generator_path.read_text()); densities=None
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="MATERIAL_DENSITY_KG_M3" for t in node.targets):
            densities=ast.literal_eval(node.value); break
    materials=sorted({r["material"] for r in csv.DictReader(mass_csv.open(newline="")) if r["material"]!="not-geometrized"})
    unknown=[m for m in materials if m not in (densities or {})]
    # Native catalog entries can verify nominal material labels and density values;
    # they do not establish layup, resin, bond or temperature qualification.
    physical_missing=["laminate/ply schedule and coupon properties", "resin/core/bond temperature data",
                     "motor/electronics envelope material qualification"]
    return {"status":"FAIL" if unknown else "BLOCKED", "declared_density_kg_m3":densities or {},
            "materials_used":materials,"unknown_materials":unknown,
            "physical_evidence_missing":physical_missing,
            "errors":(["source mass table references material with no density entry: "+", ".join(unknown)] if unknown else ["material labels and nominal densities parsed, but physical layup/coupon evidence is absent"])}


def inspect_manufacturing(geometry_dir: Path) -> dict:
    """Reimport stock-nest STEP solids and report unsupported process gates."""
    stock=geometry_dir/"stock_nests"
    files=sorted(p for p in stock.glob("*.step"))
    if len(files)!=3:
        return {"status":"BLOCKED","stock_file_count":len(files),"errors":[f"expected 3 native stock-nest STEP files; found {len(files)}"]}
    records=[]
    for path in files:
        try:
            rec=import_step(path)
            records.append({"path":str(path),"sha256":rec["sha256"],"solid_count":rec["solid_count"],
                            "valid":rec["valid"],"bbox_mm":rec["solids"][0]["bbox_mm"],
                            "volume_mm3":sum(x["volume_mm3"] for x in rec["solids"])})
        except Exception as exc:
            return {"status":"FAIL","errors":[f"native stock STEP import failed for {path}: {type(exc).__name__}: {exc}"]}
    valid=all(x["valid"] and x["solid_count"]>0 and x["volume_mm3"]>0 for x in records)
    return {"status":"BLOCKED" if valid else "FAIL","stock_files":records,
            "manufacturing_evidence_missing":["machine work envelope and tool reach", "fixture/access and join allowances",
                                               "indexed multi-axis finished rotor toolpath and containment proof"],
            "errors":["native stock solids imported; machine/process and finished-rotor evidence is not present"] if valid else ["invalid stock nest solid"]}


def main(argv=None) -> int:
    """CLI entry point with reproducible raw evidence receipts."""
    import argparse
    import importlib.metadata
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("step", "motors", "ducts", "battery", "connectors", "mass", "materials", "manufacture"))
    parser.add_argument("--geometry-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generator", type=Path)
    parser.add_argument("--mass-csv", type=Path)
    parser.add_argument("--datum", type=Path)
    args = parser.parse_args(argv)
    if args.mode == "step":
        data = import_all_step(args.geometry_dir)
        if args.datum:
            data["datum"] = validate_cad_datum(args.datum)
            if data["datum"]["status"] == "FAIL":
                data["status"] = "FAIL"
                data["errors"].extend(data["datum"]["errors"])
    elif args.mode == "motors":
        p = args.geometry_dir / "step"
        motors = [import_step(x) for x in sorted(p.glob("motor_*_3670_*_envelope.step"))]
        data = motor_bbox_collision(motors)
        data["motor_source_note"] = "native CAD envelopes are 42x72 mm; physical supplier data has not been independently sourced"
    elif args.mode == "ducts":
        p = args.geometry_dir / "step"
        pair_results = [boolean_interference(p / "fuselage_battery_bay_shell.step", p / f"duct_{d}_82OD_78ID_L110.step") for d in ("A", "B")]
        data = {"ducts": pair_results, "status": "FAIL" if any(x["status"] == "FAIL" for x in pair_results) else "PASS",
                "errors": ["duct/body intersection volume detected" for x in pair_results if x["status"] == "FAIL"]}
    elif args.mode == "battery":
        if not args.generator:
            data = {"status": "BLOCKED", "errors": ["geometry generator source is required"]}
        else:
            data = battery_bay_fit(args.geometry_dir, args.generator)
    elif args.mode == "connectors":
        data = connector_access_screen(args.geometry_dir)
    elif args.mode == "materials":
        if not args.generator or not args.mass_csv:
            data = {"status":"BLOCKED","errors":["generator and mass table are required"]}
        else:
            data = inspect_materials(args.generator,args.mass_csv)
    elif args.mode == "manufacture":
        data = inspect_manufacturing(args.geometry_dir)
    else:
        if not args.generator or not args.mass_csv:
            data = {"status": "BLOCKED", "errors": ["generator and mass source CSV are required"]}
        else:
            data = recalculate_mass_cg(args.geometry_dir, args.mass_csv, args.generator)
    data["command"] = [sys.executable, "-m", "highspeed_edf.verification.native_adapters", *sys.argv[1:]]
    data["tool_versions"] = {"cadquery": importlib.metadata.version("cadquery"),
                              "cadquery-ocp": importlib.metadata.version("cadquery-ocp")}
    data["python_executable"] = sys.executable
    data["exit_code"] = 0 if data.get("status") == "PASS" else 1 if data.get("status") == "FAIL" else 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({k: v for k, v in data.items() if k not in ("files", "components", "pairs", "ducts", "collisions", "clearance_failures")}, indent=2))
    return data["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
