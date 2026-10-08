// Flying vehicle body: the shared traffic_vehicle atlas, moved along its lane
// (traffic_lane.gdshaderinc). Placeholder boxes have no textures: paint only.
shader_type spatial;
render_mode cull_back;

#include "res://assets/shaders/traffic_lane.gdshaderinc"

uniform sampler2D albedo_tex : source_color, hint_default_white, filter_linear_mipmap_anisotropic;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D emission_tex : source_color, hint_default_black, filter_linear_mipmap_anisotropic;
uniform vec3 paint : source_color = vec3(1.0);
uniform float emission_energy = 4.0;

void vertex() {
	float time = TIME * time_scale;
	float t = lane_t(INSTANCE_CUSTOM, time);
	VERTEX = VERTEX * lane_scale(t, INSTANCE_CUSTOM.z) + lane_offset(INSTANCE_CUSTOM, t, time);
}

void fragment() {
	vec3 orm = texture(orm_tex, UV).rgb;
	ALBEDO = texture(albedo_tex, UV).rgb * paint;
	AO = orm.r;
	ROUGHNESS = orm.g;
	METALLIC = orm.b;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	EMISSION = texture(emission_tex, UV).rgb * emission_energy;
}
