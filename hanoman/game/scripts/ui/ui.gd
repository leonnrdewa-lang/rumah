class_name UI
extends CanvasLayer
## All 2D interface: HUD, prompts, toasts, area titles, Hades-style dialogue with
## big painted portraits, the boon picker, choice menus (Jembawan, Palu), title,
## pause, death and victory screens, fades and touch controls.

const F_BODY := preload("res://assets/fonts/Alegreya.ttf")
const F_HEAD := preload("res://assets/fonts/Cinzel.ttf")
const F_TITLE := preload("res://assets/fonts/CinzelDecorative-Bold.ttf")
const PANEL := preload("res://assets/textures/panel.png")
const PORTRAIT_SHADER := preload("res://shaders/portrait.gdshader")
const GOLD := Color("d9a93a")
const CREAM := Color("f3e9d2")
const INK := Color(0.05, 0.04, 0.06)

const WHO := {
	"hanoman": ["Hanoman", "Duta Prabu Rama"],
	"rama": ["Prabu Rama", "Titisan Batara Wisnu"],
	"jembawan": ["Resi Jembawan", "Penasihat Wanara"],
	"sugriwa": ["Prabu Sugriwa", "Raja Kera Kiskenda"],
	"kijang": ["Kijang Kencana", "Kala Marica"],
	"sura": ["Sura", "Raja Hiu Samudra"],
	"baya": ["Baya", "Raja Buaya Kali Mas"],
	"dewa_bayu": ["Batara Bayu", "Dewa Angin"],
	"dewa_surya": ["Batara Surya", "Dewa Matahari"],
	"dewa_baruna": ["Batara Baruna", "Dewa Samudra"],
	"dewa_indra": ["Batara Indra", "Raja Kahyangan"],
}

var hud: Control
var hp_bar: Control
var hp_label: Label
var pips: Control
var boon_box: HBoxContainer
var money: Label
var bunga_label: Label
var prompt: PanelContainer
var prompt_label: Label
var toast_box: VBoxContainer
var boss_box: VBoxContainer
var bosses: Array = []
var boss_bars: Array = []
var fader: ColorRect
var overlay: Control
var touch: Control
var _hp_lag := 1.0
var _joy_id := -1
var _joy_origin := Vector2.ZERO
var _joy_knob: Control
var _joy_base: Control
var _advance: Callable
var _typing := false
var _type_label: RichTextLabel
var _menu_buttons: Array = []


func _ready() -> void:
	layer = 10
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build_hud()
	overlay = Control.new()
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(overlay)
	_build_touch()
	fader = ColorRect.new()
	fader.color = Color(0, 0, 0, 0)
	fader.set_anchors_preset(Control.PRESET_FULL_RECT)
	fader.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(fader)
	G.run_changed.connect(_refresh)
	G.meta_changed.connect(_refresh)
	G.toast.connect(toast)


# --- helpers -----------------------------------------------------------------------

func _label(text: String, size: int, font: Font = F_BODY, color := CREAM, outline := 8) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_outline_color", INK)
	l.add_theme_constant_override("outline_size", outline)
	return l


func _panel_style(alpha := 0.92) -> StyleBoxTexture:
	var s := StyleBoxTexture.new()
	s.texture = PANEL
	s.texture_margin_left = 28
	s.texture_margin_right = 28
	s.texture_margin_top = 28
	s.texture_margin_bottom = 28
	s.content_margin_left = 26
	s.content_margin_right = 26
	s.content_margin_top = 18
	s.content_margin_bottom = 18
	s.modulate_color = Color(1, 1, 1, alpha)
	return s


func _flat(col: Color, border := Color(0, 0, 0, 0), bw := 0, radius := 6) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = col
	s.border_color = border
	s.set_border_width_all(bw)
	s.set_corner_radius_all(radius)
	s.content_margin_left = 14
	s.content_margin_right = 14
	s.content_margin_top = 8
	s.content_margin_bottom = 8
	return s


static func portrait_tex(id: String) -> Texture2D:
	var hf: Texture2D = Hf.portrait(id)
	if hf:
		return hf
	for p in ["res://assets/portraits/hf_%s.png" % id, "res://assets/portraits/%s.png" % id]:
		if ResourceLoader.exists(p):
			return load(p)
	return null


# --- HUD ------------------------------------------------------------------------------

