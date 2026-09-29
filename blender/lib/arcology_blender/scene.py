"""Scene setup, collections, part tags, GPU and paths."""

import os
import tempfile

import bpy

PART_KEY = "arcology_part"
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def repo_path(*parts):
    """Absolute path inside the repository."""
    return os.path.join(ROOT, *parts)


def output_path(*parts):
    """Where a stage writes a repo file (.blend, .glb). ARCOLOGY_OUT_DIR redirects
    all outputs to another folder, e.g. to rebuild an asset and compare it with
    the committed files."""
    out = os.environ.get("ARCOLOGY_OUT_DIR")
    return os.path.join(out, *parts) if out else repo_path(*parts)


def scratch_dir(name):
    """Folder for thumbnails and debug output, outside the repo.

    ARCOLOGY_RENDER_DIR overrides the base folder (default: <temp>/arcology).
    """
    base = os.environ.get("ARCOLOGY_RENDER_DIR", os.path.join(tempfile.gettempdir(), "arcology"))
    path = os.path.join(base, name)
    os.makedirs(path, exist_ok=True)
    return path


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.lights,
                 bpy.data.cameras, bpy.data.node_groups):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def get_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def tag(ob, part):
    """Mark an object as belonging to a part (e.g. "body", "body_col", "door")."""
    ob[PART_KEY] = part
    return ob


def part_objects(part, mesh_only=False):
    return [ob for ob in bpy.data.objects
            if ob.get(PART_KEY) == part and (ob.type == "MESH" or not mesh_only)]


def meshes(objs):
    """Only the mesh objects (drops empties such as HandleGrip)."""
    return [o for o in objs if o.type == "MESH"]


def tri_count(ob):
    if ob.type != "MESH" or ob.data is None:
        return 0
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def part_tris(part):
    return sum(tri_count(o) for o in part_objects(part))


def setup_gpu(scene):
    """Cycles on the GPU (OptiX), CPU as the fallback."""
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != "CPU"
        scene.cycles.device = "GPU"
    except Exception as exc:
        print("GPU setup failed, using CPU:", exc)
        scene.cycles.device = "CPU"


def set_colorspace(image, name):
    try:
        image.colorspace_settings.name = name
    except TypeError:
        image.colorspace_settings.name = {"Non-Color": "Non-Color", "sRGB": "sRGB"}.get(name, name)


def save_blend(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=False)
    print("SAVED", path)


def script_args():
    """Arguments after `--` on the Blender command line."""
    import sys
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
