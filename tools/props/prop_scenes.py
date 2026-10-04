"""Builds Godot prop scenes (.tscn text) from small declarative inputs.

Stdlib only. A prop's numbers live in a definition file next to this module
(tools/props/<prop>.py); run it to write the scene, or with --check to compare
the generated text with the committed .tscn:

    python tools/props/fridge.py            # write assets/props/fridge/fridge.tscn
    python tools/props/fridge.py --check    # exit code = number of scenes that differ
    python tools/props/prop_scenes.py --check   # check every definition in tools/props/

After writing, scan the filesystem in the editor and reopen the scene with
force_reload (CLAUDE.md, "Hand-written scenes and the editor").

A definition builds a Scene and adds components to it in node order:

    s = Scene("Cabinet", doc="Wall cabinet 0.6 x 0.35 x 0.7 m. Origin = bottom center, front +Z. ...")
    s.instance("Body", "assets/props/cabinet/cabinet_body.glb")
    s.hinged_door(glb="assets/props/cabinet/cabinet_door.glb", hinge_position=(-0.3, 0, 0.175),
                  hinge_rotation=HINGE_LEFT, open_max=110.0, grip=(0.55, 0.35, 0.03),
                  boxes=[("SlabCollision", (0.3, 0.35, 0.01), (0.6, 0.7, 0.02))])
    return {"assets/props/cabinet/cabinet.tscn": s}

Other building blocks: area_button() (a bare fingertip button, e.g. for a panel),
mesh() with box_mesh() / quad_mesh() (placeholder geometry, glass quads), HINGE_BOTTOM
(a sash or flap tilting about its bottom edge), TextResource (a generated .tres next
to the scenes), glb_node_position() / glb_bounds() (read empties and sizes from an
exported glb, so a scene can follow the artist's file once it exists). See
tools/props/window.py for all of them. area_button() / light_switch() also take a box
press field (box=, shape_position=: flush plates, touch sensors); pickable_scene() takes
cylinder colliders and a HolderSnap (holder=: a roll on its bar, a hand shower in its
cradle); cylinders() adds CylinderShape3Ds anywhere. glb_images() / glb_import_text() /
write_new_file() let a definition share one material between several glbs (see
tools/props/shower.py --imports).

Conventions it keeps (CLAUDE.md): position/rotation_degrees, never raw
transforms; metadata/_doc on the root; the physics layers (pickables on 3,
handles on 19, buttons detect Player Hands on 18); moving bodies are
KinematicFollowers (D-018); hinged and sliding parts get a GrabPassThrough
(D-021) and a HingeSwing / SliderSwing (D-027, D-030); switches are fingertip
area buttons (D-031).

Coordinates: all positions are in the parent's frame, Godot axes (Y up, the
prop's front faces +Z). Door boxes and grips are in the door's own frame
(origin on the hinge axis, as the glb is exported); drawer boxes and grips in
the drawer's frame (origin at the slider origin).

Value formatting (matches what the scratch generators wrote): tuples of 3 are
Vector3 with components printed like "%g"; Python floats print as 92.0, ints as
95; str values are quoted Godot strings; use raw() for anything else.
Node references are scene paths from the root ("HingeOrigin/InteractableHinge");
ref() turns them into NodePaths relative to the node that holds them.

Ordering: ext_resources are written in first-use order unless the Scene is
given `exts` (ordered, with ids) up front. Box shapes are written when added;
sphere shapes (grab points, switches) are deferred to the end of the
sub_resource list unless flush_subs() writes them earlier. Nodes are written
in the order added; `before=` inserts in front of an existing node.
"""

from __future__ import annotations

import difflib
import importlib
import json
import math
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[2]

Vec3 = tuple[float, float, float]
# (node name, center, size) or (node name, center, size, sub_resource id)
BoxSpec = tuple

# HingeOrigin rotations for a vertical hinge; the leaf opens toward +Z.
HINGE_LEFT = (0, 0, -90)   # hinge on the leaf's -X edge (leaf extends toward +X)
HINGE_RIGHT = (0, 0, 90)   # hinge on the leaf's +X edge (leaf extends toward -X)
# HingeOrigin rotation for a horizontal hinge along X at the leaf's bottom edge
# (a tilt window sash, a flap): the leaf extends up +Y and its top tilts toward +Z.
HINGE_BOTTOM = (0, 0, 0)
# SliderOrigin rotation for a drawer that pulls out toward +Z.
SLIDE_FRONT = (0, -90, 0)

LAYER_HANDLES = 262144        # 19 Grab Handles
LAYER_PICKABLE = 4            # 3 Pickable Objects
MASK_PICKABLE = 196615        # 1, 2, 3, 17, 18
MASK_PLAYER_HANDS = 131072    # 18 Player Hands (fingertips press area buttons)

