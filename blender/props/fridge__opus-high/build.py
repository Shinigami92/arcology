"""Build, UV, bake and save the fridge (variant opus-high).

blender --background --factory-startup --python build.py -- [--tex-tmp DIR] [--fast]
Writes blender/props/fridge__opus-high.blend with packed textures.
"""
import bpy, bmesh, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec as S

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAST = "--fast" in ARGV
TEX_TMP = ARGV[ARGV.index("--tex-tmp") + 1] if "--tex-tmp" in ARGV else os.path.join(
    os.environ.get("TEMP", "/tmp"), "fridge_opus_high_tex")
os.makedirs(TEX_TMP, exist_ok=True)
T0 = time.time()


def log(*a):
    print(f"[fridge {time.time() - T0:6.1f}s]", *a, flush=True)


# ---------------------------------------------------------------- scene reset
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
    for d in list(coll):
        coll.remove(d)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
COLL = scene.collection

# ---------------------------------------------------------------- materials (bake sources)
CH = {}          # material name -> dict of channel sockets / nodes
SRC = {}         # (group, kind) -> material


class NB:
    def __init__(s, mat):
        s.mat = mat
        s.nt = mat.node_tree
        s.nt.nodes.clear()
        s._co = None
        s._n = None

    def link(s, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            s.nt.links.new(v, sock)
            return
        if sock.type == "RGBA":
            if isinstance(v, (int, float)):
                v = (v, v, v, 1.0)
            elif len(v) == 3:
                v = (*v, 1.0)
        elif sock.type == "VECTOR" and isinstance(v, (int, float)):
            v = (v, v, v)
        sock.default_value = v

    def new(s, t, **props):
        n = s.nt.nodes.new(t)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def co(s):
        if s._co is None:
            s._co = s.new("ShaderNodeTexCoord").outputs["Object"]
        return s._co

    def nrm(s):
        if s._n is None:
            s._n = s.new("ShaderNodeNewGeometry").outputs["Normal"]
        return s._n

    def xyz(s, v):
        n = s.new("ShaderNodeSeparateXYZ")
        s.link(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def vec(s, x, y, z):
        n = s.new("ShaderNodeCombineXYZ")
        s.link(n.inputs[0], x)
        s.link(n.inputs[1], y)
        s.link(n.inputs[2], z)
        return n.outputs[0]

    def m(s, op, a, b=0.0, c=0.0, clamp=False):
        n = s.new("ShaderNodeMath", operation=op, use_clamp=clamp)
        s.link(n.inputs[0], a)
        s.link(n.inputs[1], b)
        s.link(n.inputs[2], c)
        return n.outputs[0]

    def add(s, a, b): return s.m("ADD", a, b)
    def sub(s, a, b): return s.m("SUBTRACT", a, b)
    def mul(s, a, b): return s.m("MULTIPLY", a, b)
    def mx(s, a, b): return s.m("MAXIMUM", a, b)

    def lin(s, c, *terms, clamp=True):
        acc = c
        for i, (v, k) in enumerate(terms):
            acc = s.m("MULTIPLY_ADD", v, k, acc, clamp=clamp and i == len(terms) - 1)
        return acc

    def mr(s, v, a, b, c=0.0, d=1.0, smooth=False):
        n = s.new("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP" if smooth else "LINEAR", clamp=True)
        s.link(n.inputs["Value"], v)
        n.inputs["From Min"].default_value = a
        n.inputs["From Max"].default_value = b
        n.inputs["To Min"].default_value = c
        n.inputs["To Max"].default_value = d
        return n.outputs["Result"]

    def mapping(s, v, scale=(1, 1, 1), loc=(0, 0, 0)):
        n = s.new("ShaderNodeMapping")
        s.link(n.inputs["Vector"], v)
        n.inputs["Scale"].default_value = scale
        n.inputs["Location"].default_value = loc
        return n.outputs[0]

    def noise(s, scale, detail=2.0, rough=0.5, v=None, stretch=None, dist=0.0, loc=(0, 0, 0)):
        v = v if v is not None else s.co()
        if stretch or loc != (0, 0, 0):
            v = s.mapping(v, stretch or (1, 1, 1), loc)
        n = s.new("ShaderNodeTexNoise")
        s.link(n.inputs["Vector"], v)
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = dist
        return n.outputs["Fac"]

    def voronoi(s, scale, v=None, stretch=None):
        v = v if v is not None else s.co()
        if stretch:
            v = s.mapping(v, stretch)
        n = s.new("ShaderNodeTexVoronoi")
        s.link(n.inputs["Vector"], v)
        n.inputs["Scale"].default_value = scale
        return n

    def white(s, w):
        n = s.new("ShaderNodeTexWhiteNoise", noise_dimensions="1D")
        s.link(n.inputs["W"], w)
        return n.outputs["Value"]

    def mixc(s, f, a, b):
        n = s.new("ShaderNodeMix", data_type="RGBA")
        s.link(n.inputs[0], f)
        s.link(n.inputs[6], a)
        s.link(n.inputs[7], b)
        return n.outputs[2]

    def dist2d(s, x, z, cx, cz, rx=1.0, rz=1.0):
        dx = s.m("MULTIPLY", s.sub(x, cx), 1.0 / rx)
        dz = s.m("MULTIPLY", s.sub(z, cz), 1.0 / rz)
        n = s.new("ShaderNodeVectorMath", operation="LENGTH")
        s.link(n.inputs[0], s.vec(dx, 0.0, dz))
        return n.outputs["Value"]

    def const(s, v):
        if isinstance(v, bpy.types.NodeSocket):
            return v
        if isinstance(v, (int, float)):
            n = s.new("ShaderNodeValue")
            n.outputs[0].default_value = v
            return n.outputs[0]
        n = s.new("ShaderNodeRGB")
        n.outputs[0].default_value = (*v, 1.0)
        return n.outputs[0]


# --- surface kinds. Coordinates are object-local meters (body: world, door: hinge origin).
def k_paint(b):   # cabinet sides and top: graphite painted steel
    x, y, z = b.xyz(b.co())
    nz = b.xyz(b.nrm())[2]
    peel = b.noise(320, 2, 0.5)
    top = b.mr(nz, 0.7, 0.95)
    dust = b.mul(b.mr(b.noise(14, 4, 0.6), 0.38, 0.78, 0.2, 1.0), top)
    low = b.mr(z, 0.32, 0.03)
    scr = b.mr(b.noise(1.0, 3, 0.6, stretch=(9, 9, 170)), 0.63, 0.69)
    scuff = b.mul(b.mul(scr, low), b.mr(b.noise(5, 2), 0.42, 0.62))
    grime = b.mul(b.mr(b.noise(4, 3), 0.3, 0.7), b.mul(low, low))
    col = b.mixc(dust, (0.040, 0.044, 0.052), (0.15, 0.145, 0.13))
    col = b.mixc(b.mul(grime, 0.6), col, (0.018, 0.018, 0.018))
    col = b.mixc(scuff, col, (0.11, 0.11, 0.115))
    rough = b.lin(0.34, (peel, 0.05), (dust, 0.35), (scuff, 0.18), (grime, 0.18))
    return dict(color=col, rough=rough, metal=0.0, height=peel, bump=0.05, dist=0.0003)


def k_stainless(b):   # door skin, vertical brushing, fingerprints around the handle
    x, y, z = b.xyz(b.co())
    g1 = b.noise(1.0, 2, 0.5, stretch=(700, 700, 5))
    g2 = b.noise(1.0, 3, 0.5, stretch=(160, 160, 1.5))
    zone = b.mr(b.dist2d(x, z, 0.53, 1.25, 0.12, 0.42), 1.25, 0.4, smooth=True)
    zone2 = b.mul(b.mr(b.dist2d(x, z, 0.50, 0.30, 0.20, 0.25), 1.2, 0.3, smooth=True), 0.5)  # knee/foot pushes
    rnd = b.mul(b.mr(b.noise(2.2, 2, loc=(3.1, 0, 0)), 0.60, 0.72), 0.45)
    zone = b.mx(b.mx(zone, zone2), rnd)
    vor = b.voronoi(42, stretch=(1, 1, 0.7))
    vd = b.add(vor.outputs["Distance"], b.m("MULTIPLY_ADD", b.noise(260, 2), 0.16, -0.08))
    blob = b.mul(b.mr(vd, 0.30, 0.20), b.mr(b.noise(120, 3), 0.35, 0.65))
    cellr = b.mr(b.xyz(vor.outputs["Color"])[0], 0.5, 0.62)
    prints = b.mul(b.mul(b.mul(blob, cellr), zone), 0.7)
    smear = b.mul(b.mul(b.mr(b.noise(9, 4, 0.55), 0.45, 0.72), zone), 0.6)
    finger = b.mx(prints, smear)
    low = b.mr(z, 0.26, 0.05)
    scr = b.mul(b.mul(b.mr(b.noise(1.0, 3, 0.6, stretch=(6, 6, 220)), 0.655, 0.705), low),
                b.mr(b.noise(4, 2), 0.35, 0.6))
    col = b.mixc(b.mul(finger, 0.6), (0.55, 0.56, 0.57), (0.47, 0.47, 0.46))
    col = b.mixc(scr, col, (0.36, 0.36, 0.37))
    rough = b.lin(0.245, (g1, 0.06), (g2, 0.05), (finger, 0.14), (scr, 0.22))
    h = b.lin(0.0, (g1, 0.6), (g2, 0.4), (scr, -0.5), clamp=False)
    return dict(color=col, rough=rough, metal=1.0, height=h, bump=0.03, dist=0.0002)


def k_handle(b):
    g1 = b.noise(1.0, 2, 0.5, stretch=(900, 900, 6))
    sm = b.mr(b.noise(28, 3, 0.6), 0.42, 0.7)
    col = b.mixc(b.mul(sm, 0.3), (0.62, 0.63, 0.65), (0.56, 0.56, 0.56))
    rough = b.lin(0.17, (g1, 0.05), (sm, 0.10))
    return dict(color=col, rough=rough, metal=1.0, height=g1, bump=0.02, dist=0.0002)


def k_rubber(b):
    x, y, z = b.xyz(b.co())
    n = b.noise(500, 2)
    low = b.mr(z, 0.45, 0.06)
    grime = b.mul(b.mr(b.noise(18, 3), 0.35, 0.65), low)
    col = b.mixc(grime, (0.050, 0.052, 0.056), (0.022, 0.021, 0.020))
    rough = b.lin(0.66, (n, 0.08), (grime, 0.12))
    return dict(color=col, rough=rough, metal=0.0, height=n, bump=0.1, dist=0.0003)


def k_darkplastic(b):
    x, y, z = b.xyz(b.co())
    n = b.noise(1100, 1)
    low = b.mr(z, 0.12, 0.0)
    scr = b.mul(b.mr(b.noise(1.0, 3, 0.6, stretch=(8, 8, 260)), 0.64, 0.70), low)
    col = b.mixc(scr, (0.034, 0.036, 0.040), (0.09, 0.09, 0.095))
    rough = b.lin(0.42, (n, 0.08), (scr, 0.2))
    return dict(color=col, rough=rough, metal=0.0, height=n, bump=0.08, dist=0.0002)


def k_grille(b):
    x, y, z = b.xyz(b.co())
    f = b.m("FRACT", b.m("MULTIPLY", x, 1.0 / 0.010))
    slot = b.mr(b.m("ABSOLUTE", b.sub(f, 0.5)), 0.24, 0.19)
    rz = b.mul(b.mr(z, 0.021, 0.024), b.mr(z, 0.041, 0.038))
    rx = b.mr(b.m("ABSOLUTE", x), 0.27, 0.265)
    hole = b.mul(b.mul(slot, rz), rx)
    col = b.mixc(hole, (0.030, 0.032, 0.035), (0.003, 0.003, 0.003))
    rough = b.lin(0.45, (hole, 0.45))
    h = b.lin(1.0, (hole, -1.0), clamp=False)
    return dict(color=col, rough=rough, metal=0.0, height=h, bump=0.8, dist=0.003)


def k_blackglass(b):
    sm = b.mr(b.noise(40, 3), 0.5, 0.75)
    return dict(color=(0.006, 0.006, 0.008), rough=b.lin(0.06, (sm, 0.1)), metal=0.0, height=None)


def k_liner(b):   # white ABS liner
    x, y, z = b.xyz(b.co())
    nz = b.xyz(b.nrm())[2]
    n = b.noise(900, 1)
    up = b.mr(nz, 0.7, 0.95)
    stain = b.mul(b.mr(b.noise(7, 3, 0.6, loc=(1.7, 0, 0)), 0.62, 0.74), up)
    age = b.mul(b.mr(b.noise(1.6, 2), 0.4, 0.7), 0.35)
    col = b.mixc(age, (0.80, 0.81, 0.80), (0.74, 0.73, 0.67))
    col = b.mixc(stain, col, (0.66, 0.60, 0.47))
    rough = b.lin(0.28, (n, 0.06), (stain, 0.16))
    return dict(color=col, rough=rough, metal=0.0, height=n, bump=0.05, dist=0.0002)


def k_shelfmetal(b):   # satin anodized aluminium plate, brushed front to back
    x, y, z = b.xyz(b.co())
    nz = b.xyz(b.nrm())[2]
    up = b.mr(nz, 0.7, 0.95)
    g = b.noise(1.0, 2, 0.5, stretch=(500, 4, 500))
    vor = b.voronoi(9)
    ring = b.mr(b.m("ABSOLUTE", b.sub(vor.outputs["Distance"], 0.30)), 0.03, 0.012)
    ring = b.mul(b.mul(ring, b.mr(b.xyz(vor.outputs["Color"])[0], 0.82, 0.86)), up)
    ring = b.mul(ring, b.mr(b.noise(60, 2), 0.3, 0.55))
    dust = b.mul(b.mr(b.noise(11, 3), 0.55, 0.75), up)
    col = b.mixc(b.mx(ring, b.mul(dust, 0.5)), (0.50, 0.51, 0.53), (0.42, 0.40, 0.36))
    rough = b.lin(0.36, (g, 0.06), (ring, 0.25), (dust, 0.12))
    return dict(color=col, rough=rough, metal=1.0, height=g, bump=0.02, dist=0.0002)


def k_binplastic(b):   # frosted, slightly blue-grey polystyrene
    n = b.noise(60, 3)
    sc = b.mr(b.noise(1.0, 3, 0.6, stretch=(40, 40, 400)), 0.66, 0.72)
    col = b.mixc(b.mul(sc, 0.5), (0.42, 0.48, 0.52), (0.60, 0.64, 0.66))
    rough = b.lin(0.2, (b.mr(n, 0.6, 0.8), 0.15), (sc, 0.2))
    return dict(color=col, rough=rough, metal=0.0, height=None)


def k_trim(b):   # satin aluminium trim strips (shelf fronts, bin rims, drawer pull)
    g = b.noise(1.0, 2, 0.5, stretch=(4, 600, 600))
    sm = b.mr(b.noise(30, 3), 0.5, 0.72)
    col = b.mixc(b.mul(sm, 0.5), (0.72, 0.73, 0.75), (0.60, 0.60, 0.60))
    return dict(color=col, rough=b.lin(0.24, (g, 0.08), (sm, 0.12)), metal=1.0, height=g, bump=0.02, dist=0.0002)


def k_vent(b):   # fan cover on the back wall: liner plastic with horizontal slots on the front face
    base = k_liner(b)
    x, y, z = b.xyz(b.co())
    ny = b.xyz(b.nrm())[1]
    f = b.m("FRACT", b.m("MULTIPLY", z, 1.0 / 0.012))
    slot = b.mr(b.m("ABSOLUTE", b.sub(f, 0.5)), 0.2, 0.15)
    m = b.mul(b.mul(slot, b.mr(b.m("ABSOLUTE", x), 0.072, 0.068)), b.mr(ny, -0.8, -0.95))
    m = b.mul(m, b.mul(b.mr(z, 1.615, 1.62), b.mr(z, 1.725, 1.72)))
    col = b.mixc(m, base["color"], (0.02, 0.02, 0.022))
    rough = b.lin(0.0, (base["rough"], 1.0), (m, 0.4))
    h = b.lin(1.0, (m, -1.0), clamp=False)
    return dict(color=col, rough=rough, metal=0.0, height=h, bump=0.8, dist=0.003)


def k_paper(b):   # handwritten shopping note
    x, y, z = b.xyz(b.co())
    u = b.add(b.m("MULTIPLY", b.sub(1.235, z), 1.0 / 0.019), b.m("MULTIPLY_ADD", b.noise(70, 2), 0.5, -0.25))
    f = b.m("FRACT", u)
    idx = b.m("FLOOR", u)
    stroke = b.mr(b.m("ABSOLUTE", b.sub(f, 0.5)), 0.13, 0.06)
    word = b.mr(b.noise(1.0, 2, 0.5, stretch=(55, 55, 8)), 0.40, 0.46)
    ltr = b.mr(b.noise(1.0, 1, 0.5, stretch=(420, 420, 70)), 0.33, 0.47)
    valid = b.mul(b.m("GREATER_THAN", idx, -0.5), b.m("LESS_THAN", idx, 6.5))
    end = b.m("MULTIPLY_ADD", b.white(idx), 0.075, 0.135)
    xm = b.mul(b.m("LESS_THAN", x, end), b.m("GREATER_THAN", x, 0.113))
    ink = b.mul(b.mul(b.mul(stroke, word), b.mul(ltr, valid)), xm)
    col = b.mixc(ink, (0.78, 0.75, 0.66), (0.02, 0.04, 0.13))
    crumple = b.noise(22, 3)
    col = b.mixc(b.mul(b.mr(crumple, 0.55, 0.8), 0.25), col, (0.62, 0.58, 0.48))
    rough = b.lin(0.82, (ink, -0.2))
    return dict(color=col, rough=rough, metal=0.0, height=crumple, bump=0.15, dist=0.001)


def k_magnet(b):
    sc = b.mr(b.noise(80, 3), 0.62, 0.72)
    col = b.mixc(sc, (0.72, 0.015, 0.10), (0.55, 0.10, 0.16))
    return dict(color=col, rough=b.lin(0.26, (sc, 0.25)), metal=0.0, height=None)


def k_sticker(b):   # round housing-authority sticker: navy, cyan ring, magenta dot
    x, y, z = b.xyz(b.co())
    r = b.dist2d(x, z, 0.14, 0.93)
    ring = b.mr(b.m("ABSOLUTE", b.sub(r, 0.017)), 0.0032, 0.0022)
    dot = b.mr(r, 0.0075, 0.0065)
    wear = b.mr(b.noise(90, 3), 0.6, 0.7)
    col = b.mixc(ring, (0.010, 0.016, 0.035), (0.0, 0.50, 0.58))
    col = b.mixc(dot, col, (0.85, 0.03, 0.16))
    col = b.mixc(b.mul(wear, 0.7), col, (0.55, 0.55, 0.55))
    return dict(color=col, rough=b.lin(0.32, (wear, 0.35)), metal=0.0, height=None)


KINDS = dict(paint=k_paint, stainless=k_stainless, handle=k_handle, rubber=k_rubber,
             darkplastic=k_darkplastic, grille=k_grille, blackglass=k_blackglass, liner=k_liner,
             shelfmetal=k_shelfmetal, binplastic=k_binplastic, paper=k_paper, magnet=k_magnet,
             sticker=k_sticker, trim=k_trim, vent=k_vent)


def src(group, kind):
    key = (group, kind)
    if key in SRC:
        return SRC[key]
    mat = bpy.data.materials.new(f"SRC_{group}_{kind}")
    try:
        mat.use_nodes = True
    except Exception:
        pass
    b = NB(mat)
    ch = KINDS[kind](b)
    p = b.new("ShaderNodeBsdfPrincipled")
    col = b.const(ch["color"])
    rough = b.const(ch["rough"])
    metal = b.const(ch["metal"])
    b.link(p.inputs["Base Color"], col)
    b.link(p.inputs["Roughness"], rough)
    b.link(p.inputs["Metallic"], metal)
    if ch.get("height") is not None:
        bump = b.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = ch["bump"]
        bump.inputs["Distance"].default_value = ch["dist"]
        b.link(bump.inputs["Height"], ch["height"])
        b.link(p.inputs["Normal"], bump.outputs["Normal"])
    out = b.new("ShaderNodeOutputMaterial")
    b.link(out.inputs["Surface"], p.outputs["BSDF"])
    em = b.new("ShaderNodeEmission")
    img = b.new("ShaderNodeTexImage")
    b.nt.nodes.active = img
    CH[mat.name] = dict(group=group, color=col, rough=rough, metal=metal, bsdf=p, out=out, emit=em, img=img, nt=b.nt)
    SRC[key] = mat
    return mat


def solid_mat(name, base, rough, emit=None, strength=0.0, emit_tex=None):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*base, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = 0.0
    if emit is not None:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = strength
    if emit_tex is not None:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = emit_tex
        nt.links.new(t.outputs["Color"], p.inputs["Emission Color"])
        p.inputs["Emission Strength"].default_value = strength
    return mat


# ---------------------------------------------------------------- geometry helpers
def mk(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    COLL.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def bm_box(bm, lo, hi):
    g = bmesh.ops.create_cube(bm, size=1.0)
    for v in g["verts"]:
        v.co = Vector([lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3)])
    return g["verts"]


def box(name, lo, hi):
    bm = bmesh.new()
    bm_box(bm, lo, hi)
    return mk(name, bm)


def cyl(name, center, r, depth, axis="Z", seg=24):
    bm = bmesh.new()
    rot = {"Z": Matrix.Identity(4), "Y": Matrix.Rotation(math.radians(90), 4, "X"),
           "X": Matrix.Rotation(math.radians(90), 4, "Y")}[axis]
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r,
                          depth=depth, matrix=Matrix.Translation(Vector(center)) @ rot)
    return mk(name, bm)


def quad_xz(name, x0, x1, z0, z1, y, rot_deg=0.0):
    bm = bmesh.new()
    c = Vector(((x0 + x1) / 2, y, (z0 + z1) / 2))
    R = Matrix.Rotation(math.radians(rot_deg), 3, "Y")
    vs = [bm.verts.new(c + R @ (Vector((px, y, pz)) - c)) for px, pz in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))]
    bm.faces.new(vs)   # X x Z -> normal -Y
    return mk(name, bm)


