extends CanvasLayer
## All 2D interface, styled after art/reference/07_target_gameplay.png:
## cream rounded pills with round icon badges (money, day/clock, Reputasi,
## Kecurigaan, energy, quest), key-prompt pills bottom-left (a tap badge next
## to the action button on touch screens), a tool hotbar bottom-right, dialogs
## (round portrait badge + speech bubble + 2-column choice pills; half-body
## anime portraits take over when assets/portraits/<name>.png exist), shop /
## list menus, morning report, pause/status panels, the title screen and the
## on-screen touch controls for phones. Open dialogs / menus push the HUD
## pieces they would cover off-screen (see _sync_hud).

const DialogView := preload("res://scripts/ui/ui_dialog.gd")
const PortraitStage := preload("res://scripts/ui/ui_portrait.gd")
const Hotbar := preload("res://scripts/ui/ui_hotbar.gd")

const CREAM := Color("fcf2dd")
const CREAM_DARK := Color("f1e0bd")
const CREAM_LIGHT := Color("fffaf0")
const LINE := Color("d8c29a")
const LINE_DARK := Color("b8986a")
const BROWN := Color("4a2f1d")
const BROWN_SOFT := Color("8a6a4a")
const INK := Color("3e2617")
const GREEN := Color("5c8a3a")
const RED := Color("c9563c")
const GOLD := Color("e9b949")
const ACCENT := Color("e8953a")
const BAR_GREEN := Color("4fb35f")
const BAR_RED := Color("e0564b")
const BAR_GOLD := Color("f2b43e")
const TITLE_BROWN := Color("6a3a18")
const FONT := preload("res://assets/fonts/Fredoka.ttf")
const TYPE_CPS := 52.0

var world: Node
var root: Control
var hud: Control
var title_screen: Control
var overlay: Control   # dims the game behind modal panels
var modal: Control     # current modal panel (dialog, menu, report...)
var prompt_pill: PanelContainer
var prompt_key: Label
var prompt_label: Label
var tools_pill: PanelContainer  ## secondary key pill "1-5 Alat" (keyboard screens)
var money_label: Label
var clock_label: Label
var clock_icon: TextureRect   # sun by day, crescent moon from dusk to dawn
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
var action_icon: TextureRect
var hotbar: HBoxContainer
var portrait_stage: Control
var tool_tip: PanelContainer
var minimap: Control
var _font_bold: FontVariation
var _font_semi: FontVariation
var _font_medium: FontVariation
var _dialog_choices: Array = []
var _typing: Label
var _typing_full := ""
var _typing_t := 0.0
var _joy_index := -1
var _joy_center := Vector2.ZERO
var _joy_home := Vector2(125, 595)
var _action_index := -1
var _touch_mode := false
var _paused := false
var _on_modal_close: Callable
var _prompt_ok := false
var _prompt_cache := ""
var _prompt_args := ["", false]  ## last set_prompt(text, ok) from the world
var _icons := {}
var _art_cache := {}
var _tile_cache := {}
var _closed_frame := -10
var _stage_owner: Control
var _last_money := -1
var _bar_tweens := {}
var _dialog_key := ""
var _toast_home := Rect2()
const TOAST_BAND := 66.0  ## room kept above tall cards for a toast
const TOAST_PAD := 70.0   ## toast pill width minus its text (badge, gap, margins)
var _layout_sig := ""


func _ready() -> void:
	layer = 10
	# Fredoka is a variable font whose default instance is Light (300). The
	# weight axis must be addressed by its integer tag: {"wght": n} is ignored.
	var wght := TextServerManager.get_primary_interface().name_to_tag("wght")
	_font_bold = FontVariation.new()
	_font_bold.base_font = FONT
	_font_bold.variation_opentype = {wght: 600}
	_font_semi = FontVariation.new()
	_font_semi.base_font = FONT
	_font_semi.variation_opentype = {wght: 470}
	_font_medium = FontVariation.new()
	_font_medium.base_font = FONT
	_font_medium.variation_opentype = {wght: 540}
	root = Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = _make_theme()
	root.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(root)
	# full-screen anime colour grade between the 3D world and the HUD (layer 5 < 10)
	var post := CanvasLayer.new()
	post.layer = 5
	post.name = "PostGrade"
	var grade := ColorRect.new()
	grade.set_anchors_preset(Control.PRESET_FULL_RECT)
	grade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var gm := ShaderMaterial.new()
	gm.shader = preload("res://shaders/post_grade.gdshader")
	grade.material = gm
	post.add_child(grade)
	add_child(post)
	_touch_mode = OS.has_feature("mobile") or OS.has_feature("web_android") or OS.has_feature("web_ios")
	_build_hud()
	_build_touch()
	overlay = ColorRect.new()
	(overlay as ColorRect).color = Color(0.12, 0.08, 0.04, 0.38)
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.visible = false
	root.add_child(overlay)
	portrait_stage = PortraitStage.new()
	portrait_stage.name = "PortraitStage"
	root.add_child(portrait_stage)
	toast_box = VBoxContainer.new()
	toast_box.alignment = BoxContainer.ALIGNMENT_BEGIN
	toast_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	toast_box.add_theme_constant_override("separation", 8)
	root.add_child(toast_box)
	GS.stats_changed.connect(_refresh_hud)
	GS.quest_changed.connect(_refresh_hud)
	GS.toast.connect(func(t, k): toast(t, k))
	get_viewport().size_changed.connect(_layout)
	_layout()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--uidemo"):
			var demo: Node = load("res://scripts/ui/ui_demo.gd").new()
			demo.set("ui", self)
			add_child(demo)


# ------------------------------------------------------------------ theme & builders
func _make_theme() -> Theme:
	var th := Theme.new()
	th.default_font = _font_semi
	th.default_font_size = 22
	th.set_color("font_color", "Label", BROWN)
	# regular buttons: cream pills with a tan outline, orange ring on focus
	var normal := _box(CREAM_LIGHT, 24, LINE, 2, true)
	var hover := _box(Color("fff5dc"), 24, ACCENT, 2, true)
	var pressed := _box(CREAM_DARK, 24, LINE_DARK, 2)
	var disabled := _box(Color(0.95, 0.91, 0.84, 0.7), 24, Color(LINE, 0.6), 2)
	var focus := _box(Color(0, 0, 0, 0), 26, ACCENT, 3)
	focus.draw_center = false
	focus.set_expand_margin_all(3)
	for st in [normal, hover, pressed, disabled]:
		_margins(st, 20, 9, 20, 10)
	th.set_stylebox("normal", "Button", normal)
	th.set_stylebox("hover", "Button", hover)
	th.set_stylebox("pressed", "Button", pressed)
	th.set_stylebox("hover_pressed", "Button", pressed)
	th.set_stylebox("disabled", "Button", disabled)
	th.set_stylebox("focus", "Button", focus)
	for c in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		th.set_color(c, "Button", BROWN)
	th.set_color("font_disabled_color", "Button", Color(0.55, 0.47, 0.38, 0.8))
	th.set_font("font", "Button", _font_bold)
	th.set_constant("h_separation", "Button", 10)
	# primary action: leaf-green pill with cream text
	th.set_type_variation("PrimaryButton", "Button")
	var pn := _box(Color("7fa047"), 24, Color("5f8336"), 2, true)
	var ph := _box(Color("8db552"), 24, ACCENT, 2, true)
	var pp := _box(Color("6b8a3a"), 24, Color("4f6e2c"), 2)
	var pd := _box(Color(0.72, 0.74, 0.62, 0.55), 24, Color(0.6, 0.62, 0.5, 0.4), 2)
	for st in [pn, ph, pp, pd]:
		_margins(st, 20, 9, 20, 10)
	th.set_stylebox("normal", "PrimaryButton", pn)
	th.set_stylebox("hover", "PrimaryButton", ph)
	th.set_stylebox("pressed", "PrimaryButton", pp)
	th.set_stylebox("hover_pressed", "PrimaryButton", pp)
	th.set_stylebox("disabled", "PrimaryButton", pd)
	for c in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		th.set_color(c, "PrimaryButton", CREAM_LIGHT)
	th.set_color("font_disabled_color", "PrimaryButton", Color(1, 1, 1, 0.8))
	# dialog choices: pill with its content (dot + labels) as child controls
	th.set_type_variation("ChoiceButton", "Button")
	var cn := _box(CREAM_LIGHT, 28, LINE, 2)
	var ch := _box(Color("fff4d8"), 28, ACCENT, 2, true)
	var cp := _box(CREAM_DARK, 28, LINE_DARK, 2)
	var cd := _box(Color(0.96, 0.93, 0.86, 0.75), 28, Color(LINE, 0.5), 2)
	for st in [cn, ch, cp, cd]:
		_margins(st, 8, 4, 8, 4)
	th.set_stylebox("normal", "ChoiceButton", cn)
	th.set_stylebox("hover", "ChoiceButton", ch)
	th.set_stylebox("pressed", "ChoiceButton", cp)
	th.set_stylebox("hover_pressed", "ChoiceButton", cp)
	th.set_stylebox("disabled", "ChoiceButton", cd)
	# no focus ring: the selected pill gets an orange dot + warm fill instead
	th.set_stylebox("focus", "ChoiceButton", StyleBoxEmpty.new())
	# panels: cream cards with a tan outline and a soft shadow
	var panel_box := _box(CREAM, 26, LINE, 3, true)
	panel_box.shadow_size = 16
	panel_box.shadow_offset = Vector2(0, 6)
	panel_box.shadow_color = Color(0.2, 0.12, 0.04, 0.3)
	_margins(panel_box, 26, 20, 26, 20)
	th.set_stylebox("panel", "PanelContainer", panel_box)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0)
	th.set_stylebox("panel", "ScrollContainer", sb)
	var grab := _box(Color("c8b08a"), 8)
	th.set_stylebox("grabber", "VScrollBar", grab)
	th.set_stylebox("grabber_highlight", "VScrollBar", _box(Color("b8986a"), 8))
	th.set_stylebox("grabber_pressed", "VScrollBar", _box(Color("a8875a"), 8))
	var track := _box(Color(0.8, 0.72, 0.58, 0.25), 8)
	_margins(track, 3, 0, 3, 0)
	th.set_stylebox("scroll", "VScrollBar", track)
	return th


func _box(color: Color, radius: int, border := Color(0, 0, 0, 0), border_w := 0, shadow := false) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = color
	s.set_corner_radius_all(radius)
	s.anti_aliasing = true
	s.corner_detail = 10
	if border_w > 0:
		s.border_color = border
		s.set_border_width_all(border_w)
	if shadow:
		s.shadow_color = Color(0.25, 0.14, 0.05, 0.24)
		s.shadow_size = 6
		s.shadow_offset = Vector2(0, 3)
	return s