# Known resources: key -> (type, path, uid). The uid is given where the
# committed scenes reference it; None writes the path only (Godot resolves it).
CATALOG: dict[str, tuple[str, str, str | None]] = {
    "pickable": ("Script", "res://addons/godot-xr-tools/objects/pickable.gd", "uid://bfrlpbsqg5lqr"),
    "hinge": ("Script", "res://addons/godot-xr-tools/interactables/interactable_hinge.gd", "uid://c8gx2wc7hsxf5"),
    "slider": ("Script", "res://addons/godot-xr-tools/interactables/interactable_slider.gd", "uid://cloxfr8r3b00u"),
    "handle": ("Script", "res://addons/godot-xr-tools/interactables/interactable_handle.gd", "uid://dlojnwxo25bky"),
    "area_button": ("Script", "res://addons/godot-xr-tools/interactables/interactable_area_button.gd", "uid://dq042kibpfryy"),
    "follower": ("Script", "res://core/interaction/kinematic_follower.gd", "uid://ccxwohhkuuyo1"),
    "stop_sound": ("Script", "res://core/interaction/hinge_stop_sound.gd", "uid://0qo7w8nlh6eu"),
    "blocker": ("Script", "res://core/interaction/hinge_body_blocker.gd", "uid://c8otihf11a0u7"),
    "pass_through": ("Script", "res://core/interaction/grab_pass_through.gd", "uid://dwnb8l1buro5f"),
    "hinge_light": ("Script", "res://core/interaction/hinge_light.gd", "uid://cyr1ortn2o3uc"),
    "hinge_swing": ("Script", "res://core/interaction/hinge_swing.gd", None),
    "slider_swing": ("Script", "res://core/interaction/slider_swing.gd", None),
    "open_alarm": ("Script", "res://core/interaction/open_alarm.gd", None),
    "light_switch": ("Script", "res://core/interaction/light_switch.gd", None),
    "hanging_rail": ("Script", "res://core/interaction/hanging_rail.gd", None),
    "rail_hanger": ("Script", "res://core/interaction/rail_hanger.gd", None),
    "impact_sound": ("Script", "res://core/interaction/impact_sound.gd", None),
    "grab_highlight": ("Script", "res://core/interaction/grab_highlight.gd", None),
    "motorized_shade": ("Script", "res://core/interaction/motorized_shade.gd", None),
    "smart_glass": ("Script", "res://core/interaction/smart_glass.gd", None),
    "window_hud": ("Script", "res://core/interaction/window_hud.gd", None),
    "window_light": ("Script", "res://core/interaction/window_light.gd", None),
    "hinge_ambience": ("Script", "res://core/interaction/hinge_ambience.gd", None),
    "named_material_override": ("Script", "res://core/interaction/named_material_override.gd", None),
    "hinge_coupling": ("Script", "res://core/interaction/hinge_coupling.gd", None),
    "hinge_detents": ("Script", "res://core/interaction/hinge_detents.gd", None),
    "press_sound": ("Script", "res://core/interaction/press_sound.gd", None),
    "holder_snap": ("Script", "res://core/interaction/holder_snap.gd", None),
}
# assets/audio/sfx/<name>.wav referenced as "sfx/<name>"; uid where committed scenes use one.
SFX_UIDS: dict[str, str | None] = {
    "fridge_close": "uid://cxy7ek1m5pq5u",
    "fridge_seal": "uid://dittphyloa30b",
    "fridge_hum": "uid://0io2m5bthts6",
    "fridge_alarm": "uid://cbikfpoe3jxnw",
    "door_bump": "uid://dgrgkkkb7rd03",
}


# ---------------------------------------------------------------- values

class Raw(str):
    """A property value written as is (ExtResource(...), Color(...), enums)."""


class Ref(str):
    """A node reference: a scene path from the root, written as a NodePath
    relative to the node holding it and listed in its node_paths."""


class NodePathValue(str):
    """A NodePath property that is not an exported Node (not in node_paths),
    e.g. XRToolsInteractableAreaButton.button. Also a scene path from the root."""


def raw(text: str) -> Raw:
    return Raw(text)


def ref(scene_path: str) -> Ref:
    return Ref(scene_path)


def node_path(scene_path: str) -> NodePathValue:
    return NodePathValue(scene_path)


def color(r: float, g: float, b: float, a: float = 1.0) -> Raw:
    return Raw("Color(%s)" % ", ".join(_g(c) for c in (r, g, b, a)))


def _g(c: float) -> str:
    return f"{c:g}"


def v3(t: Sequence[float]) -> str:
    return "Vector3(%s)" % ", ".join(_g(c) for c in t)


def v2(x: float, y: float) -> Raw:
    return Raw(f"Vector2({_g(x)}, {_g(y)})")


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _rel(from_path: str, to_path: str) -> str:
    """NodePath from the node at `from_path` to the node at `to_path` (both from the root)."""
    a = [] if from_path == "." else from_path.split("/")
    b = [] if to_path == "." else to_path.split("/")
    common = 0
    while common < min(len(a), len(b)) and a[common] == b[common]:
        common += 1
    parts = [".."] * (len(a) - common) + b[common:]
    return "/".join(parts) if parts else "."


def _fmt(value: object, owner: str) -> str:
    if isinstance(value, Ref) or isinstance(value, NodePathValue):
        return f'NodePath("{_rel(owner, value)}")'
    if isinstance(value, Raw):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, tuple) and len(value) == 3:
        return v3(value)
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(v, owner) for v in value) + "]"
    raise TypeError(f"can't format {value!r} (use raw())")


def _is_ref(value: object) -> bool:
    if isinstance(value, Ref):
        return True
    return isinstance(value, list) and any(isinstance(v, Ref) for v in value)


# ---------------------------------------------------------------- rotation

def rotate(rotation_degrees: Sequence[float], p: Sequence[float]) -> Vec3:
    """Rotates point p by Godot Euler angles (degrees, YXZ order, as rotation_degrees)."""
    x, y, z = (math.radians(a) for a in rotation_degrees)
    px, py, pz = p
    # Z, then X, then Y (Basis.from_euler with EULER_ORDER_YXZ = Ry * Rx * Rz)
    px, py = px * math.cos(z) - py * math.sin(z), px * math.sin(z) + py * math.cos(z)
    py, pz = py * math.cos(x) - pz * math.sin(x), py * math.sin(x) + pz * math.cos(x)
    px, pz = px * math.cos(y) + pz * math.sin(y), -px * math.sin(y) + pz * math.cos(y)
    return tuple(round(c, 9) + 0.0 for c in (px, py, pz))  # type: ignore[return-value]


def _inverse_single_axis(rotation_degrees: Sequence[float]) -> Vec3:
    if sum(1 for a in rotation_degrees if a) > 1:
        raise ValueError(f"rotation {tuple(rotation_degrees)} turns about more than one axis: pass leaf_rotation")
    return tuple(-a for a in rotation_degrees)  # type: ignore[return-value]


# ---------------------------------------------------------------- specs

@dataclass
class Sound:
    """An AudioStreamPlayer3D. `stream` is "sfx/<name>" or a resource path;
    `props` are player properties written after `stream`, in order
    (volume_db, unit_size, autoplay, max_distance, max_polyphony, ...)."""
    stream: str
    position: Vec3 | None = None
    name: str = ""
    props: dict = field(default_factory=dict)


@dataclass
class OmniLight:
    """An unshadowed OmniLight3D (small lights never cast shadows, CLAUDE.md)."""
    position: Vec3
    energy: float
    range: float
    color: tuple = (1, 1, 1, 1)
    attenuation: float | None = None
    visible: bool = True
    name: str = "Light"


