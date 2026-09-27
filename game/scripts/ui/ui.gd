extends CanvasLayer
## All 2D interface: title screen, HUD pills (styled after the reference
## screenshot), dialog box with choices, shop/list menus, morning report,
## pause/status panels and the on-screen touch controls for phones.

const CREAM := Color("fdf3dc")
const CREAM_DARK := Color("f1e2bf")
const BROWN := Color("5a3b22")
const BROWN_SOFT := Color("8a6a4a")
const GREEN := Color("5c8a3a")
const RED := Color("c9563c")
const GOLD := Color("e9b949")
const FONT := preload("res://assets/fonts/Fredoka.ttf")

var world: Node
var root: Control
var hud: Control
var title_screen: Control
var overlay: Control   # dims the game behind modal panels
var modal: Control     # current modal panel (dialog, menu, report...)
var prompt_pill: PanelContainer
var prompt_key: Label
var prompt_label: Label
var money_label: Label
var clock_label: Label
var energy_bar: ProgressBar
var rep_bar: ProgressBar
var heat_bar: ProgressBar
var quest_label: Label
var inv_labels := {}
var toast_box: VBoxContainer
var touch: Control
var joy_base: Control
var joy_knob: Control
var action_btn: Control
var action_label: Label
var _font_bold: FontVariation
var _font_semi: FontVariation
var _dialog_choices: Array = []
var _typing: Label
var _typing_full := ""
var _typing_t := 0.0
var _joy_index := -1
var _joy_center := Vector2.ZERO
var _action_index := -1
var _touch_mode := false
var _paused := false
var _on_modal_close: Callable
var _prompt_ok := false
var _icons := {}
var minimap: Control


func _ready() -> void:
	layer = 10
	_font_bold = FontVariation.new()
	_font_bold.base_font = FONT
	_font_bold.variation_opentype = {"wght": 680}
	_font_semi = FontVariation.new()
	_font_semi.base_font = FONT
	_font_semi.variation_opentype = {"wght": 520}
	root = Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = _make_theme()
	add_child(root)
	_build_hud()
	_build_touch()
	overlay = ColorRect.new()
	(overlay as ColorRect).color = Color(0.12, 0.09, 0.05, 0.35)
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.visible = false
	root.add_child(overlay)
	toast_box = VBoxContainer.new()
	toast_box.set_anchors_preset(Control.PRESET_CENTER_TOP)
	toast_box.position = Vector2(-300, 14)
	toast_box.custom_minimum_size = Vector2(600, 0)
	toast_box.alignment = BoxContainer.ALIGNMENT_BEGIN
	toast_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	toast_box.add_theme_constant_override("separation", 6)
	root.add_child(toast_box)
	GS.stats_changed.connect(_refresh_hud)
	GS.quest_changed.connect(_refresh_hud)
	GS.toast.connect(func(t, k): toast(t, k))
	_touch_mode = OS.has_feature("mobile") or OS.has_feature("web_android") or OS.has_feature("web_ios")
	get_viewport().size_changed.connect(_layout)
	_layout()


# ------------------------------------------------------------------ theme & builders
func _make_theme() -> Theme:
	var th := Theme.new()
	th.default_font = _font_semi
	th.default_font_size = 22
	th.set_color("font_color", "Label", BROWN)
	var normal := _box(CREAM_DARK, 16)
	var hover := _box(Color("fff8e6"), 16)
	hover.border_color = GOLD
	hover.set_border_width_all(3)
	var pressed := _box(Color("e6d2a6"), 16)
	var disabled := _box(Color(0.93, 0.89, 0.8, 0.7), 16)
	var focus := _box(Color(0, 0, 0, 0), 16)
	focus.draw_center = false
	focus.border_color = GOLD
	focus.set_border_width_all(3)
	for st in [normal, hover, pressed, disabled]:
		st.content_margin_left = 18
		st.content_margin_right = 18
		st.content_margin_top = 10
		st.content_margin_bottom = 10
	th.set_stylebox("normal", "Button", normal)
	th.set_stylebox("hover", "Button", hover)
	th.set_stylebox("pressed", "Button", pressed)
	th.set_stylebox("disabled", "Button", disabled)
	th.set_stylebox("focus", "Button", focus)
	th.set_color("font_color", "Button", BROWN)
	th.set_color("font_hover_color", "Button", BROWN)
	th.set_color("font_pressed_color", "Button", BROWN)
	th.set_color("font_focus_color", "Button", BROWN)
	th.set_color("font_disabled_color", "Button", Color(0.55, 0.47, 0.38, 0.8))
	th.set_font("font", "Button", _font_bold)
	var panel_box := _box(CREAM, 22, true)
	panel_box.content_margin_left = 22
	panel_box.content_margin_right = 22
	panel_box.content_margin_top = 16
	panel_box.content_margin_bottom = 16
	th.set_stylebox("panel", "PanelContainer", panel_box)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0)
	th.set_stylebox("panel", "ScrollContainer", sb)
	var grab := _box(Color("c8b08a"), 8)
	th.set_stylebox("grabber", "VScrollBar", grab)
	th.set_stylebox("grabber_highlight", "VScrollBar", grab)
	th.set_stylebox("grabber_pressed", "VScrollBar", grab)
	var track := _box(Color(0.8, 0.72, 0.58, 0.3), 8)
	th.set_stylebox("scroll", "VScrollBar", track)
	return th