def disc_xz(name, cx, cz, r, y, seg=32):
    bm = bmesh.new()
    vs = [bm.verts.new((cx + r * math.cos(a), y, cz + r * math.sin(a)))
          for a in [2 * math.pi * i / seg for i in range(seg)]]
    bm.faces.new(vs)   # counter-clockwise in XZ -> normal -Y
    return mk(name, bm)


def bevel(ob, width, seg=3, angle=35.0, limit="ANGLE"):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = seg
    m.limit_method = limit
    m.angle_limit = math.radians(angle)
    m.harden_normals = True
    m.use_clamp_overlap = True
    return m


def solidify(ob, t):
    m = ob.modifiers.new("Solid", "SOLIDIFY")
    m.thickness = t
    m.offset = -1.0
    m.use_even_offset = True
    return m


def boolean(ob, cutter):
    m = ob.modifiers.new("Bool", "BOOLEAN")
    m.object = cutter
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    return m


def apply(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    me.name = ob.name


def delete_faces(ob, pred):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    dead = [f for f in bm.faces if pred(f.calc_center_median(), f.normal, f)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()


def remove_top(ob):
    delete_faces(ob, lambda c, n, f: n.z > 0.9)


def set_mat(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def assign(ob, fn):
    me = ob.data
    mats, idx = [], []
    for p in me.polygons:
        m = fn(p.center, p.normal)
        if m not in mats:
            mats.append(m)
        idx.append(mats.index(m))
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", idx)


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    with bpy.context.temp_override(active_object=objs[0], object=objs[0], selected_objects=objs,
                                   selected_editable_objects=objs):
        bpy.ops.object.join()
    ob = objs[0]
    ob.name = name
    ob.data.name = name
    return ob


def remove(ob):
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if me and me.users == 0:
        bpy.data.meshes.remove(me)


# ================================================================ BODY
log("building body")
BX = lambda k: src("body_ext", k)
BI = lambda k: src("body_int", k)

cab = box("FridgeCabinet", (-S.CAB_X, -S.CAB_Y, S.FOOT_H), (S.CAB_X, S.CAB_Y, S.CAB_H))
cav = box("cut_cav", (-S.CAV_X, -0.45, S.CAV_Z0), (S.CAV_X, S.CAV_BACK, S.CAV_Z1))
bevel(cav, S.CAV_R, 4, limit="NONE")
apply(cav)
plinth = box("cut_plinth", (-0.285, -0.40, -0.05), (0.285, -0.300, S.PLINTH_TOP))
boolean(cab, cav)
boolean(cab, plinth)
apply(cab)
remove(cav)
remove(plinth)
bevel(cab, 0.005, 3, 35)
apply(cab)


def cab_mat(c, n):
    if abs(c.x) < 0.2552 and S.CAV_Z0 - 0.0002 < c.z < S.CAV_Z1 + 0.0002 and -0.3236 < c.y < S.CAV_BACK + 0.0002:
        return BI("liner")
    if c.y < -0.2995 and c.z < S.PLINTH_TOP + 0.0005 and abs(c.x) < 0.2855:
        return BX("grille")
    return BX("paint")


assign(cab, cab_mat)
body_parts = [cab]

# feet
for fx in (-0.24, 0.24):
    for fy in (-0.27, 0.27):
        f = cyl("foot", (fx, fy, S.FOOT_H / 2 + 0.0005), 0.02, S.FOOT_H + 0.001, "Z", 20)
        bevel(f, 0.002, 2, 35)
        apply(f)
        set_mat(f, BX("darkplastic"))
        body_parts.append(f)


def shelf(top, name):
    parts = []
    p = box(name + "_plate", (-S.SHELF_X, -0.195, top - 0.010), (S.SHELF_X, S.SHELF_Y1, top))
    bevel(p, 0.002, 2)
    apply(p)
    set_mat(p, BI("shelfmetal"))
    parts.append(p)
    t = box(name + "_trim", (-S.SHELF_X, S.SHELF_Y0, top - 0.024), (S.SHELF_X, -0.193, top + 0.004))
    bevel(t, 0.003, 3)
    apply(t)
    set_mat(t, BI("trim"))
    parts.append(t)
    l = box(name + "_lip", (-S.SHELF_X, S.SHELF_Y1 - 0.009, top - 0.002), (S.SHELF_X, S.SHELF_Y1, top + 0.014))
    bevel(l, 0.002, 2)
    apply(l)
    set_mat(l, BI("darkplastic"))
    parts.append(l)
    for sx in (-1, 1):   # support ribs moulded into the liner
        x0, x1 = (S.CAV_X - 0.0105, S.CAV_X + 0.0005)
        if sx < 0:
            x0, x1 = -x1, -x0
        r = box(name + "_rib", (x0, -0.195, top - 0.010 - 0.008), (x1, 0.255, top - 0.010))
        bevel(r, 0.002, 2)
        apply(r)
        set_mat(r, BI("liner"))
        parts.append(r)
    return parts


body_parts += shelf(S.CRISPER_COVER_TOP, "CrisperCover")
for i, t in enumerate(S.SHELF_TOPS):
    body_parts += shelf(t, f"Shelf{i + 1}")
vent = box("vent", (-0.09, S.CAV_BACK - 0.016, 1.60), (0.09, S.CAV_BACK + 0.001, 1.74))
bevel(vent, 0.006, 4, 35)
apply(vent)
set_mat(vent, BI("vent"))
body_parts.append(vent)
cab = join(body_parts, "FridgeCabinet")

# crisper drawer
dp = []
tray = box("tray", (-0.238, -0.196, S.DRAWER_Z0 + 0.001), (0.238, S.DRAWER_Y1, 0.300))
remove_top(tray)
solidify(tray, 0.003)
bevel(tray, 0.003, 2, 35)
apply(tray)
set_mat(tray, BI("binplastic"))
dp.append(tray)
front = box("front", (-S.DRAWER_X, S.DRAWER_Y0, S.DRAWER_Z0), (S.DRAWER_X, -0.193, S.DRAWER_Z1 - 0.006))
bevel(front, 0.004, 3)
apply(front)
set_mat(front, BI("binplastic"))
dp.append(front)
lip = box("lip", (-0.17, S.DRAWER_Y0 - 0.010, S.DRAWER_Z1 - 0.022), (0.17, S.DRAWER_Y0 + 0.002, S.DRAWER_Z1))
bevel(lip, 0.005, 3)
apply(lip)
set_mat(lip, BI("trim"))
dp.append(lip)
drawer = join(dp, "CrisperDrawer")
D_ORIGIN = Vector((0.0, S.DRAWER_Y0, S.DRAWER_Z0))
drawer.data.transform(Matrix.Translation(-D_ORIGIN))
drawer.location = D_ORIGIN

# interior light: ceiling panel + two slim LED columns on the side walls
LIGHT = solid_mat("FridgeLight", (0.92, 0.93, 0.95), 0.35, emit=(1.0, 0.965, 0.92), strength=4.0)
lp = []
pnl = box("pnl", (-0.14, -0.25, S.CAV_Z1 - 0.009), (0.14, -0.17, S.CAV_Z1 + 0.0005))
bevel(pnl, 0.003, 2)
apply(pnl)
lp.append(pnl)
for sx in (-1, 1):
    x0, x1 = S.CAV_X - 0.0045, S.CAV_X + 0.0005
    if sx < 0:
        x0, x1 = -x1, -x0
    st = box("strip", (x0, -0.300, 0.37), (x1, -0.282, 1.74))
    bevel(st, 0.0015, 2)
    apply(st)
    lp.append(st)
for o in lp:
    set_mat(o, LIGHT)
lightpanel = join(lp, "FridgeLightPanel")

# ================================================================ DOOR (door-local)
log("building door")
DX = lambda k: src("door_ext", k)
DI = lambda k: src("door_int", k)
door_parts = []

bm = bmesh.new()
bm_box(bm, (0.0, S.SLAB_Y0, S.DOOR_Z0), (S.DOOR_W, S.SLAB_Y1, S.DOOR_Z1))
backf = [f for f in bm.faces if f.normal.y > 0.9][0]
bmesh.ops.inset_individual(bm, faces=[backf], thickness=0.05)
for v in backf.verts:   # hidden centre of the back face (covered by the liner panel) gets deleted
    v.co.x = 0.06 if v.co.x < 0.3 else 0.54
    v.co.z = 0.13 if v.co.z < 0.9 else 1.76
backf.material_index = 1
slab = mk("slab", bm)
bevel(slab, 0.006, 4, 35)
apply(slab)
delete_faces(slab, lambda c, n, f: f.material_index == 1)


def slab_mat(c, n):
    if abs(n.z) > 0.7:
        return DX("darkplastic")
    if n.y > 0.7:
        return DI("liner")
    return DX("stainless")


assign(slab, slab_mat)
door_parts.append(slab)

g_out = box("gasket", (0.012, -0.015, 0.057), (0.588, -0.001, 1.833))
g_in = box("g_in", (0.036, -0.05, 0.081), (0.564, 0.05, 1.809))
boolean(g_out, g_in)
apply(g_out)
remove(g_in)
bevel(g_out, 0.005, 3, 35)
apply(g_out)
delete_faces(g_out, lambda c, n, f: c.y < -0.0125)
set_mat(g_out, DX("rubber"))
door_parts.append(g_out)

panel = box("panel", (0.05, -0.014, 0.12), (0.55, 0.018, 1.77))
bevel(panel, 0.008, 4, 35)
apply(panel)
delete_faces(panel, lambda c, n, f: c.y < -0.0125)
set_mat(panel, DI("liner"))
door_parts.append(panel)

for x0, x1 in ((0.065, 0.086), (0.514, 0.535)):
    r = box("ridge", (x0, 0.015, 0.345), (x1, 0.100, 1.73))   # starts above the pulled-out crisper
    bevel(r, 0.006, 3, 35)
    apply(r)
    delete_faces(r, lambda c, n, f: c.y < 0.0165)
    set_mat(r, DI("liner"))
    door_parts.append(r)

for i, (z0, h) in enumerate(S.BINS):
    t = box(f"bin{i}", (S.BIN_X0, S.BIN_Y0, z0), (S.BIN_X1, S.BIN_Y1 - 0.002, z0 + h))
    remove_top(t)
    solidify(t, 0.003)
    bevel(t, 0.0025, 2, 35)
    apply(t)
    set_mat(t, DI("binplastic"))
    door_parts.append(t)
    rim = box(f"rim{i}", (S.BIN_X0, S.BIN_Y1 - 0.010, z0 + h - 0.012), (S.BIN_X1, S.BIN_Y1, z0 + h))
    bevel(rim, 0.003, 3, 35)
    apply(rim)
    set_mat(rim, DI("trim"))
    door_parts.append(rim)

bar = box("bar", (S.HANDLE_X - 0.011, S.HANDLE_Y0, S.HANDLE_Z0), (S.HANDLE_X + 0.011, S.HANDLE_Y1, S.HANDLE_Z1))
bevel(bar, 0.0085, 5, 35)
apply(bar)
set_mat(bar, DX("handle"))
door_parts.append(bar)
for zc in (S.HANDLE_Z0 + 0.035, S.HANDLE_Z1 - 0.035):
    py0, py1 = -0.060, S.HANDLE_Y1 - 0.002      # embedded 2 mm into slab and bar
    post = cyl("post", (S.HANDLE_X, (py0 + py1) / 2, zc), 0.0085, py0 - py1, "Y", 20)
    bevel(post, 0.0015, 2, 35)
    apply(post)
    set_mat(post, DX("handle"))
    door_parts.append(post)
    pad = box("pad", (S.HANDLE_X - 0.014, -0.0645, zc - 0.018), (S.HANDLE_X + 0.014, -0.060, zc + 0.018))
    bevel(pad, 0.002, 3, 35)
    apply(pad)
    set_mat(pad, DX("darkplastic"))
    door_parts.append(pad)

bez = box("bezel", (S.DISP_X0 - 0.005, -0.0645, S.DISP_Z0 - 0.005), (S.DISP_X1 + 0.005, -0.060, S.DISP_Z1 + 0.005))
bevel(bez, 0.0015, 2, 35)
apply(bez)
set_mat(bez, DX("blackglass"))
door_parts.append(bez)


# display texture: seven-segment "4°C" plus a level indicator, cyan on black
def display_image():
    W, H = 256, 128
    lit = np.zeros((H, W), np.float32)
    ghost = np.zeros((H, W), np.float32)

    def rect(buf, x0, y0, x1, y1, v=1.0):
        buf[int(y0):int(y1), int(x0):int(x1)] = np.maximum(buf[int(y0):int(y1), int(x0):int(x1)], v)

    def digit(ox, oy, w, h, t, segs):
        m = h / 2
        S7 = dict(a=(ox + t, oy, ox + w - t, oy + t), b=(ox + w - t, oy + t, ox + w, oy + m),
                  c=(ox + w - t, oy + m, ox + w, oy + h - t), d=(ox + t, oy + h - t, ox + w - t, oy + h),
                  e=(ox, oy + m, ox + t, oy + h - t), f=(ox, oy + t, ox + t, oy + m),
                  g=(ox + t, oy + m - t / 2, ox + w - t, oy + m + t / 2))
        for k, r in S7.items():
            rect(lit if k in segs else ghost, *r)

    digit(34, 22, 50, 84, 10, "fgbc")          # 4
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.hypot(xx - 100, yy - 32)
    lit[(rr < 9) & (rr > 5)] = 1.0              # degree sign
    digit(116, 22, 44, 84, 10, "afed")         # C
    for i, hh in enumerate((18, 30, 42)):       # level bars, lit
        rect(lit, 186 + i * 16, 106 - hh, 196 + i * 16, 106)
    rect(ghost, 234, 50, 244, 106)
    img = ghost * 0.07 + lit
    # soft glow
    k = 5
    pad = np.pad(lit, k, mode="constant")
    glow = np.zeros_like(lit)
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            glow += pad[k + dy:k + dy + H, k + dx:k + dx + W]
    glow /= (2 * k + 1) ** 2
    img = np.clip(img + glow * 0.35, 0, 1)
    cyan = np.array([0.02, 0.851, 0.91])       # sRGB #05D9E8
    rgba = np.ones((H, W, 4), np.float32)
    rgba[..., :3] = img[..., None] * cyan
    rgba = rgba[::-1]                           # Blender rows start at the bottom
    im = bpy.data.images.new("fridge_display_emission", W, H, alpha=False)
    im.pixels.foreach_set(rgba.ravel())
    return im


DISPLAY_IMG = display_image()
DISPLAY = solid_mat("FridgeDisplay", (0.004, 0.004, 0.005), 0.12, emit_tex=DISPLAY_IMG, strength=1.5)
scr = quad_xz("screen", S.DISP_X0, S.DISP_X1, S.DISP_Z0, S.DISP_Z1, -0.0648)
set_mat(scr, DISPLAY)
door_parts.append(scr)

note = quad_xz("note", 0.10, 0.22, 1.10, 1.27, -0.0626, rot_deg=3.0)
set_mat(note, DX("paper"))
door_parts.append(note)
mag = cyl("magnet", (0.157, -0.0667, 1.252), 0.013, 0.0082, "Y", 24)
bevel(mag, 0.0022, 3, 35)
apply(mag)
set_mat(mag, DX("magnet"))
door_parts.append(mag)
stk = disc_xz("sticker", 0.14, 0.93, 0.024, -0.0623)
set_mat(stk, DX("sticker"))
door_parts.append(stk)

door = join(door_parts, "FridgeDoor")
door.location = (S.HINGE[0], S.HINGE[1], 0.0)

grip = bpy.data.objects.new("HandleGrip", None)
grip.empty_display_type = "PLAIN_AXES"
grip.empty_display_size = 0.05
COLL.objects.link(grip)
grip.parent = door
grip.location = S.GRIP

# ================================================================ UVs
log("unwrapping")
BAKED = [cab, drawer, door]
for ob in BAKED:
    ob.data.uv_layers.new(name="UVMap")
lightpanel.data.uv_layers.new(name="UVMap")
scene.tool_settings.use_uv_select_sync = True
bpy.ops.object.select_all(action="DESELECT")
for ob in BAKED:
    ob.select_set(True)
bpy.context.view_layer.objects.active = cab
bpy.ops.object.mode_set(mode="EDIT")
for g in S.TEX:
    for ob in BAKED:
        bm = bmesh.from_edit_mesh(ob.data)
        names = [ms.material.name if ms.material else "" for ms in ob.material_slots]
        for f in bm.faces:
            f.select_set(names[f.material_index].startswith(f"SRC_{g}_"))
        bm.select_flush_mode()
        bmesh.update_edit_mesh(ob.data)
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.002, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
bpy.ops.object.mode_set(mode="OBJECT")

# display quad gets a 0..1 mapping
me = door.data
uv = me.uv_layers["UVMap"].data
disp_idx = [i for i, ms in enumerate(door.material_slots) if ms.material == DISPLAY][0]
for p in me.polygons:
    if p.material_index == disp_idx:
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = ((co.x - S.DISP_X0) / (S.DISP_X1 - S.DISP_X0), (co.z - S.DISP_Z0) / (S.DISP_Z1 - S.DISP_Z0))

# ================================================================ BAKE
log("baking")
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU"
except Exception as e:
    log("GPU setup failed, CPU bake", e)
if scene.world is None:
    scene.world = bpy.data.worlds.new("World")
scene.world.light_settings.distance = 0.12
bk = scene.render.bake
bk.margin = 8
bk.margin_type = "EXTEND"
bk.use_clear = True
bk.target = "IMAGE_TEXTURES"

IMGS = {}
for g, size in S.TEX.items():
    if FAST:
        size //= 4
    for chn in ("color", "rough", "metal", "normal", "ao"):
        im = bpy.data.images.new(f"bake_{g}_{chn}", size, size, alpha=False)
        im.colorspace_settings.name = "sRGB" if chn == "color" else "Non-Color"
        if chn == "normal":
            im.generated_color = (0.5, 0.5, 1.0, 1.0)
        IMGS[(g, chn)] = im


def select_baked():
    bpy.ops.object.select_all(action="DESELECT")
    for ob in BAKED:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = cab


def prep(chn):
    for name, c in CH.items():
        nt = c["nt"]
        c["img"].image = IMGS[(c["group"], chn)]
        nt.nodes.active = c["img"]
        for l in list(c["out"].inputs["Surface"].links):
            nt.links.remove(l)
        if chn in ("color", "rough", "metal"):
            for l in list(c["emit"].inputs["Color"].links):
                nt.links.remove(l)
            nt.links.new(c[chn], c["emit"].inputs["Color"])
            nt.links.new(c["emit"].outputs[0], c["out"].inputs["Surface"])
        else:
            nt.links.new(c["bsdf"].outputs["BSDF"], c["out"].inputs["Surface"])


# the display material is not baked: give it a throwaway target so the bake can't touch its texture
DUMMY = bpy.data.images.new("bake_dummy", 16, 16)
dn = DISPLAY.node_tree.nodes.new("ShaderNodeTexImage")
dn.image = DUMMY
DISPLAY.node_tree.nodes.active = dn
select_baked()
for chn in ("color", "rough", "metal", "normal"):
    prep(chn)
    scene.cycles.samples = 4 if FAST else 16
    t = time.time()
    if chn == "normal":
        bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
    else:
        bpy.ops.object.bake(type="EMIT")
    log(f"baked {chn} in {time.time() - t:.1f}s")

# AO: move drawer and door away so each part only occludes itself
prep("ao")
drawer.location.x += 10.0
door.location.x += 20.0
bpy.context.view_layer.update()
scene.cycles.samples = 32 if FAST else 256
t = time.time()
bpy.ops.object.bake(type="AO")
log(f"baked ao in {time.time() - t:.1f}s")
drawer.location = D_ORIGIN
door.location = (S.HINGE[0], S.HINGE[1], 0.0)
DISPLAY.node_tree.nodes.remove(dn)
bpy.data.images.remove(DUMMY)

# ================================================================ FINAL MATERIALS
log("building final materials")


def px(im):
    a = np.empty(im.size[0] * im.size[1] * 4, np.float32)
    im.pixels.foreach_get(a)
    return a.reshape(im.size[1], im.size[0], 4)


def save_pack(im, name):
    im.name = name
    path = os.path.join(TEX_TMP, name + ".png")
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    im.pack()
    im.filepath_raw = f"//fridge__opus-high_tex/{name}.png"
    return im


gltf_out = bpy.data.node_groups.get("glTF Material Output")
if gltf_out is None:
    gltf_out = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    gltf_out.interface.new_socket(name="Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")

FINALS = {}
for g, mname in S.FINAL.items():

    stem = {"body_ext": "fridge_body", "body_int": "fridge_interior", "door_ext": "fridge_door",
            "door_int": "fridge_door_interior"}[g]
    alb = save_pack(IMGS[(g, "color")], f"{stem}_albedo")
    nrm = save_pack(IMGS[(g, "normal")], f"{stem}_normal")
    ao, ro, me_ = px(IMGS[(g, "ao")]), px(IMGS[(g, "rough")]), px(IMGS[(g, "metal")])
    w, h = IMGS[(g, "ao")].size
    orm = np.ones((h, w, 4), np.float32)
    orm[..., 0] = np.clip(ao[..., 0] * 0.85 + 0.15, 0, 1)   # keep AO gentle
    orm[..., 1] = ro[..., 0]
    orm[..., 2] = me_[..., 0]
    oim = bpy.data.images.new(f"{stem}_orm", w, h, alpha=False)
    oim.colorspace_settings.name = "Non-Color"
    oim.pixels.foreach_set(orm.ravel())
    save_pack(oim, f"{stem}_orm")
    for chn in ("ao", "rough", "metal"):
        bpy.data.images.remove(IMGS[(g, chn)])

    mat = bpy.data.materials.new(mname)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    p = nt.nodes.get("Principled BSDF")
    ta = nt.nodes.new("ShaderNodeTexImage"); ta.image = alb; ta.location = (-700, 300)
    to = nt.nodes.new("ShaderNodeTexImage"); to.image = oim; to.location = (-700, 0)
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = nrm; tn.location = (-700, -300)
    sep = nt.nodes.new("ShaderNodeSeparateColor"); sep.location = (-400, 0)
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (-400, -300)
    go = nt.nodes.new("ShaderNodeGroup"); go.node_tree = gltf_out; go.location = (0, -400)
    nt.links.new(ta.outputs["Color"], p.inputs["Base Color"])
    nt.links.new(to.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], p.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], p.inputs["Metallic"])
    nt.links.new(sep.outputs["Red"], go.inputs["Occlusion"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    FINALS[g] = mat

save_pack(DISPLAY_IMG, "fridge_display_emission")

for ob in BAKED:
    me = ob.data
    new = []
    for ms in ob.material_slots:
        m = ms.material
        new.append(FINALS[CH[m.name]["group"]] if m.name in CH else m)
    uniq = []
    for m in new:
        if m not in uniq:
            uniq.append(m)
    remap = [uniq.index(m) for m in new]
    idx = [0] * len(me.polygons)
    me.polygons.foreach_get("material_index", idx)
    idx = [remap[i] for i in idx]
    me.materials.clear()
    for m in uniq:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", idx)
for m in list(SRC.values()):
    bpy.data.materials.remove(m)

# ================================================================ COLLISION (body)
log("collision")
COLS = [
    ("CabinetFloor", (-S.CAB_X, -S.CAB_Y, 0.0), (S.CAB_X, S.CAB_Y, S.CAV_Z0)),
    ("CabinetWallL", (-S.CAB_X, -S.CAB_Y, S.CAV_Z0), (-S.CAV_X, S.CAB_Y, S.CAV_Z1)),
    ("CabinetWallR", (S.CAV_X, -S.CAB_Y, S.CAV_Z0), (S.CAB_X, S.CAB_Y, S.CAV_Z1)),
    ("CabinetTop", (-S.CAB_X, -S.CAB_Y, S.CAV_Z1), (S.CAB_X, S.CAB_Y, S.CAB_H)),
    ("CabinetBack", (-S.CAV_X, S.CAV_BACK, S.CAV_Z0), (S.CAV_X, S.CAB_Y, S.CAV_Z1)),
    ("CrisperCover", (-S.SHELF_X, S.SHELF_Y0, S.CRISPER_COVER_TOP - 0.03), (S.SHELF_X, S.SHELF_Y1, S.CRISPER_COVER_TOP)),
] + [(f"Shelf{i + 1}", (-S.SHELF_X, S.SHELF_Y0, t - 0.03), (S.SHELF_X, S.SHELF_Y1, t)) for i, t in enumerate(S.SHELF_TOPS)]
colcoll = bpy.data.collections.new("Collision")
scene.collection.children.link(colcoll)
for name, lo, hi in COLS:
    ob = box(name + "-convcolonly", lo, hi)
    COLL.objects.unlink(ob)
    colcoll.objects.link(ob)
    ob.display_type = "WIRE"
    ob.hide_render = True
    for p in ob.data.polygons:
        p.use_smooth = False

# collections for the two exports
cb = bpy.data.collections.new("FridgeBody")
cd = bpy.data.collections.new("FridgeDoor")
scene.collection.children.link(cb)
scene.collection.children.link(cd)
for ob in (cab, drawer, lightpanel):
    COLL.objects.unlink(ob); cb.objects.link(ob)
for ob in (door, grip):
    COLL.objects.unlink(ob); cd.objects.link(ob)

# ================================================================ report + save
dg = bpy.context.evaluated_depsgraph_get()
for ob in (cab, drawer, lightpanel, door):
    ob.data.calc_loop_triangles()
    log(f"{ob.name}: {len(ob.data.loop_triangles)} tris, mats {[m.name for m in ob.data.materials]}")
for m in bpy.data.materials:
    if m.users == 0:
        bpy.data.materials.remove(m)
for m in bpy.data.meshes:
    if m.users == 0:
        bpy.data.meshes.remove(m)
bpy.ops.wm.save_as_mainfile(filepath=S.BLEND, compress=True, relative_remap=True)
log("saved", S.BLEND)
