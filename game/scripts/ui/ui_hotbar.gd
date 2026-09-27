extends HBoxContainer
## Tool hotbar (bottom-right, as in the target screenshot): five rounded cream
## slots with dark number badges — 1 parang, 2 bibit, 3 pupuk, 4 egrek,
## 5 karung TBS — plus small extra slots for cooking oil and forged land
## papers once you have them. The slot matching the current context action
## (clear / plant / fert / harvest / sell) lifts and glows; counts pop when
## they change. Clicking/tapping a slot (or pressing 1-5) shows what it is for.

signal slot_pressed(id: String)

const SLOTS := [
	{"id": "parang", "icon": "icon_parang", "kind": "clear", "name": "Parang", "hint": "tebas semak di lahanmu"},
	{"id": "bibit", "icon": "icon_bibit", "kind": "plant", "count": "bibit", "name": "Bibit sawit", "hint": "tanam di petak kosong (beli di Koperasi)"},
	{"id": "pupuk", "icon": "icon_pupuk", "kind": "fert", "count": "pupuk", "name": "Pupuk", "hint": "sawit tumbuh lebih cepat"},
	{"id": "egrek", "icon": "icon_egrek", "kind": "harvest", "name": "Egrek", "hint": "panen tandan buah segar (TBS)"},
	{"id": "tbs", "icon": "icon_tbs", "kind": "sell", "count": "tbs", "name": "Karung TBS", "hint": "jual ke Pabrik di timur desa"},
]
const EXTRA := [
	{"id": "minyak", "icon": "icon_minyak", "count": "minyak", "name": "Minyak goreng", "hint": "tawarkan ke warga (harga kamu yang atur)"},
	{"id": "surat", "icon": "icon_surat", "count": "surat", "name": "Surat tanah palsu", "hint": "dipakai untuk 'membeli' kebun warga"},
]

var ui: Node
var slots := {}        # id -> {"card", "count", "icon", "def", "n"}
var labels := {}       # item key -> count Label (ui.inv_labels)
var active := ""
var _counts := {}
var _slot := 66.0


func build(slot_size := 66.0) -> void:
	_slot = slot_size
	add_theme_constant_override("separation", 8)
	alignment = BoxContainer.ALIGNMENT_END
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	for c in get_children():
		c.queue_free()
	slots.clear()
	labels.clear()
	for i in EXTRA.size():
		_add_slot(EXTRA[i], 0, true)
	var gap := Control.new()
	gap.name = "Gap"
	gap.custom_minimum_size = Vector2(4, 0)
	gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(gap)
	for i in SLOTS.size():
		_add_slot(SLOTS[i], i + 1, false)
	_apply_styles(false)


func _card_style(on: bool, small: bool) -> StyleBoxFlat:
	var s: StyleBoxFlat = ui._box(ui.CREAM_LIGHT if on else ui.CREAM, 16 if not small else 14,
		ui.ACCENT if on else ui.LINE, 3 if on else 2, true)
	if on:
		s.shadow_color = Color(0.95, 0.62, 0.2, 0.45)
		s.shadow_size = 12
		s.shadow_offset = Vector2(0, 2)
	return s


