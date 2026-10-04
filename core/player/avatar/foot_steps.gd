class_name FootSteps
extends RefCounted
## Procedural stepping for the avatar's feet (D-042), in world space so a
## planted foot stays put while the player (and its XROrigin) moves.
##
## Each frame BodyIK passes each foot's home (where it rests under the hips)
## and the body's velocity. A planted foot steps when its home has moved more
## than [member trigger] (plus [member trigger_per_speed] per m/s) away or
## turned more than [member turn_trigger], the one farther behind first. While
## walking only one foot is in the air; when running the next step may start
## once the other foot is [member overlap] through its step. A step lifts the
## foot on an arc and lands ahead of the home, so that the home passes over it
## by mid-stance: planted feet never slide. When the body stops, the feet
## settle back into the stance ([member settle] threshold). Off the ground
## (jumping, falling) the feet tuck up under the body; seated they rest at
## their homes.

## Home distance (m) that starts a step while moving, at standstill.
var trigger := 0.1
## Extra home distance per m/s of speed (longer strides when faster).
var trigger_per_speed := 0.12
## How far (m) a leg reaches forward or back from under the hips (with the
## hip drop); the trigger stays below [member reach_share] of it, and a foot
## beyond [member urgent_share] of it steps even while the other is still in
## the air, so a planted foot is never dragged.
var reach := 0.45
var reach_share := 0.75
var urgent_share := 0.9
## Home distance (m) that starts a step while standing still (settling).
var settle := 0.04
## Home turn (degrees) that starts a step.
var turn_trigger := 25.0
## Step duration (s) at a slow walk; shorter when faster (per m/s: [member step_time_per_speed]).
var step_time := 0.34
var step_time_per_speed := 0.05
## Shortest step duration (s), at a sprint.
var min_step_time := 0.15
## Foot lift (m) at the middle of a step, plus [member lift_per_speed] per m/s.
var lift := 0.06
var lift_per_speed := 0.02
## Longest step (m) from where the foot left.
var max_stride := 1.4
## Share of its step the other foot must have done before a foot may start
## (1 = never both in the air; below 1 lets running overlap).
var overlap := 0.55
## Speed (m/s) from which steps may overlap.
var run_speed := 2.2
## Tuck height (m) while off the ground.
var tuck := 0.18
## Home distance (m) beyond which feet snap instead of stepping (teleport).
var snap := 1.2

var _plant: Array[Transform3D] = []
var _from: Array[Transform3D] = []
var _t: Array[float] = []
var _duration: Array[float] = []


## True while that foot is in the air between plants.
func stepping(foot: int) -> bool:
	return _t.size() > foot and _t[foot] >= 0.0


## Forgets the plants: the next update puts the feet at their homes.
func reset() -> void:
	_plant.clear()


## Returns each foot's world transform for this frame.
func update(delta: float, homes: Array[Transform3D], velocity: Vector3, on_ground: bool, seated: bool) -> Array[Transform3D]:
	var count := homes.size()
	if _plant.size() != count:
		_plant = homes.duplicate()
		_from = homes.duplicate()
		_t.resize(count)
		_t.fill(-1.0)
		_duration.resize(count)
		_duration.fill(step_time)
	var flat := Vector3(velocity.x, 0.0, velocity.z)
	var speed := flat.length()
	var feet: Array[Transform3D] = []
	feet.resize(count)

	if seated or not on_ground:
		for i in count:
			_plant[i] = homes[i]
			_t[i] = -1.0
			feet[i] = homes[i] if seated else homes[i].translated(Vector3.UP * tuck)
		return feet

	# Start a step for the foot farthest from its home, if the other foot is
	# planted (walking) or far enough through its own step (running).
	var duration := clampf(step_time - speed * step_time_per_speed, min_step_time, step_time)
	var busy := false
	var urgent := false
	for i in count:
		if _t[i] >= 0.0 and (speed < run_speed or _t[i] < overlap):
			busy = true
		elif _t[i] < 0.0 and _flat_distance(_plant[i].origin, homes[i].origin) > reach * urgent_share:
			urgent = true
	if not busy or urgent:
		var worst := -1
		var worst_need := 0.0
		for i in count:
			if _t[i] >= 0.0:
				continue
			var off := _flat_distance(_plant[i].origin, homes[i].origin)
			if off > snap:
				_plant[i] = homes[i]
				continue
			var turn := rad_to_deg(_yaw_between(_plant[i].basis, homes[i].basis))
			var limit := minf(trigger + trigger_per_speed * speed, reach * reach_share) if speed > 0.1 else settle
			var need := maxf(off / limit, turn / turn_trigger)
			if need > 1.0 and need > worst_need:
				worst = i
				worst_need = need
		if worst >= 0:
			_from[worst] = _plant[worst]
			_t[worst] = 0.0
			_duration[worst] = duration

	for i in count:
		# Planted feet keep their place on the floor, but follow its height
		# (landing, stairs): only x/z and the turn stay where they were planted.
		_plant[i].origin.y = homes[i].origin.y
		_from[i].origin.y = homes[i].origin.y
		if _t[i] < 0.0:
			feet[i] = _plant[i]
			continue
		# Land ahead of the (moving) home: it passes over the foot by mid-stance,
		# a stance lasting about one step of the other foot.
		var target := homes[i]
		target.origin += flat * (_duration[i] * (1.0 - _t[i]) + _duration[i] * 0.5)
		var reach := target.origin - _from[i].origin
		reach.y = 0.0
		if reach.length() > max_stride:
			target.origin = _from[i].origin + reach.normalized() * max_stride + Vector3.UP * (target.origin.y - _from[i].origin.y)
		_t[i] = minf(_t[i] + delta / _duration[i], 1.0)
		var s := smoothstep(0.0, 1.0, _t[i])
		var basis := Basis(_from[i].basis.get_rotation_quaternion().slerp(target.basis.get_rotation_quaternion(), s))
		var position := _from[i].origin.lerp(target.origin, s) + Vector3.UP * (sin(_t[i] * PI) * (lift + lift_per_speed * speed))
		feet[i] = Transform3D(basis, position)
		if _t[i] >= 1.0:
			_plant[i] = target
			_t[i] = -1.0
	return feet


static func _flat_distance(a: Vector3, b: Vector3) -> float:
	return Vector2(a.x - b.x, a.z - b.z).length()


## Yaw difference (radians, absolute) between two foot orientations (the foot
## bone points along the foot, +Y).
static func _yaw_between(a: Basis, b: Basis) -> float:
	var fa := Vector2(a.y.x, a.y.z)
	var fb := Vector2(b.y.x, b.y.z)
	if fa.length_squared() < 0.0001 or fb.length_squared() < 0.0001:
		return 0.0
	return absf(fa.angle_to(fb))
