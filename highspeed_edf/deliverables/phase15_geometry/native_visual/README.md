# Phase-15 native CAD visual evidence

These four review images were rendered from the native `phase15_airframe_full_assembly.step` B-rep assembly pinned below. CadQuery/OpenCascade tessellates the imported STEP assembly to a temporary named OBJ; Blender 4.3.2 Eevee Next renders that mesh. The temporary OBJ is removed after rendering and is not part of this commit. The PNG overlays add titles and state the visibility treatment; they do not alter or displace geometry.

## Reproduce

Run from the repository root with Python that has CadQuery and Pillow installed, plus Blender 4.3 or newer on `PATH`:

```sh
python3 highspeed_edf/deliverables/phase15_geometry/native_visual/scripts/render_native_views.py \
  --step highspeed_edf/deliverables/phase15_geometry/step/phase15_airframe_full_assembly.step \
  --output-dir highspeed_edf/deliverables/phase15_geometry/native_visual/images \
  --blender /usr/bin/blender
```

The default source hash is pinned and checked before import. To render a deliberately different STEP, pass `--allow-unpinned-step`; the generated `render_manifest.json` records its actual hash. The script records its source hash, renderer version, tessellation settings, view visibility, and PNG hashes in the manifest.

## What each image includes

| Image | View and visibility |
|---|---|
| `01_exterior_isometric.png` | Isometric assembly view. All 73 named STEP components are included, opaque, and in their STEP placements. |
| `02_plan_packaging_hidden_skins.png` | Plan view looking from +Y. Hides only the three wing-sector parts and `fuselage_battery_bay_shell`; all remaining STEP components are opaque and unmoved. |
| `03_nose_projection.png` | Nose projection looking along −Z. All 73 named STEP components are included, opaque, and in their STEP placements. |
| `04_motor_envelopes_only.png` | Plan/detail view of the six `motor_*` envelope components only. Every other STEP component is hidden; motor components are unmoved and opaque. The footer records their native STEP axial spans. |

Visualization colors identify groups only: gray airframe, blue duct/fan, red battery, charcoal motors, green electronics/spreaders, orange actuation. They are not STEP material assignments. Opaque shading is used for all model parts in every image; no transparency or exploded placement is used.

## Source and render provenance

- Geometry source commit: `6b07330c9d77193e0c37a87994838a0edba0ac82` (`main` at render time).
- Native assembly: `highspeed_edf/deliverables/phase15_geometry/step/phase15_airframe_full_assembly.step`.
- Assembly SHA256: `9b83f3bfa5ea261c2055152c9fdd2147b9e16819634715c3c4ae23b45deae772`.
- Geometry generator: `highspeed_edf/phase15/optimization/phase15_generate_geometry.py`.
- Generator SHA256: `86275054adf53b862dd91bfb3a66b84da3470e8ea400af8e57d5e339ef124caf`.
- Render runtime used here: Python 3.12.14, CadQuery 2.7.0, OpenCascade 7.8.1.1, Pillow 12.3.0, Blender 4.3.2 Eevee Next; 1600×1100 pixels, 24 Eevee samples. STEP tessellation used 1.4 mm linear and 0.55 rad angular tolerance.
- Import produced 73 named assembly components, 516 solids, and 61,534 triangles in the temporary render mesh.

## Visual observations and limits

The native STEP motor envelopes are centered at each EDF rotor station. Per duct, the component Z spans are R1 `12..92 mm`, R2 `48..128 mm`, and R3 `84..164 mm`; adjacent spans share 36 mm. The same placements occur on both ducts. These envelope placements are directly visible in the motor-only view and are also recorded as an incompatibility in `reports/phase15_geometry_manufacturing_report.md`, item 3. This is a CAD envelope observation; the render does not analyze a sourced motor, bearings, shafting, mount stiffness, or a revised drive layout.

The nose and plan views show the two central duct/fan paths, side support/landing features, battery envelopes, and the elevated aft electronics/spreader geometry. A projection does not establish structural support, service access, cooling flow, connector access, or clearance under load. In particular, the source manufacturing report notes that board locations are outside the 88 mm body section and depend on an open-ended dorsal cooling tunnel; cooling flow remains unresolved there.

The source project rules in `highspeed_edf/AGENTS.md` explicitly prohibit treating screenshots or exported CAD as geometry validation, flight readiness, or promotion evidence. These images establish only what the pinned STEP solids look like in the stated views. They provide no CFD, structural, thermal, aeroelastic, fatigue, vibration, control-authority, manufacturing, or flight evidence.
