class_name UnitPlate
extends Node3D
## The unit number on a front door's plate (D-062). The leaf glb's plate reads
## 4417 (ours); a door placed for another unit carries `metadata/unit_number`
## on its root (the zone generator writes it), and this node covers the plate
## with a dark one showing that number. Without the metadata it does nothing.
## Origin: the plate's face center on the leaf, +Z out of the door (corridor
## side). Builds once at start; no processing.

## Plate cover size (m): a little larger than the glb's plate, so it hides it.
const COVER := Vector3(0.25, 0.115, 0.006)
const NUMBER_HEIGHT := 0.058

static var _cover_material: StandardMaterial3D


func _ready() -> void:
	var root := owner if owner else get_parent()
	var number := str(root.get_meta(&"unit_number", "")) if root else ""
	if number.is_empty():
		return
	if not _cover_material:
		_cover_material = StandardMaterial3D.new()
		_cover_material.albedo_color = Color(0.018, 0.019, 0.022)
		_cover_material.roughness = 0.35
		_cover_material.metallic = 0.2
	var cover := MeshInstance3D.new()
	cover.name = "Cover"
	var box := BoxMesh.new()
	box.size = COVER
	cover.mesh = box
	cover.material_override = _cover_material
	cover.position = Vector3(0, 0, COVER.z / 2.0 + 0.003)
	add_child(cover)
	var label := Label3D.new()
	label.name = "Number"
	label.text = number
	label.font_size = 96 if number.length() <= 4 else 64
	label.pixel_size = NUMBER_HEIGHT / 96.0
	label.modulate = Color(0.92, 0.9, 0.85)
	label.shaded = true
	label.double_sided = false
	label.outline_size = 0
	label.position = Vector3(0, 0, COVER.z + 0.0035)
	add_child(label)
