// Double-sided foliage (palm fronds, leaves, grass): wind sway, vertex-colour AO,
// optional albedo texture, see-through near the player. See foliage_body.gdshaderinc.
shader_type spatial;
render_mode cull_disabled, specular_disabled;

#define TOON_BACKLIGHT
#include "res://shaders/toon_light.gdshaderinc"

#include "res://shaders/foliage_body.gdshaderinc"
