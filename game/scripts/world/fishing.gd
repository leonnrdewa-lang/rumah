extends Node3D
## Mancing: a one-button fishing minigame (E / Space, or the round action button).
##   cast  - the rod swings back and forward, the bobber flies out onto the water
##   wait  - the bobber bobs; pressing now reels in empty (too early)
##   bite  - "!" over the player, the bobber dips: press within BITE_WINDOW s
##   reel  - a small timing bar: a cursor sweeps back and forth, press while it is
##           inside the green zone (smaller and faster for rarer fish) to land it
## Moving (stick / keys) while waiting packs the rod up. Costs GS.ENERGY_COST.fish.

const ROD_LEN := 1.75
const BITE_WINDOW := 1.25
const REEL_TIME := 5.0

var world: Node
var ui: Node
var active := false
var phase := ""
var water := "river"
var spot := Vector3.ZERO
var fish_id := ""
var fast := false          # autotest: short waits
var last_result := ""      # "caught:<id>" / "early" / "missed" / "escaped" / "cancel"
var cursor := 0.0          # 0..1 on the timing bar
var zone_c := 0.5
var zone_w := 0.25
var _dir := 1.0
var _speed := 1.0
var _t := 0.0
var _wait := 0.0
var _rod_a := 55.0         # rod pitch from vertical toward the front (deg)
var rod: Node3D
var bobber: Node3D
var _line: MeshInstance3D
var _line_mesh: ImmediateMesh
var _emote: Label3D
var _bar: Control
var _bar_zone: Panel
var _bar_sweet: Panel
var _bar_cursor: Panel
var _bar_label: Label
var _bob_from := Vector3.ZERO


func _ready() -> void:
	_build_rod()
	_build_bobber()
	_line_mesh = ImmediateMesh.new()
	_line = MeshInstance3D.new()
	_line.mesh = _line_mesh
	var lm := StandardMaterial3D.new()
	lm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	lm.albedo_color = Color(0.98, 0.96, 0.9)
	_line.material_override = lm
	_line.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_line)
	_emote = Label3D.new()
	_emote.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_emote.font = ModelLib.label_font()
	_emote.font_size = 96
	_emote.outline_size = 18
	_emote.modulate = Color("d9402a")
	_emote.outline_modulate = Color("fdf3dc")
	_emote.no_depth_test = true
	_emote.pixel_size = 0.01
	_emote.text = "!"
	_emote.visible = false
	add_child(_emote)
	rod.visible = false
	bobber.visible = false
	_line.visible = false


func _toon(name: String, col: Color) -> Material:
	var m := StandardMaterial3D.new()
	m.resource_name = "M_Fishing_" + name
	m.albedo_color = col
	return ModelLib.convert_material(m, false)


func _build_rod() -> void:
	rod = Node3D.new()
	rod.name = "Rod"
	add_child(rod)
	var parts := [
		# [top r, bottom r, from y, to y, colour]
		[0.022, 0.026, -0.05, 0.3, Color("5b3b24")],   # cork / rattan grip
		[0.008, 0.017, 0.3, ROD_LEN, Color("c9a95e")], # bamboo
	]
	for p in parts:
		var mi := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = p[0]
		cm.bottom_radius = p[1]
		cm.height = p[3] - p[2]
		cm.radial_segments = 6
		cm.rings = 1
		mi.mesh = cm
		mi.position.y = (p[2] + p[3]) * 0.5
		mi.material_override = _toon("rod%d" % parts.find(p), p[4])
		rod.add_child(mi)
	var reel := MeshInstance3D.new()
	var rm := CylinderMesh.new()
	rm.top_radius = 0.045
	rm.bottom_radius = 0.045
	rm.height = 0.04
	rm.radial_segments = 10
	reel.mesh = rm
	reel.rotation.z = PI * 0.5
	reel.position = Vector3(0.05, 0.22, 0)
	reel.material_override = _toon("reel", Color("b8c0c4"))
	rod.add_child(reel)


