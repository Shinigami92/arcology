class_name RayButtons
extends RefCounted
## The press targets the controller rays aim at (D-054): every Area3D the
## fingertips press, i.e. whose collision mask has the Player Hands layer
## (XR Tools area buttons, the world terminal's keys, ...), with a box or
## sphere shape. Found once per scene tree and kept up to date as nodes are
## added; freed ones drop out on their own.
##
## [method pick] tests a ray against them: an exact hit on a shape wins (the
## nearest), else the button whose center is closest to the ray within the
## snap angle. Either needs a clear line of sight (Static World). A press goes
## through the area's own area_entered/area_exited signals with a stand-in
## "fingertip" (GrabRay), so every button reacts exactly as to a touch.

const FINGERTIP_LAYER := 131072
## A line-of-sight ray that stops this close to its target reached it (the
## button's own housing).
const SIGHT_SLACK := 0.06

static var _tree: SceneTree
static var _targets: Array[Area3D] = []


## Every press target in [param tree].
static func targets(tree: SceneTree) -> Array[Area3D]:
	if _tree != tree:
		_tree = tree
		_targets.clear()
		for node in tree.root.find_children("*", "Area3D", true, false):
			_consider(node)
		tree.node_added.connect(_consider)
	_targets = _targets.filter(func(a: Area3D) -> bool: return is_instance_valid(a))
	return _targets


## The button a ray from [param origin] along [param dir] (unit) points at:
## {"area", "point" (where the ray meets it, or its center when snapped),
## "exact"}; empty if none within [param max_distance].
static func pick(tree: SceneTree, space: PhysicsDirectSpaceState3D, origin: Vector3, dir: Vector3,
		max_distance: float, snap_degrees: float, occluder_mask: int) -> Dictionary:
	var best := {}
	var best_t := INF
	var best_angle := deg_to_rad(snap_degrees)
	var sight := PhysicsRayQueryParameters3D.new()
	sight.collision_mask = occluder_mask
	for area in targets(tree):
		if not area.is_inside_tree() or not area.is_visible_in_tree() or not area.monitoring:
			continue
		var shape := _shape_of(area)
		if not shape:
			continue
		var xform := shape.global_transform
		var t := _intersect(shape.shape, xform, origin, dir)
		var exact := t >= 0.0 and t <= max_distance
		var point := origin + dir * t if exact else xform.origin
		if exact:
			if t >= best_t:
				continue
		else:
			if best_t < INF:
				continue
			var to := xform.origin - origin
			var dist := to.length()
			if dist > max_distance or dist < 0.01:
				continue
			var angle := dir.angle_to(to / dist)
			if angle >= best_angle:
				continue
		sight.from = origin
		sight.to = point
		var blocker := space.intersect_ray(sight)
		if not blocker.is_empty() and (blocker["position"] as Vector3).distance_to(point) > SIGHT_SLACK:
			continue
		best = {"area": area, "point": point, "exact": exact}
		if exact:
			best_t = t
		else:
			best_angle = dir.angle_to((xform.origin - origin).normalized())
	return best


static func _consider(node: Node) -> void:
	var area := node as Area3D
	if area and area.collision_mask & FINGERTIP_LAYER and not _targets.has(area):
		_targets.append(area)


static func _shape_of(area: Area3D) -> CollisionShape3D:
	for child in area.get_children():
		var shape := child as CollisionShape3D
		if shape and not shape.disabled and (shape.shape is BoxShape3D or shape.shape is SphereShape3D):
			return shape
	return null


## Distance along the ray to the shape (world units), or -1.
static func _intersect(shape: Shape3D, xform: Transform3D, origin: Vector3, dir: Vector3) -> float:
	var inv := xform.affine_inverse()
	var o := inv * origin
	var d := inv.basis * dir
	if shape is BoxShape3D:
		var half := (shape as BoxShape3D).size * 0.5
		var t_near := -INF
		var t_far := INF
		for i in 3:
			if absf(d[i]) < 1e-8:
				if absf(o[i]) > half[i]:
					return -1.0
				continue
			var t1 := (-half[i] - o[i]) / d[i]
			var t2 := (half[i] - o[i]) / d[i]
			t_near = maxf(t_near, minf(t1, t2))
			t_far = minf(t_far, maxf(t1, t2))
		if t_near > t_far or t_far < 0.0:
			return -1.0
		return maxf(t_near, 0.0)
	var r := (shape as SphereShape3D).radius
	var b := o.dot(d)
	var a := d.dot(d)
	var c := o.dot(o) - r * r
	var disc := b * b - a * c
	if disc < 0.0:
		return -1.0
	var t := (-b - sqrt(disc)) / a
	if t < 0.0:
		t = (-b + sqrt(disc)) / a
	return t if t >= 0.0 else -1.0
