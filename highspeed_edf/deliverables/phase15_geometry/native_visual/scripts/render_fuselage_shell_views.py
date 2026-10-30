#!/usr/bin/env python3
"""Render annotated review views from the repaired fuselage shell STEP."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile

import cadquery as cq
import OCP
import PIL
from PIL import Image, ImageDraw, ImageFont


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--blender", default="blender")
    args = parser.parse_args()
    step = args.step.resolve()
    out = args.output_dir.resolve()
    blender = shutil.which(args.blender) or (str(Path(args.blender).resolve()) if Path(args.blender).is_file() else None)
    if not step.is_file():
        parser.error(f"STEP does not exist: {step}")
    if not blender:
        parser.error(f"Blender executable not found: {args.blender}")
    out.mkdir(parents=True, exist_ok=True)

    imported = (cq.importers.importBrep if step.suffix.lower() == ".brep" else cq.importers.importStep)(str(step)).val()
    bounds = imported.BoundingBox()
    with tempfile.TemporaryDirectory(prefix="fuselage_shell_native_") as temp:
        obj_path = Path(temp) / "fuselage_shell.obj"
        with obj_path.open("w", encoding="ascii") as mesh:
            offset = 0
            triangles = 0
            for index, solid in enumerate(imported.Solids()):
                mesh.write(f"o shell_solid_{index}\n")
                vertices, faces = solid.tessellate(0.6, 0.35)
                for vertex in vertices:
                    mesh.write(f"v {vertex.x:.6f} {vertex.y:.6f} {vertex.z:.6f}\n")
                for a, b, c in faces:
                    mesh.write(f"f {a + offset + 1} {b + offset + 1} {c + offset + 1}\n")
                offset += len(vertices)
                triangles += len(faces)
        subprocess.run(
            [blender, "--background", "--python", str(Path(__file__).with_name("blender_render_fuselage_shell.py")),
             "--", "--mesh", str(obj_path), "--output-dir", str(out)], check=True,
        )

    captions = {
        "01_shell_isometric.png": ("Fuselage shell · isometric", "Four disconnected BREP solids, colored by solid index; no parts moved."),
        "02_shell_side.png": ("Fuselage shell · side view", "Full station span −360 to +280 mm; components remain in native locations."),
        "03_shell_top.png": ("Fuselage shell · top view", "Service aperture and cavity; four solids remain in native locations."),
    }
    for filename, (title, note) in captions.items():
        image_path = out / filename
        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        title_font = ImageFont.truetype(font_path, 25) if Path(font_path).exists() else ImageFont.load_default()
        note_font = ImageFont.truetype(font_path, 17) if Path(font_path).exists() else ImageFont.load_default()
        draw.rectangle((0, 0, image.width, 56), fill=(248, 250, 252))
        draw.rectangle((0, image.height - 42, image.width, image.height), fill=(248, 250, 252))
        draw.text((20, 10), title, font=title_font, fill=(20, 31, 42))
        draw.text((20, image.height - 33), note, font=note_font, fill=(29, 43, 54))
        image.save(image_path, optimize=True)

    manifest = {
        "sourceStep": str(step),
        "sourceStepSha256": sha256(step),
        "viewedNativeStepSolids": len(imported.Solids()),
        "tessellation": {"linearToleranceMm": 0.6, "angularToleranceRad": 0.35, "triangles": triangles},
        "boundsMm": {"x": [bounds.xmin, bounds.xmax], "y": [bounds.ymin, bounds.ymax], "z": [bounds.zmin, bounds.zmax]},
        "renderer": subprocess.run([blender, "--version"], check=True, capture_output=True, text=True).stdout.splitlines()[0],
        "runtime": {"python": platform.python_version(), "cadQuery": cq.__version__, "openCascade": OCP.__version__, "pillow": PIL.__version__},
        "images": [{"file": name, "title": title, "note": note, "sha256": sha256(out / name)} for name, (title, note) in captions.items()],
        "limitations": ["Rendered surface geometry only; these images do not establish manufacturing suitability, structural performance, or flight readiness."],
    }
    (out / "fuselage_shell_render_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