func _build_bobber() -> void:
	bobber = Node3D.new()
	bobber.name = "Bobber"
	add_child(bobber)
	var lo := MeshInstance3D.new()
	var s := SphereMesh.new()
	s.radius = 0.09
	s.height = 0.14
	s.radial_segments = 10
	s.rings = 5
	lo.mesh = s
	lo.material_override = _toon("bob_w", Color("fbf6ea"))
	bobber.add_child(lo)
	var hi := MeshInstance3D.new()
	var s2 := SphereMesh.new()
	s2.radius = 0.085
	s2.height = 0.1
	s2.radial_segments = 10
	s2.rings = 4
	hi.mesh = s2
	hi.position.y = 0.05
	hi.material_override = _toon("bob_r", Color("d9402a"))
	bobber.add_child(hi)
	var stick := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.012
	cm.bottom_radius = 0.012
	cm.height = 0.14
	cm.radial_segments = 5
	stick.mesh = cm
	stick.position.y = 0.14
	stick.material_override = _toon("bob_r", Color("d9402a"))
	bobber.add_child(stick)
	# a soft ripple ring on the water
	var ring := MeshInstance3D.new()
	ring.name = "Ripple"
	var tm := TorusMesh.new()
	tm.inner_radius = 0.16
	tm.outer_radius = 0.2
	tm.rings = 24
	tm.ring_segments = 4
	ring.mesh = tm
	ring.scale = Vector3(1, 0.1, 1)
	var rmat := StandardMaterial3D.new()
	rmat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	rmat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	rmat.albedo_color = Color(1, 1, 1, 0.55)
	ring.material_override = rmat
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	bobber.add_child(ring)


func _build_bar() -> void:
	## compact timing bar (about 300 x 64 UI px) above the bottom HUD
	_bar = PanelContainer.new()
	_bar.name = "FishBar"
	var st: StyleBoxFlat = ui._box(ui.CREAM, 22, ui.LINE, 2, true)
	ui._margins(st, 14, 8, 14, 10)
	_bar.add_theme_stylebox_override("panel", st)
	_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 6)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bar.add_child(col)
	_bar_label = ui._label("Tarik saat di hijau!", 18, ui.BROWN, true)
	_bar_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(_bar_label)
	var track := Panel.new()
	track.custom_minimum_size = Vector2(280, 22)
	track.mouse_filter = Control.MOUSE_FILTER_IGNORE
	track.add_theme_stylebox_override("panel", ui._box(Color("e9dcc2"), 11, Color("d9c6a2"), 1))
	col.add_child(track)
	_bar_zone = Panel.new()
	_bar_zone.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bar_zone.add_theme_stylebox_override("panel", ui._box(ui.BAR_GREEN, 9))
	track.add_child(_bar_zone)
	_bar_sweet = Panel.new()
	_bar_sweet.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bar_sweet.add_theme_stylebox_override("panel", ui._box(ui.BAR_GOLD, 7))
	track.add_child(_bar_sweet)
	_bar_cursor = Panel.new()
	_bar_cursor.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bar_cursor.add_theme_stylebox_override("panel", ui._box(ui.INK, 4, ui.CREAM_LIGHT, 2))
	_bar_cursor.size = Vector2(10, 32)
	track.add_child(_bar_cursor)
	_bar.visible = false
	ui.root.add_child(_bar)


func _layout_bar() -> void:
	var vp: Vector2 = ui.root.get_viewport_rect().size
	_bar.size = _bar.get_combined_minimum_size()
	_bar.position = Vector2(roundf(vp.x * 0.5 - _bar.size.x * 0.5), roundf(vp.y * 0.58))
	var w := 280.0
	_bar_zone.position = Vector2((zone_c - zone_w * 0.5) * w, 2)
	_bar_zone.size = Vector2(zone_w * w, 18)
	_bar_sweet.position = Vector2((zone_c - zone_w * 0.14) * w, 4)
	_bar_sweet.size = Vector2(zone_w * 0.28 * w, 14)
	_bar_cursor.position = Vector2(cursor * w - 5.0, -5)


# ------------------------------------------------------------------ flow
func start(spot_pos: Vector3, water_kind: String) -> bool:
	if active:
		return false
	if int(GS.inv.get("pancing", 0)) <= 0:
		ui.toast("Kamu belum punya pancing. Beli di Koperasi Desa.", "bad")
		return false
	if not GS.use_energy(GS.ENERGY_COST["fish"]):
		return false
	if _bar == null:
		_build_bar()
	active = true
	water = water_kind
	spot = spot_pos
	var pl: Player = world.player
	pl.locked = true
	pl.touch_vec = Vector2.ZERO
	var d := spot - pl.global_position
	d.y = 0.0
	if d.length() > 0.1:
		pl.facing = d.normalized()
		pl.face_point(spot, 3.0)
	rod.visible = true
	_line.visible = false
	bobber.visible = false
	_rod_a = 55.0
	_set_phase("cast")
	Sfx.play("whoosh", 1.2, -4.0)
	# swing back, then forward: the bobber leaves at the forward swing
	var tw := create_tween()
	tw.tween_property(self, "_rod_a", -25.0, 0.28).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tw.tween_property(self, "_rod_a", 78.0, 0.16).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_callback(_launch_bobber)
	tw.tween_property(self, "_rod_a", 60.0, 0.35).set_trans(Tween.TRANS_SINE)
	return true


