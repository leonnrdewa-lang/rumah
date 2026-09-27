extends Control
## Visual-novel style dialog (built by ui.gd:dialog). A cream speech panel sits
## at the bottom of the screen; the speaker's half-body portrait (drawn by the
## UI's PortraitStage) stands on its left and overlaps the panel's top edge.
## A name-tag pill rides the top edge, the line types out in a speech bubble
## and the choices are rounded pills with dark dot bullets (number shortcuts
## inside) laid out in a 2-column grid like the target screenshot.

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
var bubble: PanelContainer
var badge_room: Control
var body: Label
var grid: GridContainer
var name_tag: PanelContainer
var scrim: TextureRect
var buttons: Array = []
var _queued := false
var _panel_style: StyleBoxFlat


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
	# soft dark gradient behind the panel so the portrait and text pop
	scrim = TextureRect.new()
	var g := Gradient.new()
	g.set_color(0, Color(0.1, 0.07, 0.03, 0.0))
	g.set_color(1, Color(0.1, 0.07, 0.03, 0.32))
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
	_panel_style = ui._box(ui.CREAM, 26, ui.LINE, 3, true)
	_panel_style.shadow_size = 14
	_panel_style.shadow_offset = Vector2(0, 5)
	_panel_style.shadow_color = Color(0.2, 0.12, 0.04, 0.3)
	ui._margins(_panel_style, 24, 26, 22, 18)
	panel.add_theme_stylebox_override("panel", _panel_style)
	panel.gui_input.connect(_on_panel_input)
	add_child(panel)
	col = VBoxContainer.new()
	col.add_theme_constant_override("separation", 12)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(col)

	bubble = _Bubble.new()
	bubble.fill = ui.CREAM_LIGHT
	bubble.line = ui.LINE
	var bs: StyleBoxFlat = ui._box(ui.CREAM_LIGHT, 20, ui.LINE, 2)
	ui._margins(bs, 20, 12, 20, 14)
	bubble.add_theme_stylebox_override("panel", bs)
	bubble.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bubble.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bubble.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	# top row: [room for the round badge] [speech bubble]; the choices below
	# span the whole panel like in the target screenshot
	var top_row := HBoxContainer.new()
	top_row.add_theme_constant_override("separation", 0)
	top_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	badge_room = Control.new()
	badge_room.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top_row.add_child(badge_room)
	top_row.add_child(bubble)
	col.add_child(top_row)
	body = ui._label(text, 23, ui.BROWN)
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_constant_override("line_spacing", 3)
	body.visible_characters = 0
	bubble.add_child(body)

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

	name_tag = PanelContainer.new()
	var ns: StyleBoxFlat = ui._box(Color("6b4226"), 20, Color("fffaf0"), 3, true)
	ui._margins(ns, 20, 5, 20, 6)
	name_tag.add_theme_stylebox_override("panel", ns)
	name_tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var nl: Label = ui._label(speaker, 22, ui.CREAM_LIGHT, true)
	name_tag.add_child(nl)
	add_child(name_tag)

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
	row.offset_left = 10
	row.offset_right = -16
	row.offset_top = 6
	row.offset_bottom = -6
	row.add_theme_constant_override("separation", 12)
	b.add_child(row)
	var touch: bool = ui._touch_mode
	var dsz := 18 if touch else 27
	var dot := PanelContainer.new()
	dot.name = "Dot"
	dot.custom_minimum_size = Vector2(dsz, dsz)
	dot.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dot.add_theme_stylebox_override("panel", ui._box(ui.INK if not b.disabled else Color("b5a38a"), 16))
	if not touch:
		var n: Label = ui._label(str(i), 15, ui.CREAM_LIGHT, true)
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
	var tl: Label = ui._label(str(c.get("text", "")), 21, ui.BROWN)
	tl.add_theme_font_override("font", ui._font_medium)
	tl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	tc.add_child(tl)
	var hint := str(c.get("hint", ""))
	if hint != "":
		var hl: Label = ui._label(hint, 16, ui.BROWN_SOFT)
		hl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		tc.add_child(hl)
	if b.disabled:
		row.modulate = Color(1, 1, 1, 0.55)
	var min_h := 56.0 if touch else 50.0
	var fit := func():
		b.custom_minimum_size.y = maxf(min_h, row.get_combined_minimum_size().y + 12.0)
	row.minimum_size_changed.connect(fit)
	fit.call()
	var hl_on := func(on: bool):
		if b.disabled:
			return
		dot.add_theme_stylebox_override("panel", ui._box(ui.ACCENT if on else ui.INK, 16))
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


func _fit(h: float, max_w: float) -> Vector2:
	## Art size for height `h`, keeping its aspect and at most `max_w` wide.
	var aspect := float(art.get_width()) / float(art.get_height())
	if h * aspect > max_w:
		h = max_w / aspect
	return Vector2(h * aspect, h)


