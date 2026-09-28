// Interaction ring: a dashed cream circle like the target's (the ring round the palm
// being harvested), turning slowly. Mesh: world.gd's TorusMesh.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_back, shadows_disabled;

global uniform float wind_time;
uniform vec4 color : source_color = vec4(1.0, 0.98, 0.9, 0.9);
uniform float dashes = 14.0;

varying float ang;

void vertex() {
	ang = atan(VERTEX.z, VERTEX.x);
}

void fragment() {
	float d = fract(ang / 6.2831853 * dashes + wind_time * 0.12);
	if (d > 0.62) {
		discard;
	}
	ALBEDO = color.rgb;
	ALPHA = color.a;
}
