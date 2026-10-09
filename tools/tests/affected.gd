extends RefCounted
## --affected[=<rev>] for the interaction suite: the files changed since <rev>
## (default HEAD: staged, unstaged and untracked) pick the tests to run.
##
## A path picks the groups of every RULES entry one of its globs matches
## (String.match: * spans folders); "*" is every group, [] nothing to run
## (docs, looks, perf, Blender sources), "skyline" the other suite (a hint).
## A path no rule matches runs everything: add a rule when that happens.
## The runner itself (interaction_tests.gd) picks tests by its diff: a changed
## test, a new registry line, or a changed helper, const or class picks the
## tests that use it.

const RUNNER := "tools/tests/interaction_tests.gd"
const ALL := ["*"]

const RULES := [
	# Nothing to run: words, looks (--shots), perf, sources of generated files.
	[["docs/*", "*.md", "LICENSE", "icon.svg", ".*", "*.import", "*.uid", "blender/*",
			"tools/perf/*", "tools/shots/*", "tools/audio/*", "tools/bake_gi.gd",
			"assets/materials/*", "assets/audio/*", "assets/shaders/world_surface*",
			"assets/architecture/skirting/*", "tools/blockout/*skirting*", "tools/tests/affected.gd"], []],
	# The whole scene: everything.
	[["main.gd", "main.tscn", "project.godot", "addons/*", "tools/props/prop_scenes.py",
			"zones/apartment/*", "tools/blockout/apartment.py"], ALL],
	[["openxr_action_map.tres"], ["player", "avatar", "world"]],

	# Player
	[["core/player/player*", "core/player/stick_sprint.gd"], ["player", "avatar"]],
	[["core/player/grab_ray.gd", "core/interaction/ray_buttons.gd"], ["player", "world"]],
	[["core/player/avatar/*", "tools/player/*", "assets/characters/*"], ["avatar"]],
	[["core/player/hands/*"], ["avatar", "player", "doors_fridge", "switches"]],

	# Interaction components, by the props that use them
	[["core/interaction/hinge_swing.gd", "core/interaction/hinge_stop_sound.gd",
			"core/interaction/kinematic_follower.gd", "core/interaction/hinge_body_blocker.gd",
			"core/interaction/grab_pass_through.gd"],
			["player", "doors_fridge", "furniture", "variants", "wardrobe", "windows", "bathroom"]],
	[["core/interaction/hinge_hand_push.gd"], ["player", "doors_fridge", "furniture", "wardrobe"]],
	[["core/interaction/hinge_detents.gd"], ["player", "doors_fridge", "bathroom"]],
	[["core/interaction/hinge_light.gd", "core/interaction/open_alarm.gd"], ["doors_fridge"]],
	[["core/interaction/door_lock.gd"], ["doors_fridge", "zones"]],
	[["core/interaction/hinge_coupling.gd", "core/interaction/holder_snap.gd",
			"core/interaction/press_sound.gd", "core/interaction/shower_*"], ["bathroom"]],
	[["core/interaction/hinge_ambience.gd"], ["windows", "world", "zones"]],
	[["core/interaction/slider_swing.gd"], ["furniture", "variants", "wardrobe", "bathroom"]],
	[["core/interaction/hanging_rail.gd", "core/interaction/rail_hanger.gd"], ["wardrobe"]],
	[["core/interaction/light_switch.gd", "core/interaction/emissive_materials.gd"],
			["switches", "doors_fridge", "bathroom"]],
	[["core/interaction/named_material_override.gd"], ["windows", "bathroom", "switches"]],
	[["core/interaction/grab_highlight.gd", "core/interaction/impact_sound.gd",
			"core/interaction/trash_receiver.gd"],
			["player", "furniture", "variants", "wardrobe", "bathroom"]],
	[["core/interaction/seat.gd"], ["furniture", "variants", "avatar", "bathroom"]],
	[["core/interaction/motorized_shade.gd", "core/interaction/smart_glass.gd",
			"core/interaction/window_hud.gd", "core/interaction/window_light.gd"], ["windows", "world"]],

	# Rendering, debug, world, weather, zones
	[["core/rendering/foveation.gd", "core/debug/ab_viewport.gd"], ["rendering"]],
	[["core/rendering/door_viewer.gd", "assets/shaders/door_viewer.gdshader"], ["rendering", "zones"]],
	[["core/rendering/planar_reflection.gd", "assets/shaders/planar_*"],
			["rendering", "bathroom", "windows", "avatar", "zones"]],
	[["core/debug/*"], ["switches"]],
	[["core/weather/*", "assets/shaders/window_glass*"], ["windows", "world", "zones"]],
	[["core/world_state/*", "assets/shaders/hologram_tile.gdshader", "assets/props/world_terminal/*",
			"zones/skyline/skyline.tscn"], ["world", "windows"]],
	[["core/zones/*", "core/signage/*", "zones/zone_graph.json", "zones/corridor/*", "zones/units/*",
			"tools/blockout/blockout.py", "tools/blockout/corridor*", "tools/blockout/units.py",
			"tools/tests/zones/*", "assets/architecture/corridor/*", "assets/shaders/holo_sign.gdshader",
			"assets/shaders/guide_light.gdshader", "tools/props/door_neighbor.py"], ["zones"]],
	[["core/zones/outside_view.gd", "zones/skyline/*", "tools/city/*", "tools/props/city.py",
			"tools/props/traffic.py", "assets/architecture/city/*", "assets/props/traffic/*",
			"assets/shaders/skyline_facade.gdshader", "assets/shaders/traffic_*",
			"tools/tests/skyline_tests.gd"], ["skyline"]],

	# Props (the scene, its generator definition, its glbs)
	[["assets/props/fridge/*", "tools/props/fridge.py"], ["doors_fridge"]],
	[["assets/props/door_interior/*", "tools/props/door_interior.py"], ["doors_fridge", "player"]],
	[["assets/props/door_entrance/*", "tools/props/door_entrance.py"],
			["doors_fridge", "player", "rendering", "zones"]],
	[["assets/props/sofa/*", "tools/props/sofa.py", "assets/props/bed/*", "tools/props/bed.py"],
			["furniture", "variants"]],
	[["assets/props/nightstand/*", "tools/props/nightstand.py"], ["furniture", "variants", "switches"]],
	[["assets/props/wardrobe/*", "tools/props/wardrobe.py"], ["wardrobe", "furniture", "variants"]],
	[["assets/props/toilet/*", "assets/props/vanity/*", "assets/props/shower/*", "assets/props/bath_mirror*",
			"tools/props/toilet.py", "tools/props/vanity.py", "tools/props/shower.py",
			"tools/props/bath_mirror.py", "assets/shaders/shower_glass.gdshader",
			"assets/shaders/hose_braid.gdshader"], ["bathroom"]],
	[["assets/props/bath_mirror/*", "tools/props/bath_mirror.py"], ["avatar"]],
	[["assets/props/ab_panel/*"], ["switches"]],
	[["assets/props/ball/*", "assets/props/beverage_can/*", "assets/props/trash_can/*",
			"assets/shaders/grab_highlight.gdshader"], ["player", "furniture", "doors_fridge"]],
	[["assets/architecture/windows/*", "tools/props/window.py", "tools/props/windows/*"], ["windows", "world"]],
]