func _margins(s: StyleBox, l: float, t: float, r: float, b: float) -> void:
	s.content_margin_left = l
	s.content_margin_top = t
	s.content_margin_right = r
	s.content_margin_bottom = b


func _pill(content: Control, color := CREAM, l := 6.0, r := 18.0) -> PanelContainer:
	var p := PanelContainer.new()
	var s := _box(color, 30, LINE, 2, true)
	_margins(s, l, 4, r, 4)
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


func _smooth(tex: Texture2D, crop := false, max_h := 0) -> Texture2D:
	## Returns a mipmapped copy (optionally cropped to the opaque area and
	## downscaled) so big images stay crisp when drawn small. Falls back to
	## the original texture if the pixels cannot be read back.
	if tex == null:
		return null
	var img: Image = tex.get_image()
	if img == null or img.is_empty():
		return tex
	if img.is_compressed() and img.decompress() != OK:
		return tex
	if img.get_format() != Image.FORMAT_RGBA8:
		img.convert(Image.FORMAT_RGBA8)
	var framed := false
	if crop:
		framed = _opaque_edges(img)
		var used := img.get_used_rect()
		if not framed and used.size.x > 8 and used.size.y > 8 and used.size != img.get_size():
			img = img.get_region(used)
	if max_h > 0 and img.get_height() > max_h:
		img.resize(maxi(1, int(round(img.get_width() * float(max_h) / img.get_height()))), max_h, Image.INTERPOLATE_CUBIC)
	img.fix_alpha_edges()
	img.generate_mipmaps()
	var out := ImageTexture.create_from_image(img)
	if framed:
		out.set_meta("framed", true)
	return out


func icon(name: String) -> Texture2D:
	if not _icons.has(name):
		var path := "res://assets/icons/%s.png" % name
		_icons[name] = _smooth(load(path)) if name != "" and ResourceLoader.exists(path) else null
	return _icons[name]


func _icon_rect(name: String, size := 30) -> Control:
	var tex := icon(name)
	if tex:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tr.custom_minimum_size = Vector2(size, size)
		tr.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		return tr
	# fallback: a plain round badge
	var p := Panel.new()
	p.add_theme_stylebox_override("panel", _box(Color("a8764a"), size / 2))
	p.custom_minimum_size = Vector2(size, size)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return p


func _round_badge(text: String, size := 30, color := INK) -> Control:
	var p := PanelContainer.new()
	var s := _box(color, size / 2)
	_margins(s, 4, 0, 4, 0)
	p.add_theme_stylebox_override("panel", s)
	p.custom_minimum_size = Vector2(size, size)
	p.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var l := _label(text, int(size * 0.56), CREAM_LIGHT, true)
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


func _bar(color: Color, w := 110, h := 13) -> ProgressBar:
	var b := ProgressBar.new()
	b.show_percentage = false
	b.custom_minimum_size = Vector2(w, h)
	b.min_value = 0
	b.max_value = 100
	var bg := _box(Color("e9dcc2"), 8, Color("d9c6a2"), 1)
	var fg := _box(color, 8)
	b.add_theme_stylebox_override("background", bg)
	b.add_theme_stylebox_override("fill", fg)
	b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	b.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return b


func _set_bar(b: ProgressBar, v: float) -> void:
	if absf(b.value - v) < 0.01:
		return
	if _bar_tweens.has(b) and (_bar_tweens[b] as Tween).is_valid():
		(_bar_tweens[b] as Tween).kill()
	var tw := b.create_tween()
	tw.tween_property(b, "value", v, 0.45).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_bar_tweens[b] = tw


func button(text: String, cb: Callable, enabled := true, min_w := 0, primary := false) -> Button:
	var b := Button.new()
	b.text = text
	b.disabled = not enabled
	b.custom_minimum_size = Vector2(min_w, 50 if _touch_mode else 46)
	b.add_theme_font_size_override("font_size", 21)
	if primary:
		b.theme_type_variation = "PrimaryButton"
	b.pressed.connect(func():
		Sfx.play("click", 1.0, -6.0)
		cb.call())
	return b


# ------------------------------------------------------------------ portraits
func portrait_key(portrait: String, speaker := "") -> String:
	## "portrait_kakek" -> "kakek"; the phone boss and Mak Inah get their own art.
	if portrait == "icon_uang" or speaker.contains("Pusat"):
		return "hq"
	if speaker.contains("Mak Inah"):
		return "mak"
	return portrait.trim_prefix("portrait_").trim_prefix("icon_")


func portrait_art(key: String) -> Texture2D:
	## 2D anime half-body art (res://assets/portraits/<key>.png), cropped to its
	## opaque area and mipmapped; null if it does not exist (yet).
	if key == "":
		return null
	if not _art_cache.has(key):
		var path := "res://assets/portraits/%s.png" % key
		_art_cache[key] = _smooth(load(path), true, 720) if ResourceLoader.exists(path) else null
	return _art_cache[key]


func _opaque_edges(img: Image) -> bool:
	## True when the picture has no transparent background (the generator
	## failed to cut it out): the stage then shows it as a rounded card.
	var w := img.get_width() - 2
	var h := img.get_height() - 2
	var n := 0
	for p in [Vector2i(1, 1), Vector2i(w, 1), Vector2i(1, h / 2), Vector2i(w, h / 2)]:
		if img.get_pixelv(p).a > 0.6:
			n += 1
	return n >= 3


func portrait_fallback(portrait: String, key: String) -> Texture2D:
	## The 3D head render (icons/portrait_<key>.png) or the given icon. Head
	## renders are tagged "bust" so the badge lets the head pop out on top.
	## Speakers without a render of their own get a glyph badge (the phone for
	## HQ, the stall for Mak Inah) rather than somebody else's face.
	var names := ["portrait_" + key, portrait]
	if key == "hq":
		names = ["ui_phone"]
	elif key == "mak":
		names = ["portrait_mak", "ui_warung"]
	for n in names:
		var t := icon(n)
		if t:
			if n.begins_with("portrait_"):
				t.set_meta("bust", true)
			return t
	return null


# ------------------------------------------------------------------ HUD
func _stat_pill(icon_name: String, label: Label, badge := 42) -> PanelContainer:
	var p := _pill(_hrow([_icon_rect(icon_name, badge), label], 10), CREAM, 4, 20)
	return p


func _meter_pill(icon_name: String, title: String, bar: ProgressBar, badge := 42) -> PanelContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var t := _label(title, 16, BROWN, true)
	v.add_child(t)
	v.add_child(bar)
	return _pill(_hrow([_icon_rect(icon_name, badge), v], 10), CREAM, 4, 18)


func _build_hud() -> void:
	hud = Control.new()
	hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(hud)
	# top-left: money + day/clock, energy, quest
	var tl := VBoxContainer.new()
	tl.name = "TopLeft"
	tl.position = Vector2(16, 14)
	tl.add_theme_constant_override("separation", 8)
	tl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(tl)
	money_label = _label("Rp 0", 23, BROWN, true)
	clock_label = _label("Hari 1   06:00", 23, BROWN, true)
	var money_pill := _stat_pill("ui_coins", money_label)
	money_pill.name = "MoneyPill"
	var clock_pill := _stat_pill("ui_sun", clock_label)
	clock_icon = clock_pill.get_child(0).get_child(0) as TextureRect
	var row1 := _hrow([money_pill, clock_pill], 10)
	row1.name = "Row1"
	tl.add_child(row1)
	energy_bar = _bar(BAR_GOLD, 132, 12)
	var ep := _meter_pill("ui_energy", "Energi", energy_bar, 36)
	tl.add_child(_hrow([ep]))
	quest_label = _label("", 18, BROWN)
	quest_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	quest_label.custom_minimum_size = Vector2(330, 0)
	quest_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var qp := _pill(_hrow([_icon_rect("ui_quest", 36), quest_label], 10), CREAM, 4, 18)
	qp.name = "QuestPill"
	tl.add_child(_hrow([qp]))
	# top-right: reputation & suspicion meters, Status/Menu, minimap
	var tr := VBoxContainer.new()
	tr.name = "TopRight"
	tr.add_theme_constant_override("separation", 8)
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(tr)
	rep_bar = _bar(BAR_GREEN, 196)
	heat_bar = _bar(BAR_RED, 196)
	tr.add_child(_meter_pill("ui_leaf", "Reputasi", rep_bar))
	tr.add_child(_meter_pill("ui_eye", "Kecurigaan", heat_bar))
	var menu_row := HBoxContainer.new()
	menu_row.name = "Buttons"
	menu_row.alignment = BoxContainer.ALIGNMENT_END
	menu_row.add_theme_constant_override("separation", 8)
	var bagb := button("", show_bag)
	bagb.name = "BagButton"
	bagb.tooltip_text = "Tas (B)"
	var sb := button("Status", show_status)
	var mb := button("Menu", toggle_pause)
	for pair in [[bagb, "ui_bag"], [sb, "ui_status"], [mb, "ui_menu"]]:
		var b: Button = pair[0]
		b.icon = icon(pair[1])
		b.add_theme_constant_override("icon_max_width", 30)
		b.custom_minimum_size = Vector2(0, 44)
		b.add_theme_font_size_override("font_size", 19)
		var st := _box(CREAM, 24, LINE, 2, true)
		var rpad := 16 if b.text != "" else 6
		_margins(st, 6, 6, rpad, 6)
		b.add_theme_stylebox_override("normal", st)
		var sth := _box(CREAM_LIGHT, 24, ACCENT, 2, true)
		_margins(sth, 6, 6, rpad, 6)
		b.add_theme_stylebox_override("hover", sth)
		b.focus_mode = Control.FOCUS_NONE
		menu_row.add_child(b)
	tr.add_child(menu_row)
	minimap = preload("res://scripts/ui/minimap.gd").new()
	minimap.name = "Minimap"
	minimap.world = world
	minimap.ui = self
	minimap.font = _font_bold
	hud.add_child(minimap)
	# bottom-left: key prompt pill like "E  Panen"
	var prompts := HBoxContainer.new()
	prompts.name = "Prompts"
	prompts.add_theme_constant_override("separation", 10)
	prompts.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(prompts)
	var kb := _round_badge("E", 34)
	kb.name = "KeyBadge"
	prompt_key = kb.get_child(0)
	# on touch screens the badge shows a tapping finger (the round action
	# button does the job of the E key); "not possible" prompts show an info dot
	var kic := TextureRect.new()
	kic.name = "Icon"
	kic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	kic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	kic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	kic.visible = false
	kb.add_child(kic)
	prompt_label = _label("", 21, BROWN, true)
	prompt_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	prompt_pill = _pill(_hrow([kb, prompt_label], 12), CREAM, 5, 22)
	prompt_pill.name = "Prompt"
	prompt_pill.visible = false
	prompts.add_child(prompt_pill)
	# keyboard screens: a second, quieter key pill telling how to look at the
	# tools (the target shows two pills bottom-left: "E Panen", "Q Ganti alat")
	var tkb := _round_badge("1-5", 34)
	(tkb.get_child(0) as Label).add_theme_font_size_override("font_size", 15)
	tools_pill = _pill(_hrow([tkb, _label("Alat", 19, BROWN, true)], 10), CREAM, 5, 18)
	tools_pill.name = "ToolsHint"
	tools_pill.visible = false
	prompts.add_child(tools_pill)
	# bottom-right: tool hotbar
	hotbar = Hotbar.new()
	hotbar.name = "Inventory"
	hotbar.ui = self
	hud.add_child(hotbar)
	hotbar.build(66.0)
	inv_labels = hotbar.labels
	hotbar.slot_pressed.connect(_show_tool_tip)
	tool_tip = _pill(_label("", 18, BROWN), CREAM_LIGHT, 16, 16)
	tool_tip.name = "ToolTip"
	tool_tip.visible = false
	hud.add_child(tool_tip)
	hud.visible = false


