"""Silena's eyes (stage 4 of D-037, for the live mirror, D-049): eyeballs on the eye bones,
open lids with her calm, slightly hooded look, MPFB lashes and brows, blink shapes, and the
smoky eye makeup in the skin texture. Generic parts: arcology_blender.face.

- Fitting (`fit`, build.py before MPFB's helpers go): the eyelash and eyebrow proxies (CC0)
  as static meshes, the eyeballs' rotation centers (MPFB's eye joints).
- Lids (`build`, outfit.py after the head is split): the lid axis of each eye runs through
  its center from the inner to the outer corner of the measured opening. The upper lid is
  turned up by UPPER_REST_DEG (MPFB's covers the iris top by ~2.2 mm; hers by ~1.5 mm,
  hooded but awake), the lower one up by LOWER_REST_DEG (it meets the iris bottom: no
  sclera under the iris, her calm look), any outside of the lids that dips into the
  eyeball's sphere is pushed out (none on her), the opening is measured again for the
  shapes.
- Eyeballs (`Eyes`): a sphere (EYE_RADIUS, MPFB's eyeball) open behind EYE_BACK (inside the
  head), polar UVs (face.eyeball); the cornea's dome is in the normal map, so no geometry
  can cross the lids at any gaze. Each rigid on its bone `LeftEye` / `RightEye` (children
  of Head, head at the rotation center, +Y forward out of the pupil, +X toward her left on
  both, +Z down: the same axes for both).
- Lashes (`Lashes`, MPFB's natural lashes, the lower ones shortened) follow the lids'
  margins in every shape (turned with their margin point), brows (`Brows`) rigid on Head;
  both on one alpha-scissor material.
- Shapes on HeadMesh (joined in outfit_bake.py, keys merged by name): `BlinkLeft`,
  `BlinkRight` (her left = +X; upper lid down to a line 30 % up from the lower margin,
  slightly over it, the lower lid up to it), `LookDownLids` (both lids follow a 25 deg
  downward gaze).
- Textures (`bake_textures`, bake.py): the eye (iris, sclera, cornea normal, roughness;
  EYE_TEX), the lash/brow atlas (brow strands drawn along the brow's hair flow, MPFB's lash
  texture recolored), and the skin texture: each eye's region gets its own UV island
  EYE_UV_SCALE times larger in the texture's unused area (MPFB's skin resampled into it),
  then concealer and the makeup are composited over the face (smoky lids blended toward the
  temples, violet in the crease, liner, lower lash line, kohl on the waterline, a pink
  caruncle, the brow painted under its cards).

No per-vertex build data; the eye frames are stored on the armature (`eye_center_<side>`,
`eye_axis_<side>`).
"""

import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from silena_vesper_common import EYE_MAT, LASH_MAT, NAME
from arcology_blender import face, garment, human, rig
from arcology_blender.face import smoothstep, srgb
from arcology_blender.scene import tag

LASHES = "eyelashes01"       # MPFB system assets (CC0): natural lashes, upper and lower
BROWS = "eyebrow002"         # groomed, slightly arched
LASH_LENGTH = (0.92, 0.55)   # upper, lower lashes scaled toward their lid margin
SIDES = {"Left": 1.0, "Right": -1.0}
JOINTS = {"Left": "joint-l-eye", "Right": "joint-r-eye"}
BONES = {"Left": "LeftEye", "Right": "RightEye"}

EYE_RADIUS = 0.0170          # MPFB's eyeball (its eye proxy's inner sphere)
IRIS_RADIUS = 0.0057         # 11.4 mm iris
CORNEA = 0.0010              # the cornea dome's height over the sphere, in the normal map only
EYE_SEGMENTS = 32
EYE_BACK = 100.0             # the eyeball is open beyond this angle from its axis (hidden in the head)
EYE_BONE_LENGTH = 0.020      # tail just past the cornea
LID_CLEAR = 0.00015          # the lids' outside stays this far off the eyeball
UPPER_REST_DEG = 1.0         # upper lid turned up from MPFB's (covers the iris top ~1.5 mm)
LOWER_REST_DEG = 2.8         # lower lid turned up: it meets the iris bottom (calm, no sclera under the iris)
LID_UPPER = (4.0, 38.0)     # lid weights: full on the plate, gone at the brow (degrees above the margin)
LID_LOWER = (6.0, 22.0)
BLINK_MEET = 0.30
BLINK_OVERSHOOT = 1.6
BLINK_LOWER_OVERSHOOT = 0.6
BLINK_CORNER = 0.15         # the overlap fades toward the corners as profile ** this
LOOK_DOWN = 25.0
LOOK_DOWN_FOLLOW = (0.65, 0.40)   # upper, lower lid share of the gaze
GAZE = (30.0, 25.0)          # yaw, pitch the eyes must reach without poking through

