"""Stage 4: render closed/open thumbnails with a neutral studio setup (not saved).

  blender -b --factory-startup <blend> --python render.py -- [--quick] [--suffix NAME]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from fridge_common import LIGHT_MAT, SCRATCH, VARIANT, door_objects, setup_gpu  # noqa: E402


def studio(scene):
    coll = bpy.data.collections.new("Studio")
    scene.collection.children.link(coll)

    cam_data = bpy.data.cameras.new("StudioCam")
    cam_data.lens = 40.0
    cam = bpy.data.objects.new("StudioCam", cam_data)
    coll.objects.link(cam)
    cam.location = Vector((2.05, -2.55, 1.45))
    target = Vector((0.0, -0.1, 0.92))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    def area(name, loc, look, size, energy, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        coll.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return ob

    area("Key", (2.5, -3.0, 3.0), (0, 0, 1.0), 2.5, 900)
    area("Fill", (-3.0, -2.5, 1.8), (0, 0, 1.0), 3.0, 350, (0.9, 0.95, 1.0))
    area("Rim", (-1.5, 3.0, 2.8), (0, 0, 1.2), 2.0, 500)

    floor = bpy.data.meshes.new("StudioFloor")
    floor.from_pydata([(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [], [(0, 1, 2, 3)])
    fob = bpy.data.objects.new("StudioFloor", floor)
    coll.objects.link(fob)
    fm = bpy.data.materials.new("StudioFloorMat")
    fm.use_nodes = True
    b = fm.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.22, 0.22, 0.23, 1)
    b.inputs["Roughness"].default_value = 0.6
    floor.materials.append(fm)

    back = bpy.data.meshes.new("StudioBack")
    back.from_pydata([(-6, 1.5, 0), (6, 1.5, 0), (6, 1.5, 6), (-6, 1.5, 6)], [], [(0, 1, 2, 3)])
    bob = bpy.data.objects.new("StudioBack", back)
    coll.objects.link(bob)
    back.materials.append(fm)

    world = scene.world or bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.18, 0.19, 0.21, 1)
    bg.inputs["Strength"].default_value = 0.5


def render(scene, path, samples):
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPTIX"
    except TypeError:
        pass
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    scene.view_settings.view_transform = "AgX"
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    quick = "--quick" in argv
    suffix = argv[argv.index("--suffix") + 1] if "--suffix" in argv else ""
    samples = 16 if quick else 64

    scene = bpy.context.scene
    setup_gpu(scene)
    studio(scene)
    os.makedirs(SCRATCH, exist_ok=True)

    door = bpy.data.objects["Door"]
    light = bpy.data.materials.get(LIGHT_MAT)
    strength = light.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for ob in door_objects():
        ob.hide_render = False

    # Closed: interior light off
    door.rotation_euler = (0, 0, 0)
    saved = strength.default_value
    strength.default_value = 0.0
    render(scene, os.path.join(SCRATCH, f"{VARIANT}_closed{suffix}.png"), samples)

    # Open 100 degrees, light on
    door.rotation_euler = (0, 0, math.radians(-100.0))
    strength.default_value = 25.0
    render(scene, os.path.join(SCRATCH, f"{VARIANT}_open{suffix}.png"), samples)
    strength.default_value = saved
    door.rotation_euler = (0, 0, 0)


if __name__ == "__main__":
    main()