func _layout() -> void:
	# phones held upright: enlarge the UI so text stays readable
	var win := Vector2(get_tree().root.size)
	var want := 1.0 if win.x >= win.y else 1.35
	if _touch_mode and win.x >= win.y:
		# landscape phones: at least ~0.8 CSS px per UI px, so 15-16 px hints
		# stay >= 12 px on screen (915x412: 0.57 stretch -> 1.4 content scale)
		var css := win / _dpr()
		var stretch := minf(css.x / 1280.0, css.y / 720.0)
		# (smaller than before: the HUD covered too much of the play area on phones)
		want = clampf(0.62 / maxf(stretch, 0.01), 0.95, 1.1)
		want = snappedf(want, 0.05)
	if not is_equal_approx(get_tree().root.content_scale_factor, want):
		get_tree().root.content_scale_factor = want
		call_deferred("_layout")
		return
	var vp := root.get_viewport_rect().size
	var portrait := vp.x < vp.y
	var tl: Control = hud.get_node("TopLeft")
	var tr: Control = hud.get_node("TopRight")
	var row1: Control = tl.get_node("Row1")
	var trs := tr.get_combined_minimum_size()
	var row1_w := row1.get_combined_minimum_size().x
	var tr_y := 14.0
	if row1_w + trs.x + 48.0 > vp.x:
		# narrow screen: meters go under the money/clock row on the right
		tr_y = 14.0 + row1.get_combined_minimum_size().y + 8.0
	var free_w := vp.x - 16.0 - (trs.x + 32.0 if tr_y > 14.0 else 0.0)
	quest_label.custom_minimum_size.x = clampf(minf(vp.x * 0.3, free_w - 80.0), 200.0, 360.0)
	tl.size = Vector2.ZERO
	tr.size = Vector2.ZERO
	_place(tl, Vector2(16, 14))
	var tr_pos := Vector2(vp.x - trs.x - 16.0, tr_y)
	_place(tr, tr_pos)
	if minimap:
		if minimap.big:
			var w := minf(vp.x - 40, (vp.y - 40) * 170.0 / 150.0)
			minimap.size = Vector2(w, w * 150.0 / 170.0)
			_place(minimap, ((vp - minimap.size) * 0.5).round())
		else:
			var small := Vector2(206, 182) if vp.y >= 640 else Vector2(156, 138)
			minimap.size = small
			_place(minimap, Vector2(vp.x - small.x - 16, tr_pos.y + trs.y + 10))
	var inv_size := hotbar.get_combined_minimum_size()
	hotbar.size = inv_size
	if _touch_mode:
		_place(hotbar, Vector2(roundf(vp.x * 0.5 - inv_size.x * 0.5), vp.y - inv_size.y - 14))
	else:
		_place(hotbar, Vector2(vp.x - inv_size.x - 18, vp.y - inv_size.y - 16))
	if touch:
		_layout_touch(vp)
	_place_prompt(vp)
	# toasts: top-centre gap between the pill clusters, else below them
	var gap_l := 16.0 + row1_w + 14.0
	var gap_r := tr_pos.x - 14.0
	var tw := floorf(minf(560.0, gap_r - gap_l))
	if tr_y <= 14.0 and tw >= 360.0:
		# floored: the slot never pokes past gap_r by a rounding half-pixel
		_toast_home = Rect2(floorf((gap_l + gap_r - tw) * 0.5), 14, tw, 0)
	else:
		tw = minf(560.0, vp.x - 32.0)
		var below := maxf(14.0 + tl.get_combined_minimum_size().y, tr_pos.y + trs.y) + 12.0
		if portrait and minimap and not minimap.big:
			below = maxf(below, _home(minimap).y + minimap.size.y + 12.0)
		_toast_home = Rect2(roundf(vp.x * 0.5 - tw * 0.5), below, tw, 0)
	if modal:
		_center_modal()
	_sync_hud()


func _dpr() -> float:
	## Device pixels per CSS pixel (web) / per logical screen point.
	var d := DisplayServer.screen_get_scale()
	return d if d > 0.0 else 1.0


func screen_scale() -> float:
	## On-screen (CSS) pixels per UI canvas pixel: the window stretch times the
	## content scale, over the device pixel ratio. 1.0 at 1280x720 desktop.
	return get_tree().root.get_final_transform().get_scale().x / _dpr()


func _toast_rect() -> Rect2:
	## Where toasts go right now: the HUD's top gap, or the top edge while a
	## card modal has cleared the HUD (into the band _center_modal keeps free).
	if modal != null and not modal.has_meta("self_layout"):
		var vp := root.get_viewport_rect().size
		var tw := minf(560.0, vp.x - 32.0)
		return Rect2(roundf(vp.x * 0.5 - tw * 0.5), 8, tw, 0)
	return _toast_home


func _toast_text_w(l: Label, slot_w: float) -> float:
	## Short messages get a compact pill, long ones wrap at the slot width.
	return clampf(float(l.get_meta("natural_w", slot_w)), minf(160.0, slot_w - TOAST_PAD), slot_w - TOAST_PAD)


func _place_toasts() -> void:
	var r := _toast_rect()
	if r.size.x <= 0.0:
		return
	# rows first: a Control never shrinks below its children, so setting the
	# box width before the labels left it stuck at the wider card-mode width
	for t in toast_box.get_children():
		var l: Label = t.find_child("Text", true, false)
		if l:
			l.custom_minimum_size.x = _toast_text_w(l, r.size.x)
	toast_box.custom_minimum_size = Vector2(r.size.x, 0)
	toast_box.position = r.position
	toast_box.size = Vector2(r.size.x, 0)
	# above a tall card only the newest toasts that fit in the band are shown
	var live := toast_box.get_children().filter(func(t): return not t.is_queued_for_deletion())
	var room := live.size()
	if modal != null and not modal.has_meta("self_layout"):
		room = maxi(1, int((modal.position.y - r.position.y) / 48.0))
	for i in live.size():
		live[i].visible = i >= live.size() - room


func _place_prompt(vp: Vector2) -> void:
	var prompts: Control = hud.get_node("Prompts")
	var ps := prompts.get_combined_minimum_size()
	prompts.size = ps
	var at := Vector2(16, vp.y - ps.y - 16)
	if _touch_mode:
		# next to the round action button it stands for; above the hotbar
		# when the screen is too narrow for that
		at = Vector2(action_btn.position.x - ps.x - 16.0, roundf(action_btn.position.y + (action_btn.size.y - ps.y) * 0.5))
		if at.x < 16.0 or Rect2(at, ps).grow(8.0).intersects(Rect2(_home(hotbar), hotbar.size)):
			at = Vector2(roundf(vp.x * 0.5 - ps.x * 0.5), _home(hotbar).y - ps.y - 18)
	_place(prompts, at)
	if tool_tip.visible:
		var ts := tool_tip.get_combined_minimum_size()
		tool_tip.size = ts
		var hb := _home(hotbar)
		# right-aligned over the desktop hotbar; centred over the touch one (the
		# action prompt sits to its right)
		var tx := hb.x + hotbar.size.x - ts.x
		if _touch_mode:
			tx = hb.x + (hotbar.size.x - ts.x) * 0.5
		tool_tip.position = Vector2(clampf(tx, 12, vp.x - ts.x - 12), hb.y - ts.y - 16).round()


# ------------------------------------------------------------------ HUD vs modals
# Every HUD piece has a "home" position (set by _layout) and a hide amount k
# (0 shown .. 1 hidden). Hidden pieces slide off the nearest screen edge and
# fade, so dialogs / menus never sit on top of pills, the minimap or the
# hotbar: card modals (menus, reports, pause) clear the whole HUD (shop menus
# show the wallet themselves); dialogs clear only the pieces their panel /
# portrait would touch. On keyboard screens the dialog keeps to the gap
# between the key hint and the hotbar when it can (dialog_band), so at
# 1280x720 the whole HUD stays, as in the target; on touch screens the bottom
# HUD (joystick, action button, hotbar) always makes way.
func _place(p: Control, home: Vector2) -> void:
	p.set_meta("home", home)
	_apply_hud(p)


func _home(p: Control) -> Vector2:
	return p.get_meta("home", p.position)


func _slide_vec(p: Control) -> Vector2:
	if p == touch:
		return Vector2.ZERO
	if p == minimap:
		return Vector2.ZERO if minimap.big else Vector2(p.size.x + 40.0, 0)
	if p == hotbar or p.name == "Prompts":
		return Vector2(0, p.size.y + 40.0)
	return Vector2(0, -(p.size.y + 40.0))


func _apply_hud(p: Control) -> void:
	var k: float = p.get_meta("hide_k", 0.0)
	var e := k * k * (3.0 - 2.0 * k)
	p.position = (_home(p) + _slide_vec(p) * e).round()
	p.modulate.a = 1.0 - k
	if p != touch:
		p.visible = k < 0.995


func _hud_hide(p: Control, hide: bool, instant := false) -> void:
	if p == null:
		return
	var target := 1.0 if hide else 0.0
	if is_equal_approx(float(p.get_meta("hide_to", 0.0)), target) and not instant:
		return
	p.set_meta("hide_to", target)
	if p.has_meta("hide_tw"):
		var old: Tween = p.get_meta("hide_tw")
		if old and old.is_valid():
			old.kill()
	var from: float = p.get_meta("hide_k", 0.0)
	if instant or not hud.visible:
		p.set_meta("hide_k", target)
		_apply_hud(p)
		return
	var tw := create_tween()
	tw.tween_method(func(k: float):
		p.set_meta("hide_k", k)
		_apply_hud(p), from, target, 0.2 if hide else 0.28)
	p.set_meta("hide_tw", tw)


func _hud_top() -> Array:
	return [hud.get_node("TopLeft"), hud.get_node("TopRight"), minimap]


