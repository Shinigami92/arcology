"""Stage 4: renders (not saved into the .blend). Look at them.

  blender -b --factory-startup blender/architecture/city_spire.blend --python blender/architecture/city/spire/render.py -- [--quick] [--out DIR] [--only studio|night] [--tower NAME]

studio: one night thumbnail per tower (dim moonlight, its emission on).
night:  the five spires placed per the JSON, seen from the apartment eye (Godot
        (0, 1.6, -3) = Blender (0, 3, 1.6)), 90 degrees horizontal, looking -Z Godot
        (+Y Blender) and tilted up 25 degrees; the brutalist towers as dark stand-in
        boxes; the skyline's sky colors and exponential fog (density 0.0016, as in
        zones/skyline/skyline.tscn) added per material from the camera distance.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from spire_common import MATERIALS, SCRATCH, load_spec, roof_height, tower_objects, towers  # noqa: E402
from arcology_blender.scene import setup_gpu  # noqa: E402
from arcology_blender.studio import render_options  # noqa: E402

SKY_TOP = (0.02, 0.028, 0.055)
SKY_HORIZON = (0.16, 0.09, 0.16)
FOG_COLOR = (0.11, 0.10, 0.16)
FOG_DENSITY = 0.0016
EYE = (0.0, 3.0, 1.6)


def sky_world(scene, strength=1.0):
    world = bpy.data.worlds.new("NightSky")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = SKY_HORIZON + (1.0,)
    ramp.color_ramp.elements[1].position = 0.35
    ramp.color_ramp.elements[1].color = SKY_TOP + (1.0,)
    mp = nt.nodes.new("ShaderNodeMapRange")
    mp.inputs["From Min"].default_value = 0.0
    mp.inputs["From Max"].default_value = 1.0
    nt.links.new(sep.outputs["Z"], mp.inputs["Value"])
    nt.links.new(mp.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength


def moon(scene, strength=0.25):
    ld = bpy.data.lights.new("Moon", "SUN")
    ld.energy = strength
    ld.color = (0.62, 0.72, 1.0)
    ld.angle = math.radians(1.0)
    ob = bpy.data.objects.new("Moon", ld)
    scene.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(55), 0.0, math.radians(-140))


def add_fog(mats):
    """Mix every material toward the fog color by 1 - exp(-density * camera distance)."""
    for m in mats:
        nt = m.node_tree
        out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
        link = out.inputs["Surface"].links[0]
        src = link.from_socket
        nt.links.remove(link)
        cam = nt.nodes.new("ShaderNodeCameraData")
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = -FOG_DENSITY
        nt.links.new(cam.outputs["View Distance"], mul.inputs[0])
        ex = nt.nodes.new("ShaderNodeMath")
        ex.operation = "EXPONENT"
        nt.links.new(mul.outputs[0], ex.inputs[0])
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        nt.links.new(ex.outputs[0], inv.inputs[1])
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = FOG_COLOR + (1.0,)
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(inv.outputs[0], mix.inputs[0])
        nt.links.new(src, mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])


def plain_mat(name, base, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = tuple(base) + (1.0,)
    b.inputs["Roughness"].default_value = 0.8
    if emission:
        b.inputs["Emission Color"].default_value = tuple(emission) + (1.0,)
        b.inputs["Emission Strength"].default_value = strength
    return m


def plane(name, size, z, mat):
    s = size / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [(0, 1, 2, 3)])
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def box(name, w, d, h, mat):
    me = bpy.data.meshes.new(name)
    x, y = w / 2, d / 2
    v = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, -y, h), (x, -y, h), (x, y, h), (-x, y, h)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def camera(scene, loc, rot_deg, fov_h=None, fov_v=None):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    cam.data.clip_start, cam.data.clip_end = 0.5, 5000.0
    if fov_h is not None:
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.angle = math.radians(fov_h)
    else:
        cam.data.sensor_fit = "VERTICAL"
        cam.data.angle = math.radians(fov_v)
    scene.camera = cam
    return cam


def render(scene, path, samples, w, h):
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    scene.view_settings.view_transform = "AgX"
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


def studio(opt, spec, only=None):
    scene = bpy.context.scene
    setup_gpu(scene)
    sky_world(scene, 1.0)
    moon(scene, 0.6)
    plane("Street", 600.0, 0.0, plain_mat("street", (0.03, 0.03, 0.035)))
    names = [t["name"] for t in towers(spec)]
    for t in towers(spec):
        if only and t["name"] != only:
            continue
        for n in names:
            for ob in tower_objects(n):
                ob.hide_render = n != t["name"]
        hmax = max((ob.matrix_world @ Vector(c)).z for ob in tower_objects(t["name"]) for c in ob.bound_box)
        dist = hmax * 1.25
        target = Vector((0.0, 0.0, hmax * 0.5))
        az = math.radians(-125.0)   # front-left: from -Y toward -X
        loc = target + Vector((math.cos(az) * dist, math.sin(az) * dist, -hmax * 0.1))
        d = (target - loc).normalized()
        cam = camera(scene, loc, (0, 0, 0), fov_v=2 * math.degrees(math.atan(0.56 * hmax / dist)))
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        render(scene, os.path.join(opt.out, f"{t['name']}_studio{opt.suffix}.png"), opt.samples, 720, 1280)
        bpy.data.objects.remove(cam, do_unlink=True)


def night(opt, spec):
    scene = bpy.context.scene
    setup_gpu(scene)
    sky_world(scene, 1.0)
    moon(scene, 0.25)
    street = plain_mat("street", (0.02, 0.02, 0.025), (1.0, 0.55, 0.2), 0.35)
    plane("Street", 4000.0, -180.0, street)
    context = plain_mat("brutalist_standin", (0.035, 0.034, 0.033), (1.0, 0.7, 0.45), 0.03)
    for t in spec["towers"]:
        x, z = t["pos"]
        loc = Vector((x, -z, spec["street_y"]))
        rot = (0.0, 0.0, math.radians(t["yaw"]))
        if t["style"] == "spire":
            for ob in tower_objects(t["name"]):
                ob.location = loc
                ob.rotation_euler = rot
        else:
            ob = box(t["name"] + "_standin", t["footprint"][0], t["footprint"][1], roof_height(t, spec), context)
            ob.location = loc
            ob.rotation_euler = rot
    add_fog([bpy.data.materials[m] for m in MATERIALS] + [street, context])
    cam = camera(scene, EYE, (90, 0, 0), fov_h=90.0)
    render(scene, os.path.join(opt.out, f"night_eye{opt.suffix}.png"), opt.samples, 1920, 1080)
    cam.rotation_euler = (math.radians(115), 0.0, 0.0)
    render(scene, os.path.join(opt.out, f"night_eye_up{opt.suffix}.png"), opt.samples, 1920, 1080)


def main():
    opt = render_options(SCRATCH, samples=96, quick_samples=24)
    spec = load_spec()
    which = opt.value("--only")
    if which in (None, "studio"):
        studio(opt, spec, opt.value("--tower"))
    if which in (None, "night"):
        if which is None:   # studio moved nothing, but reload to drop its helpers
            bpy.ops.wm.revert_mainfile()
        night(opt, spec)


if __name__ == "__main__":
    main()