# Top-level declarations in the runner's source: what a diff hunk changed.
const _DECL := "^(?:static )?(?:func|const|var|class) ([A-Za-z_]\\w*)"
# Functions that call everything (the runner): their callees aren't tests to run.
const _RUNNER_ONLY := ["_registry", "_ready", "_select", "_print_list"]


## The tests (registry entries, in order) the changes since `rev` touch;
## prints which file picked what. Empty when nothing is affected.
static func select(tests: Array[Array], rev: String, root: String) -> Array[Array]:
	var known: Array[String] = []
	for test in tests:
		if not known.has(test[0]):
			known.append(test[0])
	var files := _git(root, ["diff", "--name-only", rev])
	files.append_array(_git(root, ["ls-files", "--others", "--exclude-standard"]))
	var groups: Array[String] = []
	var methods: Array[String] = []
	var names: Array[String] = []
	var skyline := false
	print("TEST AFFECTED since %s: %d file(s)" % [rev, files.size()])
	for path in files:
		if path == RUNNER:
			var changed := _changed_in_runner(root, rev, names)
			methods.append_array(_users(root.path_join(RUNNER), changed))
			print("  %s -> tests using %s" % [path, ", ".join(changed) if not changed.is_empty() else "(nothing)"])
			continue
		var picked: Array[String] = []
		var matched := false
		for rule: Array in RULES:
			for glob: String in rule[0]:
				if path.match(glob):
					matched = true
					for group: String in rule[1]:
						if not picked.has(group):
							picked.append(group)
					break
		if not matched:
			picked = ["*"]
		print("  %s -> %s%s" % [path, ", ".join(picked) if not picked.is_empty() else "(nothing)",
				"" if matched else " (no rule in tools/tests/affected.gd: everything)"])
		for group in picked:
			if group == "skyline":
				skyline = true
			elif group == "*":
				groups.assign(known)
			elif not known.has(group):
				push_error("TEST: affected.gd names an unknown group '%s'" % group)
			elif not groups.has(group):
				groups.append(group)
	if skyline:
		print("TEST AFFECTED: also run --test=skyline")
	return tests.filter(func(test: Array) -> bool:
		return groups.has(test[0]) or names.has(test[1]) or methods.has((test[2] as Callable).get_method()))


