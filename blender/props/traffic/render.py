"""Stage 4: night renders (not saved into the .blend). Look at them.

  blender -b --factory-startup blender/props/traffic.blend --python blender/props/traffic/render.py -- [--quick] [--out DIR] [--only sheet|far] [--suffix S]

sheet: every vehicle at night, 3/4 front (top row) and 3/4 rear (bottom row),
       composed into traffic_sheet<suffix>.png (tiles kept as traffic_<name>_<view>.png).
far:   the five from the apartment window's point of view: eye level, 60 m out,
       88 degrees horizontal over 1920 px (one pixel ~ one headset pixel, ~4.6 cm
       at 60 m), navy night sky; plus a 3x nearest-neighbor crop (traffic_far_crop).
Works before baking too (the src_ materials render directly).
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from traffic_common import SCRATCH, VEHICLES, vehicle_object  # noqa: E402
from arcology_blender.scene import setup_gpu  # noqa: E402
from arcology_blender.studio import render_options  # noqa: E402

NAVY = (0.0036, 0.0048, 0.0103)      # night navy #0B0F1A, linear
SKY_TOP = (0.02, 0.028, 0.055)
SKY_HORIZON = (0.16, 0.09, 0.16)
TILE = (720, 450)


def world(scene, color=None, horizon=None, strength=1.0):
    w = bpy.data.worlds.new("Night")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = strength
    if horizon is None:
        bg.inputs["Color"].default_value = tuple(color) + (1.0,)
        return
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = tuple(horizon) + (1.0,)
    ramp.color_ramp.elements[1].position = 0.35
    ramp.color_ramp.elements[1].color = tuple(color) + (1.0,)
    nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])


def light(name, kind, loc, look, energy, color, size=1.0):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    elif kind == "SUN":
        ld.angle = math.radians(1.0)
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


def camera(scene):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def look(cam, loc, target):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def setup_render(scene, w, h, samples):
    setup_gpu(scene)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPTIX"
    except TypeError:
        pass
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"


def render(scene, path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


def read_png(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)


def write_png(path, rgba):
    h, w = rgba.shape[:2]
    img = bpy.data.images.new("compose", w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(rgba, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    print("WROTE", path)


def place(objs, transforms):
    for ob, (loc, yaw) in zip(objs, transforms):
        ob.location = loc
        ob.rotation_euler = (0.0, 0.0, math.radians(yaw))
    bpy.context.view_layer.update()


def sheet(scene, opt):
    objs = [vehicle_object(v) for v in VEHICLES]
    world(scene, SKY_TOP, SKY_HORIZON, 1.0)
    light("Moon", "SUN", (0, 0, 10), (-3, 4, 0), 0.35, (0.62, 0.72, 1.0))
    light("CityKey", "AREA", (9, -6, 7), (0, 0, 0), 6000.0, (0.70, 0.82, 1.0), 6.0)
    light("NeonRim", "AREA", (-8, 7, 3), (0, 0, 0), 3500.0, (1.0, 0.25, 0.55), 5.0)
    light("Under", "AREA", (0, 0, -6), (0, 0, 0), 800.0, (0.3, 0.8, 1.0), 6.0)
    cam = camera(scene)
    cam.data.lens = 50.0
    setup_render(scene, TILE[0], TILE[1], opt.samples)
    tiles = {}
    for ob, v in zip(objs, VEHICLES):
        for other in objs:
            other.hide_render = other is not ob
        place([ob], [((0, 0, 0), 0.0)])
        r = max(ob.dimensions) * 0.5
        dist = r / math.tan(math.atan(36.0 / 2 / 50.0)) * 1.05
        for view, d in (("front", Vector((0.62, 0.70, 0.30))), ("rear", Vector((-0.66, -0.68, 0.26)))):
            look(cam, d.normalized() * dist, (0, 0, -0.05 * r))
            path = os.path.join(opt.out, f"traffic_{v}_{view}{opt.suffix}.png")
            render(scene, path)
            tiles[(v, view)] = read_png(path)
    rows = []
    for view in ("rear", "front"):  # image row 0 is the bottom
        rows.append(np.concatenate([tiles[(v, view)] for v in VEHICLES], axis=1))
    write_png(os.path.join(opt.out, f"traffic_sheet{opt.suffix}.png"), np.concatenate(rows, axis=0))
    for ob in objs:
        ob.hide_render = False


def far(scene, opt):
    objs = [vehicle_object(v) for v in VEHICLES]
    # Lanes cross the view (side-on), a few turned toward or away from the window.
    place(objs, [((-27.0, 62.0, 0.0), 90.0), ((-13.0, 58.0, 0.0), -60.0), ((0.0, 66.0, 0.6), -90.0),
                 ((12.0, 57.0, -0.4), 135.0), ((27.0, 64.0, 0.3), 90.0)])
    world(scene, NAVY, None, 1.0)
    light("Moon", "SUN", (0, 0, 10), (-3, 4, 0), 0.25, (0.62, 0.72, 1.0))
    light("CityGlow", "AREA", (0, 30, 60), (0, 60, 0), 60000.0, (0.55, 0.65, 1.0), 40.0)
    cam = camera(scene)
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(88.0)
    look(cam, (0, 0, 0), (0, 60, 0))
    setup_render(scene, 1920, 1080, opt.samples)
    path = os.path.join(opt.out, f"traffic_far{opt.suffix}.png")
    render(scene, path)
    img = read_png(path)
    h, w = img.shape[:2]
    crop = img[h // 2 - 110:h // 2 + 110, w // 2 - 600:w // 2 + 600]
    crop = np.repeat(np.repeat(crop, 3, axis=0), 3, axis=1)
    write_png(os.path.join(opt.out, f"traffic_far_crop{opt.suffix}.png"), crop)


def main():
    opt = render_options(SCRATCH, samples=96, quick_samples=24)
    scene = bpy.context.scene
    only = opt.value("--only")
    if only in (None, "sheet"):
        sheet(scene, opt)
    if only in (None, "far"):
        for ob in scene.objects:
            if ob.type == "LIGHT" or ob.type == "CAMERA":
                bpy.data.objects.remove(ob)
        far(scene, opt)


if __name__ == "__main__":
    main()
