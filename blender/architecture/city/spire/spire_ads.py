"""Holo ad atlas for the spires: invented brands, Japanese text, palette neons.

Each ad is laid out in pixels of its atlas region (spire_common.AD_REGIONS)
from flat emissive shapes (vertex-colored meshes) and text objects, rendered
once with an orthographic Cycles camera into a linear float image, then
glow and faint scanlines are added per region in numpy (mipmapped texture
detail, nothing animated: Godot may swap the material for an animated one).

Font: Yu Gothic Bold from the Windows font folder (kanji and kana); Blender's
built-in font is the fallback (Latin only: the Japanese lines turn into boxes,
so the committed PNGs are the reference, not a rebuild on another OS).
"""

import math
import os
import tempfile

import bmesh
import bpy
import numpy as np

from spire_common import AD_REGIONS, ADS_SIZE
from arcology_blender import surface
from arcology_blender.trim import image_pixels

FONT_FILES = ("YuGothB.ttc", "msgothic.ttc")

MAGENTA = (1.0, 0.023, 0.15)
CYAN = (0.0015, 0.69, 0.80)
UV = (0.20, 0.028, 1.0)
AMBER = (1.0, 0.43, 0.0)
ACID = (0.022, 1.0, 0.007)
WHITE = (0.92, 0.95, 1.0)
PINK = (1.0, 0.45, 0.65)
ICE = (0.55, 0.95, 1.0)
RED = (1.0, 0.04, 0.05)


def _font():
    folder = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")
    for f in FONT_FILES:
        p = os.path.join(folder, f)
        if os.path.exists(p):
            return bpy.data.fonts.load(p, check_existing=True)
    print("ADS WARNING: no CJK font found, using Blender's built-in font")
    return bpy.data.fonts.get("Bfont Regular") or bpy.data.fonts.load("<builtin>")


class Canvas:
    """Shapes and text in atlas pixels (x right, y up), on a scene of their own."""

    def __init__(self, scene):
        self.scene = scene
        self.coll = bpy.data.collections.new("AdCanvas")
        scene.collection.children.link(self.coll)
        self.font = _font()
        self.z = 0.0
        self.vmat = bpy.data.materials.new("ad_vcol")
        self.vmat.use_nodes = True
        nt = self.vmat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "Col"
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(attr.outputs["Color"], em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        self.tmats = {}
        self.ox = self.oy = 0.0

    def region(self, name):
        x0, y0, x1, y1 = AD_REGIONS[name]
        self.ox, self.oy = x0, y0
        return x1 - x0, y1 - y0

    def _z(self):
        self.z += 0.01
        return self.z

    def poly(self, pts, colors):
        """Filled convex polygon; colors: one color or one per point (gradients)."""
        if isinstance(colors[0], (int, float)):
            colors = [colors] * len(pts)
        bm = bmesh.new()
        z = self._z()
        vs = [bm.verts.new((self.ox + x, self.oy + y, z)) for x, y in pts]
        bm.faces.new(vs)
        me = bpy.data.meshes.new("ad_shape")
        bm.to_mesh(me)
        bm.free()
        attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        for i, c in enumerate(colors):
            attr.data[i].color = (c[0], c[1], c[2], 1.0)
        me.materials.append(self.vmat)
        self.coll.objects.link(bpy.data.objects.new("ad_shape", me))

    def rect(self, x0, y0, x1, y1, c0, c1=None, vertical=True):
        c1 = c0 if c1 is None else c1
        cols = [c0, c0, c1, c1] if vertical else [c0, c1, c1, c0]
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], cols)

    def disk(self, cx, cy, r, color, inner=None, seg=96, rx=1.0, a0=0.0, a1=360.0, inner_color=None):
        """Disk, ring (inner radius), or sector (a0..a1 degrees); rx squashes it to an ellipse."""
        full = abs(a1 - a0) >= 360.0
        n = seg if full else max(8, int(seg * abs(a1 - a0) / 360.0))
        angs = [math.radians(a0 + (a1 - a0) * k / n) for k in range(n + (0 if full else 1))]
        for k in range(len(angs) - (0 if full else 1)):
            a, b = angs[k], angs[(k + 1) % len(angs)]
            pa = (cx + r * rx * math.cos(a), cy + r * math.sin(a))
            pb = (cx + r * rx * math.cos(b), cy + r * math.sin(b))
            if inner is None:
                ic = inner_color or color
                self.poly([(cx, cy), pa, pb], [ic, color, color])
            else:
                qa = (cx + inner * rx * math.cos(a), cy + inner * math.sin(a))
                qb = (cx + inner * rx * math.cos(b), cy + inner * math.sin(b))
                self.poly([qa, pa, pb, qb], color)

    def _tmat(self, color):
        key = tuple(round(c, 4) for c in color)
        if key not in self.tmats:
            m = bpy.data.materials.new("ad_text")
            m.use_nodes = True
            nt = m.node_tree
            nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs["Color"].default_value = key + (1.0,)
            nt.links.new(em.outputs[0], out.inputs["Surface"])
            self.tmats[key] = m
        return self.tmats[key]

    def text(self, s, x, y, size, color, align="CENTER", spacing=1.0, rot=0.0):
        cu = bpy.data.curves.new("ad_text", "FONT")
        cu.body = s
        cu.font = self.font
        cu.size = size
        cu.align_x = align
        cu.align_y = "CENTER"
        cu.space_character = spacing
        cu.materials.append(self._tmat(color))
        ob = bpy.data.objects.new("ad_text", cu)
        ob.location = (self.ox + x, self.oy + y, self._z())
        ob.rotation_euler = (0.0, 0.0, math.radians(rot))
        self.coll.objects.link(ob)
        return ob

    def vtext(self, s, x, y_top, size, color, step=1.08):
        """Vertical (top-down) Japanese text, one glyph per line."""
        for k, ch in enumerate(s):
            self.text(ch, x, y_top - size * step * (k + 0.5), size, color)