func _build_hud() -> void:
	hud = Control.new()
	hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(hud)
	# health (bottom-left)
	hp_bar = Control.new()
	hp_bar.custom_minimum_size = Vector2(300, 26)
	hp_bar.anchor_top = 1.0
	hp_bar.anchor_bottom = 1.0
	hp_bar.position = Vector2(28, -70)
	hp_bar.size = Vector2(300, 26)
	hp_bar.draw.connect(_draw_hp)
	hud.add_child(hp_bar)
	hp_label = _label("50/50", 20, F_HEAD)
	hp_label.position = Vector2(8, -4)
	hp_bar.add_child(hp_label)
	pips = Control.new()
	pips.anchor_top = 1.0
	pips.anchor_bottom = 1.0
	pips.position = Vector2(28, -40)
	pips.size = Vector2(320, 24)
	pips.draw.connect(_draw_pips)
	hud.add_child(pips)
	# boons (left, above health)
	boon_box = HBoxContainer.new()
	boon_box.anchor_top = 1.0
	boon_box.anchor_bottom = 1.0
	boon_box.position = Vector2(24, -128)
	boon_box.add_theme_constant_override("separation", 6)
	hud.add_child(boon_box)
	# money (top-right)
	var mb := HBoxContainer.new()
	mb.anchor_left = 1.0
	mb.anchor_right = 1.0
	mb.position = Vector2(-250, 18)
	mb.size = Vector2(230, 40)
	mb.alignment = BoxContainer.ALIGNMENT_END
	mb.add_theme_constant_override("separation", 8)
	hud.add_child(mb)
	var ci := TextureRect.new()
	ci.texture = load("res://assets/icons/rw_kepeng.png")
	ci.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ci.custom_minimum_size = Vector2(34, 34)
	mb.add_child(ci)
	money = _label("0", 26, F_HEAD, Color(1, 0.86, 0.45))
	mb.add_child(money)
	var bi := TextureRect.new()
	bi.texture = load("res://assets/icons/rw_bunga.png")
	bi.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bi.custom_minimum_size = Vector2(34, 34)
	mb.add_child(bi)
	bunga_label = _label("0", 26, F_HEAD, CREAM)
	mb.add_child(bunga_label)
	# boss bars (top-centre)
	boss_box = VBoxContainer.new()
	boss_box.anchor_left = 0.5
	boss_box.anchor_right = 0.5
	boss_box.position = Vector2(-300, 16)
	boss_box.size = Vector2(600, 10)
	boss_box.add_theme_constant_override("separation", 4)
	boss_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(boss_box)
	# prompt (bottom-centre)
	var prow := HBoxContainer.new()
	prow.anchor_left = 0.0
	prow.anchor_right = 1.0
	prow.anchor_top = 1.0
	prow.anchor_bottom = 1.0
	prow.offset_top = -190
	prow.offset_bottom = -140
	prow.alignment = BoxContainer.ALIGNMENT_CENTER
	prow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(prow)
	prompt = PanelContainer.new()
	prompt.add_theme_stylebox_override("panel", _flat(Color(0.05, 0.05, 0.08, 0.85), GOLD, 2, 18))
	prompt.visible = false
	prompt.mouse_filter = Control.MOUSE_FILTER_STOP
	prompt.gui_input.connect(func(e):
		if (e is InputEventMouseButton and e.pressed) or (e is InputEventScreenTouch and e.pressed):
			G.main.player.try_interact())
	prow.add_child(prompt)
	prompt_label = _label("", 22, F_BODY, CREAM, 4)
	prompt.add_child(prompt_label)
	# toasts
	toast_box = VBoxContainer.new()
	toast_box.anchor_left = 0.5
	toast_box.anchor_right = 0.5
	toast_box.position = Vector2(-400, 110)
	toast_box.size = Vector2(800, 10)
	toast_box.alignment = BoxContainer.ALIGNMENT_BEGIN
	toast_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(toast_box)
	hud.visible = false


func hud_visible(on: bool) -> void:
	hud.visible = on
	touch.visible = G.touch_mode
	_refresh()


func _refresh() -> void:
	if not is_inside_tree():
		return
	money.text = str(int(G.run.get("kepeng", 0)))
	bunga_label.text = str(int(G.meta.bunga))
	money.get_parent().get_child(0).visible = G.in_run
	money.visible = G.in_run
	for c in boon_box.get_children():
		c.queue_free()
	if G.in_run:
		for slot in ["serang", "jurus", "ajian", "lesat"]:
			var id := Boons.slot_holder(slot)
			boon_box.add_child(_boon_slot("res://assets/icons/slot_%s.png" % slot, id))
		for id in G.run.boons:
			if Boons.ALL[id].slot == "pasif":
				boon_box.add_child(_boon_slot("res://assets/icons/slot_pasif.png", id))
	hp_bar.queue_redraw()


func _boon_slot(icon: String, id: String) -> Control:
	var p := PanelContainer.new()
	var col: Color = Color(0.25, 0.25, 0.3) if id == "" else G.GOD_COLORS[Boons.god_of(id)]
	p.add_theme_stylebox_override("panel", _flat(Color(0.05, 0.05, 0.08, 0.8), col, 3, 22))
	var t := TextureRect.new()
	t.texture = load("res://assets/icons/god_%s.png" % Boons.god_of(id)) if id != "" else load(icon)
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	t.custom_minimum_size = Vector2(34, 34)
	t.modulate = Color(1, 1, 1, 1.0 if id != "" else 0.35)
	p.add_child(t)
	if id != "":
		p.tooltip_text = "%s\n%s" % [Boons.ALL[id].name, Boons.desc(id, G.run.boons[id].rar, G.run.boons[id].lvl)]
	return p


