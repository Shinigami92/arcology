"""Stage 1: build the fridge geometry and procedural source materials, save the .blend.

  blender -b --factory-startup --python build.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from fridge_common import *  # noqa: E402,F403
from fridge_common import (  # noqa: E402
    BLEND, BODY_MAT, CAB_H, CAB_X, CAB_Y, CAV_X, CAV_Y_BACK, CAV_Z0, CAV_Z1, CRISPER_COVER_TOP,
    CRISPER_D, CRISPER_H, CRISPER_W, CRISPER_Y0, DISPLAY_MAT, DOOR_LINER_Y0, DOOR_LINER_Y1,
    DOOR_SKIN_Y0, DOOR_SKIN_Y1, DOOR_W, DOOR_Z0, DOOR_Z1, GASKET_Y0, GASKET_Y1, GLASS_MAT,
    GLASS_T, HANDLE_GRIP, HANDLE_R, HANDLE_X, HANDLE_Y, HANDLE_Z0, HANDLE_Z1, HINGE, LIGHT_MAT,
    PLINTH_DEPTH, PLINTH_Z, SHELF_TOPS, SHELF_Y0, apply_modifiers, assign_by_region, bevel,
    bm_box, bm_cyl, boolean_cut, clear_scene, cyl_matrix_y, finish, get_collection, new_object,
    set_colorspace, shade, tri_count,
)


# ---------------------------------------------------------------------------
# Procedural source materials (baked later into the atlases)
# ---------------------------------------------------------------------------
class Graph:
    """Tiny helper to build shader node graphs with world-position driven masks."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.nodes = self.nt.nodes
        self.links = self.nt.links
        self.nodes.clear()
        self.out = self.nodes.new("ShaderNodeOutputMaterial")
        self.bsdf = self.nodes.new("ShaderNodeBsdfPrincipled")
        self.bsdf.name = "BSDF"
        self.links.new(self.bsdf.outputs[0], self.out.inputs["Surface"])
        self.geo = self.nodes.new("ShaderNodeNewGeometry")
        self.pos = self.nodes.new("ShaderNodeSeparateXYZ")
        self.links.new(self.geo.outputs["Position"], self.pos.inputs[0])
        self.nrm = self.nodes.new("ShaderNodeSeparateXYZ")
        self.links.new(self.geo.outputs["Normal"], self.nrm.inputs[0])
        self.x, self.y, self.z = self.pos.outputs[0], self.pos.outputs[1], self.pos.outputs[2]
        self.nx, self.ny, self.nz = self.nrm.outputs[0], self.nrm.outputs[1], self.nrm.outputs[2]
        self.mat = mat

    def _set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.links.new(v, sock)
        elif isinstance(v, (tuple, list)):
            sock.default_value = tuple(v) + ((1.0,) if len(v) == 3 else ())
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0, clamp=False):
        n = self.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        self._set(n.inputs[0], a)
        self._set(n.inputs[1], b)
        return n.outputs[0]

    def add(self, a, b):
        return self.math("ADD", a, b)

    def sub(self, a, b):
        return self.math("SUBTRACT", a, b)

    def mul(self, a, b):
        return self.math("MULTIPLY", a, b)

    def maprange(self, v, fmin, fmax, tmin=0.0, tmax=1.0, smooth=True):
        n = self.nodes.new("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP" if smooth else "LINEAR"
        n.clamp = True
        self._set(n.inputs["Value"], v)
        n.inputs["From Min"].default_value = fmin
        n.inputs["From Max"].default_value = fmax
        n.inputs["To Min"].default_value = tmin
        n.inputs["To Max"].default_value = tmax
        return n.outputs["Result"]

    def band(self, v, lo, hi, soft):
        """1 inside [lo, hi], smooth falloff of width `soft` outside."""
        a = self.maprange(v, lo - soft, lo)
        b = self.maprange(v, hi + soft, hi)
        return self.mul(a, b)

    def vec(self, sx, sy, sz):
        """Scaled world position vector for stretched noise."""
        n = self.nodes.new("ShaderNodeVectorMath")
        n.operation = "MULTIPLY"
        self.links.new(self.geo.outputs["Position"], n.inputs[0])
        n.inputs[1].default_value = (sx, sy, sz)
        return n.outputs[0]

    def noise(self, scale, detail=2.0, rough=0.5, vector=None):
        n = self.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        if vector is not None:
            self.links.new(vector, n.inputs["Vector"])
        else:
            self.links.new(self.geo.outputs["Position"], n.inputs["Vector"])
        return n.outputs["Fac"]

    def _mix(self, dtype, fac, a, b):
        n = self.nodes.new("ShaderNodeMix")
        n.data_type = dtype
        n.clamp_factor = True
        self._set(n.inputs[0], fac)
        stype = {"FLOAT": "VALUE", "RGBA": "RGBA", "VECTOR": "VECTOR"}[dtype]
        sa = [s for s in n.inputs if s.name == "A" and s.type == stype][0]
        sb = [s for s in n.inputs if s.name == "B" and s.type == stype][0]
        self._set(sa, a)
        self._set(sb, b)
        return [s for s in n.outputs if s.name == "Result" and s.type == stype][0]

    def mixf(self, fac, a, b):
        return self._mix("FLOAT", fac, a, b)

    def mixc(self, fac, a, b):
        return self._mix("RGBA", fac, a, b)

    def scale_color(self, col, f):
        n = self.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = "MULTIPLY"
        n.inputs[0].default_value = 1.0
        sa = [s for s in n.inputs if s.name == "A" and s.type == "RGBA"][0]
        sb = [s for s in n.inputs if s.name == "B" and s.type == "RGBA"][0]
        self._set(sa, col)
        if isinstance(f, bpy.types.NodeSocket):
            comb = self.nodes.new("ShaderNodeCombineColor")
            for i in range(3):
                self.links.new(f, comb.inputs[i])
            self.links.new(comb.outputs[0], sb)
        else:
            sb.default_value = (f, f, f, 1.0)
        return [s for s in n.outputs if s.name == "Result" and s.type == "RGBA"][0]

    def bump(self, height, strength, distance, normal=None):
        n = self.nodes.new("ShaderNodeBump")
        n.inputs["Strength"].default_value = strength
        n.inputs["Distance"].default_value = distance
        self._set(n.inputs["Height"], height)
        if normal is not None:
            self.links.new(normal, n.inputs["Normal"])
        return n.outputs["Normal"]

    def finish(self, base, rough, metal, normal=None):
        self._set(self.bsdf.inputs["Base Color"], base)
        if isinstance(rough, bpy.types.NodeSocket):
            rough = self.math("ADD", rough, 0.0, clamp=True)
        self._set(self.bsdf.inputs["Roughness"], rough)
        self._set(self.bsdf.inputs["Metallic"], metal)
        if normal is not None:
            self.links.new(normal, self.bsdf.inputs["Normal"])
        return self.mat


def new_mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    return m


def mat_steel():
    g = Graph(new_mat("src_steel"))
    base = (0.42, 0.43, 0.45)
    rough = g.add(0.34, g.mul(g.sub(g.noise(6.0, 2.0), 0.5), 0.10))
    # sheet metal waviness (large scale only; fine grain shimmers in VR)
    n = g.bump(g.noise(2.5, 1.0), 1.0, 0.02)
    # brighter, smoother edges (pointiness)
    edge = g.maprange(g.geo.outputs["Pointiness"], 0.52, 0.64)
    rough = g.sub(rough, g.mul(edge, 0.10))
    base = g.scale_color(base, g.add(1.0, g.mul(edge, 0.12)))
    # fingerprint smudges around the handle (door front + handle bar)
    front = g.maprange(g.y, -0.365, -0.372)
    region = g.mul(g.mul(g.band(g.x, 0.10, 0.29, 0.05), g.band(g.z, 0.90, 1.60, 0.10)), front)
    fp = g.mul(region, g.mul(g.maprange(g.noise(45.0, 5.0, 0.7), 0.50, 0.58),
                             g.maprange(g.noise(7.0, 2.0), 0.40, 0.62)))
    rough = g.add(rough, g.mul(fp, 0.22))
    base = g.scale_color(base, g.sub(1.0, g.mul(fp, 0.06)))
    # scuffs and grime at the bottom edge
    low = g.maprange(g.z, 0.26, 0.10)
    scuff = g.mul(low, g.maprange(g.noise(1.0, 3.0, 0.6, g.vec(5.0, 5.0, 90.0)), 0.52, 0.66))
    rough = g.add(rough, g.mul(scuff, 0.35))
    base = g.scale_color(base, g.sub(1.0, g.mul(scuff, 0.30)))
    base = g.scale_color(base, g.maprange(g.z, 0.0, 0.10, 0.78, 1.0))
    # dust on the top
    dust = g.mul(g.mul(g.maprange(g.nz, 0.8, 0.95), g.maprange(g.z, 1.78, 1.84)),
                 g.maprange(g.noise(12.0, 2.0), 0.3, 0.7))
    rough = g.add(rough, g.mul(dust, 0.30))
    base = g.mixc(g.mul(dust, 0.35), base, (0.62, 0.60, 0.57))
    # a parcel sticker on the door front (world x -0.22..-0.13, z 0.98..1.05)
    st = g.mul(g.mul(g.band(g.x, -0.22, -0.13, 0.003), g.band(g.z, 0.98, 1.05, 0.003)), front)
    stripe = g.band(g.z, 1.034, 1.05, 0.001)
    line1 = g.mul(g.band(g.z, 1.000, 1.007, 0.001), g.band(g.x, -0.210, -0.160, 0.001))
    line2 = g.mul(g.band(g.z, 1.014, 1.021, 0.001), g.band(g.x, -0.210, -0.140, 0.001))
    st_col = g.mixc(stripe, (0.90, 0.90, 0.88), (0.85, 0.08, 0.30))
    st_col = g.mixc(g.add(line1, line2), st_col, (0.10, 0.10, 0.11))
    base = g.mixc(st, base, st_col)
    rough = g.mixf(st, rough, 0.55)
    metal = g.sub(1.0, st)
    return g.finish(base, rough, metal, n)


def mat_liner():
    g = Graph(new_mat("src_liner"))
    base = (0.90, 0.90, 0.87)
    grime = g.mul(g.maprange(g.z, 0.32, 0.13), g.maprange(g.noise(9.0, 2.0), 0.3, 0.7))
    base = g.mixc(g.mul(grime, 0.5), base, (0.80, 0.77, 0.70))
    rough = g.add(0.40, g.mul(g.sub(g.noise(20.0), 0.5), 0.10))
    rough = g.add(rough, g.mul(grime, 0.2))
    n = g.bump(g.noise(140.0, 2.0), 1.0, 0.001)
    return g.finish(base, rough, 0.0, n)


def mat_frosted():
    g = Graph(new_mat("src_frosted"))
    rough = g.add(0.14, g.mul(g.sub(g.noise(15.0), 0.5), 0.08))
    n = g.bump(g.noise(60.0, 2.0), 1.0, 0.0015)
    return g.finish((0.72, 0.78, 0.82), rough, 0.0, n)


def mat_dark():
    g = Graph(new_mat("src_dark"))
    rough = g.add(0.45, g.mul(g.sub(g.noise(25.0), 0.5), 0.10))
    n = g.bump(g.noise(200.0, 2.0), 1.0, 0.0008)
    return g.finish((0.045, 0.046, 0.05), rough, 0.0, n)


def mat_rubber():
    g = Graph(new_mat("src_rubber"))
    rough = g.add(0.72, g.mul(g.sub(g.noise(40.0), 0.5), 0.06))
    n = g.bump(g.noise(300.0, 1.0), 1.0, 0.0005)
    return g.finish((0.60, 0.60, 0.58), rough, 0.0, n)


def mat_paper():
    g = Graph(new_mat("src_paper"))
    base = (0.94, 0.93, 0.89)
    f = g.math("FRACT", g.mul(g.z, 125.0))
    line = g.maprange(f, 0.10, 0.06)
    base = g.mixc(g.mul(line, 0.8), base, (0.55, 0.65, 0.85))
    # ink scribble: thin iso-lines of a distorted wave
    w = g.nodes.new("ShaderNodeTexWave")
    w.wave_type = "BANDS"
    w.bands_direction = "X"
    w.inputs["Scale"].default_value = 30.0
    w.inputs["Distortion"].default_value = 9.0
    w.inputs["Detail"].default_value = 2.0
    g.links.new(g.geo.outputs["Position"], w.inputs["Vector"])
    stroke = g.mul(g.maprange(w.outputs["Fac"], 0.42, 0.50), g.maprange(w.outputs["Fac"], 0.58, 0.50))
    region = g.mul(g.band(g.x, -0.19, -0.135, 0.005), g.band(g.z, 1.405, 1.465, 0.005))
    base = g.mixc(g.mul(stroke, region), base, (0.12, 0.12, 0.30))
    return g.finish(base, 0.85, 0.0, None)


def mat_magnet():
    g = Graph(new_mat("src_magnet"))
    return g.finish((0.85, 0.10, 0.32), 0.25, 0.0, None)


def mat_glass():
    m = new_mat(GLASS_MAT)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.80, 0.86, 0.84, 1.0)
    b.inputs["Roughness"].default_value = 0.05
    b.inputs["Metallic"].default_value = 0.0
    return m


