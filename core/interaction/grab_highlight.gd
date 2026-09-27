class_name GrabHighlight
extends Node
## Glowing rim on a pickable while a hand targets it (near or ranged grab).
##
## Add as a direct child of an XRToolsPickable. Uses material_overlay, so the
## object's own materials are untouched and the extra pass only runs while
## highlighted.

const HIGHLIGHT := preload("res://assets/materials/grab_highlight.tres")

var _meshes: Array[MeshInstance3D] = []


func _ready() -> void:
	var pickable := get_parent() as XRToolsPickable
	if not pickable:
		push_error("GrabHighlight must be a child of XRToolsPickable: %s" % get_path())
		return
	for node in pickable.find_children("*", "MeshInstance3D", true, false):
		_meshes.append(node as MeshInstance3D)
	pickable.highlight_updated.connect(_on_highlight_updated)


func _on_highlight_updated(_pickable: XRToolsPickable, enable: bool) -> void:
	for mesh in _meshes:
		mesh.material_overlay = HIGHLIGHT if enable else null
