"""Render imported Phase-15 motor envelopes from native STEP tessellation.

This is a geometry inspection view, not a physical supplier verification or
manufacturing/flight release. Run from repository root:
  python highspeed_edf/deliverables/phase15_geometry/reports/render_native_motor_views.py
"""
from pathlib import Path
import cadquery as cq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
STEP = ROOT / "step"
OUT = ROOT / "reports" / "native_views"
OUT.mkdir(parents=True, exist_ok=True)
COLORS = {"A": "#168aad", "B": "#e76f51"}


def load_meshes():
    items = []
    for path in sorted(STEP.glob("motor_*_3670_*_envelope.step")):
        shape = cq.importers.importStep(str(path)).val().Solids()[0]
        pts, tris = shape.tessellate(0.3, 0.2)
        vertices = [[(pts[i].x, pts[i].y, pts[i].z) for i in tri] for tri in tris]
        bb = shape.BoundingBox()
        items.append({"name": path.stem, "duct": path.name.split("_")[1],
                      "z0": bb.zmin, "z1": bb.zmax, "faces": vertices})
    if len(items) != 6:
        raise RuntimeError(f"expected 6 motor STEP solids, got {len(items)}")
    return items


def draw(items, filename, elev, azim, title, view):
    fig = plt.figure(figsize=(12, 7), facecolor="white")
    ax = fig.add_subplot(111, projection="3d")
    for item in items:
        ax.add_collection3d(Poly3DCollection(
            item["faces"], facecolor=COLORS[item["duct"]], edgecolor="#263238",
            linewidth=0.08, alpha=0.38))
    ax.set_xlim(-76, 76); ax.set_ylim(-35, 35); ax.set_zlim(0, 180)
    ax.set_xlabel("Lateral X (mm)"); ax.set_ylabel("Vertical Y (mm)"); ax.set_zlabel("Aft Z (mm)")
    ax.set_title(title, pad=18, fontsize=14, weight="bold")
    ax.view_init(elev=elev, azim=azim)
    ax.set_box_aspect((164, 70, 180))
    ax.grid(True, alpha=0.22)
    if view == "side":
        ax.yaxis.set_visible(False)
        ax.set_ylabel("")
        ax.set_yticks([])
        ax.set_xlim(-74, 74)
    ax.legend(handles=[Patch(facecolor=COLORS["A"], alpha=0.7, label="Duct A motor envelopes"),
                       Patch(facecolor=COLORS["B"], alpha=0.7, label="Duct B motor envelopes")],
              loc="upper left", frameon=False)
    fig.text(0.5, 0.025, "Imported STEP solids • 72 mm motor cans at 36 mm station pitch • adjacent cans intersect by 36 mm",
             ha="center", fontsize=9, color="#455a64")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    motor_items = load_meshes()
    draw(motor_items, "phase15_motor_envelopes_side.png", 2, -90,
         "Phase 15 motor envelope fit — side view", "side")
    draw(motor_items, "phase15_motor_envelopes_isometric.png", 20, -58,
         "Phase 15 motor envelope fit — isometric view", "iso")
    print(f"Rendered native motor STEP views to {OUT}")