def mat_light():
    m = new_mat(LIGHT_MAT)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.90, 0.90, 0.90, 1.0)
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Emission Color"].default_value = (1.0, 0.96, 0.90, 1.0)
    b.inputs["Emission Strength"].default_value = 4.0
    return m


# 5x7 bitmap glyphs for the status display
GLYPHS = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "°": ["01100", "10010", "10010", "01100", "00000", "00000", "00000"],
    " ": ["00000"] * 7,
}


def draw_text(img, text, x0, y0, cell, color):
    """Draw glyphs into a HxWx4 float array; y grows downward in this helper."""
    h = img.shape[0]
    for ci, ch in enumerate(text):
        rows = GLYPHS.get(ch, GLYPHS[" "])
        for r, row in enumerate(rows):
            for c, bit in enumerate(row):
                if bit == "1":
                    xs = x0 + (ci * 6 + c) * cell
                    ys = y0 + r * cell
                    img[h - ys - cell:h - ys, xs:xs + cell, :3] = color


def make_display_texture():
    w, h = 512, 256
    img = np.zeros((h, w, 4), dtype=np.float32)
    img[..., :3] = (0.012, 0.02, 0.028)
    img[..., 3] = 1.0
    cyan = (0.02, 0.85, 0.91)
    dim = (0.02, 0.36, 0.40)
    # main temperature readout and freezer readout
    draw_text(img, "4°C", 40, 60, 12, cyan)
    draw_text(img, "-18°C", 290, 78, 7, dim)
    draw_text(img, "ECO", 290, 140, 7, dim)
    # separator line and a segmented bar
    img[h - 50:h - 47, 40:472, :3] = dim
    for i in range(8):
        col = cyan if i < 5 else (0.03, 0.10, 0.12)
        x = 40 + i * 32
        img[h - 190:h - 176, x:x + 24, :3] = col
    image = bpy.data.images.new("fridge_display_emissive", w, h, alpha=False)
    set_colorspace(image, "sRGB")
    image.pixels.foreach_set(img.ravel())
    image.pack()
    return image