func _box(color: Color, radius: int, shadow := false) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = color
	s.set_corner_radius_all(radius)
	s.anti_aliasing = true
	if shadow:
		s.shadow_color = Color(0.2, 0.12, 0.05, 0.28)
		s.shadow_size = 8
		s.shadow_offset = Vector2(0, 3)
	return s


func _pill(content: Control, color := CREAM) -> PanelContainer:
	var p := PanelContainer.new()
	var s := _box(color, 20, true)
	s.content_margin_left = 10
	s.content_margin_right = 16
	s.content_margin_top = 5
	s.content_margin_bottom = 5
	p.add_theme_stylebox_override("panel", s)
	p.add_child(content)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return p


func _label(text: String, size := 22, color := BROWN, bold := false) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	if bold:
		l.add_theme_font_override("font", _font_bold)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func icon(name: String) -> Texture2D:
	if not _icons.has(name):
		var path := "res://assets/icons/%s.png" % name
		_icons[name] = load(path) if ResourceLoader.exists(path) else null
	return _icons[name]


func _icon_rect(name: String, size := 30) -> Control:
	var tex := icon(name)
	if tex:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tr.custom_minimum_size = Vector2(size, size)
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		return tr
	# fallback: a round badge (like the reference's brown icon circles)
	var p := Panel.new()
	var s := _box(Color("a8764a"), size / 2)
	p.add_theme_stylebox_override("panel", s)
	p.custom_minimum_size = Vector2(size, size)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return p


func _round_badge(text: String, size := 30, color := Color("a8764a")) -> Control:
	var p := PanelContainer.new()
	var s := _box(color, size / 2)
	s.content_margin_left = 6
	s.content_margin_right = 6
	p.add_theme_stylebox_override("panel", s)
	p.custom_minimum_size = Vector2(size, size)
	var l := _label(text, int(size * 0.6), CREAM, true)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	p.add_child(l)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return p


func _hrow(children: Array, sep := 8) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", sep)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for c in children:
		h.add_child(c)
	return h


func _bar(color: Color, w := 110) -> ProgressBar:
	var b := ProgressBar.new()
	b.show_percentage = false
	b.custom_minimum_size = Vector2(w, 14)
	b.min_value = 0
	b.max_value = 100
	var bg := _box(Color(0.55, 0.42, 0.28, 0.25), 7)
	var fg := _box(color, 7)
	b.add_theme_stylebox_override("background", bg)
	b.add_theme_stylebox_override("fill", fg)
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	b.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return b


func button(text: String, cb: Callable, enabled := true, min_w := 0) -> Button:
	var b := Button.new()
	b.text = text
	b.disabled = not enabled
	b.custom_minimum_size = Vector2(min_w, 46)
	b.add_theme_font_size_override("font_size", 22)
	b.pressed.connect(func():
		Sfx.play("click", 1.0, -6.0)
		cb.call())
	return b


# ------------------------------------------------------------------ HUD
func _build_hud() -> void:
	hud = Control.new()
	hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(hud)
	# top-left: money, clock, energy
	var tl := VBoxContainer.new()
	tl.position = Vector2(16, 14)
	tl.add_theme_constant_override("separation", 8)
	tl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(tl)
	money_label = _label("Rp 0", 24, BROWN, true)
	clock_label = _label("Hari 1 • 06:00", 22)
	energy_bar = _bar(Color("e9b949"), 120)
	var row1 := _hrow([_pill(_hrow([_icon_rect("icon_koin", 30), money_label])),
		_pill(_hrow([_icon_rect("ui_sun", 30), clock_label]))])
	tl.add_child(row1)
	var elabel := _label("Energi", 18, BROWN_SOFT)
	tl.add_child(_hrow([_pill(_hrow([_icon_rect("ui_energy", 28), elabel, energy_bar], 10))]))
	quest_label = _label("", 19, BROWN)
	quest_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	quest_label.custom_minimum_size = Vector2(330, 0)
	var qp := _pill(_hrow([_round_badge("!", 26, GREEN), quest_label], 10))
	qp.name = "QuestPill"
	tl.add_child(_hrow([qp]))
	# top-right: reputation & suspicion + menu button
	var tr := VBoxContainer.new()
	tr.name = "TopRight"
	tr.add_theme_constant_override("separation", 8)
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(tr)
	rep_bar = _bar(GREEN, 120)
	heat_bar = _bar(RED, 120)
	var repl := _label("Reputasi", 18, BROWN_SOFT)
	repl.custom_minimum_size = Vector2(96, 0)
	var heatl := _label("Kecurigaan", 18, BROWN_SOFT)
	heatl.custom_minimum_size = Vector2(96, 0)
	tr.add_child(_pill(_hrow([repl, rep_bar], 10)))
	tr.add_child(_pill(_hrow([heatl, heat_bar], 10)))
	var menu_row := HBoxContainer.new()
	menu_row.alignment = BoxContainer.ALIGNMENT_END
	menu_row.add_theme_constant_override("separation", 8)
	var sb := button("Status", show_status)
	var mb := button("Menu", toggle_pause)
	sb.custom_minimum_size = Vector2(96, 42)
	mb.custom_minimum_size = Vector2(96, 42)
	menu_row.add_child(sb)
	menu_row.add_child(mb)
	tr.add_child(menu_row)
	minimap = preload("res://scripts/ui/minimap.gd").new()
	minimap.world = world
	minimap.font = _font_bold
	hud.add_child(minimap)
	# bottom-left: context prompt like "E  Take out the rod"
	prompt_key = _label("E", 20, CREAM, true)
	var kb := PanelContainer.new()
	var ks := _box(Color("7a5536"), 8)
	ks.content_margin_left = 9
	ks.content_margin_right = 9
	kb.add_theme_stylebox_override("panel", ks)
	kb.add_child(prompt_key)
	kb.name = "KeyBadge"
	prompt_label = _label("", 22, BROWN)
	prompt_pill = _pill(_hrow([kb, prompt_label], 10))
	prompt_pill.name = "Prompt"
	prompt_pill.visible = false
	hud.add_child(prompt_pill)
	# bottom-right: inventory
	var inv_row := HBoxContainer.new()
	inv_row.name = "Inventory"
	inv_row.add_theme_constant_override("separation", 6)
	inv_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(inv_row)
	for item in [["bibit", "icon_bibit"], ["pupuk", "icon_pupuk"], ["tbs", "icon_tbs"], ["minyak", "icon_minyak"], ["surat", "icon_surat"]]:
		var l := _label("0", 21, BROWN, true)
		inv_labels[item[0]] = l
		var p := _pill(_hrow([_icon_rect(item[1], 34), l], 4))
		p.name = "inv_" + item[0]
		inv_row.add_child(p)
	hud.visible = false


