extends Node3D
## Game director: world environment, camera, post-process, the Pancawati hub,
## the room-by-room journey (Hutan Dandaka -> Muara Kalimas), rewards, death
## and victory.

const POST := preload("res://shaders/post.gdshader")
const CAM_OFFSET := Vector3(0, 13.8, 10.4)

## Journey plan: room number -> [kind, biome, title]
const PLAN := {
	1: ["combat", "dandaka"], 2: ["combat", "dandaka"], 3: ["combat", "dandaka"],
	4: ["combat", "dandaka"], 5: ["miniboss", "dandaka"], 6: ["rest", "dandaka"],
	7: ["combat", "muara"], 8: ["combat", "muara"], 9: ["boss", "muara"],
	10: ["combat", "samudra"], 11: ["combat", "samudra"], 12: ["rest", "samudra"],
	13: ["miniboss", "alengka"], 14: ["combat", "argasoka"], 15: ["boss", "alengka"],
}
const LAST_ROOM := 15
const STAGE_TITLE := {
	"dandaka": "Dandaka Forest", "muara": "Kalimas Estuary", "samudra": "The Southern Ocean",
	"argasoka": "Asoka Garden of Alengka", "alengka": "Alengka Palace",
}
## Painted stage cards: first time a stage is reached each journey.
const STAGE_CUT := {
	1: ["scene/dandaka", ["The forest of Dandaka, where Sinta was stolen.", "Ogres stir in the dark between the temple ruins..."]],
	10: ["scene/samudra", ["Beyond the estuary lies the endless southern ocean.", "An ancient sea turtle rises to carry the envoy of Rama."]],
	13: ["scene/argasoka", ["Alengka. Gold towers burn against the night.", "Somewhere in the Asoka garden, Dewi Sinta waits."]],
}

var player: Player
var cam: Camera3D
var room: Arena
var ui: UI
var sun: DirectionalLight3D
var env: WorldEnvironment
var post_mat: ShaderMaterial
var _shake := 0.0
var _hitstop_until := 0
var _cam_target := Vector3.ZERO
var busy := false          # menus / dialogue / transitions freeze combat
var area := "title"
var _hurt := 0.0
var _flash_a := 0.0
var cam_override := false    # autotest overview shots
var _flash_col := Color.WHITE
var _flash_decay := 1.0
var _zoom := 0.0            # 0 = normal, 1 = punched in
var _focus: Node3D = null   # boss intro: camera looks at this instead of Hanoman
var _focus_until := 0


func _ready() -> void:
	G.set("main", self)
	_setup_world()
	ui = UI.new()
	add_child(ui)
	player = Player.new()
	_build_title_scene()
	ui.title_screen(func(): go_hub(true))
	Au.music("mus_title")
	var web_autotest := OS.has_feature("web") and str(JavaScriptBridge.eval("location.search", true)).contains("autotest")
	if OS.get_cmdline_user_args().has("--autotest") or web_autotest:
		var at = load("res://scripts/autotest.gd").new()
		add_child(at)


func _setup_world() -> void:
	env = WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.03, 0.04, 0.06)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.3, 0.34, 0.58)
	e.ambient_light_energy = 0.32
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_exposure = 0.95
	e.glow_enabled = true
	e.glow_intensity = 0.55
	e.glow_bloom = 0.0
	e.glow_hdr_threshold = 1.1
	e.fog_enabled = false
	env.environment = e
	add_child(env)
	G.settings_changed.connect(_apply_quality)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-58, -35, 0)
	sun.light_color = Color(0.66, 0.76, 1.0)
	sun.light_energy = 0.8
	sun.shadow_enabled = true
	sun.shadow_opacity = 0.85
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	sun.directional_shadow_max_distance = 45.0
	add_child(sun)
	_apply_quality()
	cam = Camera3D.new()
	cam.fov = 34.0
	cam.near = 1.0
	cam.far = 120.0
	add_child(cam)
	cam.position = CAM_OFFSET
	cam.look_at(Vector3.ZERO)
	var layer := CanvasLayer.new()
	layer.layer = 0
	add_child(layer)
	var rect := ColorRect.new()
	rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	post_mat = ShaderMaterial.new()
	post_mat.shader = POST
	rect.material = post_mat
	layer.add_child(rect)


