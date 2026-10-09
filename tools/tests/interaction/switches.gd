extends "res://tools/tests/interaction/base.gd"
## Switches group: the A/B panel and environment A/B, the nightstand lamp switches.


## The group's tests in run order: [name, coroutine]. Adding a test is
## one line here.
func tests() -> Array[Array]:
	return [
		["ab_panel", _test_ab_panel],
		["ab_environment", _test_ab_environment],
		["ab_panel_has_switches", _test_ab_panel_has_switches],
		["lamp_switch", _test_lamp_switches],
	]


## The A/B panel: a fingertip pressing its button flips an ABSwitch (and the
## hidden variant is disabled); a second press flips back. Built away from the
## apartment, so it runs with or without A/B pairs placed.
## An ABPanel in the zone has something to flip: a panel without any ABSwitch
## clicks but stays on "A" (the first viewport A/B was generated that way).
func _test_ab_panel_has_switches() -> void:
	var zones := _main.get_node("Zones")
	var panels := 0
	var switches := 0
	for node in zones.find_children("*", "Node3D", true, false):
		if node is ABPanel:
			panels += 1
		elif node is ABSwitch:
			switches += 1
	_check("ab_panel_has_switches", panels == 0 or switches > 0, "%d panel(s), %d switch(es)" % [panels, switches])


func _test_ab_panel() -> void:
	var sw := ABSwitch.new()
	for name in ["A", "B"]:
		var body := StaticBody3D.new()
		body.name = name
		var shape := CollisionShape3D.new()
		shape.shape = BoxShape3D.new()
		body.add_child(shape)
		sw.add_child(body)
	_main.add_child(sw)
	sw.global_position = Vector3(40, 1, 40)
	var panel: Node3D = (load("res://assets/props/ab_panel/ab_panel.tscn") as PackedScene).instantiate()
	_main.add_child(panel)
	panel.global_position = Vector3(40, 1.25, 44)
	var hand := _dummy_fingertip()
	var away := panel.to_global(Vector3(0, -0.04, 0.3))
	var press := panel.to_global(Vector3(0, -0.04, 0.05))
	hand.global_position = away
	await _frames(3)
	var before := sw.variant
	hand.global_position = press
	await _frames(5)
	var first := sw.variant
	var old_disabled := sw.get_node(before).process_mode == Node.PROCESS_MODE_DISABLED
	hand.global_position = away
	await _frames(5)
	hand.global_position = press
	await _frames(5)
	var second := sw.variant
	for node: Node in [hand, panel, sw]:
		node.queue_free()
	_check("ab_panel_press", first != before and second == before and old_disabled,
			"variant before %s, after one press %s (old one disabled %s), after a second press %s" % [before, first, old_disabled, second])


## An Environment A/B: flipping every switch applies the other variant's
## properties to the world's environment; flipping back restores them.
func _test_ab_environment() -> void:
	var env: Environment = (_main.get_node("Skyline/WorldEnvironment") as WorldEnvironment).environment
	var sw := ABEnvironment.new()
	sw.a = {"ssr_enabled": false, "ssr_max_steps": 64.0}
	sw.b = {"ssr_enabled": true, "ssr_max_steps": 8.0}
	_main.add_child(sw)
	var on_a := not env.ssr_enabled and env.ssr_max_steps == 64
	ABSwitch.toggle_all(get_tree())
	var on_b := env.ssr_enabled and env.ssr_max_steps == 8 and sw.variant == "B"
	ABSwitch.toggle_all(get_tree())
	var back := not env.ssr_enabled and env.ssr_max_steps == 64 and sw.variant == "A"
	sw.free()
	_check("ab_environment", on_a and on_b and back,
			"A applied %s, B applied %s, back to A %s" % [on_a, on_b, back])


func _test_lamp_switches() -> void:
	for variant in _variants("Nightstand"):
		await _test_lamp_switch(variant)


## Pressing the lamp's switch turns its light and glow off, pressing again on.
func _test_lamp_switch(v: String) -> void:
	var stand := _piece("Nightstand", v)
	await _frames(3)
	var button: Node3D = stand.get_node("LampSwitchButton")
	var light: Light3D = stand.get_node("LampLight")
	var tip := _dummy_fingertip()
	var away := button.global_position + Vector3(0, 0.2, 0)
	tip.global_position = away
	await _frames(3)
	var before := light.visible
	tip.global_position = button.global_position
	await _frames(4)
	var after_one := light.visible
	tip.global_position = away
	await _frames(4)
	tip.global_position = button.global_position
	await _frames(4)
	var after_two := light.visible
	tip.queue_free()
	_check("lamp%s_switch" % _suffix(v), before and not after_one and after_two,
			"lamp light: before %s, after one press %s, after two %s" % [before, after_one, after_two])
