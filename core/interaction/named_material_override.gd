class_name NamedMaterialOverride
extends Node
## Puts [member material] on every mesh surface under [member root] whose
## material is named [member material_name] (an imported glb's material
## slot, e.g. a window's `window_led`), as a surface override. Runs once.

@export var root: Node
@export var material_name := ""
@export var material: Material


func _ready() -> void:
	if not root or not material or material_name.is_empty():
		push_error("NamedMaterialOverride needs root, material_name and material: %s" % get_path())
		return
	if _apply(root) == 0:
		push_warning("NamedMaterialOverride: no material named '%s' under %s" % [material_name, root.get_path()])


func _apply(node: Node) -> int:
	var count := 0
	var mesh_instance := node as MeshInstance3D
	if mesh_instance and mesh_instance.mesh:
		for i in mesh_instance.mesh.get_surface_count():
			var mat := mesh_instance.mesh.surface_get_material(i)
			if mat and mat.resource_name == material_name:
				mesh_instance.set_surface_override_material(i, material)
				count += 1
	for child in node.get_children():
		count += _apply(child)
	return count
