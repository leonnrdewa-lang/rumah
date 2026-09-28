// Inverted-hull ink outline (next_pass of the world material): the back faces are
// pushed out along the normal by a constant width in pixels and drawn dark, giving
// the anime line art around characters, buildings and props. It skips the
// see-through hole around the player like the base material.
shader_type spatial;
render_mode cull_front, unshaded, shadows_disabled, fog_disabled;

global uniform vec2 occlude_center;
global uniform float occlude_depth;
global uniform float occlude_radius;

uniform vec4 line_color : source_color = vec4(0.17, 0.1, 0.09, 1.0);
uniform float width = 1.8;
uniform float fade_enabled = 1.0;
// 0 collapses the hull outside the clip volume ("Hemat baterai")
uniform float enabled = 1.0;

void vertex() {
	vec4 clip = PROJECTION_MATRIX * (MODELVIEW_MATRIX * vec4(VERTEX, 1.0));
	vec3 vn = mat3(MODELVIEW_MATRIX) * NORMAL;
	vec2 dir = (PROJECTION_MATRIX * vec4(vn, 0.0)).xy;
	float l = length(dir);
	if (l > 1e-5) {
		clip.xy += dir / l * width * 2.0 / VIEWPORT_SIZE * clip.w;
	}
	POSITION = enabled > 0.5 ? clip : vec4(2.0, 2.0, 2.0, 1.0);
}

void fragment() {
	ALBEDO = line_color.rgb;
	if (fade_enabled > 0.5) {
		vec2 d = (SCREEN_UV - occlude_center) * vec2(VIEWPORT_SIZE.x / VIEWPORT_SIZE.y, 1.0);
		float r = length(d);
		if (-VERTEX.z < occlude_depth - 1.2 && r < occlude_radius) {
			float th = fract(52.9829189 * fract(dot(FRAGCOORD.xy, vec2(0.06711056, 0.00583715))));
			if (th < smoothstep(occlude_radius, occlude_radius * 0.5, r) * 0.85) {
				discard;
			}
		}
	}
}