## "Rendah" graphics for weak phones: no glow, no sun shadows.
func _apply_quality() -> void:
	var hq := G.high_quality()
	env.environment.glow_enabled = hq
	if sun:
		sun.shadow_enabled = hq


var _title_scene: Node3D
var _title_t := 0.0


## Title backdrop: the Hutan Dandaka diorama built in Higgsfield 3D Jutsu (Blender),
## slowly orbited by the camera.
func _build_title_scene() -> void:
	# the title is a painted screen now; keep an empty effect layer behind it
	_title_scene = Node3D.new()
	add_child(_title_scene)
	Fx.layer = _title_scene


func _title_camera(delta: float) -> void:
	_title_t += delta * 0.06
	var r := 24.0
	cam.global_position = Vector3(sin(_title_t) * r, 13.0, cos(_title_t) * r)
	cam.look_at(Vector3(0, 1.5, 0))


func _process(delta: float) -> void:
	if area == "title" and _title_scene:
		_title_camera(delta)
		return
	if _title_scene:
		_title_scene.queue_free()
		_title_scene = null
	if player and player.is_inside_tree():
		var p := player.global_position
		if room:
			var b: Rect2 = room.bounds if room.bounds.has_area() else Rect2(-room.half, room.half * 2.0)
			var lo := b.position + Vector2(6.0 - 1.5, 3.4 - 1.0)
			var hi := b.end - Vector2(6.0 - 1.5, 3.4 - 1.0)
			var mid := b.get_center()
			p.x = clamp(p.x, lo.x, hi.x) if lo.x < hi.x else mid.x
			p.z = clamp(p.z, lo.y - 1.0, hi.y + 0.5) if lo.y < hi.y else mid.y
		if _focus and is_instance_valid(_focus) and Time.get_ticks_msec() < _focus_until:
			p = _focus.global_position
		else:
			_focus = null
		_cam_target = _cam_target.lerp(p, clamp(delta * (3.0 if _focus else 5.0), 0.0, 1.0))
	var sh := Vector3.ZERO
	if _shake > 0.0:
		_shake = max(0.0, _shake - delta * 1.8)
		var a := _shake * _shake * 0.9
		sh = Vector3(randf_range(-a, a), randf_range(-a, a), randf_range(-a, a))
	_zoom = move_toward(_zoom, 0.55 if _focus else 0.0, delta * (1.5 if _focus else 2.5))
	if not cam_override:
		cam.global_position = _cam_target + CAM_OFFSET * (1.0 - _zoom * 0.45) + sh
		cam.look_at(_cam_target + sh * 0.5 + Vector3(0, 0.6, 0))
	_hurt = move_toward(_hurt, 0.0, delta * 1.5)
	if _hitstop_until > 0 and Time.get_ticks_msec() >= _hitstop_until:
		_hitstop_until = 0
		Engine.time_scale = 1.0
	if G.in_run and player and not player.dead and float(G.run.hp) < float(G.run.max_hp) * 0.3:
		_hurt = max(_hurt, 0.35 + 0.15 * sin(Time.get_ticks_msec() * 0.006))
	post_mat.set_shader_parameter("hurt", _hurt)
	_flash_a = max(0.0, _flash_a - _flash_decay * delta)
	post_mat.set_shader_parameter("flash", Color(_flash_col.r, _flash_col.g, _flash_col.b, _flash_a))


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause") and area != "title" and not busy:
		ui.pause_menu()


# --- helpers used by actors -------------------------------------------------------

func enemies() -> Array:
	var out := []
	if room == null:
		return out
	for c in room.actors.get_children():
		if c is Enemy and not c.dead and not (c is Boss and (c as Boss).submerged):
			out.append(c)
	return out


func combat_enabled() -> bool:
	return G.in_run and not busy and room != null


func room_contains(p: Vector3, margin := 0.0) -> bool:
	if room == null:
		return false
	return room.sd(Vector2(p.x, p.z)) < margin


