"""Blender-side rendering implementation. Invoked by render_native_views.py."""
import argparse
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def category(name):
    n = name.lower()
    if any(s in n for s in ("lifting_wing", "fuselage", "elevon", "fin", "rudder", "tail_support", "landing_skids", "joiner")):
        return "airframe"
    if "battery" in n or "bonka" in n:
        return "battery"
    if n.startswith("motor_"):
        return "motor"
    if any(s in n for s in ("duct_", "rotor", "stator", "vector_vane", "side_inlet", "nozzle", "containment")):
        return "propulsor"
    if any(s in n for s in ("esc_", "flight_control", "flight_6ch", "fc_", "isolator")):
        return "electronics"
    if "servo" in n or "pushrod" in n:
        return "actuation"
    return "other"


args = parse_args()
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
scene.render.film_transparent = False
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
scene.world = bpy.data.worlds.new("Neutral CAD review background")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.91, 0.94, 0.97, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.65

palette = {
    "airframe": (0.38, 0.44, 0.50, 1),
    "battery": (0.82, 0.18, 0.14, 1),
    "motor": (0.15, 0.18, 0.21, 1),
    "propulsor": (0.08, 0.34, 0.62, 1),
    "electronics": (0.04, 0.48, 0.32, 1),
    "actuation": (0.88, 0.42, 0.06, 1),
    "other": (0.54, 0.57, 0.60, 1),
}
for ob in scene.objects:
    if ob.type != "MESH":
        continue
    group = ob.name.split(".")[0]
    key = category(group)
    color = palette[key]
    material = bpy.data.materials.new(group + "_opaque_review")
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = 0.12 if key in ("motor", "propulsor", "electronics") else 0.0
    bsdf.inputs["Roughness"].default_value = 0.36
    ob.data.materials.clear()
    ob.data.materials.append(material)
    ob.name = group


def add_area(name, location, power, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power
    data.shape = "DISK"
    data.size = size
    lamp = bpy.data.objects.new(name, data)
    scene.collection.objects.link(lamp)
    lamp.location = location
    lamp.rotation_euler = (Vector((0, 0, 15)) - lamp.location).to_track_quat("-Z", "Y").to_euler()


add_area("Key", (500, 700, -300), 2400, 700)
add_area("Fill", (-600, 350, 500), 1500, 800)
add_area("Rim", (100, -500, -400), 1100, 600)
cam_data = bpy.data.cameras.new("Review camera")
cam = bpy.data.objects.new("Review camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.type = "ORTHO"
cam_data.clip_start = 0.1
cam_data.clip_end = 10000

HIDE_FOR_PLAN = {
    "fuselage_battery_bay_shell",
    "lifting_wing_left_sector_with_duct_and_elevon_reliefs",
    "lifting_wing_centre_bridge_sector_with_duct_and_elevon_reliefs",
    "lifting_wing_right_sector_with_duct_and_elevon_reliefs",
}


def render(filename, camera_direction, up_axis, target, scale, visible_names=None, hidden_names=None):
    for ob in scene.objects:
        if ob.type != "MESH":
            continue
        ob.hide_render = False
        if visible_names is not None:
            ob.hide_render = ob.name not in visible_names
        if hidden_names is not None and ob.name in hidden_names:
            ob.hide_render = True
    target_v = Vector(target)
    direction = Vector(camera_direction).normalized()
    cam.location = target_v + direction * 1800
    cam.rotation_euler = (target_v - cam.location).to_track_quat("-Z", up_axis).to_euler()
    cam_data.ortho_scale = scale
    scene.render.filepath = str(args.output_dir / filename)
    bpy.ops.render.render(write_still=True)


all_names = {ob.name for ob in scene.objects if ob.type == "MESH"}
motor_names = {name for name in all_names if name.startswith("motor_")}
render("01_exterior_isometric.png", (1, 1, -1), "Y", (0, 0, 15), 1550)
render("02_plan_packaging_hidden_skins.png", (0, 1, 0), "Z", (0, 0, 15), 1250, hidden_names=HIDE_FOR_PLAN)
render("03_nose_projection.png", (0, 0, -1), "Y", (0, 0, 15), 850)
render("04_motor_envelopes_only.png", (0, 1, 0), "Z", (0, 0, 88), 300, visible_names=motor_names)
print(f"Rendered 4 views from {len(all_names)} named STEP components; {len(motor_names)} motor envelope objects shown in detail.", flush=True)