func _process(delta: float) -> void:
	if hud.visible and G.in_run:
		var r: float = clamp(float(G.run.hp) / max(1.0, float(G.run.max_hp)), 0.0, 1.0)
		_hp_lag = move_toward(_hp_lag, r, delta * 0.5) if _hp_lag > r else r
		hp_label.text = "%d / %d" % [ceil(float(G.run.hp)), int(G.run.max_hp)]
		hp_bar.queue_redraw()
		pips.queue_redraw()
	hp_bar.visible = G.in_run
	pips.visible = G.in_run
	for i in boss_bars.size():
		var b = bosses[i]
		var bar: Control = boss_bars[i]
		if not is_instance_valid(b):
			bar.set_meta("ratio", 0.0)
		else:
			bar.set_meta("ratio", b.hp / b.max_hp)
			(bar.get_meta("label") as Label).text = "%s — %s" % [b.boss_name, b.boss_title]
		bar.queue_redraw()


func _draw_hp() -> void:
	var r: float = clamp(float(G.run.get("hp", 0)) / max(1.0, float(G.run.get("max_hp", 1))), 0.0, 1.0)
	var w := hp_bar.size.x
	var h := hp_bar.size.y
	hp_bar.draw_rect(Rect2(-3, -3, w + 6, h + 6), INK)
	hp_bar.draw_rect(Rect2(0, 0, w, h), Color(0.18, 0.05, 0.07))
	hp_bar.draw_rect(Rect2(0, 0, w * _hp_lag, h), Color(0.95, 0.85, 0.7))
	hp_bar.draw_rect(Rect2(0, 0, w * r, h), Color(0.78, 0.12, 0.18))
	hp_bar.draw_rect(Rect2(0, 0, w * r, h * 0.35), Color(1, 0.4, 0.4, 0.35))
	hp_bar.draw_rect(Rect2(-3, -3, w + 6, h + 6), GOLD, false, 2.0)
	for i in int(G.run.get("death_defy", 0)):
		hp_bar.draw_circle(Vector2(w + 18 + i * 20, h * 0.5), 7, GOLD)


func _draw_pips() -> void:
	var p: Player = G.main.player if G.main else null
	if p == null:
		return
	var x := 0.0
	# dash charges (teal)
	for i in p.max_dash():
		var on := i < p.dash_charges
		pips.draw_rect(Rect2(x, 4, 22, 12), Color("5fe0c8") if on else Color(0.15, 0.2, 0.22))
		pips.draw_rect(Rect2(x, 4, 22, 12), INK, false, 2.0)
		x += 28
	x += 12
	# prana (special) charges (cream)
	for i in p.max_prana():
		var f: float = clamp(p.prana - i, 0.0, 1.0)
		pips.draw_circle(Vector2(x + 8, 10), 8, Color(0.15, 0.13, 0.12))
		if f >= 1.0:
			pips.draw_circle(Vector2(x + 8, 10), 7, CREAM)
		else:
			pips.draw_arc(Vector2(x + 8, 10), 5, -PI / 2, -PI / 2 + TAU * f, 12, CREAM, 3.0)
		x += 22
	x += 14
	# ajian cooldown ring
	var cf := 1.0 - p.cast_cd / Player.CAST_COOLDOWN
	var col := Color("5fe0c8") if cf >= 1.0 else Color(0.4, 0.5, 0.5)
	pips.draw_arc(Vector2(x + 11, 10), 10, -PI / 2, -PI / 2 + TAU * cf, 24, col, 4.0)
	if cf >= 1.0:
		pips.draw_circle(Vector2(x + 11, 10), 4, col)


func set_bosses(list: Array) -> void:
	bosses = list
	boss_bars = []
	for c in boss_box.get_children():
		c.queue_free()
	for b in list:
		var bar := Control.new()
		bar.custom_minimum_size = Vector2(600, 42)
		bar.set_meta("ratio", 1.0)
		var l := _label(b.boss_name, 18, F_HEAD)
		l.position = Vector2(0, -2)
		bar.add_child(l)
		bar.set_meta("label", l)
		bar.draw.connect(func():
			var r: float = bar.get_meta("ratio")
			bar.draw_rect(Rect2(-2, 24, 604, 16), INK)
			bar.draw_rect(Rect2(0, 26, 600 * r, 12), Color(0.75, 0.1, 0.2))
			bar.draw_rect(Rect2(0, 26, 600 * r, 4), Color(1, 0.5, 0.5, 0.4))
			bar.draw_rect(Rect2(-2, 24, 604, 16), GOLD, false, 2.0))
		boss_box.add_child(bar)
		boss_bars.append(bar)


func show_prompt(text: String) -> void:
	prompt.visible = text != "" and not G.main.busy
	var key := "E" if not G.touch_mode else "Ketuk"
	prompt_label.text = "[%s]  %s" % [key, text]


func toast(text: String, color := CREAM) -> void:
	var l := _label(text, 24, F_BODY, color, 8)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.custom_minimum_size = Vector2(800, 0)
	toast_box.add_child(l)
	var tw := l.create_tween()
	tw.tween_interval(2.2)
	tw.tween_property(l, "modulate:a", 0.0, 0.6)
	tw.tween_callback(l.queue_free)


var _area_box: Control