func _sync_hud() -> void:
	## Moves HUD pieces out of the current modal's way (or back home).
	if hud == null:
		return
	var dialog_open := modal != null and modal.has_meta("self_layout")
	var card := modal != null and not dialog_open
	var blocked: Array = modal.occupied_rects() if dialog_open and modal.has_method("occupied_rects") else []
	var prompts: Control = hud.get_node("Prompts")
	for p in _hud_top() + [prompts, hotbar]:
		var hide: bool = card or (p == minimap and world != null and world.inside != "")
		if dialog_open:
			if _touch_mode and (p == prompts or p == hotbar):
				hide = true  # the thumb area: the dialog takes the taps
			else:
				var r := Rect2(_home(p), p.size).grow(10.0)
				for b in blocked:
					if r.intersects(b):
						hide = true
		_hud_hide(p, hide)
	_hud_hide(touch, modal != null)
	if modal != null:
		tool_tip.visible = false
	_place_toasts()


func show_hud() -> void:
	_close_modal()
	if title_screen:
		title_screen.queue_free()
		title_screen = null
	hud.visible = true
	touch.visible = _touch_mode
	_prompt_cache = ""
	_sync_hud()
	_refresh_hud()


func _clock_text() -> String:
	if clock_icon:
		var night := GS.hour >= 18.5 or GS.hour < 5.5
		var want := icon("ui_moon" if night else "ui_sun")
		if want and clock_icon.texture != want:
			clock_icon.texture = want
	return "Hari %d   %s" % [GS.day, GS.clock_text()]


func _refresh_hud() -> void:
	money_label.text = GS.fmt_rp(GS.money)
	if _last_money >= 0 and GS.money != _last_money and hud.visible:
		var mp: Control = hud.find_child("MoneyPill", true, false)
		if mp:
			mp.pivot_offset = mp.size * 0.5
			var tw := mp.create_tween()
			tw.tween_property(mp, "scale", Vector2(1.07, 1.07), 0.08)
			tw.tween_property(mp, "scale", Vector2.ONE, 0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			money_label.add_theme_color_override("font_color", Color("3f7f2a") if GS.money > _last_money else RED)
			tw.tween_callback(func(): money_label.add_theme_color_override("font_color", BROWN))
	_last_money = GS.money
	if modal and modal.has_meta("money_label"):
		var wl = modal.get_meta("money_label")
		if is_instance_valid(wl):
			wl.text = money_label.text
	clock_label.text = _clock_text()
	var e: float = GS.energy / GS.max_energy * 100.0
	_set_bar(energy_bar, e)
	var fill := energy_bar.get_theme_stylebox("fill") as StyleBoxFlat
	var ecol := BAR_RED if e < 25.0 else BAR_GOLD
	if fill.bg_color != ecol:
		fill.bg_color = ecol
	_set_bar(rep_bar, (GS.rep + 100.0) * 0.5)
	_set_bar(heat_bar, GS.heat)
	quest_label.text = "Misi: " + GS.current_quest()
	hotbar.update_counts()
	# stats_changed fires every frame while the clock runs: only re-layout
	# when something that changes pill sizes actually changed
	var sig := "%s|%s|%s" % [money_label.text, quest_label.text, hotbar.get_combined_minimum_size()]
	if sig != _layout_sig:
		_layout_sig = sig
		call_deferred("_layout")


# ------------------------------------------------------------------ context prompt + hotbar
func _tile_of(t: Dictionary) -> Array:
	if t.has("pid") and t.has("idx"):
		return [int(t["pid"]), int(t["idx"])]
	if world == null or not ("tile_views" in world):
		return []
	var pos: Vector3 = t.get("_pos", t.get("pos", Vector3.ZERO))
	if _tile_cache.has(pos):
		return _tile_cache[pos]
	var best: Array = []
	var bd := INF
	for key in world.tile_views:
		var tv: Node3D = world.tile_views[key]
		var d := Vector2(tv.global_position.x - pos.x, tv.global_position.z - pos.z).length_squared()
		if d < bd:
			bd = d
			var parts := str(key).split(":")
			if parts.size() == 2:
				best = [int(parts[0]), int(parts[1])]
	if bd < 2.0:
		_tile_cache[pos] = best
		return best
	return []


func _context_kind(text: String, ok: bool) -> String:
	## Which tool the current context action uses: clear / plant / fert /
	## harvest (tiles, via GS.tile_action_info) or sell (at the mill).
	if world == null or not ok or text == "":
		return ""
	var t: Dictionary = world.target
	if t.is_empty():
		return ""
	if t.has("tile"):
		var ti := _tile_of(t)
		if ti.size() == 2:
			var info: Dictionary = GS.tile_action_info(ti[0], ti[1])
			return str(info.get("kind", "")) if info.get("ok", false) else ""
	var low := text.to_lower()
	if low.begins_with("tebas"):
		return "clear"
	if low.begins_with("tanam"):
		return "plant"
	if low.contains("pupuk") and low.begins_with("beri"):
		return "fert"
	if low.begins_with("panen"):
		return "harvest"
	if low.contains("pabrik") and int(GS.inv.get("tbs", 0)) > 0:
		return "sell"
	return ""


func set_prompt(text: String, ok: bool) -> void:
	_prompt_args = [text, ok]
	var blocking := is_blocking()
	var hint := _modal_hint()
	var cache := ("hint|" + hint) if hint != "" else "%s|%s|%s|%s" % [text, ok, blocking, _touch_mode]
	_prompt_ok = ok or hint != ""
	if cache == _prompt_cache:
		return
	_prompt_cache = cache
	tools_pill.visible = not _touch_mode and hint == "" and not blocking
	var kind := _context_kind(text, ok) if not blocking else ""
	hotbar.set_active(kind)
	if action_label:
		action_label.text = _short_verb(text) if ok and not blocking else ""
		var slot_icon := ""
		if ok and not blocking and (text == "Mancing" or text.begins_with("Tarik") or text.begins_with("Tunggu")):
			slot_icon = "icon_pancing"
		elif ok and not blocking and text.begins_with("Tidur"):
			slot_icon = "icon_kasur"
		if kind != "":
			for sl in Hotbar.SLOTS:
				if sl["kind"] == kind:
					slot_icon = sl["icon"]
		action_icon.texture = icon(slot_icon) if slot_icon != "" else null
		action_label.position.y = 66.0 if action_icon.texture else 0.0
		action_label.size.y = 44.0 if action_icon.texture else 124.0
		action_btn.modulate.a = 1.0 if ok and not blocking and text != "" else 0.45
	if hint != "":
		# keyboard dialogs keep a key hint bottom-left, like the target's
		# prompt pills beside its dialog: E picks the highlighted choice
		_show_key_prompt(hint, "", true)
	elif text == "" or blocking or (_touch_mode and ok):
		# touch screens: the round action button already names a possible action
		# ("Panen"), so the pill only speaks up for "not yet" reasons
		prompt_pill.visible = false
		call_deferred("_place_prompt", root.get_viewport_rect().size)
		return
	else:
		# E key on keyboards, a tapping finger on touch screens (the round action
		# button bottom-right), an info dot when the action is not possible yet
		_show_key_prompt(text, "" if ok and not _touch_mode else ("ui_tap" if ok else "ui_info"), ok)
	var pop := prompt_pill.create_tween()
	prompt_pill.pivot_offset = Vector2(0, prompt_pill.size.y * 0.5)
	prompt_pill.scale = Vector2(0.94, 0.94)
	pop.tween_property(prompt_pill, "scale", Vector2.ONE, 0.16).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	call_deferred("_place_prompt", root.get_viewport_rect().size)


func _modal_hint() -> String:
	## Key hint for the open dialog (keyboard screens only), else "".
	if _touch_mode or modal == null or not modal.has_meta("self_layout") or modal.is_queued_for_deletion():
		return ""
	return "Lanjut" if modal.choices.size() <= 1 else "Pilih"


func _show_key_prompt(text: String, glyph: String, ok: bool) -> void:
	## Fills the prompt pill: key badge ("E", or a glyph icon: ui_tap / ui_info)
	## + label.
	prompt_pill.visible = true
	prompt_label.text = text
	var kb: PanelContainer = prompt_pill.find_child("KeyBadge", true, false)
	var kic: TextureRect = kb.get_node("Icon")
	prompt_key.text = "E"
	prompt_key.visible = glyph == ""
	kic.texture = icon(glyph) if glyph != "" else null
	kic.visible = kic.texture != null
	if glyph != "" and kic.texture == null:
		prompt_key.text = "i" if not ok else "E"
		prompt_key.visible = true
	# the glyph icons are complete round badges; the key letter sits on ink
	var ks := _box(Color(0, 0, 0, 0) if kic.visible else (INK if ok else Color("a8875a")), 17)
	_margins(ks, 0 if kic.visible else 4, 0, 0 if kic.visible else 4, 0)
	kb.add_theme_stylebox_override("panel", ks)
	kb.visible = true
	prompt_label.add_theme_color_override("font_color", BROWN if ok else BROWN_SOFT)
	prompt_pill.modulate.a = 1.0 if ok else 0.92


func dialog_band(vp: Vector2) -> Vector2:
	## Free x-range [from, to] along the bottom edge between the key hint
	## (bottom-left) and the hotbar (bottom-right) on keyboard screens: a dialog
	## inside it leaves both in view, as in the target. Zero on touch screens.
	if _touch_mode:
		return Vector2.ZERO
	var prompts: Control = hud.get_node("Prompts")
	var l := 16.0
	if prompt_pill.visible and prompts.size.x > 0.0:
		l = _home(prompts).x + prompt_pill.size.x + 14.0
	return Vector2(l, _home(hotbar).x - 14.0)


func _short_verb(text: String) -> String:
	var w := text.split(" ")
	return w[0] if w.size() > 0 else text


func _show_tool_tip(id: String) -> void:
	var d: Dictionary = hotbar.slot_def(id)
	if d.is_empty() or modal != null:
		return
	Sfx.play("click", 1.2, -10.0)
	var l: Label = tool_tip.get_child(0)
	l.text = "%s — %s" % [d["name"], d["hint"]]
	tool_tip.visible = true
	tool_tip.modulate.a = 1.0
	_place_prompt(root.get_viewport_rect().size)
	if tool_tip.has_meta("tw"):
		var old: Tween = tool_tip.get_meta("tw")
		if old and old.is_valid():
			old.kill()
	var tw := tool_tip.create_tween()
	tw.tween_interval(2.2)
	tw.tween_property(tool_tip, "modulate:a", 0.0, 0.4)
	tw.tween_callback(func(): tool_tip.visible = false)
	tool_tip.set_meta("tw", tw)


func _unhandled_input(event: InputEvent) -> void:
	# number keys 1-5 outside dialogs: show what that hotbar slot is for
	if modal or not hud.visible or not (event is InputEventKey) or not event.pressed or event.echo:
		return
	var k: int = event.keycode
	if k >= KEY_1 and k <= KEY_5:
		var id: String = hotbar.id_for_number(k - KEY_0)
		if id != "":
			hotbar.flash(id)
			_show_tool_tip(id)


func toast(text: String, kind := "info") -> void:
	var col := CREAM
	var ic := "ui_info"
	match kind:
		"bad":
			col = Color("fbe3d6")
			ic = "ui_bad"
		"good":
			col = Color("eef3d8")
			ic = "ui_good"
		"quest":
			col = Color("fcecc0")
			ic = "ui_star"
	var l := _label(text, 19, BROWN)
	l.name = "Text"
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	# sized from the slot toasts go to now (never from toast_box.size, which
	# only grows)
	l.set_meta("natural_w", ceilf(_font_semi.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 19).x) + 2.0)
	l.custom_minimum_size = Vector2(_toast_text_w(l, _toast_rect().size.x), 0)
	l.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var p := _pill(_hrow([_icon_rect(ic, 32), l], 10), col, 6, 18)
	p.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	toast_box.add_child(p)
	_place_toasts()
	if kind == "quest":
		Sfx.play("quest")
	p.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(p, "modulate:a", 1.0, 0.2)
	tw.tween_interval(3.2 if kind != "quest" else 4.5)
	tw.tween_property(p, "modulate:a", 0.0, 0.5)
	tw.tween_callback(p.queue_free)
	while toast_box.get_child_count() > 4:
		var old := toast_box.get_child(0)
		toast_box.remove_child(old)
		old.queue_free()