def mat_display(image):
    m = new_mat(DISPLAY_MAT)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.01, 0.01, 0.012, 1.0)
    b.inputs["Roughness"].default_value = 0.12
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Emission Strength"].default_value = 2.5
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    return m


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def tag(ob, part):
    ob["fridge_part"] = part
    return ob


def build_body(coll, col_coll, mats):
    steel, liner, dark, frosted = mats["steel"], mats["liner"], mats["dark"], mats["frosted"]
    glass, light = mats["glass"], mats["light"]

    # Cabinet shell: outer box minus cavity and plinth recess
    bm = bmesh.new()
    bm_box(bm, (-CAB_X, -CAB_Y, 0.0), (CAB_X, CAB_Y, CAB_H))
    cab = new_object("Cabinet", bm, coll, material=steel)
    bm = bmesh.new()
    bm_box(bm, (-CAV_X, -0.40, CAV_Z0), (CAV_X, CAV_Y_BACK, CAV_Z1))
    bm_box(bm, (-0.31, -0.40, -0.01), (0.31, -CAB_Y + PLINTH_DEPTH, PLINTH_Z))
    cutter = new_object("CabinetCutter", bm, coll)
    boolean_cut(cab, cutter)
    bevel(cab, 0.006, 2)
    apply_modifiers(cab)
    bpy.data.objects.remove(cutter, do_unlink=True)
    shade(cab)
    assign_by_region(cab, [
        (((-CAV_X - 0.012, -0.34, CAV_Z0 - 0.012), (CAV_X + 0.012, CAV_Y_BACK + 0.012, CAV_Z1 + 0.012)), liner),
        (((-0.31, -0.34, -0.01), (0.31, -CAB_Y + PLINTH_DEPTH + 0.012, PLINTH_Z + 0.012)), dark),
    ], steel)
    tag(cab, "body")

    # Top hinge bracket
    bm = bmesh.new()
    bm_box(bm, (-CAB_X, -0.39, CAB_H), (-CAB_X + 0.075, -0.255, CAB_H + 0.006))
    bm_cyl(bm, 0.012, 0.006, Matrix.Translation((HINGE.x + 0.0, HINGE.y, CAB_H + 0.009)), 16)
    ob = new_object("HingeTop", bm, coll, material=steel)
    finish(ob, 0.0015, 1)
    tag(ob, "body")

    # Kick grille in the plinth recess
    bm = bmesh.new()
    yb = -CAB_Y + PLINTH_DEPTH
    bm_box(bm, (-0.285, yb - 0.006, 0.004), (0.285, yb, PLINTH_Z - 0.004))
    for i in range(5):
        z = 0.012 + i * 0.014
        bm_box(bm, (-0.28, yb - 0.012, z), (0.28, yb - 0.006, z + 0.006))
    ob = new_object("KickGrille", bm, coll, material=dark)
    finish(ob, 0.0012, 1)
    tag(ob, "body")

    # Shelf support ribs on the liner walls
    bm = bmesh.new()
    for t in SHELF_TOPS + [CRISPER_COVER_TOP]:
        y0 = SHELF_Y0 + 0.015 if t in SHELF_TOPS else CRISPER_Y0 + 0.015
        for s in (-1, 1):
            xa, xb = sorted((s * (CAV_X - 0.012), s * (CAV_X + 0.002)))
            bm_box(bm, (xa, y0, t - 0.026), (xb, CAV_Y_BACK + 0.002, t - 0.014))
    ob = new_object("ShelfRibs", bm, coll, material=liner)
    finish(ob, 0.002, 1)
    tag(ob, "body")

    # Cold air duct on the back wall, with vents and a thermostat dial
    bm = bmesh.new()
    bm_box(bm, (-0.10, CAV_Y_BACK - 0.02, 1.40), (0.10, CAV_Y_BACK + 0.002, 1.72))
    ob = new_object("BackDuct", bm, coll, material=liner)
    finish(ob, 0.004, 2)
    tag(ob, "body")
    bm = bmesh.new()
    for i in range(4):
        z = 1.43 + i * 0.05
        bm_box(bm, (-0.08, CAV_Y_BACK - 0.024, z), (0.08, CAV_Y_BACK - 0.019, z + 0.02))
    bm_cyl(bm, 0.02, 0.012, cyl_matrix_y((0.0, CAV_Y_BACK - 0.026, 1.665)), 24)
    bm_box(bm, (-0.002, CAV_Y_BACK - 0.034, 1.665), (0.002, CAV_Y_BACK - 0.03, 1.683))
    ob = new_object("DuctVents", bm, coll, material=dark)
    finish(ob, 0.001, 1)
    tag(ob, "body")

    # Interior light: frame with a recessed diffuser panel
    bm = bmesh.new()
    bm_box(bm, (-0.16, -0.21, CAV_Z1 - 0.025), (0.16, -0.05, CAV_Z1 + 0.002))
    frame = new_object("LightFrame", bm, coll, material=liner)
    bm = bmesh.new()
    bm_box(bm, (-0.14, -0.19, CAV_Z1 - 0.03), (0.14, -0.07, CAV_Z1 - 0.008))
    cutter = new_object("LightCutter", bm, coll)
    boolean_cut(frame, cutter)
    finish(frame, 0.003, 2)
    bpy.data.objects.remove(cutter, do_unlink=True)
    tag(frame, "body")
    bm = bmesh.new()
    z = CAV_Z1 - 0.012
    v = [bm.verts.new(p) for p in ((-0.14, -0.19, z), (-0.14, -0.07, z), (0.14, -0.07, z), (0.14, -0.19, z))]
    bm.faces.new(v)
    ob = new_object("LightPanel", bm, coll, material=light)
    ob.data.uv_layers.new(name="UVMap")
    for li, uv in zip(ob.data.uv_layers[0].data, ((0, 0), (0, 1), (1, 1), (1, 0))):
        li.uv = uv
    tag(ob, "body")

    # Shelves: opaque frosted-glass panes in a dark trim frame
    def shelf(name, top, y0):
        bm = bmesh.new()
        bm_box(bm, (-CAV_X + 0.0025, y0, top - GLASS_T), (CAV_X - 0.0025, CAV_Y_BACK - 0.004, top))
        g = new_object(f"{name}Glass", bm, coll, material=glass)
        shade(g, 89.0)
        tag(g, "body")
        bm = bmesh.new()
        bm_box(bm, (-CAV_X + 0.0025, y0 - 0.015, top - 0.016), (CAV_X - 0.0025, y0, top + 0.006))
        for s in (-1, 1):
            xa, xb = sorted((s * (CAV_X - 0.0025), s * (CAV_X - 0.0145)))
            bm_box(bm, (xa, y0, top - 0.014), (xb, CAV_Y_BACK - 0.004, top + 0.002))
        bm_box(bm, (-CAV_X + 0.0025, CAV_Y_BACK - 0.012, top - 0.014), (CAV_X - 0.0025, CAV_Y_BACK - 0.004, top + 0.002))
        f = new_object(f"{name}Frame", bm, coll, material=dark)
        finish(f, 0.002, 1)
        tag(f, "body")

    for i, t in enumerate(SHELF_TOPS):
        shelf(f"Shelf{i + 1}", t, SHELF_Y0)
    shelf("CrisperCover", CRISPER_COVER_TOP, CRISPER_Y0)

    # Crisper drawer: origin at front-bottom-center (world 0, CRISPER_Y0, CAV_Z0)
    hw = CRISPER_W / 2
    bm = bmesh.new()
    bm_box(bm, (-hw, 0.0, 0.0), (hw, CRISPER_D, CRISPER_H))
    bm_box(bm, (-hw - 0.0075, -0.012, 0.0), (hw + 0.0075, 0.0, CRISPER_H + 0.02))  # front panel
    bm_box(bm, (-0.08, -0.030, CRISPER_H - 0.01), (0.08, -0.012, CRISPER_H + 0.02))  # grip lip
    drawer = new_object("CrisperDrawer", bm, coll, origin=(0.0, CRISPER_Y0, CAV_Z0), material=frosted)
    bm = bmesh.new()
    bm_box(bm, (-hw + 0.008, 0.008, 0.008), (hw - 0.008, CRISPER_D - 0.008, CRISPER_H + 0.05))
    bm_box(bm, (-0.06, -0.031, CRISPER_H - 0.002), (0.06, -0.02, CRISPER_H + 0.012))  # finger recess
    cutter = new_object("DrawerCutter", bm, coll, origin=(0.0, CRISPER_Y0, CAV_Z0))
    boolean_cut(drawer, cutter)
    finish(drawer, 0.003, 2)
    bpy.data.objects.remove(cutter, do_unlink=True)
    assign_by_region(drawer, [
        (((-0.081, -0.031, CRISPER_H - 0.011), (0.081, -0.0115, CRISPER_H + 0.021)), dark),
    ], frosted)
    tag(drawer, "body")

    # Collision boxes (Godot -convcolonly): one box per piece
    def col(name, lo, hi):
        bm = bmesh.new()
        bm_box(bm, lo, hi)
        ob = new_object(f"{name}-convcolonly", bm, col_coll)
        tag(ob, "body_col")
        ob.display_type = "WIRE"

    col("ColFloor", (-CAB_X, -CAB_Y, 0.0), (CAB_X, CAB_Y, CAV_Z0))
    col("ColWallLeft", (-CAB_X, -CAB_Y, CAV_Z0), (-CAV_X, CAB_Y, CAV_Z1))
    col("ColWallRight", (CAV_X, -CAB_Y, CAV_Z0), (CAB_X, CAB_Y, CAV_Z1))
    col("ColTop", (-CAB_X, -CAB_Y, CAV_Z1), (CAB_X, CAB_Y, CAB_H))
    col("ColBack", (-CAV_X, CAV_Y_BACK, CAV_Z0), (CAV_X, CAB_Y, CAV_Z1))
    for i, t in enumerate(SHELF_TOPS):
        col(f"ColShelf{i + 1}", (-CAV_X, SHELF_Y0 - 0.015, t - 0.016), (CAV_X, CAV_Y_BACK, t))
    col("ColCrisperCover", (-CAV_X, CRISPER_Y0 - 0.015, CRISPER_COVER_TOP - 0.016),
        (CAV_X, CAV_Y_BACK, CRISPER_COVER_TOP))