func clamp_to_room(p: Vector3, margin := 1.0) -> Vector3:
	if room == null:
		return p
	var q := room.push_inside(Vector3(p.x, 0, p.z), margin)
	return Vector3(q.x, 0, q.z)


func mouse_ground() -> Vector3:
	var mp := get_viewport().get_mouse_position()
	var from := cam.project_ray_origin(mp)
	var dir := cam.project_ray_normal(mp)
	if abs(dir.y) < 0.001:
		return player.global_position
	var t := -from.y / dir.y
	return from + dir * t


func spawn_actor(a: Actor, pos: Vector3) -> void:
	room.actors.add_child(a)
	a.global_position = Vector3(pos.x, 0, pos.z)
	var to := player.global_position - a.global_position
	a.snap_face(to)


func shake(a: float) -> void:
	_shake = max(_shake, a)


func hitstop(t: float) -> void:
	Engine.time_scale = 0.08
	_hitstop_until = Time.get_ticks_msec() + int(t * 1000.0)


## Dramatic slow motion (last kill of a room), in real seconds.
func slowmo(scale: float, real_time: float) -> void:
	Engine.time_scale = scale
	_hitstop_until = Time.get_ticks_msec() + int(real_time * 1000.0)
	_zoom = 0.35


## Boss entrance: the camera swings to the boss and a title card slams in.
func boss_intro(boss: Node3D, title: String, sub: String) -> void:
	_focus = boss
	_focus_until = Time.get_ticks_msec() + 2200
	ui.boss_card(title, sub)
	flash(Color(1, 0.9, 0.75), 0.25, 0.4)
	shake(0.35)
	Au.sfx("sfx_bell", -2.0)
	Au.sfx("sfx_boss_roar", -1.0)


func hurt_flash() -> void:
	_hurt = 1.0


## Brief full-screen colour flash (laser, slams, crits, boss moments).
func flash(color: Color, strength := 0.2, time := 0.18) -> void:
	if _flash_a > strength:
		return
	_flash_col = color
	_flash_a = strength
	_flash_decay = strength / max(time, 0.01)


# --- areas ------------------------------------------------------------------------

func _clear_area() -> void:
	Engine.time_scale = 1.0
	if player.get_parent():
		player.get_parent().remove_child(player)
	if room:
		room.queue_free()
		room = null
	for n in get_tree().get_nodes_in_group("interactable"):
		n.remove_from_group("interactable")
	ui.set_bosses([])
	ui.show_prompt("")


func go_hub(first := false) -> void:
	busy = true
	ui.fade(true, func():
		_clear_area()
		area = "hub"
		G.in_run = false
		room = Hub.build(self)
		add_child(room)
		room.build()
		Hub.populate(self, room)
		Fx.layer = room.fx_layer
		room.actors.add_child(player)
		player.reset_for_run()
		player.global_position = room.player_start()
		player.snap_face(Vector3(0, 0, -1))
		_cam_target = player.global_position
		ui.hud_visible(false)
		Au.music("mus_hub")
		Au.ambience("amb_forest")
		ui.fade(false, func():
			busy = false
			ui.area_title("Pancawati Hermitage", "King Rama's Camp")
			if not G.seen("intro"):
				Hub.intro(self)))


func start_run() -> void:
	G.new_run()
	player.reset_for_run()
	var god := Boons.random_god()
	enter_room({"type": "boon", "god": god})