func area_title(title: String, sub: String) -> void:
	if _area_box and is_instance_valid(_area_box):
		_area_box.queue_free()
	var box := VBoxContainer.new()
	_area_box = box
	box.set_anchors_preset(Control.PRESET_CENTER_TOP)
	box.position = Vector2(-500, 150)
	box.size = Vector2(1000, 100)
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var t := _label(title, 58, F_TITLE, GOLD, 12)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var s := _label(sub, 26, F_HEAD, CREAM, 8)
	s.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(t)
	box.add_child(s)
	overlay.add_child(box)
	box.modulate.a = 0.0
	var tw := box.create_tween()
	tw.tween_property(box, "modulate:a", 1.0, 0.5)
	tw.tween_interval(1.6)
	tw.tween_property(box, "modulate:a", 0.0, 0.8)
	tw.tween_callback(box.queue_free)


func room_clear_banner() -> void:
	var l := _label("Raksasa Tumpas!", 44, F_TITLE, GOLD, 12)
	l.set_anchors_preset(Control.PRESET_CENTER)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.position = Vector2(-400, -160)
	l.custom_minimum_size = Vector2(800, 0)
	l.pivot_offset = Vector2(400, 30)
	overlay.add_child(l)
	l.scale = Vector2(1.4, 1.4)
	var tw := l.create_tween()
	tw.tween_property(l, "scale", Vector2.ONE, 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_interval(1.0)
	tw.tween_property(l, "modulate:a", 0.0, 0.5)
	tw.tween_callback(l.queue_free)


func fade(to_black: bool, done: Callable) -> void:
	var tw := fader.create_tween()
	tw.tween_property(fader, "color:a", 1.0 if to_black else 0.0, 0.35)
	tw.tween_callback(done)


# --- modal screens --------------------------------------------------------------------

func _modal(dim := 0.6) -> Control:
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_STOP
	var bg := ColorRect.new()
	bg.color = Color(0.01, 0.01, 0.03, dim)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(bg)
	overlay.add_child(root)
	prompt.visible = false
	touch.visible = false
	return root


func _close_modal(root: Control) -> void:
	_menu_buttons = []
	root.queue_free()
	touch.visible = _touch_enabled() and G.main.area != "title"


func _portrait(root: Control, id: String, from_left := true) -> TextureRect:
	var tex := portrait_tex(id)
	var t := TextureRect.new()
	t.texture = tex
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	t.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	t.anchor_top = 0.0
	t.anchor_bottom = 1.0
	t.anchor_left = 0.0 if from_left else 0.55
	t.anchor_right = 0.45 if from_left else 1.0
	t.offset_top = 20
	t.offset_bottom = 0
	var m := ShaderMaterial.new()
	m.shader = PORTRAIT_SHADER
	t.material = m
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(t)
	t.modulate.a = 0.0
	var tw := t.create_tween().set_parallel(true)
	tw.tween_property(t, "modulate:a", 1.0, 0.25)
	t.position.x -= 60 if from_left else -60
	tw.tween_property(t, "position:x", t.position.x + (60 if from_left else -60), 0.3).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	return t


## lines: [[speaker_id, text], ...]
func dialog(lines: Array, done: Callable) -> void:
	var root := _modal(0.0)
	var grad := TextureRect.new()
	var gt := GradientTexture2D.new()
	var g := Gradient.new()
	g.set_color(0, Color(0, 0, 0, 0))
	g.set_color(1, Color(0, 0, 0, 0.85))
	gt.gradient = g
	gt.fill_from = Vector2(0, 0)
	gt.fill_to = Vector2(0, 1)
	grad.texture = gt
	grad.set_anchors_preset(Control.PRESET_FULL_RECT)
	grad.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	root.add_child(grad)
	var holder := Control.new()
	holder.set_anchors_preset(Control.PRESET_FULL_RECT)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(holder)
	var box := PanelContainer.new()
	box.add_theme_stylebox_override("panel", _panel_style())
	box.anchor_left = 0.3
	box.anchor_right = 0.97
	box.anchor_top = 1.0
	box.anchor_bottom = 1.0
	box.offset_top = -210
	box.offset_bottom = -26
	root.add_child(box)
	var vb := VBoxContainer.new()
	box.add_child(vb)
	var name_l := _label("", 30, F_HEAD, GOLD, 6)
	vb.add_child(name_l)
	var title_l := _label("", 18, F_BODY, Color(0.75, 0.7, 0.6), 4)
	vb.add_child(title_l)
	var text := RichTextLabel.new()
	text.bbcode_enabled = false
	text.fit_content = true
	text.custom_minimum_size = Vector2(0, 90)
	text.add_theme_font_override("normal_font", F_BODY)
	text.add_theme_font_size_override("normal_font_size", 25)
	text.add_theme_color_override("default_color", CREAM)
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_child(text)
	var hint := _label("▼", 20, F_BODY, GOLD, 4)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	vb.add_child(hint)
	var idx := [0]
	var show_line := func(i: int):
		for c in holder.get_children():
			c.queue_free()
		var who: String = lines[i][0]
		var info: Array = WHO.get(who, [who.capitalize(), ""])
		name_l.text = info[0]
		title_l.text = info[1]
		_portrait(holder, who, true)
		text.text = lines[i][1]
		Hf.speak(lines[i][1])
		text.visible_ratio = 0.0
		_typing = true
		_type_label = text
		var tw := text.create_tween()
		tw.tween_property(text, "visible_ratio", 1.0, 0.018 * String(lines[i][1]).length())
		tw.tween_callback(func(): _typing = false)
		Au.sfx("sfx_ui_move", -12.0)
	show_line.call(0)
	_advance = func():
		if _typing:
			text.visible_ratio = 1.0
			_typing = false
			return
		idx[0] += 1
		if idx[0] >= lines.size():
			Hf.stop_voice()
			_advance = Callable()
			_close_modal(root)
			done.call()
		else:
			show_line.call(idx[0])
	root.gui_input.connect(func(e):
		if (e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT) or (e is InputEventScreenTouch and e.pressed):
			if _advance.is_valid(): _advance.call())


func _input(event: InputEvent) -> void:
	if _advance.is_valid() and (event.is_action_pressed("interact") or event.is_action_pressed("attack") and event is InputEventKey or event.is_action_pressed("dash")):
		get_viewport().set_input_as_handled()
		_advance.call()
		return
	if not _menu_buttons.is_empty():
		for i in 3:
			if event.is_action_pressed("ui_%d" % (i + 1)) and i < _menu_buttons.size():
				get_viewport().set_input_as_handled()
				(_menu_buttons[i] as Button).pressed.emit()
				return


func _card(title: String, title_col: Color, sub: String, desc: String, icon: String, border: Color) -> Button:
	var b := Button.new()
	b.custom_minimum_size = Vector2(0, 118)
	b.focus_mode = Control.FOCUS_ALL
	b.add_theme_stylebox_override("normal", _flat(Color(0.06, 0.06, 0.09, 0.95), border.darkened(0.3), 2, 10))
	b.add_theme_stylebox_override("hover", _flat(Color(0.12, 0.1, 0.12, 0.98), border, 3, 10))
	b.add_theme_stylebox_override("focus", _flat(Color(0.12, 0.1, 0.12, 0.98), GOLD, 3, 10))
	b.add_theme_stylebox_override("pressed", _flat(Color(0.2, 0.16, 0.1, 0.98), GOLD, 3, 10))
	b.add_theme_stylebox_override("disabled", _flat(Color(0.05, 0.05, 0.06, 0.8), Color(0.2, 0.2, 0.2), 2, 10))
	var hb := HBoxContainer.new()
	hb.set_anchors_preset(Control.PRESET_FULL_RECT)
	hb.offset_left = 14
	hb.offset_right = -14
	hb.add_theme_constant_override("separation", 14)
	hb.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(hb)
	if icon != "":
		var t := TextureRect.new()
		t.texture = load(icon)
		t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		t.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		t.custom_minimum_size = Vector2(74, 74)
		t.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		t.mouse_filter = Control.MOUSE_FILTER_IGNORE
		hb.add_child(t)
	var vb := VBoxContainer.new()
	vb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vb.alignment = BoxContainer.ALIGNMENT_CENTER
	vb.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hb.add_child(vb)
	var top := HBoxContainer.new()
	top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_child(top)
	var tl := _label(title, 24, F_HEAD, title_col, 4)
	tl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(tl)
	if sub != "":
		var sl := _label("   " + sub, 18, F_BODY, Color(0.7, 0.68, 0.62), 3)
		sl.mouse_filter = Control.MOUSE_FILTER_IGNORE
		top.add_child(sl)
	var dl := _label(desc, 19, F_BODY, CREAM, 3)
	dl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	dl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_child(dl)
	return b


func boon_menu(god: String, offers: Array, done: Callable) -> void:
	var root := _modal(0.55)
	_portrait(root, "dewa_" + god, true)
	var right := VBoxContainer.new()
	right.anchor_left = 0.42
	right.anchor_right = 0.97
	right.anchor_top = 0.08
	right.anchor_bottom = 0.95
	right.add_theme_constant_override("separation", 12)
	root.add_child(right)
	var nm := _label(G.GOD_NAMES[god], 44, F_TITLE, G.GOD_COLORS[god], 10)
	right.add_child(nm)
	right.add_child(_label(G.GOD_TITLES[god], 20, F_HEAD, Color(0.8, 0.75, 0.65), 4))
	var god_line: String = Boons.LINES[god][randi() % Boons.LINES[god].size()]
	Hf.speak(god_line)
	var line := _label("“%s”" % god_line, 22, F_BODY, CREAM, 4)
	line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(line)
	var sp := Control.new()
	sp.custom_minimum_size = Vector2(0, 8)
	right.add_child(sp)
	_menu_buttons = []
	for i in offers.size():
		var o: Dictionary = offers[i]
		var info: Dictionary = Boons.ALL[o.id]
		var sub := "%s · %s" % [Boons.SLOT_NAME[info.slot], Boons.RARITY[o.rar]]
		var holder := Boons.slot_holder(info.slot)
		var desc := Boons.desc(o.id, o.rar)
		if holder != "" and info.slot != "pasif":
			desc += "  (Mengganti: %s)" % Boons.ALL[holder].name
		var card := _card("%d. %s" % [i + 1, info.name], Boons.RARITY_COLOR[o.rar], sub, desc,
			"res://assets/icons/slot_%s.png" % info.slot, Boons.RARITY_COLOR[o.rar])
		card.pressed.connect(func():
			_close_modal(root)
			done.call(o))
		right.add_child(card)
		_menu_buttons.append(card)
	if not _menu_buttons.is_empty():
		(_menu_buttons[0] as Button).call_deferred("grab_focus")
	Au.sfx("sfx_boon_appear", -6.0)


func choice_menu(title: String, subtitle: String, opts: Array, done: Callable, closable := false) -> void:
	var root := _modal(0.7)
	var box := PanelContainer.new()
	box.add_theme_stylebox_override("panel", _panel_style())
	box.anchor_left = 0.18
	box.anchor_right = 0.82
	box.anchor_top = 0.06
	box.anchor_bottom = 0.94
	root.add_child(box)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 10)
	box.add_child(vb)
	var t := _label(title, 40, F_TITLE, GOLD, 8)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(t)
	var s := _label(subtitle, 22, F_BODY, CREAM, 4)
	s.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(s)
	var sc := ScrollContainer.new()
	sc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	vb.add_child(sc)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 8)
	sc.add_child(list)
	_menu_buttons = []
	for o in opts:
		var card := _card(o.title, CREAM, "", o.desc, o.get("icon", ""), GOLD)
		card.custom_minimum_size.y = 96
		card.disabled = o.get("disabled", false)
		card.pressed.connect(func():
			_close_modal(root)
			done.call(o))
		list.add_child(card)
		_menu_buttons.append(card)
	if closable:
		var close := Button.new()
		close.text = "Tutup"
		close.add_theme_font_override("font", F_HEAD)
		close.add_theme_font_size_override("font_size", 24)
		close.add_theme_stylebox_override("normal", _flat(Color(0.1, 0.08, 0.08), GOLD, 2, 10))
		close.add_theme_stylebox_override("hover", _flat(Color(0.2, 0.14, 0.1), GOLD, 3, 10))
		close.pressed.connect(func():
			_close_modal(root)
			done.call({}))
		vb.add_child(close)
		close.call_deferred("grab_focus")
	else:
		for b in _menu_buttons:
			if not b.disabled:
				b.call_deferred("grab_focus")
				break