def _layout(c):
    # 1. KAGEROU energy drink (portrait, blade front): heat-haze can, magenta / ultraviolet
    w, h = c.region("kagerou")
    c.rect(0, 0, w, h, (0.05, 0.004, 0.16), (0.10, 0.0, 0.05))
    c.disk(540, 700, 320, (0.22, 0.0, 0.07), inner_color=(0.45, 0.02, 0.16))
    c.disk(540, 700, 340, MAGENTA, inner=322)
    for k in range(7):  # heat-haze bands behind the can
        y = 330 + k * 70
        c.rect(380, y, 760, y + 22, (0.35, 0.02, 0.5))
    c.rect(470, 260, 690, 840, UV, MAGENTA)
    c.disk(580, 840, 110, (0.75, 0.78, 0.85), rx=1.0, a0=0, a1=180)
    c.rect(470, 255, 690, 270, (0.5, 0.5, 0.55))
    c.rect(500, 300, 530, 800, (0.95, 0.6, 0.9))  # highlight
    c.vtext("陽炎", 580, 760, 120, WHITE)
    c.vtext("陽炎", 190, 1060, 300, PINK, step=1.02)
    c.text("KAGEROU", w / 2, 150, 140, (1.0, 0.25, 0.55))
    c.text("ENERGY ・ 夜勤の味方", w / 2, 60, 52, ICE)

    # 2. TENSEI cybernetics (banner): cyan ring logo, vertical katakana
    w, h = c.region("tensei")
    c.rect(0, 0, w, h, (0.0, 0.03, 0.05), (0.0, 0.10, 0.13))
    c.disk(128, 1150, 100, CYAN, inner=84)
    c.text("転", 128, 1150, 120, WHITE)
    c.rect(36, 1018, 220, 1028, CYAN)
    c.vtext("サイバネティクス", 128, 1000, 102, ICE, step=1.06)
    c.rect(36, 108, 220, 116, CYAN)
    c.text("TENSEI", 128, 60, 56, CYAN)

    # 3. RYUJIN ramen (banner): bowl icon, vertical text, magenta and amber
    w, h = c.region("ryujin")
    c.rect(0, 0, w, h, (0.10, 0.0, 0.03), (0.03, 0.0, 0.02))
    c.disk(128, 1140, 95, AMBER, a0=180, a1=360)
    c.rect(28, 1138, 228, 1150, AMBER)
    c.poly([(70, 1170), (82, 1172), (214, 1262), (205, 1268)], WHITE)
    c.poly([(95, 1168), (106, 1168), (232, 1244), (224, 1252)], WHITE)
    c.vtext("龍神ラーメン", 128, 1010, 132, (1.0, 0.2, 0.4), step=1.06)
    c.text("RYUJIN", 128, 70, 60, AMBER)

    # 4. HOSHIZORA airways (4:3): starfield, wing, cyan on navy
    w, h = c.region("hoshizora")
    c.rect(0, 0, w, h, (0.005, 0.02, 0.06), (0.0, 0.0, 0.015))
    rng = np.random.default_rng(5)
    for _ in range(40):
        c.disk(float(rng.uniform(10, w - 10)), float(rng.uniform(120, h - 10)), float(rng.uniform(2.5, 5.0)),
               (0.6, 0.85, 1.0), seg=8)
    c.poly([(60, 105), (600, 225), (560, 240), (120, 150)], [CYAN, ICE, ICE, CYAN])
    c.poly([(140, 95), (520, 170), (500, 180), (170, 118)], CYAN)
    c.text("星空航空", w / 2, 390, 118, WHITE)
    c.text("HOSHIZORA AIRWAYS", w / 2, 292, 46, CYAN)
    c.text("NEO-TOKYO ⇄ ORBIT ONE", w / 2, 40, 34, ICE)

    # 5. MIRAI bank (4:3): gradient ring logo, ultraviolet
    w, h = c.region("mirai")
    c.rect(0, 0, w, h, (0.02, 0.0, 0.06), (0.06, 0.0, 0.10))
    c.disk(150, 280, 125, (0.6, 0.1, 1.0), inner=95)
    c.disk(150, 280, 70, MAGENTA, inner_color=(1.0, 0.5, 0.8))
    c.text("未来銀行", 430, 330, 92, WHITE)
    c.text("MIRAI BANK", 430, 215, 56, (0.7, 0.45, 1.0))
    c.text("あなたの未来を守る", w / 2, 70, 40, PINK)

    # 6. KUSURI 24 h pharmacy (2:1): acid green cross (the palette's rare highlight)
    w, h = c.region("kusuri")
    c.rect(0, 0, w, h, (0.0, 0.03, 0.01))
    c.rect(55, 130, 215, 190, ACID)
    c.rect(105, 80, 165, 240, ACID)
    c.text("薬", 380, 190, 190, WHITE)
    c.text("24H", 545, 220, 70, AMBER)
    c.text("KUSURI", 470, 60, 62, (0.4, 1.0, 0.4))

    # 7. Stock ticker (5.6:1)
    w, h = c.region("ticker")
    c.rect(0, 0, w, h, (0.01, 0.01, 0.02))
    c.rect(0, 140, w, 148, AMBER)
    c.rect(0, 12, w, 20, AMBER)
    c.text("▲ KAGEROU 4,520", 20, 80, 46, (0.3, 1.0, 0.5), align="LEFT")
    c.text("▼ MIRAI 980", 420, 80, 46, (1.0, 0.25, 0.3), align="LEFT")
    c.text("▲ 転生 12,880", 680, 80, 46, AMBER, align="LEFT")

    # 8. SORAKAZE hover cars (4:3): retro sunset, a car wedge over the horizon
    w, h = c.region("sorakaze")
    c.rect(0, 300, w, h, (0.32, 0.01, 0.14), (0.03, 0.0, 0.09))
    c.rect(0, 0, w, 300, (0.0, 0.01, 0.04), (0.08, 0.0, 0.10))
    c.disk(330, 300, 210, (1.0, 0.3, 0.2), a0=0, a1=180, inner_color=(1.0, 0.75, 0.3))
    for k in range(5):
        y = 320 + k * 34
        c.rect(110, y, 550, y + 9 + k, (0.32, 0.01, 0.14))
    c.poly([(80, 230), (560, 270), (620, 330), (380, 360), (180, 300)], (0.02, 0.02, 0.04))
    c.poly([(80, 230), (560, 270), (566, 262), (90, 222)], CYAN)
    c.poly([(330, 340), (520, 318), (480, 345)], ICE)
    c.text("空風", 800, 560, 220, WHITE)
    c.text("SORAKAZE", 800, 390, 78, CYAN)
    c.text("NEW S-9 HOVER", 800, 300, 44, ICE)
    c.text("空を走れ。", w / 2, 90, 64, PINK)

    # 9. OKAMI security (4:3): the watching eye, red and magenta
    w, h = c.region("okami")
    c.rect(0, 0, w, h, (0.02, 0.0, 0.0), (0.09, 0.0, 0.03))
    c.text("狼", 250, 420, 440, (1.0, 0.06, 0.18))
    c.disk(720, 520, 120, (0.9, 0.9, 0.95), inner=104, rx=1.9)
    c.disk(720, 520, 70, RED, inner_color=(1.0, 0.5, 0.4))
    c.disk(720, 520, 26, (0.0, 0.0, 0.0))
    c.text("見ている。", 720, 330, 80, WHITE)
    c.text("OKAMI SECURITY", w / 2, 130, 72, MAGENTA)
    c.text("WE ARE WATCHING", w / 2, 55, 36, (0.9, 0.5, 0.6))


