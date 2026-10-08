"""Shared writer for generated zone blockouts (D-015, D-048, D-059).

A zone generator (tools/blockout/<zone>.py) builds a Zone from its layout and calls write():

    z = Zone("Corridor", "zones/corridor/corridor.tscn", height=2.8, doc="...")
    z.box("Shell", "Floor", center, size, "concrete")
    z.wall("Shell", "East", "z", 8.9, (-3.2, 7.0), [z.door_gap(0.05, 0.95)])
    z.window("corridor_end", "EndWindow", (7.725, 0, -3.1), yaw=0)
    z.instance("Door4418", "door_neighbor", (8.9, 0, 0.5), (0, 90, 0))
    z.light("Hall0", "Omni", (7.7, 2.6, 0.0), color=(0.8, 0.9, 1), energy=0.6, range=3.5)
    z.probe("SideProbe", (7.7, 1.4, 2.0), (2.2, 2.8, 10.0))
    z.entry("ApartmentDoor", (7.6, 0, 2.9), 90)
    z.perf_marker((7.7, 1.7, 6.0), (0, 0, 0))
    z.write()

What it writes, like tools/blockout/apartment.py (which still has its own writer):
- one StaticBody3D per group, a MeshInstance3D + box CollisionShape3D per box (world-mapped
  surface materials, D-035), so boxes of any size tile;
- Occluders: a BoxOccluder3D per wall, floor and ceiling box, inset on its thin axis, and a
  VisibleOnScreenNotifier3D per window onto the city (group outside_view, D-048);
- Bounds: an Area3D (Player Body) over every floor box, floor to ceiling: where the player is in
  this zone, for ZoneStreamer (D-059);
- Windows, Props (instances), Signs (Label3D), Lighting (lights, probes, InteriorDaylight),
  Entries and PerfPath markers.

Coordinates are world coordinates (D-008): 1 unit = 1 m, Y up, x east, z south, the city facade
faces -Z. Wall boxes are T thick, centered on their line.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "props"))
import window as window_specs  # noqa: E402  (tools/props/window.py)

T = 0.2  # wall thickness
DOOR_H = 2.1

MATS = {
    "vinyl": "vinyl_plank", "carpet": "carpet", "concrete": "polished_concrete",
    "wall": "wall_plaster", "ceiling": "ceiling_plaster",
    "gunmetal": "gunmetal", "steel": "brushed_steel", "dark": "furniture_dark",
    "magenta": "neon_magenta", "cyan": "neon_cyan", "lamp": "ceiling_lamp",
    "wood": "wood_dark", "ceramic": "ceramic",
}
UNSHADOWED = {"magenta", "cyan", "lamp"}
OCCLUDER_MATS = {"wall", "ceiling", "vinyl", "carpet", "concrete"}
FLOOR_MATS = {"vinyl", "carpet", "concrete"}
OCCLUDER_INSET = 0.02
WINDOW_VIEW_MARGIN = 0.3
WINDOW_VIEW_DEPTH = 1.0
SCENES = {
    "door_entrance": "res://assets/props/door_entrance/door_entrance.tscn",
    "door_neighbor": "res://assets/props/door_entrance/door_neighbor.tscn",
}
WINDOW_LIGHT_SCRIPT = "res://core/interaction/window_light.gd"
INTERIOR_DAYLIGHT_SCRIPT = "res://core/world_state/interior_daylight.gd"
PLAYER_BODY_MASK = 524288  # physics layer 20
NODE_HEADER = re.compile(r'^\[node name="([^"]+)"(?: type="[^"]+")?(?: parent="([^"]+)")?')


def v3(t) -> str:
    return "Vector3(%s)" % ", ".join(f"{c:g}" for c in t)


def color(t) -> str:
    return "Color(%s, 1)" % ", ".join(f"{c:g}" for c in t)


def quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def door_gap(s: float, e: float) -> tuple:
    return (s, e, 0.0, DOOR_H)


class Zone:
    def __init__(self, root: str, out: str, *, height: float, doc: str) -> None:
        self.root, self.out, self.height, self.doc = root, ROOT / out, height, doc
        self.boxes = []      # (group, name, center, size, material, collide)
        self.windows = []    # (spec, node name, position, yaw)
        self.instances = []  # (name, scene key, position, rotation)
        self.signs = []      # (name, position, yaw, text, font_size, pixel_size, color)
        self.lights = []     # (name, kind, position, rotation, color, energy, range, shadow, extra)
        self.probes = []     # (name, center, size, blend)
        self.daylight_probes = []
        self.entries = []    # (name, position, yaw)
        self.perf_path = []  # (position, rotation)

    # -- layout

    def box(self, group, name, center, size, mat, collide=True):
        """collide: True (collision = visual box), False, or (center, size) for another box."""
        if isinstance(collide, tuple):
            collide = (tuple(collide[0]), tuple(collide[1]))
        self.boxes.append((group, name, tuple(center), tuple(size), mat, collide))

    def wall(self, group, name, axis, line, span, openings=(), mat="wall", bottom=0.0, top=None):
        """Wall along `axis` ('x' or 'z') at the fixed other coordinate `line`, from span[0] to
        span[1], floor to ceiling. openings: (start, end, bottom, top) along the wall."""
        top = self.height if top is None else top
        a0, a1 = span

        def put(n, s, e, y0, y1):
            if e - s < 1e-3 or y1 - y0 < 1e-3:
                return
            mid, length = (s + e) / 2, e - s
            cy, hy = (y0 + y1) / 2, y1 - y0
            if axis == "x":
                self.box(group, n, (mid, cy, line), (length, hy, T), mat)
            else:
                self.box(group, n, (line, cy, mid), (T, hy, length), mat)

        cursor, i = a0, 0
        for s, e, ob, ot in sorted(openings):
            put(f"{name}{i}", cursor, s, bottom, top)
            put(f"{name}{i}Below", s, e, bottom, ob)
            put(f"{name}{i}Above", s, e, ot, top)
            cursor, i = e, i + 1
        put(f"{name}{i}", cursor, a1, bottom, top)

    @staticmethod
    def door_gap(s, e):
        return door_gap(s, e)

    @staticmethod
    def window_gap(spec_name, x):
        """The wall cut for a window spec centered at x (along the wall)."""
        x0, x1, y0, y1 = window_specs.opening(*window_specs.spec(spec_name))
        return (x + x0, x + x1, y0, y1)

    def window(self, spec, name, position, yaw=0):
        """A generated window scene (tools/props/window.py); its wall needs the window_gap()."""
        self.windows.append((spec, name, tuple(position), yaw))

    def instance(self, name, key, position, rotation=(0, 0, 0)):
        self.instances.append((name, key, tuple(position), tuple(rotation)))

    def sign(self, name, position, yaw, text, *, font_size=64, pixel_size=0.002, col=(0.85, 0.93, 1.0),
             lit=True, align="center"):
        """A Label3D sign: faces +Z turned by yaw (degrees about Y). lit: self-lit (unshaded), so wayfinding
        reads at night (style guide); unlit for lettering on things (unit numbers). align: center or left."""
        self.signs.append((name, tuple(position), yaw, text, font_size, pixel_size, tuple(col), lit, align))

    def light(self, name, kind, position, *, rotation=None, color=(1, 1, 1), energy=1.0, range=4.0,
              shadow=False, extra=""):
        self.lights.append((name, kind, tuple(position), rotation, tuple(color), energy, range, shadow, extra))

    def probe(self, name, center, size, blend=None, *, daylight=False):
        self.probes.append((name, tuple(center), tuple(size), blend))
        if daylight:
            self.daylight_probes.append(name)

    def entry(self, name, position, yaw=0):
        self.entries.append((name, tuple(position), yaw))

    def perf_marker(self, position, rotation=(0, 0, 0)):
        self.perf_path.append((tuple(position), tuple(rotation)))

    # -- writer

    def write(self) -> str:
        ext, subs, nodes, ids = [], [], [], {}

        def add_ext(key, typ, path):
            if key not in ids:
                ids[key] = f"{len(ids) + 1}_{key}"
                ext.append(f'[ext_resource type="{typ}" path="{path}" id="{ids[key]}"]')

        for mat in dict.fromkeys(b[4] for b in self.boxes):
            add_ext(mat, "Material", f"res://assets/materials/{MATS[mat]}.tres")
        for key in dict.fromkeys(i[1] for i in self.instances):
            add_ext(key, "PackedScene", SCENES[key])
        for spec in dict.fromkeys(w[0] for w in self.windows):
            add_ext(spec, "PackedScene", "res://" + window_specs.paths(spec)["tscn"])
        if self.daylight_probes:
            add_ext("interior_daylight", "Script", INTERIOR_DAYLIGHT_SCRIPT)

        sizes = {}
        all_sizes = [b[3] for b in self.boxes] + [b[5][1] for b in self.boxes if isinstance(b[5], tuple)]
        for size in all_sizes:
            if size not in sizes:
                sid = f"s{len(sizes)}"
                sizes[size] = sid
                subs.append(f'[sub_resource type="BoxMesh" id="BoxMesh_{sid}"]\nsize = {v3(size)}\n')
                subs.append(f'[sub_resource type="BoxShape3D" id="BoxShape3D_{sid}"]\nsize = {v3(size)}\n')
        occluders = {}
        for _, _, _, size, mat, _ in self.boxes:
            osize = occluder_size(size)
            if mat in OCCLUDER_MATS and osize not in occluders:
                oid = f"o{len(occluders)}"
                occluders[osize] = oid
                subs.append(f'[sub_resource type="BoxOccluder3D" id="BoxOccluder3D_{oid}"]\nsize = {v3(osize)}\n')
        bounds = self.bounds()
        bound_ids = {}
        for _, size in bounds:
            if size not in bound_ids:
                bid = f"b{len(bound_ids)}"
                bound_ids[size] = bid
                subs.append(f'[sub_resource type="BoxShape3D" id="BoxShape3D_{bid}"]\nsize = {v3(size)}\n')

        nodes.append(f'[node name="{self.root}" type="Node3D"]\nmetadata/_doc = {quote(self.doc)}\n')

        for g in dict.fromkeys(b[0] for b in self.boxes):
            nodes.append(f'[node name="{g}" type="StaticBody3D" parent="."]\n')
            for gg, name, center, size, mat, collide in self.boxes:
                if gg != g:
                    continue
                shadow = "cast_shadow = 0\n" if mat in UNSHADOWED else ""
                nodes.append(f'[node name="{name}" type="MeshInstance3D" parent="{g}"]\n'
                             f"position = {v3(center)}\n{shadow}"
                             f'mesh = SubResource("BoxMesh_{sizes[size]}")\n'
                             f'surface_material_override/0 = ExtResource("{ids[mat]}")\n')
                if collide:
                    col_center, col_size = collide if isinstance(collide, tuple) else (center, size)
                    nodes.append(f'[node name="{name}Collision" type="CollisionShape3D" parent="{g}"]\n'
                                 f"position = {v3(col_center)}\n"
                                 f'shape = SubResource("BoxShape3D_{sizes[col_size]}")\n')

        nodes.append('[node name="Occluders" type="Node3D" parent="."]\n'
                     'metadata/_doc = "Occlusion culling: one box per wall, floor and ceiling box, inset on its thin axis; '
                     'openings stay holes. <Window>View: the window openings, for OutsideView (D-048). GENERATED."\n')
        for _, name, center, size, mat, _ in self.boxes:
            if mat in OCCLUDER_MATS:
                nodes.append(f'[node name="{name}" type="OccluderInstance3D" parent="Occluders"]\n'
                             f"position = {v3(center)}\n"
                             f'occluder = SubResource("BoxOccluder3D_{occluders[occluder_size(size)]}")\n')
        for spec, name, pos, yaw in self.windows:
            x0, x1, y0, y1 = window_specs.opening(*window_specs.spec(spec))
            m = WINDOW_VIEW_MARGIN
            rot = f"rotation_degrees = Vector3(0, {yaw:g}, 0)\n" if yaw else ""
            nodes.append(f'[node name="{name}View" type="VisibleOnScreenNotifier3D" parent="Occluders" groups=["outside_view"]]\n'
                         f"position = {v3(pos)}\n{rot}"
                         f"aabb = AABB({x0 - m:g}, {y0 - m:g}, {-T / 2:g}, {x1 - x0 + 2 * m:g}, {y1 - y0 + 2 * m:g}, "
                         f"{T / 2 + WINDOW_VIEW_DEPTH:g})\n")

        nodes.append('[node name="Bounds" type="Area3D" parent="."]\n'
                     f"collision_layer = 0\ncollision_mask = {PLAYER_BODY_MASK}\nmonitorable = false\n"
                     'metadata/_doc = "Where the player is in this zone (Player Body, floor to ceiling over every floor), '
                     'for ZoneStreamer (D-059). GENERATED."\n')
        for i, (center, size) in enumerate(bounds):
            nodes.append(f'[node name="Box{i}" type="CollisionShape3D" parent="Bounds"]\n'
                         f"position = {v3(center)}\n"
                         f'shape = SubResource("BoxShape3D_{bound_ids[size]}")\n')

        if self.windows:
            nodes.append('[node name="Windows" type="Node3D" parent="."]\n'
                         'metadata/_doc = "Generated window scenes (tools/props/window.py) in their wall openings."\n')
            for spec, name, pos, yaw in self.windows:
                rot = f"rotation_degrees = Vector3(0, {yaw:g}, 0)\n" if yaw else ""
                nodes.append(f'[node name="{name}" parent="Windows" instance=ExtResource("{ids[spec]}")]\n'
                             f"position = {v3(pos)}\n{rot}")

        nodes.append('[node name="Props" type="Node3D" parent="."]\n')
        for name, key, pos, rot in self.instances:
            rot_line = f"rotation_degrees = {v3(rot)}\n" if any(rot) else ""
            nodes.append(f'[node name="{name}" parent="Props" instance=ExtResource("{ids[key]}")]\n'
                         f"position = {v3(pos)}\n{rot_line}")

        if self.signs:
            nodes.append('[node name="Signs" type="Node3D" parent="."]\n'
                         'metadata/_doc = "Wayfinding and unit numbers (placeholders until the world directory, '
                         'roadmap). GENERATED."\n')
            for name, pos, yaw, text, font_size, pixel_size, col, lit, align in self.signs:
                rot = f"rotation_degrees = Vector3(0, {yaw:g}, 0)\n" if yaw else ""
                shaded = "" if lit else "shaded = true\n"
                aligned = "horizontal_alignment = 0\n" if align == "left" else ""
                nodes.append(f'[node name="{name}" type="Label3D" parent="Signs"]\nposition = {v3(pos)}\n{rot}'
                             f"pixel_size = {pixel_size:g}\n{shaded}double_sided = false\n"
                             f"modulate = {color(col)}\noutline_size = 0\nfont_size = {font_size}\n"
                             f"text = {quote(text)}\n{aligned}")

        nodes.append('[node name="Lighting" type="Node3D" parent="."]\n')
        for name, kind, pos, rot, col, energy, rng, shadow, extra in self.lights:
            typ = "OmniLight3D" if kind == "Omni" else "SpotLight3D"
            range_key = "omni_range" if kind == "Omni" else "spot_range"
            rot_line = f"rotation_degrees = {v3(rot)}\n" if rot else ""
            shadow_line = "shadow_enabled = true\n" if shadow else ""
            nodes.append(f'[node name="{name}" type="{typ}" parent="Lighting"]\nposition = {v3(pos)}\n{rot_line}'
                         f"light_color = {color(col)}\nlight_energy = {energy:g}\n{shadow_line}"
                         f"{range_key} = {rng:g}\n{extra}")
        for name, center, size, blend in self.probes:
            blend_line = f"blend_distance = {blend:g}\n" if blend is not None else ""
            nodes.append(f'[node name="{name}" type="ReflectionProbe" parent="Lighting"]\nposition = {v3(center)}\n'
                         f"size = {v3(size)}\n{blend_line}box_projection = true\ninterior = true\nambient_mode = 0\n")
        if self.daylight_probes:
            probes = ", ".join(f'NodePath("../{n}")' for n in self.daylight_probes)
            nodes.append('[node name="Daylight" type="Node" parent="Lighting" node_paths=PackedStringArray("probes")]\n'
                         f'script = ExtResource("{ids["interior_daylight"]}")\nprobes = [{probes}]\n'
                         'metadata/_doc = "Re-captures the probes that see a window as the daylight changes (D-051)."\n')

        nodes.append('[node name="Entries" type="Node3D" parent="."]\n')
        for name, pos, yaw in self.entries:
            nodes.append(f'[node name="{name}" type="Marker3D" parent="Entries"]\nposition = {v3(pos)}\n'
                         + (f"rotation_degrees = Vector3(0, {yaw:g}, 0)\n" if yaw else ""))

        nodes.append('[node name="PerfPath" type="Node3D" parent="."]\n'
                     'metadata/_doc = "Perf flythrough waypoints at eye height, visited in order; -Z is the view '
                     'direction. See tools/perf."\n')
        for i, (pos, rot) in enumerate(self.perf_path):
            rot_line = f"rotation_degrees = {v3(rot)}\n" if any(rot) else ""
            nodes.append(f'[node name="P{i}" type="Marker3D" parent="PerfPath"]\nposition = {v3(pos)}\n{rot_line}')

        text = "[gd_scene format=3]\n\n" + "\n".join(ext) + "\n\n" + "\n".join(subs) + "\n" + "\n".join(nodes)
        text = carry_ids(text, self.out)
        return text

    def bounds(self) -> list[tuple]:
        """Floor footprints, floor to ceiling: (center, size)."""
        out = []
        for _, _, center, size, mat, _ in self.boxes:
            if mat in FLOOR_MATS:
                out.append(((center[0], self.height / 2, center[2]), (size[0], self.height, size[2])))
        return out

    def save(self, check=False) -> int:
        """Writes the scene (or with check=True compares it); returns 1 if it differs."""
        text = self.write()
        old = self.out.read_text(encoding="utf-8") if self.out.exists() else ""
        rel = self.out.relative_to(ROOT)
        if check:
            print(f"{'OK   ' if old == text else 'DIFF '} {rel}")
            return int(old != text)
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {rel}: {len(self.boxes)} boxes, {len(self.windows)} windows, {len(self.instances)} props, "
              f"{len(self.signs)} signs, {len(self.lights)} lights, {len(self.probes)} probes, "
              f"{len(self.bounds())} bounds")
        return 0


def occluder_size(size):
    """The box's size with its thinnest axis inset by OCCLUDER_INSET on both faces."""
    thin = size.index(min(size))
    return tuple(round(c - 2 * OCCLUDER_INSET, 4) if i == thin else c for i, c in enumerate(size))


def carry_ids(text: str, out: Path) -> str:
    """Keeps the scene uid and the node unique_ids the editor gave the existing scene, so
    regenerating (and the editor's next save) only changes what changed."""
    if not out.exists():
        return text
    old = out.read_text(encoding="utf-8")
    uid = re.search(r'^\[gd_scene[^\]]* uid="([^"]+)"', old)
    if uid:
        text = text.replace("[gd_scene format=3]", f'[gd_scene format=3 uid="{uid.group(1)}"]', 1)
    ids = {}
    for line in old.splitlines():
        m = NODE_HEADER.match(line)
        uid_m = re.search(r" unique_id=(\d+)", line)
        if m and uid_m:
            ids[(m.group(2), m.group(1))] = uid_m.group(1)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = NODE_HEADER.match(line)
        if m and (m.group(2), m.group(1)) in ids:
            lines[i] = line[:m.end()] + f" unique_id={ids[(m.group(2), m.group(1))]}" + line[m.end():]
    return "\n".join(lines)
