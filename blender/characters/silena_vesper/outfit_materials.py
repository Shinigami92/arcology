"""Stage-3 procedural source materials (baked by bake.py into two atlases):

coat body atlas (`SilenaCoatBody`):
- `src_coat_body`: the sleeve's coat leather (pebbled grain, mottle, worn edges and fold
  crests, darker creases) on the coat body: center back and side/shoulder seams pressed
  with a topstitch row each side, two topstitch rows along the front edges and the hem,
  the sleeve's violet vine embroidered down both front panels (ornaments.vine) and a
  running scroll border around the hem (ornaments.hem_border); violet satin lining.
- `src_collar`: the same leather, stitch rows along the top edge and the front ends.

outfit atlas (`SilenaOutfit`):
- `src_top`: black lace (ornaments.lace) over the deep violet satin underlayer, corset
  seams with boning channels, a violet satin piping on the V's edge.
- `src_trousers`: matte black stretch twill, seams with topstitching, soft creases at
  the hip, the back of the knee and the ankle.
- `src_boots`: smooth black leather, toe cap and back seams, the side zip on the inside,
  creases over the instep, suede in the shaft's top, crepe rubber sole with a tread.
- `src_gear`: the belt and what hangs on it by region: leather with painted edges and
  stitching, gunmetal and steel, dark violet glass, matte black polymer, woven elastic.
- `src_hair`: black hair with a violet sheen, streaks along the strands.

Attributes come from coat.py, clothes.py, boots.py, belt.py and head.py.
"""

from silena_vesper_common import COAT_LINING, FABRIC, FILIGREE, GUNMETAL, GUNMETAL_DARK, HAIR, LEATHER, \
    LEATHER_WORN, RUBBER, STEEL, THREAD, UNDERLAYER
import belt as belt_geo
import embroidery
import ornaments
from coat_leather import Coat
from arcology_blender.shading import new_mat

VINE_ED = 0.052          # vine centerline from the front edge (m)
VINE_HM = 0.118          # the vine's foot above the hem (m)
VINE_LENGTH = 1.10       # m
HEM_BAND = (0.014, ornaments.HEM_HEIGHT / 1000.0)
EDGE_ROWS = (0.0055, 0.0115)
HEM_ROWS = (0.0060, 0.0090 + ornaments.HEM_HEIGHT / 1000.0)
STITCH = 0.0034

_IMAGES = {}


def _image(name, data):
    from embroidery import to_image

    if name not in _IMAGES:
        _IMAGES[name] = to_image(name, *data)
    return _IMAGES[name]


def remove_images():
    import bpy

    for name in list(_IMAGES) + ["coat_vine", "coat_hem", "top_lace"]:
        img = bpy.data.images.get(name)
        if img is not None:
            bpy.data.images.remove(img)
    _IMAGES.clear()


def _leather_base(g, scale=1.0):
    """The sleeve's coat leather: (height, base, rough) before features."""
    cells = g.voronoi_edge(1.0 / (0.0016 * scale))
    cells2 = g.voronoi_edge(1.0 / (0.0029 * scale), g.offset((0.41, 0.17, 0.29)))
    mixcell = g.maprange(g.noise(45.0, 2.0), 0.4, 0.6)
    pore = g.mixf(mixcell, g.maprange(cells, 0.11, 0.0), g.maprange(cells2, 0.08, 0.0))
    h = g.mul(pore, -0.000020)
    crinkle = g.maprange(g.abs(g.sub(g.noise(1.0 / 0.011, 4.0, 0.55), 0.5)), 0.03, 0.0)
    h = g.add(h, g.mul(crinkle, -0.000040))
    mottle = g.add(0.84, g.mul(g.noise(1.0 / 0.030, 3.0, 0.55), 0.32))
    base = g.scale_color(LEATHER, mottle)
    rough = g.add(0.50, g.mul(g.sub(g.noise(1.0 / 0.015, 3.0), 0.5), 0.10))
    return h, base, rough


