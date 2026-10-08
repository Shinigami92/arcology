// Holographic sign panel (HoloSign, D-060; style guide: unshaded, additive,
// cyan or magenta, scanlines, a slight flicker). One quad: a faint fill, a thin
// outline, and optional chevrons on one side that run toward where the sign
// points. The text is a Label3D in front of it.
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled;

uniform vec3 tint : source_color = vec3(0.02, 0.85, 0.91);
uniform float energy = 1.2;
uniform vec2 size = vec2(1.0, 0.3);     // panel size (m), set by HoloSign
uniform float border = 0.004;           // outline width (m)
uniform float fill = 0.06;
// Coarse on purpose: fine lines shimmer in the headset (as hologram_tile).
uniform float scanlines_per_meter = 220.0;
uniform float scanline_depth = 0.15;
// Chevrons: -1 left, 1 right, 0 none; drawn in the panel's last arrow_width meters on that side.
uniform float arrow = 0.0;
uniform float arrow_width = 0.3;
uniform float arrow_speed = 0.35;       // m/s along the arrow

varying float v_height;

void vertex() {
	v_height = (MODEL_MATRIX * vec4(VERTEX, 1.0)).y;
}

float chevrons(vec2 p) {
	// p: meters from the arrow field's inner edge (x along the arrow, y from the middle).
	float pitch = 0.09;
	float x = p.x - TIME * arrow_speed;
	float phase = fract(x / pitch) * pitch;
	// A chevron with its tip forward (toward +x, where the sign points): the arms trail back.
	float d = abs(phase - (0.065 - abs(p.y) * 0.8));
	float aa = max(fwidth(d), 1e-5);
	float stroke = 1.0 - smoothstep(0.008 - aa, 0.008 + aa, d);
	float inside = step(abs(p.y), size.y * 0.28);
	// Fade in from the text side, so the chevrons appear to come out of it.
	float fade = smoothstep(0.0, 0.08, p.x);
	return stroke * inside * fade;
}

void fragment() {
	vec2 p = (UV - 0.5) * size;
	p.y = -p.y;
	vec2 d = size * 0.5 - abs(p);
	float edge = min(d.x, d.y);
	float aa = max(fwidth(edge), 1e-5);
	float outline = 1.0 - smoothstep(border - aa, border + aa, edge);
	float glow = max(outline, fill);
	if (arrow != 0.0) {
		float x = p.x * arrow - (size.x * 0.5 - arrow_width);
		if (x > 0.0) {
			glow = max(glow, chevrons(vec2(x, p.y)));
		}
	}
	float scan = 1.0 - scanline_depth * (0.5 + 0.5 * sin(v_height * scanlines_per_meter * TAU));
	float flicker = 0.95 + 0.05 * sin(TIME * 29.0) * sin(TIME * 6.1 + v_height * 3.0);
	ALBEDO = tint * glow * scan * flicker * energy;
}
