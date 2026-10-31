"""Segment the endpoint-relief shell into A1-mini-sized prototype sections.

Prototype only. The 640 mm source master is not modified. Segments are cut
from the separately documented endpoint-relief 42.6 mm candidate, at
source-evidenced station locations only where available; intermediate section
planes are prototype layout assumptions. The section faces are only geometric
cuts; retention and sealing are not modeled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform

import cadquery as cq
import OCP


ROOT = Path(__file__).resolve().parents[3]
SOURCE_STEP = ROOT / "highspeed_edf/deliverables/phase15_geometry/step/fuselage_battery_bay_shell_endpoint_relief_42_6.step"
SOURCE_REPORT = ROOT / "highspeed_edf/deliverables/phase15_geometry/reports/fuselage_battery_bay_shell_endpoint_relief_42_6.json"
MACHINE_PROFILE = ROOT / "highspeed_edf/phase15/print_prototype/main_wing/software_slice/effective-machine.json"
TRANSVERSE_CUT_STATIONS_MM = [-240.0, -128.0, 0.0, 136.0]
BED_XY_MM = 180.0
BED_Z_MM = 180.0
BED_ROTATION_DEG = 0.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def metrics(shape: cq.Shape) -> dict:
    b = shape.BoundingBox()
    return {
        "valid": shape.isValid(),
        "solidCount": len(shape.Solids()),
        "volumeMm3": shape.Volume(),
        "boundsMm": {"x": [b.xmin, b.xmax], "y": [b.ymin, b.ymax], "z": [b.zmin, b.zmax]},
        "sizeMm": [b.xlen, b.ylen, b.zlen],
    }


def rotated_xy_bounds(shape: cq.Shape, angle_deg: float) -> list[float]:
    b = shape.BoundingBox()
    a = math.radians(angle_deg)
    corners = [(x, y) for x in (b.xmin, b.xmax) for y in (b.ymin, b.ymax)]
    xs = [x * math.cos(a) - y * math.sin(a) for x, y in corners]
    ys = [x * math.sin(a) + y * math.cos(a) for x, y in corners]
    return [max(xs) - min(xs), max(ys) - min(ys), b.zlen]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    shell = cq.importers.importStep(str(SOURCE_STEP)).val()
    if not shell.isValid() or abs(shell.BoundingBox().zlen - 640.0) > 0.01:
        raise RuntimeError("Endpoint-relief source must be a valid 640 mm envelope")

    boundaries: list[float | None] = [None, *TRANSVERSE_CUT_STATIONS_MM, None]
    segments = []
    part_records = []
    started = __import__("time").time()
    cut_faces = [cq.Face.makePlane(1000, 1000, (0, 0, z), (0, 0, 1)) for z in TRANSVERSE_CUT_STATIONS_MM]
    # The source shell's 186 mm body width grows to 211.8 mm at the aft
    # shoulders. A1 mini's 180 mm square bed cannot fit those intact sections
    # in any XY rotation, so this exploratory cut divides the shell at X=0.
    cut_faces.append(cq.Face.makePlane(1000, 1000, (0, 0, 0), (1, 0, 0)))
    split_shape = shell.split(*cut_faces)
    elapsed_split = round(__import__("time").time() - started, 2)
    solid_groups: list[list[cq.Shape]] = [[] for _ in range((len(boundaries) - 1) * 2)]
    for solid in split_shape.Solids():
        b = solid.BoundingBox()
        if b.xmax <= 0.001:
            side_index = 0
        elif b.xmin >= -0.001:
            side_index = 1
        else:
            raise RuntimeError(f"split solid crosses center plane X=0: {metrics(solid)}")
        assigned = False
        for section_index, (lo, hi) in enumerate(zip(boundaries[:-1], boundaries[1:])):
            zlo = -360.001 if lo is None else lo - 0.001
            zhi = 280.001 if hi is None else hi + 0.001
            if b.zmin >= zlo and b.zmax <= zhi:
                solid_groups[section_index * 2 + side_index].append(solid)
                assigned = True
                break
        if not assigned:
            raise RuntimeError(f"split solid crosses a section plane: {metrics(solid)}")

    piece_specs = []
    for section_index, (lo, hi) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        piece_specs.extend([
            (section_index, lo, hi, "port", solid_groups[section_index * 2]),
            (section_index, lo, hi, "starboard", solid_groups[section_index * 2 + 1]),
        ])
    for idx, (section_index, lo, hi, side, group) in enumerate(piece_specs, 1):
        clipped = cq.Compound.makeCompound(group)
        elapsed = elapsed_split if idx == 1 else 0.0
        if not clipped.isValid() or not clipped.Solids():
            raise RuntimeError(f"segment {idx} invalid/empty: {metrics(clipped)}")
        step = out / f"fuselage_shell_segment_{idx:02d}_{side}.step"
        brep = out / f"fuselage_shell_segment_{idx:02d}_{side}.brep"
        cq.exporters.export(clipped, str(step))
        cq.exporters.export(clipped, str(brep))
        step_rt = cq.importers.importStep(str(step)).val()
        brep_rt = cq.importers.importBrep(str(brep)).val()
        if not step_rt.isValid() or not brep_rt.isValid():
            raise RuntimeError(f"round-trip failed for segment {idx}")
        bed = rotated_xy_bounds(step_rt, BED_ROTATION_DEG)
        b = step_rt.BoundingBox()
        record = {
            "index": idx,
            "sectionIndex": section_index + 1,
            "sideOfCenterPlane": side,
            "actualBoundsZMm": [b.zmin, b.zmax],
            "seconds": elapsed,
            "step": step.name,
            "stepSha256": sha256(step),
            "brep": brep.name,
            "brepSha256": sha256(brep),
            "preExport": metrics(clipped),
            "stepRoundTrip": metrics(step_rt),
            "brepRoundTrip": metrics(brep_rt),
            "a1MiniPlacement": {
                "rotationAboutZDeg": BED_ROTATION_DEG,
                "printAxisMapping": "model X/Y/Z to printer X/Y/build Z",
                "rotatedEnvelopeMm": bed,
                "profileEnvelopeMm": [BED_XY_MM, BED_XY_MM, BED_Z_MM],
                "fitsAxisAlignedProfileEnvelope": bed[0] <= BED_XY_MM and bed[1] <= BED_XY_MM and bed[2] <= BED_Z_MM,
            },
        }
        part_records.append(record)
        segments.append(step_rt)
        print(json.dumps(record), flush=True)

    assembly = cq.Compound.makeCompound(segments)
    assembly_step = out / "fuselage_shell_segmented_assembly.step"
    assembly_brep = out / "fuselage_shell_segmented_assembly.brep"
    cq.exporters.export(assembly, str(assembly_step))
    cq.exporters.export(assembly, str(assembly_brep))
    assembly_step_rt = cq.importers.importStep(str(assembly_step)).val()
    assembly_brep_rt = cq.importers.importBrep(str(assembly_brep)).val()
    source_profile = json.loads(MACHINE_PROFILE.read_text(encoding="utf-8"))
    profile_xy = [[float(c) for c in point.split("x")] for point in source_profile["printable_area"]]
    receipt = {
        "status": "prototype-round-trip-valid" if assembly_step_rt.isValid() and assembly_brep_rt.isValid() else "invalid",
        "sourceStep": str(SOURCE_STEP.relative_to(ROOT)),
        "sourceStepSha256": sha256(SOURCE_STEP),
        "sourceReport": str(SOURCE_REPORT.relative_to(ROOT)),
        "sourceReportSha256": sha256(SOURCE_REPORT),
        "sourceEnvelopeMm": metrics(shell),
        "splitter": {"algorithm": "OpenCascade BRepAlgoAPI_Splitter via CadQuery Shape.split", "transverseCutPlaneStationsMm": TRANSVERSE_CUT_STATIONS_MM, "transversePlaneCount": len(TRANSVERSE_CUT_STATIONS_MM), "axialBandCount": len(TRANSVERSE_CUT_STATIONS_MM) + 1, "additionalCenterlinePlaneXmm": 0.0, "seconds": elapsed_split, "splitSolidCount": len(split_shape.Solids())},
        "volumeConservation": {
            "sourceMm3": shell.Volume(),
            "segmentsMm3": sum(item["stepRoundTrip"]["volumeMm3"] for item in part_records),
            "absoluteDifferenceMm3": abs(shell.Volume() - sum(item["stepRoundTrip"]["volumeMm3"] for item in part_records)),
            "toleranceMm3": max(1.0, shell.Volume() * 1e-5),
        },
        "sourceEvidence": {
            "bodyStationSpanMm": 640.0,
            "stationEndpointsMm": [-360.0, 280.0],
            "bodyWidthMm": 186.0,
            "bodyHeightMm": 88.0,
            "bodyShellMm": 1.2,
            "documentedJointIntent": "sealed scarf/flange joints; source states section into <=260 mm pieces at modeled frames z=-100/+100 mm",
            "sourceDoc": "highspeed_edf/phase15/optimization/phase15_generate_geometry.py",
            "intermediateSeamsSourceBacked": False,
        },
        "inheritedEndpointReliefTopology": {
            "solidCount": len(shell.Solids()),
            "reportedComponents": [
                "two duct-side shell walls",
                "lower shell section",
                "separated upper shell section",
            ],
            "sourceReportObservation": "Rendered STEP import shows four components in native locations.",
            "integratedShellContinuity": "not established; sectioning preserves the candidate's disconnected topology",
        },
        "prototypeAssumptions": {
            "transverseCutStationsMm": TRANSVERSE_CUT_STATIONS_MM,
            "additionalCenterlineSplitXmm": 0.0,
            "sourceFrameStationsNotUsedMm": [-100.0, 100.0],
            "seamRule": "four transverse planar cuts create five axial bands; one centerline plane divides each band port/starboard; geometric cuts only, with no modeled adhesive, wrap, fasteners, or flange hardware",
            "placementRotationAboutZDeg": BED_ROTATION_DEG,
            "rotationRequiredForFit": False,
            "segmentationPurpose": "fit each exported shell compound inside the 180x180x180 mm A1 mini profile envelope in the source XYZ orientation",
        },
        "printerProfile": {
            "name": source_profile.get("name"),
            "profileFile": str(MACHINE_PROFILE.relative_to(ROOT)),
            "profileSha256": sha256(MACHINE_PROFILE),
            "printableAreaMm": profile_xy,
            "printableHeightMm": float(source_profile["printable_height"]),
        },
        "segmentCount": len(part_records),
        "segments": part_records,
        "segmentedAssemblyStep": assembly_step.name,
        "segmentedAssemblyStepSha256": sha256(assembly_step),
        "segmentedAssemblyBrep": assembly_brep.name,
        "segmentedAssemblyBrepSha256": sha256(assembly_brep),
        "assemblyStepRoundTrip": metrics(assembly_step_rt),
        "assemblyBrepRoundTrip": metrics(assembly_brep_rt),
        "runtime": {"python": platform.python_version(), "cadQuery": cq.__version__, "openCascade": OCP.__version__},
        "limitations": [
            "Prototype shell segmentation only; original production shell and aircraft assembly are unchanged.",
            "Section faces provide only coincident butt boundaries. Bond, seal, alignment, flange, or fastener construction is absent and requires engineering design.",
            "The inherited endpoint-relief STEP is already four disconnected shell components; this segmentation does not repair those gaps or make a closed monocoque.",
            "The four transverse cuts [-240,-128,0,136] mm and centerline split at X=0 are layout assumptions; they do not use the source-backed frames at Z=-100/+100 mm and are not tested structural joints.",
            "Profile-envelope fit is geometric only; no slicer validation, support review, print test, structural assessment, or flight validation is implied.",
            "The inherited 42.6 mm duct-bore relief changes each bore by +0.2 mm diameter relative to the source; its local wall/interface implications remain open.",
        ],
    }
    report = out / "segmentation_manifest.json"
    report.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2), flush=True)
    if not all(part["a1MiniPlacement"]["fitsAxisAlignedProfileEnvelope"] for part in part_records):
        return 3
    if receipt["volumeConservation"]["absoluteDifferenceMm3"] > receipt["volumeConservation"]["toleranceMm3"]:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
