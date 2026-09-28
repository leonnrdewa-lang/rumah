// Alpha-scissored, double-sided variant of world.gdshader (glTF alphaMode MASK
// materials that are not foliage: fences, signs, decals like the piringan).
shader_type spatial;
render_mode cull_disabled, specular_disabled;

#include "res://shaders/toon_light.gdshaderinc"

#define ALPHA_CUT
#include "res://shaders/world_body.gdshaderinc"