# ------------------------------------------------------------------ modal plumbing
func is_blocking() -> bool:
	return modal != null or title_screen != null or _paused


func _open_modal(panel: Control, dim := true, on_close := Callable()) -> void:
	var chained := modal != null or _closed_frame == Engine.get_process_frames()
	var was_dim := overlay.visible and overlay.modulate.a > 0.5
	_close_modal()
	modal = panel
	_on_modal_close = on_close
	overlay.visible = dim
	if dim and not (chained and was_dim):
		overlay.modulate.a = 0.0
		create_tween().tween_property(overlay, "modulate:a", 1.0, 0.18)
	elif dim:
		overlay.modulate.a = 1.0
	root.add_child(panel)
	# dialog portraits stand in front of their panel (visual-novel style);
	# shopkeepers stand behind the menu card. Toasts stay on top of all.
	root.move_child(portrait_stage, -1)
	if not panel.has_meta("self_layout"):
		root.move_child(panel, -1)
	root.move_child(toast_box, -1)
	if panel.has_meta("self_layout"):
		_stage_owner = panel
		_prompt_cache = ""
		set_prompt(_prompt_args[0], _prompt_args[1])
		_place_prompt(root.get_viewport_rect().size)
		panel.relayout(root.get_viewport_rect().size)
		panel.play_in()
	else:
		panel.resized.connect(_center_modal)
		_center_modal()
		call_deferred("_center_modal")
		if not chained:
			panel.modulate.a = 0.0
			panel.scale = Vector2(0.96, 0.96)
			var tw := create_tween()
			tw.tween_property(panel, "modulate:a", 1.0, 0.16)
			tw.parallel().tween_property(panel, "scale", Vector2.ONE, 0.2).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	if minimap and minimap.big:
		minimap.big = false
		_layout()
	_sync_hud()
	if world and world.player:
		world.player.locked = true
		world.player.touch_vec = Vector2.ZERO
	_joy_index = -1
	if joy_base:
		joy_base.position = _joy_home - joy_base.size * 0.5
		joy_knob.position = joy_base.size * 0.5 - joy_knob.size * 0.5
	call_deferred("_focus_first", panel)


func _focus_first(panel: Variant) -> void:
	if not is_instance_valid(panel) or _touch_mode:
		return
	var btn := _find_button(panel)
	if btn:
		btn.grab_focus()


func _find_button(n: Node) -> Button:
	if n is Button and not (n as Button).disabled and (n as Button).focus_mode != Control.FOCUS_NONE:
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
	if modal.has_meta("self_layout"):
		modal.relayout(vp)
		_sync_hud()
		return
	var sz := modal.get_combined_minimum_size()
	modal.size = Vector2(minf(sz.x, vp.x - 24), minf(sz.y, vp.y - 24))
	modal.position = ((vp - modal.size) * 0.5).round()
	# tall cards step down to keep a band free for toasts at the top edge
	modal.position.y = maxf(modal.position.y, minf(TOAST_BAND, roundf(vp.y - modal.size.y - 12.0)))
	modal.pivot_offset = modal.size * 0.5
	# shopkeepers with anime art stand at the left edge of their menu
	var side: Texture2D = modal.get_meta("side_art") if modal.has_meta("side_art") else null
	var badge: Control = modal.get_meta("head_badge") if modal.has_meta("head_badge") else null
	var shown := false
	if side and vp.x >= vp.y:
		var ph := clampf(minf(vp.y * 0.66, modal.size.y + 140.0), 260.0, 500.0)
		var aspect := float(side.get_width()) / float(side.get_height())
		if aspect > 0.9:
			ph = ph * 0.9 / aspect
		var pw := ph * aspect
		var overlap := pw * 0.12
		var total := pw - overlap + modal.size.x
		if total <= vp.x - 24:
			var x0 := roundf((vp.x - total) * 0.5)
			modal.position.x = x0 + pw - overlap
			var bottom := modal.position.y + modal.size.y
			portrait_stage.present(str(modal.get_meta("portrait_key")), side, true, Rect2(x0, bottom - ph - 6.0, pw, ph), not modal.has_meta("presented"))
			modal.set_meta("presented", true)
			_stage_owner = modal
			shown = true
	elif side:
		# phone held upright: the shopkeeper leans in above the card's top edge
		var ph := clampf(vp.y * 0.22, 200.0, 380.0)
		var aspect := float(side.get_width()) / float(side.get_height())
		var pw := minf(ph * aspect, modal.size.x * 0.55)
		ph = pw / aspect
		var top := modal.position.y - ph + 24.0
		if top >= 150.0:
			portrait_stage.present(str(modal.get_meta("portrait_key")), side, true, Rect2(modal.position.x + 14.0, top, pw, ph), not modal.has_meta("presented"))
			modal.set_meta("presented", true)
			_stage_owner = modal
			shown = true
	if badge:
		badge.visible = not shown
	if not shown and _stage_owner == modal:
		portrait_stage.hide_portrait()
		_stage_owner = null
	_place_toasts()


func _close_modal() -> void:
	if modal:
		modal.queue_free()
		modal = null
		_closed_frame = Engine.get_process_frames()
		call_deferred("_after_close")
	overlay.visible = false
	_dialog_choices.clear()
	_typing = null
	portrait_stage.talking = false
	if world and world.player and world.state == "play":
		world.player.locked = false
	var cb := _on_modal_close
	_on_modal_close = Callable()
	if cb.is_valid():
		cb.call()


func _after_close() -> void:
	# runs after any dialog chained from a choice callback has opened
	if modal == null or not modal.has_meta("self_layout"):
		if modal == null or _stage_owner != modal:
			portrait_stage.hide_portrait()
			_stage_owner = null
	if modal == null:
		_dialog_key = ""
		_sync_hud()
		# drop the dialog's key hint; the world refreshes its prompt next frame
		_prompt_cache = ""
		set_prompt(_prompt_args[0], _prompt_args[1])


func close() -> void:
	_close_modal()


# ------------------------------------------------------------------ dialog
func dialog(portrait: String, speaker: String, text: String, choices: Array = [], on_close := Callable()) -> void:
	## choices: [{"text": String, "cb": Callable, "enabled": bool (optional), "hint": String (optional)}]
	## With no choices a single "Lanjut" button closes the dialog.
	if choices.is_empty():
		choices = [{"text": "Lanjut", "cb": Callable()}]
	var key := portrait_key(portrait, speaker)
	var chained := modal != null or _closed_frame == Engine.get_process_frames()
	var changed: bool = key != _dialog_key or not chained
	_dialog_key = key
	var art := portrait_art(key)
	var dv := DialogView.new()
	dv.name = "Dialog"
	dv.ui = self
	dv.setup(key, speaker, text, choices, art, null if art else portrait_fallback(portrait, key), chained, changed)
	_open_modal(dv, false, on_close)
	_dialog_choices = choices
	_typing = dv.body
	_typing_full = text
	_typing_t = 0.0
	portrait_stage.talking = true


func is_typing() -> bool:
	return _typing != null and is_instance_valid(_typing) and _typing.visible_characters >= 0 and _typing.visible_characters < _typing_full.length()


func finish_typing() -> void:
	if _typing and is_instance_valid(_typing):
		_typing.visible_characters = -1
	portrait_stage.talking = false


func _choose(c: Dictionary) -> void:
	if is_typing():
		finish_typing()
		return
	var cb: Callable = c.get("cb", Callable())
	_on_modal_close = Callable() if cb.is_valid() else _on_modal_close
	_close_modal()
	if cb.is_valid():
		cb.call()


func _process(delta: float) -> void:
	if _typing and is_instance_valid(_typing) and _typing.visible_characters >= 0:
		# typewriter with short pauses after punctuation
		_typing_t += delta * TYPE_CPS
		var n := _typing.visible_characters
		var total := _typing_full.length()
		while _typing_t >= 1.0 and n < total:
			_typing_t -= 1.0
			n += 1
			var ch := _typing_full[n - 1]
			if ch in ".!?" and n < total and _typing_full[n] == " ":
				_typing_t -= 0.22 * TYPE_CPS
			elif ch == ",":
				_typing_t -= 0.08 * TYPE_CPS
		_typing.visible_characters = n
		if n >= total:
			_typing.visible_characters = -1
			portrait_stage.talking = false
	if hud.visible and world and world.state == "play":
		clock_label.text = _clock_text()
		# the key badge breathes while an action is available
		var kb: Control = prompt_key.get_parent()
		kb.pivot_offset = kb.size * 0.5
		var k := 1.0 + (0.06 * sin(Time.get_ticks_msec() / 1000.0 * 5.0) if prompt_pill.visible and _prompt_ok else 0.0)
		kb.scale = Vector2(k, k)


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch or event is InputEventScreenDrag:
		if not _touch_mode:
			_touch_mode = true
			touch.visible = hud.visible
			_prompt_cache = ""
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
				return
	if modal and event is InputEventKey and event.is_action_pressed("action") and not event.is_action_pressed("ui_accept"):
		var f := get_viewport().gui_get_focus_owner()
		if f is Button and not (f as Button).disabled and modal.is_ancestor_of(f):
			get_viewport().set_input_as_handled()
			(f as Button).pressed.emit()
			return
		if is_typing():
			get_viewport().set_input_as_handled()
			finish_typing()
			return
	if modal and event.is_action_pressed("pause"):
		get_viewport().set_input_as_handled()
		if _dialog_choices.size() <= 1:
			_close_modal()
		elif modal.has_meta("closable"):
			_close_modal()