func _layout() -> void:
	# phones held upright: enlarge the UI so text stays readable
	var win := Vector2(get_tree().root.size)
	var want := 1.0 if win.x >= win.y else 1.75
	if _touch_mode and win.x >= win.y:
		want = 1.25
	if not is_equal_approx(get_tree().root.content_scale_factor, want):
		get_tree().root.content_scale_factor = want
		call_deferred("_layout")
		return
	var vp := root.get_viewport_rect().size
	var tr: Control = hud.get_node("TopRight")
	tr.position = Vector2(vp.x - tr.get_combined_minimum_size().x - 16, 14)
	if minimap:
		if minimap.big:
			var w := minf(vp.x - 40, (vp.y - 40) * 170.0 / 150.0)
			minimap.size = Vector2(w, w * 150.0 / 170.0)
			minimap.position = (vp - minimap.size) * 0.5
		else:
			var small := Vector2(204, 180) if vp.y >= 600 else Vector2(150, 132)
			minimap.size = small
			minimap.position = Vector2(vp.x - small.x - 16, tr.position.y + tr.get_combined_minimum_size().y + 10)
	var inv: Control = hud.get_node("Inventory")
	var inv_size := inv.get_combined_minimum_size()
	var portrait := vp.x < vp.y
	if _touch_mode:
		inv.position = Vector2(vp.x * 0.5 - inv_size.x * 0.5, vp.y - inv_size.y - 12)
	else:
		inv.position = Vector2(vp.x - inv_size.x - 16, vp.y - inv_size.y - 16)
	var ps := prompt_pill.get_combined_minimum_size()
	if _touch_mode:
		prompt_pill.position = Vector2(vp.x * 0.5 - ps.x * 0.5, vp.y - inv_size.y - ps.y - 26)
	else:
		prompt_pill.position = Vector2(16, vp.y - ps.y - 16)
	var qp: Control = hud.find_child("QuestPill", true, false)
	quest_label.custom_minimum_size.x = clampf(vp.x * 0.3, 220, 360) if not portrait else vp.x * 0.5
	toast_box.position = Vector2(vp.x * 0.5 - 300, 14 if not portrait else 190)
	if touch:
		_layout_touch(vp)
	if modal:
		_center_modal()


func show_hud() -> void:
	_close_modal()
	if title_screen:
		title_screen.queue_free()
		title_screen = null
	hud.visible = true
	touch.visible = _touch_mode
	_refresh_hud()


func _refresh_hud() -> void:
	money_label.text = GS.fmt_rp(GS.money)
	clock_label.text = "Hari %d • %s" % [GS.day, GS.clock_text()]
	energy_bar.value = GS.energy / GS.max_energy * 100.0
	rep_bar.value = (GS.rep + 100.0) * 0.5
	heat_bar.value = GS.heat
	quest_label.text = "Misi: " + GS.current_quest()
	for k in inv_labels:
		var n := int(GS.inv.get(k, 0))
		inv_labels[k].text = ("%d/%d" % [n, GS.capacity()]) if k == "tbs" else str(n)
	(hud.get_node("Inventory/inv_surat") as Control).visible = int(GS.inv.get("surat", 0)) > 0
	(hud.get_node("Inventory/inv_minyak") as Control).visible = GS.upgrades.get("mesin", false) or int(GS.inv.get("minyak", 0)) > 0
	call_deferred("_layout")