def _worn(g, base, rough, extra=None, amount=0.40):
    edge = g.maprange(g.pointiness(), 0.53, 0.60)
    patchy = g.maprange(g.noise(1.0 / 0.008, 4.0, 0.6), 0.35, 0.65)
    worn = g.mul(g.mul(edge, patchy), amount)
    if extra is not None:
        worn = g.add(worn, extra)
    base = g.mixc(g.mul(worn, 0.85), base, LEATHER_WORN)
    rough = g.sub(rough, g.mul(worn, 0.12))
    return base, rough


def _satin(g, x, y, img, on, h, base, rough, gain=0.00045):
    eh, em, et = g.image3(img, x, y)
    em = g.mul(em, on)
    h = g.add(h, g.mul(g.mul(eh, on), gain))
    h = g.add(h, g.mul(g.mul(g.sub(et, 0.5), em), 0.00009))
    col = g.scale_color(FILIGREE, g.add(0.42, g.mul(et, 0.42)))
    base = g.mixc(em, base, col)
    rough = g.mixf(em, rough, g.add(0.36, g.mul(g.sub(1.0, et), 0.12)))
    return h, base, rough


def src_coat_body():
    vine_img = _image("coat_vine", ornaments.vine(VINE_LENGTH * 1000.0))
    hem_img = _image("coat_hem", ornaments.hem_border())
    g = Coat(new_mat("src_coat_body"))
    attr = g.attribute
    region = attr("region")
    lining = g.maprange(region, 1.5, 1.9)
    roll = g.band(region, 0.6, 1.4, 0.2)
    leather = g.sub(1.0, lining)
    cu, cl, cv, hm, ss, fold = (attr(a) for a in ("cu", "cl", "cv", "hm", "ss", "fold"))
    ed = g.math("MINIMUM", cu, g.sub(cl, cu))
    cb = g.abs(g.sub(cu, g.mul(cl, 0.5)))
    h, base, rough = _leather_base(g)
    # long soft draw lines down the skirt, stronger on the fold crests
    draw = g.noise(1.0, 2.0, 0.45, g.combine(g.mul(cu, 40.0), g.mul(cv, 5.0), 0.0))
    draw_line = g.mul(g.maprange(g.abs(g.sub(draw, 0.5)), 0.06, 0.0), g.maprange(g.noise(1.0 / 0.06, 2.0), 0.45, 0.6))
    h = g.add(h, g.mul(draw_line, -0.00005))
    h = g.mul(h, leather)
    # seams: center back and side/shoulder seams pressed open, a topstitch row each side
    seam = g.mul(g.add(g.maprange(cb, 0.0005, 0.0), g.maprange(ss, 0.0005, 0.0)), leather)
    welt = g.mul(g.add(g.band(cb, 0.0007, 0.0024, 0.0005), g.band(ss, 0.0007, 0.0024, 0.0005)), leather)
    h = g.add(h, g.add(g.mul(seam, -0.00035), g.mul(welt, 0.00010)))
    thr_s, hole_s = g.stitches(g.abs(g.sub(ss, 0.0045)), cv, width=0.00045, length=STITCH)
    thr_b, hole_b = g.stitches(g.abs(g.sub(cb, 0.0045)), cv, width=0.00045, length=STITCH)
    # front edges and the hem: two rows each
    thr_e, hole_e = g.stitches(g.abs(g.sub(ed, EDGE_ROWS[0])), cv, width=0.00048, length=STITCH)
    thr_e2, hole_e2 = g.stitches(g.abs(g.sub(ed, EDGE_ROWS[1])), cv, width=0.00048, length=STITCH)
    thr_h, hole_h = g.stitches(g.abs(g.sub(hm, HEM_ROWS[0])), cu, width=0.00048, length=STITCH)
    thr_h2, hole_h2 = g.stitches(g.abs(g.sub(hm, HEM_ROWS[1])), cu, width=0.00048, length=STITCH)
    thread = g.mul(g.add(g.add(g.add(thr_s, thr_b), g.add(thr_e, thr_e2)), g.add(thr_h, thr_h2)), leather)
    holes = g.mul(g.add(g.add(g.add(hole_s, hole_b), g.add(hole_e, hole_e2)), g.add(hole_h, hole_h2)), leather)
    h = g.add(h, g.add(g.mul(thread, 0.00016), g.mul(holes, -0.00011)))
    # embroidery: the vine down each front panel, the border around the hem
    outer = g.mul(g.maprange(region, 0.5, 0.1), 1.0)
    vx = g.add(g.mul(g.sub(ed, VINE_ED), 1000.0 / embroidery.BAND_W), 0.5)
    vy = g.mul(g.sub(hm, VINE_HM), 1.0 / VINE_LENGTH)
    on_vine = g.mul(g.mul(outer, g.band(vx, 0.0, 1.0, 0.01)), g.band(vy, 0.0, 1.0, 0.005))
    h, base, rough = _satin(g, vx, vy, vine_img, on_vine, h, base, rough)
    hx = g.mul(cu, 1000.0 / ornaments.HEM_PERIOD)
    hy = g.mul(g.sub(hm, HEM_BAND[0]), 1.0 / HEM_BAND[1])
    on_hem = g.mul(outer, g.band(hy, 0.0, 1.0, 0.01))
    hh, hmk, ht = _repeat_image3(g, hem_img, hx, hy)
    hmk = g.mul(hmk, on_hem)
    h = g.add(h, g.mul(g.mul(hh, on_hem), 0.00045))
    h = g.add(h, g.mul(g.mul(g.sub(ht, 0.5), hmk), 0.00009))
    base = g.mixc(hmk, base, g.scale_color(FILIGREE, g.add(0.42, g.mul(ht, 0.42))))
    rough = g.mixf(hmk, rough, g.add(0.36, g.mul(g.sub(1.0, ht), 0.12)))
    # color: worn edges, rolls and fold crests; creases darker
    crest = g.mul(g.maprange(fold, 0.55, 0.95), 0.18)
    base, rough = _worn(g, base, rough, g.add(g.mul(roll, 0.45), g.add(crest, g.mul(welt, 0.25))))
    dark = g.add(g.mul(draw_line, 0.5), seam)
    base = g.scale_color(base, g.sub(1.0, g.mul(dark, 0.3)))
    rough = g.add(rough, g.mul(dark, 0.06))
    base = g.mixc(thread, base, THREAD)
    rough = g.mixf(thread, rough, 0.62)
    # lining: violet satin with a fine weave
    weave = g.add(0.88, g.mul(g.noise(1.0 / 0.0008, 2.0), 0.24))
    base = g.mixc(lining, base, g.scale_color(COAT_LINING, weave))
    rough = g.mixf(lining, rough, 0.40)
    h = g.add(g.mul(h, leather), g.mul(lining, g.mul(g.sub(weave, 1.0), 0.00002)))
    return g.finish_height(base, rough, 0.0, h)