func _big_button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(340, 60)
	b.add_theme_font_override("font", F_HEAD)
	b.add_theme_font_size_override("font_size", 28)
	b.add_theme_color_override("font_color", CREAM)
	b.add_theme_color_override("font_hover_color", GOLD)
	b.add_theme_color_override("font_focus_color", GOLD)
	b.add_theme_stylebox_override("normal", _flat(Color(0.06, 0.05, 0.07, 0.85), GOLD.darkened(0.4), 2, 8))
	b.add_theme_stylebox_override("hover", _flat(Color(0.14, 0.1, 0.08, 0.95), GOLD, 3, 8))
	b.add_theme_stylebox_override("focus", _flat(Color(0.14, 0.1, 0.08, 0.95), GOLD, 3, 8))
	b.add_theme_stylebox_override("pressed", _flat(Color(0.2, 0.14, 0.08, 0.95), GOLD, 3, 8))
	b.pressed.connect(func():
		Au.sfx("sfx_ui_select", -4.0)
		cb.call())
	return b


func title_screen(start: Callable) -> void:
	var root := _modal(0.0)
	var art := portrait_tex("keyart")
	if art:
		var bg := TextureRect.new()
		bg.texture = art
		bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		bg.set_anchors_preset(Control.PRESET_FULL_RECT)
		bg.modulate = Color(0.75, 0.75, 0.8)
		root.add_child(bg)
		var tw := bg.create_tween().set_loops()
		tw.tween_property(bg, "scale", Vector2(1.04, 1.04), 12.0).set_trans(Tween.TRANS_SINE)
		tw.tween_property(bg, "scale", Vector2(1.0, 1.0), 12.0).set_trans(Tween.TRANS_SINE)
	var shade := TextureRect.new()
	var sg := GradientTexture2D.new()
	var gg := Gradient.new()
	gg.set_color(0, Color(0, 0, 0, 0.75))
	gg.set_color(1, Color(0, 0, 0, 0.2))
	gg.add_point(0.45, Color(0, 0, 0, 0.1))
	sg.gradient = gg
	sg.fill_to = Vector2(0, 1)
	shade.texture = sg
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(shade)
	var vb := VBoxContainer.new()
	vb.anchor_left = 0.0
	vb.anchor_right = 1.0
	vb.anchor_top = 0.12
	vb.anchor_bottom = 0.95
	vb.alignment = BoxContainer.ALIGNMENT_BEGIN
	vb.add_theme_constant_override("separation", 6)
	root.add_child(vb)
	var t := _label("HANOMAN DUTA", 92, F_TITLE, GOLD, 18)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(t)
	var s := _label("Lakon Ramayana & Legenda Sura dan Baya", 28, F_HEAD, CREAM, 8)
	s.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(s)
	var sp := Control.new()
	sp.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vb.add_child(sp)
	var bb := VBoxContainer.new()
	bb.alignment = BoxContainer.ALIGNMENT_CENTER
	bb.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	bb.add_theme_constant_override("separation", 10)
	vb.add_child(bb)
	var go := _big_button("Mulai Lakon" if int(G.meta.runs) == 0 else "Lanjutkan Lakon", func():
		Au.sfx("sfx_boon_pick", -3.0)
		_close_modal(root)
		G.main.area = "hub"
		start.call())
	bb.add_child(go)
	if not Hf.loaded:
		var label_ok := go.text
		go.disabled = true
		go.text = "Memuat aset Higgsfield…"
		Hf.progress.connect(func(d, tot):
			if is_instance_valid(go): go.text = "Memuat aset Higgsfield… %d/%d" % [d, tot])
		Hf.ready_loaded.connect(func():
			if is_instance_valid(go):
				go.disabled = false
				go.text = label_ok
				go.grab_focus())
	var ctl := _big_button("Kontrol", func(): _controls_help())
	bb.add_child(ctl)
	go.call_deferred("grab_focus")
	var snd := _label("Nyalakan suara (di iPhone matikan mode senyap)", 16, F_BODY, Color(0.7, 0.68, 0.62), 4)
	snd.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(snd)
	var cr := _label("Demo · karya @leonrdewa · aset Blender & Higgsfield", 18, F_BODY, Color(0.8, 0.78, 0.7), 6)
	cr.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(cr)