func set_prompt(text: String, ok: bool) -> void:
	_prompt_ok = ok
	if text == "" or is_blocking():
		prompt_pill.visible = false
		if action_label:
			action_label.text = ""
			action_btn.modulate.a = 0.45
		return
	prompt_pill.visible = true
	prompt_label.text = text
	prompt_key.text = "E" if ok else "•"
	prompt_pill.modulate.a = 1.0 if ok else 0.85
	(prompt_pill.find_child("KeyBadge", true, false) as Control).visible = ok or not _touch_mode
	if action_label:
		action_label.text = _short_verb(text) if ok else ""
		action_btn.modulate.a = 1.0 if ok else 0.45
	var vp := root.get_viewport_rect().size
	var ps := prompt_pill.get_combined_minimum_size()
	if _touch_mode:
		var inv: Control = hud.get_node("Inventory")
		prompt_pill.position = Vector2(vp.x * 0.5 - ps.x * 0.5, vp.y - inv.get_combined_minimum_size().y - ps.y - 26)


func _short_verb(text: String) -> String:
	var w := text.split(" ")
	return w[0] if w.size() > 0 else text


func toast(text: String, kind := "info") -> void:
	var col := CREAM
	match kind:
		"bad":
			col = Color("f8d9c8")
		"good":
			col = Color("e3efc8")
		"quest":
			col = Color("fbe7a8")
	var l := _label(text, 21, BROWN)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.custom_minimum_size = Vector2(560, 0)
	var p := _pill(l, col)
	toast_box.add_child(p)
	if kind == "quest":
		Sfx.play("quest")
	p.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(p, "modulate:a", 1.0, 0.2)
	tw.tween_interval(3.2 if kind != "quest" else 4.5)
	tw.tween_property(p, "modulate:a", 0.0, 0.5)
	tw.tween_callback(p.queue_free)
	while toast_box.get_child_count() > 4:
		toast_box.get_child(0).queue_free()
		toast_box.remove_child(toast_box.get_child(0))


# ------------------------------------------------------------------ modal plumbing
func is_blocking() -> bool:
	return modal != null or title_screen != null or _paused


func _open_modal(panel: Control, dim := true, on_close := Callable()) -> void:
	_close_modal()
	modal = panel
	_on_modal_close = on_close
	overlay.visible = dim
	root.add_child(panel)
	panel.resized.connect(_center_modal)
	_center_modal()
	call_deferred("_center_modal")
	panel.modulate.a = 0.0
	panel.scale = Vector2(0.96, 0.96)
	var tw := create_tween()
	tw.tween_property(panel, "modulate:a", 1.0, 0.14)
	tw.parallel().tween_property(panel, "scale", Vector2.ONE, 0.14)
	if world and world.player:
		world.player.locked = true
		world.player.touch_vec = Vector2.ZERO
	_joy_index = -1
	if joy_base:
		joy_base.visible = false
	call_deferred("_focus_first", panel)


func _focus_first(panel: Control) -> void:
	if not is_instance_valid(panel) or _touch_mode:
		return
	var btn := _find_button(panel)
	if btn:
		btn.grab_focus()


func _find_button(n: Node) -> Button:
	if n is Button and not (n as Button).disabled:
		return n
	for c in n.get_children():
		var b := _find_button(c)
		if b:
			return b
	return null


func _center_modal() -> void:
	if not modal:
		return
	var vp := root.get_viewport_rect().size
	var sz := modal.get_combined_minimum_size()
	if modal.has_meta("bottom"):
		var w := minf(vp.x - 24, 940)
		if absf(modal.size.x - w) > 0.5:
			modal.size = Vector2(w, 0)
		modal.position = Vector2((vp.x - modal.size.x) * 0.5, vp.y - modal.size.y - 12)
	else:
		modal.size = Vector2(minf(sz.x, vp.x - 24), minf(sz.y, vp.y - 24))
		modal.position = (vp - modal.size) * 0.5
	modal.pivot_offset = modal.size * 0.5


func _close_modal() -> void:
	if modal:
		modal.queue_free()
		modal = null
	overlay.visible = false
	_dialog_choices.clear()
	_typing = null
	if world and world.player and world.state == "play":
		world.player.locked = false
	var cb := _on_modal_close
	_on_modal_close = Callable()
	if cb.is_valid():
		cb.call()


func close() -> void:
	_close_modal()


# ------------------------------------------------------------------ dialog
func dialog(portrait: String, speaker: String, text: String, choices: Array = [], on_close := Callable()) -> void:
	## choices: [{"text": String, "cb": Callable, "enabled": bool (optional), "hint": String (optional)}]
	## With no choices a single "Lanjut" button closes the dialog.
	var panel := PanelContainer.new()
	panel.set_meta("bottom", true)
	var outer := HBoxContainer.new()
	outer.add_theme_constant_override("separation", 16)
	panel.add_child(outer)
	var pic_holder := PanelContainer.new()
	var ps := _box(Color("e8d4ad"), 60)
	ps.content_margin_left = 4
	ps.content_margin_right = 4
	ps.content_margin_top = 4
	ps.content_margin_bottom = 4
	pic_holder.add_theme_stylebox_override("panel", ps)
	pic_holder.custom_minimum_size = Vector2(120, 120)
	pic_holder.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	var tex := icon(portrait)
	if tex:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tr.custom_minimum_size = Vector2(112, 112)
		pic_holder.add_child(tr)
	outer.add_child(pic_holder)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	outer.add_child(col)
	var name_l := _label(speaker, 24, Color("8a4a1c"), true)
	col.add_child(name_l)
	var body := _label("", 22, BROWN)
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.custom_minimum_size = Vector2(300, 0)
	col.add_child(body)
	body.text = text
	body.visible_characters = 0
	var grid := GridContainer.new()
	grid.columns = 2 if choices.size() > 3 else 1
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 6)
	col.add_child(grid)
	if choices.is_empty():
		choices = [{"text": "Lanjut", "cb": Callable()}]
	_dialog_choices = choices
	var i := 1
	for c in choices:
		var label: String = ("%d. " % i if not _touch_mode else "") + str(c["text"])
		if c.has("hint") and c["hint"] != "":
			label += "  (" + str(c["hint"]) + ")"
		var cc: Dictionary = c
		var b := button(label, func(): _choose(cc), c.get("enabled", true))
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.clip_text = false
		b.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		grid.add_child(b)
		i += 1
	_open_modal(panel, false, on_close)
	_dialog_choices = choices
	_typing = body
	_typing_full = text
	_typing_t = 0.0


