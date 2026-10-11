// Dialogue portrait: soft fade at the bottom edge, optional slide-in tint, and a
// subtle painted rim glow so plain renders sit well over the dark dialogue scrim.
shader_type canvas_item;

uniform float fade_bottom = 0.18;
uniform float dark = 0.0;
uniform vec4 glow_color : source_color = vec4(0.4, 0.9, 0.8, 1.0);

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	c.a *= smoothstep(0.0, fade_bottom, 1.0 - UV.y);
	c.rgb = mix(c.rgb, c.rgb * 0.25, dark);
	COLOR = c;
}
