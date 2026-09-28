// Alpha-card foliage (glTF alphaMode MASK): foliage.gdshader + alpha scissor.
shader_type spatial;
render_mode cull_disabled, specular_disabled;

#define TOON_BACKLIGHT
#include "res://shaders/toon_light.gdshaderinc"

#define ALPHA_CUT
#include "res://shaders/foliage_body.gdshaderinc"