func _choose(c: Dictionary) -> void:
	if _typing and _typing.visible_characters >= 0 and _typing.visible_characters < _typing_full.length():
		_typing.visible_characters = -1
		return
	var cb: Callable = c.get("cb", Callable())
	_on_modal_close = Callable() if cb.is_valid() else _on_modal_close
	_close_modal()
	if cb.is_valid():
		cb.call()


func _process(delta: float) -> void:
	if _typing and is_instance_valid(_typing) and _typing.visible_characters >= 0:
		_typing_t += delta * 60.0
		_typing.visible_characters = int(_typing_t)
		if _typing.visible_characters >= _typing_full.length():
			_typing.visible_characters = -1
	if hud.visible and world and world.state == "play":
		clock_label.text = "Hari %d • %s" % [GS.day, GS.clock_text()]


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch or event is InputEventScreenDrag:
		if not _touch_mode:
			_touch_mode = true
			touch.visible = hud.visible
			_layout()
		_handle_touch(event)
		return
	if modal and not _dialog_choices.is_empty() and event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		if k >= KEY_1 and k <= KEY_9:
			var i := k - KEY_1
			if i < _dialog_choices.size() and _dialog_choices[i].get("enabled", true):
				get_viewport().set_input_as_handled()
				_choose(_dialog_choices[i])
	if modal and event is InputEventKey and event.is_action_pressed("action") and not event.is_action_pressed("ui_accept"):
		var f := get_viewport().gui_get_focus_owner()
		if f is Button and not (f as Button).disabled:
			get_viewport().set_input_as_handled()
			(f as Button).pressed.emit()
			return
	if modal and event.is_action_pressed("pause"):
		get_viewport().set_input_as_handled()
		if _dialog_choices.size() <= 1:
			_close_modal()
		elif modal.has_meta("closable"):
			_close_modal()


# ------------------------------------------------------------------ list menu (shops)
func menu(title: String, subtitle: String, items: Array, on_close := Callable(), portrait := "") -> void:
	## items: [{"icon": String, "text": String, "desc": String, "price": String,
	##          "button": String, "cb": Callable, "enabled": bool}]
	var panel := PanelContainer.new()
	panel.set_meta("closable", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	panel.add_child(col)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 12)
	if portrait != "" and icon(portrait):
		head.add_child(_icon_rect(portrait, 64))
	var tcol := VBoxContainer.new()
	tcol.add_child(_label(title, 30, Color("6a3a18"), true))
	if subtitle != "":
		var sl := _label(subtitle, 19, BROWN_SOFT)
		sl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		sl.custom_minimum_size = Vector2(520, 0)
		tcol.add_child(sl)
	tcol.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(tcol)
	col.add_child(head)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var vp := root.get_viewport_rect().size
	scroll.custom_minimum_size = Vector2(minf(700, vp.x - 60), minf(items.size() * 78, vp.y - 250))
	col.add_child(scroll)
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 8)
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(list)
	for it in items:
		var row := PanelContainer.new()
		var rs := _box(Color("f6e8c8"), 14)
		rs.content_margin_left = 10
		rs.content_margin_right = 10
		rs.content_margin_top = 6
		rs.content_margin_bottom = 6
		row.add_theme_stylebox_override("panel", rs)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 12)
		row.add_child(h)
		h.add_child(_icon_rect(it.get("icon", ""), 48))
		var tc := VBoxContainer.new()
		tc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		tc.add_theme_constant_override("separation", 0)
		tc.add_child(_label(it.get("text", ""), 22, BROWN, true))
		if it.get("desc", "") != "":
			var dl := _label(it["desc"], 17, BROWN_SOFT)
			dl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			tc.add_child(dl)
		h.add_child(tc)
		if it.get("price", "") != "":
			var pl := _label(it["price"], 20, Color("7a4a12"), true)
			pl.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			h.add_child(pl)
		if it.has("cb"):
			var b := button(it.get("button", "Beli"), it["cb"], it.get("enabled", true), 110)
			b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			h.add_child(b)
		list.add_child(row)
	var close_b := button("Tutup" + ("" if _touch_mode else "  (Esc)"), _close_modal)
	close_b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(close_b)
	_open_modal(panel, true, on_close)