func _controls_help() -> void:
	var txt := "PC:  WASD gerak · J / klik kiri = Serang (kombo 3) · K / klik kanan = Jurus (tongkat mulur)\nQ = Ajian (lingkaran pengikat) · Spasi / Shift = Lesat (menghindar) · E = Interaksi · Esc = Jeda\nMouse mengarahkan serangan.\n\nHP / Tablet:  jempol kiri = gerak, tombol kanan = Serang, Jurus, Ajian, Lesat.\nSerangan otomatis membidik raksasa terdekat.\n\nGamepad:  stik kiri gerak · X Serang · Y Jurus · RB Ajian · A Lesat · B Interaksi"
	choice_menu("Kontrol", "", [{"title": "Cara bermain", "desc": txt, "disabled": true}], func(_o): pass, true)


func pause_menu() -> void:
	if get_tree().paused:
		return
	get_tree().paused = true
	var root := _modal(0.7)
	var vb := VBoxContainer.new()
	vb.set_anchors_preset(Control.PRESET_CENTER)
	vb.position = Vector2(-170, -180)
	vb.add_theme_constant_override("separation", 12)
	root.add_child(vb)
	var t := _label("Jeda", 56, F_TITLE, GOLD, 10)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(t)
	var resume := func():
		get_tree().paused = false
		_close_modal(root)
	var b := _big_button("Lanjut", resume)
	vb.add_child(b)
	vb.add_child(_big_button("Kontrol", func(): _controls_help()))
	if G.in_run:
		vb.add_child(_big_button("Kembali ke Pancawati", func():
			resume.call()
			G.end_run(false)
			G.main.go_hub()))
	b.call_deferred("grab_focus")
	root.gui_input.connect(func(e):
		if e.is_action_pressed("pause"): resume.call())


