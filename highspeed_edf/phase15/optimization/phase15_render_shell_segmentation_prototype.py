"""Render native views of the round-tripped fuselage segmentation prototype."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

import cadquery as cq
import OCP
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
BLENDER_SCRIPT = ROOT / "highspeed_edf/deliverables/phase15_geometry/native_visual/scripts/blender_render_fuselage_shell.py"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
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
    blender = shutil.which(args.blender)
    if not step.is_file() or not blender:
        parser.error("STEP file and Blender executable are required")
    out.mkdir(parents=True, exist_ok=True)
    shape = cq.importers.importStep(str(step)).val()
    if not shape.isValid():
        raise RuntimeError("Native STEP import is invalid")
    with tempfile.TemporaryDirectory(prefix="phase15_shell_segments_") as temp:
        obj = Path(temp) / "segmented_shell.obj"
        with obj.open("w", encoding="ascii") as stream:
            offset = 0
            for index, solid in enumerate(shape.Solids()):
                stream.write(f"o shell_solid_{index}\n")
                vertices, faces = solid.tessellate(0.6, 0.35)
                for v in vertices:
                    stream.write(f"v {v.x:.6f} {v.y:.6f} {v.z:.6f}\n")
                for a, b, c in faces:
                    stream.write(f"f {a+offset+1} {b+offset+1} {c+offset+1}\n")
                offset += len(vertices)
        subprocess.run([
            blender, "--background", "--python", str(BLENDER_SCRIPT), "--",
            "--mesh", str(obj), "--output-dir", str(out),
        ], check=True)

    captions = {
        "01_shell_isometric.png": ("Segmented fuselage · isometric", "20 valid solids · 10 pieces · original assembled station coordinates"),
        "02_shell_side.png": ("Segmented fuselage · side", "640 mm envelope · transverse cut planes at prototype stations"),
        "03_shell_top.png": ("Segmented fuselage · top", "Centerline section split · no retention hardware modeled"),
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
    b = shape.BoundingBox()
    receipt = {
        "nativeStep": str(step.relative_to(ROOT)),
        "nativeStepSha256": sha256(step),
        "nativeStepValid": shape.isValid(),
        "nativeStepSolidCount": len(shape.Solids()),
        "nativeStepVolumeMm3": shape.Volume(),
        "boundsMm": {"x": [b.xmin, b.xmax], "y": [b.ymin, b.ymax], "z": [b.zmin, b.zmax]},
        "tessellation": {"linearToleranceMm": 0.6, "angularToleranceRad": 0.35},
        "runtime": {"python": platform.python_version(), "cadQuery": cq.__version__, "openCascade": OCP.__version__},
        "images": [{"file": name, "title": title, "note": note, "sha256": sha256(out / name)} for name, (title, note) in captions.items()],
        "limitations": ["Rendered assembled STEP surfaces in native coordinates; this does not validate fit of bond, seal, or fastener hardware."],
    }
    (out / "native_views_manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
