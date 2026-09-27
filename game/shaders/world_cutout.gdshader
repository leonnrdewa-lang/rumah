// Alpha-scissored, double-sided variant of world.gdshader (glTF alphaMode MASK
// materials that are not foliage: fences, signs, decals like the piringan).
shader_type spatial;
render_mode cull_disabled, diffuse_lambert_wrap, specular_disabled;

#define ALPHA_CUT
#include "res://shaders/world_body.gdshaderinc"
