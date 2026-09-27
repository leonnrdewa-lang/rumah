extends Control
## Dialog box (built by ui.gd:dialog), laid out like the target screenshot
## (art/reference/07_target_gameplay.png): a compact cream panel at the bottom
## centre; top row = round portrait badge + speech bubble (speaker name on
## top, the line types out below, a small tail points at the speaker); below,
## the choices as rounded pills with dark dot bullets in a 2-column grid.
##
## Two portrait modes, picked automatically:
##  * fallback (no anime art yet): the 3D head render in a round badge inside
##    the panel's top-left corner (built here, so it moves with the panel);
##  * half-body art (assets/portraits/<key>.png exists): the portrait stands on
##    the panel's left edge and rises above it (drawn by the UI's PortraitStage
##    so it persists / swaps across chained lines), the bubble and choices fill
##    the rest of the panel.

const PortraitStage := preload("res://scripts/ui/ui_portrait.gd")
const NAME_COLOR := Color("9a5b2e")

var ui: Node
var key := ""
var speaker := ""
var text := ""
var choices: Array = []
var art: Texture2D        ## anime half-body (already cropped to its opaque area) or null
var badge_tex: Texture2D  ## fallback portrait (3D render / icon) for the round badge
var chained := false      ## opened right after another dialog line
var speaker_changed := true

var panel: PanelContainer
var col: VBoxContainer
var top_row: HBoxContainer
var bubble: PanelContainer
var badge_room: Control
var badge: Control
var name_label: Label
var body: Label
var grid: GridContainer
var scrim: TextureRect
var buttons: Array = []
var portrait_rect := Rect2()  ## canvas rect of the half-body art (empty in badge mode)
var _queued := false
var _panel_style: StyleBoxFlat
var _t := 0.0


func setup(p_key: String, p_speaker: String, p_text: String, p_choices: Array, p_art: Texture2D, p_badge: Texture2D, p_chained: bool, p_changed: bool) -> void:
	key = p_key
	speaker = p_speaker
	text = p_text
	choices = p_choices
	art = p_art
	badge_tex = p_badge
	chained = p_chained
	speaker_changed = p_changed
	set_meta("self_layout", true)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build()


func _build() -> void:
	# soft dark gradient behind the panel so text pops over busy foliage
	scrim = TextureRect.new()
	var g := Gradient.new()
	g.set_color(0, Color(0.1, 0.07, 0.03, 0.0))
	g.set_color(1, Color(0.1, 0.07, 0.03, 0.26))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill_from = Vector2(0, 0)
	gt.fill_to = Vector2(0, 1)
	gt.width = 4
	gt.height = 64
	scrim.texture = gt
	scrim.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	scrim.stretch_mode = TextureRect.STRETCH_SCALE
	scrim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(scrim)

	panel = PanelContainer.new()
	_panel_style = ui._box(ui.CREAM, 24, ui.LINE, 3, true)
	_panel_style.shadow_size = 14
	_panel_style.shadow_offset = Vector2(0, 5)
	_panel_style.shadow_color = Color(0.2, 0.12, 0.04, 0.3)
	ui._margins(_panel_style, 16, 16, 16, 16)
	panel.add_theme_stylebox_override("panel", _panel_style)
	panel.gui_input.connect(_on_panel_input)
	add_child(panel)
	col = VBoxContainer.new()
	col.add_theme_constant_override("separation", 12)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(col)

	# top row: [round badge] [speech bubble]
	top_row = HBoxContainer.new()
	top_row.add_theme_constant_override("separation", 16)
	top_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(top_row)
	badge_room = Control.new()
	badge_room.mouse_filter = Control.MOUSE_FILTER_IGNORE
	badge_room.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	top_row.add_child(badge_room)
	badge_room.visible = art == null  # the badge itself is built by relayout()

	bubble = _Bubble.new()
	bubble.fill = ui.CREAM_LIGHT
	bubble.line = ui.LINE
	bubble.anchor_node = badge_room if art == null else null
	var bs: StyleBoxFlat = ui._box(ui.CREAM_LIGHT, 18, ui.LINE, 2)
	ui._margins(bs, 18, 9, 18, 12)
	bubble.add_theme_stylebox_override("panel", bs)
	bubble.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bubble.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bubble.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	top_row.add_child(bubble)
	var bcol := VBoxContainer.new()
	bcol.add_theme_constant_override("separation", 0)
	bcol.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bubble.add_child(bcol)
	name_label = ui._label(speaker, 17, NAME_COLOR, true)
	name_label.name = "Speaker"
	bcol.add_child(name_label)
	body = ui._label(text, 22, ui.BROWN)
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_constant_override("line_spacing", 2)
	# lay out the whole line up front: the bubble must not grow (and the panel
	# jump up) while the typewriter reveals it
	body.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	body.visible_characters = 0
	bcol.add_child(body)

	grid = GridContainer.new()
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 10)
	grid.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(grid)
	var i := 1
	for c in choices:
		var b := _make_choice(i, c)
		grid.add_child(b)
		buttons.append(b)
		i += 1

	panel.minimum_size_changed.connect(_queue_relayout)
	grid.minimum_size_changed.connect(_queue_relayout)