@dataclass
class HingeLightSpec:
    """HingeLight: `light` on (and the emissive material under `emissive_root`) while open."""
    light: OmniLight
    emissive_root: str            # scene path, e.g. "Body"
    material_name: str | None = None
    emission_energy: float | None = None
    name: str = "Light"


@dataclass
class AlarmSpec:
    """OpenAlarm: `sound` loops after `delay` seconds open, until closed."""
    sound: Sound
    delay: float | None = None
    open_angle: float | None = None
    name: str = "OpenAlarm"


@dataclass
class Joint:
    """Paths of a hinged door or drawer, returned by the components."""
    group: str            # "." or the group node
    joint: str            # InteractableHinge / InteractableSlider
    leaf: str
    body: str


@dataclass
class _Node:
    name: str
    parent: str | None
    type: str | None
    instance: str | None
    props: list[tuple[str, str]]
    node_paths: list[str]
    groups: list[str]

    @property
    def path(self) -> str:
        if self.parent is None:
            return "."
        return self.name if self.parent == "." else f"{self.parent}/{self.name}"

    def text(self) -> str:
        head = f'[node name="{self.name}"'
        if self.type:
            head += f' type="{self.type}"'
        if self.parent is not None:
            head += f' parent="{self.parent}"'
        if self.node_paths:
            head += " node_paths=PackedStringArray(%s)" % ", ".join(f'"{p}"' for p in self.node_paths)
        if self.groups:
            head += " groups=[%s]" % ", ".join(f'"{g}"' for g in self.groups)
        if self.instance:
            head += f' instance=ExtResource("{self.instance}")'
        return "\n".join([head + "]"] + [f"{k} = {v}" for k, v in self.props])


def open_box(width: float, height: float, depth: float, wall: float, *, floor: float | None = None,
             center: Vec3 = (0, 0, 0), names: Sequence[str] = ("Floor", "WallLeft", "WallRight", "WallFront", "WallBack"),
             ) -> list[BoxSpec]:
    """Box colliders for an open-top container (drawer, bin, storage box):
    floor plate, full-depth side walls, front/back walls between them. Origin
    = bottom center (+ `center`); walls stand on y = 0 and are `height` tall."""
    t, f = wall, wall if floor is None else floor
    cx, cy, cz = center
    side_x, end_z = width / 2 - t / 2, depth / 2 - t / 2
    return [
        (names[0], (cx, cy + f / 2, cz), (width, f, depth)),
        (names[1], (cx - side_x, cy + height / 2, cz), (t, height, depth)),
        (names[2], (cx + side_x, cy + height / 2, cz), (t, height, depth)),
        (names[3], (cx, cy + height / 2, cz + end_z), (width - 2 * t, height, t)),
        (names[4], (cx, cy + height / 2, cz - end_z), (width - 2 * t, height, t)),
    ]


# ---------------------------------------------------------------- scene