def _repeat_image3(g, img, x, y):
    t = g.nodes.new("ShaderNodeTexImage")
    t.image = img
    t.extension = "REPEAT"
    t.interpolation = "Cubic"
    g.links.new(g.combine(x, y, 0.0), t.inputs["Vector"])
    sep = g.nodes.new("ShaderNodeSeparateColor")
    g.links.new(t.outputs["Color"], sep.inputs[0])
    return sep.outputs[0], sep.outputs[1], sep.outputs[2]


def src_collar():
    g = Coat(new_mat("src_collar"))
    attr = g.attribute
    region = attr("region")
    roll = g.band(region, 0.6, 1.4, 0.2)
    cs, cu, cl = attr("cs"), attr("cu"), attr("cl")
    h, base, rough = _leather_base(g)
    ed = g.math("MINIMUM", cu, g.sub(cl, cu))
    # stitch rows: along the top edge (outer and inner face) and along the front ends
    top = g.math("MAXIMUM", cs, 0.0)
    thr, hole = g.stitches(g.abs(g.sub(ed, 0.006)), cs, width=0.00045, length=STITCH)
    hgt = g.attribute("cs")
    thr2, hole2 = g.stitches(g.abs(g.sub(g.sub(_collar_h(g, cu, cl), hgt), 0.007)), cu, width=0.00045,
                             length=STITCH)
    thread = g.add(thr, thr2)
    holes = g.add(hole, hole2)
    h = g.add(h, g.add(g.mul(thread, 0.00016), g.mul(holes, -0.00011)))
    # the collar is stiff: a faint roll line where it turns
    h = g.add(h, g.mul(g.maprange(g.abs(g.sub(top, 0.012)), 0.002, 0.0), -0.00006))
    base, rough = _worn(g, base, rough, g.mul(roll, 0.5))
    base = g.mixc(thread, base, THREAD)
    rough = g.mixf(thread, rough, 0.62)
    return g.finish_height(base, rough, 0.0, h)


