"""Generate and round-trip an isolated Phase-15 fuselage-shell candidate.

This keeps the source-pinned production generator unchanged while exercising
sequential shell Booleans against its exact loft stations, tools, and constants.
It writes one standalone STEP and a JSON receipt; it does not regenerate or
replace the full aircraft assembly.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
from pathlib import Path
import sys
import time

import cadquery as cq
import OCP


ROOT = Path(__file__).resolve().parents[3]
BASE_GENERATOR = ROOT / "highspeed_edf/phase15/optimization/phase15_generate_geometry.py"
EXPECTED_BASE_GENERATOR_SHA256 = "53353da1c6f46d8cd9df7431209946869c0984908b269fb94d01f25a1cfabd47"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_base_generator():
    actual = sha256(BASE_GENERATOR)
    if actual != EXPECTED_BASE_GENERATOR_SHA256:
        raise RuntimeError(f"Pinned base generator hash mismatch: {actual}")
    spec = importlib.util.spec_from_file_location("phase15_base_generator", BASE_GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def metrics(shape: cq.Shape) -> dict:
    bounds = shape.BoundingBox()
    return {
        "valid": shape.isValid(),
        "solidCount": len(shape.Solids()),
        "volumeMm3": shape.Volume(),
        "boundsMm": {
            "x": [bounds.xmin, bounds.xmax],
            "y": [bounds.ymin, bounds.ymax],
            "z": [bounds.zmin, bounds.zmax],
        },
    }


def make_shell(g, order: str, stages: list[dict]) -> cq.Shape:
    stations = [
        (g.BODY_Z_MIN, 2.0, 2.0), (-350.0, 54.0, 34.0), (-330.0, 126.0, 66.0),
        (-300.0, g.BODY_WIDTH, g.BODY_HEIGHT), (-200.0, g.BODY_WIDTH, g.BODY_HEIGHT),
        (-100.0, g.BODY_WIDTH, g.BODY_HEIGHT), (0.0, g.BODY_WIDTH, g.BODY_HEIGHT),
        (120.0, g.BODY_WIDTH, g.BODY_HEIGHT), (200.0, 170.0, 80.0),
        (250.0, 112.0, 54.0), (g.BODY_Z_MAX, 3.0, 3.0),
    ]
    outer = cq.Solid.makeLoft([g.superellipse_wire(z, w, h) for z, w, h in stations], ruled=False)
    inner_stations = [
        (-298.8, g.BODY_WIDTH - 2 * g.BODY_SHELL, g.BODY_HEIGHT - 2 * g.BODY_SHELL),
        (-200.0, g.BODY_WIDTH - 2 * g.BODY_SHELL, g.BODY_HEIGHT - 2 * g.BODY_SHELL),
        (-100.0, g.BODY_WIDTH - 2 * g.BODY_SHELL, g.BODY_HEIGHT - 2 * g.BODY_SHELL),
        (0.0, g.BODY_WIDTH - 2 * g.BODY_SHELL, g.BODY_HEIGHT - 2 * g.BODY_SHELL),
        (120.0, g.BODY_WIDTH - 2 * g.BODY_SHELL, g.BODY_HEIGHT - 2 * g.BODY_SHELL),
        (198.0, 167.6, 77.6), (247.0, 106.0, 50.0),
    ]
    cavity = cq.Solid.makeLoft([g.superellipse_wire(z, w, h) for z, w, h in inner_stations], ruled=False)
    duct_tools = [
        cq.Solid.makeCylinder(42.5, 402.0, g.Vector(x, 0, -112.0), g.Vector(0, 0, 1))
        for x in g.DUCT_CENTRES_X
    ]
    slot_tools = []
    for side in (-1, 1):
        points = [
            g.Vector(side * 66.0, 42.0 * g.math.cos(2 * g.math.pi * i / 72),
                     -70.0 + 42.0 * g.math.sin(2 * g.math.pi * i / 72))
            for i in range(72)
        ]
        slot_wire = cq.Wire.makePolygon(points, close=True)
        slot_tools.append(cq.Solid.extrudeLinear(slot_wire, [], g.Vector(side * 40.0, 0, 0)))
    hatch = g.box_at(139.0, 24.0, 202.0, (0, 39.5, g.BATTERY_Z_CENTRE))
    tools = duct_tools + [cavity] + slot_tools + [hatch] if order == "ducts-first" else [cavity] + duct_tools + slot_tools + [hatch]

    shape = outer
    for index, tool in enumerate(tools):
        started = time.time()
        shape = shape.cut(tool)
        stage = metrics(shape)
        stages.append({"index": index + 1, "seconds": round(time.time() - started, 1), **stage})
        print(json.dumps(stages[-1]), flush=True)
    return shape


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order", choices=("cavity-first", "ducts-first"), default="ducts-first")
    parser.add_argument("--step", type=Path, required=True)
    parser.add_argument("--brep", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    g = load_base_generator()
    stages: list[dict] = []
    shape = make_shell(g, args.order, stages)
    args.step.parent.mkdir(parents=True, exist_ok=True)
    args.brep.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    pre_export = metrics(shape)
    cq.exporters.export(shape, str(args.brep))
    brep_round_trip = cq.importers.importBrep(str(args.brep)).val()
    cq.exporters.export(shape, str(args.step))
    round_trip = cq.importers.importStep(str(args.step)).val()
    receipt = {
        "candidateStatus": "round-trip-valid" if brep_round_trip.isValid() and round_trip.isValid() else "round-trip-invalid",
        "booleanOrder": args.order,
        "runtime": {"python": platform.python_version(), "cadQuery": cq.__version__, "openCascade": OCP.__version__},
        "baseGenerator": str(BASE_GENERATOR.relative_to(ROOT)),
        "baseGeneratorSha256": sha256(BASE_GENERATOR),
        "candidateGenerator": str(Path(__file__).relative_to(ROOT)),
        "candidateGeneratorSha256": sha256(Path(__file__)),
        "step": str(args.step.resolve().relative_to(ROOT)),
        "stepSha256": sha256(args.step),
        "brep": str(args.brep.resolve().relative_to(ROOT)),
        "brepSha256": sha256(args.brep),
        "units": "mm",
        "stationAxis": "Z",
        "stages": stages,
        "preExport": pre_export,
        "brepRoundTrip": metrics(brep_round_trip),
        "roundTrip": metrics(round_trip),
        "limitations": ["Standalone geometry candidate only; no aircraft assembly, manufacturing, structural, or flight validation is implied."],
    }
    args.report.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2), flush=True)
    return 0 if brep_round_trip.isValid() and round_trip.isValid() else 2


if __name__ == "__main__":
    raise SystemExit(main())