func enter_room(reward: Dictionary) -> void:
	busy = true
	ui.fade(true, func():
		_clear_area()
		G.run.room = int(G.run.room) + 1
		var n: int = G.run.room
		G.save_run(reward)
		var spec: Array = PLAN.get(n, PLAN[LAST_ROOM])
		room = Arena.new()
		room.kind = spec[0]
		room.biome = spec[1]
		room.depth = n
		room.reward = reward
		room.plan_layout()
		room.waves = _waves_for(n, room.chambers.size())
		room.exits = _exits_for(n)
		add_child(room)
		room.build()
		room.build_exits()
		room.exit_chosen.connect(func(rw): enter_room(rw))
		Fx.layer = room.fx_layer
		room.actors.add_child(player)
		player.global_position = room.player_start()
		player.snap_face(Vector3(0, 0, -1))
		player.velocity = Vector3.ZERO
		player.knock = Vector3.ZERO
		_cam_target = player.global_position
		ui.hud_visible(true)
		if room.kind == "rest":
			_populate_rest(room)
		var mus := "mus_dandaka" if room.biome == "dandaka" else ("mus_muara" if room.biome in Arena.WATERY else "mus_miniboss")
		if room.kind == "boss":
			mus = "mus_boss"
		elif room.kind == "miniboss":
			mus = "mus_miniboss"
		if room.kind != "rest":
			Au.music(mus)
		Au.ambience("amb_river" if room.biome in Arena.WATERY else "amb_forest")
		if STAGE_CUT.has(n) and Hf.textures.has(STAGE_CUT[n][0]):
			ui.cutscene(STAGE_CUT[n][0], STAGE_CUT[n][1], func(): _room_intro(n))
			return
		_room_intro(n))


func _room_intro(n: int) -> void:
	ui.fade(false, func():
		busy = false
		var title: String = STAGE_TITLE.get(room.biome, "Alengka")
		var sub := "Chamber %d" % n
		if room.kind == "miniboss":
			sub = "Lair of Kijang Kencana" if room.biome != "alengka" else "Kumbakarna's Hall"
		elif room.kind == "boss":
			sub = "Domain of Sura and Baya" if room.biome != "alengka" else "Indrajit's Throne Court"
		elif room.kind == "rest":
			sub = "Divine Market & Sacred Spring"
		ui.area_title(title, sub)
		if room.biome == "alengka" and room.kind != "rest":
			_alengka_intro()
			return
		if room.kind == "boss" and not G.seen("boss_intro"):
			_boss_intro()
		elif room.kind == "miniboss" and not G.seen("kijang_intro"):
			G.mark_seen("kijang_intro")
			busy = true
			ui.dialog([
				["hanoman", "A golden deer... shimmering, just like in Dewi Sinta's tale."],
				["kijang", "Come here, little monkey. Catch me if you can. Hee hee hee..."],
				["hanoman", "That's no deer's voice. You're Kala Marica, Rahwana's servant!"],
			], func():
				busy = false
				room.start())
			return
		room.start())


func _alengka_intro() -> void:
	var key := "kumba_intro" if room.kind == "miniboss" else "indrajit_intro"
	if G.seen(key):
		room.start()
		return
	G.mark_seen(key)
	busy = true
	var lines := [
		["kumbakarna", "Hrrmmm... who wakes me? I was dreaming of rice mountains..."],
		["hanoman", "Kumbakarna! I have no quarrel with you. Let me pass to Dewi Sinta."],
		["kumbakarna", "My brother is wrong to keep her, little monkey. But this is MY land. I will defend it!"],
	] if room.kind == "miniboss" else [
		["indrajit", "So the monkey crossed the ocean. My uncle sleeps and my father hides behind his walls."],
		["hanoman", "Indrajit. Tell Rahwana that Rama is coming for Sinta."],
		["indrajit", "You will tell him nothing. My Nagapasa has bound gods. It will bind a monkey!"],
	]
	ui.dialog(lines, func():
		busy = false
		room.start())


func _boss_intro() -> void:
	G.mark_seen("boss_intro")
	busy = true
	ui.dialog([
		["sura", "Who dares set foot in this estuary? The sea belongs to Sura!"],
		["baya", "The sea is yours, the land is mine, that was our pact! But this estuary... is MINE, Sura!"],
		["hanoman", "I am Hanoman, envoy of King Rama. Let me cross to Alengka."],
		["sura", "Rahwana pays us to drown anyone who passes."],
		["baya", "Just this once, Sura, we fight on the same side. Tear that ape apart!"],
	], func():
		busy = false
		room.start())