class Scene:
    """One .tscn: ext_resources, sub_resources and nodes, written in the Godot text format.

    root, root_type: the root node. doc: its metadata/_doc (written after root_props).
    exts: optional [(ref, id), ...] declared up front, in this order (legacy scenes).
    ext_ids: optional {ref: id} for resources registered later, in first-use order.
    A ref is a CATALOG key ("hinge"), "sfx/<name>", or a path ("assets/props/x/x.glb" or res://...).
    """

    def __init__(self, root: str, doc: str | None = None, *, root_type: str = "Node3D",
                 root_props: dict | None = None, groups: Sequence[str] = (),
                 exts: Iterable[tuple[str, str]] = (), ext_ids: dict[str, str] | None = None) -> None:
        self._exts: list[tuple[str, str, str | None, str]] = []   # type, path, uid, id
        self._ext_by_path: dict[str, str] = {}
        self._ext_ids = dict(ext_ids or {})
        self._subs: list[tuple[str, str, list[tuple[str, str]]]] = []   # type, id, props
        self._deferred: list[tuple[str, str, list[tuple[str, str]]]] = []
        self._nodes: list[_Node] = []
        for key, ext_id in exts:
            self.ext(key, ext_id)
        props = dict(root_props or {})
        if doc is not None:
            props["metadata/_doc"] = doc
        self.node(root, root_type, parent=None, props=props, groups=groups)

    # -- resources

    @staticmethod
    def resolve(key: str) -> tuple[str, str, str | None, str]:
        """ref -> (type, res:// path, uid or None, default id)."""
        if key in CATALOG:
            typ, path, uid = CATALOG[key]
            return typ, path, uid, key
        if key.startswith("sfx/"):
            name = key[4:]
            return "AudioStream", f"res://assets/audio/sfx/{name}.wav", SFX_UIDS.get(name), name
        path = key if key.startswith("res://") else "res://" + key.lstrip("/")
        suffix = Path(path).suffix
        typ = {".glb": "PackedScene", ".gltf": "PackedScene", ".tscn": "PackedScene", ".scn": "PackedScene",
               ".gd": "Script", ".wav": "AudioStream", ".ogg": "AudioStream", ".tres": "Resource",
               ".gdshader": "Shader", ".png": "Texture2D"}.get(suffix)
        if suffix == ".tres" and "/materials/" in path:
            typ = "Material"
        if typ is None:
            raise ValueError(f"unknown resource type for {key}")
        return typ, path, None, Path(path).stem

    def ext(self, key: str, ext_id: str | None = None) -> Raw:
        """Registers an ext_resource (once per path) and returns ExtResource("<id>")."""
        typ, path, uid, default_id = self.resolve(key)
        if path not in self._ext_by_path:
            ext_id = ext_id or self._ext_ids.get(key) or default_id
            used = {e[3] for e in self._exts}
            base, n = ext_id, 2
            while ext_id in used:
                ext_id, n = f"{base}_{n}", n + 1
            self._exts.append((typ, path, uid, ext_id))
            self._ext_by_path[path] = ext_id
        return Raw(f'ExtResource("{self._ext_by_path[path]}")')

    def ext_id(self, key: str) -> str:
        return self.ext(key)[len('ExtResource("'):-2]

    def sub(self, typ: str, sub_id: str, props: dict, *, deferred: bool = False) -> Raw:
        """Adds a sub_resource (once per id; the same id must have the same props)."""
        lines = [(k, _fmt(v, ".")) for k, v in props.items()]
        for entry in self._subs + self._deferred:
            if entry[1] == sub_id:
                if entry[0] != typ or entry[2] != lines:
                    raise ValueError(f"sub_resource {sub_id} redefined with different values")
                return Raw(f'SubResource("{sub_id}")')
        (self._deferred if deferred else self._subs).append((typ, sub_id, lines))
        return Raw(f'SubResource("{sub_id}")')

    def sphere(self, sub_id: str, radius: float) -> Raw:
        """A deferred SphereShape3D (grab points, switches)."""
        return self.sub("SphereShape3D", sub_id, {"radius": radius}, deferred=True)

    def cylinders(self, parent: str, cylinders: Sequence[tuple], prefix: str = "") -> None:
        """CollisionShape3D + CylinderShape3D (along local Y) per (name, center, radius, height[, sub id])."""
        for i, cyl in enumerate(cylinders):
            name, center, radius, height = cyl[:4]
            sub_id = cyl[4] if len(cyl) > 4 else f"CylinderShape3D_{prefix}{i}"
            shape = self.sub("CylinderShape3D", sub_id, {"height": height, "radius": radius})
            props: dict = {}
            if any(center):
                props["position"] = tuple(center)
            props["shape"] = shape
            self.node(name, "CollisionShape3D", parent=parent, props=props)

    def flush_subs(self) -> None:
        """Writes the deferred sphere shapes at this point of the sub_resource list."""
        self._subs += self._deferred
        self._deferred = []

    # -- nodes

    def set_root_props(self, props: dict) -> None:
        """Replaces the root node's properties (include metadata/_doc last)."""
        root = self._nodes[0]
        root.props = [(k, _fmt(v, ".")) for k, v in props.items()]
        root.node_paths = [k for k, v in props.items() if _is_ref(v)]

    def node(self, name: str, type: str | None = None, *, parent: str | None = ".", props: dict | None = None,
             instance: str | None = None, groups: Sequence[str] = (), before: str | None = None, **kw: object) -> str:
        """Adds a node; props (then kw) are written in order. Returns its scene path."""
        values = dict(props or {})
        values.update(kw)
        n = _Node(name, parent, type, instance, [], [], list(groups))
        n.props = [(k, _fmt(v, n.path)) for k, v in values.items()]
        n.node_paths = [k for k, v in values.items() if _is_ref(v)]
        if any(m.path == n.path for m in self._nodes):
            raise ValueError(f"duplicate node {n.path}")
        if before is None:
            self._nodes.append(n)
        else:
            i = next(i for i, m in enumerate(self._nodes) if m.path == before)
            self._nodes.insert(i, n)
        return n.path

    def instance(self, name: str, scene: str, *, parent: str = ".", position: Vec3 | None = None,
                 rotation: Vec3 | None = None, before: str | None = None) -> str:
        """A child instance of a glb or tscn (optionally placed)."""
        props: dict = {}
        if position is not None:
            props["position"] = tuple(position)
        if rotation is not None:
            props["rotation_degrees"] = tuple(rotation)
        return self.node(name, parent=parent, props=props, instance=self.ext_id(scene), before=before)

    def boxes(self, parent: str, boxes: Sequence[BoxSpec], prefix: str = "") -> None:
        """CollisionShape3D + BoxShape3D per (name, center, size[, sub id]); ids BoxShape3D_<prefix><i>."""
        for i, box in enumerate(boxes):
            name, center, size = box[:3]
            sub_id = box[3] if len(box) > 3 else f"BoxShape3D_{prefix}{i}"
            shape = self.sub("BoxShape3D", sub_id, {"size": tuple(size)})
            props: dict = {}
            if any(center):
                props["position"] = tuple(center)
            props["shape"] = shape
            self.node(name, "CollisionShape3D", parent=parent, props=props)

    def sound(self, name: str, stream: str, *, parent: str = ".", position: Vec3 | None = None,
              before: str | None = None, groups: Sequence[str] = (), **props: object) -> str:
        """An AudioStreamPlayer3D; props after `stream` in order (volume_db, autoplay, max_distance, ...)."""
        values: dict = {}
        if position is not None:
            values["position"] = tuple(position)
        values["stream"] = self.ext(stream)
        values.update(props)
        return self.node(name, "AudioStreamPlayer3D", parent=parent, props=values, before=before, groups=groups)

    def _sound(self, spec: Sound, parent: str, default_name: str) -> str:
        return self.sound(spec.name or default_name, spec.stream, parent=parent, position=spec.position, **spec.props)

    def omni_light(self, light: OmniLight, *, parent: str = ".", before: str | None = None) -> str:
        props: dict = {"position": tuple(light.position)}
        if not light.visible:
            props["visible"] = False
        props["light_color"] = color(*light.color)
        props["light_energy"] = light.energy
        props["omni_range"] = light.range
        if light.attenuation is not None:
            props["omni_attenuation"] = light.attenuation
        return self.node(light.name, "OmniLight3D", parent=parent, props=props, before=before)

    def _handles(self, leaf: str, grips: dict[str, Vec3], grab_radius: float, grab_shape: str) -> None:
        shape = self.sphere(grab_shape, grab_radius)
        for suffix, grip in grips.items():
            origin = self.node(f"HandleOrigin{suffix}", "Node3D", parent=leaf, position=tuple(grip))
            handle = self.node("InteractableHandle", "RigidBody3D", parent=origin, props={
                "collision_layer": LAYER_HANDLES, "collision_mask": 0, "freeze": True,
                "script": self.ext("handle"), "picked_up_layer": 0})
            self.node("CollisionShape3D", "CollisionShape3D", parent=handle, shape=shape)

    @staticmethod
    def _grips(grip: Vec3 | None, grips: dict[str, Vec3] | None) -> dict[str, Vec3]:
        if (grip is None) == (grips is None):
            raise ValueError("pass grip (one handle) or grips ({suffix: position})")
        return {"": grip} if grip is not None else dict(grips or {})

    def hinged_door(self, *, glb: str | None, hinge_position: Vec3, hinge_rotation: Vec3, open_max: float,
                    boxes: Sequence[BoxSpec], grip: Vec3 | None = None, grips: dict[str, Vec3] | None = None,
                    group: str | None = None, model_name: str = "Model", shape_prefix: str | None = None,
                    leaf_rotation: Vec3 | None = None, limit_min: float = 0.0,
                    grab_radius: float = 0.06, grab_shape: str = "SphereShape3D_grab",
                    stop: Sound | None = Sound("sfx/door_bump"), stop_props: dict | None = None,
                    swing: dict | None = None, no_swing: bool = False, open_sound: Sound | None = None,
                    light: HingeLightSpec | None = None, alarm: AlarmSpec | None = None) -> Joint:
        """A door, lid or flap on an XRToolsInteractableHinge (CLAUDE.md "Add a hinged interactable").

        Nodes: [group] / HingeOrigin (hinge_position, hinge_rotation: its local X is the
        hinge axis; HINGE_LEFT / HINGE_RIGHT for vertical doors, HINGE_BOTTOM for a
        sash or flap tilting about its bottom edge) / InteractableHinge
        (0..open_max degrees) / Leaf (inverse rotation, so the door frame is the glb's)
        / DoorBody (KinematicFollower, `boxes`, the glb as `model_name`), one
        HandleOrigin<suffix>/InteractableHandle per grip; then StopSound (HingeStopSound,
        `stop.position` in hinge space, default at the grip; stop_props = its exports),
        [open_sound], [light.light], Swing (HingeSwing, `swing` = its exports; no_swing
        drops it), [HingeLight], BodyBlocker, GrabPassThrough, [alarm sound, OpenAlarm].
        glb=None leaves out the model (add placeholder meshes under the returned body).
        Zero rotations aren't written.
        """
        grip_map = self._grips(grip, grips)
        base = "." if group is None else self.node(group, "Node3D")
        origin_props: dict = {"position": tuple(hinge_position)}
        if any(hinge_rotation):
            origin_props["rotation_degrees"] = tuple(hinge_rotation)
        origin = self.node("HingeOrigin", "Node3D", parent=base, props=origin_props)
        hinge = self.node("InteractableHinge", "Node3D", parent=origin, props={
            "script": self.ext("hinge"), "hinge_limit_min": limit_min, "hinge_limit_max": open_max})
        leaf_rot = tuple(leaf_rotation) if leaf_rotation is not None else _inverse_single_axis(hinge_rotation)
        leaf = self.node("Leaf", "Node3D", parent=hinge, props={"rotation_degrees": leaf_rot} if any(leaf_rot) else None)
        body = self.node("DoorBody", "AnimatableBody3D", parent=leaf, script=self.ext("follower"))
        self.boxes(body, boxes, shape_prefix if shape_prefix is not None else (group or "door"))
        if glb is not None:
            self.node(model_name, parent=body, instance=self.ext_id(glb))
        self._handles(leaf, grip_map, grab_radius, grab_shape)
        if stop is not None:
            position = stop.position if stop.position is not None else rotate(leaf_rot, next(iter(grip_map.values())))
            self.sound(stop.name or "StopSound", stop.stream, parent=hinge, position=position,
                       **stop.props, script=self.ext("stop_sound"), hinge=ref(hinge), **(stop_props or {}))
        open_path = self._sound(open_sound, base, "OpenSound") if open_sound else None
        light_path = self.omni_light(light.light, parent=base) if light else None
        if not no_swing:
            props: dict = {"script": self.ext("hinge_swing"), "hinge": ref(hinge)}
            if open_path:
                props["open_sound"] = ref(open_path)
            props.update(swing or {})
            self.node("Swing", "Node", parent=base, props=props)
        elif open_path:
            raise ValueError("open_sound needs the Swing")
        if light:
            props = {"script": self.ext("hinge_light"), "hinge": ref(hinge), "light": ref(light_path or ""),
                     "emissive_root": ref(light.emissive_root)}
            if light.material_name is not None:
                props["material_name"] = light.material_name
            if light.emission_energy is not None:
                props["emission_energy"] = light.emission_energy
            self.node(light.name, "Node", parent=base, props=props)
        self.node("BodyBlocker", "Node", parent=base, script=self.ext("blocker"), hinge=ref(hinge), leaf=ref(body))
        self.node("GrabPassThrough", "Node", parent=base, script=self.ext("pass_through"), body=ref(body),
                  handles_root=ref(leaf))
        if alarm:
            alarm_sound = self._sound(alarm.sound, base, "AlarmSound")
            props = {"script": self.ext("open_alarm"), "hinge": ref(hinge), "alarm": ref(alarm_sound)}
            if alarm.delay is not None:
                props["delay"] = alarm.delay
            if alarm.open_angle is not None:
                props["open_angle"] = alarm.open_angle
            self.node(alarm.name, "Node", parent=base, props=props)
        return Joint(base, hinge, leaf, body)

    def sliding_drawer(self, name: str, *, glb: str, origin: Vec3, travel: float, boxes: Sequence[BoxSpec],
                       grip: Vec3 | None = None, grips: dict[str, Vec3] | None = None,
                       rotation: Vec3 = SLIDE_FRONT, shape_prefix: str | None = None, model_name: str = "Model",
                       grab_radius: float = 0.06, grab_shape: str = "SphereShape3D_grab",
                       stop: Sound | None = Sound("sfx/drawer_bump"), swing: dict | None = None) -> Joint:
        """A drawer on an XRToolsInteractableSlider (D-030).

        Nodes: <name> / SliderOrigin (origin, rotation: its local X is the slide
        direction; SLIDE_FRONT pulls toward +Z) / InteractableSlider (0..travel m) /
        Leaf (inverse rotation) / DrawerBody (KinematicFollower, `boxes`, the glb),
        HandleOrigin/InteractableHandle; then StopSound (at `stop.position`, default
        the slider origin), Swing (SliderSwing; `swing` = its exports), GrabPassThrough.
        """
        grip_map = self._grips(grip, grips)
        group = self.node(name, "Node3D")
        origin_path = self.node("SliderOrigin", "Node3D", parent=group, position=tuple(origin),
                                rotation_degrees=tuple(rotation))
        slider = self.node("InteractableSlider", "Node3D", parent=origin_path, script=self.ext("slider"),
                           slider_limit_max=travel)
        leaf = self.node("Leaf", "Node3D", parent=slider, rotation_degrees=_inverse_single_axis(rotation))
        body = self.node("DrawerBody", "AnimatableBody3D", parent=leaf, script=self.ext("follower"))
        self.boxes(body, boxes, shape_prefix if shape_prefix is not None else name)
        self.node(model_name, parent=body, instance=self.ext_id(glb))
        self._handles(leaf, grip_map, grab_radius, grab_shape)
        props: dict = {"script": self.ext("slider_swing"), "slider": ref(slider)}
        if stop is not None:
            stop_path = self.sound(stop.name or "StopSound", stop.stream, parent=group,
                                   position=stop.position if stop.position is not None else tuple(origin), **stop.props)
            props["stop_sound"] = ref(stop_path)
        props.update(swing or {})
        self.node("Swing", "Node", parent=group, props=props)
        self.node("GrabPassThrough", "Node", parent=group, script=self.ext("pass_through"), body=ref(body),
                  handles_root=ref(leaf))
        return Joint(group, slider, leaf, body)

    def area_button(self, name: str, *, position: Vec3, radius: float = 0.025, displacement: Vec3 = (0, -0.003, 0),
                    shape_id: str | None = None, parent: str = ".", box: Vec3 | None = None,
                    shape_position: Vec3 | None = None) -> str:
        """A fingertip-pressed XRToolsInteractableAreaButton (D-031): Area3D detecting Player
        Hands with a sphere of `radius` (deferred shape `shape_id`), or a box of size `box`
        (a flat plate, a touch field), optionally offset by `shape_position`, and a Cap node
        that moves by `displacement` when pressed (put the button's visuals under <name>/Cap)."""
        if box is not None:
            shape = self.sub("BoxShape3D", shape_id or f"BoxShape3D_{name}", {"size": tuple(box)})
        else:
            shape = self.sphere(shape_id or f"SphereShape3D_{name}", radius)
        button = self.node(name, "Area3D", parent=parent, props={
            "position": tuple(position), "collision_layer": 0, "collision_mask": MASK_PLAYER_HANDS,
            "monitorable": False, "script": self.ext("area_button"),
            "button": node_path(f"{parent}/{name}/Cap".removeprefix("./")), "displacement": tuple(displacement)})
        shape_props: dict = {}
        if shape_position is not None and any(shape_position):
            shape_props["position"] = tuple(shape_position)
        shape_props["shape"] = shape
        self.node("CollisionShape3D", "CollisionShape3D", parent=button, props=shape_props)
        self.node("Cap", "Node3D", parent=button)
        return button

    def mesh(self, name: str, mesh: Raw, *, parent: str = ".", position: Vec3 | None = None,
             rotation: Vec3 | None = None, material: str | Raw | None = None, override: bool = False,
             shadow: bool = True, props: dict | None = None, groups: Sequence[str] = ()) -> str:
        """A MeshInstance3D with a mesh sub_resource (see box_mesh, quad_mesh). material: a
        resource ref ("assets/materials/x.tres") or a SubResource, written as
        surface_material_override/0, or as material_override with override=True.
        props: more properties, written before the mesh."""
        values: dict = {}
        if position is not None and any(position):
            values["position"] = tuple(position)
        if rotation is not None and any(rotation):
            values["rotation_degrees"] = tuple(rotation)
        if not shadow:
            values["cast_shadow"] = 0
        values.update(props or {})
        values["mesh"] = mesh
        if material is not None:
            mat = material if isinstance(material, Raw) else self.ext(material)
            values["material_override" if override else "surface_material_override/0"] = mat
        return self.node(name, "MeshInstance3D", parent=parent, props=values, groups=groups)

    def box_mesh(self, size: Vec3) -> Raw:
        """A BoxMesh sub_resource, shared by size."""
        return self._sized("BoxMesh", tuple(size), {"size": tuple(size)})

    def quad_mesh(self, width: float, height: float) -> Raw:
        """A QuadMesh sub_resource (XY plane, facing +Z), shared by size."""
        return self._sized("QuadMesh", (width, height), {"size": v2(width, height)})

    def _sized(self, typ: str, key: tuple, props: dict) -> Raw:
        ids = self.__dict__.setdefault("_sized_ids", {})
        if (typ, key) not in ids:
            ids[(typ, key)] = f"{typ}_{sum(1 for t, _ in ids if t == typ)}"
        return self.sub(typ, ids[(typ, key)], props)

    def light_switch(self, name: str, *, position: Vec3, lights: Sequence[str], emissive_root: str | None = None,
                     material_name: str | None = None, radius: float = 0.025, displacement: Vec3 = (0, -0.003, 0),
                     click: Sound | None = Sound("sfx/button_click", props={"volume_db": -8.0}),
                     shape_id: str | None = None, parent: str = ".", switch_props: dict | None = None,
                     box: Vec3 | None = None, shape_position: Vec3 | None = None) -> str:
        """A fingertip-pressed switch (D-031): <name>Button (XRToolsInteractableAreaButton
        detecting Player Hands, sphere of `radius`, a Cap that moves by `displacement`),
        a click sound (default name <name>Click, at the button) and <name> (LightSwitch
        toggling `lights` and `material_name` under `emissive_root`; switch_props = more exports).
        box / shape_position: a box press field instead of the sphere (see area_button)."""
        default_id = f"BoxShape3D_{name}" if box is not None else f"SphereShape3D_{name}"
        button = self.area_button(f"{name}Button", position=position, radius=radius, displacement=displacement,
                                  shape_id=shape_id or default_id, parent=parent, box=box,
                                  shape_position=shape_position)
        props: dict = {"script": self.ext("light_switch"), "button": ref(button), "lights": [ref(p) for p in lights]}
        if emissive_root is not None:
            props["emissive_root"] = ref(emissive_root)
        if material_name is not None:
            props["material_name"] = material_name
        if click is not None:
            click_path = self.sound(click.name or f"{name}Click", click.stream, parent=parent,
                                    position=click.position if click.position is not None else tuple(position),
                                    **click.props)
            props["click"] = ref(click_path)
        props.update(switch_props or {})
        return self.node(name, "Node", parent=parent, props=props)

    def hanging_rail(self, name: str, *, start: Vec3, end: Vec3, radius: float = 0.0125, parent: str = ".",
                     **props: object) -> str:
        """A HangingRail (D-031): hangers with a RailHanger hook onto start..end."""
        return self.node(name, "Node3D", parent=parent, props={
            "script": self.ext("hanging_rail"), "start": tuple(start), "end": tuple(end), "radius": radius, **props})

    # -- output

    def text(self) -> str:
        if self._deferred:
            self.flush_subs()
        blocks: list[str] = []
        if self._exts:
            lines = []
            for typ, path, uid, ext_id in self._exts:
                uid_part = f' uid="{uid}"' if uid else ""
                lines.append(f'[ext_resource type="{typ}"{uid_part} path="{path}" id="{ext_id}"]')
            blocks.append("\n".join(lines))
        for typ, sub_id, props in self._subs:
            blocks.append("\n".join([f'[sub_resource type="{typ}" id="{sub_id}"]'] + [f"{k} = {v}" for k, v in props]))
        blocks += [n.text() for n in self._nodes]
        return "[gd_scene format=3]\n\n" + "\n\n".join(blocks) + "\n"


