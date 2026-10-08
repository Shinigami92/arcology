// Distant flying traffic as light glows: one camera-facing quad per vehicle,
// white headlights while it comes toward the camera, red taillights while it
// leaves. Never smaller than min_pixels (sub-pixel lights would sparkle in VR);
// a glow that has to grow gets dimmer by the same area, so it fades out with
// distance instead. Faded in beyond near_start..near_end, where the meshes'
// own lamps take over. Additive and unshaded, so the scene fog is applied by
// hand (fog_* mirror the skyline Environment, set by FlyingTraffic).
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, fog_disabled, shadows_disabled, skip_vertex_transform;

#include "res://assets/shaders/traffic_lane.gdshaderinc"

// Lamp pair centers in the vehicle's frame (nose = -Z) per vehicle type: x
// head z, y tail z, z height. The type is INSTANCE_CUSTOM.w's whole part, so
// one MultiMesh holds every type's glows (FlyingTraffic).
uniform vec3 lamps[8];

uniform vec3 head_color : source_color = vec3(1.0, 0.93, 0.82);
uniform vec3 tail_color : source_color = vec3(1.0, 0.07, 0.04);
uniform float energy = 8.0;
uniform float base_size = 2.0;        // glow diameter up close (m)
uniform float pixel_angle = 0.0012;   // radians per headset pixel
uniform float min_pixels = 4.0;
uniform float near_start = 120.0;
uniform float near_end = 260.0;
uniform float fog_density = 0.0016;
uniform float fog_height = -30.0;
uniform float fog_height_density = 0.025;

varying vec3 glow;

void vertex() {
	float time = TIME * time_scale;
	float t = lane_t(INSTANCE_CUSTOM, time);
	vec3 type_lamps = lamps[clamp(int(INSTANCE_CUSTOM.w), 0, 7)];
	float head_z = type_lamps.x;
	float tail_z = type_lamps.y;
	vec3 travel = normalize(-MODEL_MATRIX[2].xyz);
	vec3 center = (MODEL_MATRIX * vec4(lane_offset(INSTANCE_CUSTOM, t, time) + vec3(0.0, type_lamps.z, 0.0), 1.0)).xyz;
	vec3 to_cam = CAMERA_POSITION_WORLD - center;
	float dist = length(to_cam);
	float facing = smoothstep(-0.15, 0.15, dot(travel, to_cam / dist));
	vec3 lamp = center - travel * mix(tail_z, head_z, facing);

	float size = max(base_size, dist * pixel_angle * min_pixels);
	float fog = 1.0 - exp(-dist * fog_density);
	fog = max(fog, 1.0 - exp(min(0.0, (lamp.y - fog_height) * fog_height_density)));
	float strength = energy * pow(base_size / size, 2.0) * lane_scale(t, INSTANCE_CUSTOM.z)
			* smoothstep(near_start, near_end, dist) * (1.0 - fog);
	glow = mix(tail_color, head_color, facing) * strength;

	vec3 view = (VIEW_MATRIX * vec4(lamp, 1.0)).xyz;
	view.z += 1.5;  // in front of the body, so the hull doesn't hide its own lamps
	VERTEX = view + vec3(VERTEX.xy * size, 0.0);
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	ALBEDO = glow * exp(-dot(p, p) * 4.0);
}
