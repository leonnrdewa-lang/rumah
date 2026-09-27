// Stylised opaque material for every imported model (buildings, props, characters, trunks).
// Optional albedo texture, vertex-colour AO, soft wrap lighting and the see-through
// hole around the player. See world_body.gdshaderinc.
shader_type spatial;
render_mode cull_back, diffuse_lambert_wrap, specular_disabled;

#include "res://shaders/world_body.gdshaderinc"
