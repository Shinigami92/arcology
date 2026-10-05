// Window glass (D-033, D-034): one transparent layer per pane, nearly clear, with
// reflections (live per eye while in view, D-049; else the room's ReflectionProbe), low-frequency smudges,
// smart-glass tint, an optional HUD readout and rain on the outside.
// Style guide: a single pane, no stacked transparent layers.
//
// Premultiplied alpha: ALBEDO is premultiplied by the coverage here, so
// reflections (specular) and the HUD (emission) stay at full strength on an
// almost clear pane, and ALPHA only says how much of the view behind is kept.
// Expects a QuadMesh (local XY plane, meters, centered): the HUD, the smudges
// and the rain are laid out in the pane's own meters.
//
// Two variants share this file: window_glass.gdshader (dry: no rain code, no
// screen read) and window_glass_wet.gdshader (WINDOW_GLASS_RAIN, and with
// WINDOW_GLASS_RAIN_SCREEN the drops refract through the screen texture, the
// opaque scene, one layer per eye in stereo; without it they show a flat
// average: the fallback, about 0.6 ms cheaper, see D-034).
// RainOnGlass puts the window materials on the wet one only while the glass is
// wet, because a shader that reads the screen makes Godot copy it every frame.

// Live reflection (D-049): a PlanarReflection per window renders the room as seen
// in the glass while the window is in view; then it replaces the probe reflection.
#include "res://assets/shaders/planar_reflection.gdshaderinc"

// ---- glass
uniform vec3 glass_color : source_color = vec3(0.78, 0.85, 0.9);
// Share of the view behind that the clear glass takes away (dust, absorption).
uniform float clear_alpha : hint_range(0.0, 0.3) = 0.035;
// Specular level (0.5 = F0 0.04, real float glass); a little more reads better in VR.
uniform float reflectivity : hint_range(0.0, 1.0) = 0.6;
uniform float roughness : hint_range(0.0, 0.5) = 0.025;
// Live reflection strength over one face's Fresnel: double glazing reflects from both panes.
uniform float reflection_gain : hint_range(0.0, 4.0) = 1.6;

// ---- smudges: large, soft wipes only (no high-frequency noise: it shimmers in stereo)
uniform float smudge_amount : hint_range(0.0, 1.0) = 0.5;
uniform float smudge_scale = 1.6;  // features per meter (about 0.3-0.6 m blobs)

// ---- smart glass (electrochromic)
// 0 = clear, 1 = fully tinted. Driven by SmartGlass.
uniform float tint : hint_range(0.0, 1.0) = 0.0;
uniform vec3 tint_color : source_color = vec3(0.1, 0.13, 0.17);
// Coverage at tint 1 (0.96 keeps 4% of the view behind, like dark electrochromic glass).
uniform float tint_alpha : hint_range(0.0, 1.0) = 0.96;
// Faint cool glow of the tinted layer (city light coming through it).
uniform float tint_glow : hint_range(0.0, 0.2) = 0.1;
uniform float tint_reflectivity : hint_range(0.0, 1.0) = 0.25;

// ---- rain on the outer face, driven by RainOnGlass (all 0 = dry: rain() returns at once)
// How hard it rains now (smoothed): new beads landing, the wet haze.
uniform float rain_amount : hint_range(0.0, 1.0) = 0.0;
// Bead coverage: lags behind the rain and dries out after it (evaporation).
uniform float rain_wet : hint_range(0.0, 1.0) = 0.0;
// Clocks (s) that only run while it rains / while drops slide, so beads stop
// changing and runners stop where they are when the rain ends.
uniform float rain_time = 0.0;
uniform float rain_slide_time = 0.0;
// Drops sit this far outside the pane (the outer glass face): parallax and stereo depth.
uniform float rain_depth = 0.012;
// Lens strength: a drop shows an area this many times its own size, upside down.
uniform float rain_lens = 5.0;
// Micro-droplet mist on wet glass (coverage at full wetness), and its faint milky scatter.
uniform float rain_mist : hint_range(0.0, 1.0) = 0.45;
uniform vec3 rain_mist_color : source_color = vec3(0.006, 0.007, 0.009);
// Highlight of the room's lights on each drop.
uniform vec3 rain_highlight : source_color = vec3(0.5, 0.4, 0.3);
// What drops and mist show without the screen read (WINDOW_GLASS_RAIN_SCREEN off).
uniform vec3 rain_fallback_color : source_color = vec3(0.05, 0.045, 0.04);
#ifdef WINDOW_GLASS_RAIN_SCREEN
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
#endif