## Waves for each chamber of room `n`: the three chambers of a stage get
## progressively tougher mixes drawn from that stage's raksasa.
func _waves_for(n: int, chambers_n: int) -> Array:
	var pools := {
		1: ["wil", "wil", "wil", "banaspati"],
		2: ["wil", "wil", "cakil", "banaspati"],
		3: ["wil", "cakil", "banaspati", "buto_ijo"],
		4: ["cakil", "banaspati", "wil", "buto_ijo"],
		7: ["yuyu", "wil", "banaspati", "cakil"],
		8: ["yuyu", "cakil", "banaspati", "wil", "pemanah", "buto_ijo"],
		10: ["yuyu", "pemanah", "banaspati", "tameng"],
		11: ["pemanah", "yuyu", "dukun", "banaspati", "tameng"],
		14: ["pemanah", "dukun", "cakil", "tameng", "buto_ijo"],
	}
	var pool: Array = pools.get(n, ["wil", "wil"])
	var out := []
	for k in chambers_n:
		var ch_waves := []
		var count := 1 if k == 0 and n <= 2 else 2
		for w in count:
			var size := 3 + (1 if n >= 3 else 0) + (1 if k == chambers_n - 1 else 0)
			var list := []
			for i in size:
				list.append(pool[randi() % pool.size()])
			# every chamber after the first carries one of the stage's heavy hitters
			if k > 0 and w == count - 1:
				list[0] = pool[pool.size() - 1]
			list.shuffle()
			ch_waves.append(list)
		out.append(ch_waves)
	return out


func _exits_for(n: int) -> Array:
	match n:
		4:
			return [{"type": "miniboss"}]
		5:
			return [{"type": "rest"}]
		8:
			return [{"type": "boss"}]
		11:
			return [{"type": "rest"}]
		12:
			return [{"type": "miniboss"}]
		14:
			return [{"type": "boss"}]
		LAST_ROOM:
			return []
	var out := []
	var count := 2
	var used_god := ""
	for i in count:
		var r := randf()
		var rw := {}
		var has_boons: bool = not G.run.boons.is_empty()
		if r < 0.5:
			var god := Boons.random_god(used_god)
			used_god = god
			rw = {"type": "boon", "god": god}
		elif r < 0.66:
			rw = {"type": "kepeng"}
		elif r < 0.8:
			rw = {"type": "tirta"}
		elif r < 0.9 or not has_boons:
			rw = {"type": "bunga"}
		else:
			rw = {"type": "palu"}
		if i == 1 and rw.type == out[0].type and rw.type != "boon":
			rw = {"type": "boon", "god": Boons.random_god(used_god)}
		out.append(rw)
	return out


# --- rewards --------------------------------------------------------------------

func on_room_cleared(r: Arena) -> void:
	if r.kind == "boss" and r.biome == "alengka":
		_victory()
		return
	var rw: Dictionary = r.reward
	if r.kind == "boss":
		# Sura and Baya fall: the legend of Surabaya, then onward across the ocean
		G.meta.boss_kills = int(G.meta.boss_kills) + 1
		G.add_bunga(6)
		G.run.bunga_gained = int(G.run.bunga_gained) + 6
		busy = true
		cinematic_kill("Sura and Baya are defeated!", func():
			ui.dialog([
				["baya", "Sura... we were beaten by a monkey..."],
				["sura", "Shut up, Baya! This is all your fault. This estuary is still mine!"],
				["hanoman", "Even in defeat, you two still squabble. People will remember this place by both your names: Sura and Baya."],
				["dewa_baruna", "Go, envoy. The ocean opens a way for you. Alengka awaits on the far shore."],
			], func():
				busy = false
				_spawn_reward(r, {"type": "boon", "god": "baruna"})
				r.open_gates()))
		return
	if r.kind == "miniboss":
		G.meta.boss_kills = int(G.meta.boss_kills) + 1
		cinematic_kill(("Kumbakarna" if r.biome == "alengka" else "Kijang Kencana") + " falls!", func(): pass)
		G.add_bunga(5)
		G.run.bunga_gained = int(G.run.bunga_gained) + 5
		G.say("+5 Wijayakusuma Blossoms", Color(1, 0.95, 0.85))
		rw = {"type": "boon", "god": Boons.random_god()}
	if r.kind == "rest":
		r.open_gates()
		return
	_spawn_reward(r, rw)
	r.open_gates()