SHAPES = ("BlinkLeft", "BlinkRight", "LookDownLids")
EYE_TEX = 1024
LASH_TEX = (2048, 1024)      # brow strands left half, lashes right half
BROW_HAIRS = 720             # strands per brow
SKIN_TEX_NAME = f"{NAME}_skin_albedo"
EYE_BOX = ((-24.0, 34.0), (-17.0, 27.0))   # makeup region per eye (mm along the lid axis, up)
EYE_UV_SCALE = 4.0                          # its UV island, magnified from MPFB's ~2 px/mm
EYE_UV_FREE = ((0.17, 0.03), (0.62, 0.58))  # skin texture area free of visible skin (UV lo, hi)

# iris: a deep violet-grey, darker limbal ring, lighter silvery flecks around the pupil
EYE_STYLE = dict(
    pupil=0.30, pupil_color=srgb("#030203"), ruff=srgb("#110C14"),
    inner=srgb("#57506A"), mid=srgb("#3B3349"), outer=srgb("#26212F"), limbal=srgb("#0C0A10"),
    fleck=srgb("#7F7890"), crypt=srgb("#1A161F"), collarette=0.50, crypts=40,
    sclera=srgb("#BFB2A6"), sclera_corner=srgb("#9C857E"), vein=srgb("#8A3532"), veins=34,
    rough_cornea=0.04, rough_sclera=0.12, lid_shade=0.22, lid_ao=0.35,
)
LASH_COLOR = srgb("#0B090D")
BROW_COLOR = srgb("#2A2024")
LASH_ROUGHNESS = 0.65
BROW_LIFT = 0.0003           # brow cards laid onto the skin this far out (hairs lie flat; no floating shadow)

# makeup (linear colors)
SMOKE = srgb("#140E17")
SMOKE_VIOLET = srgb("#2B1D3E")     # the palette's #5B3F86, deepened for the lid
CONCEAL = 0.55               # MPFB's red eye corners evened out toward the forehead's tone
LINER = srgb("#0A080C")
WATERLINE = srgb("#2B1D23")
CARUNCLE = srgb("#C48683")
BROW_BASE = srgb("#2C2226")
BROW_PAINT = 0.72            # the brow painted onto the skin under its cards (hair texture, blurred)


# --- fitting (build.py, before remove_helpers) -------------------------------------------------
def fit(body, arm, collection):
    """Fit lashes and brows, store the eye centers on the armature."""
    for side, joint in JOINTS.items():
        arm[f"eye_center_{side.lower()}"] = tuple(human.joint_center(body, joint))
    lashes = human.fit_proxy(body, "eyelashes", LASHES, "LashesSource", collection)
    brows = human.fit_proxy(body, "eyebrows", BROWS, "BrowsSource", collection)
    tag(lashes, "lashes_src")
    tag(brows, "brows_src")
    for ob in (lashes, brows):
        ob.hide_render = True
        ob.hide_set(True)
    print(f"EYES centers {[tuple(round(c, 4) for c in arm[f'eye_center_{s.lower()}']) for s in SIDES]} "
          f"lashes {len(lashes.data.vertices)} v, brows {len(brows.data.vertices)} v")
    return lashes, brows


def centers(arm):
    return {side: Vector(arm[f"eye_center_{side.lower()}"]) for side in SIDES}


def source(part):
    return next(o for o in bpy.data.objects if o.get("arcology_part") == part)


# --- frames and openings ------------------------------------------------------------------------
def skin_bvh(head, faces=None):
    co = face.vertex_positions(head)
    polys = [list(p.vertices) for p in head.data.polygons if faces is None or p.index in faces]
    return BVHTree.FromPolygons([Vector(p) for p in co], polys)


def frames(head, arm, faces=None):
    """{side: (EyeFrame, Opening)} on the head skin (rest positions; `faces`: the skin's
    polygons in a joined mesh). The lid axis comes from the measured corners (stored on the
    armature by `build`; measured when missing)."""
    bvh = skin_bvh(head, None if faces is None else set(faces))
    out = {}
    for side, sx in SIDES.items():
        c = centers(arm)[side]
        key = f"eye_axis_{side.lower()}"
        stored = key in arm.keys()
        fr = face.EyeFrame(c, Vector(arm[key]) if stored else Vector((sx, 0.0, 0.0)))
        op = face.measure_opening(bvh, fr)
        if not stored:
            pin, pout = (fr.point(np.array([s]), op.mid(np.array([s])), np.array([0.018]))[0] for s in op.corners)
            fr = face.EyeFrame(c, pout - pin)
            op = face.measure_opening(bvh, fr)
        out[side] = (fr, op)
    return out


def lid_weights(fr, op, co):
    return face.lid_weights(fr, op, co, upper=LID_UPPER, lower=LID_LOWER)


