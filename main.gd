extends Node3D
## Entry scene: starts XR, loads the world backdrop and the first zone, and
## places the player at the zone's entry marker.
##
## Zone streaming (core/zones) replaces the static zone instance in M3.
## Command-line user args (after "--"):
##   --perf=<zone>        run the perf flythrough for that zone and quit
##   --perf-duration=<s>  flythrough length in seconds (default 20)
##   --perf-hide=<a,b>    zone-relative node paths to hide (A/B cost tests)
##   --test=<suite>       run tools/tests/<suite>_tests.gd and quit with the failure count
##   --shots=<views>      render still images and quit (see tools/shots/shots.gd)
##   --rain=<0..1>        start with rain on the glass (wet at once; RainOnGlass)
##   --rain-delay=<s>     with --rain: start dry and let the rain set in after s seconds

const PERF_SCRIPT := "res://tools/perf/perf_flythrough.gd"
const SHOTS_SCRIPT := "res://tools/shots/shots.gd"

## Entry marker path inside the zone to spawn at.
@export var entry := NodePath("Zones/Apartment/Entries/Default")

@onready var _player: ArcologyPlayer = $Player


func _ready() -> void:
	var marker := get_node_or_null(entry) as Node3D
	if marker:
		_player.global_transform = marker.global_transform
	else:
		push_warning("Entry marker not found: %s" % entry)

	var args := _user_args()
	if args.has("rain"):
		var rain := $Weather/RainOnGlass as RainOnGlass
		if args.has("rain-delay"):
			get_tree().create_timer(float(args["rain-delay"])).timeout.connect(rain.set_rain.bind(float(args["rain"])))
		else:
			rain.set_rain(float(args["rain"]), true)
	if args.has("perf"):
		_start_perf(args)
	elif args.has("test"):
		var suite := load("res://tools/tests/%s_tests.gd" % args["test"]) as GDScript
		if not suite or not suite.can_instantiate():
			# A parse error would otherwise leave the game running until a timeout.
			push_error("TEST: suite '%s' failed to load (see the parse error above)" % args["test"])
			get_tree().quit(2)
			return
		add_child(suite.new())
	elif args.has("shots"):
		var shots: Node = load(SHOTS_SCRIPT).new()
		shots.set("zone", $Zones.get_child(0))
		shots.set("views", (args["shots"] as String).split(";", false))
		shots.set("hinges", (args.get("shot-hinge", "") as String).split(",", false))
		shots.set("ab", args.get("shot-ab", ""))
		shots.set("calls", (args.get("shot-call", "") as String).split(",", false))
		add_child(shots)


func _start_perf(args: Dictionary) -> void:
	var zone_name: String = args["perf"]
	var zone := $Zones.find_child(zone_name.to_pascal_case(), false) as Node3D
	if not zone:
		push_error("PERF: zone not loaded: %s" % zone_name)
		get_tree().quit(2)
		return
	var perf: Node = load(PERF_SCRIPT).new()
	perf.set("zone_name", zone_name)
	perf.set("zone", zone)
	perf.set("player", _player)
	if args.has("perf-duration"):
		perf.set("duration", float(args["perf-duration"]))
	if args.has("perf-hide"):
		perf.set("hide_nodes", (args["perf-hide"] as String).split(",", false))
	add_child(perf)


static func _user_args() -> Dictionary:
	var result := {}
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--"):
			var parts := arg.substr(2).split("=", true, 1)
			result[parts[0]] = parts[1] if parts.size() > 1 else ""
	return result
