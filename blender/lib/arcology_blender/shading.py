"""Materials: the `Graph` builder for procedural sources, plain and emissive materials, bitmap text.

Procedural materials are baked (see bake.py), so they can use anything Cycles
can render: world-position masks, pointiness, noise. Name them `src_*`.
Materials that stay unbaked (glass, lights, screens) are plain Principled
BSDFs, so glTF exports them losslessly.
"""

import bpy
import numpy as np

from .scene import set_colorspace


def new_mat(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


class Graph:
    """Builds a Principled BSDF node graph with world-position driven masks.

    Every method takes floats, colors (3- or 4-tuples) or node sockets and
    returns a socket. `x`, `y`, `z` are the world position, `nx`, `ny`, `nz`
    the world normal.
    """

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
        """Clamped remap; fmin > fmax inverts (1 below fmax, 0 above fmin)."""
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
        return self.mul(self.maprange(v, lo - soft, lo), self.maprange(v, hi + soft, hi))

    def rect_xz(self, lo, hi, soft=0.003):
        """1 inside an x/z rectangle (world), e.g. a decal on a -Y facing front."""
        return self.mul(self.band(self.x, lo[0], hi[0], soft), self.band(self.z, lo[1], hi[1], soft))

    def vec(self, sx, sy, sz):
        """Scaled world position, for stretched noise (e.g. horizontal scuffs)."""
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
        self.links.new(vector if vector is not None else self.geo.outputs["Position"], n.inputs["Vector"])
        return n.outputs["Fac"]

    def wave(self, scale, distortion, detail=2.0, direction="X"):
        n = self.nodes.new("ShaderNodeTexWave")
        n.wave_type = "BANDS"
        n.bands_direction = direction
        n.inputs["Scale"].default_value = scale
        n.inputs["Distortion"].default_value = distortion
        n.inputs["Detail"].default_value = detail
        self.links.new(self.geo.outputs["Position"], n.inputs["Vector"])
        return n.outputs["Fac"]

    def pointiness(self):
        return self.geo.outputs["Pointiness"]

    def attribute(self, name):
        """Float value of a mesh attribute (interpolated across faces)."""
        n = self.nodes.new("ShaderNodeAttribute")
        n.attribute_type = "GEOMETRY"
        n.attribute_name = name
        return n.outputs["Fac"]

    def dist_xy(self, cx, cy):
        """Distance in world x/y from (cx, cy)."""
        dx, dy = self.sub(self.x, cx), self.sub(self.y, cy)
        return self.math("SQRT", self.add(self.mul(dx, dx), self.mul(dy, dy)))

    def _mix(self, dtype, fac, a, b):
        n = self.nodes.new("ShaderNodeMix")
        n.data_type = dtype
        n.clamp_factor = True
        self._set(n.inputs[0], fac)
        stype = {"FLOAT": "VALUE", "RGBA": "RGBA", "VECTOR": "VECTOR"}[dtype]
        self._set([s for s in n.inputs if s.name == "A" and s.type == stype][0], a)
        self._set([s for s in n.inputs if s.name == "B" and s.type == stype][0], b)
        return [s for s in n.outputs if s.name == "Result" and s.type == stype][0]

    def mixf(self, fac, a, b):
        return self._mix("FLOAT", fac, a, b)

    def mixc(self, fac, a, b):
        return self._mix("RGBA", fac, a, b)

    def scale_color(self, col, f):
        """Color times a float (socket or constant)."""
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
        """Connect the final values to the BSDF and return the material."""
        self._set(self.bsdf.inputs["Base Color"], base)
        if isinstance(rough, bpy.types.NodeSocket):
            rough = self.math("ADD", rough, 0.0, clamp=True)
        self._set(self.bsdf.inputs["Roughness"], rough)
        self._set(self.bsdf.inputs["Metallic"], metal)
        if normal is not None:
            self.links.new(normal, self.bsdf.inputs["Normal"])
        return self.mat


def solid_mat(name, base, rough, metal=0.0, emission=None, emission_strength=0.0):
    """Plain (unbaked) Principled material, e.g. opaque glass or a light panel."""
    m = new_mat(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = tuple(base) + (1.0,)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emission is not None:
        b.inputs["Emission Color"].default_value = tuple(emission) + (1.0,)
        b.inputs["Emission Strength"].default_value = emission_strength
    return m


def emissive_image_mat(name, image, base=(0.01, 0.01, 0.012), rough=0.12, strength=2.5):
    """Screen or sign: a dark glossy surface emitting an image."""
    m = solid_mat(name, base, rough)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Emission Strength"].default_value = strength
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    return m


# --- Bitmap text for displays and signs -----------------------------------------
# 5x7 glyphs; add characters as needed.
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


def pixel_canvas(w, h, color):
    """HxWx4 float array filled with an opaque color (row 0 is the bottom, as Blender stores it)."""
    img = np.zeros((h, w, 4), dtype=np.float32)
    img[..., :3] = color
    img[..., 3] = 1.0
    return img


def fill_rect(img, x0, y0, x1, y1, color):
    """Fill pixels x0..x1, y0..y1 measured from the top-left corner (y grows downward)."""
    h = img.shape[0]
    img[h - y1:h - y0, x0:x1, :3] = color


def draw_text(img, text, x0, y0, cell, color):
    """Draw glyphs into a canvas; (x0, y0) is the top-left corner, y grows downward."""
    h = img.shape[0]
    for ci, ch in enumerate(text):
        for r, row in enumerate(GLYPHS.get(ch, GLYPHS[" "])):
            for c, bit in enumerate(row):
                if bit == "1":
                    xs = x0 + (ci * 6 + c) * cell
                    ys = y0 + r * cell
                    img[h - ys - cell:h - ys, xs:xs + cell, :3] = color


def canvas_image(name, img):
    """Packed sRGB image from a canvas."""
    h, w = img.shape[:2]
    image = bpy.data.images.new(name, w, h, alpha=False)
    set_colorspace(image, "sRGB")
    image.pixels.foreach_set(img.ravel())
    image.pack()
    return image