# ------------------------------------------------------------------ list menu (shops)
func _portrait_badge(tex: Texture2D, size := 76) -> Control:
	## Same round badge as the dialog's fallback portrait.
	var c := PortraitStage.build_badge(tex, size)
	c.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	return c


func _title_label(title: String, color := TITLE_BROWN, size := 30) -> Label:
	var l := _label(title, size, color, true)
	return l


func menu(title: String, subtitle: String, items: Array, on_close := Callable(), portrait := "") -> void:
	## items: [{"icon": String, "text": String, "desc": String, "price": String,
	##          "button": String, "cb": Callable, "enabled": bool}]
	var panel := PanelContainer.new()
	panel.name = "Menu"
	panel.set_meta("closable", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 12)
	panel.add_child(col)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 14)
	if portrait != "":
		var key := portrait_key(portrait, title)
		var art := portrait_art(key)
		if art:
			panel.set_meta("side_art", art)
			panel.set_meta("portrait_key", key)
		var badge := _portrait_badge(portrait_fallback(portrait, key), 76)
		head.add_child(badge)
		panel.set_meta("head_badge", badge)
	var tcol := VBoxContainer.new()
	tcol.add_theme_constant_override("separation", 2)
	tcol.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tcol.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var vp := root.get_viewport_rect().size
	var list_w := minf(680.0, vp.x - 90.0)
	# the HUD (money pill included) steps aside for menus, so every shop shows
	# the wallet as a coin chip; a "Uang: ..." part of the subtitle would repeat it
	var chip := _chip("ui_coins", GS.fmt_rp(GS.money))
	chip.name = "Wallet"
	chip.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	panel.set_meta("money_label", chip.find_child("Text", true, false))
	var parts := PackedStringArray()
	for part in subtitle.split(" • "):
		if not part.strip_edges().begins_with("Uang:"):
			parts.append(part)
	subtitle = " • ".join(parts)
	var title_row := _hrow([_title_label(title)], 12)
	title_row.get_child(0).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tcol.add_child(title_row)
	var wide := vp.x >= vp.y
	if wide:
		title_row.add_child(chip)
	if subtitle != "":
		var sl := _label(subtitle, 18, BROWN_SOFT)
		sl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		sl.custom_minimum_size = Vector2(list_w - 100.0, 0)
		tcol.add_child(sl)
	if not wide:
		# phones held upright: no room beside the title, the chip goes below
		chip.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		tcol.add_child(chip)
	head.add_child(tcol)
	col.add_child(head)
	col.add_child(_divider())
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.custom_minimum_size = Vector2(list_w, minf(items.size() * 78, vp.y - 270))
	col.add_child(scroll)
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 8)
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(list)
	_fit_scroll_later(scroll, list, vp.y - 270)
	for it in items:
		var row := PanelContainer.new()
		var rs := _box(CREAM_LIGHT, 18, LINE, 2)
		_margins(rs, 10, 8, 12, 8)
		row.add_theme_stylebox_override("panel", rs)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 12)
		row.add_child(h)
		var ib := PanelContainer.new()
		var ibs := _box(Color("f3e4c4"), 28)
		_margins(ibs, 4, 4, 4, 4)
		ib.add_theme_stylebox_override("panel", ibs)
		ib.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		ib.add_child(_icon_rect(it.get("icon", ""), 48))
		h.add_child(ib)
		var tc := VBoxContainer.new()
		tc.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		tc.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		tc.add_theme_constant_override("separation", 0)
		tc.add_child(_label(it.get("text", ""), 21, BROWN, true))
		if it.get("desc", "") != "":
			var dl := _label(it["desc"], 16, BROWN_SOFT)
			dl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			tc.add_child(dl)
		h.add_child(tc)
		if it.get("price", "") != "":
			var pl := _label(it["price"], 18, Color("7a4a12"), true)
			var pp := PanelContainer.new()
			var pps := _box(Color("f7e2a6"), 16, Color("e6c677"), 1)
			_margins(pps, 12, 3, 12, 4)
			pp.add_theme_stylebox_override("panel", pps)
			pp.add_child(pl)
			pp.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			h.add_child(pp)
		if it.has("cb"):
			var b := button(it.get("button", "Beli"), it["cb"], it.get("enabled", true), 110, true)
			b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			h.add_child(b)
		list.add_child(row)
	var close_b := button("Tutup" + ("" if _touch_mode else "  (Esc)"), _close_modal, true, 180)
	close_b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(close_b)
	_open_modal(panel, true, on_close)


func refresh_menu(rebuild: Callable) -> void:
	## Re-opens the current menu after a purchase without firing on_close.
	_on_modal_close = Callable()
	rebuild.call()


func _divider() -> Control:
	var d := ColorRect.new()
	d.color = Color(LINE, 0.8)
	d.custom_minimum_size = Vector2(0, 2)
	d.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return d


