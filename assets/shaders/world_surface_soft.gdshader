// Plain-mipmap variant of world_surface.gdshaderinc: plaster, carpet.
shader_type spatial;

#define SURFACE_FILTER filter_linear_mipmap
#include "res://assets/shaders/world_surface.gdshaderinc"