// ---- HUD readout, driven by WindowHud. Shown on panes with hud_enabled.
instance uniform bool hud_enabled = false;
// Lower right corner of the readout in the pane's local meters (+X = right seen from the room).
instance uniform vec2 hud_anchor = vec2(0.0);
uniform vec3 hud_color : source_color = vec3(0.02, 0.85, 0.91);
uniform float hud_energy = 1.6;
uniform float hud_height = 0.075;  // time digits (m); the second line is 0.8 of that
// Hours and minutes as digits (h1, h2, m1, m2), -1 = blank.
uniform ivec4 hud_time = ivec4(1, 2, 0, 0);
uniform int hud_temperature = 14;  // °C, -99..99
uniform int hud_weather = 1;       // 0 clear night, 1 cloudy, 2 rain, 3 sun

varying vec2 v_local;
varying float v_seed;
// Vector from the vertex to this eye's camera, in the pane's local space (rain parallax).
varying vec3 v_to_cam;

// 7-segment bits: a (top), b (top right), c (bottom right), d (bottom), e (bottom left), f (top left), g (middle).
const int SEGMENTS[10] = { 63, 6, 91, 79, 102, 109, 125, 7, 127, 111 };
const int SEG_MINUS = 64;
const float DIGIT_W = 0.5;      // in digit heights
const float DIGIT_ADV = 0.74;
const float STROKE = 0.11;      // stroke width in digit heights
const float SLANT = 0.08;
// The glow around the glyphs fades out within this distance (m); shapes are evaluated that far out.
const float HALO = 0.025;

void vertex() {
	v_local = VERTEX.xy;
	v_seed = dot(MODEL_MATRIX[3].xyz, vec3(1.7, 0.3, 2.9));
#ifdef WINDOW_GLASS_RAIN
	// This eye's position (the view matrix is the eyes' midpoint in stereo).
	vec3 eye_world = (INV_VIEW_MATRIX * vec4(EYE_OFFSET, 1.0)).xyz;
	v_to_cam = (inverse(MODEL_MATRIX) * vec4(eye_world, 1.0)).xyz - VERTEX;
#else
	v_to_cam = vec3(0.0, 0.0, 1.0);
#endif
}

// ---------------------------------------------------------------- noise
float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// 0..1, mostly 0 with a few soft wipes and a hazier band low on the pane (hands, cleaning).
float smudges(vec2 p, float seed) {
	vec2 q = p * smudge_scale + vec2(seed, seed * 0.37);
	float n = value_noise(q) * 0.65 + value_noise(q * 2.3 + 7.1) * 0.35;
	float wipe = smoothstep(0.55, 0.85, n);
	float low = (1.0 - smoothstep(-0.4, 0.6, p.y)) * 0.35 * value_noise(q * 0.7 + 3.0);
	return clamp(wipe + low, 0.0, 1.0);
}

#ifdef WINDOW_GLASS_RAIN
// ---------------------------------------------------------------- rain
// Heartfelt-style rain in the pane's meters (down = local -Y, so a tilted sash
// carries its drops along): a mist of micro-droplets (the blurred, haloed city),
// two layers of static beads, and runners that hang, grow, break loose and run
// down a wandering path, wiping a clear track through the mist and the beads,
// with a trail of tiny beads that dries out behind them.
//
// No shimmer: each layer fades by its drop size in pixels (fwidth) into the
// mist before its drops get sub-pixel; edges are anti-aliased over a pixel.