def mine(co, side):
    return (np.asarray(co)[:, 0] * SIDES[side]) > 0.0


# --- build (outfit.py) ------------------------------------------------------------------------------
def build(head, arm, collection):
    """Lids, eyeballs, lashes, brows, eye bones, weights and shapes. Returns (eyes, lashes, brows)."""
    lashes = _copy(source("lashes_src"), "Lashes", collection)
    brows = _copy(source("brows_src"), "Brows", collection)
    fr0 = frames(head, arm)
    for side, (fr, _) in fr0.items():
        arm[f"eye_axis_{side.lower()}"] = tuple(fr.A)
    shorten_lashes(lashes, fr0)
    lay_on_skin(brows, head, BROW_LIFT)

    # rest lids: the upper lid up a little, nothing of the lids' outside inside the eyeball
    co = face.vertex_positions(head)
    lco = face.vertex_positions(lashes)
    for side, (fr, op) in fr0.items():
        s, _, _ = fr.coords(co)
        w_up, w_low = lid_weights(fr, op, co)
        co = fr.turn(co, (UPPER_REST_DEG * w_up + LOWER_REST_DEG * w_low) * op.profile(s) * mine(co, side))
        lco = fr.turn(lco, lash_turns(fr, op, lco, side, lambda x, op=op: UPPER_REST_DEG * op.profile(x),
                                      lambda x, op=op: LOWER_REST_DEG * op.profile(x)))
    _set(head, co)
    _set(lashes, lco)
    pushed = {}
    for side, c in centers(arm).items():
        fr = fr0[side][0]

        def mask(p, c=np.array(c), F=fr.F):
            d = p - c
            return np.linalg.norm(d) < 0.026 and d.dot(F) > -0.004

        pushed[side] = face.push_clear(head, c, EYE_RADIUS + LID_CLEAR, mask)
    fr1 = frames(head, arm)
    for side, (fr, op) in fr1.items():
        cov = coverage(fr, op)
        print(f"EYES {side}: corners s {op.corners[0] * 1000:.1f}/{op.corners[1] * 1000:.1f} mm, margins at the "
              f"middle up {op.up(np.array([0.0]))[0]:.1f} low {op.low(np.array([0.0]))[0]:.1f} deg, upper lid "
              f"covers the iris top by {cov[0] * 1000:.2f} mm, lower lid the bottom by {cov[1] * 1000:.2f} mm; "
              f"lids pushed out up to {pushed[side] * 1000:.2f} mm")

    eyes = build_eyeballs(arm, collection)
    add_bones(arm)
    garment.set_weights(eyes, [{BONES["Left" if v.co.x > 0.0 else "Right"]: 1.0} for v in eyes.data.vertices])
    for ob in (lashes, brows):
        garment.set_weights(ob, [{"Head": 1.0} for _ in ob.data.vertices])
    remap_atlas(lashes, 0.5)
    remap_atlas(brows, 0.0)
    add_shapes(head, lashes, fr1)
    for ob, name in ((eyes, EYE_MAT), (lashes, LASH_MAT), (brows, LASH_MAT)):
        ob.data.materials.clear()
        ob.data.materials.append(_placeholder(name))
        for p in ob.data.polygons:
            p.use_smooth = True
    return eyes, lashes, brows


def coverage(fr, op):
    """How far (m, seen from the front) the upper lid covers the iris top and the lower lid
    the iris bottom at the middle of the opening (negative: sclera shows)."""
    z = np.array([0.0])
    up = fr.point(z, op.up(z), op.rho_up(z))[0]
    low = fr.point(z, op.low(z), op.rho_low(z))[0]
    return IRIS_RADIUS - (up - fr.c).dot(fr.U), IRIS_RADIUS + (low - fr.c).dot(fr.U)


def shorten_lashes(lashes, frs):
    """Scale each lash vertex toward the nearest point of its lid's margin (LASH_LENGTH)."""
    co = face.vertex_positions(lashes)
    for side, (fr, op) in frs.items():
        m = mine(co, side)
        up = face.margin_side(op, fr, co) > 0
        for is_up, k in ((True, LASH_LENGTH[0]), (False, LASH_LENGTH[1])):
            sel = m & (up == is_up)
            if not sel.any():
                continue
            margin = op.margin_points(fr, "up" if is_up else "low", 200)
            d = np.linalg.norm(co[sel][:, None, :] - margin[None, :, :], axis=2)
            root = margin[d.argmin(axis=1)]
            co[sel] = root + (co[sel] - root) * k
    _set(lashes, co)


