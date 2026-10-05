// Holographic panel tiles (style guide: unshaded, additive, cyan, scanlines,
// a slight flicker). Drawn as one MultiMesh of unit quads: the instance color
// is the tile's color and brightness, INSTANCE_CUSTOM.xy its size in meters,
// INSTANCE_CUSTOM.z its fill (0 outline only .. 1 solid).
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled;

uniform float energy = 1.4;
uniform float border = 0.0025;          // outline width (m)
uniform float base_fill = 0.12;         // fill of an idle tile
// Coarse on purpose: fine lines shimmer in the headset (style guide).
uniform float scanlines_per_meter = 260.0;
uniform float scanline_depth = 0.12;

varying vec2 v_size;
varying float v_fill;
varying float v_height;

void vertex() {
	v_size = max(INSTANCE_CUSTOM.xy, vec2(0.001));
	v_fill = INSTANCE_CUSTOM.z;
	v_height = (MODEL_MATRIX * vec4(VERTEX, 1.0)).y;
}

void fragment() {
	// Distance to the tile's edge in meters, antialiased by its screen size.
	vec2 p = (UV - 0.5) * v_size;
	vec2 d = v_size * 0.5 - abs(p);
	float edge = min(d.x, d.y);
	float aa = max(fwidth(edge), 1e-5);
	float outline = 1.0 - smoothstep(border - aa, border + aa, edge);
	float fill = mix(base_fill, 0.3, v_fill);
	float scan = 1.0 - scanline_depth * (0.5 + 0.5 * sin(v_height * scanlines_per_meter * TAU));
	float flicker = 0.96 + 0.04 * sin(TIME * 31.0) * sin(TIME * 7.3 + v_height * 4.0);
	ALBEDO = COLOR.rgb * max(outline, fill) * scan * flicker * energy;
}
