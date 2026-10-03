"""Hand poses: `Open` (relaxed on a controller, nothing pressed) and `Grip` (a full
grip around a 38 mm handle across the palm, thumb wrapped). Godot's hand blend
tree mixes them per finger (index = trigger, the others = grip), so each
finger's curl stands on its own.

Rotations are degrees in the bones' local axes (rig.pose_action): fingers curl
about +X toward the palm and spread about Z (+ toward the index); the thumb's
metacarpal flexes across the palm about +X and abducts away from the index
about +Z. Poses are authored for the left hand and mirrored to the right
(rig.mirror_rotations).

The grip is solved, not hand-tuned: a cylinder of GRIP_DIAMETER lies across the
palm (diagonal, from the heel of the hand toward the index knuckle), pushed out
until the palm only touches it; then each finger's three joints are searched
(coarse to fine) so every segment lies as close to the handle as possible
without pressing in deeper than CONTACT. The thumb (metacarpal flexion and
abduction, both joints) is searched the same way against the handle, the palm
and the posed fingers.
"""

import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from silena_vesper_common import GRIP_DIAMETER, POSES
import glove as glove_geo
from arcology_blender import rig

# Relaxed hand: a cascade from index to little (more curl toward the little finger),
# fingers slightly spread, the thumb resting a little toward the palm.
OPEN = {
    "LeftIndexProximal": (14.0, 0.0, 1.0), "LeftIndexIntermediate": (22.0, 0.0, 0.0),
    "LeftIndexDistal": (12.0, 0.0, 0.0),
    "LeftMiddleProximal": (18.0, 0.0, -1.0), "LeftMiddleIntermediate": (27.0, 0.0, 0.0),
    "LeftMiddleDistal": (14.0, 0.0, 0.0),
    "LeftRingProximal": (22.0, 0.0, -3.0), "LeftRingIntermediate": (31.0, 0.0, 0.0),
    "LeftRingDistal": (16.0, 0.0, 0.0),
    "LeftLittleProximal": (26.0, 0.0, -5.0), "LeftLittleIntermediate": (33.0, 0.0, 0.0),
    "LeftLittleDistal": (17.0, 0.0, 0.0),
    "LeftThumbMetacarpal": (14.0, 0.0, -4.0), "LeftThumbProximal": (14.0, 0.0, 0.0),
    "LeftThumbDistal": (16.0, 0.0, 0.0),
}

# Grip: spread per finger (the curls and the thumb are solved).
GRIP_SPREAD = {"Index": 2.0, "Middle": 0.0, "Ring": -2.0, "Little": -5.0}
GRIP_HANDLE_TILT = 18.0         # degrees: handle axis from "across the knuckles" toward the index knuckle
GRIP_HANDLE_ALONG = 0.80        # handle center along the palm (wrist 0, middle knuckle 1)
CONTACT = -0.0015               # leather and flesh compress this much where it touches the handle
LIMITS = (95.0, 110.0, 80.0)    # base, middle, last joint