func refresh_menu(rebuild: Callable) -> void:
	## Re-opens the current menu after a purchase without firing on_close.
	_on_modal_close = Callable()
	rebuild.call()


# ------------------------------------------------------------------ panels
func info_panel(title: String, lines: Array, button_text := "Oke", on_close := Callable(), title_color := Color("6a3a18")) -> void:
	var panel := PanelContainer.new()
	panel.set_meta("closable", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	panel.add_child(col)
	var tl := _label(title, 32, title_color, true)
	tl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(tl)
	var vp := root.get_viewport_rect().size
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.custom_minimum_size = Vector2(minf(640, vp.x - 60), minf(lines.size() * 34 + 20, vp.y - 200))
	var inner := VBoxContainer.new()
	inner.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inner.add_theme_constant_override("separation", 6)
	scroll.add_child(inner)
	col.add_child(scroll)
	for line in lines:
		var l := _label(str(line), 20, BROWN)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.custom_minimum_size = Vector2(minf(600, vp.x - 90), 0)
		if str(line).begins_with("[SIDAK]"):
			l.add_theme_color_override("font_color", RED)
		inner.add_child(l)
	var b := button(button_text, _close_modal, true, 180)
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(b)
	_open_modal(panel, true, on_close)


func show_morning(report: Array) -> void:
	Sfx.play("whoosh")
	var lines: Array = report.duplicate()
	lines.append("Kecurigaan warga & aparat: %d/100 • Reputasi: %d" % [int(GS.heat), int(GS.rep)])
	info_panel("Pagi, Hari ke-%d" % GS.day, lines, "Mulai hari", func(): world.deals.run_morning_events())


func show_status() -> void:
	if modal:
		return
	var lines: Array = []
	lines.append("Uang: %s   •   Harga TBS: %s/tandan" % [GS.fmt_rp(GS.money), GS.fmt_rp(GS.tbs_price)])
	lines.append("Lahan dikuasai: %d/7 (milikmu %d)   •   Pohon sawit: %d" % [GS.controlled_parcels(), GS.owned_parcels(), GS.palm_count()])
	lines.append("Buruh: %d   •   Kapasitas angkut: %d TBS   •   Harga minyak: %s" % [GS.workers.size(), GS.capacity(), GS.OIL_PRICE_NAMES[GS.oil_price_level]])
	lines.append("Reputasi: %d   •   Kecurigaan: %d/100   •   Sidak: %d/3" % [int(GS.rep), int(GS.heat), GS.stats["sidak"]])
	lines.append("— Warga —")
	for vid in GS.villagers:
		var v: Dictionary = GS.villagers[vid]
		var st: String = {"owner": "punya kebun", "landless": "tanpa lahan"}.get(v["status"], v["status"])
		if GS.parcel_of(vid)["plasma"]:
			st = "mitra franchise"
		var extra := ""
		if v["debt"] > 0:
			extra += " • utang " + GS.fmt_rp(v["debt"])
		if v["worker"]:
			extra += " • buruhmu"
		lines.append("%s: %s • percaya %d%%%s" % [GS.vname(vid), st, int(v["trust"]), extra])
	lines.append("— Catatan dosa —")
	lines.append("Beli wajar %d • Tawar murah %d • Tipu %d • Gusur %d • Sita utang %d" % [GS.stats["land_fair"], GS.stats["land_cheap"], GS.stats["land_fraud"], GS.stats["land_seized"], GS.stats["land_debt"]])
	info_panel("Status Juragan", lines, "Tutup")


func toggle_pause() -> void:
	if modal:
		if modal.has_meta("pause"):
			_paused = false
			_close_modal()
		return
	var panel := PanelContainer.new()
	panel.set_meta("pause", true)
	panel.set_meta("closable", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	panel.add_child(col)
	var t := _label("Jeda", 34, Color("6a3a18"), true)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(t)
	col.add_child(button("Lanjut main", func(): _paused = false; _close_modal(), true, 300))
	col.add_child(button("Simpan permainan", func():
		GS.save_game()
		toast("Permainan tersimpan.", "good"), true, 300))
	col.add_child(button("Grafik: " + ("Tinggi" if world.quality_high else "Hemat baterai"), func():
		world.set_quality(not world.quality_high)
		_paused = false
		_close_modal()
		toggle_pause(), true, 300))
	col.add_child(button("Musik: " + ("Nyala" if Sfx.music_on else "Mati"), func():
		Sfx.set_music(not Sfx.music_on)
		_paused = false
		_close_modal()
		toggle_pause(), true, 300))
	col.add_child(button("Layar penuh", func():
		var fs := DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED if fs else DisplayServer.WINDOW_MODE_FULLSCREEN)
		_paused = false
		_close_modal(), true, 300))
	col.add_child(button("Cara main", func(): _paused = false; _close_modal(); show_help(), true, 300))
	col.add_child(button("Keluar ke judul", func():
		GS.save_game()
		_paused = false
		_close_modal()
		world.enter_title(), true, 300))
	_paused = true
	_open_modal(panel, true, func(): _paused = false)


func show_help(on_close := Callable()) -> void:
	var lines := [
		"Tujuan: jadi Raja Sawit! Kuasai ke-7 lahan desa lalu beli Lisensi Sawit The Franchise (Rp 20 juta) di Kantor.",
		"Gerak: WASD / panah (Shift untuk lari). Di HP: geser jempol kiri di layar.",
		"Aksi: E / Spasi (atau tombol bulat kanan bawah di HP) — tebas semak, tanam, pupuk, panen, ngobrol.",
		"Menu: Esc / P.  Status: Tab / I.  Pilihan dialog: tombol angka 1–6.",
		"Sawit butuh ±6 hari untuk berbuah; pupuk mempercepat. Panen TBS lalu jual ke Pabrik di timur.",
		"Lahan warga bisa dibeli wajar, ditawar murah, ditipu pakai surat palsu, atau dirampas pakai preman (sewa dari Bang Jeki dekat dermaga). Preman juga bisa memalak tabungan warga.",
		"Makin culas, makin tinggi Kecurigaan. Kalau penuh (100), Satgas datang menyidak: denda besar. Sidak ke-3 = tamat.",
		"Punya Mesin Olah Minyak? Olah TBS jadi minyak goreng lalu jual ke warga... harganya kamu yang atur.",
		"Warga tanpa lahan bisa kamu jadikan buruh murah. Warga yang masih punya lahan bisa diajak 'kemitraan franchise'.",
		"Tidur di Kantor untuk lanjut hari & menyimpan otomatis. Lewat jam 24:00 kamu pingsan.",
	]
	info_panel("Cara Main", lines, "Siap, Juragan!", on_close)


func show_game_over(reason: String) -> void:
	Sfx.play("bad")
	var lines := [reason, "Hari bertahan: %d • Total pendapatan: %s" % [GS.day, GS.fmt_rp(GS.stats["earned"])],
		"Lahan yang kamu ambil paksa: %d • yang kamu tipu: %d" % [GS.stats["land_seized"], GS.stats["land_fraud"]],
		"Kamu dijebloskan ke penjara... setidaknya sampai ada remisi."]
	GS.delete_save()
	info_panel("TAMAT: Tertangkap!", lines, "Kembali ke judul", func(): world.enter_title(), RED)


func show_ending() -> void:
	Sfx.play("quest")
	var s: Dictionary = GS.stats
	var lines := [
		"Selamat, Juragan! Seluruh desa kini hijau... hijau sawit.",
		"Dalam %d hari kamu menguasai 7 lahan: %d dibeli wajar, %d ditawar murah, %d ditipu, %d digusur, %d disita karena utang, %d jadi mitra franchise." % [GS.day, s["land_fair"], s["land_cheap"], s["land_fraud"], s["land_seized"], s["land_debt"], s["franchise"]],
		"Total pendapatan: %s • Minyak goreng terjual: %d jerigen." % [GS.fmt_rp(s["earned"]), s["oil_sold"]],
		"Warga desa? Mereka kini membeli minyak goreng darimu... dengan harga spesial.",
		"Kantor pusat mengirim piagam: 'Pewaralaba Terbaik Sawit The Franchise™'.",
		"Terima kasih sudah bermain! (Ini satir. Di dunia nyata, hormati hak tanah warga & hutan.)",
	]
	GS.save_game()
	info_panel("RAJA SAWIT!", lines, "Kembali ke judul", func(): world.enter_title(), GREEN)


# ------------------------------------------------------------------ title
func show_title() -> void:
	_close_modal()
	hud.visible = false
	if touch:
		touch.visible = false
	if title_screen:
		title_screen.queue_free()
	title_screen = Control.new()
	title_screen.set_anchors_preset(Control.PRESET_FULL_RECT)
	title_screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(title_screen)
	var shade := ColorRect.new()
	shade.color = Color(0.99, 0.95, 0.86, 0.0)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	title_screen.add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	title_screen.add_child(center)
	var col := VBoxContainer.new()
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	col.add_theme_constant_override("separation", 6)
	center.add_child(col)
	var logo := _label("SAWIT", 120, Color("4f8a2a"), true)
	logo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	logo.add_theme_color_override("font_outline_color", CREAM)
	logo.add_theme_constant_override("outline_size", 26)
	logo.add_theme_color_override("font_shadow_color", Color(0.25, 0.15, 0.05, 0.45))
	logo.add_theme_constant_override("shadow_offset_y", 6)
	col.add_child(logo)
	var ribbon := PanelContainer.new()
	var rs := _box(RED, 14, true)
	rs.content_margin_left = 28
	rs.content_margin_right = 28
	rs.content_margin_top = 2
	rs.content_margin_bottom = 4
	ribbon.add_theme_stylebox_override("panel", rs)
	var rl := _label("THE FRANCHISE", 38, CREAM, true)
	ribbon.add_child(rl)
	ribbon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(ribbon)
	var tag := _label("Kebun sawit impian... untukmu, bukan untuk mereka.", 22, BROWN)
	tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var tagp := _pill(tag)
	tagp.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(Control.new())
	col.add_child(tagp)
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(0, 18)
	col.add_child(spacer)
	var bcol := VBoxContainer.new()
	bcol.add_theme_constant_override("separation", 10)
	bcol.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(bcol)
	if GS.has_save():
		bcol.add_child(button("Lanjutkan", func(): world.start_game(true), true, 300))
	bcol.add_child(button("Main Baru", func(): world.start_game(false), true, 300))
	if _touch_mode or OS.has_feature("web"):
		bcol.add_child(button("Layar penuh", func():
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN), true, 300))
	bcol.add_child(button("Cara Main", func():
		title_screen.visible = false
		show_help(func(): if title_screen: title_screen.visible = true), true, 300))
	var credit := _label("Dibuat dengan Blender + Godot • Konsep art: Higgsfield GPT Image 2.5", 16, BROWN_SOFT)
	credit.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	credit.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	credit.position = Vector2(-330, -34)
	credit.custom_minimum_size = Vector2(660, 0)
	title_screen.add_child(credit)
	call_deferred("_focus_first", bcol)
	var tw := logo.create_tween().set_loops()
	tw.tween_property(logo, "scale", Vector2(1.03, 1.03), 1.2).set_trans(Tween.TRANS_SINE)
	tw.tween_property(logo, "scale", Vector2.ONE, 1.2).set_trans(Tween.TRANS_SINE)
	logo.pivot_offset = Vector2(180, 70)