func _summary_lines() -> String:
	return "Ruang dicapai: %d / %d\nAnugerah: %d\nKembang Wijayakusuma didapat: %d" % [
		int(G.run.get("room", 0)), G.main.LAST_ROOM, G.run.get("boons", {}).size(), int(G.run.get("bunga_gained", 0))]


func death_screen(done: Callable) -> void:
	var root := _modal(0.8)
	var vb := VBoxContainer.new()
	vb.set_anchors_preset(Control.PRESET_CENTER)
	vb.position = Vector2(-400, -200)
	vb.custom_minimum_size = Vector2(800, 0)
	vb.add_theme_constant_override("separation", 16)
	root.add_child(vb)
	var t := _label("Hanoman Gugur", 70, F_TITLE, Color(0.85, 0.2, 0.25), 14)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(t)
	var q := _label("Angin tak pernah mati. Ia hanya kembali ke asalnya.", 24, F_BODY, CREAM, 6)
	q.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(q)
	var s := _label(_summary_lines(), 22, F_HEAD, Color(0.8, 0.78, 0.7), 6)
	s.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(s)
	var b := _big_button("Kembali ke Pancawati", func():
		_close_modal(root)
		done.call())
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	vb.add_child(b)
	b.call_deferred("grab_focus")


func victory_screen(done: Callable) -> void:
	var root := _modal(0.85)
	var art := portrait_tex("keyart")
	if art == null:
		art = portrait_tex("title")
	if art:
		var bg := TextureRect.new()
		bg.texture = art
		bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		bg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		bg.set_anchors_preset(Control.PRESET_FULL_RECT)
		bg.modulate = Color(0.5, 0.5, 0.55)
		root.add_child(bg)
	var vb := VBoxContainer.new()
	vb.set_anchors_preset(Control.PRESET_CENTER)
	vb.position = Vector2(-450, -230)
	vb.custom_minimum_size = Vector2(900, 0)
	vb.add_theme_constant_override("separation", 14)
	root.add_child(vb)
	for row in [["Muara Kalimas Terlampaui", 58, F_TITLE, GOLD], ["Sura dan Baya takluk — dan sejak hari itu, orang menyebut tanah di muara itu Surabaya.", 24, F_BODY, CREAM],
			["Bersambung ke Alengka...", 34, F_HEAD, Color("5fe0c8")], [_summary_lines(), 22, F_HEAD, Color(0.8, 0.78, 0.7)],
			["+10 Kembang Wijayakusuma", 24, F_HEAD, CREAM]]:
		var l := _label(row[0], row[1], row[2], row[3], 8)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		vb.add_child(l)
	var b := _big_button("Kembali ke Pancawati", func():
		_close_modal(root)
		done.call())
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	vb.add_child(b)
	b.call_deferred("grab_focus")


