"""Silena's glove leather: one procedural source material (`src_leather`) for every
part of the glove, baked into albedo/normal/ORM by bake.py.

Black aniline-finish leather with a fine pebbled grain and soft crinkles; side
seams on every finger (a pressed seam line with a row of fine stitches on the
back's side, running over the fingertip); creases across the back of the
finger joints and flexion creases on the palm side; an embossed filigree panel
on the back of the hand and a running scroll under the cuff's hem, tone on
tone with a faint deep-violet sheen (albedo/normal only, never emissive); a
burnished, slightly worn palm and lighter worn edges (knuckles, fingertips,
the cuff's rolled hem, the strap's edges); suede lining inside the cuff; a
dark gunmetal snap. The per-vertex coordinates come from glove.py.
"""

import bpy

from silena_vesper_common import (
    FILIGREE, GUNMETAL, GUNMETAL_DARK, LEATHER, LEATHER_WORN, LINING, STRAP_W, THREAD,
)
import filigree
from arcology_blender.shading import Graph, new_mat

STITCH = 0.0021          # stitch length along a seam
BAND_REPEATS = 6         # cuff scroll motifs around the cuff
BAND_CENTER = 0.0175     # cuff scroll band: distance below the cuff's edge
HEM_STITCH = 0.0045      # stitch row below the cuff's edge
FINGER_STITCH = 0.0012   # stitch row beside a finger seam (toward the back of the finger)
CUFF_STITCH = 0.0016     # stitch rows on both sides of the cuff seam


class Leather(Graph):
    """Graph with the node types this material needs beyond the toolkit's."""

    def uv(self, name):
        n = self.nodes.new("ShaderNodeUVMap")
        n.uv_map = name
        sep = self.nodes.new("ShaderNodeSeparateXYZ")
        self.links.new(n.outputs["UV"], sep.inputs[0])
        return sep.outputs[0], sep.outputs[1]

    def image(self, img, u, v, extension="CLIP"):
        t = self.nodes.new("ShaderNodeTexImage")
        t.image = img
        t.extension = extension
        t.interpolation = "Cubic"
        self.links.new(self.combine(u, v, 0.0), t.inputs["Vector"])
        sep = self.nodes.new("ShaderNodeSeparateColor")
        self.links.new(t.outputs["Color"], sep.inputs[0])
        return sep.outputs[0], sep.outputs[1]

    def voronoi_edge(self, scale, vector=None, randomness=1.0):
        n = self.nodes.new("ShaderNodeTexVoronoi")
        n.feature = "DISTANCE_TO_EDGE"
        n.inputs["Scale"].default_value = scale
        n.inputs["Randomness"].default_value = randomness
        self.links.new(vector if vector is not None else self.geo.outputs["Position"], n.inputs["Vector"])
        return n.outputs["Distance"]

    def abs(self, a):
        return self.math("ABSOLUTE", a)

    def frac(self, a):
        return self.math("FRACT", a)

    def cos(self, a):
        return self.math("COSINE", a)

    def dot_n(self, d):
        """World normal . constant direction."""
        return self.add(self.add(self.mul(self.nx, d[0]), self.mul(self.ny, d[1])), self.mul(self.nz, d[2]))

    def stitches(self, dist, along, width=0.00034, length=STITCH):
        """(thread, holes) masks of a stitch row: `dist` = distance from the row's line,
        `along` = distance along it."""
        lateral = self.maprange(dist, width * 0.5, width * 0.15)
        f = self.frac(self.mul(along, 1.0 / length))
        dash = self.band(f, 0.14, 0.76, 0.07)
        hole = self.mul(self.maprange(dist, width * 0.55, 0.0), self.band(f, 0.84, 0.96, 0.03))
        return self.mul(lateral, dash), hole