func _make_choice(i: int, c: Dictionary) -> Button:
	var b := Button.new()
	b.theme_type_variation = "ChoiceButton"
	b.disabled = not c.get("enabled", true)
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	b.focus_mode = Control.FOCUS_ALL
	b.mouse_filter = Control.MOUSE_FILTER_STOP
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.set_anchors_preset(Control.PRESET_FULL_RECT)
	row.offset_left = 14
	row.offset_right = -14
	row.offset_top = 5
	row.offset_bottom = -5
	row.add_theme_constant_override("separation", 12)
	b.add_child(row)
	var touch: bool = ui._touch_mode
	# dark dot bullet; on keyboard devices it carries the number shortcut
	var dsz := 18 if touch else 24
	var dot := PanelContainer.new()
	dot.name = "Dot"
	dot.custom_minimum_size = Vector2(dsz, dsz)
	dot.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dot.add_theme_stylebox_override("panel", ui._box(ui.INK if not b.disabled else Color("b5a38a"), 14))
	if not touch:
		var n: Label = ui._label(str(i), 14, ui.CREAM_LIGHT, true)
		n.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		n.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		dot.add_child(n)
	row.add_child(dot)
	var tc := VBoxContainer.new()
	tc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tc.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	tc.add_theme_constant_override("separation", -2)
	tc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(tc)
	var tl: Label = ui._label(str(c.get("text", "")), 20, ui.BROWN)
	tl.add_theme_font_override("font", ui._font_medium)
	tl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	tc.add_child(tl)
	var hint := str(c.get("hint", ""))
	if hint != "":
		var hl: Label = ui._label(hint, 15, ui.BROWN_SOFT)
		hl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		tc.add_child(hl)
	if b.disabled:
		row.modulate = Color(1, 1, 1, 0.55)
	var min_h := 52.0 if touch else 46.0
	var fit := func():
		b.custom_minimum_size.y = maxf(min_h, row.get_combined_minimum_size().y + 10.0)
	row.minimum_size_changed.connect(fit)
	fit.call()
	var hl_on := func(on: bool):
		if b.disabled:
			return
		dot.add_theme_stylebox_override("panel", ui._box(ui.ACCENT if on else ui.INK, 14))
	b.focus_entered.connect(hl_on.bind(true))
	b.focus_exited.connect(func(): hl_on.call(b.is_hovered()))
	b.mouse_entered.connect(hl_on.bind(true))
	b.mouse_exited.connect(func(): hl_on.call(b.has_focus()))
	var cc: Dictionary = c
	b.pressed.connect(func():
		Sfx.play("click", 1.0, -6.0)
		ui._choose(cc))
	return b


func _on_panel_input(e: InputEvent) -> void:
	# tapping the panel finishes the typewriter (touch friendly)
	if (e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT) or (e is InputEventScreenTouch and e.pressed):
		if ui.is_typing():
			ui.finish_typing()
			accept_event()


func _queue_relayout() -> void:
	if _queued:
		return
	_queued = true
	call_deferred("_do_relayout")


func _do_relayout() -> void:
	_queued = false
	# a dialog closed this frame must not re-summon its portrait
	if is_inside_tree() and not is_queued_for_deletion() and ui.modal == self:
		relayout(get_viewport_rect().size)


