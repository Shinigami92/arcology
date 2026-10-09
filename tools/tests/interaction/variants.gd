extends "res://tools/tests/interaction/base.gd"
## Variants group: the spare props (A/B runners-up) placed and checked like the originals.


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["spare_sofa", _test_spare_sofa],
		["spare_variants", _test_spare_variants],
	]


## The spare boucle sofa (kept for other apartments) isn't placed anywhere:
## spawn it away from the apartment and check its seat collision.
func _test_spare_sofa() -> void:
	var sofa: Node3D = (load("res://assets/props/sofa/sofa_boucle.tscn") as PackedScene).instantiate()
	_main.add_child(sofa)
	sofa.global_position = Vector3(30, 0, 30)
	await _frames(2)
	var local := await _drop_can_on_seat(sofa)
	sofa.queue_free()
	_check("sofa_boucle_can_on_seat", absf(local.y - 0.50) < 0.05,
			"can center at local y %.2f (seat 0.44 + half can)" % local.y)


## The runner-up variants kept for other apartments load, and their static
## collision works (spawned away from the apartment).
func _test_spare_variants() -> void:
	var results: Array[String] = []
	var ok := true
	for path in ["res://assets/props/bed/bed_padded.tscn", "res://assets/props/wardrobe/wardrobe_lit.tscn",
			"res://assets/props/nightstand/nightstand_square.tscn"]:
		var scene := load(path) as PackedScene
		if not scene:
			ok = false
			results.append("%s: failed to load" % path.get_file())
			continue
		var node: Node3D = scene.instantiate()
		_main.add_child(node)
		node.global_position = Vector3(-30, 0, -30)
		await _frames(2)
		# A can dropped on top lands on its collision, not on the ground.
		var top := 0.50 if path.contains("bed") else (2.10 if path.contains("wardrobe") else 0.55)
		var can: RigidBody3D = (load(CAN_SCENE) as PackedScene).instantiate()
		_main.add_child(can)
		can.global_position = node.to_global(Vector3(0.1, top + 0.3, 0.1))
		await _frames(120)
		var y := node.to_local(can.global_position).y
		can.queue_free()
		node.queue_free()
		var landed := absf(y - top - 0.06) < 0.08
		ok = ok and landed
		results.append("%s can at %.2f (top %.2f)" % [path.get_file().get_basename(), y, top])
	_check("spare_variants", ok, ", ".join(results))