def lay_on_skin(ob, skin, lift):
    """Move every vertex onto the nearest skin point, `lift` out along its normal."""
    bvh = skin_bvh(skin)
    co = face.vertex_positions(ob)
    for i, p in enumerate(co):
        loc, nrm, _, _ = bvh.find_nearest(Vector(p), 0.02)
        if loc is not None:
            co[i] = np.array(loc + nrm.normalized() * lift)
    _set(ob, co)


def _copy(src, name, collection):
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = ob.data.name = name
    collection.objects.link(ob)
    for k in list(ob.keys()):
        del ob[k]
    ob.hide_render = False
    ob.hide_set(False)
    return ob


def _set(ob, co):
    ob.data.vertices.foreach_set("co", np.asarray(co, dtype=np.float32).ravel())
    ob.data.update()


def build_eyeballs(arm, collection):
    import bmesh

    bm = bmesh.new()
    for side, sx in SIDES.items():
        face.eyeball(bm, centers(arm)[side], (0.0, -1.0, 0.0), (sx, 0.0, 0.0), EYE_RADIUS, IRIS_RADIUS, 0.0,
                     segments=EYE_SEGMENTS, back_deg=EYE_BACK)
    me = bpy.data.meshes.new("Eyes")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Eyes", me)
    collection.objects.link(ob)
    return ob


def add_bones(arm):
    """LeftEye / RightEye under Head: head at the rotation center, +Y straight forward, +Z down
    (so +X points to her left on both: Godot axes X +x, Y +z, Z -y)."""
    for side, c in centers(arm).items():
        if arm.data.bones.get(BONES[side]) is None:
            rig.add_bone_chain(arm, "Head", [BONES[side]], [c, c + Vector((0.0, -EYE_BONE_LENGTH, 0.0))],
                               normals=[(0.0, 0.0, -1.0)])


def remap_atlas(ob, u0):
    uv = ob.data.uv_layers.active.data
    a = np.empty(len(uv) * 2, dtype=np.float32)
    uv.foreach_get("uv", a)
    a = a.reshape(-1, 2)
    a[:, 0] = u0 + np.clip(a[:, 0], 0.0, 1.0) * 0.5
    uv.foreach_set("uv", a.ravel())


def lash_turns(fr, op, co, side, upper_fn, lower_fn):
    """Per lash vertex: its lid's turn at its margin point (upper or lower), 0 on the other eye."""
    s, _, _ = fr.coords(co)
    up = face.margin_side(op, fr, co) > 0
    return np.where(mine(co, side), np.where(up, upper_fn(s), lower_fn(s)), 0.0)


def add_shapes(head, lashes, fr):
    """BlinkLeft / BlinkRight / LookDownLids on the head skin and the lashes."""
    co = face.vertex_positions(head)
    lco = face.vertex_positions(lashes)
    look_h, look_l = co.copy(), lco.copy()
    for side, (f, op) in fr.items():
        s, _, _ = f.coords(co)
        w_up, w_low = lid_weights(f, op, co)
        m = (co[:, 0] * SIDES[side]) > -0.004
        w_up, w_low = w_up * m, w_low * m

        def blink(x, op=op):
            return face.blink_turns(op, x, BLINK_MEET, BLINK_OVERSHOOT, BLINK_LOWER_OVERSHOOT, BLINK_CORNER)

        du, dl = blink(s)
        face.set_shape_key(head, f"Blink{side}", f.turn(co, du * w_up + dl * w_low))
        face.set_shape_key(lashes, f"Blink{side}", f.turn(lco, lash_turns(f, op, lco, side, lambda x: blink(x)[0],
                                                                          lambda x: blink(x)[1])))
        fu, fl = LOOK_DOWN_FOLLOW
        look_h = f.turn(look_h, -LOOK_DOWN * op.profile(s) * (fu * w_up + fl * w_low))
        look_l = f.turn(look_l, lash_turns(f, op, look_l, side, lambda x, op=op: -LOOK_DOWN * fu * op.profile(x),
                                           lambda x, op=op: -LOOK_DOWN * fl * op.profile(x)))
    face.set_shape_key(head, "LookDownLids", look_h)
    face.set_shape_key(lashes, "LookDownLids", look_l)