func _launch_bobber() -> void:
	if not active:
		return
	_bob_from = tip()
	bobber.visible = true
	_line.visible = true
	bobber.global_position = _bob_from
	var tw := create_tween()
	tw.tween_method(func(u: float):
		var p := _bob_from.lerp(spot, u)
		p.y += sin(u * PI) * 1.4
		bobber.global_position = p, 0.0, 1.0, 0.55)
	tw.tween_callback(func():
		if not active:
			return
		Sfx.play("pop", 0.7, -8.0)
		world.burst(spot + Vector3(0, 0.05, 0), Color("cfe8f0"), 10)
		_set_phase("wait")
		_wait = randf_range(0.35, 0.6) if fast else randf_range(1.8, 4.8)
		ui.set_prompt("Tunggu umpan dimakan...", true))


func press() -> void:
	## the action button while fishing
	if not active:
		return
	match phase:
		"cast":
			pass
		"wait":
			_finish("early", "Terlalu cepat! Umpannya kamu tarik sendiri.")
		"bite":
			fish_id = GS.roll_fish(water, GS.hour)
			var hard: float = float(GS.FISH[fish_id]["hard"])
			zone_w = lerpf(0.34, 0.13, hard)
			zone_c = randf_range(0.2 + zone_w * 0.5, 0.8 - zone_w * 0.5)
			_speed = lerpf(0.75, 1.7, hard)
			cursor = 0.0
			_dir = 1.0
			_emote.visible = false
			_set_phase("reel")
			_bar_label.text = "Tarik saat di hijau!" if hard < 0.8 else "Ikan besar! Tarik saat di hijau!"
			_bar.visible = true
			_layout_bar()
			Sfx.play("click", 0.8, -4.0)
			ui.set_prompt("Tarik!", true)
		"reel":
			var off := absf(cursor - zone_c)
			if off <= zone_w * 0.5:
				_catch(off <= zone_w * 0.14)
			else:
				_finish("missed", "Yah, ikannya lepas! Coba lagi.")


func cancel() -> void:
	if active:
		_finish("cancel", "")


func _set_phase(p: String) -> void:
	phase = p
	_t = 0.0


func _catch(perfect: bool) -> void:
	var id := fish_id
	var f: Dictionary = GS.FISH[id]
	GS.catch_fish(id)
	var rare := float(f["w"]) < 5.0
	Sfx.play("quest" if rare else "harvest")
	var pl: Player = world.player
	world.float_text(pl.global_position + Vector3(0, 0.4, 0), "+" + str(f["name"]), Color("2f6d2a") if not rare else Color("b8401f"))
	var msg := "Dapat %s! (laku %s di warung)" % [f["name"], GS.fmt_short(int(f["price"]))]
	if perfect:
		msg = "Tarikan sempurna! " + msg
	ui.toast(msg, "quest" if rare else "good")
	_show_catch(id)
	pl.anim.play_action("cheer", 1.0)
	_finish("caught:" + id, "")


func _show_catch(id: String) -> void:
	## the fish (its icon on a billboard) jumps out of the water up to the player
	var tex: Texture2D = ui.icon(id)
	if tex == null:
		return
	var s := Sprite3D.new()
	s.texture = tex
	s.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	s.pixel_size = 0.006
	s.no_depth_test = true
	s.shaded = false
	world.add_child(s)
	var from := bobber.global_position if bobber.visible else spot
	var to: Vector3 = world.player.global_position + Vector3(0, 1.9, 0)
	s.global_position = from
	var tw := s.create_tween()
	tw.tween_method(func(u: float):
		var p := from.lerp(to, u)
		p.y += sin(u * PI) * 1.2
		s.global_position = p, 0.0, 1.0, 0.5)
	tw.tween_interval(1.1)
	tw.tween_property(s, "modulate:a", 0.0, 0.35)
	tw.tween_callback(s.queue_free)


