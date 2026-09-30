"""Stage 4: thumbnails in a render-only room (wall with the opening, floor,
ceiling, night backdrop, glass, a lowered shade). Nothing is saved.

  blender -b --factory-startup blender/architecture/windows_<spec>.blend --python blender/architecture/windows/render.py -- [--quick] [--out DIR] [--only NAME,...]

Views: the living window from the room at seated (1.2 m) and standing (1.7 m)
eye height, a sill corner and an LED head corner close-up (bedroom), the
bedroom sash tilted open, the exterior sill, the wall panel.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from windows_common import (  # noqa: E402
    GODOT, MAT_LED, MAT_PANEL_LED, SCRATCH, bar_objects, button_objects, frame_objects, load_spec, panel_objects,
    sash_objects, windows,
)
from arcology_blender.geo import bm_box, new_object  # noqa: E402
from arcology_blender.scene import setup_gpu  # noqa: E402
from arcology_blender.studio import aim, render_options  # noqa: E402
from arcology_blender.trim import GODOT_TO_BLENDER  # noqa: E402

LED_COLORS = {"warm": (1.0, 0.60, 0.30), "cyan": (0.02, 0.85, 0.91)}
WALL = (0.69, 0.64, 0.55)     # warm off-white #D8D2C4 (linear)
ROOM_DEPTH, CEILING = 4.5, 2.6


def gb(p):
    return GODOT_TO_BLENDER @ Vector(p)


def mat(name, base, rough, metal=0.0, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emission:
        b.inputs["Emission Color"].default_value = (*emission, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def glass_mat():
    m = bpy.data.materials.new("r_glass")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs[0].default_value = (0.93, 0.95, 0.96, 1)
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.02
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.12
    nt.links.new(lw.outputs["Fresnel"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def city_mat():
    """Night backdrop: navy gradient with scattered warm and cyan windows."""
    m = bpy.data.materials.new("r_city")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.distance = "CHEBYCHEV"
    vor.inputs["Scale"].default_value = 320.0
    vor.inputs["Randomness"].default_value = 0.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
    ramp.color_ramp.elements[1].position = 0.18
    ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
    lit = nt.nodes.new("ShaderNodeMath")
    lit.operation = "GREATER_THAN"
    lit.inputs[1].default_value = 0.93
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    hue = nt.nodes.new("ShaderNodeValToRGB")
    hue.color_ramp.elements[0].color = (1.0, 0.55, 0.15, 1)
    hue.color_ramp.elements[1].color = (0.05, 0.8, 0.95, 1)
    grad = nt.nodes.new("ShaderNodeMix")
    grad.data_type = "RGBA"
    nt.links.new(tc.outputs["Generated"], vor.inputs["Vector"])
    nt.links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
    nt.links.new(vor.outputs["Color"], hue.inputs["Fac"])
    nt.links.new(vor.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[1], lit.inputs[0])            # only some cells are lit windows
    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    nt.links.new(lit.outputs[0], mul.inputs[1])
    grad.inputs["A"].default_value = (0.006, 0.009, 0.02, 1)
    nt.links.new(mul.outputs[0], grad.inputs["Factor"])
    nt.links.new(hue.outputs["Color"], grad.inputs["B"])
    nt.links.new(grad.outputs["Result"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.6
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def fabric_mat():
    m = bpy.data.materials.new("r_fabric")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = bpy.data.images["shade_fabric_albedo"]
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = bpy.data.images["shade_fabric_normal"]
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(ta.outputs[0], b.inputs["Base Color"])
    nt.links.new(tn.outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.92
    return m


def box(name, lo, hi, material, coll):
    """Axis-aligned box given in Godot coordinates."""
    a, b = gb(lo), gb(hi)
    lo_b = Vector([min(a[i], b[i]) for i in range(3)])
    hi_b = Vector([max(a[i], b[i]) for i in range(3)])
    bm = bmesh.new()
    bm_box(bm, lo_b, hi_b)
    return new_object(name, bm, coll, material=material)


def quad(name, pts_godot, material, coll, uv_m=False):
    me = bpy.data.meshes.new(name)
    vs = [gb(p) for p in pts_godot]
    me.from_pydata(vs, [], [(0, 1, 2, 3)])
    if uv_m:  # UVs in meters (fabric tiles once per meter)
        uvl = me.uv_layers.new(name="UVMap")
        p0 = Vector(pts_godot[0])
        for li, vi in enumerate(me.polygons[0].vertices):
            d = Vector(pts_godot[vi]) - p0
            uvl.data[li].uv = (d.x, d.y)
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def context(w, coll, mats):
    """Wall with the window's cut, floor, ceiling, side walls, backdrop, glass."""
    W, B, T, wd = w.W, w.B, w.T, w.wd
    cut_b = B - (GODOT["sill_t"] if w.sill == "stone" else 0.0)
    half = W / 2 + 1.6
    z0, z1 = -wd / 2, wd / 2
    wall = mats["wall"]
    box("r_wall_w", (-half, 0, z0), (-W / 2, CEILING, z1), wall, coll)
    box("r_wall_e", (W / 2, 0, z0), (half, CEILING, z1), wall, coll)
    box("r_wall_top", (-W / 2, T, z0), (W / 2, CEILING, z1), wall, coll)
    if cut_b > 0.0:
        box("r_wall_low", (-W / 2, 0, z0), (W / 2, cut_b, z1), wall, coll)
    box("r_floor", (-half, -0.05, z0), (half, 0.0, ROOM_DEPTH), mats["floor"], coll)
    box("r_ceiling", (-half, CEILING, z0), (half, CEILING + 0.05, ROOM_DEPTH), wall, coll)
    box("r_side_w", (-half - 0.05, 0, z1), (-half, CEILING, ROOM_DEPTH), wall, coll)
    box("r_side_e", (half, 0, z1), (half + 0.05, CEILING, ROOM_DEPTH), wall, coll)
    box("r_back", (-half, 0, ROOM_DEPTH), (half, CEILING, ROOM_DEPTH + 0.05), wall, coll)
    box("r_facade_below", (-half - 6, -8, z0), (half + 6, 0.0, z1), mats["facade"], coll)
    quad("r_city", [(-60, -30, -45), (60, -30, -45), (60, 40, -45), (-60, 40, -45)], mats["city"], coll)
    panes = []
    for i in range(w.n):
        if i == w.vent_bay:
            continue
        x0, x1, y0, y1 = w.glass_rect(i)
        panes.append(quad(f"r_glass{i}", [(x0, y0, w.gz), (x1, y0, w.gz), (x1, y1, w.gz), (x0, y1, w.gz)],
                          mats["glass"], coll))
    if w.vent:
        x0, x1, y0, y1 = w.glass_rect(w.vent_bay)
        panes.append(quad("r_glass_vent", [(x0, y0, w.gz), (x1, y0, w.gz), (x1, y1, w.gz), (x0, y1, w.gz)],
                          mats["glass"], coll))
    return panes


