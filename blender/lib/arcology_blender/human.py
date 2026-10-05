"""MPFB2 base humans (D-037): body mesh, rig and skin from the MakeHuman assets.

MPFB is a Blender extension (GPLv3; its core assets and generated humans are
CC0). Stage scripts run with --factory-startup, which loads no extensions, so
`mpfb()` enables it for the running process. The asset packs (system assets,
skins, eyebrows, eyelashes) must be installed through MPFB's "Install asset
pack" once per Blender version. Avoid CC-BY packs (Hair 02/03) or credit them.
Proxies (eyelashes, eyebrows, clothes) are fitted with `fit_proxy` and become plain
static meshes the build owns.
"""

import os

import addon_utils

MODULE = "bl_ext.blender_org.mpfb"

# Macro sliders MPFB accepts (0..1); race is a dict of african/asian/caucasian weights.
MACROS = ("gender", "age", "muscle", "weight", "proportions", "height", "cupsize", "firmness")


def mpfb():
    """Enable MPFB for this Blender process and return its services as a namespace
    (`.HumanService`, `.TargetService`, `.LocationService`)."""
    import importlib
    import sys

    if MODULE not in sys.modules:
        mod = addon_utils.enable(MODULE, default_set=True, persistent=False)  # MPFB reads its own preferences entry
        if mod is None:
            raise RuntimeError(f"{MODULE} is not installed: Preferences > Get Extensions > MPFB")
    services = importlib.import_module(MODULE + ".services")

    class Services:
        HumanService = importlib.import_module(services.__name__ + ".humanservice").HumanService
        TargetService = importlib.import_module(services.__name__ + ".targetservice").TargetService
        LocationService = importlib.import_module(services.__name__ + ".locationservice").LocationService

    return Services


def create_human(rig="game_engine", race=None, targets=None, **macros):
    """New MPFB human with feet on the ground at the origin, facing -Y, and a built-in rig.

    `macros` are MPFB's sliders (`MACROS`, 0..1; gender 0 = female, 1 = male), `race`
    a dict like {"caucasian": 1.0}. `rig` is a built-in rig name ("game_engine": 53
    bones, Unreal-style names; "default": 163 with face and twist bones), or None.
    `targets` maps MPFB detail targets (path under MPFB's data/targets without
    ".target.gz", e.g. "hands/l-hand-fingers-length-incr") to weights 0..1; they
    are loaded before the rig, so the rig fits the shaped body.
    Returns (body, armature); the body is parented to the armature with an Armature
    modifier and one vertex group per deforming bone.
    """
    svc = mpfb()
    info = svc.TargetService.get_default_macro_info_dict()
    for key, value in macros.items():
        if key not in MACROS:
            raise KeyError(f"unknown MPFB macro {key!r}; use one of {MACROS}")
        info[key] = value
    if race:
        info["race"] = {k: race.get(k, 0.0) for k in info["race"]}
    body = svc.HumanService.create_human(macro_detail_dict=info)
    for name, weight in (targets or {}).items():
        svc.TargetService.load_target(body, target_path(name), weight=weight)
    arm = svc.HumanService.add_builtin_rig(body, rig) if rig else None
    return body, arm


def skin_path(name):
    """Path of an installed skin's .mhmat by folder name (e.g. "young_caucasian_female")."""
    svc = mpfb()
    path = os.path.join(svc.LocationService.get_user_data("skins"), name, name + ".mhmat")
    if not os.path.exists(path):
        raise FileNotFoundError(f"MPFB skin {name!r} not installed ({path})")
    return path


def set_skin(body, name, skin_type="GAMEENGINE"):
    """Give the body an installed skin. "GAMEENGINE" is a plain Principled material with
    the skin's diffuse/normal images (glTF-safe); MPFB's SSS types don't export."""
    mpfb().HumanService.set_character_skin(skin_path(name), body, skin_type=skin_type)


def remove_helpers(body):
    """Delete MPFB's helper geometry (joint cubes, eye/hair/clothes fitting helpers) and
    the mask modifier hiding it, so triangle counts and edits see only the skin.
    Fit MPFB proxies (eyes, eyebrows, clothes) before this: they need the helpers."""
    import bmesh

    ids = {vg.index for vg in body.vertex_groups if vg.name in ("HelperGeometry", "JointCubes")}
    bm = bmesh.new()
    bm.from_mesh(body.data)
    deform = bm.verts.layers.deform.verify()
    doomed = [v for v in bm.verts if any(g in ids and w > 0.0 for g, w in v[deform].items())]
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    for mod in [m for m in body.modifiers if m.type == "MASK"]:
        body.modifiers.remove(mod)


def proxy_path(kind, name):
    """Path of an installed MPFB proxy asset (.mhclo) by kind ("eyelashes", "eyebrows",
    "eyes", "clothes", ...) and folder name (e.g. "eyelashes02")."""
    svc = mpfb()
    path = os.path.join(svc.LocationService.get_user_data(kind), name, name + ".mhclo")
    if not os.path.exists(path):
        raise FileNotFoundError(f"MPFB {kind} proxy {name!r} not installed ({path})")
    return path