# ---------------------------------------------------------------- whole scenes

def static_prop_scene(root: str, glb: str, doc: str, *, model_name: str = "Model", model_id: str | None = None) -> Scene:
    """A static glb prop (collision from the glb's -colonly/-convcolonly meshes): root + one instance."""
    s = Scene(root, doc, ext_ids={glb: model_id} if model_id else None)
    s.instance(model_name, glb)
    return s


def pickable_scene(root: str, glb: str, *, mass: float, boxes: Sequence[BoxSpec], doc: str,
                   sound: str = "sfx/pillow_thud", friction: float = 0.8, bounce: float = 0.05,
                   linear_damp: float = 0.2, angular_damp: float = 1.0, continuous_cd: bool = False,
                   release_unfrozen: bool = False, hook: Vec3 | None = None, groups: Sequence[str] = (),
                   material_id: str = "PhysicsMaterial_1", shape_prefix: str = "",
                   impact: dict | None = None, ext_ids: dict[str, str] | None = None,
                   cylinders: Sequence[tuple] = (), holder: str | None = None,
                   holder_props: dict | None = None) -> Scene:
    """An XRToolsPickable (CLAUDE.md "Add a pickable"): RigidBody3D on layer 3 with the
    pickable mask, freeze_mode kinematic, LERP ranged grab, second-hand grab, a
    PhysicsMaterial, box colliders (then `cylinders`: (name, center, radius, height)),
    the glb as Model, an ImpactSound, a GrabHighlight.
    hook: adds Hook (Marker3D) + RailHanger, which needs release_unfrozen (D-031).
    holder: adds a HolderSnap for that holder group (sits frozen in a holder until
    grabbed, snaps back when dropped near one; holder_props = its exports), which also
    needs release_unfrozen. groups: tags (CLAUDE.md Tags table). impact: ImpactSound props."""
    if (hook is not None or holder is not None) and not release_unfrozen:
        raise ValueError("a RailHanger / HolderSnap needs release_unfrozen=True (release_mode = UNFROZEN)")
    ids = {"pickable": "1_pickable", "impact_sound": "2_impact", sound: "3_sound", "grab_highlight": "4_highlight",
           glb: "5_model", "rail_hanger": "6_hanger"}
    ids.update(ext_ids or {})
    s = Scene(root, root_type="RigidBody3D", groups=groups, ext_ids=ids)
    for key in ("pickable", "impact_sound", sound, "grab_highlight", glb):
        s.ext(key)
    if hook is not None:
        s.ext("rail_hanger")
    material = s.sub("PhysicsMaterial", material_id, {"friction": friction, "bounce": bounce})
    props: dict = {"collision_layer": LAYER_PICKABLE, "collision_mask": MASK_PICKABLE, "mass": mass,
                   "physics_material_override": material}
    if continuous_cd:
        props["continuous_cd"] = True
    props.update({"linear_damp": linear_damp, "angular_damp": angular_damp, "freeze_mode": 1,
                  "script": s.ext("pickable")})
    if release_unfrozen:
        props["release_mode"] = 0
    props.update({"ranged_grab_method": 2, "second_hand_grab": 1, "metadata/_doc": doc})
    s.set_root_props(props)
    s.boxes(".", boxes, shape_prefix)
    s.cylinders(".", cylinders, shape_prefix)
    s.instance("Model", glb)
    impact_props = {"unit_size": 3.0, "max_polyphony": 2, "script": s.ext("impact_sound"), "min_speed": 0.6,
                    "max_speed": 5.0}
    impact_props.update(impact or {})
    s.sound("ImpactSound", sound, **impact_props)
    s.node("GrabHighlight", "Node", script=s.ext("grab_highlight"))
    if hook is not None:
        s.node("Hook", "Marker3D", props={"position": tuple(hook)} if any(hook) else None)
        s.node("RailHanger", "Node", script=s.ext("rail_hanger"), hook=ref("Hook"))
    if holder is not None:
        s.node("HolderSnap", "Node", props={"script": s.ext("holder_snap"), "holder_group": holder,
                                            **(holder_props or {})})
    return s


