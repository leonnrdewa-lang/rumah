// Inverted-hull ink outline (next_pass of the toon material): back faces pushed out
// along the screen-space normal by a constant pixel width and drawn as dark ink.
shader_type spatial;
render_mode cull_front, unshaded, shadows_disabled, fog_disabled;

uniform vec4 line_color : source_color = vec4(0.04, 0.03, 0.05, 1.0);
uniform float width = 2.4;
uniform float fade = 1.0;

void vertex() {
	vec4 clip = PROJECTION_MATRIX * (MODELVIEW_MATRIX * vec4(VERTEX, 1.0));
	vec3 vn = mat3(MODELVIEW_MATRIX) * NORMAL;
	vec2 dir = (PROJECTION_MATRIX * vec4(vn, 0.0)).xy;
	float l = length(dir);
	if (l > 1e-5) {
		clip.xy += dir / l * width * (VIEWPORT_SIZE.y / 720.0) * 2.0 / VIEWPORT_SIZE * clip.w;
	}
	POSITION = clip;
}

void fragment() {
	ALBEDO = line_color.rgb;
	if (fade < 0.999) {
		float th = fract(52.9829189 * fract(dot(FRAGCOORD.xy, vec2(0.06711056, 0.00583715))));
		if (th > fade) { discard; }
	}
}
