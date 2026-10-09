extends "res://tools/tests/interaction/base.gd"
## Furniture group: sofa, bedroom (bed, nightstands, wardrobe doors), bedding collision.


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["sofa", _test_sofa],
		["bedroom", _test_bedrooms],
		["bed_bedding", _test_bed_bedding_collision],
	]


## A can dropped on the middle seat rests on the seat surface (0.44 m), and the
## throw pillows have settled on the sofa, not on the floor.
func _test_sofa() -> void:
	var root: Node3D = _main.get_node("Zones/Apartment/Props/Sofa")
	var local := await _drop_can_on_seat(root)
	_check("sofa_can_on_seat", absf(local.y - 0.50) < 0.05,
			"can center at local y %.2f (seat 0.44 + half can)" % local.y)
	var settled: Array[String] = []
	var ok := true
	for i in [1, 2]:
		var pillow: RigidBody3D = _main.get_node("Zones/Apartment/Props/SofaPillow%d" % i)
		var p := root.to_local(pillow.global_position)
		ok = ok and p.y > 0.45 and absf(p.x) < 1.05 and absf(p.z) < 0.5 and pillow.linear_velocity.length() < 0.05
		settled.append("%s at %s" % [pillow.name, p.snappedf(0.01)])
	_check("sofa_pillows_settled", ok, ", ".join(settled))


func _test_bedrooms() -> void:
	for variant in _variants("Bed"):
		await _test_bedroom(variant)


