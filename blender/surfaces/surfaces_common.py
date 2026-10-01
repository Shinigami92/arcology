"""Apartment surface textures: seamless tileable PBR sets for floors, walls and ceilings.
Built on blender/lib (D-028); quick reference: blender/lib/README.md (module `surface`).

These are not meshes: Godot keeps the generated box shell (tools/blockout/apartment.py)
and maps each set with world-space triplanar projection, so each set is one square
tile that repeats in U and V with a known real-world size (TILE_M below: the Godot
material scales its UVs by 1 / tile).

Stages (Blender 5.2, background, from the repo root):

  blender -b --factory-startup --python blender/surfaces/build.py -- [--only a,b] [--preview DIR]
  blender -b --factory-startup --python blender/surfaces/render.py -- [--quick] [--out DIR] [--floor a,b]
  blender -b --factory-startup --python blender/surfaces/verify.py

build.py writes assets/materials/surfaces/<name>/<name>_{albedo,normal,orm}.png
(albedo sRGB; normal OpenGL +Y up; ORM linear: R = AO, G = roughness, B = metallic)
and, per set, a 2x2 tiled preview plus a full-resolution crop around the tile
corner (seam check) into the preview folder. render.py renders a 4 x 4 x 2.6 m
room corner once per floor set, with the wall and ceiling plaster. The recipes
(textures.py) are deterministic: same seed, same pixels.

ARCOLOGY_OUT_DIR=<folder> sends the textures there instead of the repo.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

from arcology_blender.scene import output_path, scratch_dir  # noqa: E402

PREVIEW = scratch_dir("surfaces")  # 2x2 tiles, seam crops, room renders (--preview / --out override)

# name: texture size (px, square), tile size (m), seed, where it goes
SETS = {
    "vinyl_plank": dict(size=2048, tile_m=7.32, seed=4101, use="floor: living room, kitchen, hallway, vestibule"),
    "carpet": dict(size=2048, tile_m=4.0, seed=4202, use="floor: bedroom (wall-to-wall)"),
    "polished_concrete": dict(size=2048, tile_m=4.0, seed=4303, use="floor: bathroom"),
    "wall_plaster": dict(size=2048, tile_m=4.0, seed=4404, use="all walls"),
    "ceiling_plaster": dict(size=1024, tile_m=4.0, seed=4505, use="all ceilings"),
}
FLOORS = ("vinyl_plank", "carpet", "polished_concrete")


def texture_dir(name):
    return output_path("assets", "materials", "surfaces", name)


def texture_paths(name):
    d = texture_dir(name)
    return {k: os.path.join(d, f"{name}_{k}.png") for k in ("albedo", "normal", "orm")}