def build_door(coll, mats):
    steel, liner, dark, frosted = mats["steel"], mats["liner"], mats["dark"], mats["frosted"]
    rubber, paper, magnet, display = mats["rubber"], mats["paper"], mats["magnet"], mats["display"]

    # Door skin (root of the door hierarchy, origin on the hinge axis)
    bm = bmesh.new()
    bm_box(bm, (0.0, DOOR_SKIN_Y0, DOOR_Z0), (DOOR_W, DOOR_SKIN_Y1, DOOR_Z1))
    door = new_object("Door", bm, coll, origin=HINGE, material=steel)
    finish(door, 0.010, 3)
    tag(door, "door")

    def child(name, bm, material, bevel_w=None, segs=1):
        ob = new_object(name, bm, coll, material=material, parent=door)
        if bevel_w:
            finish(ob, bevel_w, segs)
        else:
            shade(ob)
        tag(ob, "door")
        return ob

    # Inner liner panel
    bm = bmesh.new()
    bm_box(bm, (0.031, DOOR_LINER_Y0, 0.118), (DOOR_W - 0.031, DOOR_LINER_Y1, DOOR_Z1 - 0.028))
    child("DoorLiner", bm, liner, 0.003, 2)

    # Gasket ring
    bm = bmesh.new()
    bm_box(bm, (0.010, GASKET_Y0, 0.098), (DOOR_W - 0.010, GASKET_Y1, DOOR_Z1 - 0.008))
    gasket = new_object("DoorGasket", bm, coll, material=rubber, parent=door)
    bm = bmesh.new()
    bm_box(bm, (0.030, GASKET_Y0 - 0.01, 0.118), (DOOR_W - 0.030, GASKET_Y1 + 0.01, DOOR_Z1 - 0.028))
    cutter = new_object("GasketCutter", bm, coll, parent=door)
    boolean_cut(gasket, cutter)
    finish(gasket, 0.003, 2)
    bpy.data.objects.remove(cutter, do_unlink=True)
    tag(gasket, "door")

    # Door bins (bottom z, front wall height)
    for i, (zb, hgt) in enumerate(((0.42, 0.12), (0.86, 0.12), (1.36, 0.10))):
        x0, x1 = 0.06, DOOR_W - 0.06
        y0, y1 = DOOR_LINER_Y1, 0.09
        w = 0.006
        bm = bmesh.new()
        bm_box(bm, (x0, y0, zb), (x1, y1, zb + w))                       # bottom
        bm_box(bm, (x0, y0, zb + w), (x0 + w, y1, zb + hgt))             # left wall
        bm_box(bm, (x1 - w, y0, zb + w), (x1, y1, zb + hgt))             # right wall
        bm_box(bm, (x0 + w, y1 - w, zb + w), (x1 - w, y1, zb + hgt))     # front wall
        bm_box(bm, (x0, y1 - 0.012, zb + hgt - 0.006), (x1, y1, zb + hgt + 0.002))  # top rim
        child(f"DoorBin{i + 1}", bm, frosted, 0.0015, 1)

    # Handle: vertical bar on two standoffs
    bm = bmesh.new()
    zc = (HANDLE_Z0 + HANDLE_Z1) / 2
    bm_cyl(bm, HANDLE_R, HANDLE_Z1 - HANDLE_Z0, Matrix.Translation((HANDLE_X, HANDLE_Y, zc)), 24)
    for z in (HANDLE_Z0 + 0.05, HANDLE_Z1 - 0.05):
        yc = (DOOR_SKIN_Y0 + HANDLE_Y) / 2
        bm_cyl(bm, 0.009, abs(HANDLE_Y - DOOR_SKIN_Y0) + 0.004, cyl_matrix_y((HANDLE_X, yc + 0.002, z)), 16)
    child("Handle", bm, steel, 0.004, 2)

    # Status display: bezel + emissive screen
    bm = bmesh.new()
    bm_box(bm, (0.43, DOOR_SKIN_Y0 - 0.003, 1.60), (0.56, DOOR_SKIN_Y0 + 0.004, 1.66))
    child("DisplayBezel", bm, dark, 0.0015, 2)
    bm = bmesh.new()
    y = DOOR_SKIN_Y0 - 0.0032
    v = [bm.verts.new(p) for p in ((0.44, y, 1.61), (0.55, y, 1.61), (0.55, y, 1.65), (0.44, y, 1.65))]
    bm.faces.new(v)
    screen = child("DisplayScreen", bm, display)
    screen.data.uv_layers.new(name="UVMap")
    for li, uv in zip(screen.data.uv_layers[0].data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        li.uv = uv

    # A note held by a magnet
    bm = bmesh.new()
    y = DOOR_SKIN_Y0 - 0.0006
    rot = Matrix.Rotation(math.radians(-4.0), 4, "Y")
    center = Vector((0.1375, y, 1.45))
    pts = []
    for dx, dz in ((-0.0375, -0.05), (0.0375, -0.05), (0.0375, 0.05), (-0.0375, 0.05)):
        p = rot @ Vector((dx, 0.0, dz))
        pts.append(center + p)
    v = [bm.verts.new(p) for p in pts]
    bm.faces.new(v)
    child("Note", bm, paper)
    bm = bmesh.new()
    bm_cyl(bm, 0.013, 0.006, cyl_matrix_y((0.1375, y - 0.003, 1.49)), 24)
    child("Magnet", bm, magnet, 0.0015, 2)

    # Grip point for the Godot handle
    grip = bpy.data.objects.new("HandleGrip", None)
    grip.empty_display_type = "SPHERE"
    grip.empty_display_size = 0.03
    grip.location = HANDLE_GRIP
    grip.parent = door
    coll.objects.link(grip)
    tag(grip, "door")
    return door


def main():
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    body_coll = get_collection("FridgeBody")
    col_coll = get_collection("FridgeBodyCollision")
    door_coll = get_collection("FridgeDoor")

    display_img = make_display_texture()
    mats = {
        "steel": mat_steel(),
        "liner": mat_liner(),
        "dark": mat_dark(),
        "frosted": mat_frosted(),
        "rubber": mat_rubber(),
        "paper": mat_paper(),
        "magnet": mat_magnet(),
        "glass": mat_glass(),
        "light": mat_light(),
        "display": mat_display(display_img),
    }

    build_body(body_coll, col_coll, mats)
    build_door(door_coll, mats)

    body = sum(tri_count(o) for o in bpy.data.objects if o.get("fridge_part") == "body")
    col = sum(tri_count(o) for o in bpy.data.objects if o.get("fridge_part") == "body_col")
    door = sum(tri_count(o) for o in bpy.data.objects if o.get("fridge_part") == "door")
    print(f"TRIS body={body} collision={col} door={door} total={body + col + door}")

    os.makedirs(os.path.dirname(BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=False)
    print("SAVED", BLEND)


if __name__ == "__main__":
    main()