## Bedroom set (bed, wardrobe, nightstand), for variant `v` of an A/B pair or
## the placed pieces: the hidden variant has no collision, a can rests on the
## bed, the wardrobe doors' collision follows them, and the nightstand drawer
## slides, slides on after release, soft-closes and holds a can.
func _test_bedroom(v: String) -> void:
	var bed := _piece("Bed", v)
	await _frames(3)
	var space := _main.get_world_3d().direct_space_state
	var sw := _main.get_node("Zones/Apartment/Props/Bed") as ABSwitch
	if sw:
		# Only the shown bed collides.
		var hidden: Node3D = sw.get_node("B" if v == "A" else "A")
		var probe := PhysicsPointQueryParameters3D.new()
		probe.position = bed.to_global(Vector3(0, 0.25, 0.2))
		var owners: Array[String] = []
		for hit in space.intersect_point(probe):
			var collider := hit.collider as Node
			owners.append("shown" if bed.is_ancestor_of(collider) else ("hidden" if hidden.is_ancestor_of(collider) else collider.name))
		_check("bed%s_only_shown_collides" % _suffix(v), owners.has("shown") and not owners.has("hidden"), "colliders at the bed center: %s" % [owners])
	var q := PhysicsPointQueryParameters3D.new()

	var local := await _drop_can_on_seat(bed)
	_check("bed%s_can_on_bed" % _suffix(v), absf(local.y - 0.56) < 0.05, "can center at local y %.2f (sleeping surface 0.50 + half can)" % local.y)

	# Wardrobe doors: collision in front of the closed doors follows them.
	var wardrobe := _piece("Wardrobe", v)
	for side in ["Left", "Right"]:
		var hinge: XRToolsInteractableHinge = wardrobe.get_node("Door%s/HingeOrigin/InteractableHinge" % side)
		var body: PhysicsBody3D = wardrobe.get_node("Door%s/HingeOrigin/InteractableHinge/Leaf/DoorBody" % side)
		q.position = wardrobe.to_global(Vector3(-0.4 if side == "Left" else 0.4, 1.0, 0.31))
		var hits_door := func() -> bool:
			return space.intersect_point(q).any(func(hit: Dictionary) -> bool: return hit.collider == body)
		var closed: bool = hits_door.call()
		hinge.hinge_position = 90.0
		hinge.hinge_moved.emit(90.0)
		await _frames(3)
		var opened: bool = hits_door.call()
		hinge.hinge_position = 0.0
		hinge.hinge_moved.emit(0.0)
		await _frames(2)
		_check("wardrobe%s_door_%s" % [_suffix(v), side.to_lower()], closed and not opened, "door body in front of the carcass: closed %s, open %s" % [closed, opened])

	# Nightstand drawer.
	var stand := _piece("Nightstand", v)
	var slider: XRToolsInteractableSlider = stand.get_node("Drawer/SliderOrigin/InteractableSlider")
	var drawer: PhysicsBody3D = stand.get_node("Drawer/SliderOrigin/InteractableSlider/Leaf/DrawerBody")
	var swing: SliderSwing = stand.get_node("Drawer/Swing")
	q.position = stand.to_global(Vector3(0, 0.45, 0.19))
	var drawer_hit := func() -> bool:
		return space.intersect_point(q).any(func(hit: Dictionary) -> bool: return hit.collider == drawer)
	var closed_hit: bool = drawer_hit.call()
	slider.move_slider(0.25)
	await _frames(3)
	var open_hit: bool = drawer_hit.call()
	_check("nightstand%s_drawer_collision" % _suffix(v), closed_hit and not open_hit, "drawer front at the closed spot: closed %s, open %s" % [closed_hit, open_hit])

	var can: RigidBody3D = (load(CAN_SCENE) as PackedScene).instantiate()
	_main.add_child(can)
	can.global_position = drawer.to_global(Vector3(0, 0.12, -0.19))
	await _frames(120)
	var in_drawer := drawer.to_local(can.global_position)
	can.queue_free()
	_check("nightstand%s_can_in_drawer" % _suffix(v), in_drawer.y > 0.0 and in_drawer.y < 0.12 and in_drawer.z < -0.03 and in_drawer.z > -0.36,
			"can at drawer-local %s" % in_drawer.snappedf(0.01))

	# Pushed shut at 0.6 m/s from 0.25 m it slides on and closes; a slow
	# release at 1 cm soft-closes; pulled out at 0.4 m/s it slides on.
	slider.move_slider(0.10)
	slider.grabbed.emit(slider)
	for i in 10:
		await get_tree().physics_frame
		slider.move_slider(0.10 + 0.4 * (i + 1) * _step())
	var released_at := slider.slider_position
	slider.released.emit(slider)
	await _frames(120)
	var coasted := slider.slider_position
	slider.move_slider(0.01)
	slider.released.emit(slider)
	await _frames(90)
	var soft_closed := slider.slider_position
	_check("nightstand%s_drawer_swing" % _suffix(v), coasted > released_at + 0.02 and swing.get_velocity() == 0.0 and soft_closed < 0.001,
			"released at %.3f m going 0.4 m/s, rested at %.3f m; let go at 1 cm, ended at %.4f m" % [released_at, coasted, soft_closed])


## The bed's collision follows the bedding: a small sphere swept down onto a
## pillow stops on the pillow (about 0.58-0.72 m), not on the hidden block
## (0.44 m) under the duvet. (A dropped can tips off the sloped pillow and
## rolls onto the sheet, which is fine.)
func _test_bed_bedding_collision() -> void:
	var bed := _piece("Bed")
	var space := _main.get_world_3d().direct_space_state
	var sphere := SphereShape3D.new()
	sphere.radius = 0.03
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = sphere
	query.collision_mask = 1
	var heights: Array[String] = []
	var ok := true
	for spot: Vector3 in [Vector3(0.4, 1.2, -0.7), Vector3(-0.4, 1.2, -0.7)]:
		query.transform = Transform3D(Basis.IDENTITY, bed.to_global(spot))
		query.motion = Vector3(0, -1.0, 0)
		var fraction := space.cast_motion(query)[0]
		var rest_y: float = spot.y - 1.0 * fraction - sphere.radius
		ok = ok and rest_y > 0.55
		heights.append("%.2f" % rest_y)
	_check("bed_pillow_collision", ok, "sphere stops at local y %s over the pillows (hidden block at 0.44)" % ", ".join(heights))
