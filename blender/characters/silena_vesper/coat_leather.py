"""Silena's coat leather: the procedural source material of the sleeve (`src_coat`),
baked into its own albedo/normal/ORM set by bake.py.

Heavier, suppler black leather than the glove: a coarser pebbled grain, soft long
draw lines along the forearm, compression creases in the crook of the elbow; the
outer sleeve seam pressed open with a topstitch row on each side, the inner seam
pressed; the armhole's piped seam with a stitch row below it; the turned-back
cuff with a stitch row above the fold and below its top edge. Violet satin-stitch
embroidery (`embroidery.py`): a vine along the outer sleeve and an ornament on the
cuff over the back of the wrist, real relief and thread sheen (albedo, never
emissive). Worn: lighter, smoother edges (the opening's fold, the cuff's edge,
seam welts, fold crests), a burnished elbow. A violet satin lining shows in the
opening; the dome inside the armhole is black lining. Per-vertex data from
sleeve.py.
"""

from silena_vesper_common import COAT_LINING, CUFF_TOP_T, FILIGREE, LEATHER, LEATHER_WORN, SLEEVE_OPEN_T, THREAD
import embroidery
from leather import Leather
from arcology_blender.shading import new_mat

COAT_STITCH = 0.0032     # stitch length
SEAM_ROW = 0.0042        # topstitch rows beside the outer seam
CUFF_ROWS = (0.0058, CUFF_TOP_T - SLEEVE_OPEN_T - 0.0062)  # above the fold, below the cuff's edge
ARMHOLE_ROW = 0.0065     # below the armhole seam
BAND_T0 = CUFF_TOP_T + 0.014   # the vine starts above the cuff ...
BAND_TOP_GAP = 0.052           # ... and ends this far below the shoulder joint
PANEL_CT0 = 0.0095             # cuff ornament: from this far above the fold


class Coat(Leather):
    def image3(self, img, u, v):
        t = self.nodes.new("ShaderNodeTexImage")
        t.image = img
        t.extension = "CLIP"
        t.interpolation = "Cubic"
        self.links.new(self.combine(u, v, 0.0), t.inputs["Vector"])
        sep = self.nodes.new("ShaderNodeSeparateColor")
        self.links.new(t.outputs["Color"], sep.inputs[0])
        return sep.outputs[0], sep.outputs[1], sep.outputs[2]


def band_range(sf):
    """(t0, length) of the vine along the sleeve, meters."""
    return BAND_T0, (sf.t_S - BAND_TOP_GAP) - BAND_T0