struct Drop {
	float mask;   // coverage of the strongest drop at this pixel (anti-aliased)
	vec2 q;       // from that drop's center (m)
	float r;      // its radius (m)
};

struct Rain {
	vec3 rgb;      // light coming through the rain layer, premultiplied by alpha
	float alpha;   // share of the view behind that the rain layer replaces
	float rough;   // extra roughness (wet film)
};

vec4 hash42(vec2 p) {
	vec4 p4 = fract(vec4(p.xyxy) * vec4(0.1031, 0.1030, 0.0973, 0.1099));
	p4 += dot(p4, p4.wzxy + 33.33);
	return fract((p4.xxyz + p4.yzzw) * p4.zywx);
}

// 1 at x <= a, 0 at x >= b (a < b); smoothstep with reversed edges is undefined in GLSL.
float fall(float a, float b, float x) {
	return 1.0 - smoothstep(a, b, x);
}

void take(inout Drop best, float mask, vec2 q, float r) {
	if (mask > best.mask) {
		best.mask = mask;
		best.q = q;
		best.r = r;
	}
}

// Anti-aliased disc: 1 inside radius r, over one pixel.
float disc(float d, float r, float px) {
	return fall(r - px * 0.5, r + px * 0.5, d) * step(1e-5, r);
}

// Layer detail from the drop radius in pixels: 1 while the radius is >= 2.2 px,
// 0 below 0.8 px (then only the mist stands for it).
float drop_detail(float px, float r) {
	return fall(0.45, 1.25, px / r);
}

// One bead per cell; beads come and go while it rains (rain_time), vanish one by
// one as the glass dries (rain_wet) and are wiped by runners (swept).
// share: cells holding a bead on wet glass.
void static_beads(vec2 p, float cell, float r_min, float r_max, float share, float seed, float px, float swept,
		inout Drop best) {
	float detail = drop_detail(px, 0.5 * (r_min + r_max));
	if (detail <= 0.0) {
		return;
	}
	vec2 uv = p / cell + seed;
	vec2 id = floor(uv);
	vec4 a = hash42(id);
	// A new bead lands in this cell every 15-45 s of rain; the old one shrinks away first.
	float cycle = rain_time / (15.0 + 30.0 * a.w) + a.z;
	vec4 n = hash42(id + floor(cycle) * 17.31);
	float life = fract(cycle);
	float present = smoothstep(n.w, n.w + 0.08, share * smoothstep(0.0, 1.0, rain_wet) * 1.08);
	float r = mix(r_min, r_max, n.z * n.z) * sqrt(present) * smoothstep(0.0, 0.02, life) * fall(0.85, 1.0, life)
			* (1.0 - swept);
	vec2 c = (n.xy - 0.5) * (cell - 2.0 * r_max);
	vec2 q = (fract(uv) - 0.5) * cell - c;
	take(best, disc(length(q), r, px) * detail, q, r);
}

// Normalized x of a runner's path (in column widths) at height y (0..1 in its cell).
float runner_x(float y, float x0, float phase) {
	return x0 + 0.05 * sin(y * 21.0 + phase) + 0.025 * sin(y * 53.0 + phase * 2.3);
}