static func _git(root: String, args: Array[String]) -> Array[String]:
	var output: Array = []
	var full: Array[String] = ["-C", root]
	full.append_array(args)
	# stdout only: git's warnings (line endings) would read as file names.
	if OS.execute("git", full, output) != 0:
		push_error("TEST: git %s failed (is <rev> a commit?)" % " ".join(args))
		return []
	var lines: Array[String] = []
	for line in ("".join(output) as String).split("\n", false):
		lines.append(line.strip_edges())
	return lines


## The runner's top-level functions, consts and classes the diff touches (by
## the hunk headers and added or removed declarations); test names on new
## registry lines go into `names`.
static func _changed_in_runner(root: String, rev: String, names: Array[String]) -> Array[String]:
	var decl := RegEx.create_from_string(_DECL)
	var hunk := RegEx.create_from_string("^@@ [^@]* @@ (.*)$")
	var entry := RegEx.create_from_string("^\\+\\s*\\[\"\\w+\", \"(\\w+)\"")
	var changed: Array[String] = []
	# The declaration a changed indented line belongs to: the hunk header's, or
	# one the hunk declares (lines added after a function aren't its body).
	var enclosing := ""
	for line in _git(root, ["diff", "-U0", rev, "--", RUNNER]):
		var m := hunk.search(line)
		if m:
			var header := decl.search(m.get_string(1))
			enclosing = header.get_string(1) if header else ""
			continue
		if not (line.begins_with("+") or line.begins_with("-")) or line.begins_with("+++") or line.begins_with("---"):
			continue
		var text := line.substr(1)
		var e := entry.search(line)
		if e and not names.has(e.get_string(1)):
			names.append(e.get_string(1))
		var name := ""
		var d := decl.search(text)
		if d:
			name = d.get_string(1)
			enclosing = name
		elif text.begins_with("\t") and enclosing != "":
			name = enclosing
		if name != "" and not changed.has(name) and not _RUNNER_ONLY.has(name):
			changed.append(name)
	return changed


## Every top-level function that reaches one of `changed` (itself included),
## following calls and references through the runner's source.
static func _users(path: String, changed: Array[String]) -> Array[String]:
	var decl := RegEx.create_from_string(_DECL)
	var bodies := {}
	var current := ""
	for line in FileAccess.get_file_as_string(path).split("\n"):
		var d := decl.search(line)
		if d:
			current = d.get_string(1)
			bodies[current] = ""
		elif current != "" and not line.is_empty() and not line.begins_with("\t") and not line.begins_with("#"):
			current = ""
		if current != "":
			bodies[current] += line + "\n"
	var reached: Array[String] = changed.duplicate()
	var words: Array[RegEx] = []
	for name in reached:
		words.append(RegEx.create_from_string("\\b%s\\b" % name))
	var grew := true
	while grew:
		grew = false
		for fn: String in bodies:
			if reached.has(fn) or _RUNNER_ONLY.has(fn):
				continue
			for word in words:
				if word.search(bodies[fn]):
					reached.append(fn)
					words.append(RegEx.create_from_string("\\b%s\\b" % fn))
					grew = true
					break
	return reached