func _finish(result: String, msg: String) -> void:
	last_result = result
	if msg != "":
		ui.toast(msg, "bad" if result != "cancel" else "info")
		Sfx.play("bad", 1.0, -8.0)
	active = false
	phase = ""
	_emote.visible = false
	if _bar:
		_bar.visible = false
	bobber.visible = false
	_line.visible = false
	var pl: Player = world.player
	# the rod stays out a moment (and while cheering), then goes away
	get_tree().create_timer(0.9).timeout.connect(func():
		if not active:
			rod.visible = false)
	if world.state == "play" and not ui.is_blocking():
		pl.locked = false


# ------------------------------------------------------------------ per frame
func tip() -> Vector3:
	return rod.global_transform * Vector3(0, ROD_LEN, 0)


func _process(delta: float) -> void:
	if not rod.visible or world == null or world.player == null:
		return
	var pl: Player = world.player
	var yaw_b := Basis(Vector3.UP, atan2(pl.facing.x, pl.facing.z))
	if pl.model:
		yaw_b = pl.model.global_transform.basis.orthonormalized()
		yaw_b = Basis(Vector3.UP, yaw_b.get_euler().y)
	var hand := pl.global_position + yaw_b * Vector3(-0.2, 0.5, 0.18)
	rod.global_transform = Transform3D(yaw_b * Basis(Vector3.RIGHT, deg_to_rad(_rod_a)), hand)
	if not active:
		return
	_t += delta
	match phase:
		"wait":
			bobber.global_position = spot + Vector3(0, sin(_t * 2.6) * 0.025, 0)
			_wait -= delta
			if _moving_input():
				_finish("cancel", "")
				ui.toast("Pancing digulung.", "info")
				return
			if _wait <= 0.0:
				_set_phase("bite")
				_emote.visible = true
				_emote.scale = Vector3.ONE * 0.3
				create_tween().tween_property(_emote, "scale", Vector3.ONE, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
				Sfx.play("pop", 1.4, -2.0)
				world.burst(spot + Vector3(0, 0.05, 0), Color("cfe8f0"), 8)
				ui.set_prompt("Tarik sekarang!", true)
		"bite":
			bobber.global_position = spot + Vector3(0, -0.07 - absf(sin(_t * 18.0)) * 0.06, 0)
			_rod_a = 60.0 + sin(_t * 30.0) * 3.0
			if _t > BITE_WINDOW:
				_finish("escaped", "Ikannya kabur... kurang cepat!")
		"reel":
			bobber.global_position = spot + Vector3(sin(_t * 9.0) * 0.08, -0.04, cos(_t * 7.0) * 0.08)
			_rod_a = 45.0 + sin(_t * 14.0) * 4.0
			cursor += _dir * _speed * delta
			if cursor >= 1.0:
				cursor = 1.0
				_dir = -1.0
			elif cursor <= 0.0:
				cursor = 0.0
				_dir = 1.0
			_layout_bar()
			if _t > REEL_TIME:
				_finish("escaped", "Ikannya berhasil kabur!")
	if active:
		_emote.global_position = pl.global_position + Vector3(0, 1.75 + sin(_t * 8.0) * 0.04, 0)
		var ripple := bobber.get_node("Ripple") as Node3D
		var k := fmod(_t * 0.8, 1.0)
		ripple.scale = Vector3(1.0 + k * 1.6, 0.1, 1.0 + k * 1.6)
		(ripple as MeshInstance3D).material_override.albedo_color.a = 0.55 * (1.0 - k)
		ripple.global_position = Vector3(bobber.global_position.x, spot.y + 0.01, bobber.global_position.z)
	_draw_line()


func _moving_input() -> bool:
	var pl: Player = world.player
	return Input.get_vector("move_left", "move_right", "move_up", "move_down").length() > 0.5 or pl.touch_vec.length() > 0.5


func _draw_line() -> void:
	_line_mesh.clear_surfaces()
	if not _line.visible:
		return
	var a := tip()
	var b := bobber.global_position + Vector3(0, 0.2, 0)
	_line_mesh.surface_begin(Mesh.PRIMITIVE_LINE_STRIP)
	var sag := 0.35 if phase == "wait" else 0.08
	for i in 13:
		var u := i / 12.0
		var p := a.lerp(b, u) - Vector3(0, sag * 4.0 * u * (1.0 - u), 0)
		_line_mesh.surface_add_vertex(p)
	_line_mesh.surface_end()
