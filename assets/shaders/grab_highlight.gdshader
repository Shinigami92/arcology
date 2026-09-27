// Additive fresnel rim used as material_overlay on grab targets.
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back;

uniform vec3 color : source_color = vec3(0.02, 0.851, 0.91);
uniform float power = 2.5;
uniform float energy = 1.6;

void fragment() {
	float rim = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), power);
	ALBEDO = color * (0.12 + rim) * energy;
}
