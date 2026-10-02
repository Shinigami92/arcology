class_name EmissiveMaterials
extends RefCounted
## Finds the materials named [param material_name] on the meshes under a root
## (e.g. an imported glb), gives each mesh its own copy (so two lamps don't
## share one switch), and switches them on and off by emission energy only:
## toggling `emission_enabled` would compile a new shader variant on first use.

var _materials: Array[BaseMaterial3D] = []
var _energy_on: Array[float] = []
var _energy_off := 0.0


## on_energy < 0 keeps each material's imported energy as its "on" level;
## off_energy is the "off" level (0 = dark; a little keeps an indicator findable).
func _init(root: Node, material_name: String, on_energy := -1.0, off_energy := 0.0) -> void:
	_energy_off = off_energy
	if root:
		_collect(root, material_name, on_energy)


func is_empty() -> bool:
	return _materials.is_empty()


func set_on(on: bool) -> void:
	for i in _materials.size():
		_materials[i].emission_energy_multiplier = _energy_on[i] if on else _energy_off


func _collect(node: Node, material_name: String, on_energy: float) -> void:
	var mesh_instance := node as MeshInstance3D
	if mesh_instance and mesh_instance.mesh:
		for i in mesh_instance.mesh.get_surface_count():
			var mat := mesh_instance.get_active_material(i) as BaseMaterial3D
			if mat and mat.resource_name == material_name:
				var own := mat.duplicate() as BaseMaterial3D
				own.emission_enabled = true
				mesh_instance.set_surface_override_material(i, own)
				_materials.append(own)
				_energy_on.append(on_energy if on_energy >= 0.0 else own.emission_energy_multiplier)
	for child in node.get_children():
		_collect(child, material_name, on_energy)