// Runners: at most one per cell of RUN_COLUMN x RUN_CELL. Returns how clean the
// pixel is from a runner's fresh track (0..1).
const float RUN_COLUMN = 0.05;
const float RUN_CELL = 0.3;
float runners(vec2 p, float px, inout Drop best) {
	float col = floor(p.x / RUN_COLUMN);
	vec4 cn = hash42(vec2(col, 11.7));
	float y = p.y / RUN_CELL + cn.x;
	float row = floor(y);
	vec4 n = hash42(vec2(col, row) + 3.1);
	vec2 f = vec2(fract(p.x / RUN_COLUMN) - 0.5, fract(y));
	float present = smoothstep(n.x, n.x + 0.06, 0.55 * rain_wet * rain_wet);
	if (present <= 0.0) {
		return 0.0;
	}
	// Hang and grow, break loose, run down (faster and faster) to the cell bottom.
	float t = fract(rain_slide_time / (3.0 + 5.0 * n.y) + n.z);
	float hang = 0.3 + 0.35 * n.w;
	float run = clamp((t - hang) / (1.0 - hang), 0.0, 1.0);
	float top = 0.93;
	float yd = top - 0.88 * pow(run, 1.5);
	float x0 = (n.y - 0.5) * 0.35;
	float phase = n.w * 6.2832;
	float r = mix(0.0025, 0.0036, n.w) * mix(0.6, 1.0, smoothstep(0.0, hang, t)) * fall(0.94, 1.0, t) * sqrt(present);
	// The drop, a little taller while it runs.
	vec2 q = vec2((f.x - runner_x(yd, x0, phase)) * RUN_COLUMN, (f.y - yd) * RUN_CELL);
	float stretch = mix(1.0, 0.7, smoothstep(0.0, 0.1, run));
	take(best, disc(length(vec2(q.x, q.y * stretch)), r, px) * drop_detail(px, 0.003), q, r);

	// Its track, from where it broke loose: clean glass that mists over again behind it.
	float behind = (f.y - yd) * RUN_CELL;
	if (behind < 0.0 || f.y > top || run <= 0.0) {
		return 0.0;
	}
	float dx = abs(f.x - runner_x(f.y, x0, phase)) * RUN_COLUMN;
	float fresh = fall(0.0, 0.5, behind) * present;
	float band = fall(r * 0.3, r * 1.1 + px * 2.0, dx);
	// Tiny beads left in the track, about every 6 mm, shrinking as it dries.
	float step_m = 0.006;
	float k = floor(f.y * RUN_CELL / step_m);
	vec4 b = hash42(vec2(col * 7.0 + k, row));
	float by = (k + 0.5 + (b.x - 0.5) * 0.4) * step_m;
	vec2 bq = vec2((f.x - runner_x(by / RUN_CELL, x0, phase)) * RUN_COLUMN + (b.z - 0.5) * r * 0.7, f.y * RUN_CELL - by);
	float br = mix(0.0004, 0.0009, b.w) * fall(0.15, 0.45, behind) * step(0.3, b.y) * present;
	take(best, disc(length(bq), br, px) * drop_detail(px, 0.0007), bq, br);
	return band * fresh * 0.55;
}