func _spawn_reward(r: Arena, rw: Dictionary) -> void:
	var pos := clamp_to_room(player.global_position.lerp(Vector3.ZERO, 0.6), 2.0)
	var t: String = rw.get("type", "kepeng")
	var node: Node3D
	match t:
		"boon":
			node = Interactable.make("Accept boon of " + G.GOD_NAMES[rw.god], func(i: Interactable):
				i.active = false
				_open_boon(rw.god, func(): i.queue_free()))
			var m := Art.model("orb_dewa")
			node.add_child(m)
			var core := Fx.orb(G.GOD_COLORS[rw.god], 0.28)
			core.position.y = 1.3
			node.add_child(core)
			var l := OmniLight3D.new()
			l.light_color = G.GOD_COLORS[rw.god]
			l.light_energy = 2.0
			l.omni_range = 5.0
			l.position.y = 1.4
			node.add_child(l)
			Au.sfx("sfx_boon_appear", -3.0)
		"palu":
			node = Interactable.make("Take the Palu Heirloom", func(i: Interactable):
				i.active = false
				_open_palu(func(): i.queue_free()))
			var s := Sprite3D.new()
			s.texture = load("res://assets/icons/rw_palu.png")
			s.pixel_size = 0.012
			s.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			s.position.y = 1.2
			node.add_child(s)
		_:
			node = Pickup.make(t)
	r.add_child(node)
	node.global_position = pos
	var tw := node.create_tween().set_loops()
	tw.tween_property(node, "position:y", 0.25, 0.8).set_trans(Tween.TRANS_SINE)
	tw.tween_property(node, "position:y", 0.0, 0.8).set_trans(Tween.TRANS_SINE)


func _open_boon(god: String, done: Callable) -> void:
	busy = true
	Au.duck(true)
	var offers := Boons.offers(god)
	if offers.is_empty():
		G.add_kepeng(80)
		G.say("You already hold every boon of %s. +80 Kepeng" % G.GOD_NAMES[god])
		busy = false
		Au.duck(false)
		done.call()
		return
	ui.boon_menu(god, offers, func(choice: Dictionary):
		Boons.take(choice.id, choice.rar)
		Au.sfx("sfx_boon_pick", -2.0)
		Fx.burst(player.global_position + Vector3(0, 1, 0), G.GOD_COLORS[god], 30, 6.0, 0.25, 0.7)
		busy = false
		Au.duck(false)
		done.call())


func _open_palu(done: Callable) -> void:
	var owned: Array = G.run.boons.keys()
	owned.shuffle()
	owned = owned.slice(0, 3)
	if owned.is_empty():
		G.add_kepeng(60)
		done.call()
		return
	busy = true
	var opts := []
	for id in owned:
		var b: Dictionary = G.run.boons[id]
		opts.append({"title": "%s  (Lv %d → %d)" % [Boons.ALL[id].name, b.lvl, int(b.lvl) + 1],
			"desc": Boons.desc(id, b.rar, int(b.lvl) + 1), "icon": "res://assets/icons/god_%s.png" % Boons.god_of(id), "id": id})
	ui.choice_menu("Palu Heirloom", "Choose one boon to raise its level.", opts, func(o: Dictionary):
		Boons.level_up(o.id)
		Au.sfx("sfx_boon_pick", -2.0)
		busy = false
		done.call())


