"""Stage 4: studio thumbnails, drawer closed and pulled out 0.2 m, lamp lit. Not saved.

  blender -b --factory-startup blender/props/nightstand__opus-high.blend --python blender/props/nightstand__opus-high/render.py -- [--quick] [--out DIR] [--suffix NAME] [--detail]

Works before baking too (procedural src_ materials render directly).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from nightstand_common import (  # noqa: E402
    BULB_CENTER_Z, LAMP_POS, LIGHT_MAT, SCRATCH, TAG, body_collision_objects,
)
from arcology_blender.scene import script_args  # noqa: E402
from arcology_blender.studio import render_still, studio  # noqa: E402

VIEW = dict(camera=(1.02, -1.38, 1.02), target=(0.03, 0.0, 0.45), lens=48.0)
DETAIL = dict(camera=(0.30, -0.62, 0.78), target=(0.0, -0.10, 0.50), lens=45.0)
PULL = dict(camera=(0.16, -0.52, 0.56), target=(0.0, -0.22, 0.455), lens=60.0)
SHADE = dict(camera=(0.36, -0.30, 1.22), target=(0.085, 0.045, 0.80), lens=45.0)
BULB_COLOR = (1.0, 0.40, 0.095)  # 2700 K
RENDER_EMISSION = 6.0             # a touch brighter than the glb: the studio is lit


def aim(cam, camera, target, lens):
    cam.location = Vector(camera)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


def light_on(scene):
    """Godot adds a small warm OmniLight at the bulb. Here three small point
    lights ring the (opaque) bulb inside the shade, so light leaves through
    the shade's openings; the shade and bulb glow by their emission."""
    import math
    for i in range(3):
        t = math.radians(90.0 + 120.0 * i)
        ld = bpy.data.lights.new(f"BulbLight{i}", "POINT")
        ld.energy = 9.0
        ld.color = BULB_COLOR
        ld.shadow_soft_size = 0.008
        ob = bpy.data.objects.new(f"BulbLight{i}", ld)
        scene.collection.objects.link(ob)
        ob.location = LAMP_POS + Vector((0.034 * math.cos(t), 0.034 * math.sin(t), BULB_CENTER_Z - 0.004))
    for m in bpy.data.materials:
        if m.name == LIGHT_MAT or m.name in ("src_shade", "src_bulb"):
            b = [n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"][0]
            b.inputs["Emission Strength"].default_value = RENDER_EMISSION


def main():
    args = script_args()
    samples = 16 if "--quick" in args else 64
    out = args[args.index("--out") + 1] if "--out" in args else SCRATCH
    suffix = args[args.index("--suffix") + 1] if "--suffix" in args else ""
    os.makedirs(out, exist_ok=True)
    scene = bpy.context.scene
    cam = studio(scene, key=300.0, fill=110.0, rim=220.0, **VIEW)
    for ob in body_collision_objects():
        ob.hide_render = True
    light_on(scene)
    drawer = bpy.data.objects["Drawer"]
    closed = drawer.location.copy()

    render_still(scene, os.path.join(out, f"nightstand_{TAG}_closed{suffix}.png"), samples)
    drawer.location = closed + Vector((0.0, -0.2, 0.0))
    render_still(scene, os.path.join(out, f"nightstand_{TAG}_open{suffix}.png"), samples)
    if "--detail" in args:
        aim(cam, **DETAIL)
        render_still(scene, os.path.join(out, f"nightstand_{TAG}_detail{suffix}.png"), samples)
        drawer.location = closed
        aim(cam, **PULL)
        render_still(scene, os.path.join(out, f"nightstand_{TAG}_pull{suffix}.png"), samples)
        aim(cam, **SHADE)
        render_still(scene, os.path.join(out, f"nightstand_{TAG}_shade{suffix}.png"), samples)
    drawer.location = closed


if __name__ == "__main__":
    main()
