extends Node3D
## Entry scene: starts XR, loads the world backdrop and the first zone, and
## places the player at the zone's entry marker.
##
## Zone streaming (core/zones) replaces the static zone instance in M3.
## Command-line user args (after "--"):
##   --perf=<zone>        run the perf flythrough for that zone and quit
##   --perf-duration=<s>  flythrough length in seconds (default 20)
##   --perf-hide=<a,b>    zone-relative node paths to hide (A/B cost tests)

const PERF_SCRIPT := "res://tools/perf/perf_flythrough.gd"

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
	if args.has("perf"):
		_start_perf(args)


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
