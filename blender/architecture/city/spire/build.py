"""Stage 1: build the five spires (geometry, UVs, material slots), save the .blend.

  blender -b --factory-startup --python blender/architecture/city/spire/build.py

Each tower is one body mesh (glass, metal, lights), its ad panels (<tower>_ad<n>)
and its aircraft warning lights (<tower>_blink), in a collection of its own at the
origin. Detail is spent on silhouettes (tapers, facets, setbacks, sky lobby
recesses, crowns, masts, ad frames); everything below ~0.4 m lives in the tiling
textures. Heights are multiples of the 4 m floor so slabs line up with the glass.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mathutils import Vector  # noqa: E402

from spire_common import (  # noqa: E402
    BLEND, MAT_ADS, MAT_GLASS, MAT_LIGHTS, MAT_METAL, ad_part, blink_part, body_part, load_spec, roof_height,
    seed_of, towers,
)
from spire_kit import (  # noqa: E402
    Builder, Section, ad_panel, blink_lights, cap, chamfer_rect, stack, taper_plan,
)
from lib_candidates import offset_polygon, scale_polygon  # noqa: E402
from arcology_blender.scene import clear_scene, get_collection, part_tris, save_blend  # noqa: E402
from arcology_blender.shading import solid_mat  # noqa: E402
from spire_common import light_uv  # noqa: E402


def kinds(face="glass", corner=None, corner_tags=("corner",)):
    """kind(tag): corners (chamfers, tips, prows) get `corner`, everything else `face`."""
    def kind(tag):
        if corner is not None and tag in corner_tags:
            if corner.startswith("strip:") and "/" not in corner and face in ("glass", "louver", "metal"):
                return f"{corner}/{face}"   # wide corners: a fixture over the face's surface
            return corner
        return face
    return kind


def const(pts):
    return lambda z: pts


def finish(b, name, coll):
    return b.to_object(name, coll, body_part(name))


def plan_columns(plan, spacing=9.0, width=1.4):
    return (plan, spacing, width)


# ---------------------------------------------------------------------------------------
# city_spire_blade: thin faceted glass blade, magenta tip strips, slanted crown screen,
# the giant KAGEROU ad on its front around eye level
# ---------------------------------------------------------------------------------------
def blade(t, H, coll):
    name = t["name"]
    hw, hd = t["footprint"][0] / 2, t["footprint"][1] / 2
    tip = 1.2
    base = [(-0.48 * hw, -0.83 * hd), (0.0, -hd), (0.48 * hw, -0.83 * hd), (hw, -tip), (hw, tip),
            (0.48 * hw, 0.83 * hd), (0.0, hd), (-0.48 * hw, 0.83 * hd), (-hw, tip), (-hw, -tip)]
    tags = ["front", "front", "side", "tip", "side", "back", "back", "side", "tip", "side"]
    top_s = 0.9
    plan = taper_plan(base, H, top_s)
    lobby = taper_plan(base, H, top_s, inset=2.5)
    g = kinds("glass", "strip:magenta", ("tip",))
    fins = (("side",), 3.0, 0.6, 1.2)    # side facets: close vertical fins, glass between

    lv = kinds("louver", "strip:magenta", ("tip",))
    b = Builder(seed_of(name))
    secs = [
        Section(0, 12, lobby, "lobby_warm", tags, plan_columns(plan, 10.0)),
        Section(12, 120, plan, g, tags, fins=fins), Section(120, 128, plan, lv, tags),
        Section(128, 276, plan, g, tags, fins=fins),
        Section(276, 288, lobby, "lobby", tags, plan_columns(plan, 10.0)),
        Section(288, 400, plan, g, tags, fins=fins), Section(400, 408, plan, lv, tags),
        Section(408, H, plan, g, tags, fins=fins),
    ]
    stack(b, secs)

    # crown: a screen wall around the roof, its top edge rising from east to west, traced by a cyan light
    P = plan(H)
    xmin, xmax = min(p[0] for p in P), max(p[0] for p in P)
    low, high, band = 8.0, 46.0, 1.4

    def zt(x):
        return H + low + (high - low) * (xmax - x) / (xmax - xmin)

    for k in range(len(P)):
        a, c = P[k], P[(k + 1) % len(P)]
        A, C = Vector((a[0], a[1], H)), Vector((c[0], c[1], H))
        Ah, Ch = Vector((a[0], a[1], zt(a[0]) - band)), Vector((c[0], c[1], zt(c[0]) - band))
        At, Ct = Vector((a[0], a[1], zt(a[0]))), Vector((c[0], c[1], zt(c[0])))
        along = (C - A).normalized()
        b.metal_wall([A, C, Ch, Ah], (A + C) / 2, along, 0.0, H, 0.0)
        b.add([Ah, Ch, Ct, At], MAT_LIGHTS, [light_uv("cyan", 0.0, 0.0), light_uv("cyan", (C - A).length, 0.0),
                                              light_uv("cyan", (C - A).length, 1.0), light_uv("cyan", 0.0, 1.0)])
    # the screen's inner face and a cap on its top edge, so it reads solid from any angle
    inner = offset_polygon(P, 0.8)
    for k in range(len(P)):
        a, c = P[k], P[(k + 1) % len(P)]
        ia, ic = inner[k], inner[(k + 1) % len(P)]
        b.metal_auto([(a[0], a[1], zt(a[0])), (c[0], c[1], zt(c[0])), (ic[0], ic[1], zt(ic[0])), (ia[0], ia[1], zt(ia[0]))])
        b.metal_auto([(ic[0], ic[1], H), (ia[0], ia[1], H), (ia[0], ia[1], zt(ia[0])), (ic[0], ic[1], zt(ic[0]))])
    # roof plant and a window-cleaning crane hidden behind the screen, a mast at the high end
    b.box((-6, -4, H), (6, 4, H + 5), 0.0, (6.0, 0.0))
    b.box((-2, -2, H), (2, 2, H + 9), 0.0, (-6.0, 0.0))
    mx = xmin + 4.0
    b.mast(mx, 0.0, zt(mx) - 4.0, H + 95.0, 1.8, 0.5)
    body = finish(b, name, coll)

    # ad: KAGEROU on the front, 32 x 40 m, eye level (local z 170..210 = world y -10..30)
    zc = 170.0
    s_mid = 1.0 + (top_s - 1.0) * (zc + 20.0) / H
    apex = -hd * s_mid
    ad_b = Builder(seed_of(name, "ad"))
    w = 32.0
    y_panel = apex - 2.6
    ad_panel(f"{name}_ad1", coll, ad_part(name), "kagerou", (0.0, y_panel, zc), (0.0, -1.0), w, body=ad_b,
             struts=[(-8.0, zc + 6, 4.6), (8.0, zc + 6, 4.6), (-8.0, zc + 34, 4.6), (8.0, zc + 34, 4.6),
                     (0.0, zc + 20, 1.8)])
    # frame and struts belong to the body mesh: merge them in
    _merge(body, ad_b, coll, name)
    blink_lights(f"{name}_blink", coll, blink_part(name),
                 [(mx, 0.0, H + 95.8), (xmin + 0.9, 0.0, zt(xmin) + 0.9), (xmax - 0.9, 0.0, zt(xmax) + 0.9)])


def _merge(body, extra_builder, coll, name):
    """Join an extra builder's faces (ad frames, struts) into the tower's body mesh."""
    if not extra_builder.faces:
        return
    import bpy
    ob = extra_builder.to_object(f"{name}_extra", coll, "tmp")
    with bpy.context.temp_override(active_object=body, selected_editable_objects=[body, ob],
                                   selected_objects=[body, ob]):
        bpy.ops.object.join()


# ---------------------------------------------------------------------------------------
# city_spire_taper: chamfered square tapering to 60 %, cyan strips on the corners
# ---------------------------------------------------------------------------------------
def taper(t, H, coll):
    name = t["name"]
    W = t["footprint"][0]
    base, tags = chamfer_rect(W, t["footprint"][1], 5.0)
    plan = taper_plan(base, H, 0.6)
    lobby = taper_plan(base, H, 0.6, inset=2.5)
    g = kinds("glass", "strip:cyan")
    lv = kinds("louver", "strip:cyan")
    P = plan(H)
    crown = offset_polygon(P, 3.5)
    b = Builder(seed_of(name))
    fins = (("front", "right", "back", "left"), 7.0, 0.8, 1.4)
    secs = [
        Section(0, 12, lobby, "lobby_warm", tags, plan_columns(plan)),
        Section(12, 100, plan, g, tags, fins=fins), Section(100, 108, plan, lv, tags),
        Section(108, 196, plan, g, tags, fins=fins),
        Section(196, 208, lobby, "lobby", tags, plan_columns(plan)),
        Section(208, 300, plan, g, tags, fins=fins), Section(300, 308, plan, lv, tags),
        Section(308, H, plan, g, tags, fins=fins),
        Section(H, H + 12, const(crown), kinds("louver", "strip:cyan"), tags),
        Section(H + 12, H + 16, const(offset_polygon(crown, 2.0)), "metal", tags),
    ]
    stack(b, secs)
    top = H + 16
    b.box((-3, -3, top), (3, 3, top + 4), 0.0, (0.0, 0.0))
    b.mast(0.0, 0.0, top + 4, H + 80.0, 2.4, 0.6)
    # window-cleaning crane on the roof
    b.box((-1.5, -1.5, top), (1.5, 1.5, top + 3.0), 0.0, (5.0, -5.0))
    b.beam((5.0, -5.0, top + 2.6), (5.0 - 6.0, -5.0 - 12.0, top + 4.0), 0.8)
    finish(b, name, coll)
    corners = [((crown[k][0] + crown[(k + 1) % 8][0]) / 2, (crown[k][1] + crown[(k + 1) % 8][1]) / 2) for k in (1, 3, 5, 7)]
    blink_lights(f"{name}_blink", coll, blink_part(name),
                 [(0.0, 0.0, H + 80.8)] + [(x * 0.95, y * 0.95, H + 12.8) for x, y in corners])


# ---------------------------------------------------------------------------------------
# city_spire_twin: two faceted prow shafts joined by sky bridges, lit lantern crowns
# ---------------------------------------------------------------------------------------
def twin(t, H, coll):
    name = t["name"]
    W, D = t["footprint"]
    hd = D / 2
    gap = 4.0
    hw = (W - gap) / 4               # half width of one shaft
    b = Builder(seed_of(name))
    tags = ["front", "prow", "front", "side", "back", "prow", "back", "side"]
    tips = []
    for cx, Hs, louver_z in ((-(gap / 2 + hw), H, 160), (gap / 2 + hw, H - 40.0, 120)):
        shoulder = hd - 4.0
        base = [(cx - hw, -shoulder), (cx - 1.0, -hd), (cx + 1.0, -hd), (cx + hw, -shoulder),
                (cx + hw, shoulder), (cx + 1.0, hd), (cx - 1.0, hd), (cx - hw, shoulder)]
        plan = taper_plan(base, H, 0.92, center=(cx, 0.0))
        lobby = taper_plan(base, H, 0.92, inset=2.0, center=(cx, 0.0))
        g = kinds("glass", "strip:white", ("prow",))
        lv = kinds("louver", "strip:white", ("prow",))
        secs = [
            Section(0, 12, lobby, "lobby_warm", tags, plan_columns(plan, 8.0)),
            Section(12, louver_z, plan, g, tags, ledges=(48.0, 0.8, 0.7)),
            Section(louver_z, louver_z + 8, plan, lv, tags),
            Section(louver_z + 8, Hs, plan, g, tags, ledges=(48.0, 0.8, 0.7)),
        ]
        stack(b, secs, roof=False)
        # lit lantern crown: glowing facets leaning in to 62 %, a dark roof, a thin mast
        P = plan(Hs)
        P1 = scale_polygon(P, 0.62, (cx, 0.0))
        z1 = Hs + 34.0
        for k in range(len(P)):
            k2 = (k + 1) % len(P)
            A, C = Vector((P[k][0], P[k][1], Hs)), Vector((P[k2][0], P[k2][1], Hs))
            A1, C1 = Vector((P1[k][0], P1[k][1], z1)), Vector((P1[k2][0], P1[k2][1], z1))
            b.light_band([A, C, C1, A1], "crown", (A + C) / 2, (C - A).normalized(), Hs, z1)
        cap(b, P1, z1)
        b.mast(cx, 0.0, z1, z1 + 42.0, 1.6, 0.4)
        tips.append((cx, 0.0, z1 + 42.8))
    # sky bridges between the shafts (lit glazing front and back)
    for z0, z1 in ((176.0, 188.0), (296.0, 302.0)):
        x0, x1, y0, y1 = -gap / 2 - 1.5, gap / 2 + 1.5, -9.0, 9.0
        b.light_band([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], "lobby", (0, y0, z0), (1, 0, 0), z0, z1)
        b.light_band([(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], "lobby", (0, y1, z0), (-1, 0, 0), z0, z1)
        b.metal_flat([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
        b.metal_flat([(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)])
    finish(b, name, coll)
    blink_lights(f"{name}_blink", coll, blink_part(name), tips)


# ---------------------------------------------------------------------------------------
# city_spire_crown: the landmark. Three setback tiers with sky lobbies, a landing pad,
# a lit lantern, four leaning corner fins and an antenna mast with warning lights
# ---------------------------------------------------------------------------------------
LEDGES = (32.0, 1.2, 1.0)   # every 8 floors: 1.2 m tall, 1 m deep


def crown(t, H, coll):
    name = t["name"]
    W, D = t["footprint"]
    base, tags = chamfer_rect(W, D, 8.0)
    t2, t3 = scale_polygon(base, 0.84), scale_polygon(base, 0.68)
    g = kinds("glass", "strip:white")
    lv = kinds("louver", "strip:white")
    b = Builder(seed_of(name))
    secs = [
        Section(0, 16, const(offset_polygon(base, 3.0)), "lobby_warm", tags, plan_columns(const(base), 9.0, 1.6)),
        Section(16, 120, const(base), g, tags, ledges=LEDGES), Section(120, 128, const(base), lv, tags),
        Section(128, 200, const(base), g, tags, ledges=LEDGES),
        Section(200, 212, const(offset_polygon(t2, 2.5)), "lobby", tags, plan_columns(const(t2), 9.0, 1.6)),
        Section(212, 320, const(t2), g, tags, ledges=LEDGES), Section(320, 328, const(t2), lv, tags),
        Section(328, 400, const(t2), g, tags, ledges=LEDGES),
        Section(400, 412, const(offset_polygon(t3, 2.5)), "lobby_warm", tags, plan_columns(const(t3), 9.0, 1.6)),
        Section(412, 500, const(t3), g, tags, ledges=LEDGES), Section(500, 508, const(t3), lv, tags),
        Section(508, H, const(t3), g, tags, ledges=LEDGES),
        Section(H, H + 16, const(offset_polygon(t3, 4.0)), "crown", tags),
    ]
    stack(b, secs)
    top = H + 16
    blinks = []
    # corner fins leaning in, a white light on each leading edge
    for k in (1, 3, 5, 7):
        a, c = Vector(t3[k]), Vector(t3[(k + 1) % 8])
        m = (a + c) / 2
        d = m.normalized()
        side = Vector((-d.y, d.x)) * 0.8
        r = m.length
        r_in, r_out, r_top, z_top = r - 12.0, r + 0.6, r - 6.0, H + 84.0
        Pi, Po, Pt = d * r_in, d * r_out, d * r_top
        L = [Vector((p.x + sgn * side.x, p.y + sgn * side.y, z)) for sgn in (-1, 1)
             for p, z in ((Pi, H), (Po, H), (Pt, z_top))]
        # L: [Pi-, Po-, Pt-, Pi+, Po+, Pt+]
        b.metal_auto([L[0], L[1], L[2]])            # side faces
        b.metal_auto([L[3], L[5], L[4]])
        b.metal_auto([L[2], L[5], L[3], L[0]])      # inner edge
        b.strip((L[1], L[2]), (L[4], L[5]), "white")  # leading edge
        blinks.append((Pt.x, Pt.y, z_top + 0.8))
    # mast with two service platforms and an antenna
    b.mast(0.0, 0.0, top, H + 120.0, 4.0, 1.4)
    b.mast(0.0, 0.0, H + 120.0, H + 180.0, 0.8, 0.3)
    b.box((-3.5, -3.5, H + 60.0), (3.5, 3.5, H + 61.2))
    b.box((-2.5, -2.5, H + 100.0), (2.5, 2.5, H + 101.0))
    blinks += [(0.0, 0.0, H + 180.8), (0.0, 0.0, H + 121.0)]
    blinks += [(sx * 3.0, sy * 3.0, H + 62.0) for sx in (-1, 1) for sy in (-1, 1)]
    # landing pad cantilevered from the first sky lobby (front right), amber edge lights
    pc = Vector((W / 2 + 4.0, -D / 2 - 4.0))
    rad, zt_, zb_ = 10.0, 200.8, 199.2   # deck 0.8 m above the terrace (no coplanar faces)
    pad = [pc + Vector((math.cos(math.radians(22.5 + 45 * k)), math.sin(math.radians(22.5 + 45 * k)))) * rad
           for k in range(8)]
    u = 0.0
    for k in range(8):
        p, q = pad[k], pad[(k + 1) % 8]
        seg = (q - p).length
        b.add([(p.x, p.y, zb_), (q.x, q.y, zb_), (q.x, q.y, zt_), (p.x, p.y, zt_)], MAT_LIGHTS,
              [light_uv("pad", u, 0.0), light_uv("pad", u + seg, 0.0), light_uv("pad", u + seg, 1.0),
               light_uv("pad", u, 1.0)])
        u += seg
    cap(b, [tuple(p) for p in pad], zt_, up=True)
    cap(b, [tuple(p) for p in pad], zb_, up=False)
    # gangway from the sky lobby terrace out to the pad
    r_pad = pc.length - rad * math.cos(math.radians(22.5))
    b.box((27.0, -3.0, 199.8), (r_pad, 3.0, zt_), -45.0, (0.0, 0.0), skip=("+x",))
    for off in (-4.0, 4.0):
        sd = Vector((1, 1)).normalized()
        perp = Vector((-sd.y, sd.x)) * off
        b.beam((pc.x - 4 + perp.x, pc.y + 4 + perp.y, zb_ - 0.4), (W / 2 - 6 + perp.x, -D / 2 + 6 + perp.y, 182.0), 1.4)
    finish(b, name, coll)
    blink_lights(f"{name}_blink", coll, blink_part(name), blinks)


# ---------------------------------------------------------------------------------------
# city_spire_adtower: slim tower wrapped in stacked ad screens on its front and left faces
# ---------------------------------------------------------------------------------------
def adtower(t, H, coll):
    name = t["name"]
    W, D = t["footprint"]
    base, tags = chamfer_rect(W, D, 2.0)
    top = scale_polygon(base, 0.86)
    g = kinds("glass", "strip:magenta")
    lv = kinds("louver", "strip:magenta")
    b = Builder(seed_of(name))
    secs = [
        Section(0, 12, const(offset_polygon(base, 2.0)), "lobby_warm", tags, plan_columns(const(base), 8.0)),
        Section(12, 120, const(base), g, tags), Section(120, 128, const(base), lv, tags),
        Section(128, 300, const(base), g, tags), Section(300, 308, const(base), lv, tags),
        Section(308, 396, const(base), g, tags),
        Section(396, H, const(top), g, tags),
        Section(H, H + 10, const(offset_polygon(top, 3.0)), lv, tags),
    ]
    stack(b, secs)
    b.mast(0.0, 0.0, H + 10, H + 70.0, 2.0, 0.5)
    ads = Builder(seed_of(name, "ad"))
    n = 0
    stand = 1.3
    # front: a ticker and four 28 x 21 m screens, bottom to top; all above the brutalist
    # bridge block in front of it (its roof is at world y 95 = local z 275)
    for region, z in (("ticker", 279.0), ("hoshizora", 287.0), ("sorakaze", 312.0), ("okami", 337.0),
                      ("mirai", 362.0)):
        n += 1
        _, h = ad_panel(f"{name}_ad{n}", coll, ad_part(name), region, (0.0, -D / 2 - stand, z), (0.0, -1.0), 28.0,
                        body=ads, struts=[(-10.0, z + 1.0, 0.8), (10.0, z + 1.0, 0.8)])
    # left side: two vertical banners and the pharmacy sign
    for region, yc, z, w in (("tensei", 6.0, 296.0, 9.0), ("ryujin", -5.5, 296.0, 9.0), ("kusuri", 0.0, 346.0, 16.0)):
        n += 1
        ad_panel(f"{name}_ad{n}", coll, ad_part(name), region, (-W / 2 - stand, yc, z), (-1.0, 0.0), w,
                 body=ads, struts=[(0.0, z + 1.0, 0.8)])
    body = finish(b, name, coll)
    _merge(body, ads, coll, name)
    tc = offset_polygon(top, 3.0)
    corners = [((tc[k][0] + tc[k + 1][0]) / 2, (tc[k][1] + tc[k + 1][1]) / 2) for k in (1, 3, 5)]
    corners.append(((tc[7][0] + tc[0][0]) / 2, (tc[7][1] + tc[0][1]) / 2))
    blink_lights(f"{name}_blink", coll, blink_part(name),
                 [(0.0, 0.0, H + 70.8)] + [(x, y, H + 10.8) for x, y in corners])


BUILDERS = {
    "city_spire_blade": blade,
    "city_spire_taper": taper,
    "city_spire_twin": twin,
    "city_spire_crown": crown,
    "city_spire_adtower": adtower,
}

# Placeholder looks until bake.py wires the texture sets in (same names).
PLACEHOLDER = {
    MAT_GLASS: dict(base=(0.12, 0.14, 0.17), rough=0.12, metal=0.9),
    MAT_METAL: dict(base=(0.05, 0.053, 0.06), rough=0.45, metal=0.8),
    MAT_LIGHTS: dict(base=(0.5, 0.5, 0.5), rough=0.3, metal=0.0, emission=(0.8, 0.9, 1.0), emission_strength=3.0),
    MAT_ADS: dict(base=(0.1, 0.0, 0.1), rough=0.3, metal=0.0, emission=(1.0, 0.1, 0.5), emission_strength=3.0),
}


def main():
    clear_scene()
    for m, kw in PLACEHOLDER.items():
        solid_mat(m, **kw)
    spec = load_spec()
    for t in towers(spec):
        if t["name"] not in BUILDERS:
            raise SystemExit(f"no design for spire {t['name']}")
        H = roof_height(t, spec)
        BUILDERS[t["name"]](t, H, get_collection(t["name"]))
        tris = part_tris(body_part(t["name"])) + part_tris(ad_part(t["name"])) + part_tris(blink_part(t["name"]))
        print(f"TRIS {t['name']} total={tris} body={part_tris(body_part(t['name']))} "
              f"ads={part_tris(ad_part(t['name']))} blink={part_tris(blink_part(t['name']))}")
    save_blend(BLEND)


if __name__ == "__main__":
    main()
