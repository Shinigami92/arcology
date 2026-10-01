// Anisotropic variant of world_surface.gdshaderinc: vinyl, concrete.
shader_type spatial;

#define SURFACE_FILTER filter_linear_mipmap_anisotropic
#include "res://assets/shaders/world_surface.gdshaderinc"