# --- touch controls ---------------------------------------------------------------------

func _touch_enabled() -> bool:
	return G.touch_mode


func _build_touch() -> void:
	touch = Control.new()
	touch.set_anchors_preset(Control.PRESET_FULL_RECT)
	touch.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(touch)
	_joy_base = Panel.new()
	var st := _flat(Color(1, 1, 1, 0.08), Color(1, 1, 1, 0.3), 3, 90)
	_joy_base.add_theme_stylebox_override("panel", st)
	_joy_base.size = Vector2(180, 180)
	_joy_base.visible = false
	_joy_base.mouse_filter = Control.MOUSE_FILTER_IGNORE
	touch.add_child(_joy_base)
	_joy_knob = Panel.new()
	_joy_knob.add_theme_stylebox_override("panel", _flat(Color(1, 1, 1, 0.3), GOLD, 3, 40))
	_joy_knob.size = Vector2(80, 80)
	_joy_knob.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_joy_base.add_child(_joy_knob)
	var buttons := [
		["attack", "Serang", Vector2(-150, -150), 120, "slot_serang"],
		["special", "Jurus", Vector2(-290, -110), 84, "slot_jurus"],
		["cast", "Ajian", Vector2(-240, -250), 84, "slot_ajian"],
		["dash", "Lesat", Vector2(-120, -290), 84, "slot_lesat"],
	]
	for b in buttons:
		var c := Control.new()
		c.anchor_left = 1.0
		c.anchor_right = 1.0
		c.anchor_top = 1.0
		c.anchor_bottom = 1.0
		var sz: int = b[3]
		c.position = b[2] - Vector2(sz, sz) * 0.5
		c.size = Vector2(sz, sz)
		c.set_meta("action", b[0])
		c.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var pnl := Panel.new()
		pnl.add_theme_stylebox_override("panel", _flat(Color(0.05, 0.05, 0.08, 0.55), GOLD, 3, sz / 2))
		pnl.set_anchors_preset(Control.PRESET_FULL_RECT)
		pnl.mouse_filter = Control.MOUSE_FILTER_IGNORE
		c.add_child(pnl)
		var ic := TextureRect.new()
		ic.texture = load("res://assets/icons/%s.png" % b[4])
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.set_anchors_preset(Control.PRESET_FULL_RECT)
		ic.offset_left = sz * 0.2
		ic.offset_top = sz * 0.2
		ic.offset_right = -sz * 0.2
		ic.offset_bottom = -sz * 0.2
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		c.add_child(ic)
		touch.add_child(c)
	var pause_b := Button.new()
	pause_b.text = "II"
	pause_b.anchor_left = 1.0
	pause_b.anchor_right = 1.0
	pause_b.position = Vector2(-70, 70)
	pause_b.size = Vector2(52, 52)
	pause_b.add_theme_stylebox_override("normal", _flat(Color(0.05, 0.05, 0.08, 0.6), GOLD, 2, 26))
	pause_b.pressed.connect(func(): if not G.main.busy: pause_menu())
	touch.add_child(pause_b)
	touch.visible = false


var _btn_touch := {}


func _unhandled_input(event: InputEvent) -> void:
	if not touch.visible:
		if event is InputEventScreenTouch and event.pressed and not G.touch_mode and G.main and G.main.area != "title":
			G.enable_touch()
			touch.visible = true
		return
	if event is InputEventScreenTouch:
		var pos: Vector2 = event.position
		if event.pressed:
			var hit := _button_at(pos)
			if hit != "":
				_btn_touch[event.index] = hit
				Input.action_press(hit)
				get_viewport().set_input_as_handled()
				return
			if pos.x < get_viewport().get_visible_rect().size.x * 0.5 and _joy_id == -1:
				_joy_id = event.index
				_joy_origin = pos
				_joy_base.visible = true
				_joy_base.position = pos - _joy_base.size * 0.5
				_joy_knob.position = _joy_base.size * 0.5 - _joy_knob.size * 0.5
				get_viewport().set_input_as_handled()
		else:
			if _btn_touch.has(event.index):
				Input.action_release(_btn_touch[event.index])
				_btn_touch.erase(event.index)
			if event.index == _joy_id:
				_joy_id = -1
				_joy_base.visible = false
				G.main.player.touch_move = Vector2.ZERO
	elif event is InputEventScreenDrag and event.index == _joy_id:
		var d: Vector2 = event.position - _joy_origin
		var l := d.length()
		var maxr := 80.0
		if l > maxr:
			d = d / l * maxr
		_joy_knob.position = _joy_base.size * 0.5 - _joy_knob.size * 0.5 + d
		G.main.player.touch_move = d / maxr
		get_viewport().set_input_as_handled()


func _button_at(pos: Vector2) -> String:
	for c in touch.get_children():
		if c.has_meta("action"):
			var r := Rect2(c.global_position, c.size).grow(14)
			if r.has_point(pos):
				return c.get_meta("action")
	return ""


func show_touch(on: bool) -> void:
	touch.visible = on and _touch_enabled()
