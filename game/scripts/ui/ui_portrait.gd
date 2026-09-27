extends Control
## Speaker portrait layer for dialogs and shop menus. It lives outside the
## modal panels so a portrait can persist across chained dialog lines:
##  * slides + fades in when a conversation starts,
##  * breathes (idle bob) and bounces lightly while the text is typing,
##  * when the speaker changes, the old portrait dims and slides away while the
##    new one slides in; when the conversation ends it slides out.
## Two looks: the 2D anime half-body art (assets/portraits/<name>.png, soft fade
## at the waist cut; art delivered with an opaque background is shown as a
## rounded card instead) or, as a fallback, the 3D head render in a round
## cream badge with the head popping out above the circle.

const SHADER_CODE := """
shader_type canvas_item;
uniform float fade_bottom = 0.0;
uniform bool badge = false;
uniform vec2 circle_center = vec2(0.5, 0.58);
uniform float circle_radius = 0.41;
uniform float corner_px = 0.0;
uniform vec2 size_px = vec2(1.0);
void fragment() {
	float a = 1.0;
	if (corner_px > 0.0) {
		// rounded-card clip for art that came with an opaque background
		vec2 p = UV * size_px;
		vec2 q = min(p, size_px - p);
		if (q.x < corner_px && q.y < corner_px) {
			float d = length(vec2(corner_px) - q);
			a *= 1.0 - smoothstep(corner_px - 1.2, corner_px, d);
		}
	}
	if (badge) {
		float d = length(UV - circle_center);
		a = 1.0 - smoothstep(circle_radius - 0.01, circle_radius, d);
		if (UV.y < circle_center.y) {
			a = 1.0;
		}
	}
	if (fade_bottom > 0.0) {
		a *= smoothstep(0.0, fade_bottom, 1.0 - UV.y);
	}
	COLOR.a *= a;
}
"""

var talking := false
var cur: Control
var cur_key := ""
var cur_art := false
var _cur_born := 0.0
var _t := 0.0
var _shader: Shader


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func has_portrait() -> bool:
	return cur != null


func present(key: String, tex: Texture2D, is_art: bool, rect: Rect2, animate := true) -> void:
	## Shows `tex` for speaker `key` in `rect` (canvas coordinates). Calling it
	## again for the same speaker just glides the portrait to the new rect.
	if tex == null:
		hide_portrait()
		return
	if cur and cur_key == key and cur_art == is_art:
		if not cur.get_rect().is_equal_approx(rect):
			if _t - _cur_born < 0.2:
				cur.position = rect.position
				cur.size = rect.size
			else:
				var tw := cur.create_tween().set_parallel().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
				tw.tween_property(cur, "position", rect.position, 0.2)
				tw.tween_property(cur, "size", rect.size, 0.2)
		cur.pivot_offset = Vector2(rect.size.x * 0.5, rect.size.y)
		return
	var swapping := cur != null
	if cur:
		_dismiss(cur, true)
	cur = _make_holder(tex, is_art, rect)
	cur_key = key
	cur_art = is_art
	_cur_born = _t
	add_child(cur)
	if animate or swapping:
		var bob: Control = cur.get_child(0)
		cur.modulate = Color(1, 1, 1, 0)
		bob.position.x = -46.0 if not swapping else -30.0
		var tw := cur.create_tween().set_parallel()
		tw.tween_property(cur, "modulate", Color.WHITE, 0.22)
		tw.tween_property(bob, "position:x", 0.0, 0.34).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


func hide_portrait() -> void:
	if cur:
		_dismiss(cur, false)
	cur = null
	cur_key = ""


func _dismiss(node: Control, swapped: bool) -> void:
	var bob: Control = node.get_child(0)
	node.set_meta("dying", true)
	var tw := node.create_tween().set_parallel()
	if swapped:
		# the previous speaker steps back: darker, smaller, sliding away
		node.modulate = Color(0.62, 0.6, 0.66, 1.0)
		tw.tween_property(node, "modulate", Color(0.45, 0.43, 0.5, 0.0), 0.26)
		tw.tween_property(bob, "position:x", -60.0, 0.26).set_ease(Tween.EASE_IN)
		tw.tween_property(bob, "scale", Vector2(0.94, 0.94), 0.26)
	else:
		tw.tween_property(node, "modulate:a", 0.0, 0.18)
		tw.tween_property(bob, "position:x", -36.0, 0.18).set_ease(Tween.EASE_IN)
	tw.chain().tween_callback(node.queue_free)


func _material(fade_bottom: float, badge: bool, center := Vector2(0.5, 0.58), radius := 0.41) -> ShaderMaterial:
	if _shader == null:
		_shader = Shader.new()
		_shader.code = SHADER_CODE
	var m := ShaderMaterial.new()
	m.shader = _shader
	m.set_shader_parameter("fade_bottom", fade_bottom)
	m.set_shader_parameter("badge", badge)
	m.set_shader_parameter("circle_center", center)
	m.set_shader_parameter("circle_radius", radius)
	return m