// The rain layer at pane point p (already moved onto the outer face).
// px: meters per pixel; to_px: pane meters -> screen pixels; screen_uv, view_size: this pixel.
Rain rain(vec2 p, float px, mat2 to_px, vec2 screen_uv, vec2 view_size) {
	Rain w;
	w.rgb = vec3(0.0);
	w.alpha = 0.0;
	w.rough = 0.0;
	if (rain_wet <= 0.0 && rain_amount <= 0.0) {
		return w;
	}
	Drop best;
	best.mask = 0.0;
	best.q = vec2(0.0);
	best.r = 1.0;
	float swept = runners(p, px, best);
	static_beads(p, 0.005, 0.00075, 0.0014, 0.8, 3.7, px, swept, best);
	static_beads(p, 0.012, 0.0012, 0.003, 0.7, 9.1, px, swept, best);
	// Mist of micro-droplets (patchy, thicker while it pours), wiped by the runners.
	float patches = 0.65 + 0.35 * value_noise(p * 4.0 + v_seed);
	float mist = rain_wet * rain_mist * patches * (0.4 + 0.6 * rain_amount) * (1.0 - swept);
	// Beads too small to draw at this distance join the average.
	mist += rain_wet * 0.2 * (1.0 - drop_detail(px, 0.0018)) * (1.0 - swept);

	// A drop is a lens: a spherical cap showing a wider view, upside down and squeezed,
	// with a dark rim and a small highlight from the room.
	vec2 nq = best.q / max(best.r, 1e-5);
	nq /= max(1.0, length(nq));   // the anti-aliased edge lies a little outside r
	float rr = dot(nq, nq);
	float rim = mix(0.3, 1.0, fall(0.5, 1.0, rr));
	vec3 n = normalize(vec3(nq * 0.9, sqrt(max(1.0 - 0.81 * rr, 0.0))));
	// Only on drops wide enough to show it (a sub-pixel highlight would sparkle).
	float highlight = pow(max(dot(n, normalize(vec3(-0.25, 0.55, 0.8))), 0.0), 90.0)
			* smoothstep(1.5, 4.0, best.r / max(px, 1e-5));
	// The mist blurs over about 12 mm of glass, and at least ~6 px: far away it stands
	// for all the drops too small to draw (the wet average).
	float mist_lod = clamp(log2(0.012 / max(px, 1e-5)), 2.5, 6.0);
#ifdef WINDOW_GLASS_RAIN_SCREEN
	vec2 refr_px = to_px * (-best.q * rain_lens);
	vec2 refr_uv = clamp(screen_uv + refr_px / view_size, vec2(0.001), vec2(0.999));
	vec3 through = best.mask > 0.0 ? textureLod(screen_tex, refr_uv, 1.0).rgb : vec3(0.0);
	vec3 blur = mist > 0.0 ? textureLod(screen_tex, screen_uv, mist_lod).rgb : vec3(0.0);
#else
	// No screen read: drops and mist show a dim, cool average of the night city.
	vec3 through = rain_fallback_color;
	vec3 blur = rain_fallback_color;
#endif
	float dm = best.mask;
	vec3 drop_rgb = through * rim * 1.05 + rain_highlight * highlight;
	vec3 mist_rgb = blur * 0.9 + rain_mist_color;
	w.alpha = dm + (1.0 - dm) * mist;
	w.rgb = drop_rgb * dm + mist_rgb * mist * (1.0 - dm);
	w.rough = mist * 0.3;
	return w;
}

#endif

// ---------------------------------------------------------------- HUD shapes (units: meters)
float sd_segment(vec2 p, vec2 a, vec2 b) {
	vec2 pa = p - a;
	vec2 ba = b - a;
	float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * h);
}

float sd_round_box(vec2 p, vec2 half_size, float r) {
	vec2 d = abs(p) - half_size + r;
	return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r;
}

// Distance to the stroke centerlines of a 7-segment glyph (bits), p in digit heights, centered.
float sd_seven(vec2 p, int bits) {
	p.x -= p.y * SLANT;
	float w = DIGIT_W * 0.5;
	float g = 0.07;
	float d = 1e5;
	if ((bits & 1) != 0) d = min(d, sd_segment(p, vec2(-w + g, 0.5), vec2(w - g, 0.5)));
	if ((bits & 2) != 0) d = min(d, sd_segment(p, vec2(w, 0.5 - g), vec2(w, g)));
	if ((bits & 4) != 0) d = min(d, sd_segment(p, vec2(w, -g), vec2(w, -0.5 + g)));
	if ((bits & 8) != 0) d = min(d, sd_segment(p, vec2(-w + g, -0.5), vec2(w - g, -0.5)));
	if ((bits & 16) != 0) d = min(d, sd_segment(p, vec2(-w, -g), vec2(-w, -0.5 + g)));
	if ((bits & 32) != 0) d = min(d, sd_segment(p, vec2(-w, 0.5 - g), vec2(-w, g)));
	if ((bits & 64) != 0) d = min(d, sd_segment(p, vec2(-w + g, 0.0), vec2(w - g, 0.0)));
	return d - STROKE * 0.5;
}

float sd_digit(vec2 p, int digit) {
	if (digit < 0 || digit > 9) {
		return 1e5;
	}
	return sd_seven(p, SEGMENTS[digit]);
}

float sd_cloud(vec2 p) {
	float d = length(p - vec2(-0.2, -0.04)) - 0.19;
	d = min(d, length(p - vec2(0.04, 0.08)) - 0.25);
	d = min(d, length(p - vec2(0.26, -0.06)) - 0.17);
	d = min(d, sd_round_box(p - vec2(0.03, -0.15), vec2(0.36, 0.08), 0.08));
	return d;
}