func _populate_rest(r: Arena) -> void:
	Au.music("mus_hub")
	# Sendang: healing spring
	var spring := Interactable.make("Drink from the Sacred Spring (heal 40%)", func(i: Interactable):
		i.active = false
		G.heal(float(G.run.max_hp) * 0.4)
		Au.sfx("sfx_pickup_heal")
		Fx.burst(player.global_position + Vector3(0, 1, 0), Color(0.5, 0.9, 1.0), 24, 4.0, 0.2, 0.6)
		G.say("The spring water revives Hanoman."))
	spring.add_child(Art.model("sumur"))
	r.add_child(spring)
	spring.position = Vector3(-5.0, 0, 1.0)
	# Pasar Sang Hyang: three offerings on stone altars
	var goods := [
		{"t": "boon", "god": Boons.random_god(), "price": 130},
		{"t": "tirta", "price": 55},
		{"t": "palu", "price": 110} if not G.run.boons.is_empty() else {"t": "bunga", "price": 70},
	]
	for k in goods.size():
		var g: Dictionary = goods[k]
		var label := ""
		match g.t:
			"boon":
				label = "Boon of " + G.GOD_NAMES[g.god]
			"tirta":
				label = "Tirta Amerta (+25 health)"
			"palu":
				label = "Palu Heirloom"
			"bunga":
				label = "3 Wijayakusuma Blossoms"
		var it := Interactable.make("Buy %s — %d Kepeng" % [label, g.price], func(i: Interactable): _buy(i, g))
		it.add_child(Art.model("altar_dewa"))
		var s := Sprite3D.new()
		s.texture = load("res://assets/icons/god_%s.png" % g.god if g.t == "boon" else Arena.REWARD_ICON[g.t])
		s.pixel_size = 0.008
		s.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		s.position.y = 1.7
		it.add_child(s)
		it.set_meta("icon", s)
		var price := Label3D.new()
		price.text = "%d" % g.price
		price.font = preload("res://assets/fonts/Cinzel.ttf")
		price.font_size = 36
		price.outline_size = 10
		price.modulate = Color(1, 0.85, 0.4)
		price.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		price.pixel_size = 0.008
		price.position.y = 2.4
		it.add_child(price)
		r.add_child(it)
		it.position = Vector3(1.5 + k * 2.6, 0, -1.5)


func _buy(i: Interactable, g: Dictionary) -> void:
	if int(G.run.kepeng) < int(g.price):
		G.say("Not enough Kepeng.", Color(1, 0.5, 0.4))
		Au.sfx("sfx_ui_back")
		return
	G.add_kepeng(-int(g.price))
	Au.sfx("sfx_pickup_coin")
	i.active = false
	i.get_meta("icon").queue_free()
	match g.t:
		"boon":
			_open_boon(g.god, func(): pass)
		"tirta":
			G.heal(25)
		"palu":
			_open_palu(func(): pass)
		"bunga":
			G.add_bunga(3)
			G.run.bunga_gained = int(G.run.bunga_gained) + 3


# --- death & victory -----------------------------------------------------------

func on_player_death() -> void:
	busy = true
	G.end_run(false)
	Au.music("")
	Au.sting("stg_death")
	Engine.time_scale = 0.4
	get_tree().create_timer(0.8, true, false, true).timeout.connect(func():
		Engine.time_scale = 1.0
		ui.death_screen(func(): go_hub()))


## Boss down: letterbox, slow motion on the fallen foe, a caption.
func cinematic_kill(caption: String, done: Callable) -> void:
	slowmo(0.2, 1.2)
	_zoom = 0.6
	ui.letterbox(true)
	ui.phase_banner(caption)
	flash(Color(1, 0.95, 0.85), 0.35, 0.6)
	get_tree().create_timer(2.2, true, false, true).timeout.connect(func():
		ui.letterbox(false)
		done.call())


## Continue a saved journey from the title screen.
func resume_run() -> void:
	var rw := G.load_run()
	if rw.is_empty():
		go_hub(true)
		return
	area = "run"
	player.reset_for_run()
	enter_room(rw)


func _victory() -> void:
	busy = true
	G.meta.boss_kills = int(G.meta.boss_kills) + 1
	G.add_bunga(10)
	G.run.bunga_gained = int(G.run.bunga_gained) + 10
	G.end_run(true)
	player.bark("vo_victory", true)
	Au.music("")
	Au.sting("stg_victory")
	player.rig.play("victory", 2.5)
	cinematic_kill("Indrajit retreats into the smoke!", func(): pass)
	get_tree().create_timer(2.6).timeout.connect(func():
		ui.dialog([
			["indrajit", "This is not over, monkey... my father's army is endless..."],
			["hanoman", "Then let him count his soldiers. Rama is coming."],
			["hanoman", "(In the Asoka garden, a woman in white looks up as a white monkey drops from the trees.)"],
			["hanoman", "Dewi Sinta. I am Hanoman, envoy of King Rama. He sends you his ring... and his promise."],
			["rama", "(Far away, at Pancawati, Rama feels the wind change. His envoy has found her.)"],
		], func():
			ui.victory_screen(func(): go_hub())))