# ------------------------------------------------------------------ touch controls
func _build_touch() -> void:
	touch = Control.new()
	touch.set_anchors_preset(Control.PRESET_FULL_RECT)
	touch.mouse_filter = Control.MOUSE_FILTER_IGNORE
	touch.visible = false
	root.add_child(touch)
	joy_base = Panel.new()
	joy_base.add_theme_stylebox_override("panel", _circle(Color(1, 0.97, 0.88, 0.35), 80, Color(1, 1, 1, 0.6)))
	joy_base.size = Vector2(160, 160)
	joy_base.mouse_filter = Control.MOUSE_FILTER_IGNORE
	joy_base.visible = false
	touch.add_child(joy_base)
	joy_knob = Panel.new()
	joy_knob.add_theme_stylebox_override("panel", _circle(Color(1, 0.97, 0.88, 0.85), 34, Color(0.55, 0.4, 0.25, 0.5)))
	joy_knob.size = Vector2(68, 68)
	joy_knob.position = Vector2(46, 46)
	joy_knob.mouse_filter = Control.MOUSE_FILTER_IGNORE
	joy_base.add_child(joy_knob)
	var hint := _label("geser untuk jalan", 16, Color(1, 1, 1, 0.85))
	hint.name = "JoyHint"
	hint.add_theme_color_override("font_outline_color", Color(0.3, 0.2, 0.1, 0.6))
	hint.add_theme_constant_override("outline_size", 6)
	touch.add_child(hint)
	action_btn = Panel.new()
	action_btn.add_theme_stylebox_override("panel", _circle(CREAM, 62, Color("a8764a")))
	action_btn.size = Vector2(124, 124)
	action_btn.mouse_filter = Control.MOUSE_FILTER_IGNORE
	touch.add_child(action_btn)
	action_label = _label("", 22, BROWN, true)
	action_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	action_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	action_label.size = Vector2(124, 124)
	action_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	action_btn.add_child(action_label)
	action_btn.modulate.a = 0.45


