extends Control
## Small island map for the HUD: roads and coast from a baked texture, parcels
## coloured by who controls them, key buildings, the current quest target and
## the player. Click/tap toggles a big view.

const TEX := preload("res://assets/textures/minimap.png")
const LABELS := {"kantor": "Kantor", "toko": "Koperasi", "warung": "Warung", "pabrik": "Pabrik", "calo": "Calo"}

var world: Node
var ui: Node
var big := false
var font: Font
var _t := 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = true
	gui_input.connect(func(e):
		if ui and ui.is_blocking():
			return  # no big map on top of a dialog / menu
		if (e is InputEventMouseButton and e.pressed) or (e is InputEventScreenTouch and e.pressed):
			big = not big
			Sfx.play("click", 1.0, -6.0)
			var n := get_parent()
			while n and not n.has_method("_layout"):
				n = n.get_parent()
			if n:
				n.call_deferred("_layout")
			accept_event())


func _process(delta: float) -> void:
	_t += delta
	if is_visible_in_tree():
		queue_redraw()


## map v3: the island is ~350 m across. The big map shows all of it; the small one a
## 170 x 150 m window (the v2 island's size) around the player.
const ISLAND_CROP := Rect2(2.0 - 178.0, -2.0 - 157.0, 356.0, 314.0)
const LOCAL_SIZE := Vector2(170.0, 150.0)


func _crop() -> Rect2:
	if big or world == null or world.player == null:
		return ISLAND_CROP
	var c := Vector2(world.player.global_position.x, world.player.global_position.z)
	var o := c - LOCAL_SIZE * 0.5
	o.x = clampf(o.x, ISLAND_CROP.position.x, ISLAND_CROP.end.x - LOCAL_SIZE.x)
	o.y = clampf(o.y, ISLAND_CROP.position.y, ISLAND_CROP.end.y - LOCAL_SIZE.y)
	return Rect2(o, LOCAL_SIZE)


func world_to_map(p: Vector3, area: Rect2) -> Vector2:
	# show the island (crop the empty sea around it)
	var crop := _crop()
	var u := (p.x - crop.position.x) / crop.size.x
	var v := (p.z - crop.position.y) / crop.size.y
	return area.position + Vector2(u, v) * area.size


func _draw() -> void:
	if world == null:
		return
	var area := Rect2(Vector2.ZERO, size)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color("3f9aa0")
	bg.set_corner_radius_all(18)
	bg.anti_aliasing = true
	draw_style_box(bg, area)
	var ws: float = world.world_size
	var crop := _crop()
	var src := Rect2((crop.position.x + ws * 0.5) / ws * TEX.get_width(), (crop.position.y + ws * 0.5) / ws * TEX.get_height(),
		crop.size.x / ws * TEX.get_width(), crop.size.y / ws * TEX.get_height())
	draw_texture_rect_region(TEX, area.grow(-3), src)
	var tile: float = world.tile_size
	var ph: Array = world.layout.get("parcel_half", [tile * 1.5, tile])
	var half := Vector3(float(ph[0]) + tile * 0.5, 0, float(ph[1]) + tile * 0.5)
	for p in GS.parcels:
		var c := Vector3(p["center"][0], 0, p["center"][1])
		var a := world_to_map(c - half, area)
		var b := world_to_map(c + half, area)
		var col := Color("8a5a32")
		if p["owner"] == "player":
			col = Color("2f6d2a")
		elif p["plasma"]:
			col = Color("e08a2c")
		draw_rect(Rect2(a, b - a), Color(col, 0.55), true)
		draw_rect(Rect2(a, b - a), col, false, 2.0)
	var fs := 13 if not big else 18
	# the small map only names Pabrik / Kantor, and only while it is at least
	# ~200 px wide on screen: smaller, the names sit on the markers and roads
	var on_screen: float = size.x * (ui.screen_scale() if ui and ui.has_method("screen_scale") else 1.0)
	var names := big or on_screen >= 200.0
	for id in LABELS:
		if not world.door_points.has(id):
			continue
		var pt := world_to_map(world.door_points[id], area)
		draw_circle(pt, 4.5 if not big else 6.0, Color("fdf3dc"))
		draw_circle(pt, 3.0 if not big else 4.0, Color("c9563c"))
		if big or (names and id in ["pabrik", "kantor"]):
			var text: String = LABELS[id]
			var tw := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
			var at := pt + Vector2(6, 4)
			if at.x + tw > size.x - 6:
				at.x = pt.x - 6 - tw
			draw_string_outline(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, 4, Color("fdf3dc"))
			draw_string(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color("5a3b22"))
	if big:
		# the hamlets' names (map v3)
		for v in world.layout.get("villages", []):
			if v["id"] == "sukamakmur":
				continue
			var vp := world_to_map(Vector3(v["center"][0], 0, v["center"][1]), area) + Vector2(0, -14)
			var vt: String = v["name"]
			var vw := font.get_string_size(vt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs - 2).x
			draw_string_outline(font, vp - Vector2(vw * 0.5, 0), vt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs - 2, 4, Color("fdf3dc"))
			draw_string(font, vp - Vector2(vw * 0.5, 0), vt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs - 2, Color("3b5d2a"))
	var target: Variant = quest_target()
	if target != null:
		var tp := world_to_map(target, area)
		var r := 7.0 + sin(_t * 5.0) * 2.0
		draw_arc(tp, r, 0, TAU, 20, Color("e9b949"), 2.5)
	if world.player:
		var pp := world_to_map(world.player.global_position, area)
		var f: Vector3 = world.player.facing
		var dir := Vector2(f.x, f.z).normalized()
		var side := Vector2(-dir.y, dir.x)
		var pts := PackedVector2Array([pp + dir * 8.0, pp - dir * 5.0 + side * 5.0, pp - dir * 5.0 - side * 5.0])
		draw_colored_polygon(pts, Color("fdf3dc"))
		draw_circle(pp, 3.5, Color("d0402a"))
	# cream frame with a thin tan outline, like the HUD pills
	var border := StyleBoxFlat.new()
	border.draw_center = false
	border.border_color = Color("fcf2dd")
	border.set_border_width_all(5)
	border.set_corner_radius_all(18)
	border.anti_aliasing = true
	draw_style_box(border, area)
	var outline := StyleBoxFlat.new()
	outline.draw_center = false
	outline.border_color = Color("d8c29a")
	outline.set_border_width_all(2)
	outline.set_corner_radius_all(18)
	outline.anti_aliasing = true
	draw_style_box(outline, area)



func quest_target() -> Variant:
	match GS.quest_index:
		0, 2:
			return Vector3(GS.parcels[0]["center"][0], 0, GS.parcels[0]["center"][1])
		1, 6:
			return world.door_points.get("pabrik")
		3:
			return world.door_points.get("kantor")
		4:
			return world.door_points.get("calo") if GS.money < 3500000 else null
		9:
			return world.door_points.get("kantor") if GS.controlled_parcels() >= GS.LICENSE_NEED else null
	return null
