shader_type spatial;
// Door viewer lens (D-058), fed by a DoorViewer node: a disc on the inner lens
// that shows its camera's wide view of the far side as through a fisheye. Each
// eye's ray through the lens leaves at `magnification` times its angle to the
// axis, so an eye up close sees the whole wide view in the small lens and one
// further away a bright distorted dot. Only `shown_view` (the eye at the
// lens, DoorViewer picks it) looks through; the other eye sees dark glass, as
// with a real peephole seen with one eye. The camera renders in HDR with a linear
// tone mapper (PlanarReflection's environment); unshaded, the main pass tone
// maps once.
render_mode unshaded, shadows_disabled, cull_back;

uniform sampler2D view_texture : hint_default_black, filter_linear, repeat_disable;
// 0 before the first render: dark glass.
uniform float live = 0.0;
// -1 (no eye at the lens): both eyes see it, a bright dot from afar.
uniform int shown_view = -1;
uniform float radius = 0.0072;
uniform float magnification = 6.0;
// tan(fov / 2) of the camera.
uniform float tan_half_fov = 1.732;
uniform vec3 glass_color : source_color = vec3(0.02, 0.025, 0.03);

varying vec3 lens_pos;
varying vec3 eye_pos;

void vertex() {
	lens_pos = VERTEX;
	// Per view: each eye looks through at its own angle.
	eye_pos = (inverse(MODEL_MATRIX) * vec4(INV_VIEW_MATRIX[3].xyz, 1.0)).xyz;
}

void fragment() {
	float r = length(lens_pos.xy);
	if (r > radius) {
		discard;
	}
	// The other eye sees dark glass (no image).
	float seen = (shown_view >= 0 && int(VIEW_INDEX) != shown_view) ? 0.0 : live;
	vec3 d = normalize(lens_pos - eye_pos);
	float theta = acos(clamp(-d.z, -1.0, 1.0)) * magnification;
	vec3 image = vec3(0.0);
	if (theta < 1.5) {
		vec2 dir = d.xy / max(length(d.xy), 1e-6);
		vec2 p = tan(theta) * dir / tan_half_fov;
		if (max(abs(p.x), abs(p.y)) < 1.0) {
			image = texture(view_texture, vec2(0.5 + 0.5 * p.x, 0.5 - 0.5 * p.y)).rgb;
		}
		// The fisheye darkens toward its rim.
		image *= smoothstep(1.5, 1.05, theta);
	}
	image *= smoothstep(radius, radius * 0.7, r);
	ALBEDO = mix(glass_color, image, seen);
}