class Solver:
    """Linear blend skinning of the glove in numpy (the Armature modifier is off
    while solving), so a pose can be tried thousands of times."""

    def __init__(self, arm, glove, hf):
        self.arm, self.glove, self.hf = arm, glove, hf
        self.pb = arm.pose.bones
        for p in self.pb:
            p.rotation_mode = "XYZ"
            p.rotation_euler = (0.0, 0.0, 0.0)
        self.mod = glove.modifiers["Armature"]
        self.mod.show_viewport = False
        bpy.context.view_layer.update()
        me = glove.data
        n = len(me.vertices)
        mw = np.array(glove.matrix_world)
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        self.rest = co.reshape(-1, 3).astype(np.float64) @ mw[:3, :3].T + mw[:3, 3]
        self.bones = [vg.name for vg in glove.vertex_groups if arm.data.bones.get(vg.name)]
        col = {name: i for i, name in enumerate(self.bones)}
        gi = {vg.index: col.get(vg.name) for vg in glove.vertex_groups}
        self.w = np.zeros((n, len(self.bones)))
        for v in me.vertices:
            for g in v.groups:
                if gi[g.group] is not None:
                    self.w[v.index, gi[g.group]] = g.weight
        self.dominant = [self.bones[i] if self.w[k, i] > 0 else "" for k, i in enumerate(self.w.argmax(axis=1))]
        region = np.zeros(n, dtype=np.float32)
        me.attributes["region"].data.foreach_get("value", region)
        self.shell = region == glove_geo.REGION_SHELL
        me.calc_loop_triangles()
        self.tris = [tuple(t.vertices) for t in me.loop_triangles]
        amw = np.array(arm.matrix_world)
        self.arm_mw = amw
        self.inv_rest = {b: np.linalg.inv(amw @ np.array(arm.data.bones[b].matrix_local)) for b in self.bones}

    def finish(self):
        for p in self.pb:
            p.rotation_euler = (0.0, 0.0, 0.0)
        self.mod.show_viewport = True
        bpy.context.view_layer.update()

    def set(self, rotations):
        for name, deg in rotations.items():
            self.pb[name].rotation_euler = [math.radians(d) for d in deg]

    def coords(self, idx=None):
        """World positions of the glove's vertices (or `idx`) in the current pose."""
        bpy.context.view_layer.update()
        pts = self.rest if idx is None else self.rest[idx]
        w = self.w if idx is None else self.w[idx]
        ph = np.c_[pts, np.ones(len(pts))]
        out = np.zeros((len(pts), 3))
        for i, b in enumerate(self.bones):
            wi = w[:, i]
            if not wi.any():
                continue
            m = self.arm_mw @ np.array(self.pb[b].matrix) @ self.inv_rest[b]
            out += wi[:, None] * (ph @ m.T)[:, :3]
        return out

    def verts_of(self, bones):
        bones = set(bones)
        return np.array([i for i, d in enumerate(self.dominant) if d in bones and self.shell[i]], dtype=int)

    def cylinder_sd(self, pts):
        d = pts - self.c
        along = d @ self.axis
        radial = d - along[:, None] * self.axis
        return np.linalg.norm(radial, axis=1) - GRIP_DIAMETER * 0.5

    def place_handle(self):
        hf = self.hf
        tilt = math.radians(GRIP_HANDLE_TILT)
        self.axis = np.array((hf.across * math.cos(tilt) + hf.along * math.sin(tilt)).normalized()[:])
        palm = self.verts_of({f"{hf.side}Hand"})
        co = self.coords(palm)
        start = np.array((hf.wrist + hf.along * hf.palm_length * GRIP_HANDLE_ALONG)[:])
        normal = np.array(hf.palm[:])
        lo, hi = 0.0, 0.08  # move out along the palm normal until the palm only touches
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            self.c = start + normal * mid
            if self.cylinder_sd(co).min() < CONTACT:
                lo = mid
            else:
                hi = mid
        self.c = start + normal * hi

    @staticmethod
    def search(cost, ranges, steps):
        """Coarse-to-fine grid search minimizing cost(*angles) over `ranges` [(lo, hi), ...]."""
        best, center = None, None
        for k, step in enumerate(steps):
            axes = []
            for d, (lo, hi) in enumerate(ranges):
                if center is None:
                    axes.append(np.arange(lo, hi + 1e-6, step))
                else:
                    span = steps[k - 1]
                    axes.append(np.unique(np.clip(np.arange(center[d] - span, center[d] + span + 1e-6, step), lo, hi)))
            for combo in np.array(np.meshgrid(*axes, indexing="ij")).reshape(len(ranges), -1).T:
                val = cost(*combo)
                if best is None or val < best[0]:
                    best = (val, tuple(float(x) for x in combo))
            center = best[1]
        return best

    def wrap_finger(self, names, spread):
        """Curl one finger around the handle: every segment as close to it as possible
        without pressing in deeper than CONTACT."""
        segs = [self.verts_of([n]) for n in names]
        allv = np.concatenate(segs)
        offsets = np.cumsum([0] + [len(s) for s in segs])

        def pose(a1, a2, a3):
            return {names[0]: (a1, 0.0, spread), names[1]: (a2, 0.0, 0.0), names[2]: (a3, 0.0, 0.0)}

        def cost(a1, a2, a3):
            self.set(pose(a1, a2, a3))
            sd = self.cylinder_sd(self.coords(allv))
            gaps, pen = [], 0.0
            for i in range(3):
                seg = np.sort(sd[offsets[i]:offsets[i + 1]])
                pen += max(0.0, CONTACT - seg[0])
                gaps.append(seg[: max(3, len(seg) * 3 // 10)].mean())  # the palm side lies along the handle
            coupling = 0.0015 * ((a3 - 0.7 * a2) / 30.0) ** 2         # the last joint follows the middle one
            return gaps[0] + gaps[1] + 1.5 * gaps[2] + 40.0 * pen + coupling

        _, best = self.search(cost, [(0.0, LIMITS[0]), (0.0, LIMITS[1]), (0.0, LIMITS[2])], (12.0, 4.0, 1.0))
        out = pose(*best)
        self.set(out)
        return out

    def wrap_thumb(self, names, obstacles):
        """Close the thumb over the handle and the fingers: its metacarpal (flexion
        about X, abduction about Z) and both joints are searched together; no part of
        it may press into the handle, the palm or the fingers (`obstacles`: vertex
        indices, posed already; signed distance to their triangles)."""
        co = self.coords()
        obs = set(int(i) for i in obstacles)
        tris = [t for t in self.tris if all(i in obs for i in t)]
        tree = BVHTree.FromPolygons([Vector(p) for p in co], tris, all_triangles=True)
        mw = self.arm.matrix_world
        thumb = []
        for k, n in enumerate(names[1:]):
            b = self.arm.data.bones[n]
            h, t = np.array((mw @ b.head_local)[:]), np.array((mw @ b.tail_local)[:])
            for i in self.verts_of([n]):
                u = (self.rest[i] - h) @ (t - h) / np.dot(t - h, t - h)
                if k == 1 or u > 0.3:  # the proximal's base meets the palm on purpose
                    thumb.append(i)
        thumb = np.array(thumb, dtype=int)
        distal = np.isin(thumb, self.verts_of([names[2]]))

        def pose(x1, z1, a2, a3):
            return {names[0]: (x1, 0.0, z1), names[1]: (a2, 0.0, 0.0), names[2]: (a3, 0.0, 0.0)}

        def cost(x1, z1, a2, a3):
            self.set(pose(x1, z1, a2, a3))
            pts = self.coords(thumb)
            sd = self.cylinder_sd(pts)
            inside = 0.0
            gap = np.empty(len(pts))
            for j, p in enumerate(pts):
                loc, nrm, _, dist = tree.find_nearest(Vector(p))
                signed = (Vector(p) - loc).dot(nrm) if loc is not None else 1.0
                gap[j] = signed
                inside += max(0.0, -0.0008 - signed)
            pen = np.clip(CONTACT - sd, 0.0, None).sum() + inside
            near = np.minimum(sd, gap)
            pad = np.sort(near[distal])[: max(3, distal.sum() // 4)].mean()
            return pad + 0.3 * max(0.0, near[~distal].min()) + 10.0 * pen

        _, best = self.search(cost, [(5.0, 55.0), (-15.0, 25.0), (0.0, 70.0), (0.0, 85.0)], (10.0, 4.0, 2.0))
        out = pose(*best)
        self.set(out)
        return out


def solve_grip(arm, glove, hf):
    side = hf.side
    s = Solver(arm, glove, hf)
    s.place_handle()
    rot = {}
    for finger in ("Index", "Middle", "Ring", "Little"):
        rot.update(s.wrap_finger(glove_geo.chain(side, finger), GRIP_SPREAD[finger]))
    obstacles = s.verts_of([f"{side}Hand"] + [n for f in ("Index", "Middle", "Ring", "Little")
                                              for n in glove_geo.chain(side, f)])
    rot.update(s.wrap_thumb(glove_geo.chain(side, "Thumb"), obstacles))
    handle = (Vector(s.c), Vector(s.axis))
    s.finish()
    return rot, handle


def build_poses(arm, glove, hf):
    grip, (center, axis) = solve_grip(arm, glove, hf)
    arm["grip_center"] = tuple(center)
    arm["grip_axis"] = tuple(axis)
    for name, deg in grip.items():
        print(f"GRIP {name} " + " ".join(f"{d:6.1f}" for d in deg))
    for name, left in (("Open", OPEN), ("Grip", grip)):
        both = dict(left)
        both.update(rig.mirror_rotations(arm, left, "Left", "Right"))
        rig.pose_action(arm, name, both)
    assert tuple(t.name for t in arm.animation_data.nla_tracks) == POSES