def _collar_h(g, cu, cl):
    """The collar's height at a point along it (coat.COLLAR_H as a smooth ramp)."""
    import coat
    q = g.math("DIVIDE", cu, cl)
    s = g.math("MINIMUM", q, g.sub(1.0, q))
    keys = coat.COLLAR_H
    h = keys[0][1]
    out = g.add(0.0, h)
    for (x0, y0), (x1, y1) in zip(keys, keys[1:]):
        out = g.add(out, g.mul(g.maprange(s, x0, x1), y1 - y0))
    return out


# --- outfit atlas --------------------------------------------------------------------------------
def src_top():
    img = _image("top_lace", ornaments.lace())
    g = Coat(new_mat("src_top"))
    attr = g.attribute
    region, vd, az, hz = attr("region"), attr("vd"), attr("az"), attr("hz")
    edge = g.maprange(region, 0.5, 0.9)
    T = ornaments.LACE_TILE / 1000.0
    u = g.mul(g.mul(az, 0.135), 1.0 / T)
    v = g.mul(hz, 1.0 / T)
    lh, lm, lc = _repeat_image3(g, img, u, v)
    lace = g.mul(lm, g.sub(1.0, edge))
    # the satin underneath: deep violet, a soft sheen across the weave
    sheen = g.add(0.85, g.mul(g.noise(1.0 / 0.012, 2.0), 0.3))
    under = g.scale_color(UNDERLAYER, sheen)
    lace_col = g.scale_color((0.0055, 0.0050, 0.0068), g.add(0.9, g.mul(lc, 0.35)))
    base = g.mixc(lace, under, lace_col)
    rough = g.mixf(lace, 0.34, g.add(0.62, g.mul(lc, -0.08)))
    h = g.mul(g.mul(lh, g.sub(1.0, edge)), 0.00038)
    # corset seams with boning channels: princess lines and the center back
    import math
    seams = 0
    for a0 in (0.42, -0.42, 1.25, -1.25, math.pi, -math.pi):
        d = g.abs(g.sub(az, a0))
        ch = g.band(d, 0.0, 0.055, 0.012)
        ridge = g.maprange(g.abs(g.sub(d, 0.026)), 0.022, 0.0)
        h = g.add(h, g.mul(g.mul(ch, ridge), 0.0006))
        line = g.maprange(g.abs(g.sub(d, 0.052)), 0.004, 0.0)
        h = g.add(h, g.mul(line, -0.0002))
        seams = g.add(seams, g.mul(ch, 0.7))
    seams = g.math("MINIMUM", seams, 1.0)
    base = g.mixc(g.mul(seams, 0.6), base, g.scale_color(UNDERLAYER, 0.55))
    # V edge: violet satin piping, and the bound edge itself
    pipe = g.add(g.maprange(vd, 0.0065, 0.003), edge)
    pipe = g.math("MINIMUM", pipe, 1.0)
    base = g.mixc(pipe, base, g.scale_color(UNDERLAYER, 1.25))
    rough = g.mixf(pipe, rough, 0.30)
    h = g.add(h, g.mul(g.maprange(g.abs(g.sub(vd, 0.0065)), 0.0008, 0.0), -0.00012))
    return g.finish_height(base, rough, 0.0, h)