func _columns(land: bool) -> int:
	if not land or choices.size() < 2:
		return 1
	var longest := 0
	for c in choices:
		longest = maxi(longest, str(c.get("text", "")).length())
	return 2 if longest <= 42 else 1


func _text_w(s: String, font: Font, fsize: int) -> float:
	return font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, fsize).x


func _fit(h: float, max_w: float) -> Vector2:
	## Art size for height `h`, keeping its aspect and at most `max_w` wide.
	var aspect := float(art.get_width()) / float(art.get_height())
	if h * aspect > max_w:
		h = max_w / aspect
	return Vector2(h * aspect, h)


func occupied_rects() -> Array:
	## Canvas rects this dialog covers (panel + standing portrait), so the HUD
	## can move out of the way.
	var out := [Rect2(panel.position, panel.size)]
	if portrait_rect.has_area():
		out.append(portrait_rect)
	return out


func relayout(vp: Vector2) -> void:
	size = vp
	var land := vp.x >= vp.y * 1.05
	var touch: bool = ui._touch_mode
	var m := 14.0
	var bottom := vp.y - clampf(vp.y * 0.028, 12.0, 24.0)
	var cols := _columns(land)
	grid.columns = cols
	# badge diameter (fallback) / half-body size (art)
	var d := clampf(vp.y * 0.14, 84.0, 108.0) if land else clampf(vp.x * 0.24, 88.0, 116.0)
	var pw := 0.0
	var ph := 0.0
	if art:
		if land:
			ph = clampf(vp.y * 0.56, 230.0, 430.0)
			var sz := _fit(ph, ph * 0.92)
			pw = sz.x
			ph = sz.y
		else:
			ph = clampf(vp.y * 0.26, 220.0, 440.0)
			var sz := _fit(ph, (vp.x - 2.0 * m) * 0.62)
			pw = sz.x
			ph = sz.y
	# panel width: wide enough for the longest choice (two columns) and a
	# comfortable line of text, never wider than the screen allows
	var w := vp.x - 2.0 * m
	var pad_left := 16.0
	if land:
		var dot := 18.0 if touch else 24.0
		var longest := 0.0
		for c in choices:
			longest = maxf(longest, _text_w(str(c.get("text", "")), ui._font_medium, 20))
			longest = maxf(longest, _text_w(str(c.get("hint", "")), ui._font_semi, 15))
		var col_need := 14.0 + dot + 12.0 + longest + 14.0 + 6.0
		var need_choices := cols * col_need + (cols - 1) * 12.0 + 32.0
		if choices.size() == 1:
			need_choices = 0.0
		var lead := (d + 16.0) if art == null else 0.0
		var body_px := _text_w(text, ui._font_semi, 22)
		var need_text := 32.0 + lead + 36.0 + minf(body_px + 8.0, 600.0)
		var art_extra := 0.0
		if art:
			pad_left = 12.0 + pw + 14.0
			art_extra = pad_left - 16.0
		var min_w := maxf(560.0, vp.x * 0.46)
		var max_w := 880.0
		w = clampf(maxf(need_choices, need_text), min_w, max_w) + art_extra
		w = minf(w, vp.x - 2.0 * m)
	elif art:
		pad_left = 16.0
	_panel_style.content_margin_left = pad_left
	# fallback badge sits in the top-left corner of the panel
	if art == null:
		badge_room.custom_minimum_size = Vector2(d, d)
		if badge == null or not is_equal_approx(float(badge.get_meta("d", 0.0)), d):
			_rebuild_badge(d)
	bubble.tail = true
	if choices.size() == 1:
		# a lone "Lanjut" sits bottom-right like a continue arrow
		grid.size_flags_horizontal = Control.SIZE_SHRINK_END
		buttons[0].custom_minimum_size.x = 180.0
	else:
		grid.size_flags_horizontal = Control.SIZE_FILL
	var lead_w := (d + 16.0) if art == null else 0.0
	var inner_w := w - pad_left - 16.0
	body.custom_minimum_size.x = maxf(120.0, inner_w - lead_w - 36.0 - 2.0)
	panel.size = Vector2(w, 0)
	panel.size = Vector2(w, panel.get_combined_minimum_size().y)
	var x0 := roundf((vp.x - w) * 0.5)
	panel.position = Vector2(x0, roundf(bottom - panel.size.y))
	var ptop := panel.position.y
	scrim.position = Vector2(0, ptop - 120.0)
	scrim.size = Vector2(vp.x, vp.y - ptop + 120.0)
	# half-body art: stands on the panel's bottom-left (landscape) or leans
	# over its top-left corner (portrait screens)
	portrait_rect = Rect2()
	if art:
		if land:
			portrait_rect = Rect2(panel.position.x + 12.0, bottom - ph - 4.0, pw, ph)
		else:
			portrait_rect = Rect2(panel.position.x + 14.0, ptop - ph + 22.0, pw, ph)
			# the bubble's tail would point at nothing: the art is above it
			bubble.tail = false
	var stage: Control = ui.portrait_stage
	if ui.modal != self:
		return
	if art:
		stage.present(key, art, true, portrait_rect, not chained)
	else:
		stage.hide_portrait()
	ui._sync_hud()


