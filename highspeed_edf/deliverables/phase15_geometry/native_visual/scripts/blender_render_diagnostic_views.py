"""Blender worker for render_diagnostic_views.py."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
parser = argparse.ArgumentParser()
parser.add_argument("--mesh", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
parser.add_argument("--view", choices=("05", "06", "07"))
args = parser.parse_args(argv)
args.output_dir.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=str(args.mesh), forward_axis="Y", up_axis="Z")
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = 24
scene.render.resolution_x = 1600
scene.render.resolution_y = 1100
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"
scene.world = bpy.data.worlds.new("Diagnostic CAD background")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.91, 0.94, 0.97, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.65

palette = {
    "airframe": (0.38, 0.44, 0.50, 1), "battery": (0.82, 0.18, 0.14, 1),
    "motor": (0.15, 0.18, 0.21, 1), "propulsor": (0.08, 0.34, 0.62, 1),
    "electronics": (0.04, 0.48, 0.32, 1), "actuation": (0.88, 0.42, 0.06, 1),
    "other": (0.54, 0.57, 0.60, 1),
}

def category(n):
    n = n.lower()
    if any(s in n for s in ("lifting_wing", "fuselage", "elevon", "fin", "rudder", "tail_support", "landing_skids", "joiner")): return "airframe"
    if "battery" in n or "bonka" in n: return "battery"
    if n.startswith("motor_"): return "motor"
    if any(s in n for s in ("duct_", "rotor", "stator", "vector_vane", "side_inlet", "nozzle", "containment")): return "propulsor"
    if any(s in n for s in ("esc_", "flight_control", "flight_6ch", "fc_", "isolator")): return "electronics"
    if "servo" in n or "pushrod" in n: return "actuation"
    return "other"

meshes = [o for o in scene.objects if o.type == "MESH"]
for ob in meshes:
    group = ob.name.split(".")[0]
    color = palette[category(group)]
    material = bpy.data.materials.new(group + "_diagnostic_opaque")
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = 0.12 if category(group) in ("motor", "propulsor", "electronics") else 0.0
    bsdf.inputs["Roughness"].default_value = 0.36
    ob.data.materials.clear()
    ob.data.materials.append(material)
    ob.name = group

def area(name, location, power, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.shape, data.size = power, "DISK", size
    lamp = bpy.data.objects.new(name, data)
    scene.collection.objects.link(lamp)
    lamp.location = location
    lamp.rotation_euler = (Vector((0, 0, 15)) - lamp.location).to_track_quat("-Z", "Y").to_euler()

area("Key", (500, 700, -300), 2400, 700)
area("Fill", (-600, 350, 500), 1500, 800)
area("Rim", (100, -500, -400), 1100, 600)
cam_data = bpy.data.cameras.new("Diagnostic orthographic camera")
cam_data.type, cam_data.clip_start, cam_data.clip_end = "ORTHO", 0.1, 10000
cam = bpy.data.objects.new("Diagnostic orthographic camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

def render(filename, prefixes, direction, up_axis, target, scale):
    visible = []
    for ob in meshes:
        ob.hide_render = not any(ob.name.startswith(prefix) for prefix in prefixes)
        if not ob.hide_render:
            visible.append(ob)
    world_points = [ob.matrix_world @ Vector(corner) for ob in visible for corner in ob.bound_box]
    mins = [min(p[i] for p in world_points) for i in range(3)]
    maxs = [max(p[i] for p in world_points) for i in range(3)]
    component_bounds = {}
    for ob in visible:
        points = [ob.matrix_world @ Vector(corner) for corner in ob.bound_box]
        component_bounds[ob.name] = {"min": [min(p[i] for p in points) for i in range(3)], "max": [max(p[i] for p in points) for i in range(3)]}
    auto_framed = filename.startswith("06_")
    target_v = Vector([(mins[i] + maxs[i]) / 2 for i in range(3)]) if auto_framed else Vector(target)
    direction_v = Vector(direction).normalized()
    world_up = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[up_axis]
    # Blender cameras use local +Z as the back axis. Build a proper right-handed
    # world basis: +Z(back)=viewDirection, +X(right)=up×back, +Y(up)=back×right.
    screen_right = world_up.cross(direction_v).normalized()
    screen_up = direction_v.cross(screen_right).normalized()
    quat = Matrix((screen_right, screen_up, direction_v)).transposed().to_quaternion()
    cam.location = target_v + direction_v * 1800
    cam.rotation_euler = quat.to_euler()
    if auto_framed:
        projected = [(p - target_v) for p in world_points]
        span_x = max(v.dot(screen_right) for v in projected) - min(v.dot(screen_right) for v in projected)
        span_y = max(v.dot(screen_up) for v in projected) - min(v.dot(screen_up) for v in projected)
        aspect = scene.render.resolution_x / scene.render.resolution_y
        scale = max(span_x, span_y * aspect) * 1.12
    cam_data.ortho_scale = scale
    scene.render.filepath = str(args.output_dir / filename)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {filename}; shown components={sum(not o.hide_render for o in meshes)}; direction={direction}, up_axis={up_axis}, target={target}, scale={scale}", flush=True)
    if filename.startswith("06_"):
        (args.output_dir / "diagnostic_view_bounds.json").write_text(json.dumps({
            "view": filename,
            "visibleComponents": sorted(ob.name for ob in visible),
            "componentBoundsMm": component_bounds,
            "worldBoundsMm": {"min": mins, "max": maxs},
            "autoFraming": {"targetMm": list(target_v), "orthoScaleMm": scale, "cameraDirection": list(direction_v), "worldUp": list(world_up), "screenRight": list(screen_right), "screenUp": list(screen_up), "projectionSpanMm": {"horizontal": span_x, "vertical": span_y}, "aspectRatio": aspect},
            "label": "Axial distribution: battery group (red) and avionics / cooling group (green)",
        }, indent=2) + "\n")

views = {
    "05": ("05_drive_a_side_projection.png", ["duct_A_rotor_R", "duct_A_stator_S", "motor_A_R", "six_hot_side_motor_carrier_frames"], (1, 0, 0), "Y", (-44, 0, 88), 270),
    "06": ("06_battery_electronics_side_projection.png", ["Bonka_", "battery_", "esc_", "flight_control_", "flight_6ch_", "fc_", "board_isolator_"], (1, 0, 0), "Y", (0, 42, 70), 1500),
    "07": ("07_duct_a_top_projection.png", ["duct_A_rotor_R", "duct_A_stator_S", "duct_A_vector_vane", "motor_A_", "servo_mount_vane_A"], (0, 1, 0), "Z", (-44, 0, 88), 310),
}
selected = [args.view] if args.view else list(views)
for key in selected:
    render(*views[key])
print(f"Rendered {len(selected)} targeted projections from {len(meshes)} imported component meshes; no source geometry moved.", flush=True)