def lower_shade(w, bay, drop, coll, mats):
    """A shade lowered by `drop`: fabric from the slot down to a copy of the bar."""
    x, y, z = w.shade_top(bay)
    wd = w.shade_width(bay) - 0.01
    quad("r_fabric", [(x - wd / 2, y - drop, z), (x + wd / 2, y - drop, z), (x + wd / 2, y, z), (x - wd / 2, y, z)],
         mats["fabric"], coll, uv_m=True)
    src = bar_objects(w.name)[0]
    ob = bpy.data.objects.new("r_bar", src.data)
    coll.objects.link(ob)
    ob.location = gb((x, y - drop, z))


def show_only(objs):
    keep = set(objs)
    for ob in bpy.data.objects:
        if ob.type in ("MESH", "EMPTY") and not ob.name.startswith("r_"):
            ob.hide_render = ob not in keep


def light(name, coll, loc_godot, size, energy, color, look_godot):
    ld = bpy.data.lights.new(name, "AREA")
    ld.size, ld.energy, ld.color = size, energy, color
    ob = bpy.data.objects.new(name, ld)
    ob.visible_camera = False
    ob.visible_glossy = False
    coll.objects.link(ob)
    ob.location = gb(loc_godot)
    ob.rotation_euler = (gb(look_godot) - ob.location).to_track_quat("-Z", "Y").to_euler()
    return ob