func _rebuild_badge(d: float) -> void:
	## (Re)builds the round badge at diameter `d`; the render's clip circle is
	## baked into its material, so a size change needs a fresh one.
	var old := badge
	badge = PortraitStage.build_badge(badge_tex, d)
	badge.set_meta("d", d)
	badge.pivot_offset = Vector2(d * 0.5, d * 0.5)
	badge_room.add_child(badge)
	if old:
		old.set_meta("d", -1.0)
		badge_room.remove_child(old)
		old.queue_free()


func play_in() -> void:
	## Entrance: fresh conversations slide up + fade; chained lines only pop the
	## badge / name when a different person speaks.
	if not chained:
		modulate = Color(1, 1, 1, 0)
		position.y = 26.0
		var tw := create_tween().set_parallel()
		tw.tween_property(self, "modulate:a", 1.0, 0.18)
		tw.tween_property(self, "position:y", 0.0, 0.26).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	if speaker_changed or not chained:
		if badge:
			badge.scale = Vector2(0.7, 0.7)
			badge.modulate.a = 0.0
			var t1 := badge.create_tween().set_parallel()
			t1.tween_property(badge, "scale", Vector2.ONE, 0.32).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT).set_delay(0.04)
			t1.tween_property(badge, "modulate:a", 1.0, 0.14).set_delay(0.04)
		name_label.pivot_offset = Vector2(0, name_label.size.y * 0.5)
		name_label.modulate.a = 0.0
		var t2 := name_label.create_tween()
		t2.tween_property(name_label, "modulate:a", 1.0, 0.2).set_delay(0.08)


func _process(delta: float) -> void:
	_t += delta
	if badge == null:
		return
	# the badge breathes, and bounces lightly while the line is typing
	var bob: Control = badge.get_node_or_null("Bob")
	if bob == null:
		return
	var y := sin(_t * TAU / 2.6) * 1.2
	if ui.is_typing():
		y -= absf(sin(_t * 9.0)) * 2.2
	bob.position.y = y


class _Bubble extends PanelContainer:
	## Speech bubble with a small tail on its left edge pointing at the speaker
	## (at the badge's centre when `anchor_node` is set, else near the top).
	var fill := Color.WHITE
	var line := Color.BLACK
	var anchor_node: Control
	var tail := true:
		set(v):
			tail = v
			queue_redraw()

	func _notification(what: int) -> void:
		if what == NOTIFICATION_RESIZED or what == NOTIFICATION_SORT_CHILDREN:
			queue_redraw()

	func _draw() -> void:
		if not tail:
			return
		var y := minf(30.0, size.y * 0.5)
		if anchor_node and anchor_node.is_inside_tree():
			y = anchor_node.position.y + anchor_node.size.y * 0.5 - position.y
		y = clampf(y, 16.0, size.y - 16.0)
		var pts := PackedVector2Array([Vector2(1.5, y - 10.0), Vector2(-12.0, y + 1.0), Vector2(1.5, y + 10.0)])
		draw_colored_polygon(pts, fill)
		draw_polyline(PackedVector2Array([pts[0], pts[1], pts[2]]), line, 2.0, true)
		# hide the bubble's own border where the tail joins
		draw_line(Vector2(1.0, y - 8.5), Vector2(1.0, y + 8.5), fill, 3.0)
