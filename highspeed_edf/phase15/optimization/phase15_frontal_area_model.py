"""Frontal-area model with the corrected assumptions.

Corrections applied (from review):
  1. The two EDF ducts are NOT coaxial. They sit side by side, so both duct
     envelopes appear in the front silhouette.
  2. The duct bore is a PASS-THROUGH (a hole), not solid frontal area. Only the
     duct wall annulus, the hub seen through the mouth, and structure count.
  3. Wings, tail, fins, control surfaces, and landing gear contribute frontal
     area.

Method: rasterize the front-view silhouette on a 1 mm grid, mark solid regions
(body, duct walls, hubs, wing, tail, fins, gear), subtract the intake
through-flow holes, and count solid pixels. This handles unions and overlaps
exactly, unlike the earlier "max(fan_disk, body)" union approximation.

Units are millimetres internally. This is a geometry screen, not measured drag.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


PHASE = Path(__file__).resolve().parents[1]
RESULTS = PHASE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

GAP_MM = 6.0            # gap between the two side-by-side ducts
WALL_MM = 2.0           # duct wall thickness
BODY_MARGIN_MM = 10.0   # body shell around the duct pair
BODY_TOP_MM = 6.0       # trimmed to match the spec body outline 186x78 mm (was 24, giving 104 mm tall)
WING_SPAN_MM = 520.0
WING_THICK_MM = 30.0   # spec wing thickness 22-30-36 mm (was 15, which under-counted the wing strip)
# No horizontal tail exists (tailless, two canted fins only); TAIL_* constants removed.
FIN_THICK_MM = 8.0
FIN_H_MM = 70.0
GEAR_W_MM = 20.0
GEAR_H_MM = 40.0
LEG_X_MM = 60.0         # lateral offset of the landing-gear struts
CONTROL_W_MM = 200.0    # combined elevon/vane projected strip
CONTROL_THICK_MM = 10.0


def silhouette_area_cm2(duct_od_mm: float, hub_mm: float, coaxial: bool, with_wings: bool, inlet: str = "front") -> dict:
    duct_count = 1 if coaxial else 2
    half_w = 420.0
    half_h = 220.0
    step = 1.0
    nx = int(2 * half_w / step)
    ny = int(2 * half_h / step)
    solid = bytearray(nx * ny)

    def mark(x0, x1, y0, y1, value):
        ix0 = max(0, int((x0 + half_w) / step))
        ix1 = min(nx, int((x1 + half_w) / step) + 1)
        iy0 = max(0, int((y0 + half_h) / step))
        iy1 = min(ny, int((y1 + half_h) / step) + 1)
        for ix in range(ix0, ix1):
            base = ix * ny
            for iy in range(iy0, iy1):
                solid[base + iy] = value

    def mark_circle(cx, cy, radius, value):
        x0, x1 = cx - radius, cx + radius
        y0, y1 = cy - radius, cy + radius
        ix0 = max(0, int((x0 + half_w) / step))
        ix1 = min(nx, int((x1 + half_w) / step) + 1)
        iy0 = max(0, int((y0 + half_h) / step))
        iy1 = min(ny, int((y1 + half_h) / step) + 1)
        r2 = radius * radius
        for ix in range(ix0, ix1):
            x = ix * step - half_w + step / 2.0
            base = ix * ny
            for iy in range(iy0, iy1):
                y = iy * step - half_h + step / 2.0
                if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                    solid[base + iy] = value

    # Duct centres: side by side, not coaxial.
    centre_offset = 0.0 if coaxial else (duct_od_mm + GAP_MM) / 2.0
    centres = [(0.0, 0.0)] if coaxial else [(-centre_offset, 0.0), (centre_offset, 0.0)]

    # 1. Body block enclosing the duct(s) plus shell margin, and battery bay.
    if coaxial:
        body_half_w = duct_od_mm / 2.0 + BODY_MARGIN_MM
    else:
        body_half_w = centre_offset + duct_od_mm / 2.0 + BODY_MARGIN_MM
    body_half_h = duct_od_mm / 2.0 + BODY_TOP_MM / 2.0
    mark(-body_half_w, body_half_w, -body_half_h, body_half_h, 1)

    # 3. Front-facing inlets are through-flow holes; side inlets are not in the
    # front silhouette at all.
    if inlet == "front":
        for cx, cy in centres:
            mark_circle(cx, cy, (duct_od_mm - 2.0 * WALL_MM) / 2.0, 0)

    # 4. Hubs are visible through a front inlet only.
    if inlet == "front":
        for cx, cy in centres:
            mark_circle(cx, cy, hub_mm / 2.0, 1)

    # 5. Wings, tail, thin fins, gear. Control surfaces are part of the wing/tail.
    if with_wings:
        mark(-WING_SPAN_MM / 2.0, WING_SPAN_MM / 2.0, -WING_THICK_MM / 2.0, WING_THICK_MM / 2.0, 1)
        mark(-body_half_w - FIN_THICK_MM, -body_half_w, -FIN_H_MM / 2.0, FIN_H_MM / 2.0, 1)
        mark(body_half_w, body_half_w + FIN_THICK_MM, -FIN_H_MM / 2.0, FIN_H_MM / 2.0, 1)
        mark(-LEG_X_MM - GEAR_W_MM / 2.0, -LEG_X_MM + GEAR_W_MM / 2.0, -body_half_h - GEAR_H_MM, -body_half_h, 1)
        mark(LEG_X_MM - GEAR_W_MM / 2.0, LEG_X_MM + GEAR_W_MM / 2.0, -body_half_h - GEAR_H_MM, -body_half_h, 1)

    solid_cells = sum(solid)
    area_cm2 = solid_cells * (step * step) / 100.0

    # Decomposition for interpretation.
    hub_area = len(centres) * math.pi * (hub_mm / 20.0) ** 2
    hole_area = len(centres) * math.pi * ((duct_od_mm - 2.0 * WALL_MM) / 20.0) ** 2
    wing_area = (WING_SPAN_MM * WING_THICK_MM) / 100.0 if with_wings else 0.0
    body_outline = (2 * body_half_w) * (2 * body_half_h) / 100.0
    return {
        "duct_od_mm": duct_od_mm,
        "hub_mm": hub_mm,
        "layout": "coaxial" if coaxial else "side_by_side",
        "inlet": inlet,
        "wings_included": with_wings,
        "body_outline_cm2": round(body_outline, 2),
        "intake_hole_cm2": round(hole_area, 2) if inlet == "front" else 0.0,
        "hub_cm2": round(hub_area, 2) if inlet == "front" else 0.0,
        "wing_strip_cm2": round(wing_area, 2),
        "total_frontal_solid_cm2": round(area_cm2, 2),
    }


def main() -> None:
    rows = []
    for od in (70, 80, 90):
        for hub in (32, 40):
            for coaxial in (False, True):
                for wings in (True, False):
                    for inlet in ("front", "side"):
                        rows.append(silhouette_area_cm2(od, hub, coaxial, wings, inlet))

    # Reference: the 90 mm side-by-side, wings, 32 mm hub, side-inlet case.
    reference = next(
        r for r in rows
        if r["duct_od_mm"] == 90 and r["hub_mm"] == 32 and r["layout"] == "side_by_side"
        and r["wings_included"] and r["inlet"] == "side"
    )
    for row in rows:
        row["cda_ratio_vs_90mm_reference"] = round(row["total_frontal_solid_cm2"] / reference["total_frontal_solid_cm2"], 4)
        row["estimated_cda_m2_at_constant_cd"] = round(0.0009 * row["cda_ratio_vs_90mm_reference"], 7)

    with (RESULTS / "phase15_frontal_area_model.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "method": "1 mm raster silhouette; passthrough bores subtracted; hubs added; wings/tail/fins/gear/controls included",
        "corrections": [
            "ducts are side by side, not coaxial",
            "duct bore is a passthrough hole, not solid frontal area",
            "wings, tail, fins, landing gear and control surfaces contribute area",
        ],
        "referenceCase": reference,
        "fanSolidContributionCm2": {
            "note": "duct wall is inside the body outline; only hubs plus the bore-hole subtraction involve the fan",
            "two_hub_cm2": round(2 * math.pi * (40 / 20.0) ** 2, 2),
            "two_bore_hole_cm2": round(2 * math.pi * ((80 - 4) / 20.0) ** 2, 2),
        },
        "cases": rows,
    }
    (RESULTS / "phase15_frontal_area_model.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["referenceCase"], indent=2))
    print("fanSolidContributionCm2", json.dumps(summary["fanSolidContributionCm2"], indent=2))
    for row in rows:
        if row["hub_mm"] == 40 and row["layout"] == "side_by_side":
            print(row["duct_od_mm"], row["inlet"], "wings" if row["wings_included"] else "no-wings",
                  "-> frontal", row["total_frontal_solid_cm2"], "cm2; CdA", row["estimated_cda_m2_at_constant_cd"])
    assert all(row["total_frontal_solid_cm2"] > 0 for row in rows)


if __name__ == "__main__":
    main()
