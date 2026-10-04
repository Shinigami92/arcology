"""Stage 4: thumbnails (not saved into the .blend).

  blender -b --factory-startup blender/architecture/city_brutalist.blend --python blender/architecture/city/brutalist/render.py -- [--quick] [--out DIR] [--suffix S] [--thumbs-only] [--night-only] [--roof]

- <tower>_thumb.png: each tower alone at dusk, seen from the apartment's side
  (3/4 from the eye direction), so the concrete reads next to the lit windows.
- night_eye.png (+ night_eye_left/right.png): the night view from the
  apartment eye (Godot (0, 1.6, -3), looking -Z, 90 degrees horizontal), the
  five towers placed per tools/city/near_towers.json, dark navy sky, distance
  fog and a denser street haze (absorption + emission volumes: noise-free).
- --roof: deck_roof.png, a 30 degree crop from the eye onto the deck's roof.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

from brutalist_common import SCRATCH, eye_blender, load_spec, tower_objects, towers  # noqa: E402
from arcology_blender.scene import setup_gpu  # noqa: E402
from arcology_blender.studio import render_options  # noqa: E402

NAVY = (0.0033, 0.0048, 0.0100)       # #0B0F1A
SMOG = (0.0118, 0.0232, 0.0423)       # #1C2A3A
HORIZON = (0.034, 0.042, 0.062)       # city glow near the horizon


def world(scene, zenith, horizon, strength=1.0, fog=0.0, fog_color=SMOG):
    w = bpy.data.worlds.new("CityWorld")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.05
    mr.inputs["From Max"].default_value = 0.45
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*horizon, 1)
    mix.inputs["B"].default_value = (*zenith, 1)
    nt.links.new(mr.outputs["Result"], mix.inputs["Factor"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    nt.links.new(mix.outputs["Result"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    if fog > 0:
        nt.links.new(fog_volume(nt, fog, fog_color), out.inputs["Volume"])


def fog_volume(nt, density, color):
    """Homogeneous absorption + emission (no scattering): fog that tends to `color`."""
    ab = nt.nodes.new("ShaderNodeVolumeAbsorption")
    ab.inputs["Color"].default_value = (0, 0, 0, 1)
    ab.inputs["Density"].default_value = density
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = density
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(ab.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    return add.outputs[0]


def haze_box(name, z0, z1, density, color, size=3000.0):
    me = bpy.data.meshes.new(name)
    s = size / 2
    v = [(-s, -s, z0), (s, -s, z0), (s, s, z0), (-s, s, z0), (-s, -s, z1), (s, -s, z1), (s, s, z1), (-s, s, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(fog_volume(nt, density, color), out.inputs["Volume"])
    me.materials.append(m)
    return ob


def sun(name, rot_deg, energy, color):
    ld = bpy.data.lights.new(name, "SUN")
    ld.energy = energy
    ld.color = color
    ld.angle = math.radians(2.0)
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = Euler([math.radians(a) for a in rot_deg])
    return ob


def camera(name, loc, look, lens=None, hfov=None):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(look) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.sensor_fit = "HORIZONTAL"
    if hfov:
        cam.data.angle = math.radians(hfov)
    elif lens:
        cam.data.lens = lens
    cam.data.clip_end = 5000.0
    cam.data.clip_start = 0.5
    return cam


def render(scene, cam, path, samples, w, h, exposure=0.0):
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPTIX"
    except TypeError:
        pass
    scene.cycles.max_bounces = 4
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = exposure
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


def place(t, at_origin=False):
    for ob in tower_objects(t["name"]):
        if at_origin:
            ob.location = (0, 0, 0)
            ob.rotation_euler = (0, 0, 0)
        else:
            x, z = t["pos"]
            ob.location = (x, -z, -180.0)
            ob.rotation_euler = (0, 0, math.radians(t["yaw"]))


def eye_dir_local(t, spec):
    """Horizontal unit vector from the tower toward the eye, in the tower's local frame."""
    ex, ey, ez = spec["eye"]
    x, z = t["pos"]
    d = Vector((ex - x, -(ez - z), 0)).normalized()  # Blender world
    return Euler((0, 0, -math.radians(t["yaw"]))).to_matrix() @ d