def _post(em):
    """Glow and faint scanlines, per region (nothing bleeds between ads)."""
    out = em.copy()
    for name, (x0, y0, x1, y1) in AD_REGIONS.items():
        pad = 40
        crop = np.zeros((y1 - y0 + 2 * pad, x1 - x0 + 2 * pad, 3))
        crop[pad:-pad, pad:-pad] = em[y0:y1, x0:x1]
        glow = surface.blur(crop, 5.0) * 0.30 + surface.blur(crop, 18.0) * 0.22
        r = crop + glow
        rows = np.arange(r.shape[0])[:, None, None]
        r = r * (0.94 + 0.06 * np.cos(2 * math.pi * rows / 6.0))
        out[y0:y1, x0:x1] = r[pad:-pad, pad:-pad]
    return np.clip(out, 0.0, 1.0)


def render_atlas(samples=24):
    """Render the atlas in a temporary scene; returns linear (h, w, 3) emission."""
    old = bpy.context.window.scene if bpy.context.window else bpy.context.scene
    scene = bpy.data.scenes.new("AdAtlas")
    if bpy.context.window:
        bpy.context.window.scene = scene
    c = Canvas(scene)
    _layout(c)
    cam = bpy.data.objects.new("AdCam", bpy.data.cameras.new("AdCam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = ADS_SIZE
    cam.data.clip_start, cam.data.clip_end = 0.1, 100.0
    cam.location = (ADS_SIZE / 2, ADS_SIZE / 2, 50.0)
    c.coll.objects.link(cam)
    scene.camera = cam
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 0
    scene.render.filter_size = 1.2
    scene.render.resolution_x = scene.render.resolution_y = ADS_SIZE
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.world = bpy.data.worlds.new("AdWorld")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    path = os.path.join(tempfile.gettempdir(), "arcology_city_spire_ads.exr")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=scene.name)
    img = bpy.data.images.load(path)
    em = np.array(image_pixels(img), dtype=np.float64)
    bpy.data.images.remove(img)
    # clean up the canvas scene and its data
    for ob in list(c.coll.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)
        elif isinstance(data, bpy.types.Camera):
            bpy.data.cameras.remove(data)
    bpy.data.collections.remove(c.coll)
    for m in [c.vmat] + list(c.tmats.values()):
        bpy.data.materials.remove(m)
    world = scene.world
    if bpy.context.window:
        bpy.context.window.scene = old
    bpy.data.scenes.remove(scene)
    bpy.data.worlds.remove(world)
    for f in list(bpy.data.fonts):
        if f.users == 0:
            bpy.data.fonts.remove(f)
    return _post(em)