class TextResource:
    """Any other generated text file (e.g. a .tres) for run(): holds its full text."""

    def __init__(self, content: str) -> None:
        self._content = content

    def text(self) -> str:
        return self._content


# ---------------------------------------------------------------- glb

def glb_json(path: str) -> dict | None:
    """The glTF JSON of a repo-relative .glb, or None if the file doesn't exist (yet)."""
    file = ROOT / path
    if not file.exists():
        return None
    data = file.read_bytes()
    magic, _version, _length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise ValueError(f"{path} is not a glb")
    chunk_length, chunk_type = struct.unpack_from("<I4s", data, 12)
    if chunk_type != b"JSON":
        raise ValueError(f"{path}: first chunk isn't JSON")
    return json.loads(data[20:20 + chunk_length])


def _glb_walk(gltf: dict):
    """Yields (node, translation from the scene root) for every node; rotations and scales
    are taken as identity (true for exported empties and our props' parts)."""
    scene = gltf.get("scenes", [{}])[gltf.get("scene", 0)]
    stack = [(i, (0.0, 0.0, 0.0)) for i in scene.get("nodes", [])]
    nodes = gltf.get("nodes", [])
    while stack:
        index, offset = stack.pop()
        node = nodes[index]
        t = node.get("translation", (0, 0, 0))
        at = (offset[0] + t[0], offset[1] + t[1], offset[2] + t[2])
        yield node, at
        stack += [(c, at) for c in node.get("children", [])]