// Filled weather glyph, p in glyph heights, centered.
float sd_weather(vec2 p, int kind) {
	if (kind == 0) {
		// Crescent moon.
		float outer = length(p) - 0.38;
		float inner = length(p - vec2(0.2, 0.14)) - 0.32;
		return max(outer, -inner);
	}
	if (kind == 3) {
		// Sun: a disc and eight short rays.
		float d = length(p) - 0.2;
		for (int i = 0; i < 8; i++) {
			vec2 dir = vec2(cos(float(i) * 0.7854), sin(float(i) * 0.7854));
			d = min(d, sd_segment(p, dir * 0.3, dir * 0.42) - 0.045);
		}
		return d;
	}
	if (kind == 2) {
		float d = sd_cloud((p - vec2(0.0, 0.16)) / 0.8) * 0.8;
		for (int i = 0; i < 3; i++) {
			float x = -0.2 + float(i) * 0.2;
			d = min(d, sd_segment(p, vec2(x + 0.05, -0.12), vec2(x - 0.03, -0.38)) - 0.045);
		}
		return d;
	}
	return sd_cloud(p);
}

// Signed distance (m) to the readout: time on top, weather and temperature below, right-aligned at the anchor.
float sd_hud(vec2 p) {
	float h1 = hud_height;
	float h2 = hud_height * 0.8;
	float gap = hud_height * 0.35;
	float d = 1e5;
	// Line 1, HH:MM, digits from the right.
	vec2 q = p - vec2(0.0, h2 + gap + h1 * 0.5);
	float x = -DIGIT_ADV * h1 * 0.5;
	if (abs(q.y) < h1 * 0.6 + HALO) {
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h1, hud_time.w) * h1);
		x -= DIGIT_ADV * h1;
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h1, hud_time.z) * h1);
		x -= DIGIT_ADV * h1 * 0.5 + 0.2 * h1;
		// Colon.
		d = min(d, length(q - vec2(x + 0.03 * h1, 0.2 * h1)) - STROKE * 0.6 * h1);
		d = min(d, length(q - vec2(x - 0.03 * h1, -0.2 * h1)) - STROKE * 0.6 * h1);
		x -= 0.2 * h1 + DIGIT_ADV * h1 * 0.5;
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h1, hud_time.y) * h1);
		x -= DIGIT_ADV * h1;
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h1, hud_time.x) * h1);
	}
	// Line 2: [glyph] [-]DD°
	q = p - vec2(0.0, h2 * 0.5);
	if (abs(q.y) < h2 * 0.6 + HALO) {
		x = -0.16 * h2;
		// Degree ring.
		d = min(d, abs(length(q - vec2(x, 0.34 * h2)) - 0.09 * h2) - STROKE * 0.35 * h2);
		x -= 0.2 * h2 + DIGIT_ADV * h2 * 0.5;
		int t = clamp(hud_temperature, -99, 99);
		int a = abs(t);
		d = min(d, sd_digit((q - vec2(x, 0.0)) / h2, a % 10) * h2);
		if (a >= 10) {
			x -= DIGIT_ADV * h2;
			d = min(d, sd_digit((q - vec2(x, 0.0)) / h2, a / 10) * h2);
		}
		if (t < 0) {
			x -= DIGIT_ADV * h2;
			d = min(d, sd_seven((q - vec2(x, 0.0)) / h2, SEG_MINUS) * h2);
		}
		x -= DIGIT_ADV * h2 * 0.5 + 0.55 * h2;
		d = min(d, sd_weather((q - vec2(x, 0.0)) / h2, hud_weather) * h2);
	}
	return d;
}

