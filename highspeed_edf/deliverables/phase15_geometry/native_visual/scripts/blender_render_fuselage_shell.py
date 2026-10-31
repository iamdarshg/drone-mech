"""Blender-side opaque renders of the repaired native fuselage STEP mesh."""
import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Vector


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
parser = argparse.ArgumentParser()
parser.add_argument("--mesh", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args(argv)

args.output_dir.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=str(args.mesh), forward_axis="Y", up_axis="Z")
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = 32
scene.render.resolution_x = 1600
scene.render.resolution_y = 1100
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"
scene.world = bpy.data.worlds.new("Neutral CAD review background")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.91, 0.94, 0.97, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.65

solid_palette = [
    (0.34, 0.43, 0.52, 1),
    (0.08, 0.42, 0.66, 1),
    (0.84, 0.40, 0.12, 1),
    (0.12, 0.56, 0.42, 1),
]
mesh_objects = [obj for obj in scene.objects if obj.type == "MESH"]
for obj in mesh_objects:
    group = obj.name.split(".")[0]
    try:
        solid_index = int(group.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        solid_index = 0
    color = solid_palette[solid_index % len(solid_palette)]
    material = bpy.data.materials.new(f"Opaque shell solid {solid_index}")
    material.diffuse_color = color
    material.use_nodes = True
    material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
    material.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.4
    obj.data.materials.clear()
    obj.data.materials.append(material)

def area(name, location, power, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power
    data.shape = "DISK"
    data.size = size
    lamp = bpy.data.objects.new(name, data)
    scene.collection.objects.link(lamp)
    lamp.location = location
    lamp.rotation_euler = (Vector((0, 0, -40)) - lamp.location).to_track_quat("-Z", "Y").to_euler()

area("Key", (450, 700, 300), 2600, 700)
area("Fill", (-500, 250, -450), 1500, 800)
area("Rim", (100, -500, 400), 1100, 600)
camera_data = bpy.data.cameras.new("CAD review camera")
camera = bpy.data.objects.new("CAD review camera", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
camera_data.type = "ORTHO"
camera_data.clip_start = 0.1
camera_data.clip_end = 10000

target = Vector((0, 0, -40))
def render(filename, direction, up_axis, scale):
    camera.location = target + Vector(direction).normalized() * 1800
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", up_axis).to_euler()
    camera_data.ortho_scale = scale
    scene.render.filepath = str(args.output_dir / filename)
    bpy.ops.render.render(write_still=True)

render("01_shell_isometric.png", (1, 1, 1), "Z", 1100)
render("02_shell_side.png", (1, 0, 0), "Z", 1100)
render("03_shell_top.png", (0, 1, 0), "Z", 1100)
print(f"Rendered three opaque views from {len(mesh_objects)} mesh object(s).", flush=True)