def glb_node_position(path: str, name: str) -> Vec3 | None:
    """Position of the node named `name` (e.g. the HandleGrip empty), or None."""
    gltf = glb_json(path)
    if gltf is None:
        return None
    for node, at in _glb_walk(gltf):
        if node.get("name") == name:
            return tuple(round(c, 5) + 0.0 for c in at)  # type: ignore[return-value]
    return None


def glb_bounds(path: str) -> tuple[Vec3, Vec3] | None:
    """Axis-aligned bounds (min, max) of every mesh in the glb, or None if it doesn't exist."""
    gltf = glb_json(path)
    if gltf is None:
        return None
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for node, at in _glb_walk(gltf):
        if "mesh" not in node:
            continue
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            acc = gltf["accessors"][prim["attributes"]["POSITION"]]
            for k in range(3):
                lo[k] = min(lo[k], acc["min"][k] + at[k])
                hi[k] = max(hi[k], acc["max"][k] + at[k])
    if lo[0] == math.inf:
        return None
    return (tuple(round(c, 5) + 0.0 for c in lo), tuple(round(c, 5) + 0.0 for c in hi))  # type: ignore[return-value]


def glb_images(path: str) -> dict[str, bytes]:
    """The embedded images of a repo-relative .glb: {image name: encoded bytes (png/jpeg)}."""
    data = (ROOT / path).read_bytes()
    gltf = glb_json(path) or {}
    json_length = struct.unpack_from("<I", data, 12)[0]
    bin_start = 20 + json_length + 8   # after the JSON chunk and the BIN chunk's header
    out: dict[str, bytes] = {}
    for i, image in enumerate(gltf.get("images", [])):
        view = gltf["bufferViews"][image["bufferView"]]
        start = bin_start + view.get("byteOffset", 0)
        out[image.get("name", f"image_{i}")] = data[start:start + view["byteLength"]]
    return out