// ---------------------------------------------------------------- main
void fragment() {
	// Meters per pixel on the pane, taken before any branch (derivatives).
	float px = length(fwidth(v_local));
#ifdef WINDOW_GLASS_RAIN
	vec2 dx = dFdx(v_local);
	vec2 dy = dFdy(v_local);
#endif

	float m = smudges(v_local, v_seed) * smudge_amount;

#ifdef WINDOW_GLASS_RAIN
	// Rain sits on the outer face: follow this eye's ray rain_depth further out.
	vec3 to_cam = normalize(v_to_cam);
	vec2 rain_p = v_local - to_cam.xy * (to_cam.z > 0.0 ? rain_depth / max(to_cam.z, 0.25) : 0.0);
	float det = dx.x * dy.y - dy.x * dx.y;
	mat2 to_px = abs(det) > 1e-12 ? inverse(mat2(dx, dy)) : mat2(0.0);
	Rain r = rain(rain_p, px, to_px, SCREEN_UV, VIEWPORT_SIZE);
#endif

	float t = clamp(tint, 0.0, 1.0);
	float coverage = mix(clear_alpha, tint_alpha, t) + m * 0.02;
	vec3 color = mix(glass_color, tint_color, t);

	// Fresnel: at grazing angles glass reflects more and lets less through.
	float n_dot_v = clamp(abs(dot(normalize(NORMAL), normalize(VIEW))), 0.0, 1.0);
	float fresnel = pow(1.0 - n_dot_v, 5.0);
	coverage = clamp(coverage + (1.0 - coverage) * fresnel * 0.9, 0.0, 1.0);

	vec3 emission = tint_color * tint_glow * t;

	// Live reflection, on panes in the reflection's plane only (not a tilted vent):
	// Schlick's Fresnel with the glass's F0 (SPECULAR 0.5 = 0.04), added as light.
	float specular = clamp(reflectivity + tint_reflectivity * t, 0.0, 1.0);
	float live = 0.0;
	if (reflection_enabled > 0.0) {
		vec3 world_n = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
		live = reflection_enabled * smoothstep(0.998, 0.9999, abs(dot(world_n, reflection_normal)));
		if (live > 0.0) {
			vec3 world_pos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
			float f0 = 0.08 * specular;
			float reflect_f = f0 + (1.0 - f0) * fresnel;
			emission += planar_reflection(world_pos, VIEW_INDEX) * reflect_f * reflection_gain * live * (1.0 - m * 0.3);
		}
	}
	// The rain layer is outside: seen through the glass, over the view behind.
	// The glass itself (lit albedo) keeps its own coverage.
	float glass_coverage = coverage;
#ifdef WINDOW_GLASS_RAIN
	emission += r.rgb * (1.0 - coverage);
	coverage = 1.0 - (1.0 - coverage) * (1.0 - r.alpha);
#endif

	if (hud_enabled) {
		vec2 hp = v_local - hud_anchor;
		// Bounds of the readout (about 0.25 x 0.17 m plus the glow) before the shapes are evaluated.
		float pad = HALO + px * 3.0;
		if (hp.x < pad && hp.x > -hud_height * 3.6 - pad && hp.y > -pad && hp.y < hud_height * 2.2 + pad) {
			float d = sd_hud(hp);
			// Soft edges: at least 1.5 mm, or a pixel and a half far away (no aliasing).
			float aa = max(px * 1.5, 0.0015);
			float glyph = 1.0 - smoothstep(-aa, aa, d);
			float halo = (1.0 - smoothstep(0.0, HALO, d)) * 0.1;
			emission += hud_color * hud_energy * (glyph + halo);
			coverage = max(coverage, glyph * 0.25);
		}
	}

	ALBEDO = color * glass_coverage;
	ALPHA = coverage;
	PREMUL_ALPHA_FACTOR = 1.0;
	METALLIC = 0.0;
	// The probe's reflection (and the lamps' highlights) only where the live one isn't.
	SPECULAR = specular * (1.0 - live);
#ifdef WINDOW_GLASS_RAIN
	ROUGHNESS = clamp(roughness + m * 0.18 + r.rough, 0.0, 1.0);
#else
	ROUGHNESS = clamp(roughness + m * 0.18, 0.0, 1.0);
#endif
	EMISSION = emission;
}
