"""Stage 4: studio thumbnails on a plaster wall at room height, LED on. Not saved.

  blender -b --factory-startup blender/props/bath_mirror.blend --python blender/props/bath_mirror/render.py -- [--quick] [--out DIR] [--suffix NAME] [--detail]

Shots: front 3/4 (magnifier folded), dark (only the LED), magnifier swung out
80 degrees, scale (1.8 m figure, 0.90 m vanity placeholder); --detail adds the
touch sensor close-up. The halo renders additively (emission + transparent),
as Godot should draw it. Works before baking too.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402

from bath_mirror_common import (  # noqa: E402
    GLASS_Y, LED_MAT, LED_STRENGTH, MAG_POS, NAME, SCRATCH, TOUCH_Z, WALL_PLASTER, collision_objects,
)
from arcology_blender import curves  # noqa: E402
from arcology_blender.geo import bm_box, new_object  # noqa: E402
from arcology_blender.shading import solid_mat  # noqa: E402
from arcology_blender.studio import aim, render_options, render_still, studio  # noqa: E402

MOUNT_Z = 1.18                     # the mirror's bottom edge in the room
FRONT = dict(camera=(1.05, -1.95, 0.62), target=(0.18, 0.0, 0.40), lens=32.0)
SWUNG = dict(camera=(0.45, -1.15, 0.72), target=(0.93, -0.17, 0.25), lens=42.0)
SCALE = dict(camera=(3.0, -4.6, 0.55), target=(0.1, 0.0, -0.25), lens=26.0)
TOUCH = dict(camera=(0.09, -0.32, 0.13), target=(0.0, GLASS_Y, TOUCH_Z), lens=60.0)


def additive_halo():
    """Godot draws mirror_led unshaded + additive; mimic it: emission + transparent."""
    m = bpy.data.materials[LED_MAT]
    nt = m.node_tree
    tex = [n for n in nt.nodes if n.type == "TEX_IMAGE"][0]
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = LED_STRENGTH
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(em.outputs[0], add.inputs[0])
    nt.links.new(tr.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])


def room(coll):
    """Plaster wall at Y = 0, floor 1.18 m below the mirror, a vanity placeholder."""
    wall = solid_mat("render_wall", WALL_PLASTER, 0.85)
    bm = bmesh.new()
    bm_box(bm, (-2.4, 0.0, -MOUNT_Z), (2.4, 0.05, 2.6 - MOUNT_Z))
    new_object("RenderWall", bm, coll, material=wall)
    marble = solid_mat("render_marble", (0.79, 0.76, 0.70), 0.25)
    walnut = solid_mat("render_walnut", (0.066, 0.034, 0.020), 0.45)
    bm = bmesh.new()
    bm_box(bm, (-0.70, -0.52, -MOUNT_Z + 0.25), (0.70, 0.0, -MOUNT_Z + 0.86))
    new_object("RenderVanity", bm, coll, material=walnut)
    bm = bmesh.new()
    bm_box(bm, (-0.70, -0.52, -MOUNT_Z + 0.86), (0.70, 0.0, -MOUNT_Z + 0.90))
    new_object("RenderVanityTop", bm, coll, material=marble)


def figure(coll):
    """1.8 m reference figure (pill body, head)."""
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.16, 0.0)] + [(0.17, z) for z in (0.05, 1.30)] + [(0.13, 1.45), (0.06, 1.52)]
    prof += [(0.105 * math.cos(math.radians(a)), 1.69 + 0.11 * math.sin(math.radians(a))) for a in range(-60, 91, 15)]
    prof[-1] = (0.0, 1.80)
    curves.lathe(bm, prof, 24)
    ob = new_object("RenderFigure", bm, coll, origin=(-1.15, -0.75, -MOUNT_Z),
                    material=solid_mat("render_figure", (0.25, 0.30, 0.38), 0.6))
    ob.hide_render = True
    return ob


def main():
    opt = render_options(SCRATCH)
    scene = bpy.context.scene
    cam = studio(scene, key=260.0, fill=70.0, rim=60.0, **FRONT)
    for name in ("StudioFloor",):
        bpy.data.objects[name].location.z = -MOUNT_Z
    bpy.data.objects["StudioBack"].hide_render = True
    for ob in collision_objects() + [o for o in bpy.data.objects if o.name.startswith("ColMag")]:
        ob.hide_render = True
    coll = bpy.data.collections.new("RenderRoom")
    scene.collection.children.link(coll)
    room(coll)
    fig = figure(coll)
    additive_halo()
    arm = bpy.data.objects["MagnifierArm"]

    render_still(scene, os.path.join(opt.out, f"{NAME}_front{opt.suffix}.png"), opt.samples)

    lights = [o for o in bpy.data.objects if o.type == "LIGHT"]
    energy = {o.name: o.data.energy for o in lights}
    for o in lights:
        o.data.energy *= 0.08
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.05
    render_still(scene, os.path.join(opt.out, f"{NAME}_dark{opt.suffix}.png"), opt.samples)
    for o in lights:
        o.data.energy = energy[o.name]
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5

    arm.rotation_euler.z = math.radians(-80.0)
    aim(cam, **SWUNG)
    render_still(scene, os.path.join(opt.out, f"{NAME}_magnifier_swung{opt.suffix}.png"), opt.samples)

    fig.hide_render = False
    aim(cam, **SCALE)
    render_still(scene, os.path.join(opt.out, f"{NAME}_scale{opt.suffix}.png"), opt.samples)
    fig.hide_render = True
    arm.rotation_euler.z = 0.0
    if opt.has("--detail"):
        aim(cam, **TOUCH)
        render_still(scene, os.path.join(opt.out, f"{NAME}_touch{opt.suffix}.png"), opt.samples)
        arm.rotation_euler.z = math.radians(-170.0)
        aim(cam, camera=(MAG_POS.x + 0.2, -0.9, 0.35), target=(MAG_POS.x - 0.3, -0.05, MAG_POS.z), lens=35.0)
        render_still(scene, os.path.join(opt.out, f"{NAME}_magnifier_170{opt.suffix}.png"), opt.samples)
        arm.rotation_euler.z = 0.0


if __name__ == "__main__":
    main()
