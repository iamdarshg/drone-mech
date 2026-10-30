#!/usr/bin/env python3
"""Experimental A1 mini segmentation of the actual Phase-15 wing STEP parts.

The three airframe STEP solids are cut with planar butt seams only. No keys,
spars, fasteners, adhesive joints, tolerances, or structural qualification are
provided by this prototype.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cadquery as cq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

PROJECT = Path(__file__).resolve().parents[2]
STEP_DIR = PROJECT / "deliverables/phase15_geometry/step"
OUT = PROJECT / "phase15/print_prototype/main_wing"
SOURCE_COMMIT = "a055d113c931c2cd070e837fdb24e9afada066a8"
MAX_BUILD_MM = 180.0
PARTITION_VOLUME_REL_TOL = 1e-6
SOURCES = [
    {
        "id": "left_sector",
        "file": "lifting_wing_left_sector_with_duct_and_elevon_reliefs.step",
        "sha256": "b1fb7cd66f98e8b5e9c65ecb25c703993bb32218cf2ada2c3baa3d1559e7121b",
        "x_bins": 2, "z_bins": 3,
    },
    {
        "id": "centre_bridge",
        "file": "lifting_wing_centre_bridge_sector_with_duct_and_elevon_reliefs.step",
        "sha256": "9e7c2fc06e9be6c9e5e1a12a102e52b2df9e822bf094a025c9bc360715e8bc7d",
        "x_bins": 1, "z_bins": 3,
    },
    {
        "id": "right_sector",
        "file": "lifting_wing_right_sector_with_duct_and_elevon_reliefs.step",
        "sha256": "90687229e733623ccd40ee8839a10d711f38367b46e70e7ae0d86a330b7c358f",
        "x_bins": 2, "z_bins": 3,
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def bounds_mm(shape: cq.Shape) -> list[float]:
    b = shape.BoundingBox()
    return [b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax]


def box(x0: float, x1: float, y0: float, y1: float,
        z0: float, z1: float) -> cq.Shape:
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0,
                            cq.Vector(x0, y0, z0))


def mesh_triangles(shape: cq.Shape, deflection: float = 1.0):
    vertices, triangles = shape.tessellate(deflection, 0.2)
    return [[vertices[i].toTuple() for i in face] for face in triangles]


def make_views(source_shapes: list[tuple[str, cq.Shape]],
               pieces: list[dict], path: Path) -> None:
    fig = plt.figure(figsize=(15, 7), constrained_layout=True)
    ax1 = fig.add_subplot(1, 2, 1, projection="3d")
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")
    for _, shape in source_shapes:
        for face in mesh_triangles(shape):
            ax1.add_collection3d(Poly3DCollection(
                [face], facecolor="#86a9bc", edgecolor="none", alpha=0.88))
    ax1.set_title("Existing left, centre and right wing STEP parts")
    colors = plt.cm.turbo.colors
    # Offsets make the butt seams visible; exported STEP remains in exact source
    # coordinates. Alternating offsets are small and only used in this preview.
    for i, item in enumerate(pieces):
        shift = (0.0, (i % 5) * 1.2, 0.0)
        for face in mesh_triangles(item["shape"]):
            moved = [(x + shift[0], y + shift[1], z + shift[2]) for x, y, z in face]
            ax2.add_collection3d(Poly3DCollection(
                [moved], facecolor=colors[i % len(colors)], edgecolor="#36454f",
                linewidth=0.035, alpha=0.9))
    ax2.set_title("15 planar-cut prototype pieces (preview offsets only)")
    for ax in (ax1, ax2):
        ax.set_xlabel("X span (mm)")
        ax.set_ylabel("Y (mm)")
        ax.set_zlabel("Z chordwise (mm)")
        ax.view_init(elev=24, azim=-52)
        ax.set_box_aspect((540, 55, 560))
        ax.set_xlim(-275, 275)
        ax.set_ylim(-32, 45)
        ax.set_zlim(-285, 285)
    fig.suptitle("Phase-15 actual main-wing STEP segmentation — prototype")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_pieces: list[dict] = []
    components: list[dict] = []
    source_shapes: list[tuple[str, cq.Shape]] = []
    for source_config in SOURCES:
        source_path = (STEP_DIR / source_config["file"]).resolve()
        if sha256(source_path) != source_config["sha256"]:
            raise RuntimeError(f"Pinned source STEP hash mismatch: {source_path}")
        source = cq.importers.importStep(str(source_path)).val()
        if not source.isValid() or len(source.Solids()) != 1:
            raise RuntimeError(f"Source must be one valid solid: {source_path.name}")
        source_shapes.append((source_config["id"], source))
        bb = source.BoundingBox()
        xs = [bb.xmin + (bb.xmax - bb.xmin) * i / source_config["x_bins"]
              for i in range(source_config["x_bins"] + 1)]
        zs = [bb.zmin + (bb.zmax - bb.zmin) * i / source_config["z_bins"]
              for i in range(source_config["z_bins"] + 1)]
        pad = 1.0
        component_pieces = []
        for xi in range(source_config["x_bins"]):
            for zi in range(source_config["z_bins"]):
                clipped = source.intersect(box(
                    xs[xi], xs[xi + 1], bb.ymin - pad, bb.ymax + pad,
                    zs[zi], zs[zi + 1]))
                solids = clipped.Solids()
                if len(solids) != 1 or not clipped.isValid() or solids[0].Volume() <= 0:
                    raise RuntimeError(f"Bad cut solid {source_config['id']} x{xi+1} z{zi+1}")
                shape = solids[0]
                bounds = bounds_mm(shape)
                extents = [bounds[1] - bounds[0], bounds[3] - bounds[2],
                           bounds[5] - bounds[4]]
                if max(extents) >= MAX_BUILD_MM:
                    raise RuntimeError(f"Piece exceeds 180 mm envelope: {extents}")
                piece_id = f"wing_{source_config['id']}_x{xi+1}_z{zi+1}"
                step_path = OUT / f"{piece_id}.step"
                cq.exporters.export(shape, str(step_path), exportType="STEP")
                roundtrip = cq.importers.importStep(str(step_path)).val()
                rb = bounds_mm(roundtrip)
                rextents = [rb[1] - rb[0], rb[3] - rb[2], rb[5] - rb[4]]
                if (len(roundtrip.Solids()) != 1 or not roundtrip.isValid()
                        or max(rextents) >= MAX_BUILD_MM):
                    raise RuntimeError(f"STEP roundtrip failed: {step_path.name}")
                item = {"id": piece_id, "shape": shape, "step": step_path,
                        "volumeMm3": shape.Volume(), "boundsMm": bounds,
                        "extentsMm": extents, "roundtripBoundsMm": rb,
                        "roundtripExtentsMm": rextents, "sha256": sha256(step_path)}
                component_pieces.append(item)
                all_pieces.append(item)
                print(f"wrote {piece_id}", flush=True)

        source_volume = source.Volume()
        piece_volume_sum = sum(p["shape"].Volume() for p in component_pieces)
        rel_error = abs(piece_volume_sum - source_volume) / source_volume
        # Every output is a valid result of `source ∩ slab`, and the slabs
        # form a complete grid over the source bounding box with disjoint
        # interiors. Matching additive volume therefore verifies coverage and
        # no volumetric overlap without invoking an expensive coplanar fuse.
        partition_volume_difference = piece_volume_sum - source_volume
        if rel_error > PARTITION_VOLUME_REL_TOL:
            raise RuntimeError(f"Partition volume check failed: {source_config['id']}")
        components.append({
            "id": source_config["id"],
            "path": str(source_path.relative_to(PROJECT.parent)),
            "sha256": source_config["sha256"],
            "sourceBoundsMm": bounds_mm(source),
            "sourceVolumeMm3": source_volume,
            "pieceCount": len(component_pieces),
            "pieceIds": [p["id"] for p in component_pieces],
            "pieceVolumeSumMm3": piece_volume_sum,
            "partitionVolumeDifferenceMm3": partition_volume_difference,
            "relativePartitionVolumeError": rel_error,
            "sourceCoverageFractionByPartitionVolume": piece_volume_sum / source_volume,
            "partitionVolumeRelativeTolerance": PARTITION_VOLUME_REL_TOL,
            "coverageMethod": "Every piece is a valid source∩slab boolean; axis-aligned bins tile the source bounding box with disjoint interiors; additive piece volume agrees with source volume within stated OCC tolerance. No solid fusion/reconstructed STEP was run.",
        })
        print(f"partition volume checked: {source_config['id']}", flush=True)

    preview = OUT / "phase15_main_wing_segments_views.png"
    make_views(source_shapes, all_pieces, preview)
    manifest = {
        "classification": "EXPERIMENTAL PRINT SEGMENTATION PROTOTYPE; NOT A FABRICATION OR FLIGHT RELEASE",
        "sourceRepositoryCommit": SOURCE_COMMIT,
        "method": {
            "partition": "Left/right sectors each split 2 equal X-span bins × 3 equal Z-chordwise bins; centre bridge split into 3 equal Z-chordwise bins.",
            "printEnvelopeMm": [180, 180, 180],
            "pieceCount": len(all_pieces),
            "seams": "Planar butt cuts, exact coordinate mating, no added joints or clearances.",
            "previewOffsets": "Small Y offsets are used for visualization only. STEP outputs preserve source coordinates.",
        },
        "checks": {
            "allSourcesValidSingleSolid": True,
            "allPieceStepsRoundTripValidSingleSolid": True,
            "allPiecesStrictlyBelow180mmInAllAxes": True,
            "maximumPieceAxisExtentMm": max(max(p["extentsMm"]) for p in all_pieces),
            "maximumRoundtripPieceAxisExtentMm": max(max(p["roundtripExtentsMm"]) for p in all_pieces),
            "allBooleanCutPiecesValidSingleSolid": True,
            "eachComponentPartitionVolumeMatchesSourceWithinTolerance": True,
            "partitionVolumeRelativeTolerance": PARTITION_VOLUME_REL_TOL,
            "fusedReconstructionPerformed": False,
        },
        "components": components,
        "pieces": [{k: v for k, v in item.items() if k not in {"shape", "step"}}
                   | {"step": item["step"].name} for item in all_pieces],
        "preview": preview.name,
        "limitations": [
            "These are the existing Phase-15 left and right 498 mm wing sectors and 425 mm centre bridge components, not the FSI wing_t36mm test article or the full aircraft assembly.",
            "Geometric partition and STEP round trips do not establish printer fit, support strategy, strength, load transfer, alignment, fastening, fatigue, tolerances, or structural integrity.",
            "No slicer, printer, material, coupon, structural, flight, or fabrication validation was performed.",
            "No fabrication or flight suitability is claimed; joint design and structural integration remain unproven.",
        ],
    }
    (OUT / "segmentation_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(OUT), "pieceCount": len(all_pieces),
                      "maximumPieceAxisExtentMm": manifest["checks"]["maximumPieceAxisExtentMm"],
                      "components": [{"id": c["id"], "relativePartitionVolumeError": c["relativePartitionVolumeError"]}
                                     for c in components]}, indent=2))


if __name__ == "__main__":
    main()
