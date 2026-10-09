extends "res://tools/tests/interaction/base.gd"
## Interaction tests on the real main scene (desktop, no XR). Started by
## main.gd:
##
##   "$GODOT4_EDITOR" --path . --xr-mode off --fixed-fps 90 -- --test=interaction
##
## Prints one line per check ("TEST PASS/FAIL <name>: <details>") and quits
## with the number of failures (2 for a bad --only or a group that doesn't
## load). Runs through main.gd (not --script) so the XR Tools autoloads exist.
## --fixed-fps 90 (an engine option, before "--") steps 1/90 s per frame as fast
## as the machine renders: tests wait in frames and engine time, never the wall
## clock, so they hold.
##
## The tests live in interaction/<group>.gd, one file per group (GROUPS, in run
## order), each listing its tests in tests(); shared helpers in interaction/base.gd.
## Subsets:
##   --only=<a,b>   groups, or tests whose name contains the word
##                  (--only=avatar, --only=doors_fridge,windows, --only=arm_ik)
##   --affected[=<rev>]  the groups the changes since <rev> touch (default HEAD:
##                  staged, unstaged, untracked; tools/tests/affected.gd)
##   --list         print the groups and their tests (or the picked ones), run nothing
## Before each test the rig is put back (nothing held, pickups at their hands,
## player at HOME), so a test or group run alone sees what it sees in a full run.

## The groups in run order; each is interaction/<group>.gd.
const GROUPS: Array[String] = ["player", "doors_fridge", "rendering", "furniture", "variants", "switches",
		"avatar", "wardrobe", "windows", "world", "bathroom", "zones"]
const Affected := preload("res://tools/tests/affected.gd")

var _failures := 0
# The pickups' transforms at the start; restored before each test.
var _pickup_rest: Array[Transform3D] = []


## Every test in run order: [group, name, coroutine], from each group's
## tests(). The groups become children of the runner, so they share its tree.
## Empty if a group doesn't load (a parse error).
func _registry() -> Array[Array]:
	var tests: Array[Array] = []
	for group in GROUPS:
		var script := load("res://tools/tests/interaction/%s.gd" % group) as GDScript
		if not script or not script.can_instantiate():
			push_error("TEST: group '%s' failed to load (see the parse error above)" % group)
			return []
		var suite: Node = script.new()
		suite.name = group
		suite.set("_main", _main)
		suite.connect("checked", _on_checked)
		add_child(suite)
		for entry: Array in suite.call("tests"):
			tests.append([group, entry[0], entry[1]])
	return tests


func _ready() -> void:
	_main = get_parent() as Node3D
	var tests := _registry()
	if tests.is_empty():
		get_tree().quit(2)
		return
	var args := OS.get_cmdline_user_args()
	var only: PackedStringArray = []
	var subset := ""
	for arg in args:
		if arg.begins_with("--only="):
			only = arg.trim_prefix("--only=").split(",", false)
			subset = arg
		elif arg == "--affected" or arg.begins_with("--affected="):
			subset = arg
	if not only.is_empty():
		tests = _select(tests, only)
		if tests.is_empty():
			get_tree().quit(2)
			return
	elif subset != "":
		var rev := subset.trim_prefix("--affected").trim_prefix("=")
		tests = Affected.select(tests, rev if rev != "" else "HEAD", ProjectSettings.globalize_path("res://"))
		if tests.is_empty():
			print("TEST AFFECTED: nothing to run")
			print("TEST DONE: 0 failure(s)")
			get_tree().quit(0)
			return
	if args.has("--list"):
		_print_list(tests)
		get_tree().quit(0)
		return
	if subset != "":
		var names: Array[String] = []
		for test in tests:
			names.append(test[1])
		print("TEST ONLY %s: %s" % [subset.trim_prefix("--").trim_prefix("only="), ", ".join(names)])

	await _frames(30)
	for side in SIDES:
		_pickup_rest.append((_main.get_node("Player/%sHand/CollisionHand/FunctionPickup" % side) as Node3D).transform)
	var run_start := Time.get_ticks_msec()
	var engine_start := Engine.get_physics_frames()
	var group_ms := {}
	for test in tests:
		var start := Time.get_ticks_msec()
		await _reset_rig()
		await (test[2] as Callable).call()
		group_ms[test[0]] = group_ms.get(test[0], 0) + Time.get_ticks_msec() - start
	var ran: Array[String] = []
	for group: String in group_ms:
		ran.append("%s %.1f s" % [group, group_ms[group] / 1000.0])
	print("TEST GROUPS: %s%s" % [", ".join(ran), "" if subset == "" else " (%s)" % subset])
	var wall := (Time.get_ticks_msec() - run_start) / 1000.0
	var engine := float(Engine.get_physics_frames() - engine_start) / Engine.physics_ticks_per_second
	print("TEST TIME: %.1f s for %.1f s of engine time%s" % [wall, engine,
			" (add --fixed-fps 90 before -- to run faster)" if engine > 10.0 and wall > 0.8 * engine else ""])
	print("TEST DONE: %d failure(s)" % _failures)
	get_tree().quit(_failures)


## The tests a --only list picks: a token is a group name, or else part of a
## test's name. An unknown token prints the choices and returns nothing.
func _select(tests: Array[Array], only: PackedStringArray) -> Array[Array]:
	var groups: Array[String] = []
	for test in tests:
		if not groups.has(test[0]):
			groups.append(test[0])
	var picked: Array[Array] = []
	var unknown: Array[String] = []
	for token in only:
		var hit := false
		for test in tests:
			if test[0] == token or (not groups.has(token) and (test[1] as String).contains(token)):
				hit = true
				if not picked.has(test):
					picked.append(test)
		if not hit:
			unknown.append(token)
	if not unknown.is_empty():
		push_error("TEST: no group or test matches %s (groups: %s; --list shows the tests)" % [
				", ".join(unknown), ", ".join(groups)])
		return []
	# Keep the registry order.
	return tests.filter(func(test: Array) -> bool: return picked.has(test))


func _print_list(tests: Array[Array]) -> void:
	var by_group := {}
	for test in tests:
		if not by_group.has(test[0]):
			by_group[test[0]] = []
		(by_group[test[0]] as Array).append(test[1])
	print("TEST LIST: %d tests in %d groups (--only=<group or part of a test name>,...)" % [tests.size(), by_group.size()])
	for group: String in by_group:
		var names: Array = by_group[group]
		print("  %s (%d): %s" % [group, names.size(), ", ".join(names)])


## Puts the rig back: nothing held, pickups at their hands, the player body at
## HOME (waits only if it had moved; at the start the body stands 0.1 m off it).
func _reset_rig() -> void:
	for i in SIDES.size():
		var pickup: XRToolsFunctionPickup = _main.get_node("Player/%sHand/CollisionHand/FunctionPickup" % SIDES[i])
		if pickup.picked_up_object:
			pickup.drop_object()
		pickup.transform = _pickup_rest[i]
	var body: XRToolsPlayerBody = _main.get_node("Player/PlayerBody")
	if body.global_position.distance_to(HOME.origin) > 0.05 or body.global_basis.z.dot(HOME.basis.z) < 0.999:
		body.teleport(HOME)
		await _frames(30)


func _on_checked(ok: bool) -> void:
	if not ok:
		_failures += 1