# ------------------------------------------------------------------ panels
func info_panel(title: String, lines: Array, button_text := "Oke", on_close := Callable(), title_color := TITLE_BROWN, icon_name := "", footer: Control = null) -> void:
	var panel := PanelContainer.new()
	panel.name = "Info"
	panel.set_meta("closable", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	panel.add_child(col)
	var head := HBoxContainer.new()
	head.alignment = BoxContainer.ALIGNMENT_CENTER
	head.add_theme_constant_override("separation", 12)
	if icon_name != "":
		head.add_child(_icon_rect(icon_name, 46))
	var tl := _title_label(title, title_color, 32)
	head.add_child(tl)
	col.add_child(head)
	col.add_child(_divider())
	var vp := root.get_viewport_rect().size
	var w := minf(640.0, vp.x - 70.0)
	var inner := VBoxContainer.new()
	inner.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inner.add_theme_constant_override("separation", 7)
	# measured like the Labels will lay out (the old per-character guess left
	# a tall empty gap above the button); corrected after the first layout
	var est := 0.0
	var sep := 7.0
	for line in lines:
		var s := str(line)
		if inner.get_child_count() > 0:
			est += sep
		if s.begins_with("—") or s.begins_with("- "):
			var st := s.trim_prefix("—").trim_suffix("—").strip_edges()
			var sec := _label(st, 18, BROWN_SOFT, true)
			sec.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			inner.add_child(sec)
			est += _text_h(st, _font_bold, 18, w)
			continue
		var raid := s.begins_with("[SIDAK]")
		var l := _label(s, 20, RED if raid else BROWN)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.custom_minimum_size = Vector2(w - 44.0, 0)
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var bullet: Control
		if raid:
			bullet = _icon_rect("ui_bad", 22)
		else:
			var dot := Panel.new()
			dot.add_theme_stylebox_override("panel", _box(INK, 6))
			dot.custom_minimum_size = Vector2(11, 11)
			dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
			var holder := CenterContainer.new()
			holder.custom_minimum_size = Vector2(22, 26)
			holder.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
			holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
			holder.add_child(dot)
			bullet = holder
		bullet.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		inner.add_child(_hrow([bullet, l], 10))
		est += maxf(26.0, _text_h(s, _font_semi, 20, w - 32.0))
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var max_h := vp.y - (230.0 if footer == null else 290.0)
	scroll.custom_minimum_size = Vector2(w, minf(ceilf(est), max_h))
	scroll.add_child(inner)
	_fit_scroll_later(scroll, inner, max_h)
	col.add_child(scroll)
	if footer:
		col.add_child(footer)
	var b := button(button_text, _close_modal, true, 200, true)
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(b)
	_open_modal(panel, true, on_close)


func _text_h(text: String, font: Font, fsize: int, width: float) -> float:
	## Height of an autowrapped (AUTOWRAP_WORD_SMART) Label `width` px wide.
	var para := TextParagraph.new()
	para.add_string(text, font, fsize)
	para.width = width
	para.break_flags = TextServer.BREAK_MANDATORY | TextServer.BREAK_WORD_BOUND | TextServer.BREAK_ADAPTIVE
	return para.get_size().y + maxf(0.0, para.get_line_count() - 1) * 3.0


func _fit_scroll_later(scroll: ScrollContainer, inner: Control, max_h: float) -> void:
	## Once the panel has been laid out, size the scroll box to its content
	## exactly (no gap above the buttons), up to max_h.
	# weak refs: a menu rebuilt after a purchase frees the old scroll first
	var sref: WeakRef = weakref(scroll)
	var iref: WeakRef = weakref(inner)
	get_tree().process_frame.connect(func():
		var sc: ScrollContainer = sref.get_ref()
		var box: Control = iref.get_ref()
		if sc == null or box == null or not sc.is_inside_tree():
			return
		var h := minf(ceilf(box.get_combined_minimum_size().y), max_h)
		if absf(h - sc.custom_minimum_size.y) > 0.5:
			sc.custom_minimum_size.y = h
			if modal and modal.is_ancestor_of(sc):
				_center_modal(), CONNECT_ONE_SHOT)


func _chip(icon_name: String, text: String, color := BROWN) -> Control:
	var l := _label(text, 18, color, true)
	l.name = "Text"
	l.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var p := _pill(_hrow([_icon_rect(icon_name, 30), l], 8), CREAM_LIGHT, 4, 14)
	return p


func show_morning(report: Array) -> void:
	Sfx.play("whoosh")
	var lines: Array = report.duplicate()
	var chips := HBoxContainer.new()
	chips.alignment = BoxContainer.ALIGNMENT_CENTER
	chips.add_theme_constant_override("separation", 10)
	chips.add_child(_chip("ui_coins", GS.fmt_rp(GS.money)))
	chips.add_child(_chip("ui_leaf", "Reputasi %d" % int(GS.rep), Color("3f7f2a") if GS.rep >= 0 else RED))
	chips.add_child(_chip("ui_eye", "Kecurigaan %d/100" % int(GS.heat), RED if GS.heat >= 60 else BROWN))
	info_panel("Pagi, Hari ke-%d" % GS.day, lines, "Mulai hari", func(): world.deals.run_morning_events(), TITLE_BROWN, "ui_sun", chips)


func show_status() -> void:
	if modal:
		return
	var lines: Array = []
	lines.append("Uang: %s   •   Harga TBS: %s/tandan" % [GS.fmt_rp(GS.money), GS.fmt_rp(GS.tbs_price)])
	lines.append("Lahan dikuasai: %d/%d (milikmu %d)   •   Pohon sawit: %d" % [GS.controlled_parcels(), GS.LICENSE_NEED, GS.owned_parcels(), GS.palm_count()])
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
	info_panel("Status Juragan", lines, "Tutup", Callable(), TITLE_BROWN, "ui_status")


func toggle_pause() -> void:
	if modal:
		if modal.has_meta("pause"):
			_paused = false
			_close_modal()
		return
	var panel := PanelContainer.new()
	panel.name = "Pause"
	panel.set_meta("pause", true)
	panel.set_meta("closable", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	panel.add_child(col)
	var head := _hrow([_icon_rect("ui_menu", 42), _title_label("Jeda", TITLE_BROWN, 34)], 12)
	head.alignment = BoxContainer.ALIGNMENT_CENTER
	col.add_child(head)
	col.add_child(_divider())
	col.add_child(button("Lanjut main", func(): _paused = false; _close_modal(), true, 320, true))
	col.add_child(button("Simpan permainan", func():
		GS.save_game()
		toast("Permainan tersimpan.", "good"), true, 320))
	col.add_child(button("Grafik: " + ("Tinggi" if world.quality_high else "Hemat baterai"), func():
		world.set_quality(not world.quality_high)
		_paused = false
		_close_modal()
		toggle_pause(), true, 320))
	col.add_child(button("Musik: " + ("Nyala" if Sfx.music_on else "Mati"), func():
		Sfx.set_music(not Sfx.music_on)
		_paused = false
		_close_modal()
		toggle_pause(), true, 320))
	col.add_child(button("Layar penuh", func():
		var fs := DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED if fs else DisplayServer.WINDOW_MODE_FULLSCREEN)
		_paused = false
		_close_modal(), true, 320))
	col.add_child(button("Cara main", func(): _paused = false; _close_modal(); show_help(), true, 320))
	col.add_child(button("Dibuat oleh", func(): _paused = false; _close_modal(); show_credits(), true, 320))
	col.add_child(button("Keluar ke judul", func():
		GS.save_game()
		_paused = false
		_close_modal()
		world.enter_title(), true, 320))
	_paused = true
	_open_modal(panel, true, func(): _paused = false)


const CREATOR_IG := "leonrdewa"


func show_credits(on_close := Callable()) -> void:
	var lines := [
		"Sawit The Franchise dibuat oleh @%s." % CREATOR_IG,
		"Instagram: instagram.com/%s — follow untuk update game ini!" % CREATOR_IG,
		"Dibuat dengan Blender + Godot Engine. Konsep art: Higgsfield GPT Image 2.5.",
	]
	info_panel("Dibuat oleh", lines, "Buka Instagram @" + CREATOR_IG, func():
		OS.shell_open("https://instagram.com/" + CREATOR_IG)
		if on_close.is_valid():
			on_close.call(), TITLE_BROWN, "ui_info")


func show_help(on_close := Callable()) -> void:
	var lines := [
		"Tujuan: jadi Raja Sawit! Kuasai ke-7 lahan desa lalu beli Lisensi Sawit The Franchise (Rp 20 juta) di Kantor.",
		"Gerak: WASD / panah (Shift untuk lari). Di HP: geser jempol kiri di layar.",
		"Aksi: E / Spasi (atau tombol bulat kanan bawah di HP) — tebas semak, tanam, pupuk, panen, ngobrol, masuk rumah, mancing. Alat di hotbar kanan bawah dipilih otomatis sesuai aksi.",
		"Menu: Esc / P.  Status: Tab / I.  Tas: B.  Pilihan dialog: tombol angka 1–6.",
		"Sawit butuh ±6 hari untuk berbuah; pupuk mempercepat. Panen TBS lalu jual ke Pabrik di timur.",
		"Lahan warga bisa dibeli wajar, ditawar murah, ditipu pakai surat palsu, atau dirampas pakai preman (sewa dari Bang Jeki dekat dermaga). Preman juga bisa memalak tabungan warga.",
		"Makin culas, makin tinggi Kecurigaan. Kalau penuh (100), Satgas datang menyidak: denda besar. Sidak ke-3 = tamat.",
		"Punya Mesin Olah Minyak? Olah TBS jadi minyak goreng lalu jual ke warga... harganya kamu yang atur.",
		"Warga tanpa lahan bisa kamu jadikan buruh murah. Warga yang masih punya lahan bisa diajak 'kemitraan franchise'.",
		"Mancing: hadap ke air (pantai, sungai, dermaga, jembatan) lalu tekan aksi. Tunggu tanda \"!\", tekan, lalu tekan lagi saat penanda di zona hijau. Jual ikan di Warung atau Koperasi. Ikan langka: Arwana Emas!",
		"Tas: tombol tas di kanan atas (atau B) untuk melihat semua barang bawaanmu.",
		"Rumah bisa dimasuki lewat pintunya. Tidur di kasur rumahmu (timur Kantor) untuk lanjut hari & menyimpan otomatis. Lewat jam 24:00 kamu pingsan.",
	]
	info_panel("Cara Main", lines, "Siap, Juragan!", on_close, TITLE_BROWN, "ui_info")


# ------------------------------------------------------------------ bag (tas)
const BAG_ORDER := ["tbs", "bibit", "pupuk", "minyak", "surat", "pancing"]


func bag_entries() -> Array:
	## [{"key", "name", "icon", "desc", "count" (-1 = tool), "price"}] in display order
	var out: Array = []
	var keys: Array = BAG_ORDER.duplicate()
	for id in GS.FISH:
		keys.append(id)
	for k in keys:
		var n := int(GS.inv.get(k, 0))
		if n <= 0 and not (k in ["tbs", "bibit", "pupuk"]):
			continue
		var info: Dictionary = GS.item_info(k)
		if info.is_empty():
			continue
		out.append({"key": k, "name": info["name"], "icon": info["icon"], "desc": info["desc"], "count": n,
			"price": int(info.get("price", 0))})
	for t in GS.TOOLS:
		out.append({"key": t["icon"], "name": t["name"], "icon": t["icon"], "desc": t["desc"], "count": -1, "price": 0})
	for u in [["gerobak", "Gerobak dorong", "icon_gerobak", "Kapasitas angkut TBS 25."], ["truk", "Truk pickup", "icon_truk", "Kapasitas angkut TBS 80."],
			["mesin", "Mesin Olah Minyak", "icon_minyak", "Olah TBS jadi minyak goreng di Pabrik."]]:
		if GS.upgrades.get(u[0], false):
			out.append({"key": u[0], "name": u[1], "icon": u[2], "desc": u[3], "count": -1, "price": 0})
	return out


func is_bag_open() -> bool:
	return modal != null and modal.has_meta("bag")


func show_bag(select := "") -> void:
	if modal and not is_bag_open():
		return
	if is_bag_open() and select == "":
		_close_modal()
		return
	var entries := bag_entries()
	if select == "" and not entries.is_empty():
		select = entries[0]["key"]
	var panel := PanelContainer.new()
	panel.name = "Bag"
	panel.set_meta("bag", true)
	panel.set_meta("closable", true)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	panel.add_child(col)
	var vp := root.get_viewport_rect().size
	var wide := vp.x >= vp.y
	var chip := _chip("ui_coins", GS.fmt_rp(GS.money))
	chip.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	panel.set_meta("money_label", chip.find_child("Text", true, false))
	var title := _title_label("Tas", TITLE_BROWN, 30)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var head := _hrow([_icon_rect("ui_bag", 44), title, chip], 12)
	col.add_child(head)
	col.add_child(_divider())
	var cell := 86.0 if _touch_mode else 80.0
	var cols := 6 if wide else 4
	cols = mini(cols, maxi(3, int((vp.x - 90.0) / (cell + 8.0))))
	var grid := GridContainer.new()
	grid.columns = cols
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 8)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var rows := int(ceil(entries.size() / float(cols)))
	var max_h := maxf(cell + 8.0, vp.y - 330.0)
	scroll.custom_minimum_size = Vector2(cols * (cell + 8.0), minf(rows * (cell + 8.0), max_h))
	scroll.add_child(grid)
	col.add_child(scroll)
	var sel: Dictionary = {}
	for e in entries:
		var b := Button.new()
		b.name = "slot_" + str(e["key"])
		b.custom_minimum_size = Vector2(cell, cell)
		b.focus_mode = Control.FOCUS_ALL
		var on: bool = e["key"] == select
		if on:
			sel = e
		var st := _box(CREAM_LIGHT if on else CREAM, 16, ACCENT if on else LINE, 3 if on else 2)
		b.add_theme_stylebox_override("normal", st)
		b.add_theme_stylebox_override("hover", _box(CREAM_LIGHT, 16, ACCENT, 2))
		b.add_theme_stylebox_override("pressed", _box(CREAM_DARK, 16, ACCENT, 3))
		b.add_theme_stylebox_override("focus", _box(Color(0, 0, 0, 0), 16, ACCENT, 3))
		var ic := TextureRect.new()
		ic.texture = icon(str(e["icon"]))
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ic.position = Vector2(cell * 0.13, cell * 0.1)
		ic.size = Vector2(cell * 0.74, cell * 0.74)
		if int(e["count"]) == 0:
			ic.modulate.a = 0.4
		b.add_child(ic)
		if int(e["count"]) >= 0:
			var cl := _label(str(e["count"]), 17, BROWN, true)
			cl.add_theme_color_override("font_outline_color", CREAM_LIGHT)
			cl.add_theme_constant_override("outline_size", 6)
			cl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			cl.position = Vector2(4, cell - 28)
			cl.size = Vector2(cell - 12, 24)
			b.add_child(cl)
		var key: String = e["key"]
		b.pressed.connect(func():
			Sfx.play("click", 1.1, -8.0)
			_on_modal_close = Callable()
			show_bag_select(key))
		grid.add_child(b)
	# the selected item's info
	var info := PanelContainer.new()
	var ist := _box(CREAM_LIGHT, 18, LINE, 2)
	_margins(ist, 12, 8, 14, 10)
	info.add_theme_stylebox_override("panel", ist)
	var ih := HBoxContainer.new()
	ih.add_theme_constant_override("separation", 12)
	info.add_child(ih)
	var tcol := VBoxContainer.new()
	tcol.add_theme_constant_override("separation", 0)
	tcol.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var dw := maxf(200.0, cols * (cell + 8.0) - 110.0)
	if not sel.is_empty():
		ih.add_child(_icon_rect(str(sel["icon"]), 56))
		var nm := str(sel["name"])
		if int(sel["count"]) > 0:
			nm += "  x%d" % int(sel["count"])
		tcol.add_child(_label(nm, 21, BROWN, true))
		var dl := _label(str(sel["desc"]), 17, BROWN_SOFT)
		dl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		dl.custom_minimum_size = Vector2(dw, 0)
		tcol.add_child(dl)
		if int(sel["price"]) > 0:
			tcol.add_child(_label("Harga jual: %s / ekor" % GS.fmt_short(int(sel["price"])), 17, Color("7a4a12"), true))
	else:
		tcol.add_child(_label("Tasmu kosong.", 20, BROWN_SOFT))
	ih.add_child(tcol)
	col.add_child(info)
	var nf := GS.fish_count()
	var foot := _label(("Ikan: %d ekor • nilai %s (jual di Warung / Koperasi)" % [nf, GS.fmt_short(GS.fish_value())]) if nf > 0 else "Bawaan TBS: %d/%d" % [int(GS.inv.get("tbs", 0)), GS.capacity()], 16, BROWN_SOFT)
	foot.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(foot)
	var close_b := button("Tutup" + ("" if _touch_mode else "  (B / Esc)"), _close_modal, true, 180)
	close_b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(close_b)
	_open_modal(panel, true)
	panel.set_meta("bag_select", select)