func _circle(color: Color, radius: int, border := Color(0, 0, 0, 0)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = color
	s.set_corner_radius_all(radius)
	s.anti_aliasing = true
	if border.a > 0:
		s.border_color = border
		s.set_border_width_all(4)
	return s


func _layout_touch(vp: Vector2) -> void:
	action_btn.position = Vector2(vp.x - 124 - 28, vp.y - 124 - 90)
	var hint: Control = touch.get_node("JoyHint")
	hint.position = Vector2(40, vp.y - 60)


func _handle_touch(event: InputEvent) -> void:
	if not hud.visible or world == null or world.state != "play":
		return
	var vp := root.get_viewport_rect().size
	# events arrive in window coordinates; convert to the canvas
	var xf := root.get_viewport().get_final_transform().affine_inverse()
	var pos: Vector2 = xf * event.position
	if event is InputEventScreenTouch:
		if event.pressed:
			if is_blocking():
				return
			var ab := Rect2(action_btn.position - Vector2(20, 20), action_btn.size + Vector2(40, 40))
			if ab.has_point(pos):
				_action_index = event.index
				action_btn.scale = Vector2(0.92, 0.92)
				action_btn.pivot_offset = action_btn.size * 0.5
				world.try_action()
				return
			if pos.x < vp.x * 0.55 and pos.y > vp.y * 0.28 and _joy_index < 0:
				_joy_index = event.index
				_joy_center = pos
				joy_base.visible = true
				joy_base.position = pos - joy_base.size * 0.5
				joy_knob.position = joy_base.size * 0.5 - joy_knob.size * 0.5
				touch.get_node("JoyHint").visible = false
		else:
			if event.index == _joy_index:
				_joy_index = -1
				joy_base.visible = false
				world.player.touch_vec = Vector2.ZERO
			if event.index == _action_index:
				_action_index = -1
				action_btn.scale = Vector2.ONE
	elif event is InputEventScreenDrag and event.index == _joy_index:
		var d: Vector2 = pos - _joy_center
		var r := 70.0
		if d.length() > r:
			d = d.normalized() * r
		joy_knob.position = joy_base.size * 0.5 - joy_knob.size * 0.5 + d
		var v := d / r
		world.player.touch_vec = v if v.length() > 0.12 else Vector2.ZERO
