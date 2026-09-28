"""Neutral studio setup and still renders for thumbnails (never saved into the .blend)."""

import bpy
from mathutils import Vector

from .scene import setup_gpu


def _look_at(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def studio(scene, camera=(2.05, -2.55, 1.45), target=(0.0, -0.1, 0.92), lens=40.0,
           key=900.0, fill=350.0, rim=500.0):
    """Camera, three area lights, a gray floor and backdrop, dim world.

    The defaults frame a ~2 m tall appliance at the origin from the front-right.
    """
    setup_gpu(scene)
    coll = bpy.data.collections.new("Studio")
    scene.collection.children.link(coll)

    cam = bpy.data.objects.new("StudioCam", bpy.data.cameras.new("StudioCam"))
    cam.data.lens = lens
    coll.objects.link(cam)
    cam.location = Vector(camera)
    _look_at(cam, target)
    scene.camera = cam

    def area(name, loc, look, size, energy, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        coll.objects.link(ob)
        ob.location = loc
        _look_at(ob, look)

    area("Key", (2.5, -3.0, 3.0), (0, 0, 1.0), 2.5, key)
    area("Fill", (-3.0, -2.5, 1.8), (0, 0, 1.0), 3.0, fill, (0.9, 0.95, 1.0))
    area("Rim", (-1.5, 3.0, 2.8), (0, 0, 1.2), 2.0, rim)

    fm = bpy.data.materials.new("StudioFloorMat")
    fm.use_nodes = True
    b = fm.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.22, 0.22, 0.23, 1)
    b.inputs["Roughness"].default_value = 0.6
    for name, verts in (("StudioFloor", [(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)]),
                        ("StudioBack", [(-6, 1.5, 0), (6, 1.5, 0), (6, 1.5, 6), (-6, 1.5, 6)])):
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], [(0, 1, 2, 3)])
        me.materials.append(fm)
        coll.objects.link(bpy.data.objects.new(name, me))

    world = scene.world or bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.18, 0.19, 0.21, 1)
    bg.inputs["Strength"].default_value = 0.5
    return cam


def render_still(scene, path, samples=64, size=1024):
    """Cycles still (OptiX denoised, AgX) written to `path` as PNG."""
    scene.render.resolution_x = size
    scene.render.resolution_y = size
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
