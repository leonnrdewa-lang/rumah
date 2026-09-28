// Full-screen anime colour grade, drawn on a CanvasLayer between the 3D world and
// the HUD (ui.gd): vibrance that lifts dull greens most, teal-blue shadows and warm
// cream highlights (split toning), a soft bloom haze, a gentle vignette and a very
// fine film grain. Cheap: 5 screen fetches.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear, repeat_disable;
uniform float amount = 1.0;
uniform float vibrance = 0.3;
uniform float green_boost = 0.06;
uniform vec3 shadow_tint = vec3(0.05, 0.11, 0.24);
uniform vec3 high_tint = vec3(1.04, 0.99, 0.9);
uniform float haze = 0.22;
uniform float vignette = 0.32;
uniform float grain = 0.018;
global uniform float night;

void fragment() {
	vec3 src = texture(screen_tex, SCREEN_UV).rgb;
	vec3 c = src;
	// soft bloom haze: a wide 4-tap blur, only the bright parts
	vec2 px = SCREEN_PIXEL_SIZE * 9.0;
	vec3 b = texture(screen_tex, SCREEN_UV + vec2(px.x, px.y)).rgb + texture(screen_tex, SCREEN_UV + vec2(-px.x, px.y)).rgb
		+ texture(screen_tex, SCREEN_UV + vec2(px.x, -px.y)).rgb + texture(screen_tex, SCREEN_UV - px).rgb;
	b *= 0.25;
	c += max(b - vec3(0.55), vec3(0.0)) * haze * (1.0 + night);
	// vibrance: dull colours gain the most saturation; greens get a little extra
	float l = dot(c, vec3(0.299, 0.587, 0.114));
	float mx = max(c.r, max(c.g, c.b));
	float mn = min(c.r, min(c.g, c.b));
	float s = mx - mn;
	float green = smoothstep(0.0, 0.08, c.g - max(c.r, c.b) + 0.03);
	c = mix(vec3(l), c, 1.0 + (vibrance + green_boost * green) * (1.0 - s) * (1.0 - 0.7 * night));
	c.g += green * green_boost * 0.12 * (1.0 - night);
	// split toning
	c += shadow_tint * (1.0 - smoothstep(0.0, 0.45, l)) * 0.5;
	c *= mix(vec3(1.0), high_tint, smoothstep(0.45, 0.95, l));
	// vignette
	vec2 d = (SCREEN_UV - 0.5) * vec2(1.0, 0.8);
	c *= 1.0 - vignette * smoothstep(0.12, 0.55, dot(d, d) * 2.0);
	// grain
	float g = fract(sin(dot(FRAGCOORD.xy + fract(TIME) * 61.0, vec2(12.9898, 78.233))) * 43758.5453);
	c += (g - 0.5) * grain;
	COLOR = vec4(mix(src, clamp(c, 0.0, 1.0), amount), 1.0);
}
