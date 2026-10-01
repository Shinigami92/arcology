// Tileable PBR surface mapped in world space along the face's own axis (floors, walls,
// ceilings of the generated shell, D-035). One sample per map, unlike triplanar's three;
// only valid for flat, axis-aligned faces (BoxMesh). Textures: blender/surfaces/.
// Compiled as world_surface.gdshader (anisotropic, patterned floors seen at grazing angles)
// and world_surface_soft.gdshader (plain mipmaps: plaster, carpet; saves ~0.5 ms GPU).
#ifndef SURFACE_FILTER
#define SURFACE_FILTER filter_linear_mipmap_anisotropic
#endif

render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_texture : source_color, SURFACE_FILTER, repeat_enable;
uniform sampler2D orm_texture : hint_default_white, SURFACE_FILTER, repeat_enable;
uniform sampler2D normal_texture : hint_normal, SURFACE_FILTER, repeat_enable;
uniform vec4 albedo_tint : source_color = vec4(1.0);
uniform float tile_size = 4.0; // meters per texture tile
uniform float normal_scale = 1.0;
uniform float rim : hint_range(0.0, 1.0) = 0.0;
uniform float rim_tint : hint_range(0.0, 1.0) = 0.5;

varying vec2 world_uv;

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 wn = normalize(mat3(MODEL_MATRIX) * NORMAL);
	vec3 t;
	vec3 b; // toward the image's top (Godot normal maps are +Y up)
	if (abs(wn.y) >= max(abs(wn.x), abs(wn.z))) {
		// Floor tops and ceiling undersides: U along world X.
		t = vec3(1.0, 0.0, 0.0);
		b = vec3(0.0, 0.0, -sign(wn.y));
	} else {
		// Walls: image up = world up, U to the right as seen from the front.
		vec3 n = abs(wn.x) >= abs(wn.z) ? vec3(sign(wn.x), 0.0, 0.0) : vec3(0.0, 0.0, sign(wn.z));
		t = cross(vec3(0.0, 1.0, 0.0), n);
		b = vec3(0.0, 1.0, 0.0);
	}
	world_uv = vec2(dot(wp, t), -dot(wp, b)) / tile_size;
	mat3 to_model = inverse(mat3(MODEL_MATRIX));
	TANGENT = normalize(to_model * t);
	BINORMAL = normalize(to_model * b);
}

void fragment() {
	vec3 orm = texture(orm_texture, world_uv).rgb;
	ALBEDO = texture(albedo_texture, world_uv).rgb * albedo_tint.rgb;
	AO = orm.r;
	AO_LIGHT_AFFECT = 0.0;
	ROUGHNESS = orm.g;
	METALLIC = orm.b;
	NORMAL_MAP = texture(normal_texture, world_uv).rgb;
	NORMAL_MAP_DEPTH = normal_scale;
	RIM = rim;
	RIM_TINT = rim_tint;
}
