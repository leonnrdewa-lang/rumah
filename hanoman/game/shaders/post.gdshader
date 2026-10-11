// Full-screen painted grade: deepen shadows toward blue-violet, lift saturated
// accents, a soft bloom haze on bright glows, strong vignette and paper grain.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear, repeat_disable;
uniform float haze = 0.25;
uniform float vignette = 0.62;
uniform float grain = 0.03;
uniform vec3 shadow_tint = vec3(0.03, 0.02, 0.08);
uniform float hurt = 0.0;
uniform vec4 flash = vec4(0.0);

void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	vec2 px = SCREEN_PIXEL_SIZE * 7.0;
	vec3 b = texture(screen_tex, SCREEN_UV + vec2(px.x, px.y)).rgb + texture(screen_tex, SCREEN_UV + vec2(-px.x, px.y)).rgb
		+ texture(screen_tex, SCREEN_UV + vec2(px.x, -px.y)).rgb + texture(screen_tex, SCREEN_UV - px).rgb
		+ texture(screen_tex, SCREEN_UV + vec2(px.x * 2.2, 0.0)).rgb + texture(screen_tex, SCREEN_UV - vec2(px.x * 2.2, 0.0)).rgb;
	b /= 6.0;
	c += max(b - vec3(0.5), vec3(0.0)) * haze;
	float l = dot(c, vec3(0.299, 0.587, 0.114));
	c += shadow_tint * (1.0 - smoothstep(0.0, 0.35, l)) * 0.6;
	float mx = max(c.r, max(c.g, c.b));
	float mn = min(c.r, min(c.g, c.b));
	c = mix(vec3(l), c, 1.0 + 0.12 * (1.0 - (mx - mn)));
	vec2 d = (SCREEN_UV - 0.5) * vec2(1.0, 0.85);
	float v = smoothstep(0.1, 0.6, dot(d, d) * 2.2);
	c *= 1.0 - vignette * v;
	c = mix(c, vec3(0.55, 0.0, 0.03), hurt * v * 0.8);
	float g = fract(sin(dot(FRAGCOORD.xy + fract(TIME) * 61.0, vec2(12.9898, 78.233))) * 43758.5453);
	c += (g - 0.5) * grain;
	c = mix(c, flash.rgb, flash.a);
	COLOR = vec4(clamp(c, 0.0, 1.0), 1.0);
}