def src_trousers():
    g = Coat(new_mat("src_trousers"))
    attr = g.attribute
    az, hz, ld = attr("az"), attr("hz"), attr("ld")
    import math
    # twill: fine diagonal ridges in the leg's surface coordinates
    twill = g.cos(g.mul(g.add(g.mul(g.mul(az, 0.06), 1.0), g.mul(hz, 1.0)), 6.2832 / 0.0009))
    h = g.mul(twill, 0.000006)
    slub = g.noise(1.0 / 0.004, 2.0)
    h = g.add(h, g.mul(g.sub(slub, 0.5), 0.00001))
    base = g.scale_color(FABRIC, g.add(0.9, g.mul(slub, 0.2)))
    rough = g.add(0.78, g.mul(g.sub(g.noise(1.0 / 0.02, 2.0), 0.5), 0.06))
    # outseam and inseam on the legs, a topstitch row beside the outseam
    leg = g.abs(ld)
    for a0 in (math.pi * 0.5, -math.pi * 0.5):
        d = g.abs(g.sub(g.mul(az, ld), a0))
        arc = g.mul(d, 0.075)
        h = g.add(h, g.mul(g.mul(g.maprange(arc, 0.0006, 0.0), leg), -0.00025))
        thr, hole = g.stitches(g.abs(g.sub(arc, 0.004)), hz, width=0.0004, length=0.0028)
        h = g.add(h, g.mul(g.mul(thr, leg), 0.00008))
    # soft creases: across the hip front, behind the knee, above the boots
    w1 = g.maprange(g.abs(g.sub(hz, 0.91)), 0.05, 0.0)
    w2 = g.maprange(g.abs(g.sub(hz, 0.52)), 0.04, 0.0)
    w3 = g.maprange(g.abs(g.sub(hz, 0.38)), 0.04, 0.0)
    wav = g.maprange(g.cos(g.mul(g.add(hz, g.mul(g.noise(1.0 / 0.03, 2.0), 0.01)), 6.2832 / 0.016)), 0.2, 1.0)
    crease = g.mul(wav, g.add(g.add(g.mul(w1, 0.6), w2), g.mul(w3, 0.8)))
    h = g.add(h, g.mul(crease, -0.0003))
    base = g.scale_color(base, g.sub(1.0, g.mul(crease, 0.15)))
    return g.finish_height(base, rough, 0.0, h)


