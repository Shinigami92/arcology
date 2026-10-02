class_name NamedMaterialOverride
extends Node
## Puts [member material] on every mesh surface under [member root] whose
## material is named [member material_name] (an imported glb's material
## slot, e.g. a window's `window_led`), as a surface override. Runs once.
##
## Without [member material], it overrides those surfaces with a copy of the
## imported material instead. Either way [member properties] are then set on
## the override (e.g. {"blend_mode": 1} to turn an emissive glow additive), and
## [member cast_shadow] (if >= 0) on the meshes that carry it.
## Put it before nodes that look the material up by name (LightSwitch): the
## copy keeps the name.

@export var root: Node
@export var material_name := ""
@export var material: Material
## Material properties set on the override (name -> value).
@export var properties: Dictionary = {}
## GeometryInstance3D.ShadowCastingSetting for meshes with this material; -1 = unchanged.
@export_range(-1, 3) var cast_shadow := -1

var _override: Material


func _ready() -> void:
	if not root or material_name.is_empty() or (not material and properties.is_empty()):
		push_error("NamedMaterialOverride needs root, material_name and a material or properties: %s" % get_path())
		return
	if material and not properties.is_empty():
		_override = material.duplicate()
		_set_properties(_override)
	else:
		_override = material
	if _apply(root) == 0:
		push_warning("NamedMaterialOverride: no material named '%s' under %s" % [material_name, root.get_path()])


func _apply(node: Node) -> int:
	var count := 0
	var mesh_instance := node as MeshInstance3D
	if mesh_instance and mesh_instance.mesh:
		for i in mesh_instance.mesh.get_surface_count():
			var mat := mesh_instance.mesh.surface_get_material(i)
			if mat and mat.resource_name == material_name:
				if not _override:
					_override = mat.duplicate()
					_set_properties(_override)
				mesh_instance.set_surface_override_material(i, _override)
				if cast_shadow >= 0:
					mesh_instance.cast_shadow = cast_shadow as GeometryInstance3D.ShadowCastingSetting
				count += 1
	for child in node.get_children():
		count += _apply(child)
	return count


func _set_properties(mat: Material) -> void:
	for key: Variant in properties:
		mat.set(StringName(str(key)), properties[key])