def fit_proxy(body, kind, name, object_name, collection=None):
    """Fit an MPFB proxy (eyelashes, eyebrows, eyes, clothes) to the body's current shape
    and return it as a plain static mesh in world coordinates: no parent, modifiers or
    weights, MPFB's material removed (its texture's path is kept in `ob["texture"]`).
    Call before `remove_helpers` (proxies are fitted to the helper geometry)."""
    import bpy
    import numpy as np

    svc = mpfb()
    path = proxy_path(kind, name)
    ob = svc.HumanService.add_mhclo_asset(path, body, asset_type=kind, subdiv_levels=0,
                                          material_type="GAMEENGINE", set_up_rigging=False)
    bpy.context.view_layer.update()
    texture = ""
    mats = [m for m in ob.data.materials if m is not None]
    for m in mats:
        for n in m.node_tree.nodes if m.node_tree else []:
            if n.type == "TEX_IMAGE" and n.image is not None and not texture:
                texture = bpy.path.abspath(n.image.filepath)
    mw = np.array(ob.matrix_world)
    me = ob.data.copy()
    me.name = object_name
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    me.vertices.foreach_set("co", co.ravel())
    me.materials.clear()
    me.update()
    out = bpy.data.objects.new(object_name, me)
    (collection or bpy.context.scene.collection).objects.link(out)
    out["texture"] = texture
    old = ob.data
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(old)
    for m in mats:
        imgs = {n.image.name for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image} if m.node_tree else set()
        bpy.data.materials.remove(m)
        for name in imgs:
            img = bpy.data.images.get(name)
            if img is not None and img.users == 0:
                bpy.data.images.remove(img)
    return out


def joint_center(body, joint):
    """Center of one of MPFB's joint cubes (e.g. "joint-l-eye": the eyeball's rotation
    center), world coordinates of the shaped body. Call before `remove_helpers`."""
    import bpy
    import numpy as np
    from mathutils import Vector

    vg = body.vertex_groups.get(joint)
    if vg is None:
        raise KeyError(f"no MPFB joint {joint!r}")
    saved = [(m, m.show_viewport) for m in body.modifiers]
    for m, _ in saved:
        m.show_viewport = False
    bpy.context.view_layer.update()
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    idx = [v.index for v in body.data.vertices if any(g.group == vg.index and g.weight > 0.0 for g in v.groups)]
    co = np.array([tuple(ev.data.vertices[i].co) for i in idx])
    for m, show in saved:
        m.show_viewport = show
    return body.matrix_world @ Vector(co.mean(axis=0))


def target_path(name):
    """Full path of an MPFB detail target, e.g. "hands/l-hand-fingers-length-incr"."""
    path = os.path.join(mpfb().LocationService.get_mpfb_data("targets"), name + ".target.gz")
    if not os.path.exists(path):
        raise FileNotFoundError(f"MPFB target {name!r} not found ({path})")
    return path


def measure(body, arm, side="Left"):
    """Rest-shape measurements in meters (call before `remove_helpers`: the eye
    position comes from MPFB's eye helper). Returns a dict: `height` (top of the
    skin above the feet' lowest point), `eye` (midpoint of the eye helpers),
    `hand_length` (wrist joint to the farthest middle-finger skin, the usual
    "wrist crease to fingertip" measure) and `hand_width` (across the index and
    little knuckles' skin)."""
    import bpy
    import numpy as np
    from mathutils import Vector

    saved = [(m, m.show_viewport) for m in body.modifiers]
    for m, _ in saved:
        m.show_viewport = False
    bpy.context.view_layer.update()
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(ev.data.vertices) * 3, dtype=np.float32)
    ev.data.vertices.foreach_get("co", co)
    for m, show in saved:
        m.show_viewport = show
    mw = np.array(body.matrix_world)
    co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]

    def group(name, minimum=0.5):
        vg = body.vertex_groups.get(name)
        if vg is None:
            return np.zeros(len(co), dtype=bool)
        mask = np.zeros(len(co), dtype=bool)
        for v in body.data.vertices:
            for g in v.groups:
                if g.group == vg.index and g.weight >= minimum:
                    mask[v.index] = True
        return mask

    helper = group("HelperGeometry", 1e-6) | group("JointCubes", 1e-6)
    skin = co[~helper] if helper.any() else co
    eyes = group("helper-l-eye", 1e-6) | group("helper-r-eye", 1e-6)
    bones = arm.data.bones
    hand = bones.get(f"{side}Hand") or bones.get("hand_" + side[0].lower())
    mid3 = f"{side}MiddleDistal" if bones.get(f"{side}MiddleDistal") else "middle_03_" + side[0].lower()
    wrist = np.array(arm.matrix_world @ hand.head_local)
    tip = co[group(mid3) & ~helper]
    out = {
        "height": float(skin[:, 2].max() - skin[:, 2].min()),
        "eye": Vector(co[eyes].mean(axis=0)) if eyes.any() else None,
        "hand_length": float(np.linalg.norm(tip - wrist, axis=1).max()) if len(tip) else 0.0,
    }
    i1 = "index_01_" + side[0].lower() if bones.get("index_01_" + side[0].lower()) else f"{side}IndexProximal"
    l1 = "pinky_01_" + side[0].lower() if bones.get("pinky_01_" + side[0].lower()) else f"{side}LittleProximal"
    a, b = np.array(arm.matrix_world @ bones[i1].head_local), np.array(arm.matrix_world @ bones[l1].head_local)
    across = (a - b) / np.linalg.norm(a - b)
    palm = co[group(hand.name, 0.3) & ~helper]
    proj = (palm - wrist) @ across
    out["hand_width"] = float(proj.max() - proj.min()) if len(palm) else 0.0
    return out