def src_boots():
    g = Coat(new_mat("src_boots"))
    attr = g.attribute
    region, bt, ba, bh = attr("region"), attr("bt"), attr("ba"), attr("bh")
    sole = g.maprange(region, 2.5, 2.9)
    lining = g.band(region, 1.6, 2.4, 0.2)
    fold = g.band(region, 0.6, 1.4, 0.2)
    upper = g.sub(1.0, g.add(sole, lining))
    h, base, rough = _leather_base(g, scale=0.75)
    base = g.scale_color(base, 0.9)
    rough = g.sub(rough, 0.08)                      # smooth, a little polished
    import math
    # back seam, toe cap seam, side zip on the inside (from the top to above the ankle)
    back = g.abs(g.sub(g.abs(ba), math.pi))
    seam_b = g.maprange(back, 0.03, 0.0)
    toe = g.maprange(g.abs(g.sub(bt, 0.395)), 0.0012, 0.0)
    zip_zone = g.mul(g.band(g.mul(ba, -1.0), 1.25, 1.65, 0.03), g.maprange(bt, 0.20, 0.17))
    teeth = g.maprange(g.cos(g.mul(bt, 6.2832 / 0.0032)), 0.0, 0.6)
    zip_core = g.mul(g.band(g.mul(ba, -1.0), 1.38, 1.52, 0.02), g.maprange(bt, 0.20, 0.17))
    h = g.add(h, g.mul(g.add(seam_b, toe), -0.00030))
    h = g.add(h, g.mul(g.mul(zip_core, teeth), 0.0004))
    h = g.add(h, g.mul(g.sub(zip_zone, zip_core), -0.0002))
    thr, hole = g.stitches(g.abs(g.sub(back, 0.06)), bt, width=0.00045, length=0.0028)
    thr2, hole2 = g.stitches(g.abs(g.sub(bt, 0.400)), ba, width=0.00045, length=0.0030)
    thr3, hole3 = g.stitches(g.abs(g.sub(bh, 0.0075)), ba, width=0.00045, length=0.0030)
    thread = g.mul(g.add(g.add(thr, thr2), thr3), upper)
    h = g.add(h, g.mul(thread, 0.00014))
    # instep creases where the foot flexes
    flex = g.mul(g.maprange(g.abs(g.sub(bt, 0.36)), 0.035, 0.0), g.maprange(g.abs(ba), 0.9, 0.4))
    wav = g.maprange(g.cos(g.mul(g.add(bt, g.mul(g.noise(1.0 / 0.02, 2.0), 0.008)), 6.2832 / 0.010)), 0.5, 1.0)
    h = g.add(h, g.mul(g.mul(flex, wav), -0.00028))
    base, rough = _worn(g, base, rough, g.add(g.mul(fold, 0.4), g.mul(g.maprange(bh, 0.05, 0.01), 0.15)))
    base = g.mixc(thread, base, THREAD)
    rough = g.mixf(thread, rough, 0.6)
    zip_col = g.mixc(teeth, GUNMETAL_DARK, GUNMETAL)
    base = g.mixc(zip_core, base, zip_col)
    rough = g.mixf(zip_core, rough, 0.35)
    metal = g.mul(zip_core, 1.0)
    # suede in the shaft's top
    suede = g.add(0.85, g.mul(g.noise(1.0 / 0.0006, 2.0), 0.3))
    base = g.mixc(lining, base, g.scale_color((0.010, 0.009, 0.011), suede))
    rough = g.mixf(lining, rough, 0.9)
    # crepe sole: bumpy, a tread grid underneath, the heel's edge
    crepe = g.noise(1.0 / 0.0018, 3.0, 0.6)
    bottom = g.maprange(bh, -0.0105, -0.0118)
    tread = g.mul(g.maprange(g.abs(g.sub(g.math("FRACT", g.mul(ba, 22.0)), 0.5)), 0.12, 0.2), bottom)
    heel_line = g.maprange(g.abs(g.sub(ba, 0.30)), 0.004, 0.0)
    hs = g.add(g.mul(g.sub(crepe, 0.5), 0.00018), g.add(g.mul(tread, -0.0006), g.mul(heel_line, -0.0005)))
    h = g.mixf(sole, h, hs)
    rcol = g.scale_color(RUBBER, g.add(0.85, g.mul(crepe, 0.3)))
    base = g.mixc(sole, base, rcol)
    rough = g.mixf(sole, rough, 0.82)
    return g.finish_height(base, rough, metal, h)


