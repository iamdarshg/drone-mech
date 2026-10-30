#!/usr/bin/env python3
"""Tessellate the pinned Phase-15 STEP assembly and render review views.

Requires CadQuery/OpenCascade, Pillow, and Blender 4.3+ (Eevee Next). The STEP
is read only. The intermediate OBJ is held in a temporary directory and removed
when rendering exits; only the four annotated PNGs are written to --output-dir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import cadquery as cq
import OCP
import PIL
from PIL import Image, ImageDraw, ImageFont

EXPECTED_STEP_SHA256 = "9b83f3bfa5ea261c2055152c9fdd2147b9e16819634715c3c4ae23b45deae772"
HERE = Path(__file__).resolve().parents[1]
DEFAULT_STEP = HERE.parent / "step" / "phase15_airframe_full_assembly.step"
DEFAULT_OUTPUT = HERE / "images"
BLENDER_SCRIPT = Path(__file__).with_name("blender_render_views.py")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")


def export_named_obj(step_path: Path, obj_path: Path) -> tuple[int, int]:
    """Write temporary OBJ groups per STEP assembly node, keeping source names."""
    assembly = cq.Assembly.importStep(str(step_path))
    if not assembly.children:
        raise RuntimeError("STEP assembly import returned no named components")
    solid_count = triangle_count = 0
    with obj_path.open("w", encoding="ascii") as output:
        output.write("# Temporary tessellation of the pinned native Phase-15 STEP assembly\n")
        vertex_offset = 0
        for child in assembly.children:
            solids = child.obj.Solids() if hasattr(child.obj, "Solids") else []
            if not solids:
                continue
            output.write(f"o {safe_name(child.name)}\n")
            for solid in solids:
                vertices, triangles = solid.tessellate(1.4, 0.55)
                if not vertices or not triangles:
                    continue
                for vertex in vertices:
                    output.write(f"v {vertex.x:.6f} {vertex.y:.6f} {vertex.z:.6f}\n")
                for a, b, c in triangles:
                    output.write(f"f {a + vertex_offset + 1} {b + vertex_offset + 1} {c + vertex_offset + 1}\n")
                vertex_offset += len(vertices)
                solid_count += 1
                triangle_count += len(triangles)
    return solid_count, triangle_count


def annotate(path: Path, title: str, note: str | tuple[str, ...]) -> None:
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font_paths = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    font = next((ImageFont.truetype(p, 25) for p in font_paths if Path(p).exists()), ImageFont.load_default())
    small = next((ImageFont.truetype(p, 17) for p in font_paths if Path(p).exists()), ImageFont.load_default())
    lines = (note,) if isinstance(note, str) else note
    top_h, bottom_h = 64, 62 if len(lines) > 1 else 43
    draw.rectangle((0, 0, image.width, top_h), fill=(248, 250, 252))
    draw.rectangle((0, image.height - bottom_h, image.width, image.height), fill=(248, 250, 252))
    draw.text((24, 12), title, font=font, fill=(20, 31, 42))
    for index, line in enumerate(lines):
        draw.text((24, image.height - bottom_h + 7 + index * 24), line, font=small, fill=(29, 43, 54))
    image.save(path, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=Path, default=DEFAULT_STEP, help="source STEP assembly")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="directory for rendered PNGs")
    parser.add_argument("--blender", default=os.environ.get("BLENDER", "blender"), help="Blender executable")
    parser.add_argument("--allow-unpinned-step", action="store_true", help="allow a source STEP with a different SHA256")
    args = parser.parse_args()

    step_path = args.step.resolve()
    out_dir = args.output_dir.resolve()
    if not step_path.is_file():
        parser.error(f"STEP file does not exist: {step_path}")
    source_hash = sha256(step_path)
    if source_hash != EXPECTED_STEP_SHA256 and not args.allow_unpinned_step:
        parser.error(f"STEP SHA256 {source_hash} does not match pinned source {EXPECTED_STEP_SHA256}; pass --allow-unpinned-step only for an intentional alternate")
    blender = shutil.which(args.blender) if not Path(args.blender).is_file() else str(Path(args.blender).resolve())
    if not blender:
        parser.error(f"Blender executable not found: {args.blender}")
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="phase15_native_visual_") as temp_dir:
        obj_path = Path(temp_dir) / "phase15_named_components.obj"
        solids, triangles = export_named_obj(step_path, obj_path)
        print(f"Native STEP: {step_path}\nSHA256: {source_hash}\nTessellated: {solids} solids, {triangles} triangles", flush=True)
        subprocess.run(
            [blender, "--background", "--python", str(BLENDER_SCRIPT), "--",
             "--mesh", str(obj_path), "--output-dir", str(out_dir)],
            check=True,
        )

    captions = {
        "01_exterior_isometric.png": ("01 · Exterior isometric", "All STEP components included; all opaque. No part is hidden or displaced."),
        "02_plan_packaging_hidden_skins.png": ("02 · Plan packaging view", "Hidden: 3 wing sectors + fuselage battery-bay shell. Remaining components opaque."),
        "03_nose_projection.png": ("03 · Nose projection", "All STEP components included; all opaque. View along −Z, X lateral / Y vertical."),
        "04_motor_envelopes_only.png": ("04 · Motor-envelope detail", (
            "Visible: six motor_* envelope parts only; all other STEP components hidden.",
            "Per duct Z spans: R1 12–92, R2 48–128, R3 84–164 mm; adjacent spans overlap by 36 mm.",
        )),
    }
    for filename, (title, note) in captions.items():
        path = out_dir / filename
        if not path.is_file():
            raise RuntimeError(f"Expected render was not produced: {path}")
        annotate(path, title, note)
    blender_version = subprocess.run([blender, "--version"], check=True, capture_output=True, text=True).stdout.splitlines()[0]
    manifest = {
        "provenance": {
            "sourceCommit": "6b07330c9d77193e0c37a87994838a0edba0ac82",
            "sourceStep": str(step_path.relative_to(HERE.parents[3])) if step_path.is_relative_to(HERE.parents[3]) else str(step_path),
            "sourceStepSha256": source_hash,
            "geometryGenerator": "highspeed_edf/phase15/optimization/phase15_generate_geometry.py",
            "geometryGeneratorSha256": "86275054adf53b862dd91bfb3a66b84da3470e8ea400af8e57d5e339ef124caf",
            "assemblyNodes": 73,
            "tessellatedSolids": solids,
            "triangles": triangles,
            "tessellation": {"linearToleranceMm": 1.4, "angularToleranceRad": 0.55},
            "renderer": blender_version,
            "renderEngine": "Blender Eevee Next",
            "pythonVersion": platform.python_version(),
            "cadQueryVersion": cq.__version__,
            "openCascadeVersion": OCP.__version__,
            "pillowVersion": PIL.__version__,
            "resolutionPixels": [1600, 1100],
            "materials": "Opaque category colors; no part is moved or made transparent.",
            "intermediateMesh": "Temporary OBJ; deleted after rendering; not included in this evidence package.",
        },
        "views": [
            {"image": filename, "title": captions[filename][0], "shownOrHidden": captions[filename][1], "sha256": sha256(out_dir / filename)}
            for filename in captions
        ],
        "limitations": [
            "Visual inspection of tessellated STEP geometry only; no CFD, structural, thermal, fatigue, or flight validation is implied.",
            "The motor Z-span comparison is an envelope placement observation; the image is not a motor installation or clearance certification.",
        ],
    }
    (out_dir / "render_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered and annotated four PNGs under {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