def still(scene, path, samples, res=(1600, 1000)):
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


def main():
    opt = render_options(SCRATCH, samples=96, quick_samples=24)
    only = set((opt.value("--only", "") or "").split(",")) - {""}
    _, data = load_spec()
    wins = {w.name: w for w in windows(data)}
    scene = bpy.context.scene
    setup_gpu(scene)
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.01, 0.012, 0.02, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3
    cam = bpy.data.objects.new("r_cam", bpy.data.cameras.new("r_cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    mats = dict(wall=mat("r_wall", WALL, 0.85), floor=mat("r_floor", (0.05, 0.032, 0.02), 0.45),
                facade=mat("r_facade", (0.09, 0.095, 0.1), 0.8), glass=glass_mat(), city=city_mat(),
                fabric=fabric_mat())
    led = bpy.data.materials[MAT_LED].node_tree.nodes.get("Principled BSDF")

    def shot(name, w, cam_g, target_g, lens, res=(1600, 1000), extra=()):
        if only and name not in only:
            return
        coll = bpy.data.collections.new(f"r_{name}")
        scene.collection.children.link(coll)
        objs = frame_objects(w.name) + list(extra)
        show_only(objs)
        context(w, coll, mats)
        if led is not None:
            led.inputs["Emission Color"].default_value = (*LED_COLORS[w.spec["led"]], 1)
        light("r_ceiling_light", coll, (0.0, CEILING - 0.02, 2.2), 1.2, 140.0, (1.0, 0.78, 0.55), (0.0, 0.0, 2.2))
        light("r_fill", coll, (0.0, 1.4, ROOM_DEPTH - 0.2), 2.0, 40.0, (1.0, 0.85, 0.7), (0.0, 1.2, 0.0))
        light("r_moon", coll, (-3.0, 6.0, -8.0), 4.0, 900.0, (0.6, 0.7, 1.0), (0.0, 1.0, 0.0))
        yield_ = coll
        aim(cam, gb(cam_g), gb(target_g), lens)
        return yield_

    def done(coll):
        for ob in list(coll.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(coll)

    out = lambda n: os.path.join(opt.out, f"{n}{opt.suffix}.png")  # noqa: E731

    liv = wins.get("apartment_living")
    if liv:
        bar = bar_objects(liv.name)
        for name, cam_g, tgt, lens in (("living_seated", (0.9, 1.2, 3.0), (0.0, 1.15, 0.0), 18.0),
                                       ("living_standing", (-0.6, 1.7, 2.8), (0.0, 1.35, 0.0), 18.0)):
            c = shot(name, liv, cam_g, tgt, lens, extra=bar)
            if c:
                lower_shade(liv, 1, 1.05, c, mats)
                still(scene, out(name), opt.samples)
                done(c)
    bed = wins.get("apartment_bedroom")
    if bed:
        extra = sash_objects(bed.name) + bar_objects(bed.name) + bar_objects(bed.name, True)
        W, B, T = bed.W, bed.B, bed.T
        c = shot("bedroom_sill_corner", bed, (W / 2 - 0.25, B + 0.28, 0.42), (W / 2 - 0.05, B + 0.04, 0.02), 40.0,
                 extra=extra)
        if c:
            still(scene, out("bedroom_sill_corner"), opt.samples)
            done(c)
        c = shot("bedroom_head_led", bed, (W / 2 - 0.35, T - 0.40, 0.45), (W / 2 - 0.04, T - 0.03, 0.04), 32.0,
                 extra=extra)
        if c:
            still(scene, out("bedroom_head_led"), opt.samples)
            done(c)
        sash = [o for o in sash_objects(bed.name) if o.type == "MESH"][0]
        c = shot("bedroom_sash_open", bed, (-0.55, 1.45, 1.9), (0.55, 1.35, 0.1), 24.0, extra=extra)
        if c:
            vent_bar = bar_objects(bed.name, True)[0]
            pane = bpy.data.objects["r_glass_vent"]
            for ob in (vent_bar, pane):
                mw = ob.matrix_world.copy()
                ob.parent = sash
                ob.matrix_parent_inverse = sash.matrix_world.inverted()
                ob.matrix_world = mw
            sash.rotation_euler = (math.radians(bed.open_max), 0, 0)
            still(scene, out("bedroom_sash_open"), opt.samples)
            sash.rotation_euler = (0, 0, 0)
            for ob in (vent_bar, pane):
                mw = ob.matrix_world.copy()
                ob.parent = None
                ob.matrix_world = mw
            done(c)
        c = shot("bedroom_handle", bed, (0.30, 1.42, 0.42), (0.05, 1.33, 0.0), 38.0, extra=extra)
        if c:
            still(scene, out("bedroom_handle"), opt.samples)
            done(c)
        c = shot("bedroom_exterior", bed, (0.95, B + 0.45, -1.0), (0.55, B + 0.02, -0.12), 30.0, extra=extra)
        if c:
            still(scene, out("bedroom_exterior"), opt.samples)
            done(c)
    kit = wins.get("apartment_kitchen")
    if kit:
        c = shot("kitchen", kit, (0.5, 1.45, 1.6), (0.0, 1.6, 0.0), 26.0, extra=bar_objects(kit.name))
        if c:
            still(scene, out("kitchen"), opt.samples)
            done(c)
    # panel on a wall patch
    if not only or "panel" in only:
        coll = bpy.data.collections.new("r_panel")
        scene.collection.children.link(coll)
        panel = [o for o in panel_objects() if o.type == "MESH"][0]
        objs = [panel] + button_objects()
        show_only(objs)
        pm = bpy.data.materials[MAT_PANEL_LED].node_tree.nodes.get("Principled BSDF")
        pm.inputs["Emission Color"].default_value = (*LED_COLORS["warm"], 1)
        pl = panel.location
        wallp = bpy.data.meshes.new("r_panel_wall")
        wallp.from_pydata([pl + Vector(v) for v in ((-0.5, 0.0002, -0.5), (0.5, 0.0002, -0.5), (0.5, 0.0002, 0.5),
                                                    (-0.5, 0.0002, 0.5))], [], [(0, 1, 2, 3)])
        wallp.materials.append(mats["wall"])
        coll.objects.link(bpy.data.objects.new("r_panel_wall", wallp))
        btn2 = bpy.data.objects.new("r_button2", button_objects()[0].data)
        coll.objects.link(btn2)
        btn2.location = button_objects()[0].location + Vector((0, 0, -0.07))
        ld = bpy.data.lights.new("r_panel_key", "AREA")
        ld.size, ld.energy, ld.color = 0.4, 6.0, (1.0, 0.85, 0.7)
        lo = bpy.data.objects.new("r_panel_key", ld)
        coll.objects.link(lo)
        lo.location = pl + Vector((0.25, -0.35, 0.3))
        lo.rotation_euler = (pl - lo.location).to_track_quat("-Z", "Y").to_euler()
        aim(cam, pl + Vector((0.09, -0.26, 0.05)), pl, 55.0)
        still(scene, out("panel"), opt.samples, res=(1000, 1000))
        done(coll)


if __name__ == "__main__":
    main()
