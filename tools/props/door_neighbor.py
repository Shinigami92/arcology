"""Neighbor's door: assets/props/door_entrance/door_neighbor.tscn, the entrance door's frame and leaf, shut for good.

    python tools/props/door_neighbor.py [--check]

The other units on our floor (D-059): the same security door as ours (tools/props/door_entrance.py), static,
seen from the corridor only. The leaf's unit plate still reads 4417 (it's in the leaf glb); the corridor generator
covers it with the unit's own number (tools/blockout/corridor.py, NUMBER_PLATE).
"""

from door_entrance import GLB, HARDWARE, HINGE, LEAF_BOX
from prop_scenes import Scene, main

DOC = ("A neighbor's front door: the entrance door's steel frame and leaf (0.90 x 2.10 m opening in a 0.20 m wall), "
       "closed and static. Origin = bottom center of the opening on the wall's center plane; +Z = the unit's side. "
       "Collision: the frame's own shapes and the leaf box. Unit number: placed by the zone over the leaf's plate.")


def scenes() -> dict[str, Scene]:
    s = Scene("DoorNeighbor", DOC)
    s.instance("Frame", GLB.format("frame"))
    s.node("Leaf", "StaticBody3D", position=HINGE)
    name, center, size = LEAF_BOX
    s.boxes("Leaf", [(name, center, size)], prefix="leaf")
    s.instance("Model", GLB.format("leaf"), parent="Leaf")
    for node, part, position in HARDWARE:
        if part == "lever_corridor":
            s.instance(node, GLB.format(part), parent="Leaf", position=position)
    return {"assets/props/door_entrance/door_neighbor.tscn": s}


if __name__ == "__main__":
    main(scenes)