def src_gear():
    g = Coat(new_mat("src_gear"))
    attr = g.attribute
    region, hu, hv = attr("region"), attr("hu"), attr("hv")
    R = belt_geo

    def is_(code):
        return g.band(region, code - 0.4, code + 0.4, 0.1)

    leather = g.add(is_(R.H_LEATHER), is_(R.H_STRAP))
    metal = is_(R.H_METAL)
    glass = is_(R.H_GLASS)
    poly = is_(R.H_POLY)
    elastic = is_(R.H_ELASTIC)
    h, base, rough = _leather_base(g, scale=0.8)
    base = g.scale_color(base, 1.05)
    # belt band and straps: painted edges, a stitch row along each edge (hv = across, m)
    across = g.abs(hv)
    edge_paint = g.mul(g.maprange(across, 0.0255, 0.0272), g.mul(is_(R.H_LEATHER), g.maprange(hu, 999.0, 1000.0)))
    band_only = g.mul(is_(R.H_LEATHER), g.maprange(hu, 999.0, 1000.0))
    thr, hole = g.stitches(g.abs(g.sub(across, 0.0225)), g.mul(g.sub(hu, 1000.0), 0.0028), width=0.00045,
                           length=0.0032)
    thread = g.mul(thr, band_only)
    h = g.add(h, g.mul(thread, 0.00014))
    # the tongue's holes (hu 100..101 along it)
    t = g.sub(hu, 100.0)
    on_t = g.mul(g.band(t, 0.0, 1.0, 0.01), is_(R.H_LEATHER))
    hole_c = g.maprange(g.abs(g.sub(g.math("FRACT", g.mul(t, 5.0)), 0.5)), 0.05, 0.03)
    holes = g.mul(g.mul(hole_c, g.maprange(across, 0.004, 0.0025)), g.mul(on_t, g.band(t, 0.35, 0.95, 0.02)))
    h = g.add(h, g.mul(holes, -0.0015))
    base, rough = _worn(g, base, rough, None, 0.35)
    base = g.mixc(thread, base, THREAD)
    base = g.mixc(edge_paint, base, (0.0045, 0.004, 0.005))
    rough = g.mixf(edge_paint, rough, 0.3)
    base = g.scale_color(base, g.sub(1.0, g.mul(holes, 0.8)))
    # metal: gunmetal, brighter worn edges; the handcuffs are steel (lighter)
    brushed = g.noise(1.0, 2.0, 0.5, g.combine(g.mul(hu, 900.0), g.mul(hv, 30.0), 0.0))
    edge_m = g.maprange(g.pointiness(), 0.52, 0.62)
    mcol = g.mixc(g.mul(edge_m, 0.7), GUNMETAL, STEEL)
    mrough = g.add(0.32, g.mul(brushed, 0.12))
    # glass: dark violet, glossy
    gcol = g.scale_color((0.020, 0.008, 0.040), g.add(0.8, g.mul(g.pointiness(), 0.6)))
    # polymer: matte black with a fine stipple
    stip = g.noise(1.0 / 0.0005, 2.0)
    pcol = g.scale_color((0.010, 0.010, 0.012), g.add(0.85, g.mul(stip, 0.3)))
    # elastic: woven ribs
    rib = g.maprange(g.cos(g.mul(hv, 6.2832 / 0.0011)), -0.2, 1.0)
    ecol = g.scale_color((0.008, 0.007, 0.009), g.add(0.8, g.mul(rib, 0.3)))
    base = g.mixc(metal, base, mcol)
    base = g.mixc(glass, base, gcol)
    base = g.mixc(poly, base, pcol)
    base = g.mixc(elastic, base, ecol)
    rough = g.mixf(metal, rough, mrough)
    rough = g.mixf(glass, rough, 0.12)
    rough = g.mixf(poly, rough, g.add(0.55, g.mul(stip, 0.1)))
    rough = g.mixf(elastic, rough, 0.8)
    h = g.mixf(g.add(metal, glass), h, g.mul(brushed, 0.000004))
    h = g.mixf(poly, h, g.mul(stip, 0.00001))
    h = g.mixf(elastic, h, g.mul(rib, 0.00012))
    return g.finish_height(base, rough, metal, h)


def src_hair():
    g = Coat(new_mat("src_hair"))
    attr = g.attribute
    hs, ha = attr("hs"), attr("ha")
    streak = g.noise(1.0, 3.0, 0.5, g.combine(g.mul(ha, 60.0), g.mul(hs, 4.0), g.mul(g.z, 2.0)))
    fine = g.noise(1.0, 2.0, 0.5, g.combine(g.mul(ha, 400.0), g.mul(hs, 20.0), 0.0))
    s = g.maprange(g.add(g.mul(streak, 0.7), g.mul(fine, 0.3)), 0.3, 0.75)
    base = g.mixc(g.mul(s, 0.6), HAIR, (0.030, 0.014, 0.060))
    rough = g.add(0.42, g.mul(s, -0.1))
    h = g.mul(g.sub(fine, 0.5), 0.0003)
    return g.finish_height(base, rough, 0.0, h)
