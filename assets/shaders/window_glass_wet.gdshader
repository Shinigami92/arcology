shader_type spatial;
// Window glass with rain on the outside (D-034): see window_glass.gdshaderinc.
render_mode blend_premul_alpha, cull_disabled, depth_draw_opaque, diffuse_burley, specular_schlick_ggx;

#define WINDOW_GLASS_RAIN
// Refraction through the screen texture (+0.6 ms p95 at full rain, D-034). Comment out for the flat fallback.
#define WINDOW_GLASS_RAIN_SCREEN
#include "res://assets/shaders/window_glass.gdshaderinc"
