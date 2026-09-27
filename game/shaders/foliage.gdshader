// Double-sided foliage (palm fronds, leaves, grass): wind sway, vertex-colour AO,
// optional albedo texture, see-through near the player. See foliage_body.gdshaderinc.
shader_type spatial;
render_mode cull_disabled, diffuse_lambert_wrap, specular_disabled;

#include "res://shaders/foliage_body.gdshaderinc"