func relayout(vp: Vector2) -> void:
	size = vp
	var land := vp.x >= vp.y * 1.05
	var m := 14.0
	var touch: bool = ui._touch_mode
	var pw := 0.0
	var ph := 0.0
	var pad_left := 22.0
	var room := 0.0  # indent of the bubble next to a round badge
	var w := 0.0
	if land:
		if art:
			ph = clampf(vp.y * 0.56, 230.0, 430.0)
			var sz := _fit(ph, ph * 0.92)
			pw = sz.x
			ph = sz.y
			pad_left = 12.0 + pw + 12.0
		elif badge_tex:
			ph = clampf(vp.y * 0.23, 118.0, 164.0)
			pw = ph
			room = pw + 20.0
		var text_w := clampf(vp.x - 2.0 * m - pad_left - room - 26.0, 340.0, 700.0 if not touch else 780.0)
		w = minf(pad_left + room + text_w + 26.0, vp.x - 2.0 * m)
	else:
		w = vp.x - 2.0 * m
		if art:
			ph = clampf(vp.y * 0.26, 220.0, 440.0)
			var sz := _fit(ph, w * 0.62)
			pw = sz.x
			ph = sz.y
		elif badge_tex:
			ph = clampf(vp.x * 0.26, 120.0, 180.0)
			pw = ph
	_panel_style.content_margin_left = pad_left
	badge_room.custom_minimum_size = Vector2(room, maxf(0.0, pw * 0.66 - 28.0 + 6.0) if room > 0.0 else 0.0)
	_panel_style.content_margin_top = 28.0 if (land or (art == null and badge_tex == null)) else 30.0
	bubble.tail = land and (art != null or badge_tex != null)
	grid.columns = _columns(land)
	if choices.size() == 1:
		# a lone "Lanjut" sits bottom-right like a continue arrow
		grid.size_flags_horizontal = Control.SIZE_SHRINK_END
		buttons[0].custom_minimum_size.x = 220.0
	var inner_w := w - pad_left - room - 26.0
	body.custom_minimum_size.x = maxf(120.0, inner_w - 40.0)
	panel.size = Vector2(w, 0)
	panel.size = Vector2(w, panel.get_combined_minimum_size().y)
	var bottom := vp.y - m
	panel.position = Vector2(roundf((vp.x - w) * 0.5), roundf(bottom - panel.size.y))
	var ptop := panel.position.y
	# name tag riding the panel's top edge, above the text column
	var ns := name_tag.get_combined_minimum_size()
	name_tag.size = ns
	var tag_x := panel.position.x + pad_left + room - 6.0
	if not land and (art or badge_tex):
		tag_x = panel.position.x + 16.0 + pw + 12.0
		if tag_x + ns.x > panel.position.x + w - 12.0:
			tag_x = panel.position.x + w - 12.0 - ns.x
	name_tag.position = Vector2(roundf(tag_x), roundf(ptop - ns.y * 0.55))
	name_tag.pivot_offset = ns * 0.5
	scrim.position = Vector2(0, ptop - 150.0)
	scrim.size = Vector2(vp.x, vp.y - ptop + 150.0)
	# portrait rect (canvas coordinates) for the stage
	var r := Rect2()
	if art:
		if land:
			r = Rect2(panel.position.x + 12.0, bottom - ph - 4.0, pw, ph)
		else:
			r = Rect2(panel.position.x + 14.0, ptop - ph + 26.0, pw, ph)
	elif badge_tex:
		if land:
			r = Rect2(panel.position.x + 22.0, ptop - pw * 0.34, pw, pw)
		else:
			r = Rect2(panel.position.x + 16.0, ptop - pw * 0.72, pw, pw)
	var stage: Control = ui.portrait_stage
	if ui.modal != self:
		return
	if art or badge_tex:
		stage.present(key, art if art else badge_tex, art != null, r, not chained)
	else:
		stage.hide_portrait()


func play_in() -> void:
	## Entrance: fresh conversations slide up + fade; chained lines only pop the
	## name tag when a different person speaks.
	if not chained:
		modulate = Color(1, 1, 1, 0)
		position.y = 26.0
		var tw := create_tween().set_parallel()
		tw.tween_property(self, "modulate:a", 1.0, 0.18)
		tw.tween_property(self, "position:y", 0.0, 0.26).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	if speaker_changed or not chained:
		name_tag.scale = Vector2(0.6, 0.6)
		var t2 := name_tag.create_tween()
		t2.tween_property(name_tag, "scale", Vector2.ONE, 0.3).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT).set_delay(0.05)


class _Bubble extends PanelContainer:
	## Speech bubble with a small tail pointing at the portrait on the left.
	var fill := Color.WHITE
	var line := Color.BLACK
	var tail := true:
		set(v):
			tail = v
			queue_redraw()

	func _draw() -> void:
		if not tail:
			return
		var y := minf(34.0, size.y * 0.5)
		var pts := PackedVector2Array([Vector2(1.5, y - 11.0), Vector2(-13.0, y + 2.0), Vector2(1.5, y + 11.0)])
		draw_colored_polygon(pts, fill)
		draw_polyline(PackedVector2Array([pts[0], pts[1], pts[2]]), line, 2.0, true)
		# hide the bubble's own border where the tail joins
		draw_line(Vector2(1.0, y - 9.5), Vector2(1.0, y + 9.5), fill, 3.0)
