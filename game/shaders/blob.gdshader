// Fake contact shadow / ambient occlusion decal: a flat quad lying on the ground
// that darkens it softly (round blob under characters, rounded rectangle around
// building footprints). Unshaded, alpha blended, never writes depth.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix, shadows_disabled, fog_disabled;

global uniform float night;

uniform vec4 color : source_color = vec4(0.13, 0.17, 0.07, 0.42);
uniform float shape = 0.0;            // 0 = round blob, 1 = rounded rectangle
uniform vec2 quad_size = vec2(2.0);   // metres covered by the quad (x, z)
uniform vec2 inner_half = vec2(0.5);  // rectangle: half size of the solid core
uniform float margin = 1.0;           // rectangle: fade distance outside the core

void fragment() {
	vec2 p = (UV - 0.5) * quad_size;
	float a;
	if (shape < 0.5) {
		float r = length((UV - 0.5) * 2.0);
		a = exp(-3.2 * r * r) * (1.0 - smoothstep(0.8, 1.0, r));
	} else {
		vec2 q = max(abs(p) - inner_half, vec2(0.0));
		float d = length(q);
		a = 1.0 - smoothstep(0.0, margin, d);
		a *= a;
	}
	ALBEDO = color.rgb;
	ALPHA = clamp(color.a * a * (1.0 - night * 0.5), 0.0, 1.0);
}