func show_bag_select(key: String) -> void:
	## re-open the bag with another item selected (keeps the panel in place)
	show_bag(key)


func on_inside_changed() -> void:
	_sync_hud()
	_prompt_cache = ""


var _fade_rect: ColorRect


func fade_screen(mid: Callable, done := Callable()) -> void:
	## dark fade (0.25 s), `mid` at full dark, fade back in (0.3 s)
	if _fade_rect == null:
		_fade_rect = ColorRect.new()
		_fade_rect.color = Color("1e140c")
		_fade_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
		_fade_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(_fade_rect)
	root.move_child(_fade_rect, -1)
	_fade_rect.visible = true
	_fade_rect.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(_fade_rect, "modulate:a", 1.0, 0.25)
	tw.tween_callback(mid)
	tw.tween_interval(0.12)
	tw.tween_property(_fade_rect, "modulate:a", 0.0, 0.3)
	tw.tween_callback(func():
		_fade_rect.visible = false
		if done.is_valid():
			done.call())


func show_game_over(reason: String) -> void:
	Sfx.play("bad")
	var lines := [reason, "Hari bertahan: %d • Total pendapatan: %s" % [GS.day, GS.fmt_rp(GS.stats["earned"])],
		"Lahan yang kamu ambil paksa: %d • yang kamu tipu: %d" % [GS.stats["land_seized"], GS.stats["land_fraud"]],
		"Kamu dijebloskan ke penjara... setidaknya sampai ada remisi."]
	GS.delete_save()
	info_panel("TAMAT: Tertangkap!", lines, "Kembali ke judul", func(): world.enter_title(), RED, "ui_bad")


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
	info_panel("RAJA SAWIT!", lines, "Kembali ke judul", func(): world.enter_title(), GREEN, "ui_star")


# ------------------------------------------------------------------ title
func show_title() -> void:
	_close_modal()
	portrait_stage.hide_portrait()
	hud.visible = false
	if touch:
		touch.visible = false
	if title_screen:
		title_screen.queue_free()
	title_screen = Control.new()
	title_screen.set_anchors_preset(Control.PRESET_FULL_RECT)
	title_screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(title_screen)
	var shade := TextureRect.new()
	var g := Gradient.new()
	g.set_color(0, Color(0.99, 0.95, 0.86, 0.0))
	g.set_color(1, Color(0.12, 0.08, 0.03, 0.35))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.45)
	gt.fill_to = Vector2(1.1, 1.1)
	shade.texture = gt
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shade.stretch_mode = TextureRect.STRETCH_SCALE
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
	logo.add_theme_color_override("font_outline_color", CREAM_LIGHT)
	logo.add_theme_constant_override("outline_size", 26)
	logo.add_theme_color_override("font_shadow_color", Color(0.25, 0.15, 0.05, 0.45))
	logo.add_theme_constant_override("shadow_offset_y", 6)
	col.add_child(logo)
	var ribbon := PanelContainer.new()
	var rs := _box(Color("d9572c"), 16, CREAM_LIGHT, 3, true)
	_margins(rs, 28, 2, 28, 4)
	ribbon.add_theme_stylebox_override("panel", rs)
	var rl := _label("THE FRANCHISE", 38, CREAM_LIGHT, true)
	ribbon.add_child(rl)
	ribbon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(ribbon)
	var tag := _label("Kebun sawit impian... untukmu, bukan untuk mereka.", 21, BROWN)
	tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var tagp := _pill(tag, CREAM, 18, 18)
	tagp.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(Control.new())
	col.add_child(tagp)
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(0, 16)
	col.add_child(spacer)
	var card := PanelContainer.new()
	card.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(card)
	var bcol := VBoxContainer.new()
	bcol.add_theme_constant_override("separation", 10)
	card.add_child(bcol)
	if GS.has_save():
		bcol.add_child(button("Lanjutkan", func(): world.start_game(true), true, 300, true))
	bcol.add_child(button("Main Baru", func(): world.start_game(false), true, 300, not GS.has_save()))
	if _touch_mode or OS.has_feature("web"):
		bcol.add_child(button("Layar penuh", func():
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN), true, 300))
	bcol.add_child(button("Cara Main", func():
		title_screen.visible = false
		show_help(func(): if title_screen: title_screen.visible = true), true, 300))
	bcol.add_child(button("Dibuat oleh", func():
		title_screen.visible = false
		show_credits(func(): if title_screen: title_screen.visible = true), true, 300))
	var credit := _label("Dibuat oleh @leonrdewa (Instagram) • Blender + Godot", 15, CREAM_LIGHT)
	credit.add_theme_color_override("font_outline_color", Color(0.3, 0.2, 0.1, 0.6))
	credit.add_theme_constant_override("outline_size", 5)
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
	joy_base.size = Vector2(170, 170)
	joy_base.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# a fixed joystick bottom-left, always on screen while playing (phones)
	touch.add_child(joy_base)
	joy_knob = Panel.new()
	joy_knob.add_theme_stylebox_override("panel", _circle(Color(1, 0.97, 0.88, 0.9), 34, Color(0.55, 0.4, 0.25, 0.5)))
	joy_knob.size = Vector2(72, 72)
	joy_knob.position = Vector2(49, 49)
	joy_knob.mouse_filter = Control.MOUSE_FILTER_IGNORE
	joy_base.add_child(joy_knob)
	# joystick hint: cream text in a translucent dark pill (readable on grass)
	var hl := _label("geser untuk jalan", 18, CREAM_LIGHT, true)
	var hint := PanelContainer.new()
	var hs := _box(Color(0.16, 0.1, 0.05, 0.55), 18)
	_margins(hs, 16, 6, 16, 7)
	hint.add_theme_stylebox_override("panel", hs)
	hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hint.add_child(hl)
	hint.name = "JoyHint"
	touch.add_child(hint)
	action_btn = Panel.new()
	var ast := _circle(CREAM, 62, LINE)
	ast.shadow_color = Color(0.25, 0.14, 0.05, 0.3)
	ast.shadow_size = 8
	ast.shadow_offset = Vector2(0, 3)
	action_btn.add_theme_stylebox_override("panel", ast)
	action_btn.size = Vector2(124, 124)
	action_btn.mouse_filter = Control.MOUSE_FILTER_IGNORE
	touch.add_child(action_btn)
	action_icon = TextureRect.new()
	action_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	action_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	action_icon.position = Vector2(34, 12)
	action_icon.size = Vector2(56, 56)
	action_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	action_btn.add_child(action_icon)
	action_label = _label("", 21, BROWN, true)
	action_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	action_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	action_label.size = Vector2(124, 124)
	action_label.clip_text = true
	action_btn.add_child(action_label)
	action_btn.modulate.a = 0.45


func _circle(color: Color, radius: int, border := Color(0, 0, 0, 0)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = color
	s.set_corner_radius_all(radius)
	s.anti_aliasing = true
	s.corner_detail = 16
	if border.a > 0:
		s.border_color = border
		s.set_border_width_all(4)
	return s


func _layout_touch(vp: Vector2) -> void:
	# above the hotbar's row when that reaches the right edge, else lower down
	# (landscape phones: the centred hotbar leaves the corner free, and the
	# button must stay clear of the minimap above it)
	var ax := vp.x - 124 - 28
	var lift := 96.0
	if vp.x > vp.y and _home(hotbar).x + hotbar.size.x < ax - 24.0:
		lift = 28.0
	action_btn.position = Vector2(ax, vp.y - 124 - lift)
	# the fixed joystick: bottom-left corner, above the hotbar on portrait phones
	_joy_home = Vector2(40.0 + joy_base.size.x * 0.5, vp.y - 40.0 - joy_base.size.y * 0.5)
	var hb := Rect2(_home(hotbar), hotbar.size).grow(6.0)
	if hb.intersects(Rect2(_joy_home - joy_base.size * 0.5, joy_base.size)):
		_joy_home.y = hb.position.y - 20.0 - joy_base.size.y * 0.5
	if _joy_index < 0:
		joy_base.position = _joy_home - joy_base.size * 0.5
	var hint: Control = touch.get_node("JoyHint")
	hint.size = hint.get_combined_minimum_size()
	hint.position = Vector2(_joy_home.x - hint.size.x * 0.5, joy_base.position.y - hint.size.y - 8.0)


func _handle_touch(event: InputEvent) -> void:
	if not hud.visible or world == null or world.state != "play":
		return
	var vp := root.get_viewport_rect().size
	# _input already receives the events in canvas coordinates (the root window
	# applies its stretch / content-scale transform before dispatch). Transforming
	# them again put every touch at the wrong place on scaled phone screens: the
	# joystick jumped and the action button never registered its taps.
	var pos: Vector2 = root.get_global_transform_with_canvas().affine_inverse() * event.position
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
			if Rect2(hotbar.position - Vector2(6, 14), hotbar.size + Vector2(12, 20)).has_point(pos):
				return  # hotbar slots handle their own taps
			if minimap and Rect2(minimap.position, minimap.size).has_point(pos):
				return
			# the joystick: grabbed on (or near) its fixed base; a touch elsewhere in
			# the lower left of the screen moves the base under the thumb
			if _joy_index < 0 and (pos.distance_to(_joy_home) < joy_base.size.x * 0.9
					or (pos.x < vp.x * 0.45 and pos.y > vp.y * 0.35)):
				_joy_index = event.index
				_joy_center = _joy_home if pos.distance_to(_joy_home) < joy_base.size.x * 0.9 else pos
				joy_base.position = _joy_center - joy_base.size * 0.5
				_joy_drag(pos)
				touch.get_node("JoyHint").visible = false
		else:
			if event.index == _joy_index:
				_joy_index = -1
				joy_base.position = _joy_home - joy_base.size * 0.5
				joy_knob.position = joy_base.size * 0.5 - joy_knob.size * 0.5
				world.player.touch_vec = Vector2.ZERO
			if event.index == _action_index:
				_action_index = -1
				action_btn.scale = Vector2.ONE
	elif event is InputEventScreenDrag and event.index == _joy_index:
		_joy_drag(pos)


func _joy_drag(pos: Vector2) -> void:
	var d: Vector2 = pos - _joy_center
	var r := 70.0
	if d.length() > r:
		d = d.normalized() * r
	joy_knob.position = joy_base.size * 0.5 - joy_knob.size * 0.5 + d
	var v := d / r
	world.player.touch_vec = v if v.length() > 0.12 else Vector2.ZERO
