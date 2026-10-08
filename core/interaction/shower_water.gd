class_name ShowerWater
extends Node
## Running water for the shower (D-058): the flow lever ([member flow], a
## hinge from -90 = hand shower through 0 = off to +90 = rain head) opens the
## hand shower's spray or the rain head's, in proportion to how far it's
## turned. Each spray is a GPUParticles3D of falling streaks (built here) that
## vanish on the floor, walls and glass ([member colliders]), with a looped
## spray sound. Particles and sound run only while that outlet is open.

@export var flow: XRToolsInteractableHinge
## The hand shower's spray face: drops leave along its +Z.
@export var hand_nozzle: Node3D
## The rain head's middle: drops fall along its -Y.
@export var rain_nozzle: Node3D
## Rain head nozzle field (square side).
@export_custom(PROPERTY_HINT_NONE, "suffix:m") var rain_size := 0.32
## Boxes the drops vanish on (floor, walls, glass), in this node's parent's
## frame; each becomes a GPUParticlesCollisionBox3D.
@export var colliders: Array[AABB] = []
@export var sound: AudioStream = preload("res://assets/audio/sfx/shower_spray.wav")
@export var sound_db := -12.0

## Below this share of full flow an outlet counts as closed.
const MIN_FLOW := 0.06

var _hand: GPUParticles3D
var _rain: GPUParticles3D
var _hand_sound: AudioStreamPlayer3D
var _rain_sound: AudioStreamPlayer3D


func _ready() -> void:
	if not flow or not hand_nozzle or not rain_nozzle:
		push_error("ShowerWater needs flow, hand_nozzle and rain_nozzle: %s" % get_path())
		return
	_hand = _spray(hand_nozzle, "HandSpray", 500, 0.7, Vector3(0, 0, 1), 10.0, 3.2, 0.032)
	_rain = _spray(rain_nozzle, "RainSpray", 900, 1.1, Vector3(0, -1, 0), 4.0, 1.2, 0.0)
	var box := _rain.process_material as ParticleProcessMaterial
	box.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	box.emission_box_extents = Vector3(rain_size / 2.0, 0.0, rain_size / 2.0)
	_hand_sound = _player(hand_nozzle, "HandSpraySound")
	# The rain is heard where it lands.
	_rain_sound = _player(rain_nozzle, "RainSpraySound")
	_rain_sound.position = Vector3(0, -2.4, 0)
	var parent := get_parent() as Node3D
	for i in colliders.size():
		var c := GPUParticlesCollisionBox3D.new()
		c.name = "WaterCollider%d" % i
		c.size = colliders[i].size
		c.position = colliders[i].get_center()
		parent.add_child.call_deferred(c)
	flow.hinge_moved.connect(_on_flow)
	_on_flow(flow.hinge_position)


## Share of full flow at the hand shower and the rain head (0..1).
func get_flow() -> Vector2:
	var angle := flow.hinge_position
	return Vector2(clampf(-angle / 90.0, 0.0, 1.0), clampf(angle / 90.0, 0.0, 1.0))


func _on_flow(_angle: float) -> void:
	var f := get_flow()
	_set_outlet(_hand, _hand_sound, f.x)
	_set_outlet(_rain, _rain_sound, f.y)


func _set_outlet(spray: GPUParticles3D, player: AudioStreamPlayer3D, amount: float) -> void:
	var on := amount >= MIN_FLOW
	spray.amount_ratio = clampf(amount, 0.0, 1.0)
	if spray.emitting != on:
		spray.emitting = on
	player.volume_db = sound_db + linear_to_db(maxf(amount, 0.01))
	if on and not player.playing:
		player.play()
	elif not on and player.playing:
		player.stop()


func _player(parent: Node3D, player_name: String) -> AudioStreamPlayer3D:
	var p := AudioStreamPlayer3D.new()
	p.name = player_name
	p.stream = sound
	p.unit_size = 3.0
	p.max_distance = 15.0
	parent.add_child(p)
	return p


## Streaks of water leaving `parent` along `direction` (its frame).
func _spray(parent: Node3D, spray_name: String, amount: int, lifetime: float, direction: Vector3,
		spread: float, speed: float, ring: float) -> GPUParticles3D:
	var process := ParticleProcessMaterial.new()
	process.direction = direction
	process.spread = spread
	process.initial_velocity_min = speed * 0.85
	process.initial_velocity_max = speed * 1.1
	process.gravity = Vector3(0, -9.8, 0)
	process.collision_mode = ParticleProcessMaterial.COLLISION_HIDE_ON_CONTACT
	process.scale_min = 0.7
	process.scale_max = 1.2
	if ring > 0.0:
		process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
		process.emission_ring_axis = Vector3(0, 0, 1)
		process.emission_ring_radius = ring
		process.emission_ring_inner_radius = 0.0
		process.emission_ring_height = 0.0
	var streak := QuadMesh.new()
	streak.size = Vector2(0.0025, 0.045)
	var look := StandardMaterial3D.new()
	look.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	look.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	look.albedo_color = Color(0.78, 0.86, 0.95, 0.28)
	look.cull_mode = BaseMaterial3D.CULL_DISABLED
	look.disable_receive_shadows = true
	streak.material = look
	var p := GPUParticles3D.new()
	p.name = spray_name
	p.amount = amount
	p.lifetime = lifetime
	p.emitting = false
	p.local_coords = false
	p.process_material = process
	p.draw_pass_1 = streak
	p.transform_align = GPUParticles3D.TRANSFORM_ALIGN_Z_BILLBOARD_Y_TO_VELOCITY
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.collision_base_size = 0.01
	p.visibility_aabb = AABB(Vector3(-2, -3, -2), Vector3(4, 4, 4))
	parent.add_child(p)
	return p
