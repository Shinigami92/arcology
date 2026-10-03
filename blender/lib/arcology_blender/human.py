"""MPFB2 base humans (D-037): body mesh, rig and skin from the MakeHuman assets.

MPFB is a Blender extension (GPLv3; its core assets and generated humans are
CC0). Stage scripts run with --factory-startup, which loads no extensions, so
`mpfb()` enables it for the running process. The asset packs (system assets,
skins, eyebrows, eyelashes) must be installed through MPFB's "Install asset
pack" once per Blender version. Avoid CC-BY packs (Hair 02/03) or credit them.
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


def create_human(rig="game_engine", race=None, **macros):
    """New MPFB human with feet on the ground at the origin, facing -Y, and a built-in rig.

    `macros` are MPFB's sliders (`MACROS`, 0..1; gender 0 = female, 1 = male), `race`
    a dict like {"caucasian": 1.0}. `rig` is a built-in rig name ("game_engine": 53
    bones, Unreal-style names; "default": 163 with face and twist bones), or None.
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
