// Far-city facade: dark concrete with procedural lit windows and rare neon bands.
// Windows are placed in world space so scaled box instances get consistent
// floor heights. Per-instance variety comes from INSTANCE_CUSTOM.x (0..1 seed).
//
// Anti-aliased analytically: MSAA doesn't touch shader patterns and there are
// no mipmaps, so pane edges are smoothed by their screen-space derivative and
// the whole pattern fades to its average brightness once a window cell gets
// smaller than about a pixel. Without this, distant windows shimmer in VR.
shader_type spatial;
render_mode cull_back, specular_disabled;

uniform vec3 wall_color : source_color = vec3(0.035, 0.04, 0.05);
uniform vec3 warm_light : source_color = vec3(1.0, 0.72, 0.42);
uniform vec3 cold_light : source_color = vec3(0.55, 0.8, 1.0);
uniform vec3 neon_a : source_color = vec3(1.0, 0.165, 0.427);
uniform vec3 neon_b : source_color = vec3(0.02, 0.851, 0.91);
uniform float floor_height = 3.4;
uniform float window_spacing = 2.6;
uniform float lit_fraction : hint_range(0.0, 1.0) = 0.38;
uniform float window_energy = 2.2;
uniform float neon_energy = 7.0;
// Anti-aliasing: pane edges are smoothed over edge_softness pixels; the pattern
// fades to its average between far_start and far_end cells per pixel.
uniform float edge_softness = 2.0;
uniform float far_start = 0.2;
uniform float far_end = 0.5;
// The tonemapper compresses bright windows, so the true average reads too
// bright from afar; scale it down to match the look of resolved windows.
uniform float far_brightness = 0.5;

// Pane extent inside a cell (fractions of the cell).
const vec2 PANE_MIN = vec2(0.18, 0.25);
const vec2 PANE_MAX = vec2(0.82, 0.8);
// Share of warm windows, for the far-distance average.
const float COLD_SHARE = 0.28;
const float BAND_HALF_WIDTH = 0.08;

varying vec3 world_pos;
varying vec3 world_normal;
varying float seed;

float hash(vec3 p) {
	p = fract(p * 0.3183099 + 0.1);
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

// 1 inside [lo, hi], 0 outside, edges smoothed over w.
float box(float x, float lo, float hi, float w) {
	return smoothstep(lo - w, lo + w, x) * (1.0 - smoothstep(hi - w, hi + w, x));
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	seed = INSTANCE_CUSTOM.x;
}

void fragment() {
	ALBEDO = wall_color;
	ROUGHNESS = 0.9;

	if (abs(world_normal.y) < 0.5) {
		// Horizontal coordinate along the face.
		float u = abs(world_normal.x) > 0.5 ? world_pos.z : world_pos.x;
		vec2 cell = vec2(u / window_spacing, world_pos.y / floor_height);
		// Derivatives of the continuous coordinate (fract() would jump at borders).
		vec2 fw = fwidth(cell) * edge_softness;
		vec2 id = floor(cell);
		vec2 f = fract(cell);

		float pane = box(f.x, PANE_MIN.x, PANE_MAX.x, fw.x) * box(f.y, PANE_MIN.y, PANE_MAX.y, fw.y);
		float h = hash(vec3(id, seed * 97.0));
		float lit = step(1.0 - lit_fraction, h);
		vec3 tint = mix(warm_light, cold_light, step(0.72, hash(vec3(id.yx, seed * 13.0))));
		float flicker = 0.75 + 0.25 * hash(vec3(id, 5.0));
		vec3 near_emission = tint * pane * lit * flicker * window_energy;

		vec2 pane_size = PANE_MAX - PANE_MIN;
		vec3 average = mix(warm_light, cold_light, COLD_SHARE) * pane_size.x * pane_size.y
				* lit_fraction * 0.875 * window_energy * far_brightness;
		float far = smoothstep(far_start, far_end, max(fw.x, fw.y) / max(edge_softness, 1e-4));
		vec3 emission = mix(near_emission, average, far);

		// Rare horizontal neon band on some buildings; thins out by coverage.
		float band_floor = floor(seed * 40.0) + 6.0;
		float d = abs(cell.y - band_floor);
		float band = (1.0 - smoothstep(BAND_HALF_WIDTH, BAND_HALF_WIDTH + fw.y, d))
				* min(1.0, 2.0 * BAND_HALF_WIDTH / max(fw.y, 1e-4));
		band *= step(0.6, seed);
		emission += mix(neon_a, neon_b, step(0.8, seed)) * band * neon_energy;

		EMISSION = emission;
	}
}
