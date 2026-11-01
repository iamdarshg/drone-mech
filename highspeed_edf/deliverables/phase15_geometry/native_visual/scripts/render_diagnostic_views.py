#!/usr/bin/env python3
"""Render three targeted Phase-15 STEP assembly inspection views.

The views only hide named source components; no geometry is moved or altered.
CadQuery/OpenCascade makes a temporary named OBJ from the pinned STEP, and
Blender renders orthographic views. This is visual evidence, not interference
or clearance analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
RENDER_SCRIPT = HERE / "blender_render_diagnostic_views.py"
EXPECTED_STEP_SHA256 = "9b83f3bfa5ea261c2055152c9fdd2147b9e16819634715c3c4ae23b45deae772"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=Path, default=HERE.parents[1] / "step" / "phase15_airframe_full_assembly.step")
    parser.add_argument("--output-dir", type=Path, default=HERE.parents[3] / "phase15" / "reports" / "visual_buildability_20261101")
    parser.add_argument("--blender", default="/usr/bin/blender")
    parser.add_argument("--view", choices=("05", "06", "07"), help="render one view only; default renders all three")
    args = parser.parse_args()
    step = args.step.resolve()
    out = args.output_dir.resolve()
    digest = sha256(step)
    if digest != EXPECTED_STEP_SHA256:
        parser.error(f"STEP hash mismatch: {digest}")
    out.mkdir(parents=True, exist_ok=True)

    # Reuse the audited named-component tessellator; importing the module does
    # not execute its CLI because __name__ is not __main__.
    sys.path.insert(0, str(HERE))
    from render_native_views import export_named_obj

    with tempfile.TemporaryDirectory(prefix="phase15_diagnostic_visual_") as td:
        mesh = Path(td) / "phase15_named_components.obj"
        solids, triangles = export_named_obj(step, mesh)
        command = [args.blender, "--background", "--python", str(RENDER_SCRIPT), "--", "--mesh", str(mesh), "--output-dir", str(out)]
        if args.view:
            command += ["--view", args.view]
        subprocess.run(command, check=True)

    views = [
        {"image": "05_drive_a_side_projection.png", "cameraDirection": [1, 0, 0], "worldUp": [0, 1, 0], "targetMm": [-44, 0, 88], "orthoScaleMm": 270, "screenHorizontalWorldAxis": "-Z (aft points left)", "screenVerticalWorldAxis": "+Y (up)", "imageLabel": "Duct A side projection · motor envelopes and rotor stations", "imageAxes": "Screen-right -Z; +Z aft points left. Screen-up +Y.", "includedPrefixes": ["duct_A_rotor_R", "duct_A_stator_S", "motor_A_R", "six_hot_side_motor_carrier_frames"], "purpose": "Show axial placement of the three motor-can envelopes against Rotor A and stator stations, with other duct and airframe parts hidden."},
        {"image": "06_battery_electronics_side_projection.png", "cameraDirection": [1, 0, 0], "worldUp": [0, 1, 0], "targetMm": "computed from included STEP component bounds", "orthoScaleMm": "1.12 x maximum projected span", "screenHorizontalWorldAxis": "-Z (aft points left)", "screenVerticalWorldAxis": "+Y (up)", "imageLabel": "Battery and avionics groups · actual STEP axial distribution", "imageAxes": "Screen-right -Z; +Z aft points left. Screen-up +Y.", "includedPrefixes": ["Bonka_", "battery_", "esc_", "flight_control_", "flight_6ch_", "fc_", "board_isolator_"], "purpose": "Show battery and board/spreader/cooling group axial distribution with wing, ducts and skins hidden; this view does not imply those parts are adjacent or assembled as one package."},
        {"image": "07_duct_a_top_projection.png", "cameraDirection": [0, 1, 0], "worldUp": [0, 0, 1], "targetMm": [-44, 0, 88], "orthoScaleMm": 310, "screenHorizontalWorldAxis": "-X (lateral right-to-left)", "screenVerticalWorldAxis": "+Z (aft)", "imageLabel": "Duct A axial stack · outer duct hidden", "imageAxes": "Screen-right -X. Screen-up +Z aft.", "includedPrefixes": ["duct_A_rotor_R", "duct_A_stator_S", "duct_A_vector_vane", "motor_A_", "servo_mount_vane_A"], "purpose": "Show Rotor A and stator rows against motor envelopes, with the outer duct and airframe hidden."},
    ]
    if args.view:
        views = [v for v in views if v["image"].startswith(args.view)]
    bounds_path = out / "diagnostic_view_bounds.json"
    bounds = json.loads(bounds_path.read_text()) if bounds_path.is_file() and (not args.view or args.view == "06") else None
    for view in views:
        p = out / view["image"]
        if not p.is_file():
            raise RuntimeError(f"Missing rendered view: {p}")
        if view["image"].startswith("06_") and bounds:
            view["targetMm"] = bounds["autoFraming"]["targetMm"]
            view["orthoScaleMm"] = bounds["autoFraming"]["orthoScaleMm"]
            view["includedComponentNames"] = bounds["visibleComponents"]
            view["componentBoundsMm"] = bounds["componentBoundsMm"]
            view["worldBoundsMm"] = bounds["worldBoundsMm"]
            view["projectedSpanMm"] = bounds["autoFraming"]["projectionSpanMm"]
            view["screenRight"] = bounds["autoFraming"]["screenRight"]
            view["screenUp"] = bounds["autoFraming"]["screenUp"]
        if view.get("imageLabel"):
            img = Image.open(p).convert("RGB")
            draw = ImageDraw.Draw(img)
            regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font = ImageFont.truetype(bold, 27) if Path(bold).exists() else ImageFont.load_default()
            small = ImageFont.truetype(regular, 20) if Path(regular).exists() else ImageFont.load_default()
            draw.rectangle((0, 0, img.width, 52), fill=(248, 250, 252))
            draw.rectangle((0, img.height - 48, img.width, img.height), fill=(248, 250, 252))
            draw.text((22, 10), view["imageLabel"], font=font, fill=(20, 31, 42))
            draw.text((22, img.height - 42), view["imageAxes"] + " Projection only; no clearance claim.", font=small, fill=(29, 43, 54))
            img.save(p, optimize=True)
        view["sha256"] = sha256(p)
    manifest = {
        "sourceStep": str(step.relative_to(HERE.parents[3])),
        "sourceStepSha256": digest,
        "rendererScriptSha256": sha256(RENDER_SCRIPT),
        "cadTessellatorSha256": sha256(HERE / "render_native_views.py"),
        "tessellatedSolids": solids,
        "triangles": triangles,
        "rendering": "Blender orthographic projections, opaque category colors, source placements unchanged; named parts hidden only as specified.",
        "limitations": ["Visual evidence only; opaque projections and selective hiding do not prove physical contact, clearance, alignment, assembly access, or buildability.", "No geometry was moved; no collision solver, CFD, structural analysis, CAM simulation, or physical test was run."],
        "views": views,
    }
    (out / "diagnostic_views_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
