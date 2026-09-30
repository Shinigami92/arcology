shader_type spatial;
// Window glass, dry (D-033): see window_glass.gdshaderinc. RainOnGlass swaps in
// window_glass_wet.gdshader while it rains.
render_mode blend_premul_alpha, cull_disabled, depth_draw_opaque, diffuse_burley, specular_schlick_ggx;

#include "res://assets/shaders/window_glass.gdshaderinc"