def thumbs(scene, opt, spec):
    ts = towers(spec)
    world(scene, (0.020, 0.028, 0.045), (0.075, 0.07, 0.075), strength=1.0)
    sn = sun("Dusk", (62, 0, -35), 1.6, (1.0, 0.82, 0.68))
    for t in ts:
        for o in [o for tt in ts for o in tower_objects(tt["name"])]:
            o.hide_render = tt_name(o) != t["name"]
        place(t, at_origin=True)
        d = eye_dir_local(t, spec)
        a = math.atan2(d.x, -d.y)                       # 0 = straight at the front
        a += math.copysign(math.radians(25.0), a)       # 3/4: further toward the side the apartment sees
        cdir = Vector((math.sin(a), -math.cos(a), 0.0))
        hgt = t["height"] + 20.0
        dist = max(hgt, t["W"] * 1.3) * 1.55
        loc = Vector((0, 0, hgt * 0.63)) + cdir * dist
        cam = camera("ThumbCam", loc, (0, 0, hgt * 0.47), lens=50.0)
        sn.rotation_euler = Euler((math.radians(58), 0, a - math.radians(35) * math.copysign(1, a)))
        render(scene, cam, os.path.join(opt.out, f"{t['name']}_thumb{opt.suffix}.png"), opt.samples, 1024, 1024,
               exposure=0.0)
        bpy.data.objects.remove(cam)
    for o in [o for tt in ts for o in tower_objects(tt["name"])]:
        o.hide_render = False


def tt_name(o):
    from arcology_blender.scene import PART_KEY
    return o.get(PART_KEY)


def night(scene, opt, spec, roof=False):
    ts = towers(spec)
    for t in ts:
        place(t)
    world(scene, NAVY, HORIZON, strength=1.0, fog=0.0018, fog_color=SMOG)
    haze_box("StreetHaze", -400.0, -150.0, 0.012, (0.010, 0.018, 0.032))
    haze_box("LowHaze", -150.0, -110.0, 0.005, (0.010, 0.018, 0.032))
    sun("Moon", (55, 0, 150), 0.04, (0.75, 0.85, 1.0))
    sun("StreetGlow", (200, 0, 30), 0.05, (1.0, 0.62, 0.35))  # light from the streets below (verification only)
    eye = eye_blender(spec)
    if roof:
        t = [t for t in ts if t["name"] == "city_brutal_deck"][0]
        x, z = t["pos"]
        cam = camera("RoofCam", eye, (x, -z, -35.0), hfov=34.0)
        render(scene, cam, os.path.join(opt.out, f"deck_roof{opt.suffix}.png"), opt.samples * 2, 1600, 1000)
        return
    for name, yaw in (("night_eye", 0.0), ("night_eye_left", 42.0), ("night_eye_right", -42.0)):
        a = math.radians(yaw)
        look = Vector(eye) + Vector((-math.sin(a), math.cos(a), 0.0)) * 100.0
        cam = camera("EyeCam", eye, look, hfov=90.0)
        render(scene, cam, os.path.join(opt.out, f"{name}{opt.suffix}.png"), opt.samples * 2, 1920, 1080)
        bpy.data.objects.remove(cam)
        if opt.has("--front-only"):
            break


def main():
    opt = render_options(os.path.join(SCRATCH))
    spec = load_spec()
    scene = bpy.context.scene
    setup_gpu(scene)
    if opt.has("--roof"):
        night(scene, opt, spec, roof=True)
        return
    if not opt.has("--night-only"):
        thumbs(scene, opt, spec)
    if not opt.has("--thumbs-only"):
        for ob in [o for o in bpy.data.objects if o.type == "LIGHT"]:
            bpy.data.objects.remove(ob)
        night(scene, opt, spec)


if __name__ == "__main__":
    main()
