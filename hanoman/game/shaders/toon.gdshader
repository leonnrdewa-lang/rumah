// Painted toon shading for every model (Hades-like): three hard light bands, a
// cool-tinted shadow side, a warm rim on the lit edge, and a faint world-space
// brush-stroke texture so flat colours read as paint. `glow` turns the material
// into an emissive accent (eyes, flames, flowers). `flash` whitens on hit.
shader_type spatial;
render_mode cull_back, specular_disabled;

uniform vec4 albedo : source_color = vec4(0.8, 0.8, 0.8, 1.0);
uniform float glow = 0.0;
uniform float flash = 0.0;
uniform vec4 flash_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform vec3 shadow_tint = vec3(0.42, 0.45, 0.72);
uniform float rim = 0.55;
uniform float fade = 1.0;
uniform sampler2D brush : filter_linear_mipmap, repeat_enable;

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize(mat3(MODEL_MATRIX) * NORMAL);
}

void fragment() {
	vec3 an = abs(wnrm);
	vec2 uv = an.y > 0.6 ? wpos.xz : (an.x > an.z ? wpos.zy : wpos.xy);
	float b = texture(brush, uv * 0.35).r;
	vec3 c = albedo.rgb * (0.9 + 0.2 * b);
	c = mix(c, flash_color.rgb, flash);
	ALBEDO = c;
	EMISSION = albedo.rgb * glow * (0.85 + 0.3 * b) + flash_color.rgb * flash * 0.25;
	if (fade < 0.999) {
		float th = fract(52.9829189 * fract(dot(FRAGCOORD.xy, vec2(0.06711056, 0.00583715))));
		if (th > fade) { discard; }
	}
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float sh = ATTENUATION;
	float lit = smoothstep(-0.05, 0.05, ndl) * 0.6 + smoothstep(0.45, 0.52, ndl) * 0.4;
	lit *= smoothstep(0.3, 0.6, sh);
	vec3 base = mix(shadow_tint * 0.35, vec3(1.0), lit);
	DIFFUSE_LIGHT += LIGHT_COLOR * base * 0.33;
	float r = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	r = smoothstep(0.62, 0.7, r) * smoothstep(-0.2, 0.3, ndl);
	DIFFUSE_LIGHT += LIGHT_COLOR * r * rim * 0.33;
}
