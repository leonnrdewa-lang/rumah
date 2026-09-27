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


func world_to_map(p: Vector3, area: Rect2) -> Vector2:
	var ws: float = world.world_size
	# show the island (crop the empty sea around it)
	var crop := Rect2(-85, -75, 170, 150)
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
	var crop := Rect2(-85, -75, 170, 150)
	var src := Rect2((crop.position.x + ws * 0.5) / ws * TEX.get_width(), (crop.position.y + ws * 0.5) / ws * TEX.get_height(),
		crop.size.x / ws * TEX.get_width(), crop.size.y / ws * TEX.get_height())
	draw_texture_rect_region(TEX, area.grow(-3), src)
	var tile: float = world.tile_size
	for p in GS.parcels:
		var c := Vector3(p["center"][0], 0, p["center"][1])
		var a := world_to_map(c - Vector3(tile * 2, 0, tile * 1.5), area)
		var b := world_to_map(c + Vector3(tile * 2, 0, tile * 1.5), area)
		var col := Color("8a5a32")
		if p["owner"] == "player":
			col = Color("2f6d2a")
		elif p["plasma"]:
			col = Color("e08a2c")
		draw_rect(Rect2(a, b - a), Color(col, 0.55), true)
		draw_rect(Rect2(a, b - a), col, false, 2.0)
	var fs := 13 if not big else 18
	for id in LABELS:
		if not world.door_points.has(id):
			continue
		var pt := world_to_map(world.door_points[id], area)
		draw_circle(pt, 4.5 if not big else 6.0, Color("fdf3dc"))
		draw_circle(pt, 3.0 if not big else 4.0, Color("c9563c"))
		if big or id in ["pabrik", "kantor"]:
			var text: String = LABELS[id]
			var tw := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
			var at := pt + Vector2(6, 4)
			if at.x + tw > size.x - 6:
				at.x = pt.x - 6 - tw
			draw_string_outline(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, 4, Color("fdf3dc"))
			draw_string(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color("5a3b22"))
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
			return world.door_points.get("kantor") if GS.controlled_parcels() >= 7 else null
	return null