GLB_IMPORT = """[remap]

importer="scene"
importer_version=1
type="PackedScene"

[deps]

source_file="res://{path}"

[params]

nodes/root_type=""
nodes/root_name=""
nodes/root_script=null
mesh_library/use_node_names_as_mesh_names=false
array_mesh/deduplicate_surfaces=true
nodes/apply_root_scale=true
nodes/root_scale=1.0
nodes/import_as_skeleton_bones=false
nodes/use_name_suffixes=true
nodes/use_node_type_suffixes=true
meshes/ensure_tangents=true
meshes/generate_lods=true
meshes/create_shadow_meshes=true
meshes/light_baking=1
meshes/lightmap_texel_size=0.2
meshes/force_disable_compression=false
skins/use_named_skins=true
animation/import=true
animation/fps=30
animation/trimming=false
animation/remove_immutable_tracks=true
animation/import_rest_as_RESET=false
import_script/path=""
materials/extract=0
materials/extract_format=0
materials/extract_path=""
_subresources={subresources}
gltf/naming_version=2
gltf/embedded_image_handling={images}
gltf/texture_map_mode=1
"""


# A texture's .import: VRAM-compressed with mipmaps; normal maps flagged (normal_map=1, roughness_mode=1).
TEXTURE_IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://{path}"

[params]

compress/mode=2
compress/high_quality=false
compress/lossy_quality=0.7
compress/uastc_level=0
compress/rdo_quality_loss=0.0
compress/hdr_compression=1
compress/normal_map={normal_map}
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode={roughness_mode}
roughness/src_normal=""
process/channel_remap/red=0
process/channel_remap/green=1
process/channel_remap/blue=2
process/channel_remap/alpha=3
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def glb_import_text(path: str, materials: dict[str, str], embedded_images: int = 1) -> str:
    """A scene .import for a glb whose materials {name: repo path of a .tres} are external,
    shared resources. embedded_images: 0 discards the glb's embedded textures (when every
    textured material is external), 1 extracts them next to the glb (Godot's default)."""
    if materials:
        entries = ",\n".join(
            f'"{name}": {{\n"use_external/enabled": true,\n"use_external/fallback_path": "res://{tres}",\n'
            f'"use_external/path": "res://{tres}"\n}}' for name, tres in materials.items())
        subresources = '{\n"materials": {\n' + entries + "\n}\n}"
    else:
        subresources = "{}"
    return GLB_IMPORT.format(path=path, subresources=subresources, images=embedded_images)


def write_new_file(rel: str, content: str | bytes) -> bool:
    """Writes a repo-relative file only if it doesn't exist yet (Godot owns .import files
    once it has imported them, adding uids). Returns whether it wrote."""
    path = ROOT / rel
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {rel}")
    return True


# ---------------------------------------------------------------- CLI

def run(scenes: dict[str, Scene | TextResource], check: bool) -> int:
    """Writes (or with check, compares) each {repo-relative path: Scene or TextResource}.
    Returns the number that differ."""
    bad = 0
    for rel, scene in scenes.items():
        path = ROOT / rel
        text = scene.text()
        old = path.read_bytes().decode("utf-8") if path.exists() else None
        if check:
            if old == text:
                print(f"OK    {rel}")
            else:
                bad += 1
                print(f"DIFF  {rel}")
                diff = difflib.unified_diff((old or "").splitlines(), text.splitlines(), "committed", "generated",
                                            lineterm="", n=1)
                for line in list(diff)[:60]:
                    print("      " + line)
        elif old == text:
            print(f"same  {rel}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {rel}")
    return bad


def main(scenes: Callable[[], dict[str, Scene]]) -> None:
    """Entry point for a definition file: `python tools/props/<prop>.py [--check]`."""
    sys.exit(run(scenes(), "--check" in sys.argv[1:]))


def _definitions() -> list[str]:
    here = Path(__file__).resolve().parent
    return sorted(p.stem for p in here.glob("*.py") if p.stem != "prop_scenes" and not p.stem.startswith("_"))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    check = "--check" in sys.argv[1:]
    total = 0
    for module_name in _definitions():
        total += run(importlib.import_module(module_name).scenes(), check)
    print(f"{total} scene(s) differ" if check else "done")
    sys.exit(total)
