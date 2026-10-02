"""Stage 4: studio thumbnails against a wall, with a 1.8 m reference figure. Not saved.

  blender -b --factory-startup blender/props/vanity.blend --python blender/props/vanity/render.py -- [--quick] [--out DIR] [--suffix NAME] [--only NAME,...]

Views: front (3/4, closed, figure), top_open (top drawer out 0.30 m), bottom_open
(bottom drawer out 0.36 m), mixer (lever lifted 30 and swung 20 degrees toward hot),
dispenser (close-up), led (room dark, under-cabinet light on the floor; the strip's
emission is raised for the still). Works before baking too.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from vanity_common import (  # noqa: E402
    LED_MAT, LEVER_LIFT, NAME, SCRATCH, collision_objects, drawer_collision,
)
from arcology_blender import curves  # noqa: E402
from arcology_blender.shading import solid_mat  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

VIEWS = {
    "front": dict(camera=(1.75, -2.45, 1.55), target=(-0.05, -0.25, 0.68), lens=32.0),
    "top_open": dict(camera=(0.75, -1.45, 1.55), target=(0.0, -0.55, 0.70), lens=38.0),
    "bottom_open": dict(camera=(0.85, -1.55, 1.35), target=(0.0, -0.60, 0.48), lens=38.0),
    "mixer": dict(camera=(0.42, -0.78, 1.25), target=(0.06, -0.22, 0.90), lens=42.0),
    "dispenser": dict(camera=(0.66, -0.66, 1.04), target=(0.40, -0.24, 0.94), lens=55.0),
    "led": dict(camera=(0.95, -1.75, 0.30), target=(0.0, -0.25, 0.22), lens=30.0),
}


def room(scene):
    """Plaster wall at y = 0, a concrete floor tone, and a 1.8 m figure to the left."""
    wall = solid_mat("RenderWall", (0.62, 0.60, 0.56), 0.85)
    me = bpy.data.meshes.new("RenderWall")
    me.from_pydata([(-2.5, 0.0005, 0.0), (2.5, 0.0005, 0.0), (2.5, 0.0005, 2.6), (-2.5, 0.0005, 2.6)], [],
                   [(0, 1, 2, 3)])
    me.materials.append(wall)
    scene.collection.objects.link(bpy.data.objects.new("RenderWall", me))
    fig = solid_mat("RenderFigure", (0.30, 0.32, 0.36), 0.6)
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.13, 0.0), (0.16, 0.30), (0.17, 0.9), (0.20, 1.35), (0.21, 1.45), (0.07, 1.52),
            (0.065, 1.56), (0.10, 1.62), (0.105, 1.70), (0.08, 1.77), (0.0, 1.80)]
    curves.lathe(bm, prof, 24, center=(-1.15, -0.45, 0.0))
    me = bpy.data.meshes.new("RenderFigure")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(fig)
    scene.collection.objects.link(bpy.data.objects.new("RenderFigure", me))


def led_scene(scene, on):
    """Dim the studio (LED view) and show the strip's emission."""
    for ob in scene.objects:
        if ob.type == "LIGHT" and ob.name in ("Key", "Fill", "Rim"):
            ob.data.energy *= 0.04 if on else 25.0
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.02 if on else 0.5


def main():
    opt = render_options(SCRATCH)
    only = opt.value("--only")
    want = set(only.split(",")) if only else set(VIEWS)
    scene = bpy.context.scene
    cam = studio(scene, key=700.0, fill=260.0, rim=320.0, **VIEWS["front"])
    for ob in collision_objects() + drawer_collision("top") + drawer_collision("bottom"):
        ob.hide_render = True
    room(scene)
    top, bot, lever = (bpy.data.objects[n] for n in ("DrawerTop", "DrawerBottom", "Lever"))
    saved = {ob: (ob.location.copy(), ob.rotation_euler.copy()) for ob in (top, bot, lever)}

    def reset():
        for ob, (loc, rot) in saved.items():
            ob.location, ob.rotation_euler = loc, rot

    def shot(view, setup=None):
        if view not in want:
            return
        reset()
        if setup:
            setup()
        aim(cam, **VIEWS[view])
        render_still(scene, os.path.join(opt.out, f"{NAME}_{view}{opt.suffix}.png"), opt.samples)

    shot("front")
    shot("top_open", lambda: setattr(top, "location", saved[top][0] + Vector((0, -0.30, 0))))
    shot("bottom_open", lambda: setattr(bot, "location", saved[bot][0] + Vector((0, -0.36, 0))))
    shot("mixer", lambda: setattr(lever, "rotation_euler", (math.radians(-LEVER_LIFT), 0.0, math.radians(-20.0))))
    shot("dispenser")
    if "led" in want:
        led_scene(scene, True)
        led = bpy.data.materials.get(LED_MAT)
        if led is not None:
            led.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 12.0
        shot("led")
        led_scene(scene, False)
    reset()


if __name__ == "__main__":
    main()
