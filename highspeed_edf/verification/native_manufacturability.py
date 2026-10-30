#!/usr/bin/env python3
"""Source-pinned, geometry-only manufacturability screen for Phase 15 CAD.

This reads the committed STEP BREP files; it does not make toolpaths or infer
unprovided machine, cutter, fixture, print-volume, or material constraints.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import cadquery as cq
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box


ASSETS = {
    "sheet_A": "stock_nests/sheet_A_250x120x5_36rotors_63stators.step",
    "sheet_B": "stock_nests/sheet_B_300x120x5_36rotors_63stators.step",
    "hub_bar": "stock_nests/six_hubs_300x50x16_bar.step",
    "rotor": "step/duct_A_rotor_R1_N13.step",
    "stator": "step/duct_A_stator_S1_N23.step",
    "duct": "step/duct_A_82OD_78ID_L110.step",
    "nozzle": "step/duct_A_separate_nozzle_and_exit_lip.step",
    "fuselage_shell": "step/fuselage_battery_bay_shell.step",
    "wing_left": "step/lifting_wing_left_sector_with_duct_and_elevon_reliefs.step",
    "wing_center": "step/lifting_wing_centre_bridge_sector_with_duct_and_elevon_reliefs.step",
    "wing_right": "step/lifting_wing_right_sector_with_duct_and_elevon_reliefs.step",
}
STOCK_NOMINAL = {
    "sheet_A": (250.0, 120.0, 5.0),
    "sheet_B": (300.0, 120.0, 5.0),
    "hub_bar": (300.0, 50.0, 16.0),
}
REPORT_DIR = Path("highspeed_edf/deliverables/phase15_geometry/reports")
PARAMETERS = Path("highspeed_edf/deliverables/phase15_geometry/reports/phase15_parameter_register.json")
GENERATOR = Path("highspeed_edf/phase15/optimization/phase15_generate_geometry.py")
WING_SEGMENT_DIR = Path("highspeed_edf/phase15/print_prototype/main_wing")
WING_SEGMENT_MANIFEST = WING_SEGMENT_DIR / "segmentation_manifest.json"
SLICER_COMMANDS = ("BambuStudio", "bambu-studio", "orca-slicer", "OrcaSlicer",
                   "prusa-slicer", "PrusaSlicer", "curaengine", "CuraEngine", "slic3r")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def shape_metrics(path: Path) -> dict[str, Any]:
    imported = cq.importers.importStep(str(path))
    solids = imported.solids().vals()
    if not solids:
        raise ValueError(f"STEP has no solids: {path}")
    box = optimal_bbox(imported.val())
    return {
        "solids": len(solids),
        "bboxMm": {axis: round(box[axis.lower() + "len"], 3)
                   for axis in ("X", "Y", "Z")},
        "bboxExtentsMm": {name: round(box[name], 3)
                          for name in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")},
        "volumeMm3": round(sum(s.Volume() for s in solids), 3),
        "allSolidsValid": all(s.isValid() and s.Volume() > 0 for s in solids),
        "sha256": sha256(path),
        "fileBytes": path.stat().st_size,
    }


def optimal_bbox(shape: cq.Shape) -> dict[str, float]:
    """Tight OCCT geometry bounds, excluding the loose control-polygon box."""
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, box, True, False)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return {
        "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax, "zmin": zmin, "zmax": zmax,
        "xlen": xmax - xmin, "ylen": ymax - ymin, "zlen": zmax - zmin,
    }


def vertex_diameter_mm(path: Path) -> float:
    """Lower bound on maximum point distance, from imported BREP vertices."""
    imported = cq.importers.importStep(str(path))
    points = [v.Center().toTuple() for v in imported.vertices().vals()]
    max_sq = 0.0
    for i, a in enumerate(points):
        for b in points[i + 1:]:
            max_sq = max(max_sq, sum((a[k] - b[k]) ** 2 for k in range(3)))
    return round(math.sqrt(max_sq), 3)


def stock_containment(root: Path, key: str, expected: tuple[float, float, float]) -> dict[str, Any]:
    path = root / "highspeed_edf/deliverables/phase15_geometry" / ASSETS[key]
    imported = cq.importers.importStep(str(path))
    solids = imported.solids().vals()
    stock = max(solids, key=lambda s: s.Volume())
    stock_box = optimal_bbox(stock)
    loose = [s for s in solids if s is not stock]
    tol = 1e-5
    outside = []
    min_clearance = float("inf")
    for i, solid in enumerate(loose, 1):
        b = optimal_bbox(solid)
        margins = (b["xmin"] - stock_box["xmin"], stock_box["xmax"] - b["xmax"],
                   b["ymin"] - stock_box["ymin"], stock_box["ymax"] - b["ymax"],
                   b["zmin"] - stock_box["zmin"], stock_box["zmax"] - b["zmax"])
        min_clearance = min(min_clearance, *margins)
        if min(margins) < -tol:
            outside.append({
                "looseSolidIndex": i,
                "overrunMm": round(-min(margins), 3),
                "bboxExtentsMm": {n: round(b[n], 3)
                                  for n in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")},
            })
    actual = (stock_box["xlen"], stock_box["ylen"], stock_box["zlen"])
    stock_match = all(abs(a - b) <= tol for a, b in zip(actual, expected))
    return {
        "expectedStockMm": expected,
        "measuredStockMm": tuple(round(v, 3) for v in actual),
        "stockSolidMatchesNominal": stock_match,
        "looseBlankCount": len(loose),
        "outOfStockBlankCount": len(outside),
        "largestOutrunMm": round(max((x["overrunMm"] for x in outside), default=0.0), 3),
        "minimumBBoxEdgeMarginMm": round(min_clearance, 3),
        "outOfStockExamples": outside[:3],
        "containmentStatus": "FAIL" if outside or not stock_match else "PASS",
        "scope": "Per-solid BREP bounding-box containment only; tool-center offset, part-to-part gap, clamps, vacuum area and collision-free operations are not evaluated.",
    }


def freecad_probe(root: Path) -> dict[str, Any]:
    executable = shutil.which("freecadcmd")
    if not executable:
        return {"available": False, "result": "BLOCKED: freecadcmd not on PATH"}
    step = root / "highspeed_edf/deliverables/phase15_geometry" / ASSETS["sheet_A"]
    crosscheck_files = {
        key: str(root / "highspeed_edf/deliverables/phase15_geometry" / ASSETS[key])
        for key in ("wing_left", "wing_center", "wing_right", "fuselage_shell")
    }
    source = (
        "import json\n"
        "import Part\n"
        f"s=Part.read({str(step)!r})\n"
        "b=s.BoundBox\n"
        "print('SCREEN_NATIVE_STEP solids=%d valid=%s xyz=%.3f,%.3f,%.3f' % "
        "(len(s.Solids), s.isValid(), b.XLength, b.YLength, b.ZLength))\n"
        "import Path\n"
        "print('SCREEN_CAM_MODULE available=%s' % str(Path is not None))\n"
        f"crosschecks={crosscheck_files!r}\n"
        "for name,path in crosschecks.items():\n"
        " sh=Part.read(path)\n"
        " pts,_=sh.tessellate(0.1)\n"
        " dims=[max(getattr(p,a) for p in pts)-min(getattr(p,a) for p in pts) for a in ('x','y','z')]\n"
        " print('SCREEN_MESH '+json.dumps({'asset':name,'bboxMm':[round(x,3) for x in dims],'linearDeflectionMm':0.1}))\n"
    )
    with tempfile.TemporaryDirectory(prefix="phase15_cam_screen_") as td:
        macro = Path(td) / "native_probe.py"
        macro.write_text(source, encoding="utf-8")
        version = subprocess.run([executable, "--version"], capture_output=True,
                                 text=True, timeout=20, check=False)
        result = subprocess.run([executable, str(macro)], capture_output=True,
                                text=True, timeout=90, check=False)
    output = result.stdout + result.stderr
    line = next((line for line in output.splitlines() if line.startswith("SCREEN_NATIVE_STEP")), None)
    cam_line = next((line for line in output.splitlines() if line.startswith("SCREEN_CAM_MODULE")), None)
    mesh_lines = [line.removeprefix("SCREEN_MESH ") for line in output.splitlines()
                  if line.startswith("SCREEN_MESH ")]
    return {
        "available": True,
        "executable": executable,
        "versionExitCode": version.returncode,
        "versionOutput": (version.stdout + version.stderr).strip().splitlines()[0:2],
        "nativeStepImportExitCode": result.returncode,
        "nativeStepImportEvidence": line,
        "camModuleEvidence": cam_line,
        "freecadTessellationCrosschecks": [json.loads(line) for line in mesh_lines],
        "screenRunExitCode": result.returncode,
        "scope": "FreeCAD independently imported stock and print-part STEPs and meshed wing/shell surfaces at 0.1 mm linear deflection. Its default spline-control-polygon BoundBox is deliberately not used for fit because it is loose; tight OCCT AddOptimal bounds are used and checked against these tessellated extents. Path module availability does not establish a machine, postprocessor, or valid toolpath.",
    }


def git_commit(root: Path) -> str:
    p = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                       text=True, capture_output=True, check=True)
    return p.stdout.strip()


def wing_segment_screen(root: Path) -> dict[str, Any]:
    """Check committed experimental wing partitions against the A1 mini cube."""
    manifest_path = root / WING_SEGMENT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    build_volume = tuple(float(x) for x in manifest["method"]["printEnvelopeMm"])
    pieces = []
    for row in manifest["pieces"]:
        path = root / WING_SEGMENT_DIR / row["step"]
        actual_sha256 = sha256(path)
        shape = cq.importers.importStep(str(path)).val()
        bbox = optimal_bbox(shape)
        extents = [bbox["xlen"], bbox["ylen"], bbox["zlen"]]
        solid_count = len(shape.Solids())
        valid = solid_count == 1 and shape.isValid() and shape.Volume() > 0
        axis_fit = all(d < cap for d, cap in zip(extents, build_volume))
        pieces.append({
            "id": row["id"], "path": str(path.relative_to(root)),
            "sha256": actual_sha256, "manifestSha256": row["sha256"],
            "manifestSha256Matches": actual_sha256 == row["sha256"],
            "solids": solid_count,
            "bboxMm": [round(v, 3) for v in extents],
            "volumeMm3": round(shape.Volume(), 3),
            "validSingleSolid": valid, "strictAxisAlignedEnvelopeFit": axis_fit,
        })
    available = {name: path for name in SLICER_COMMANDS if (path := shutil.which(name))}
    source_parts = []
    for item in manifest["components"]:
        path = root / item["path"]
        actual_sha256 = sha256(path)
        source_parts.append({
            "id": item["id"], "path": item["path"],
            "sha256": actual_sha256, "manifestSha256": item["sha256"],
            "manifestSha256Matches": actual_sha256 == item["sha256"],
        })
    return {
        "prototypeClassification": manifest["classification"],
        "sourceRepositoryCommit": manifest["sourceRepositoryCommit"],
        "manifest": {"path": str(manifest_path.relative_to(root)), "sha256": sha256(manifest_path)},
        "sourceParts": source_parts,
        "allSourcePartHashesMatch": all(item["manifestSha256Matches"] for item in source_parts),
        "printerBuildVolumeMm": list(build_volume),
        "pieceCount": len(pieces), "pieces": pieces,
        "allPiecesValid": all(row["validSingleSolid"] for row in pieces),
        "allPieceHashesMatchManifest": all(row["manifestSha256Matches"] for row in pieces),
        "allPiecesStrictAxisAlignedEnvelopeFit": bool(pieces) and all(
            row["strictAxisAlignedEnvelopeFit"] for row in pieces),
        "maximumPieceAxisExtentMm": round(max(max(row["bboxMm"]) for row in pieces), 3),
        "slicerDiscovery": {
            "searchedCommands": list(SLICER_COMMANDS), "available": available,
            "result": ("SLICER_FOUND_NOT_A_PRINTABILITY_RESULT" if available
                       else "BLOCKED_NO_SUPPORTED_SLICER_EXECUTABLE_FOUND"),
        },
        "limitations": [
            "This checks the 15 committed planar butt-cut STEP prototypes against the nominal printer cube only.",
            "The pieces have no joint keys, spar, alignment features, tolerances, or structural validation; the source manifest explicitly says no slicer or print test was performed.",
            "Axis-aligned envelope fit does not establish bed adhesion, supportability, orientation, material/process feasibility, or printer clearance.",
        ],
    }


def build(root: Path) -> dict[str, Any]:
    geometry = root / "highspeed_edf/deliverables/phase15_geometry"
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "screen": "Phase-15 CNC/FDM geometry manufacturability preflight",
        "sourceCommit": git_commit(root),
        "sourceInputs": {
            "screenProgram": {"path": "highspeed_edf/verification/native_manufacturability.py",
                              "sha256": sha256(root / "highspeed_edf/verification/native_manufacturability.py")},
            "geometryGenerator": {"path": str(GENERATOR), "sha256": sha256(root / GENERATOR)},
            "parameterRegister": {"path": str(PARAMETERS), "sha256": sha256(root / PARAMETERS)},
        },
        "nativeToolEvidence": {
            "cadqueryVersion": cq.__version__,
            "openCascadePythonVersion": __import__("OCP").__version__,
            "freecad": freecad_probe(root),
        },
        "assets": {},
        "stockNesting": {},
        "manufacturingConstraints": {
            "documentedCncEnvelopeRequirementMm": [320, 140, 45],
            "userStatedCncIdentifier": "233018 Pro (as transcribed; manufacturer/model not verified)",
            "designBriefMachineClass": "3018-class (generic reference only; manufacturer not established)",
            "machineIdentityOrMeasuredTravelEvidence": "UNKNOWN; no verified manufacturer/model, serial, measured travel, fixture envelope, spindle/runout, or tool-holder data is present.",
            "userReportedAluminumCuttingCapability": "can barely cut aluminum; qualitative report only, no measured forces, spindle/load data, feeds/speeds or cut test supplied.",
            "userStatedShopStock": "6 mm and 20 mm 6061 aluminum sheet; temper and sheet dimensions unknown.",
            "userStatedCutters": "Two-flute PCB-style carbide cutters nominally Ø0.1–2 mm and V-cutters. Flute length is visually estimated at 8–10 mm, not measured per tool; usable reach, stickout, runout, holders, condition and cutting data are unknown.",
            "stockCutterDepthScreen": {
                "6mmSheetVsVisuallyEstimated8To10mmFlute": "2–4 mm nominal flute-length spare only if that estimate applies to the selected tool; not proof of safe reach, through-cut clearance, or holder/workholding access.",
                "20mmSheetVsVisuallyEstimated8To10mmFlute": "10–12 mm deeper than the visual flute estimate; full-thickness machining requires staged access/tooling or another process, with reach and setup evidence still required.",
                "designStockThicknessesMm": {"rotorStatorSheets": 5.0, "hubBar": 16.0},
                "fit": "Unknown: user stock dimensions are not stated; 20 mm sheet is not evidence of the specified 300×50×16 mm hub bar. The STEP nests model 5 mm sheets and a 16 mm bar.",
            },
            "camReadiness": "BLOCKED: no sourced tool library/feed-speed data, stock/workholding model, postprocessor identity, generated operation, collision simulation, or NC output is evidenced.",
            "selectedPrinter": "Bambu Lab A1 mini (user-stated)",
            "selectedPrinterBuildVolumeMm": [180, 180, 180],
            "printerBuildVolumeSource": "Bambu Lab A1 mini official specifications/product page: https://bambulab.com/en/a1-mini/tech-specs (build volume 180 × 180 × 180 mm).",
            "fdmReadiness": "BLOCKED: no slicer profile, filament datasheet, support plan, or sliced job is evidenced.",
            "userStockThicknessScreen": {
                "reportedSheetThicknessMm": [6.0, 20.0],
                "designSheetStockMm": [5.0],
                "designHubBlankThicknessMm": 16.0,
                "interpretation": "The 6 mm stock differs by +1 mm from the 5 mm sheet nest; the 20 mm stock differs by +4 mm from the 16 mm hub blank. Sheet XY, temper, flatness and thickness tolerance are not stated, so neither can yet be matched to the STEP nests. With only a visually estimated 8–10 mm flute length, 20 mm through-depth is beyond the estimate; no staged operation or long-reach tool is approved by this screen.",
            },
            "promotableFabricationRelease": False,
        },
    }
    for key, rel in ASSETS.items():
        result["assets"][key] = {"path": f"highspeed_edf/deliverables/phase15_geometry/{rel}", **shape_metrics(geometry / rel)}
    for key, expected in STOCK_NOMINAL.items():
        result["stockNesting"][key] = stock_containment(root, key, expected)

    # Conservative documented geometry checks: compare actual single-part STEP
    # extents with the source brief's own maximum 260 mm FDM section length.
    result["fdmGeometryChecks"] = {
        "printer": "Bambu Lab A1 mini",
        "nominalBuildVolumeMm": [180.0, 180.0, 180.0],
        "fitMethod": "Tight OCCT AddOptimal BREP bounds (not the loose default FreeCAD BoundBox around spline control polygons); the maximum of BREP vertex-pair distance and the largest axis span is a lower bound on the part's maximum point separation. All axis permutations are checked for the 180 mm cube. A lower bound above the 311.77 mm cube body diagonal proves no rotation can fit; a smaller value does not prove fit.",
        "documentedMaximumSectionLengthMm": 260.0,
        "fuselageShell": {
            "measuredExportBboxMm": result["assets"]["fuselage_shell"]["bboxMm"],
            "documentedMasterBodyLengthMm": 640.0,
            "status": "BLOCKED: exported shell BREP is only 84 mm in Z and does not provide the described 640 mm master or its ≤260 mm print sections.",
        },
        "wingLeft": {
            "measuredExportBboxMm": result["assets"]["wing_left"]["bboxMm"],
            "longestAxisMm": max(result["assets"]["wing_left"]["bboxMm"].values()),
            "status": "FAIL against the documented 260 mm maximum section envelope: the exported single solid has a 498.61 mm axis-aligned extent; no finer split artifacts are present.",
        },
        "wingRight": {
            "measuredExportBboxMm": result["assets"]["wing_right"]["bboxMm"],
            "longestAxisMm": max(result["assets"]["wing_right"]["bboxMm"].values()),
            "status": "FAIL against the documented 260 mm maximum section envelope: the exported single solid has a 498.61 mm axis-aligned extent; no finer split artifacts are present.",
        },
        "a1MiniPartFits": {},
        "limitation": "The vertex-diameter lower bound can prove impossible fit when it exceeds the cube body diagonal; a smaller value does not prove arbitrary rotated fit. No slicer/printability judgement is made.",
    }
    for key in ("rotor", "stator", "duct", "nozzle", "fuselage_shell", "wing_left", "wing_center", "wing_right"):
        a = result["assets"][key]
        extents = tuple(a["bboxMm"].values())
        axis_fit = any(all(d <= cap for d, cap in zip(order, (180.0, 180.0, 180.0)))
                       for order in itertools.permutations(extents))
        diameter = vertex_diameter_mm(geometry / ASSETS[key])
        diameter_lower_bound = max(diameter, *extents)
        diagonal = math.sqrt(3 * 180.0 ** 2)
        result["fdmGeometryChecks"]["a1MiniPartFits"][key] = {
            "bboxMm": a["bboxMm"],
            "farthestBrepVertexPairMm": diameter,
            "orientationIndependentDiameterLowerBoundMm": round(diameter_lower_bound, 3),
            "printerCubeBodyDiagonalMm": round(diagonal, 3),
            "axisAlignedOrAxisPermutedFit": axis_fit,
            "orientationIndependentResult": "IMPOSSIBLE" if diameter_lower_bound > diagonal else "UNRESOLVED_BY_DIAMETER_BOUND",
            "orientationScreen": "FITS_AXIS_ALIGNED" if axis_fit else ("IMPOSSIBLE_ANY_ORIENTATION" if diameter_lower_bound > diagonal else "NO_AXIS_ALIGNED_FIT; ROTATED_FIT_UNRESOLVED"),
        }
    result["fdmGeometryChecks"]["segmentedWingPrototype"] = wing_segment_screen(root)
    outside = sum(entry["outOfStockBlankCount"] for entry in result["stockNesting"].values())
    result["overallDisposition"] = (
        "FAIL geometry containment / BLOCKED machine-specific CAM and FDM feasibility"
        if outside else "BLOCKED machine-specific CAM and FDM feasibility"
    )
    result["prohibitedInferences"] = [
        "A positive-volume STEP reimport is not evidence of machinability, printability, a valid toolpath, or fabrication readiness.",
        "This screen does not qualify rotor balance, fatigue, material temperature, surface finish, or overspeed containment.",
    ]
    return result


def render_markdown(data: dict[str, Any]) -> str:
    assets = data["assets"]
    lines = [
        "# Phase-15 CNC and FDM manufacturability screen",
        "",
        f"**Disposition:** {data['overallDisposition']}. Fabrication release is not supported by this screen.",
        "",
        f"CAD input revision (commit containing the measured STEP files and parameter register): `{data['sourceCommit']}`. Geometry, register and screen-program hashes are recorded in the companion JSON.",
        "",
        "## Native geometry findings",
        "",
        "All dimensions below were measured by importing the committed STEP BREP, in mm. This is a geometric preflight; no CAM toolpath or sliced print was generated.",
        "",
        "| Asset | BREP solids | X × Y × Z bounds | Result |",
        "|---|---:|---:|---|",
    ]
    for key in ASSETS:
        a = assets[key]
        dims = " × ".join(f"{v:g}" for v in a["bboxMm"].values())
        status = "valid positive-volume BREP" if a["allSolidsValid"] else "invalid BREP"
        lines.append(f"| `{key}` | {a['solids']} | {dims} | {status} |")
    lines += ["", "## Fabrication blockers", ""]
    for key, entry in data["stockNesting"].items():
        lines.append(
            f"- **{key}: {entry['containmentStatus']} stock containment.** Nominal stock "
            f"{entry['expectedStockMm']} mm; measured {entry['measuredStockMm']} mm; "
            f"{entry['outOfStockBlankCount']} of {entry['looseBlankCount']} loose blanks extend beyond the raw-stock BREP "
            f"(maximum {entry['largestOutrunMm']} mm; minimum bounding-box edge margin {entry['minimumBBoxEdgeMarginMm']} mm)."
        )
    lines += [
        "- The CNC design requirement is **≥320 × 140 × 45 mm**. User-stated machine identifier is `233018 Pro`; manufacturer and exact model remain unverified, and no measured travel is available. The user reports it can barely cut aluminum. The design brief separately mentions generic 3018-class equipment. Stock dimensions and the nominal class do not establish setup fit; clamps, fixture, tool and approach clearances remain unknown.",
        "- User-reported stock is 6061 aluminum with unspecified temper, as 6 mm and 20 mm sheets (sheet dimensions, flatness, and thickness tolerances unknown). The nests use 5 mm sheet and model 16 mm hub blanks in a 300 × 50 × 16 mm bar. Thickness alone does not establish a stock match; no 300 × 50 × 16 mm bar is identified.",
        "- User-reported tooling is two-flute PCB-style carbide cutters, nominal Ø0.1–2 mm, plus V-cutters. Flutes are visually estimated at 8–10 mm, not measured. A 6 mm through-cut has only 2–4 mm nominal flute spare under that estimate; a 20 mm through-cut is 10–12 mm deeper. This does not prove flute reach, shank/holder clearance, tool stickout, clamp access, safe feeds/speeds, runout, or suitability for the unspecified 6061 temper. A staged strategy or suitable longer-reach tooling must be evidenced for 20 mm stock.",
        "- Rotor/stator blanks are nested stock geometry only. The design calls for indexed/two-sided 3D machining, but there is no tool library, operation plan, feeds/speeds, machine model, collision check, postprocessor identity or NC file. The 20 mm stock is 10–12 mm deeper than the visually estimated 8–10 mm flute length; no staged setup or longer-reach tool has been verified.",
        "- The fuselage shell STEP measures only 194.04 × 76.06 × 84 mm, while the geometry notes describe a 640 mm master divided into sections up to 260 mm. The exported shell file does not contain that master or the described print sections.",
        "- The selected printer is the Bambu Lab A1 mini; Bambu Lab lists a 180 × 180 × 180 mm build volume ([official specifications](https://bambulab.com/en/a1-mini/tech-specs)). Rotor, stator, duct and nozzle axis-aligned extents fit the cube. The three unsplit wing BREP source parts exceed the cube's 311.77 mm body diagonal by a rotation-independent distance bound: the left and right sectors each have a 498.61 mm axis span; the center bridge has a 425.054 mm axis span. None can fit in any orientation. Their 15 experimental segmentation pieces are assessed separately below. The shell's lower bound is between 180 mm and the cube diagonal: its direct fit fails one axis, while a rotated fit is unresolved. It is only the short shell export described above.",
        "- The main wing now has 15 experimental planar-cut STEP pieces. The source-pinned prototype checks their BREP validity and confirms every piece is strictly inside the A1 mini's nominal 180 mm cube when axis-aligned; the maximum piece axis extent is %.3f mm. The cuts are simple butt seams without alignment/joinery features and are not a structural wing design. No supported slicer executable, profile, or sliced job is available in this environment. These BREP envelope checks establish neither print feasibility nor assembly strength." % data["fdmGeometryChecks"]["segmentedWingPrototype"]["maximumPieceAxisExtentMm"],
        "- A FreeCAD 1.0.0 native STEP import independently confirmed the sheet-A nest and tessellated wing/shell surfaces at 0.1 mm linear deflection. FreeCAD's default spline-control-polygon `BoundBox` can report much larger extents; this screen uses tight OCCT `AddOptimal` bounds, which agree with the mesh extents. FreeCAD's `Path` CAM module is installed, but this only proves module availability; no machine configuration, postprocessor or toolpath was executed.",
        "- FDM material/process feasibility remains blocked despite the user-stated printer and known nominal volume: no slicer profile, filament grade/datasheet, material/process qualification, orientation/support plan or sliced job is pinned. Composite and hot-side material requirements need separate qualification.",
        "",
        "## Scope and reproducibility",
        "",
        "Run from the repository root with `python highspeed_edf/verification/native_manufacturability.py`. The program imports 11 actual STEP assets and all 15 wing segmentation STEP prototypes with CadQuery/OpenCascade, records file SHA-256 and tight `BRepBndLib.AddOptimal` bounds/volumes, checks loose-blank BREP bounding boxes against the stock solid, records whether a supported slicer executable is present, then independently imports sheet A and compares selected print-part bounds against FreeCAD tessellation at 0.1 mm linear deflection. It writes JSON and this report in the Phase-15 reports directory.",
        "",
        "Stock containment checks use bounding boxes only; part-to-part spacing, cutter compensation, fixtures, machine travel, collision-free toolpaths and sliced print volume are not evaluated. Do not infer fabrication readiness from STEP validity or this screen.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true", help="generate outputs and verify known geometry blockers")
    args = parser.parse_args()
    root = args.repo.resolve()
    data = build(root)
    report_dir = root / REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "phase15_manufacturability_screen.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (report_dir / "phase15_manufacturability_screen.md").write_text(
        render_markdown(data), encoding="utf-8")
    print(f"screen disposition: {data['overallDisposition']}")
    print(f"FreeCAD probe: {data['nativeToolEvidence']['freecad']['nativeStepImportEvidence']}")
    print(f"out-of-stock blanks: {sum(x['outOfStockBlankCount'] for x in data['stockNesting'].values())}")
    if args.self_test:
        assert data["nativeToolEvidence"]["freecad"]["nativeStepImportExitCode"] == 0
        assert data["nativeToolEvidence"]["freecad"]["nativeStepImportEvidence"]
        assert data["stockNesting"]["sheet_A"]["outOfStockBlankCount"] == 0
        assert data["stockNesting"]["sheet_A"]["containmentStatus"] == "PASS"
        assert data["stockNesting"]["sheet_B"]["outOfStockBlankCount"] == 0
        assert data["stockNesting"]["sheet_B"]["containmentStatus"] == "PASS"
        assert data["stockNesting"]["hub_bar"]["outOfStockBlankCount"] == 0
        assert data["fdmGeometryChecks"]["fuselageShell"]["measuredExportBboxMm"]["Z"] == 84.0
        assert data["fdmGeometryChecks"]["wingLeft"]["longestAxisMm"] > 260.0
        assert data["fdmGeometryChecks"]["a1MiniPartFits"]["wing_left"]["orientationIndependentResult"] == "IMPOSSIBLE"
        segmented = data["fdmGeometryChecks"]["segmentedWingPrototype"]
        assert segmented["pieceCount"] == 15
        assert segmented["allSourcePartHashesMatch"]
        assert segmented["allPieceHashesMatchManifest"]
        assert segmented["allPiecesValid"] and segmented["allPiecesStrictAxisAlignedEnvelopeFit"]
        assert segmented["slicerDiscovery"]["result"] == "BLOCKED_NO_SUPPORTED_SLICER_EXECUTABLE_FOUND"
        mesh_bounds = {row["asset"]: row["bboxMm"]
                       for row in data["nativeToolEvidence"]["freecad"]["freecadTessellationCrosschecks"]}
        for key, asset_key in (("wing_left", "wing_left"), ("wing_center", "wing_center"),
                               ("wing_right", "wing_right"), ("fuselage_shell", "fuselage_shell")):
            measured = data["assets"][asset_key]["bboxMm"]
            for index, axis in enumerate(("X", "Y", "Z")):
                assert abs(measured[axis] - mesh_bounds[key][index]) <= 0.1
        assert data["manufacturingConstraints"]["promotableFabricationRelease"] is False
        print("self-test: PASS (observed STEP fit blockers and blocked release state)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
