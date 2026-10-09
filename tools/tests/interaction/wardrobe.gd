extends "res://tools/tests/interaction/base.gd"
## Wardrobe group: the interior (rail, hangers, boxes, drawers).


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["wardrobe_interior", _test_wardrobe_interior],
	]


## The wardrobe with an interior (variant with drawers, box and hangers):
## drawers slide and carry their collision, the hangers start hung on the
## rail, a hanger dropped near the rail hangs again, and one dropped away
## from it falls; the box and lid rest on the shelf.
func _test_wardrobe_interior() -> void:
	var v := ""
	var sw := _main.get_node("Zones/Apartment/Props/Wardrobe") as ABSwitch
	if sw:
		for candidate in ["A", "B"]:
			if sw.get_node(candidate).has_node("Rail"):
				v = candidate
	var w := _piece("Wardrobe", v)
	if not w.has_node("Rail"):
		_check("wardrobe_interior", false, "the wardrobe has no interior (rail, drawers)")
		return
	await _frames(30)
	var space := _main.get_world_3d().direct_space_state

	# Doors open so the drawers can come out.
	for side in ["Left", "Right"]:
		var hinge: XRToolsInteractableHinge = w.get_node("Door%s/HingeOrigin/InteractableHinge" % side)
		hinge.hinge_position = 95.0
		hinge.hinge_moved.emit(95.0)
	await _frames(3)
	for drawer_node in w.get_children().filter(func(n: Node) -> bool: return n.name.begins_with("Drawer")):
		var side := (drawer_node.name as String).trim_prefix("Drawer")
		var slider: XRToolsInteractableSlider = drawer_node.get_node("SliderOrigin/InteractableSlider")
		var body: PhysicsBody3D = drawer_node.get_node("SliderOrigin/InteractableSlider/Leaf/DrawerBody")
		var q := PhysicsPointQueryParameters3D.new()
		q.position = body.to_global(Vector3(0, 0.12, -0.009))
		var front_at := q.position
		slider.move_slider(0.3)
		await _frames(3)
		q.position = front_at
		var still_there := space.intersect_point(q).any(func(hit: Dictionary) -> bool: return hit.collider == body)
		q.position = front_at + w.global_basis.z * 0.3
		var moved_there := space.intersect_point(q).any(func(hit: Dictionary) -> bool: return hit.collider == body)
		slider.move_slider(0.0)
		await _frames(2)
		_check("wardrobe_drawer_%s" % side.to_lower(), not still_there and moved_there,
				"drawer front collision: left the closed spot %s, followed to 0.3 m %s" % [not still_there, moved_there])

	var rail: HangingRail = w.get_node("Rail")
	var hook_y := rail.start.y + rail.radius
	var hangers := w.get_children().filter(func(n: Node) -> bool: return n is XRToolsPickable and n.has_node("RailHanger"))
	var hung := 0
	for i in hangers.size():
		var hanger: XRToolsPickable = w.get_node("Hanger%d" % i)
		var hook := w.to_local(hanger.global_position)
		if hanger.freeze and absf(hook.y - hook_y) < 0.005 and absf(hook.z - rail.start.z) < 0.005:
			hung += 1
	_check("wardrobe_hangers_hung", hung == hangers.size() and hung > 0, "%d of %d hangers hang on the rail" % [hung, hangers.size()])

	var hanger0: XRToolsPickable = w.get_node("Hanger0")
	var rail_hanger: RailHanger = hanger0.get_node("RailHanger")
	hanger0.freeze = false
	hanger0.global_position = w.to_global(Vector3(rail.start.x + 0.2, hook_y - 0.04, 0.05))
	hanger0.dropped.emit(hanger0)
	await _frames(2)
	var rehung := rail_hanger.is_hung() and absf(w.to_local(hanger0.global_position).y - hook_y) < 0.005
	hanger0.freeze = false
	hanger0.global_position = w.to_global(Vector3(0.1, 1.2, 0.5))
	hanger0.dropped.emit(hanger0)
	await _frames(30)
	var fell := not hanger0.freeze and w.to_local(hanger0.global_position).y < 1.15
	_check("wardrobe_rehang", rehung and fell, "dropped near the rail hangs %s, dropped away from it falls %s" % [rehung, fell])

	var box: Node3D = w.get_node("StorageBox")
	var lid: Node3D = w.get_node("StorageBoxLid")
	var box_y := w.to_local(box.global_position).y
	var lid_above := w.to_local(lid.global_position).y - box_y
	var wall: CollisionShape3D = box.get_node("WallLeft")
	var rim := wall.position.y + (wall.shape as BoxShape3D).size.y / 2.0
	var skirt := ((lid.get_node("SkirtLeft") as CollisionShape3D).shape as BoxShape3D).size.y
	var expect_lid := rim - skirt
	_check("wardrobe_box_and_lid", absf(lid_above - expect_lid) < 0.012 and (box as RigidBody3D).linear_velocity.length() < 0.05,
			"box resting at %.3f, lid %.3f above it (skirt over the rim: %.3f)" % [box_y, lid_above, expect_lid])
	for side in ["Left", "Right"]:
		var hinge: XRToolsInteractableHinge = w.get_node("Door%s/HingeOrigin/InteractableHinge" % side)
		hinge.hinge_position = 0.0
		hinge.hinge_moved.emit(0.0)
