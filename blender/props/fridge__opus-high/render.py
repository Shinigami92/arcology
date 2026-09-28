"""Studio thumbnails of the fridge (variant opus-high). Does not save the .blend.

blender --background blender/props/fridge__opus-high.blend --python render.py -- OUT_DIR [--view NAME] [--samples N]
Views: closed, open (default: both), plus debug views: front, inside, doorin, handle.
"""
import bpy, math, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec as S

ARGV = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGV[0]
VIEWS = [ARGV[ARGV.index("--view") + 1]] if "--view" in ARGV else ["closed", "open"]
SAMPLES = int(ARGV[ARGV.index("--samples") + 1]) if "--samples" in ARGV else 64
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene

# --- studio
import bmesh
bm = bmesh.new()
prof = [(-5.0, 0.0)] + [(1.2 + 1.0 * math.sin(a), 1.0 - 1.0 * math.cos(a))
                        for a in [i * math.pi / 2 / 12 for i in range(13)]] + [(2.2, 4.0)]
row = []
for y, z in prof:
    row.append((bm.verts.new((-6, y, z)), bm.verts.new((6, y, z))))
for (a0, a1), (b0, b1) in zip(row, row[1:]):
    bm.faces.new((a0, a1, b1, b0))
me = bpy.data.meshes.new("studio")
bm.to_mesh(me)
for p in me.polygons:
    p.use_smooth = True
studio = bpy.data.objects.new("studio", me)
scene.collection.objects.link(studio)
sm = bpy.data.materials.new("studio")
p = sm.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.30, 0.30, 0.31, 1)
p.inputs["Roughness"].default_value = 0.7
me.materials.append(sm)


def area(name, loc, target, size, power, sx=None, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size = size
    ld.size_y = sx or size
    ld.energy = power
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


area("key", (-2.2, -2.8, 3.0), (0, 0, 0.9), 2.5, 900, color=(1.0, 0.97, 0.93))
area("fill", (3.0, -2.2, 1.4), (0, 0, 0.9), 3.0, 320, color=(0.93, 0.96, 1.0))
area("rim", (1.2, 2.2, 3.4), (0, 0, 1.0), 2.0, 380)
if scene.world is None:
    scene.world = bpy.data.worlds.new("World")
w = scene.world
bg = w.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.06, 0.06, 0.065, 1)
bg.inputs["Strength"].default_value = 1.0

cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam

CAMS = {
    "closed": ((1.75, -3.05, 1.30), (-0.03, -0.20, 0.90), 42),
    "open": ((1.75, -3.05, 1.30), (-0.03, -0.20, 0.90), 42),
    "front": ((0.0, -2.2, 1.2), (0.0, -0.3, 1.15), 50),
    "inside": ((0.25, -1.3, 1.25), (0.0, 0.0, 0.85), 30),
    "doorin": ((0.9, -1.2, 1.1), (-0.30, -0.70, 0.95), 32),
    "handle": ((0.55, -0.95, 1.35), (0.20, -0.39, 1.20), 50),
    "low": ((0.9, -1.2, 0.35), (0.0, -0.3, 0.12), 35),
}

# interior bulb for the open view (render only; in Godot use an OmniLight/SpotLight when the door opens)
bulb_d = bpy.data.lights.new("fridge_bulb", "AREA")
bulb_d.shape = "RECTANGLE"
bulb_d.size, bulb_d.size_y = 0.28, 0.08
bulb_d.energy = 2.5
bulb_d.color = (1.0, 0.965, 0.92)
bulb = bpy.data.objects.new("fridge_bulb", bulb_d)
scene.collection.objects.link(bulb)
bulb.location = (0, -0.21, S.CAV_Z1 - 0.012)
strips = []
for sx in (-1, 1):
    ld = bpy.data.lights.new("strip", "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = 1.35, 0.02
    ld.energy = 3
    ld.color = (1.0, 0.965, 0.92)
    ob = bpy.data.objects.new("strip", ld)
    scene.collection.objects.link(ob)
    ob.location = (sx * (S.CAV_X - 0.006), -0.291, 1.055)
    ob.rotation_euler = (0, math.radians(90 * sx), 0)
    strips.append(ob)

scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU"
except Exception:
    pass
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
for ob in bpy.data.collections["Collision"].objects:
    ob.hide_render = True

door = bpy.data.objects["FridgeDoor"]
for v in VIEWS:
    loc, tgt, lens = CAMS[v]
    cam.location = loc
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam_d.lens = lens
    is_open = v in ("open", "inside", "doorin", "low")
    door.rotation_euler = (0, 0, math.radians(S.OPEN_DEG) if is_open else 0)
    bulb.hide_render = not is_open
    for s in strips:
        s.hide_render = not is_open
    scene.render.filepath = os.path.join(OUT, f"{S.TAG}_{v}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scene.render.filepath)