func _add_slot(def: Dictionary, n: int, small: bool) -> void:
	var sz := _slot * (0.8 if small else 1.0)
	var holder := Control.new()
	holder.name = "inv_" + str(def["id"])
	holder.custom_minimum_size = Vector2(sz, sz)
	holder.size_flags_vertical = Control.SIZE_SHRINK_END
	holder.mouse_filter = Control.MOUSE_FILTER_STOP
	holder.tooltip_text = ""
	add_child(holder)
	var card := Panel.new()
	card.name = "Card"
	card.size = Vector2(sz, sz)
	card.pivot_offset = Vector2(sz, sz) * 0.5
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_theme_stylebox_override("panel", _card_style(false, small))
	holder.add_child(card)
	var ic := TextureRect.new()
	ic.texture = ui.icon(str(def["icon"]))
	ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var isz := sz * 0.74
	ic.size = Vector2(isz, isz)
	ic.position = Vector2(sz - isz, sz - isz) * 0.5
	ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(ic)
	var cnt: Label = null
	if def.has("count"):
		cnt = ui._label("0", 17 if not small else 15, ui.BROWN, true)
		cnt.add_theme_color_override("font_outline_color", ui.CREAM_LIGHT)
		cnt.add_theme_constant_override("outline_size", 6)
		cnt.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		cnt.position = Vector2(2, -1)
		cnt.size = Vector2(sz - 8, 22)
		card.add_child(cnt)
		labels[def["count"]] = cnt
	if n > 0:
		var badge := PanelContainer.new()
		badge.add_theme_stylebox_override("panel", ui._box(ui.INK, 14, ui.CREAM_LIGHT, 2))
		badge.size = Vector2(26, 26)
		badge.position = Vector2(sz - 19, sz - 19)
		badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var nl: Label = ui._label(str(n), 14, ui.CREAM_LIGHT, true)
		nl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		nl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		badge.add_child(nl)
		card.add_child(badge)
	var id := str(def["id"])
	holder.gui_input.connect(func(e: InputEvent):
		if (e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT) or (e is InputEventScreenTouch and e.pressed):
			flash(id)
			slot_pressed.emit(id)
			holder.accept_event())
	slots[id] = {"card": card, "count": cnt, "icon": ic, "def": def, "n": n, "small": small, "holder": holder}


func slot_def(id: String) -> Dictionary:
	return slots[id]["def"] if slots.has(id) else {}


func id_for_number(n: int) -> String:
	for id in slots:
		if int(slots[id]["n"]) == n:
			return id
	return ""


func update_counts() -> void:
	for id in slots:
		var s: Dictionary = slots[id]
		var def: Dictionary = s["def"]
		if not def.has("count"):
			continue
		var k := str(def["count"])
		var n := int(GS.inv.get(k, 0))
		var l: Label = s["count"]
		l.text = ("%d/%d" % [n, GS.capacity()]) if k == "tbs" else str(n)
		var empty := n <= 0 and k in ["bibit", "pupuk"]
		var full := k == "tbs" and n >= GS.capacity()
		l.add_theme_color_override("font_color", ui.RED if empty or full else ui.BROWN)
		(s["icon"] as Control).modulate = Color(1, 1, 1, 0.5 if empty else 1.0)
		if _counts.has(k) and int(_counts[k]) != n:
			pop(id)
		_counts[k] = n
	(slots["surat"]["holder"] as Control).visible = int(GS.inv.get("surat", 0)) > 0
	(slots["minyak"]["holder"] as Control).visible = GS.upgrades.get("mesin", false) or int(GS.inv.get("minyak", 0)) > 0
	(get_node("Gap") as Control).visible = (slots["surat"]["holder"] as Control).visible or (slots["minyak"]["holder"] as Control).visible


func set_active(kind: String) -> void:
	var id := ""
	if kind != "":
		for sid in slots:
			if str(slots[sid]["def"].get("kind", "")) == kind:
				id = sid
	if id == active:
		return
	active = id
	_apply_styles(true)


func _apply_styles(animate: bool) -> void:
	for id in slots:
		var s: Dictionary = slots[id]
		var card: Panel = s["card"]
		var on: bool = id == active
		card.add_theme_stylebox_override("panel", _card_style(on, s["small"]))
		var y := -8.0 if on else 0.0
		var sc := Vector2(1.08, 1.08) if on else Vector2.ONE
		if animate:
			var tw := card.create_tween().set_parallel().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			tw.tween_property(card, "position:y", y, 0.22)
			tw.tween_property(card, "scale", sc, 0.22)
		else:
			card.position.y = y
			card.scale = sc


func pop(id: String) -> void:
	if not slots.has(id):
		return
	var card: Panel = slots[id]["card"]
	var base := Vector2(1.08, 1.08) if id == active else Vector2.ONE
	var tw := card.create_tween()
	tw.tween_property(card, "scale", base * 1.16, 0.08)
	tw.tween_property(card, "scale", base, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


func flash(id: String) -> void:
	pop(id)