def src_coat(sf):
    t0, length = band_range(sf)
    band_img, panel_img = embroidery.images(length * 1000.0)
    g = Coat(new_mat("src_coat"))
    attr = g.attribute
    region = attr("region")
    lining = g.maprange(region, 0.45, 0.05)
    fold = g.band(region, 0.9, 1.1, 0.35)
    cuff = g.band(region, 1.9, 2.1, 0.35)
    lip = g.band(region, 2.9, 4.1, 0.35)
    body = g.band(region, 4.9, 5.1, 0.35)
    seam_r = g.band(region, 5.9, 6.1, 0.35)
    cap = g.maprange(region, 6.5, 6.9)
    leather = g.sub(1.0, g.add(lining, cap))
    so, si, ct, at = attr("so"), attr("si"), attr("ct"), attr("at")
    crook, rub = attr("crook"), attr("rub")
    ou, ov = g.uv("OrnUV")

    # --- grain, crinkles, draw lines -------------------------------------------------
    cells = g.voronoi_edge(1.0 / 0.0016)
    cells2 = g.voronoi_edge(1.0 / 0.0029, g.offset((0.41, 0.17, 0.29)))
    mixcell = g.maprange(g.noise(45.0, 2.0), 0.4, 0.6)
    pore = g.mixf(mixcell, g.maprange(cells, 0.11, 0.0), g.maprange(cells2, 0.08, 0.0))
    h = g.mul(pore, -0.000020)
    crinkle = g.maprange(g.abs(g.sub(g.noise(1.0 / 0.011, 4.0, 0.55), 0.5)), 0.03, 0.0)
    h = g.add(h, g.mul(crinkle, -0.000040))
    draw = g.noise(1.0, 2.0, 0.45, g.combine(g.mul(ou, 45.0), g.mul(ov, 7.0), 0.0))
    draw_line = g.mul(g.maprange(g.abs(g.sub(draw, 0.5)), 0.07, 0.0), g.maprange(g.noise(1.0 / 0.05, 2.0), 0.45, 0.6))
    h = g.add(h, g.mul(g.mul(draw_line, body), -0.00005))
    h = g.mul(h, leather)

    # --- crook of the elbow: compression creases across the arm -------------------------
    wob = g.mul(g.sub(g.noise(1.0, 2.0, 0.5, g.combine(g.mul(ou, 35.0), g.mul(ov, 35.0), 0.0)), 0.5), 0.010)
    crease_phase = g.mul(g.add(ov, g.add(wob, g.mul(g.abs(ou), 0.12))), 6.2832 / 0.0085)
    crease = g.mul(g.maprange(g.cos(crease_phase), 0.80, 1.0), crook)
    h = g.add(h, g.mul(crease, -0.00022))

    # --- seams and stitches --------------------------------------------------------------
    seam_mask = g.add(g.add(body, cuff), g.add(fold, lip))
    groove_o = g.mul(g.maprange(so, 0.00045, 0.0), seam_mask)
    welt_o = g.mul(g.band(so, 0.0006, 0.0020, 0.0004), seam_mask)
    groove_i = g.mul(g.maprange(si, 0.00040, 0.0), seam_mask)
    welt_i = g.mul(g.band(si, 0.0005, 0.0016, 0.0004), seam_mask)
    h = g.add(h, g.add(g.mul(groove_o, -0.00032), g.mul(welt_o, 0.00010)))
    h = g.add(h, g.add(g.mul(groove_i, -0.00026), g.mul(welt_i, 0.00007)))
    thr_o, hole_o = g.stitches(g.abs(g.sub(so, SEAM_ROW)), ov, width=0.00045, length=COAT_STITCH)
    thr_o, hole_o = g.mul(thr_o, g.add(body, cuff)), g.mul(hole_o, g.add(body, cuff))
    # cuff rows (around the cuff, along the ornament coordinate)
    thr_c, hole_c = g.stitches(g.abs(g.sub(ct, CUFF_ROWS[0])), ou, width=0.00045, length=COAT_STITCH)
    thr_c2, hole_c2 = g.stitches(g.abs(g.sub(ct, CUFF_ROWS[1])), ou, width=0.00045, length=COAT_STITCH)
    thr_c, hole_c = g.mul(g.add(thr_c, thr_c2), cuff), g.mul(g.add(hole_c, hole_c2), cuff)
    # armhole row
    thr_a, hole_a = g.stitches(g.abs(g.sub(at, ARMHOLE_ROW)), ou, width=0.00045, length=COAT_STITCH)
    thr_a, hole_a = g.mul(thr_a, body), g.mul(hole_a, body)
    # the piped armhole seam: a groove where the piping meets the sleeve
    pipe_groove = g.mul(g.maprange(g.abs(g.sub(at, 0.0034)), 0.0005, 0.0), g.add(body, seam_r))
    h = g.add(h, g.mul(pipe_groove, -0.00025))
    thread = g.add(g.add(thr_o, thr_c), thr_a)
    holes = g.add(g.add(hole_o, hole_c), hole_a)
    h = g.add(h, g.add(g.mul(thread, 0.00016), g.mul(holes, -0.00011)))
    # cuff: a pressed line where the leather turns at the fold and under the edge
    h = g.add(h, g.mul(g.mul(g.maprange(g.abs(g.sub(ct, 0.0028)), 0.0005, 0.0), cuff), -0.00008))

    # --- embroidery ------------------------------------------------------------------------
    bx = g.add(g.mul(ou, 1000.0 / embroidery.BAND_W), 0.5)
    by = g.mul(g.sub(ov, t0), 1.0 / length)
    eh, em, et = g.image3(band_img, bx, by)
    px = g.add(g.mul(ou, 1000.0 / embroidery.PANEL_W), 0.5)
    py = g.mul(g.sub(ct, PANEL_CT0), 1000.0 / embroidery.PANEL_H)
    ph, pm, pth = g.image3(panel_img, px, py)
    on_band = g.mul(body, g.maprange(g.abs(ou), 0.035, 0.030))   # never the far side of the sleeve
    on_panel = g.mul(cuff, g.maprange(g.abs(ou), 0.060, 0.055))
    e_h = g.add(g.mul(eh, on_band), g.mul(ph, on_panel))
    e_m = g.add(g.mul(em, on_band), g.mul(pm, on_panel))
    e_t = g.add(g.mul(et, on_band), g.mul(pth, on_panel))
    h = g.add(h, g.mul(e_h, 0.00045))
    h = g.add(h, g.mul(g.mul(g.sub(e_t, 0.5), e_m), 0.00009))

    # --- color and roughness --------------------------------------------------------------------
    mottle = g.add(0.84, g.mul(g.noise(1.0 / 0.030, 3.0, 0.55), 0.32))
    base = g.scale_color(LEATHER, mottle)
    rough = g.add(0.50, g.mul(g.sub(g.noise(1.0 / 0.015, 3.0), 0.5), 0.10))
    # worn: convex crests (fold edges, the cuff's edge, fold ridges, seam welts) and the elbow
    edge = g.maprange(g.pointiness(), 0.53, 0.60)
    patchy = g.maprange(g.noise(1.0 / 0.008, 4.0, 0.6), 0.35, 0.65)
    worn = g.mul(g.mul(edge, patchy), 0.40)
    worn = g.add(worn, g.mul(g.add(fold, g.mul(lip, 0.8)), 0.45))
    worn = g.add(worn, g.mul(g.add(welt_o, welt_i), 0.25))
    worn = g.add(worn, g.mul(rub, g.add(0.10, g.mul(patchy, 0.18))))
    rough = g.sub(rough, g.mul(rub, 0.08))   # the elbow's point is burnished more than lightened
    worn = g.mul(worn, leather)
    base = g.mixc(g.mul(worn, 0.85), base, LEATHER_WORN)
    rough = g.sub(rough, g.mul(worn, 0.12))
    # creases and grooves collect a darker, drier finish
    dark = g.add(g.add(crease, g.mul(draw_line, g.mul(body, 0.5))), g.add(groove_o, g.add(groove_i, pipe_groove)))
    base = g.scale_color(base, g.sub(1.0, g.mul(dark, 0.30)))
    rough = g.add(rough, g.mul(dark, 0.06))
    # embroidery: violet satin, lighter on the thread crowns, a little glossier
    emb_col = g.scale_color(FILIGREE, g.add(0.42, g.mul(e_t, 0.42)))
    base = g.mixc(e_m, base, emb_col)
    rough = g.mixf(e_m, rough, g.add(0.36, g.mul(g.sub(1.0, e_t), 0.12)))
    # stitches
    base = g.mixc(thread, base, THREAD)
    rough = g.mixf(thread, rough, 0.62)
    # lining in the opening: violet satin; the armhole's dome: black lining
    weave = g.add(0.88, g.mul(g.noise(1.0 / 0.0008, 2.0), 0.24))
    base = g.mixc(lining, base, g.scale_color(COAT_LINING, weave))
    rough = g.mixf(lining, rough, 0.40)
    base = g.mixc(cap, base, g.scale_color((0.0060, 0.0052, 0.0075), weave))
    rough = g.mixf(cap, rough, 0.55)
    return g.finish_height(base, rough, 0.0, h)


def remove_images():
    embroidery.remove_images()