def src_leather(hf):
    panel_img, band_img = filigree.images()
    g = Leather(new_mat("src_leather"))
    attr = g.attribute
    region = attr("region")
    shell = g.maprange(region, 0.45, 0.05)
    cuff = g.band(region, 0.9, 1.1, 0.35)
    hem = g.band(region, 1.9, 2.1, 0.35)
    lining = g.band(region, 2.9, 3.1, 0.35)
    strap = g.band(region, 3.9, 5.1, 0.35)
    snap = g.maprange(region, 5.5, 5.9)
    leather = g.sub(1.0, g.add(lining, snap))

    # --- grain and crinkles (all leather) ----------------------------------------------
    cells = g.voronoi_edge(1.0 / 0.0010)
    cells2 = g.voronoi_edge(1.0 / 0.0018, g.offset((0.37, 0.11, 0.53)))
    mixcell = g.maprange(g.noise(60.0, 2.0), 0.4, 0.6)
    pore = g.mixf(mixcell, g.maprange(cells, 0.10, 0.0), g.maprange(cells2, 0.07, 0.0))
    h = g.mul(pore, -0.000014)
    crinkle = g.maprange(g.abs(g.sub(g.noise(1.0 / 0.006, 4.0, 0.55), 0.5)), 0.035, 0.0)
    h = g.add(h, g.mul(crinkle, -0.000025))
    h = g.mul(h, leather)

    # --- finger seams and stitches ----------------------------------------------------------
    fs, fu, fj, fjk, fm = attr("fs"), attr("fu"), attr("fj"), attr("fjk"), attr("fm")
    fmask = g.mul(g.maprange(fm, 0.35, 0.75), shell)
    afs = g.abs(fs)
    seam = g.mul(g.maprange(afs, 0.00035, 0.0), fmask)
    welt = g.mul(g.band(afs, 0.0004, 0.0010, 0.0003), fmask)
    thread_f, hole_f = g.stitches(g.abs(g.sub(fs, FINGER_STITCH)), fu)
    thread_f, hole_f = g.mul(thread_f, fmask), g.mul(hole_f, fmask)
    h = g.add(h, g.add(g.mul(seam, -0.00022), g.mul(welt, 0.00006)))

    # --- creases at the finger joints ---------------------------------------------------------
    back = g.maprange(fs, 0.0012, 0.0040)
    palmar = g.maprange(fs, -0.0012, -0.0040)
    wobble = g.mul(g.sub(g.noise(1.0 / 0.003, 2.0), 0.5), 0.0005)
    fjw = g.add(fj, g.add(wobble, g.mul(g.mul(fs, fs), 18.0)))  # creases bow toward the tip at the sides
    near = g.maprange(g.abs(fj), 0.0050, 0.0022)
    outer = g.band(fjk, 0.7, 2.3, 0.2)
    waves = g.maprange(g.cos(g.mul(fjw, 6.2832 / 0.0016)), 0.72, 1.0)
    h = g.add(h, g.mul(g.mul(g.mul(waves, near), g.mul(back, outer)), g.mul(fmask, -0.00013)))
    flex = g.maprange(g.abs(g.sub(fjw, 0.0004)), 0.0007, 0.0)
    h = g.add(h, g.mul(g.mul(flex, palmar), g.mul(g.maprange(fm, 0.3, 0.6), g.mul(shell, -0.0002))))
    knuckle = g.mul(g.mul(g.band(fjk, -0.3, 0.3, 0.2), g.maprange(g.abs(fj), 0.006, 0.002)), g.mul(back, fmask))

    # --- filigree on the back of the hand ------------------------------------------------------
    ou, ov = g.uv("OrnUV")
    s = 1.0 / filigree.PANEL_SIZE
    orn_h, orn_m = g.image(panel_img, g.add(g.mul(ou, s), 0.5), g.add(g.mul(ov, s), 0.5), "CLIP")
    hd = attr("hd")
    dorsal = g.maprange(hd, 0.30, 0.60)
    panel = g.mul(g.mul(shell, dorsal), g.sub(1.0, g.maprange(fm, 0.2, 0.5)))
    h = g.add(h, g.mul(g.mul(orn_h, panel), 0.00011))
    orn = g.mul(orn_m, panel)

    # --- cuff: seam, hem stitching, scroll band ----------------------------------------------------
    ct, ca, cs = attr("ct"), attr("ca"), attr("cs")
    cu, cv = g.uv("CuffUV")
    cseam = g.mul(g.maprange(cs, 0.00035, 0.0), cuff)
    cwelt = g.mul(g.band(cs, 0.0004, 0.0011, 0.0003), cuff)
    h = g.add(h, g.add(g.mul(cseam, -0.00024), g.mul(cwelt, 0.00007)))
    thread_c, hole_c = g.stitches(g.abs(g.sub(cs, CUFF_STITCH)), cv)
    thread_h, hole_h = g.stitches(g.abs(g.sub(ct, HEM_STITCH)), cu)
    away = g.maprange(cs, 0.0025, 0.004)
    thread_h, hole_h = g.mul(thread_h, g.mul(cuff, away)), g.mul(hole_h, g.mul(cuff, away))
    thread_c, hole_c = g.mul(thread_c, g.mul(cuff, g.maprange(ct, 0.0, 0.002))), g.mul(hole_c, cuff)
    turn = g.mul(g.maprange(g.abs(g.sub(ct, 0.0026)), 0.0004, 0.0), cuff)  # where the folded hem ends
    h = g.add(h, g.mul(turn, -0.00008))
    by = g.add(g.mul(g.sub(ct, BAND_CENTER), 1.0 / filigree.BAND_HEIGHT), 0.5)
    band_h, band_m = g.image(band_img, g.mul(ca, float(BAND_REPEATS)), by, "REPEAT")
    band_mask = g.mul(g.mul(cuff, g.band(by, 0.02, 0.98, 0.02)), g.maprange(cs, 0.006, 0.010))
    h = g.add(h, g.mul(g.mul(band_h, band_mask), 0.0001))
    orn = g.add(orn, g.mul(band_m, band_mask))
    cuff_wrinkle = g.maprange(g.noise(1.0, 3.0, 0.5, g.combine(g.mul(cu, 45.0), g.mul(ct, 420.0), 0.0)), 0.55, 0.7)
    h = g.add(h, g.mul(g.mul(cuff_wrinkle, cuff), -0.00004))

    # --- strap and tab: stitched edges, painted edge -------------------------------------------------
    su, sv = cu, cv
    asv = g.abs(sv)
    thread_s, hole_s = g.stitches(g.abs(g.sub(asv, STRAP_W * 0.5 - 0.0016)), su)
    thread_s, hole_s = g.mul(thread_s, strap), g.mul(hole_s, strap)
    strap_edge = g.mul(g.maprange(asv, STRAP_W * 0.5 - 0.0009, STRAP_W * 0.5 - 0.0002), strap)

    thread = g.add(g.add(thread_f, thread_c), g.add(thread_h, thread_s))
    holes = g.add(g.add(hole_f, hole_c), g.add(hole_h, hole_s))
    h = g.add(h, g.add(g.mul(thread, 0.00013), g.mul(holes, -0.00009)))

    # --- snap: domed gunmetal cap, a pressed ring, worn rim --------------------------------------------
    rho = g.math("SQRT", g.add(g.mul(su, su), g.mul(sv, sv)))
    ring = g.mul(g.maprange(g.abs(g.sub(rho, 0.0034)), 0.00035, 0.0), snap)
    h = g.add(h, g.mul(ring, -0.00012))
    spun = g.noise(1.0, 2.0, 0.5, g.combine(g.mul(rho, 9000.0), 0.0, 0.0))
    h = g.add(h, g.mul(g.mul(spun, snap), 0.000004))

    # --- color and roughness ---------------------------------------------------------------------------
    mottle = g.add(0.82, g.mul(g.noise(1.0 / 0.025, 3.0, 0.55), 0.36))
    base = g.scale_color(LEATHER, mottle)
    rough = g.add(0.43, g.mul(g.sub(g.noise(1.0 / 0.012, 3.0), 0.5), 0.12))
    # worn: convex edges (knuckles, fingertips, hem, strap edges) lighter and smoother
    edge = g.maprange(g.pointiness(), 0.545, 0.62)
    patchy = g.maprange(g.noise(1.0 / 0.006, 4.0, 0.6), 0.35, 0.65)
    worn = g.add(g.mul(g.mul(edge, patchy), 0.45), g.mul(knuckle, 0.30))
    worn = g.add(worn, g.mul(hem, 0.45))
    base = g.mixc(g.mul(worn, leather), base, LEATHER_WORN)
    rough = g.sub(rough, g.mul(worn, 0.10))
    # palm: burnished and a little lighter from holding things
    palm = g.mul(g.maprange(hd, -0.15, -0.6), shell)
    rub = g.mul(palm, g.maprange(g.noise(1.0 / 0.01, 3.0), 0.3, 0.7))
    base = g.mixc(g.mul(rub, 0.35), base, LEATHER_WORN)
    rough = g.sub(rough, g.mul(palm, 0.09))
    # creases collect a little darker, drier finish
    crease_dark = g.add(g.mul(g.mul(waves, near), g.mul(back, fmask)), g.add(seam, cseam))
    base = g.scale_color(base, g.sub(1.0, g.mul(crease_dark, 0.35)))
    rough = g.add(rough, g.mul(crease_dark, 0.08))
    # filigree: tone on tone with a faint violet sheen, slightly glossier
    base = g.mixc(g.mul(orn, 0.30), base, tuple(c * 0.28 for c in FILIGREE))
    rough = g.sub(rough, g.mul(orn, 0.10))
    # strap edge paint: darker and glossy
    base = g.mixc(g.mul(strap_edge, 0.8), base, (0.004, 0.0036, 0.0045))
    rough = g.sub(rough, g.mul(strap_edge, 0.12))
    # thread
    base = g.mixc(thread, base, THREAD)
    rough = g.mixf(thread, rough, 0.62)
    # lining: dull suede
    suede = g.add(0.85, g.mul(g.noise(1.0 / 0.0006, 2.0), 0.3))
    base = g.mixc(lining, base, g.scale_color(LINING, suede))
    rough = g.mixf(lining, rough, 0.88)
    # snap
    rim = g.maprange(rho, 0.0040, 0.0050)
    metal_col = g.mixc(g.mul(g.add(rim, g.mul(g.maprange(g.pointiness(), 0.55, 0.62), 0.5)), 0.6),
                       GUNMETAL, (0.22, 0.225, 0.235))
    metal_col = g.mixc(g.maprange(rho, 0.0018, 0.0), metal_col, GUNMETAL_DARK)
    base = g.mixc(snap, base, metal_col)
    rough = g.mixf(snap, rough, g.add(0.30, g.mul(spun, 0.08)))
    return g.finish_height(base, rough, snap, h)


def remove_images():
    for name in ("filigree_panel", "filigree_band"):
        img = bpy.data.images.get(name)
        if img is not None:
            bpy.data.images.remove(img)