def _placeholder(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    return m


# --- textures (bake.py) ---------------------------------------------------------------------------
def bake_textures(head, arm, skin_mat):
    """The eye and lash/brow materials and the makeup in the skin texture."""
    from arcology_blender import bake

    layout = face.EyeUV(math.degrees(math.asin(IRIS_RADIUS / EYE_RADIUS)), EYE_BACK)
    albedo, normal, orm = face.eye_textures(EYE_TEX, layout, EYE_RADIUS, IRIS_RADIUS, EYE_STYLE, CORNEA, seed=11)
    a_img = face.image_from(f"{NAME}_eye_albedo", face.linear_to_srgb(albedo))
    n_img = face.image_from(f"{NAME}_eye_normal", normal, "Non-Color")
    o_img = face.image_from(f"{NAME}_eye_orm", orm, "Non-Color")
    bake.final_material(EYE_MAT, a_img, n_img, o_img)
    brow_alpha, brow_shade = brow_strands(bpy.data.objects["Brows"], (LASH_TEX[1], LASH_TEX[0] // 2))
    lash_material(brow_alpha, brow_shade)
    paint_makeup(head, arm, skin_mat, brow_alpha=brow_alpha)


def brow_flow(t, n):
    """Brow hair direction (degrees from her outward direction toward up) at `t` along the
    brow (0 at the head by the nose, 1 at the tail) and `n` across it (-1 lower edge, +1
    upper): up at the head, the lower and upper hairs converging on the middle line along
    the body, down at the tail."""
    head = 78.0 - 10.0 * n
    body = 16.0 - 24.0 * n
    tail = -12.0 - 10.0 * n
    a = head + (body - head) * smoothstep(t, 0.06, 0.24)
    return a + (tail - a) * smoothstep(t, 0.62, 0.95)


def brow_strands(brows, shape, count=BROW_HAIRS, seed=5):
    """The brow cards' texture as separate hair strands (alpha, shade) for the atlas' brow half
    (`shape` (H, W) px over the brow cards' own UV square): starts spread over MPFB's brow
    coverage, each strand traced along `brow_flow` in the brow's own frame (mm on the skin)
    and mapped into the card's UVs by an affine fit per brow."""
    rng = np.random.default_rng(seed)
    h, w = shape
    img = bpy.data.images.load(source("brows_src")["texture"], check_existing=False)
    img.scale(w, h)
    cover = face.image_array(img)[..., 3].astype(np.float64)
    bpy.data.images.remove(img)
    me = brows.data
    uv = me.uv_layers.active.data
    vuv = np.zeros((len(me.vertices), 2))
    for lp in me.loops:
        vuv[lp.vertex_index] = uv[lp.index].uv
    vuv[:, 0] = np.clip(vuv[:, 0] * 2.0, 0.0, 1.0)        # atlas' left half -> the card's own square
    co = face.vertex_positions(brows) * 1000.0
    strands = []
    for comp in face.mesh_bmesh_islands(brows):
        idx = np.array(comp)
        side = np.sign(co[idx, 0].mean())
        x, z = co[idx, 0] * side, co[idx, 2]
        A = np.c_[x, z, np.ones(len(idx))]
        fit, *_ = np.linalg.lstsq(A, vuv[idx], rcond=None)          # (x, z, 1) -> (u, v)
        M, t0 = fit[:2].T, fit[2]
        Minv = np.linalg.inv(M)
        zc = np.polyfit(x, z, 2)
        x0, x1 = x.min(), x.max()
        half = max(np.percentile(np.abs(z - np.polyval(zc, x)), 90), 1.0)
        lo, hi = vuv[idx].min(axis=0), vuv[idx].max(axis=0)
        made, tries = 0, 0
        while made < count and tries < count * 60:
            tries += 1
            u = rng.uniform(lo, hi)
            px = (int(u[0] * w) % w, int(u[1] * h) % h)
            if rng.random() > cover[px[1], px[0]] ** 0.8:
                continue
            p = Minv @ (u - t0)                                     # mm: (outward, up)
            t = (p[0] - x0) / (x1 - x0)
            length = (3.2 + 3.0 * smoothstep(t, 0.05, 0.35) - 1.2 * smoothstep(t, 0.75, 1.0)) * rng.uniform(0.75, 1.2)
            pts, d = [p.copy()], None
            jitter = rng.normal(0.0, 7.0)
            for _ in range(int(length / 0.25)):
                tt = (p[0] - x0) / (x1 - x0)
                nn = np.clip((p[1] - np.polyval(zc, p[0])) / half, -1.0, 1.0)
                a = math.radians(brow_flow(tt, nn) + jitter)
                nd = np.array([math.cos(a), math.sin(a)])
                d = nd if d is None else 0.7 * d + 0.3 * nd
                d /= np.linalg.norm(d)
                p = p + d * 0.25
                pts.append(p.copy())
            q = np.array([M @ pp + t0 for pp in pts]) * np.array([w, h])
            strands.append((q, rng.uniform(1.2, 1.8), 0.4, rng.uniform(0.75, 1.3)))
            made += 1
    alpha, shade = face.draw_strands((h, w), strands)
    return alpha, np.where(alpha > 0.0, shade, 1.0)


def lash_material(brow_alpha, brow_shade):
    """Atlas of the brow strands (left half) and the recolored MPFB lash cards (right half);
    alpha scissor (glTF MASK: alpha rounded at 0.5), two-sided."""
    w, h = LASH_TEX
    out = np.zeros((h, w, 4))
    out[:, :w // 2, :3] = np.asarray(BROW_COLOR)[None, None, :] * brow_shade[..., None]
    out[:, :w // 2, 3] = brow_alpha
    img = bpy.data.images.load(source("lashes_src")["texture"], check_existing=False)
    img.scale(w // 2, h)
    a = face.image_array(img).astype(np.float64)
    bpy.data.images.remove(img)
    al = a[..., 3]
    lum = a[..., :3].mean(axis=-1)
    ref = lum[al > 0.3].mean() if (al > 0.3).any() else 0.0
    shade = np.clip(0.8 + 4.0 * (lum - ref) + 0.25 * al, 0.6, 1.5)
    out[:, w // 2:, :3] = np.asarray(LASH_COLOR)[None, None, :] * shade[..., None]
    out[:, w // 2:, 3] = smoothstep(al, 0.10, 0.70)
    out[..., :3] = face.linear_to_srgb(out[..., :3])
    img = face.image_from(f"{NAME}_lashes_albedo", out)
    m = bpy.data.materials.get(LASH_MAT) or bpy.data.materials.new(LASH_MAT)
    m.use_nodes = True
    m.use_backface_culling = False
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    r = nt.nodes.new("ShaderNodeMath")
    r.operation = "ROUND"
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(t.outputs["Alpha"], r.inputs[0])
    nt.links.new(r.outputs[0], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = LASH_ROUGHNESS
    nt.links.new(b.outputs[0], o.inputs["Surface"])
    return m


def eye_region_faces(head, f):
    """Faces of one eye's makeup region: the chart box EYE_BOX around it (mm)."""
    co = face.vertex_positions(head)
    d = (co - f.c) * 1000.0
    x, y, z = d @ f.A, d @ f.U, d @ f.F
    (x0, x1), (y0, y1) = EYE_BOX
    inside = (x > x0) & (x < x1) & (y > y0) & (y < y1) & (z > -25.0)
    return [p.index for p in head.data.polygons if all(inside[i] for i in p.vertices)]


def magnify_eye_regions(head, frs, base):
    """Each eye's region gets its own UV island EYE_UV_SCALE times larger (MPFB's layout gives
    the face ~2 px/mm; the body skin the clothes hide left most of the texture unused), placed
    in EYE_UV_FREE; MPFB's skin is resampled into it. Returns the new base texture (linear in,
    linear out: sRGB values as stored). Done once (`head["eye_uv"]`); again it returns `base`."""
    if head.get("eye_uv"):
        return base
    head["eye_uv"] = True
    me = head.data
    old = me.uv_layers.new(name="UVSource")
    src = me.uv_layers["UVMap"]
    a = np.empty(len(me.loops) * 2, dtype=np.float32)
    src.data.foreach_get("uv", a)
    old.data.foreach_set("uv", a)
    me.uv_layers.active = src
    h, w = base.shape[:2]
    moved = []
    (u0, v0), (u1, v1) = EYE_UV_FREE
    cursor_v = v0
    for side in SIDES:
        faces = face.uv_islands(head, eye_region_faces(head, frs[side][0]))[0]   # the face skin, not the pocket
        q = np.array([src.data[li].uv for fi in faces for li in me.polygons[fi].loop_indices])
        size = (q.max(axis=0) - q.min(axis=0)) * EYE_UV_SCALE
        center = (u0 + 0.5 * size[0], cursor_v + 0.5 * size[1])
        lo, hi = face.magnify_uv(head, faces, EYE_UV_SCALE, center)
        if hi[0] > u1 or hi[1] > v1:
            raise RuntimeError(f"eye UV island {side} {lo}..{hi} doesn't fit {EYE_UV_FREE}")
        cursor_v = hi[1] + 0.01
        moved += faces
        print(f"EYES {side} makeup island: {len(faces)} faces, UV {np.round(lo, 3)}..{np.round(hi, 3)} "
              f"({size[0] * w:.0f} x {size[1] * h:.0f} px)")
    rest = [p.index for p in me.polygons if p.index not in set(moved)]
    clash = face.uv_occupancy(head, moved) & face.uv_occupancy(head, rest)
    if clash.any():
        raise RuntimeError(f"eye UV islands overlap other head faces ({clash.sum()} cells)")
    pos, _, mask, olduv = face.uv_positions(head, w, moved, other_uv="UVSource")
    out = base.copy()
    out[mask] = face.sample_bilinear(base, olduv[mask])
    grown, gmask = face.dilate(out * mask[..., None], mask, 4)
    out[gmask & ~mask] = grown[gmask & ~mask]
    me.uv_layers.remove(me.uv_layers["UVSource"])
    me.uv_layers.active = me.uv_layers["UVMap"]
    return out


def brow_coverage(brows, pts, brow_alpha, reach=0.0025, blur=6):
    """Per point: the brow cards' hair texture (alpha, blurred `blur` px) where the nearest
    card point lies, fading out `reach` m away from the cards: the brow painted onto the
    skin under its cards (the cards alone read as hard strokes under alpha scissor)."""
    me = brows.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    co = face.vertex_positions(brows)
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    tri_uv = [np.array([uv[li].uv for li in t.loops]) for t in me.loop_triangles]
    bt = BVHTree.FromPolygons([Vector(p) for p in co], tris, all_triangles=True)
    a = brow_alpha.astype(np.float64)
    for _ in range(blur):                       # box blur, separable
        a = (np.roll(a, 1, 0) + a + np.roll(a, -1, 0)) / 3.0
        a = (np.roll(a, 1, 1) + a + np.roll(a, -1, 1)) / 3.0
    a = a[..., None]
    out = np.zeros(len(pts))
    from mathutils.geometry import barycentric_transform

    for i, p in enumerate(pts):
        loc, _, ti, dist = bt.find_nearest(Vector(p), reach)
        if loc is None:
            continue
        t = tris[ti]
        q = tri_uv[ti]
        b = barycentric_transform(loc, Vector(co[t[0]]), Vector(co[t[1]]), Vector(co[t[2]]),
                                  Vector((q[0][0], q[0][1], 0.0)), Vector((q[1][0], q[1][1], 0.0)),
                                  Vector((q[2][0], q[2][1], 0.0)))
        u = np.array([[min(b.x * 2.0, 1.0), b.y]])        # the atlas' left half -> the source texture
        out[i] = float(face.sample_bilinear(a, u)[0, 0]) * (1.0 - float(smoothstep(dist, 0.4 * reach, reach)))
    return np.clip(out * 1.6, 0.0, 1.0)


def conceal_skin(base, mask, pts, frs):
    """Concealer: pull the skin around the eyes (sRGB values, in place) toward the
    forehead's tone, more where it's redder than that (MPFB's skin is pink at the corners)."""
    texels = base[mask]
    tone = np.zeros(3)
    weight = np.zeros(len(pts))
    for side, (f, op) in frs.items():
        d = (pts - f.c) * 1000.0
        x, y = d @ f.A, d @ f.U
        forehead = (y > 24.0) & (y < 34.0) & (np.abs(x) < 10.0) & mine(pts, side)
        if forehead.any():
            tone += texels[forehead].mean(axis=0) * 0.5
        r = np.hypot(x / 26.0, (y + 2.0) / 18.0)
        weight = np.maximum(weight, (1.0 - smoothstep(r, 0.55, 1.0)) * mine(pts, side))
    red = np.clip((texels[:, 0] - texels[:, 1:].mean(axis=1)) - (tone[0] - tone[1:].mean()), 0.0, 1.0)
    k = (CONCEAL * weight * np.clip(0.4 + red * 6.0, 0.0, 1.0))[:, None]
    base[mask] = texels * (1.0 - k) + tone[None, :] * k


def paint_makeup(head, arm, skin_mat, debug=False, brow_alpha=None):
    """Composite the eye makeup over the skin texture (a new packed image in the skin
    material, same size), from 3D masks around each eye's measured lids. `debug`: the
    makeup's coverage black on white instead (where it lands).

    Per eye a chart in mm: x along the lid axis from the eye's center (outward positive), y
    up (frontal projection); the margins y_up(x), y_low(x) are the measured lids, continued
    past the outer corner as rising lines (the wing's lower and upper edge)."""
    nt = skin_mat.node_tree
    tex = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image is not None)
    src = tex.image
    w, h = src.size
    base = face.image_array(src)[..., :3].astype(np.float64)
    frs = frames(head, arm)
    base = magnify_eye_regions(head, frs, base)
    region = [p.index for p in head.data.polygons
              if min((Vector(p.center) - c).length for c in centers(arm).values()) < 0.055]
    pos, _, mask, _ = face.uv_positions(head, w, region)
    pts = pos[mask]
    color = np.zeros((len(pts), 3))
    alpha = np.zeros(len(pts))

    def over(c, a):
        nonlocal color, alpha
        a = np.clip(a, 0.0, 1.0)
        out_a = a + alpha * (1.0 - a)
        mixed = (np.asarray(c)[None, :] * a[:, None] + color * (alpha * (1.0 - a))[:, None]) \
            / np.maximum(out_a, 1e-6)[:, None]
        color = np.where(out_a[:, None] > 1e-6, mixed, color)
        alpha = out_a

    R = EYE_RADIUS * 1000.0
    conceal_skin(base, mask, pts, frs)
    for side, (f, op) in frs.items():
        m = mine(pts, side)
        d = (pts - f.c) * 1000.0
        x, y = d @ f.A, d @ f.U
        r = np.linalg.norm(d, axis=1)
        s_in, s_out = (c * 1000.0 for c in op.corners)
        xs = np.linspace(s_in, s_out, 80)
        yu = op.margin_points(f, "up", 80) - f.c
        yl = op.margin_points(f, "low", 80) - f.c
        yu, yl = yu @ f.U * 1000.0, yl @ f.U * 1000.0
        y_corner = 0.5 * (yu[-1] + yl[-1])
        past = np.maximum(x - s_out, 0.0)                    # mm past the outer corner
        y_up = np.interp(x, xs, yu) + 0.34 * past            # the upper margin, then the wing's line
        y_low = np.where(x > s_out, y_corner + 0.62 * past, np.interp(x, xs, yl))
        u = np.clip((x - s_in) / (s_out - s_in), 0.0, 1.0)  # 0 inner corner .. 1 outer corner
        d_up = y - y_up                                      # mm above the upper margin (or wing line)
        d_low = y_low - y                                    # mm below the lower margin
        in_x = smoothstep(x, s_in - 2.0, s_in + 2.5) * (1.0 - smoothstep(past, 5.0, 15.0))
        # smoky lid: dense over the lid, softly gone above the crease; higher toward the temple
        top = (6.5 + 4.0 * u ** 1.3) * (1.0 - 0.55 * smoothstep(past, 0.0, 12.0))
        lid = (1.0 - smoothstep(d_up, 0.40 * top, top)) * smoothstep(d_up, -1.6, -0.2 + 0.0 * x)
        wing_low = smoothstep(y - y_low, -0.8, 1.6) * (x > s_out - 3.0) + (x <= s_out - 3.0)
        lid = lid * np.where(x > s_out - 3.0, wing_low, 1.0) * in_x * m
        lid = np.where(x <= s_out, lid * (d_up > -1.6), lid)
        violet = smoothstep(d_up, 0.45 * top, 0.7 * top) * (1.0 - smoothstep(d_up, 0.75 * top, 1.1 * top)) \
            * smoothstep(u, 0.3, 0.8) * in_x * m + 0.7 * smoothstep(past, 1.0, 7.0) * lid
        over(SMOKE_VIOLET, 0.65 * np.clip(violet, 0.0, 1.0))
        over(SMOKE, 0.97 * lid * (1.0 - 0.5 * np.clip(violet, 0.0, 1.0)))
        # liner along the upper lashes, thicker outward, a short flick along the wing line
        lw = (0.55 + 0.85 * u) * (1.0 - smoothstep(past, 0.0, 4.5))
        liner = np.exp(-(np.maximum(d_up, 0.0) / np.maximum(lw, 0.05)) ** 2) * (d_up > -0.4) \
            * smoothstep(x, s_in - 0.5, s_in + 1.5) * (past < 4.5) * m
        over(LINER, 0.98 * liner)
        # lower lash line: a soft smudge, stronger toward the outer corner, into the wing
        lowl = np.exp(-(np.maximum(d_low, 0.0) / (1.4 + 2.2 * u)) ** 2) * (d_low > -0.6) * (0.55 + 0.45 * u) \
            * smoothstep(x, s_in + 0.5, s_in + 4.0) * (1.0 - smoothstep(past, 2.0, 9.0)) * m
        over(SMOKE, 0.92 * lowl)
        # the lid margins and the waterline (toward the eyeball, inside the lash lines): kohl
        water = (1.0 - smoothstep(r, R + 1.0, R + 2.0)) * (r > R - 5.0) * smoothstep(x, s_in + 1.0, s_in + 3.0) * m
        over(WATERLINE, 0.92 * water)
        # caruncle: the pink at the inner corner
        car = np.exp(-((x - s_in + 0.6) / 1.8) ** 2 - ((y - y_corner * 0.0 - np.interp(s_in, xs, yu)) / 2.0) ** 2) \
            * (r < R + 3.5) * m
        over(CARUNCLE, 0.55 * car)
    brows = next((o for o in bpy.data.objects if o.name == "Brows"), None)
    if brows is not None and brow_alpha is not None:
        over(BROW_BASE, BROW_PAINT * brow_coverage(brows, pts, brow_alpha))
    layer = np.zeros((h, w, 4))
    layer[mask, :3] = color
    layer[mask, 3] = alpha
    layer, _ = face.dilate(layer, mask, 4)
    lin = face.srgb_to_linear(base)
    a = layer[..., 3:4]
    if debug:
        lin, layer[..., :3] = np.ones_like(lin), 0.0
    out = lin * (1.0 - a) + layer[..., :3] * a
    img = face.image_from(SKIN_TEX_NAME, face.linear_to_srgb(out))
    tex.image = img
    return img
