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
##   --shot-no-player     with --shots: hide the player rig (hands) in the stills
##   --shot-player=x,z,yaw  with --shots: stand the player there first (mirrors)
##   --shot-foveation     with --shots: render with the shading rate map (Foveation)
##   --rain=<0..1>        start with rain on the glass (wet at once; RainOnGlass)
##   --rain-delay=<s>     with --rain: start dry and let the rain set in after s seconds
##   --time=<h|HH:MM|now> time of day (WorldState); tests, stills and perf runs
##                        default to FIXED_TIME, stopped, so they don't depend on the clock
##   --time-speed=<x>     game seconds per real second from --time on (0 stops the clock)
##   --date=<MM-DD>       the date (the sun's path); automated runs default to FIXED_DATE
##   --weather=<clear|cloudy>  sun out or overcast (WorldState)
##   --ab=B               start with every A/B switch on its B variant (perf runs)
##   --foveation=<off|r[,s]>  foveated rendering off, or its min radius and strength (Foveation)
##   --msaa=<0|2|4|8>     3D MSAA samples instead of the project's (perf A/B)

const PERF_SCRIPT := "res://tools/perf/perf_flythrough.gd"
const SHOTS_SCRIPT := "res://tools/shots/shots.gd"
## Time of day for tests, stills and perf runs without --time: night.
const FIXED_TIME := 22.0
## Date and UTC offset for tests, stills and perf runs without --date.
const FIXED_DATE: Array[int] = [10, 5]
const FIXED_UTC_OFFSET := 2.0

## Entry marker path inside the zone to spawn at.
@export var entry := NodePath("Zones/Apartment/Entries/Default")

@onready var _player: ArcologyPlayer = $Player
var _foveation := Foveation.new()


func _ready() -> void:
	var marker := get_node_or_null(entry) as Node3D
	if marker:
		_player.global_transform = marker.global_transform
	else:
		push_warning("Entry marker not found: %s" % entry)

	var args := _user_args()
	if args.has("msaa"):
		var samples: int = {"0": Viewport.MSAA_DISABLED, "2": Viewport.MSAA_2X, "4": Viewport.MSAA_4X, "8": Viewport.MSAA_8X}.get(args["msaa"], -1)
		if samples >= 0:
			get_viewport().msaa_3d = samples as Viewport.MSAA
		else:
			push_warning("--msaa: expected 0, 2, 4 or 8, got '%s'" % args["msaa"])
	_foveation.name = "Foveation"
	_foveation.configure(args.get("foveation", ""))
	add_child(_foveation)
	_set_time(args)
	if args.has("rain"):
		var world := $WorldState as WorldState
		if args.has("rain-delay"):
			get_tree().create_timer(float(args["rain-delay"])).timeout.connect(world.set_rain.bind(float(args["rain"])))
		else:
			world.set_rain(float(args["rain"]), true)
	if args.get("ab", "") == "B":
		ABSwitch.toggle_all(get_tree())
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
		shots.set("player_at", args.get("shot-player", ""))
		shots.set("player", _player)
		if args.has("shot-foveation"):
			shots.set("foveation", _foveation)
		if args.has("shot-no-player"):
			_player.visible = false
		add_child(shots)


func _set_time(args: Dictionary) -> void:
	var world := $WorldState as WorldState
	var run_speed := float(args["time-speed"]) if args.has("time-speed") else -1.0
	var automated := args.has("perf") or args.has("test") or args.has("shots")
	if args.has("date"):
		var date := WorldState.parse_date(args["date"])
		if date.is_empty():
			push_warning("--date: expected MM-DD, got '%s'" % args["date"])
		else:
			world.set_date(date[0], date[1])
	elif automated:
		world.set_date(FIXED_DATE[0], FIXED_DATE[1], FIXED_UTC_OFFSET)
	if args.has("weather"):
		var kind := WorldState.parse_weather(args["weather"])
		if kind < 0:
			push_warning("--weather: expected clear, cloudy or rain, got '%s'" % args["weather"])
		else:
			world.set_weather(kind as WorldState.Weather, true)
	if args.has("time"):
		var at := WorldState.parse_time(args["time"])
		if at >= 0.0:
			world.set_time(at, run_speed if run_speed >= 0.0 else (0.0 if automated else 1.0))
		elif args["time"] == "now":
			world.follow_clock()
		else:
			push_warning("--time: expected hours, HH:MM or now, got '%s'" % args["time"])
	elif automated:
		world.set_time(FIXED_TIME, maxf(run_speed, 0.0))
	elif run_speed >= 0.0:
		world.set_time(world.hours, run_speed)


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
	perf.set("foveation", _foveation)
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
