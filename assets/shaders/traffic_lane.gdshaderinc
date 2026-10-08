// Flying traffic moves on the GPU (FlyingTraffic, zones/skyline/flying_traffic.gd).
// Each MultiMesh instance is one vehicle; its transform is its lane's start,
// local -Z along the lane. INSTANCE_CUSTOM: x = phase (0..1), y = lane speed /
// lane length (1/s), z = lane length (m), w = vehicle type + seed (0..1): the
// whole part picks the type's lamps (traffic_lights.gdshader), the fraction
// the bob's phase.

uniform float lane_fade = 0.015;  // share of the lane at each end where vehicles scale in/out
uniform float lane_fade_min = 15.0;  // ... but at least this far (m): short lanes end at junctions in view
uniform float bob = 0.25;         // hover bob amplitude (m)
uniform float time_scale = 1.0;   // 0 freezes the traffic (FlyingTraffic.set_frozen, shimmer test)

// 0..1 along the lane.
float lane_t(vec4 custom, float time) {
	return fract(custom.x + time * custom.y);
}

// 0 at the lane's ends, 1 in between.
float lane_scale(float t, float lane_length) {
	float fade = max(lane_fade, lane_fade_min / max(lane_length, 1.0));
	return smoothstep(0.0, fade, t) * smoothstep(1.0, 1.0 - fade, t);
}

// The vehicle's center in the lane frame.
vec3 lane_offset(vec4 custom, float t, float time) {
	return vec3(0.0, sin(time * 0.7 + custom.w * 6.2832) * bob, -t * custom.z);
}
