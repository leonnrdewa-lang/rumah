// Alpha-card foliage (glTF alphaMode MASK): foliage.gdshader + alpha scissor.
shader_type spatial;
render_mode cull_disabled, diffuse_lambert_wrap, specular_disabled;

#define ALPHA_CUT
#include "res://shaders/foliage_body.gdshaderinc"