func _make_holder(tex: Texture2D, is_art: bool, rect: Rect2) -> Control:
	var holder := Control.new()
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.position = rect.position
	holder.size = rect.size
	holder.pivot_offset = Vector2(rect.size.x * 0.5, rect.size.y)
	var bob := Control.new()
	bob.name = "Bob"
	bob.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bob.set_anchors_preset(Control.PRESET_FULL_RECT)
	holder.add_child(bob)
	if is_art:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_SCALE
		tr.set_anchors_preset(Control.PRESET_FULL_RECT)
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if tex.has_meta("framed"):
			var card := Panel.new()
			var cs := StyleBoxFlat.new()
			cs.bg_color = Color("fffaf0")
			cs.set_corner_radius_all(24)
			cs.shadow_color = Color(0.2, 0.12, 0.04, 0.3)
			cs.shadow_size = 12
			cs.shadow_offset = Vector2(0, 4)
			card.add_theme_stylebox_override("panel", cs)
			card.set_anchors_preset(Control.PRESET_FULL_RECT)
			card.mouse_filter = Control.MOUSE_FILTER_IGNORE
			bob.add_child(card)
			var m := _material(0.0, false)
			m.set_shader_parameter("corner_px", 22.0)
			m.set_shader_parameter("size_px", rect.size)
			tr.material = m
			tr.name = "Framed"
			bob.add_child(tr)
			var edge := Panel.new()
			var es := StyleBoxFlat.new()
			es.draw_center = false
			es.set_corner_radius_all(24)
			es.border_color = Color("fffaf0")
			es.set_border_width_all(5)
			es.anti_aliasing = true
			edge.add_theme_stylebox_override("panel", es)
			edge.set_anchors_preset(Control.PRESET_FULL_RECT)
			edge.mouse_filter = Control.MOUSE_FILTER_IGNORE
			bob.add_child(edge)
			return holder
		tr.material = _material(0.06, false)
		bob.add_child(tr)
	else:
		# round cream badge; the render is drawn 1.24x bigger, bottom-aligned,
		# clipped to the circle below its centre so the head pops out on top
		var circle := Panel.new()
		var s := StyleBoxFlat.new()
		s.bg_color = Color("f6e6c4")
		s.set_corner_radius_all(512)
		s.border_color = Color("fffaf0")
		s.set_border_width_all(5)
		s.shadow_color = Color(0.25, 0.14, 0.05, 0.28)
		s.shadow_size = 10
		s.shadow_offset = Vector2(0, 4)
		s.anti_aliasing = true
		circle.add_theme_stylebox_override("panel", s)
		circle.set_anchors_preset(Control.PRESET_FULL_RECT)
		circle.mouse_filter = Control.MOUSE_FILTER_IGNORE
		bob.add_child(circle)
		var ring := Panel.new()
		var rs := StyleBoxFlat.new()
		rs.draw_center = false
		rs.set_corner_radius_all(512)
		rs.border_color = Color("d8c29a")
		rs.set_border_width_all(2)
		rs.anti_aliasing = true
		ring.add_theme_stylebox_override("panel", rs)
		ring.set_anchors_preset(Control.PRESET_FULL_RECT)
		ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
		# head renders pop out of the circle; flat icons sit inside it
		var bust := tex.has_meta("bust")
		var k := 1.24 if bust else 0.78
		var d := rect.size.x
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_SCALE
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		tr.set_anchors_preset(Control.PRESET_TOP_LEFT)
		tr.size = Vector2(k * d, k * d)
		if bust:
			tr.position = Vector2(-(k - 1.0) * 0.5 * d, d - k * d - d * 0.02)
			var cy := (k * d - d * 0.5 + d * 0.02) / (k * d)
			tr.material = _material(0.0, true, Vector2(0.5, cy), (d * 0.5 - 4.0) / (k * d))
		else:
			tr.position = Vector2(d - k * d, d - k * d) * 0.5
		bob.add_child(tr)
		bob.add_child(ring)
	return holder


func _process(delta: float) -> void:
	_t += delta
	if cur == null or not is_instance_valid(cur):
		return
	var bob: Control = cur.get_child(0)
	var framed: TextureRect = bob.get_node_or_null("Framed")
	if framed:
		(framed.material as ShaderMaterial).set_shader_parameter("size_px", framed.size)
	var breathe := sin(_t * TAU / 2.6)
	var y := breathe * 2.2
	if talking:
		y -= absf(sin(_t * 9.0)) * 2.4
	bob.position.y = y
	bob.pivot_offset = Vector2(cur.size.x * 0.5, cur.size.y)
	bob.scale = Vector2(1.0 - breathe * 0.003, 1.0 + breathe * 0.006)
