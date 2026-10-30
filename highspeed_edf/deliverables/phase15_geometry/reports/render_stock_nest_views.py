"""Render top-down camera views from native sheet-nest STEP solids.

Run from repository root:
  python highspeed_edf/deliverables/phase15_geometry/reports/render_stock_nest_views.py
"""
from pathlib import Path
import cadquery as cq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "stock_nests"
OUT = ROOT / "reports" / "phase15_stock_nest_views.png"
SHEETS = [
    ("sheet_A_250x120x5_36rotors_63stators.step", 250.0, 120.0),
    ("sheet_B_300x120x5_36rotors_63stators.step", 300.0, 120.0),
]


def mesh_solid(solid):
    points, triangles = solid.tessellate(0.4, 0.2)
    # Orthographically project the imported 3D mesh along -Z onto XY.
    return [[(points[index].x, points[index].y) for index in tri]
            for tri in triangles]


def draw_sheet(ax, filename, sx, sy):
    solids = cq.importers.importStep(str(STOCK / filename)).val().Solids()
    if len(solids) != 100:
        raise RuntimeError(f"{filename}: expected 100 solids, found {len(solids)}")
    stock_bb = solids[0].BoundingBox()
    ax.add_patch(Rectangle((stock_bb.xmin, stock_bb.ymin),
                           stock_bb.xmax - stock_bb.xmin,
                           stock_bb.ymax - stock_bb.ymin,
                           facecolor="#aeb8bf", edgecolor="#455a64",
                           linewidth=0.8, alpha=0.18, zorder=1))
    for solid in solids[1:]:
        bb = solid.BoundingBox()
        kind_color = "#168aad" if abs((bb.xmax - bb.xmin) - 29.0) < 1e-3 else "#e76f51"
        ax.add_collection(PolyCollection(mesh_solid(solid), facecolor=kind_color,
                                         edgecolor="#263238", linewidth=0.04, alpha=0.82,
                                         zorder=2))
    ax.set_xlim(0, sx); ax.set_ylim(0, sy)
    ax.set_xlabel("Stock X (mm)"); ax.set_ylabel("Stock Y (mm)")
    ax.set_title(f"{filename.split('_')[1]} — {sx:g} × {sy:g} × 5 mm", fontsize=11, weight="bold")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.2)


def main():
    fig = plt.figure(figsize=(13, 7), facecolor="white")
    for index, (filename, sx, sy) in enumerate(SHEETS, start=1):
        draw_sheet(fig.add_subplot(1, 2, index), filename, sx, sy)
    fig.suptitle("Phase-15 sheet nests — top-down projection of native STEP solids", fontsize=15, weight="bold")
    fig.text(0.5, 0.035,
             "Blue: 36 rotor blanks  •  Orange: 63 stator blanks  •  Gray: raw sheet overlay  •  Geometry-only nest; no CAM or machine verification",
             ha="center", fontsize=9, color="#455a64")
    fig.tight_layout(rect=(0, 0.08, 1, 0.92))
    fig.savefig(OUT, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Rendered {OUT}")


if __name__ == "__main__":
    main()
