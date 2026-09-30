"""Stage 3: export every window's glb files and the kit into assets/architecture/windows/.

  blender -b --factory-startup blender/architecture/windows_<spec>.blend --python blender/architecture/windows/export.py [-- --spec F]

Per window: <name>_frame.glb (static, origin = the window's local origin),
<name>_sash.glb (vent: origin on the hinge axis, HandleGrip empty),
<name>_shade_bar.glb (a fixed bay's bar) and <name>_shade_bar_vent.glb (the
vent's bar, narrower by 2 * sash_face), bars with the origin at their top
center. Kit: window_panel.glb (+ ButtonTop / ButtonBottom empties),
window_panel_button.glb, the shade fabric PNGs and the trim sheet PNGs (the
same pixels every glb embeds, for a shared Godot material).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from windows_common import (  # noqa: E402
    FABRIC_ALBEDO, FABRIC_NORMAL, GLB_BUTTON, GLB_PANEL, MAT_TRIM, TRIM_PNG, bar_objects, button_objects,
    frame_objects, glb_bar, glb_frame, glb_sash, load_spec, panel_objects, sash_objects, windows,
)
from arcology_blender.export import export_glb, export_glb_at_origin  # noqa: E402
from arcology_blender.trim import image_pixels, write_png  # noqa: E402


def root(objs):
    return [o for o in objs if o.parent is None][0]


def main():
    _, data = load_spec()
    for w in windows(data):
        export_glb(frame_objects(w.name), glb_frame(w.name))
        if w.vent:
            objs = sash_objects(w.name)
            export_glb_at_origin(root(objs), objs, glb_sash(w.name))
        for vent in (False, True):
            objs = bar_objects(w.name, vent)
            if objs:
                export_glb_at_origin(objs[0], objs, glb_bar(w.name, vent))
    objs = panel_objects()
    export_glb_at_origin(root(objs), objs, GLB_PANEL)
    objs = button_objects()
    export_glb_at_origin(objs[0], objs, GLB_BUTTON)
    write_png(FABRIC_ALBEDO, image_pixels(bpy.data.images["shade_fabric_albedo"]))
    write_png(FABRIC_NORMAL, image_pixels(bpy.data.images["shade_fabric_normal"]))
    for k, path in TRIM_PNG.items():
        write_png(path, image_pixels(bpy.data.images[f"{MAT_TRIM}_{k}"]))


if __name__ == "__main__":
    main()
