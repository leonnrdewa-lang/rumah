extends Node
## Developer harness: `godot --path game -- --autotest=<scenario> --shots=<dir>`
## Drives the game without input and saves screenshots, for automated checks.

var world: Node
var scenario := "basic"
var shots_dir := "/tmp"
var _i := 0
var _tune := {}


func _process(_delta: float) -> void:
	# "tune" scenario: scale the day light after world.gd set it for this frame
	if _tune.is_empty():
		return
	world.sun.light_energy *= float(_tune.get("sun", 1.0))
	world.env.ambient_light_energy *= float(_tune.get("amb", 1.0))
	if _tune.has("amb_col"):
		world.env.ambient_light_color = Color(_tune["amb_col"])
	if _tune.has("sun_col"):
		world.sun.light_color = Color(_tune["sun_col"])
	if _tune.has("opacity"):
		world.sun.shadow_opacity = float(_tune["opacity"])


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--autotest="):
			scenario = a.get_slice("=", 1)
		elif a.begins_with("--shots="):
			shots_dir = a.get_slice("=", 1)
	await get_tree().process_frame
	await _run()
	get_tree().quit()


func shot(name: String, frames := 20) -> void:
	for i in frames:
		await get_tree().process_frame
	var img := get_viewport().get_texture().get_image()
	img.save_png("%s/%02d_%s.png" % [shots_dir, _i, name])
	_i += 1
	print("[shot] ", name)


const MASK_SHADER := """shader_type spatial;
render_mode unshaded, cull_disabled;
uniform sampler2D data_tex : filter_linear, repeat_disable;
uniform float world_size = 200.0;
varying vec3 wpos;
void vertex() { wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	vec4 d = texture(data_tex, (wpos.xz + world_size * 0.5) / world_size);
	ALBEDO = max(d.b, d.g) > 0.5 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
}
"""


const KEY_SHADER := """shader_type spatial;
render_mode unshaded, cull_disabled;
uniform vec3 key : source_color = vec3(1.0, 0.0, 1.0);
uniform sampler2D albedo_tex : hint_default_white;
uniform float cut = 0.0;
void fragment() {
	if (cut > 0.5 && texture(albedo_tex, UV).a < 0.45) { discard; }
	ALBEDO = key;
}
"""


func _key_material(src: Material, col: Color) -> ShaderMaterial:
	## unshaded key colour that keeps the source's alpha-card cut-out
	var m := ShaderMaterial.new()
	m.shader = Shader.new()
	m.shader.code = KEY_SHADER
	m.set_shader_parameter("key", col)
	if src is ShaderMaterial and src.get_shader_parameter("albedo_tex") != null:
		m.set_shader_parameter("albedo_tex", src.get_shader_parameter("albedo_tex"))
		m.set_shader_parameter("cut", 1.0 if str(src.shader.resource_path).contains("cutout") else 0.0)
	return m


func _mask_shot(name: String, bare: bool) -> void:
	## Terrain in key colours (green = land, red = road / sand); the parcels' palm fronds
	## magenta, their trunks and fruit blue; the piringan discs count as bare land
	## (green); with `bare` the undergrowth and parcel gardens are hidden too.
	var env: Environment = world.env
	var glow: bool = env.glow_enabled
	env.glow_enabled = false
	env.adjustment_enabled = false
	var key := ShaderMaterial.new()
	key.shader = Shader.new()
	key.shader.code = MASK_SHADER
	key.set_shader_parameter("data_tex", world.DATA_TEX)
	var terrain: Array = []
	for mi in ModelLib.find_meshes(world):
		if mi.material_override == world.terrain_mat:
			terrain.append(mi)
			mi.material_override = key
	var keyed: Array = []   # [GeometryInstance3D, surface or -1]
	for k in world.tile_views:
		for mi in ModelLib.find_meshes(world.tile_views[k]):
			for i in mi.mesh.get_surface_count():
				var sm: Material = mi.mesh.surface_get_material(i)
				var frond := sm != null and sm.resource_name.findn("Frond") >= 0
				mi.set_surface_override_material(i, _key_material(sm, Color(1, 0, 1) if frond else Color(0, 0, 1)))
				keyed.append([mi, i])
	var hidden: Array = []
	for n in world.get_children():
		if str(n.name).begins_with("ParcelDecor"):
			for c in n.get_children():
				var mmi := c as MultiMeshInstance3D
				if mmi and mmi.multimesh.mesh.get_surface_count() > 0:
					var sm: Material = mmi.multimesh.mesh.surface_get_material(0)
					if sm and sm.resource_name.findn("Piringan") >= 0:
						keyed.append([mmi, -1, mmi.material_override])
						mmi.material_override = _key_material(sm, Color(0, 1, 0))
			if bare:
				hidden.append(n)
	if bare:
		hidden.append(world.undergrowth)
	for n in hidden:
		n.visible = false
	await shot(name, 3)
	for mi in terrain:
		mi.material_override = world.terrain_mat
	for kd in keyed:
		if kd[1] < 0:
			kd[0].material_override = kd[2]
		else:
			kd[0].set_surface_override_material(kd[1], null)
	for n in hidden:
		n.visible = true
	env.glow_enabled = glow
	env.adjustment_enabled = true


func wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func press(key: Key) -> void:
	var ev := InputEventKey.new()
	ev.keycode = key
	ev.physical_keycode = key
	ev.pressed = true
	Input.parse_input_event(ev)
	await get_tree().process_frame
	var up := ev.duplicate()
	up.pressed = false
	Input.parse_input_event(up)
	await get_tree().process_frame
	await get_tree().process_frame


func tp(x: float, z: float, face := Vector3(0, 0, 1)) -> void:
	world.player.global_position = Vector3(x, world.height_at(x, z), z)
	world.player.facing = face
	world.cam_rig.global_position = world.player.global_position


func _run() -> void:
	match scenario:
		"anim":
			# character animation checks (anim track): scripts/actors/anim_check.gd
			await AnimCheck.run(self)
		"basic":
			await shot("title", 60)
			world.start_game(false)
			await shot("intro_dialog", 40)
			world.ui.close()
			await shot("start", 30)
			tp(-17, 30, Vector3(0, 0, -1))
			await shot("plot", 30)
			# harvest the 3 ripe palms
			for idx in [0, 1, 2]:
				world._tile_action(0, idx)
			await shot("harvested", 10)
			print("tbs=", GS.inv["tbs"], " energy=", GS.energy, " quest=", GS.quest_index)
			tp(-4, 4)
			await shot("village", 30)
			tp(48, 2, Vector3(0, 0, -1))
			await shot("pabrik", 30)
			world.deals.open_pabrik()
			await shot("pabrik_menu", 10)
			world.deals._sell_tbs()
			print("money=", GS.money, " quest=", GS.quest_index)
			world.ui.close()
			tp(-27, -3)
			world.deals.talk("ibu")
			await shot("talk", 30)
			world.ui.close()
			GS.hour = 20.5
			tp(8, 8)
			await shot("night", 40)
			GS.sleep()
			await shot("morning", 20)
		"music":
			await _music_check()
		"voice":
			await _voice_check()
		"ambience":
			await _ambience_check()
		"logic":
			world.start_game(false)
			world.ui.close()
			await _features_logic()
			var d: Node = world.deals
			GS.money = 60000000
			GS.inv["surat"] = 3
			GS.upgrades["preman"] = 2
			# every land route
			d._buy_fair("kakek")
			world.ui.close()
			d.rng.seed = 1
			d._lowball("ibu")
			world.ui.close()
			d._fraud("nenek")
			world.ui.close()
			d._evict("pemuda")
			world.ui.close()
			d._bribe_kades("kades", 5500000)
			world.ui.close()
			d._sign_franchise("petani")
			world.ui.close()
			# map v3: a hamlet villager's land deal, the landless villagers and a passer-by
			d.talk("somad")
			world.ui.close()
			d.land_menu("rt")
			world.ui.close()
			for eid in d.EXTRAS:
				d.talk_extra(eid)
				world.ui.close()
			d.talk_walker(0)
			world.ui.close()
			print("map v3: parcels=%d tiles/parcel=%d villagers=%d extras=%d walkers=%d bridges=%d houses=%d" % [GS.parcels.size(),
				GS.tile_count(), GS.VILLAGERS.size(), d.EXTRAS.size(), world.walkers.size(), world.bridges.size(),
				world.building_nodes.keys().filter(func(k): return String(k).begins_with("rumah")).size()])
			print("owners: ", GS.parcels.map(func(p): return "%s%s" % [p["owner"], "*" if p["plasma"] else ""]))
			print("controlled=", GS.controlled_parcels(), " heat=", GS.heat, " rep=", GS.rep, " stats=", GS.stats)
			# work the land for a few days
			GS.add_item("bibit", 60)
			GS.add_item("pupuk", 20)
			for day in 8:
				for p in GS.parcels:
					if p["owner"] != "player":
						continue
					for i in GS.tile_count():
						GS.energy = 100
						world._tile_action(p["id"], i)
				if int(GS.inv["tbs"]) > 0:
					d._sell_tbs()
					world.ui.close()
				GS.sleep()
				world.ui.close()
				while not GS.pending_events.is_empty():
					GS.pending_events.pop_front()
			print("day=", GS.day, " palms=", GS.palm_count(), " money=", GS.money, " quest=", GS.quest_index, " ", GS.current_quest())
			# oil
			GS.upgrades["mesin"] = true
			GS.add_item("tbs", 3)
			d._process_oil(3)
			world.ui.close()
			for vid in GS.villagers:
				d._sell_oil(vid)
				world.ui.close()
			print("oil sold=", GS.stats["oil_villager"], " debts=", GS.villagers.values().map(func(v): return v["debt"]))
			# debt seizure of the franchise partner
			GS.villagers["petani"]["debt"] = 9000000
			d._seize_for_debt("petani")
			world.ui.close()
			d.open_kantor()
			world.ui.close()
			print("controlled=", GS.controlled_parcels(), " quest=", GS.quest_index)
			GS.money = 40000000
			d._buy_license()
			print("license=", GS.upgrades["lisensi"], " state=", world.state)
			world.ui.close()
			# save / load round trip
			GS.save_game()
			var before := JSON.stringify(GS.parcels)
			GS.load_game()
			print("save roundtrip ok=", before == JSON.stringify(GS.parcels))
			# heat -> raids -> game over
			GS.heat = 100
			GS.money = 100
			GS.sleep()
			print("after raid game_active=", GS.game_active)
			await wait(0.2)
		"features":
			await _features_shots()
		"walk":
			world.start_game(false)
			world.ui.close()
			var pl: Player = world.player
			# into the sea from the south beach
			tp(0, 38)
			pl.touch_vec = Vector2(0, 1)
			await wait(4.0)
			print("sea test: z=%.1f walkable=%s h=%.2f" % [pl.global_position.z, world.is_walkable(pl.global_position.x, pl.global_position.z), pl.global_position.y])
			# into the kantor from the north side
			var k: Vector3 = world.building_nodes["kantor"].global_position
			tp(k.x, k.z - 6)
			pl.touch_vec = Vector2(0, 1)
			await wait(2.5)
			print("building test: dist to kantor centre=%.2f" % Vector2(pl.global_position.x - k.x, pl.global_position.z - k.z).length())
			# along the jetty
			var j: Vector3 = world.building_nodes["dermaga"].global_position
			tp(j.x - 1.0, j.z)
			pl.touch_vec = Vector2(1, 0)
			await wait(2.0)
			print("jetty test: x=%.1f (start %.1f) y=%.2f" % [pl.global_position.x, j.x - 1.0, pl.global_position.y])
			pl.touch_vec = Vector2.ZERO
			await shot("jetty", 10)
		"input":
			# drive the game with synthetic key presses like a player would
			world.start_game(false)
			var presses := 0
			while world.ui.modal != null and presses < 12:
				await press(KEY_E)
				await wait(0.15)
				presses += 1
			print("after intro: modal=", world.ui.modal != null, " presses=", presses)
			var tv: Node3D = world.tile_views["0:0"]
			tp(tv.global_position.x, tv.global_position.z + 1.3, Vector3(0, 0, -1))
			await wait(0.3)
			await press(KEY_E)
			await wait(0.6)
			print("tbs after E=", GS.inv["tbs"], " target=", world.target.get("prompt", func(): return "none").call())
			# walk to the kantor door and open its menu
			var d: Vector3 = world.door_points["kantor"]
			tp(d.x, d.z + 0.5, Vector3(0, 0, -1))
			await wait(0.3)
			await press(KEY_E)
			await wait(0.4)
			print("kantor menu open=", world.ui.modal != null)
			await shot("kantor_menu", 5)
			await press(KEY_ESCAPE)
			await wait(0.3)
			print("closed=", world.ui.modal == null)
			await press(KEY_ESCAPE)
			await wait(0.3)
			print("pause open=", world.ui.modal != null and world.ui.modal.has_meta("pause"))
			await shot("pause", 5)
			await press(KEY_ESCAPE)
			await wait(0.3)
			await press(KEY_TAB)
			await wait(0.3)
			await shot("status", 5)
		"econ":
			# honest strategy: farm, buy land at fair price, hire workers; how long to win?
			world.start_game(false)
			world.ui.close()
			var d: Node = world.deals
			var order := ["nenek", "kakek", "pemuda", "ibu", "petani", "kades"]
			for day in 60:
				GS.energy = GS.max_energy
				var meals := 2
				for p in GS.parcels:
					if p["owner"] != "player":
						continue
					for i in GS.tile_count():
						var info := GS.tile_action_info(p["id"], i)
						if not info["ok"] and info["verb"].begins_with("Butuh bibit") and GS.money > 400000:
							d._buy("bibit", 5, GS.PRICE["bibit"] * 5, func(): pass)
							info = GS.tile_action_info(p["id"], i)
						if info["ok"] and info["kind"] == "fert":
							continue
						if GS.energy < 12 and meals > 0 and GS.money > 20000:
							GS.money -= 15000
							GS.energy += 40
							meals -= 1
						if int(GS.inv["tbs"]) >= GS.capacity():
							d._sell_tbs()
						GS.do_tile_action(p["id"], i)
				d._sell_tbs()
				world.ui.close()
				for vid in order:
					if GS.villagers[vid]["status"] == "owner" and GS.money > GS.VILLAGERS[vid]["value"] + 600000:
						d._buy_fair(vid)
						world.ui.close()
						break
				if GS.palm_count() >= 30 and GS.workers.size() < 3 and GS.money > 3000000:
					d._hire_generic()
					world.ui.close()
				if not GS.upgrades["gerobak"] and GS.money > 1500000:
					d._buy_upgrade("gerobak")
					world.ui.close()
				if GS.controlled_parcels() >= 7 and GS.money >= GS.PRICE["lisensi"]:
					print("WIN on day ", GS.day)
					break
				GS.sleep()
				world.ui.close()
				GS.pending_events.clear()
				if day % 5 == 4:
					print("day %d money=%s parcels=%d palms=%d workers=%d" % [GS.day, GS.fmt_short(GS.money), GS.controlled_parcels(), GS.palm_count(), GS.workers.size()])
		"touch":
			world.start_game(false)
			world.ui.close()
			await wait(0.2)
			var x0: float = world.player.global_position.x
			var t := InputEventScreenTouch.new()
			t.index = 0
			t.position = Vector2(250, 520)
			t.pressed = true
			Input.parse_input_event(t)
			for k in 8:
				var dr := InputEventScreenDrag.new()
				dr.index = 0
				dr.position = Vector2(250 - k * 10, 520)
				dr.relative = Vector2(-10, 0)
				Input.parse_input_event(dr)
				await get_tree().process_frame
			await wait(1.0)
			print("touch joystick: touch_mode=%s moved dx=%.2f" % [world.ui._touch_mode, world.player.global_position.x - x0])
			await shot("touch_joystick", 2)
			t.pressed = false
			Input.parse_input_event(t)
			await wait(0.2)
			print("released vec=", world.player.touch_vec)
		"perf":
			for i in 30:
				await get_tree().process_frame
			print("perf at title: draw calls=%d objects=%d primitives=%d" % [
				Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
				Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
				Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])
			world.start_game(false)
			world.ui.close()
			for q in [true, false]:
				world.set_quality(q)
				for s in [[-17, 30], [-3, 5], [48, 0], [0, -40]]:
					tp(s[0], s[1])
					for i in 30:
						await get_tree().process_frame
					print("perf%s at %s: draw calls=%d objects=%d primitives=%d" % ["" if q else " (Hemat baterai)", s,
						Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
						Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
						Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])
			world.set_quality(true)
		"perfsplit":
			# where do the draw calls go? hide one group at a time at the busiest spot
			world.start_game(false)
			world.ui.close()
			var groups := {
				"undergrowth": [world.undergrowth],
				"decor": world.get_children().filter(func(n): return n is MultiMeshInstance3D),
				"tiles": world.tile_views.values(),
				"parcel_batch": world.get_children().filter(func(n): return str(n.name).begins_with("ParcelDecor")),
				"buildings": world.building_nodes.values(),
				"npcs": world.get_children().filter(func(n): return n is Npc),
				"player": [world.player],
				"ambient": [world.ambient],
				"props": world.get_children().filter(func(n): return n is MeshInstance3D and not n in world.building_nodes.values()),
			}
			for spot in [[-17, 30], [48, 0]]:
				tp(spot[0], spot[1])
				for i in 30:
					await get_tree().process_frame
				var base := [Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)]
				print("perfsplit %s all: draw=%d prims=%d" % [spot, base[0], base[1]])
				for g in groups:
					for n in groups[g]:
						n.visible = false
					for i in 4:
						await get_tree().process_frame
					var dc: float = Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
					var pr: float = Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
					print("perfsplit   %-12s draw=%4d prims=%7d" % [g, base[0] - dc, base[1] - pr])
					for n in groups[g]:
						n.visible = true
				world.sun.shadow_enabled = false
				for i in 4:
					await get_tree().process_frame
				print("perfsplit   %-12s draw=%4d prims=%7d" % ["shadows", base[0] - Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), base[1] - Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])
				world.sun.shadow_enabled = true
		"hero":
			# the target screenshot's composition: standing at a ripe palm, harvesting
			world.start_game(false)
			world.ui.close()
			GS.hour = 8.5
			tp(-17.4, 25.4, Vector3(-0.5, 0, -1).normalized())
			await shot("hero", 40)
			world._tile_action(0, 1)
			await wait(0.9)
			await shot("hero_harvest", 2)
		"look":
			# quick two-shot look check for render tuning
			world.start_game(false)
			world.ui.close()
			GS.hour = 8.5
			for s in [[-17, 28.0, "parcel"], [-9, 10, "road"]]:
				tp(s[0], s[1], Vector3(0, 0, -1))
				await shot("look_" + s[2], 30)
		"vis":
			# curated views for comparing against art/reference/07_target_gameplay.png
			world.start_game(false)
			world.ui.close()
			GS.hour = 8.5
			for s in [[-17, 28.0, "parcel"], [-9, 10, "road"], [-44, 36, "garden"], [-3, 36, "kantor"], [49, -3, "pabrik"], [-3, 26.5, "behind_kantor"], [-30, -20, "field"]]:
				tp(s[0], s[1], Vector3(0, 0, -1))
				await shot("vis_" + s[2], 40)
			# buy Kakek's garden, clear a few tiles and plant: the parcel batch must follow
			GS.money = 60000000
			world.deals._buy_fair("kakek")
			world.ui.close()
			for i in [0, 1, 2, 5, 6]:
				GS.energy = 100
				world._tile_action(1, i)
			for i in [0, 1]:
				GS.energy = 100
				world._tile_action(1, i)
			tp(-44, 36, Vector3(0, 0, -1))
			await shot("vis_garden_cleared", 30)
			# running along the road: dust puffs
			tp(-20, 8.5, Vector3(1, 0, 0))
			world.player.touch_vec = Vector2(1, 0)
			await wait(0.8)
			await shot("vis_run", 2)
			world.player.touch_vec = Vector2.ZERO
			GS.hour = 20.5
			tp(-17, 32.5, Vector3(0, 0, -1))
			await shot("vis_night", 60)
			# the mill's steam must not glow at night
			tp(49, -3, Vector3(0, 0, -1))
			await shot("vis_night_pabrik", 30)
			GS.hour = 8.5
			world.set_quality(false)
			tp(-17, 32.5, Vector3(0, 0, -1))
			await shot("vis_parcel_low", 30)
			world.set_quality(true)
		"pitch":
			# camera tuning: the hero spot at a few pitch / distance / look-ahead sets
			world.start_game(false)
			world.ui.close()
			world.ui.visible = false
			var sets := [[45.0, 12.5, 0.8], [43.0, 12.5, 0.8], [45.0, 13.0, 1.2], [44.0, 12.0, 0.6]]
			for a in OS.get_cmdline_user_args():
				if a.begins_with("--sets="):
					sets = JSON.parse_string(a.get_slice("=", 1))
			for pd in sets:
				world.cam_pitch = pd[0]
				world.cam_distance = pd[1]
				world.cam_lead = pd[2]
				GS.hour = 8.5
				tp(-17.4, 25.4, Vector3(-0.5, 0, -1).normalized())
				await shot("pitch_%d_%d_%d" % [pd[0], pd[1] * 10, pd[2] * 10], 12)
				tp(-17, 28, Vector3(0, 0, -1))
				await shot("parcel_%d_%d_%d" % [pd[0], pd[1] * 10, pd[2] * 10], 12)
			world.ui.visible = true
		"measure":
			# UI-free frames + key-colour masks for scripted comparisons with the target
			# (/tmp tools: crown HSV from the palm mask, undergrowth coverage of the land)
			world.start_game(false)
			world.ui.close()
			world.ui.visible = false
			var spots := [[-17.4, 25.4, "hero"], [-17, 30, "parcel"], [-9, 10, "road"], [-3, 36, "kantor"],
				[-44, 36, "garden"], [-30, -20, "field"],
				# (fix round 2: the other villager gardens of the tour; only with --spots=)
				[-20, -40, "garden2"], [18, -40, "garden3"], [22, 34, "garden4"]]
			var only := ""
			var masks := true
			var low := false
			var hour := 8.5
			for a in OS.get_cmdline_user_args():
				if a.begins_with("--spots="):
					only = a.get_slice("=", 1)
				elif a == "--nomask":
					masks = false
				elif a == "--low":
					low = true
				elif a.begins_with("--hour="):
					hour = float(a.get_slice("=", 1))
			for s in spots:
				if only != "" and not str(s[2]) in only.split(","):
					continue
				if only == "" and str(s[2]).begins_with("garden") and str(s[2]) != "garden":
					continue
				GS.hour = hour
				tp(s[0], s[1], Vector3(0, 0, -1))
				await shot("m_%s_noui" % s[2], 14)
				if masks:
					await _mask_shot("m_%s_mask" % s[2], false)
					await _mask_shot("m_%s_mask0" % s[2], true)
				if low:
					world.set_quality(false)
					GS.hour = hour
					await shot("m_%slow_noui" % s[2], 10)
					world.set_quality(true)
			world.ui.visible = true
		"tune":
			# render tuning: --tune=<json file> = [{"name", "terrain": {uniform: value},
			# "foliage": {uniform: value}, "frond": {...}, "sun": x, "amb": x, "sat": x}, ...]
			world.start_game(false)
			world.ui.close()
			world.ui.visible = false
			var path := ""
			var only := "hero,road"
			for a in OS.get_cmdline_user_args():
				if a.begins_with("--tune="):
					path = a.get_slice("=", 1)
				elif a.begins_with("--spots="):
					only = a.get_slice("=", 1)
			var sets: Array = JSON.parse_string(FileAccess.get_file_as_string(path))
			var spots := {"hero": [-17.4, 25.4], "road": [-9, 10], "kantor": [-3, 36], "field": [-30, -20], "pabrik": [49, -3],
				"garden": [-44, 36], "parcel": [-17, 30]}
			for st in sets:
				_tune = st
				for k in st.get("terrain", {}):
					var v = st["terrain"][k]
					world.terrain_mat.set_shader_parameter(k, Vector3(v[0], v[1], v[2]) if v is Array else v)
				for m in ModelLib._materials.values():
					var sm := m as ShaderMaterial
					if sm == null or not str(sm.shader.resource_path).contains("foliage"):
						continue
					var frond: bool = sm.resource_name.findn("Frond") >= 0 and sm.resource_name.findn("Dry") < 0
					for grp in ["foliage", "frond"]:
						if grp == "frond" and not frond:
							continue
						for k in st.get(grp, {}):
							var fv = st[grp][k]
							sm.set_shader_parameter(k, Vector3(fv[0], fv[1], fv[2]) if fv is Array else fv)
				world.env.adjustment_saturation = st.get("sat", world.POST_SATURATION)
				world.env.adjustment_brightness = st.get("bright", world.POST_BRIGHTNESS)
				if st.has("low"):
					world.set_quality(not st["low"])
				for sp in only.split(","):
					GS.hour = st.get("hour", 8.5)
					tp(spots[sp][0], spots[sp][1], Vector3(0, 0, -1))
					if st.get("mask", false):
						# names measure.py pairs up: m_<set><spot>_noui / _mask / _mask0
						await shot("m_%s%s_noui" % [st["name"], sp], 12)
						await _mask_shot("m_%s%s_mask" % [st["name"], sp], false)
						await _mask_shot("m_%s%s_mask0" % [st["name"], sp], true)
					else:
						await shot("t_%s_%s" % [st["name"], sp], 12)
				if st.has("low"):
					world.set_quality(true)
			_tune = {}
			world.ui.visible = true
		"dawn":
			# the first frames of a new game (06:00) and of the evening
			await shot("title", 10)
			world.start_game(false)
			await shot("dawn_intro", 12)
			world.ui.close()
			await shot("dawn_0600", 12)
			for hh in [7.0, 12.0, 16.5, 17.5, 18.5]:
				GS.hour = hh
				await shot("dawn_%04d" % int(hh * 100), 12)
			GS.hour = 8.5
			world.set_quality(false)
			await shot("dawn_0830_low", 12)
			world.set_quality(true)
			await shot("dawn_0830", 12)
		"portrait":
			# run with --resolution 576x1280 (phone held upright)
			world.start_game(false)
			world.ui.close()
			GS.hour = 8.5
			tp(-17.4, 25.4, Vector3(-0.5, 0, -1).normalized())
			await shot("portrait_hero", 14)
			tp(-3.5, 37.5, Vector3(0, 0, -1))
			await shot("portrait_spawn", 14)
		"lush":
			# render tuning: UI-free frames at 08:30 (tour spots + curated views) for
			# measuring brightness / shade coverage against the target screenshot
			world.start_game(false)
			world.ui.close()
			world.ui.visible = false
			var spots := [[-3, 34], [-14, 3], [8, 5], [50, -2], [-44, 36], [-20, -40], [18, -40], [66, 13], [30, 45],
				[-9, 10], [-3, 36], [-30, -20], [-17, 28], [-17.4, 25.4], [-3, 26], [-26, -2]]
			for s in spots:
				GS.hour = 8.5
				tp(s[0], s[1], Vector3(0, 0, -1))
				await shot("lush_%d_%d" % [s[0], s[1]], 25)
			world.ui.visible = true
		"sweep":
			# budget check over the whole title orbit (16 positions of world._title_t over
			# one lap, 0..TAU / 0.05 s) and a grid of gameplay spots (--grid, --low)
			var worst := [0, 0]
			for k in 16:
				world._title_t = k * (TAU / 0.05) / 16.0
				var a: float = world._title_t * 0.05
				world.cam_rig.global_position = Vector3(sin(a) * 18.0, 0, 6.0 + cos(a) * 10.0)
				for i in 8:
					await get_tree().process_frame
				var dc: int = Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
				var pr: int = Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
				worst = [maxi(worst[0], dc), maxi(worst[1], pr)]
				print("sweep title k=%d draw=%d prims=%d" % [k, dc, pr])
			print("sweep title max: draw=%d prims=%d" % worst)
			var args := OS.get_cmdline_user_args()
			if "--split" in args:
				# where do the title's triangles go? (k = 15, the busiest view)
				world._title_t = 15 * (TAU / 0.05) / 16.0
				var a2: float = world._title_t * 0.05
				world.cam_rig.global_position = Vector3(sin(a2) * 18.0, 0, 6.0 + cos(a2) * 10.0)
				for i in 8:
					await get_tree().process_frame
				var base := [Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)]
				var groups := {
					"undergrowth": [world.undergrowth],
					"decor": world.get_children().filter(func(n): return n is MultiMeshInstance3D),
					"tiles": world.tile_views.values(),
					"parcel_batch": world.get_children().filter(func(n): return str(n.name).begins_with("ParcelDecor")),
					"buildings": world.building_nodes.values(),
					"npcs": world.get_children().filter(func(n): return n is Npc),
					"ambient": [world.ambient],
					"props": world.get_children().filter(func(n): return n is MeshInstance3D and not n in world.building_nodes.values()),
				}
				for g in groups:
					for n in groups[g]:
						n.visible = false
					for i in 3:
						await get_tree().process_frame
					print("sweep split %-12s draw=%4d prims=%7d" % [g, base[0] - Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), base[1] - Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])
					for n in groups[g]:
						n.visible = true
				world.sun.shadow_enabled = false
				for i in 3:
					await get_tree().process_frame
				print("sweep split %-12s draw=%4d prims=%7d" % ["shadows", base[0] - Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME), base[1] - Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)])
				world.sun.shadow_enabled = true
			if "--grid" in args:
				world.start_game(false)
				world.ui.close()
				for q in ([false] if "--low" in args else [true]):
					world.set_quality(q)
					worst = [0, 0, ""]
					for x in [-56, -40, -24, -8, 8, 24, 40, 56]:
						for z in [-48, -32, -16, 0, 16, 32, 44]:
							if world.height_at(x, z) < -0.2:
								continue
							tp(x, z)
							for i in 8:
								await get_tree().process_frame
							var dc2: int = Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
							var pr2: int = Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
							if pr2 > worst[1]:
								worst = [dc2, pr2, "%d,%d" % [x, z]]
					print("sweep grid%s worst: draw=%d prims=%d at %s" % ["" if q else " (Hemat baterai)", worst[0], worst[1], worst[2]])
				world.set_quality(true)
		"tiles":
			# tile-state readability: every state side by side in Lahan Kantor, the bush
			# thickets of a villager garden, and the player standing in the carpet
			world.start_game(false)
			world.ui.close()
			world.ui.visible = false
			var states := [["palm", 3], ["palm", 3], ["palm", 3], ["palm", 3], ["empty", 0], ["palm", 0], ["palm", 1],
				["palm", 2], ["bush", 0], ["bush", 0], ["empty", 0], ["palm", 1]]
			for i in GS.tile_count():
				var t: Dictionary = GS.parcels[0]["tiles"][i]
				t["s"] = states[i % states.size()][0]
				t["st"] = states[i % states.size()][1]
				t["fr"] = states[i % states.size()][1] == 3
			GS.parcel_changed.emit(0)
			GS.hour = 8.5
			tp(-17, 29.5, Vector3(0, 0, -1))
			await shot("tiles_kantor", 20)
			tp(-17.4, 25.4, Vector3(-0.5, 0, -1).normalized())
			await shot("tiles_hero", 14)
			tp(-44, 35, Vector3(0, 0, -1))
			await shot("tiles_garden", 14)
			# in the carpet: the legs must show
			# (fix round 2: + on a "Tebas semak" thicket in Kakek's garden and in Lahan Kantor,
			# and in the fern mass south of the garden)
			for s in [[-30, -20.5], [-41.5, 36.5], [-9.5, 14.5], [-45.6, 34.2], [-21.8, 30.2], [-44, 39.5]]:
				tp(s[0], s[1], Vector3(0, 0, 1))
				await shot("tiles_stand_%d_%d" % [s[0], s[1]], 14)
			world.ui.visible = true
		"showcase":
			await _showcase()
		"map3":
			# map v3 check: the dense staggered palms, the bridges (and walking over one),
			# every hamlet, the big minimap and the frame cost in a hamlet
			world.start_game(false)
			world.ui.close()
			GS.hour = 9.0
			for i in GS.tile_count():
				GS.parcels[0]["tiles"][i] = {"s": "palm", "st": 3, "g": 0, "f": false, "fr": i % 3 == 0, "fd": 0}
			GS.parcel_changed.emit(0)
			tp(-17, 34, Vector3(0, 0, -1))
			await shot("m3_dense_palms", 30)
			tp(-17, 25.5, Vector3(0, 0, -1))
			await shot("m3_dense_palms_in", 20)
			for b in world.layout.get("bridges", []):
				tp(float(b["pos"][0]) + 1.5, float(b["pos"][2]), Vector3(0, 0, 1))
				await shot("m3_bridge_%d_%d" % [b["pos"][0], b["pos"][2]], 25)
			tp(70, 16, Vector3(1, 0, 0))
			await shot("m3_lagoon_jetty", 25)
			var br: Array = world.layout["bridges"][0]["pos"]
			var pl: Player = world.player
			tp(float(br[0]) - 9.0, float(br[2]), Vector3(1, 0, 0))
			pl.touch_vec = Vector2(1, 0)
			var ymax := -10.0
			for k in 60:
				await wait(0.1)
				ymax = maxf(ymax, pl.global_position.y)
			pl.touch_vec = Vector2.ZERO
			print("bridge walk: from x=%.1f to x=%.1f, max y=%.2f, walkable mid=%s" % [float(br[0]) - 9.0,
				pl.global_position.x, ymax, world.is_walkable(float(br[0]), float(br[2]))])
			for v in world.layout.get("villages", []):
				tp(float(v["center"][0]) + 2.0, float(v["center"][1]) + 7.0, Vector3(0, 0, -1))
				await shot("m3_village_%s" % v["id"], 25)
				print("perf at %s: draw calls=%d primitives=%d fps=%d" % [v["id"],
					Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
					Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME), Engine.get_frames_per_second()])
			tp(-3.5, 37.5, Vector3(0, 0, -1))
			world.ui.minimap.big = true
			world.ui.call("_layout")
			await shot("m3_minimap_big", 10)
			world.ui.minimap.big = false
			world.ui.call("_layout")
			print("npcs=%d extras=%d walkers=%d houses=%d" % [world.npcs.size(), world.extras.size(), world.walkers.size(),
				world.building_nodes.size()])
		"tour":
			world.start_game(false)
			world.ui.close()
			var spots := [[-3, 34], [-14, 3], [8, 5], [50, -2], [56, 22], [-44, 36], [-20, -40], [18, -40], [22, 34], [66, 13], [0, -50], [30, 45]]
			for s in spots:
				tp(s[0], s[1])
				await shot("tour_%d_%d" % [s[0], s[1]], 25)


func grab(name: String) -> void:
	## save the frame being shown right now (for 0.1 s bursts: no extra frame waits)
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png("%s/%s.png" % [shots_dir, name])
	print("[grab] ", name)


func _near_npc(npc: Node3D, back := 1.6) -> void:
	## stand south of an NPC (camera side), facing it
	var p := npc.global_position
	tp(p.x + 0.4, p.z + back, Vector3(-0.4, 0, -back).normalized())


func _showcase() -> void:
	## Release showcase frames (integration rounds): named PNGs in --shots=<dir>
	world.start_game(false)
	world.ui.close()
	GS.hour = 8.5
	GS.money = 6000000
	GS.inv["surat"] = 1
	GS.upgrades["preman"] = 1
	GS.stats_changed.emit()
	# every palm of the player's parcel ripe
	for t in GS.parcels[0]["tiles"]:
		if t["s"] == "palm":
			t["st"] = 3
			t["fr"] = true
	GS.parcel_changed.emit(0)
	# 1. hero harvest at the player's parcel
	tp(-17.4, 25.4, Vector3(-0.5, 0, -1).normalized())
	await wait(0.6)
	await shot("hero", 20)
	world._tile_action(0, 1)
	for k in 6:
		await wait(0.1)
		await grab("burst_harvest_%d" % k)
	await wait(0.4)
	await shot("hero_harvest", 2)
	# 2. village road + a walking burst along it
	GS.hour = 8.5
	tp(-9, 10, Vector3(0, 0, -1))
	await shot("village_road", 30)
	tp(-20, 8.5, Vector3(1, 0, 0))
	world.player.touch_vec = Vector2(0.55, 0)
	await wait(0.8)
	for k in 6:
		await wait(0.1)
		await grab("burst_walk_%d" % k)
	world.player.touch_vec = Vector2.ZERO
	await wait(0.3)
	# 3. the warung with villagers gathered in front
	var wd: Vector3 = world.door_points.get("warung", Vector3(8, 0, 5))
	var guests := ["kakek", "nenek"]
	for i in guests.size():
		var n: Npc = world.npcs[guests[i]]
		n.set_anchor(wd + Vector3(-1.6 + i * 1.3, 0, 1.6 + i * 0.3), 0.3, true)
	(world.npcs["kakek"] as Npc)._start_chat(world.npcs["nenek"], 20.0, true)
	(world.npcs["nenek"] as Npc)._start_chat(world.npcs["kakek"], 20.0, false)
	tp(wd.x + 1.8, wd.z + 3.2, Vector3(-0.3, 0, -1).normalized())
	await wait(1.0)
	await shot("warung", 10)
	# 4. the mill
	tp(49, -3, Vector3(0, 0, -1))
	await shot("pabrik", 30)
	# 5. beach and jetty
	var j: Vector3 = world.building_nodes["dermaga"].global_position
	tp(j.x - 2.0, j.z + 3.0, Vector3(1, 0, 0))
	await shot("beach_jetty", 30)
	# 6. villager dialog with the land choices (the target's dialog)
	var ibu: Npc = world.npcs["ibu"]
	_near_npc(ibu)
	await wait(0.5)
	world.deals.talk("ibu")
	await wait(0.3)
	world.deals.land_menu("ibu")
	await wait(1.5)
	world.ui.finish_typing()
	await shot("dialog_choices", 10)
	world.ui.close()
	await wait(0.3)
	# 7. shop menu
	var td: Vector3 = world.door_points.get("toko", Vector3(-14, 0, 3))
	tp(td.x, td.z + 0.8, Vector3(0, 0, -1))
	await wait(0.3)
	world.deals.open_toko()
	await shot("shop_menu", 20)
	world.ui.close()
	# 8. night in the village (warung lights, fireflies)
	GS.hour = 20.5
	tp(wd.x, wd.z + 4.0, Vector3(0, 0, -1))
	await shot("night", 50)
	# 9. morning report
	GS.sleep()
	await shot("morning_report", 25)
	world.ui.close()
	# 10. touch layout at a landscape phone size
	GS.hour = 8.5
	world.ui._touch_mode = true
	world.ui.touch.visible = true
	world.ui._prompt_cache = ""
	get_window().size = Vector2i(915, 412)
	tp(-17.4, 25.4, Vector3(-0.5, 0, -1).normalized())
	await wait(0.5)
	world.ui._layout()
	await shot("touch_915x412", 20)
	get_window().size = Vector2i(1280, 720)
	await wait(0.3)


# ------------------------------------------------------------------ fishing / bag / houses
var _fails := 0


func check(ok: bool, what: String) -> void:
	print("CHECK %s: %s" % ["ok" if ok else "FAIL", what])
	if not ok:
		_fails += 1
		push_error("autotest check failed: " + what)


func find_fish_spot(center: Vector3, want: String, radius := 40.0) -> bool:
	## puts the player on land (or a deck) facing `want` water ("sea" / "river")
	var dirs := [Vector3(1, 0, 0), Vector3(-1, 0, 0), Vector3(0, 0, 1), Vector3(0, 0, -1)]
	var r := 0.0
	while r <= radius:
		var n := maxi(1, int(r * 1.5))
		for i in n:
			var a := TAU * i / n
			var x := center.x + cos(a) * r
			var z := center.z + sin(a) * r
			if not world.is_walkable(x, z) or not world.is_free(x, z, 0.4):
				continue
			for f in dirs:
				tp(x, z, f)
				var sp: Dictionary = world.fishing_spot()
				if not sp.is_empty() and sp["water"] == want:
					return true
		r += 2.0
	return false


func _fish_once(perfect := true) -> String:
	## one full cast; returns fishing.last_result
	var fi: Node = world.fishing
	fi.fast = true
	if not world.start_fishing():
		return "no-start"
	var t := 0.0
	while fi.phase != "bite" and fi.active and t < 4.0:
		await get_tree().process_frame
		t += get_process_delta_time()
	fi.press()
	if fi.phase == "reel":
		fi.cursor = fi.zone_c if perfect else fmod(fi.zone_c + 0.5, 1.0)
		fi.press()
	await wait(0.1)
	return fi.last_result


func _features_logic() -> void:
	var d: Node = world.deals
	var ui: Node = world.ui
	# --- fishing at the sea and at a river, then selling
	check(int(GS.inv.get("pancing", 0)) == 1, "new game gives a fishing rod")
	var j: Vector3 = world.building_nodes["dermaga"].global_position
	check(find_fish_spot(j, "sea"), "found a sea fishing spot near the jetty")
	world._update_target()
	check(world.target.get("fish", false) and String(world.target["prompt"].call()).begins_with("Mancing"), "prompt at the water is Mancing")
	var e0: float = GS.energy
	var res: String = await _fish_once(true)
	check(res.begins_with("caught:"), "sea catch (%s)" % res)
	check(GS.energy < e0, "fishing costs energy")
	check(GS.fish_count() == 1, "fish in the bag")
	var br: Array = world.bridges[0]
	check(find_fish_spot(Vector3(br[0], 0, br[1]), "river", 30.0), "found a river fishing spot at a bridge")
	res = await _fish_once(true)
	check(res.begins_with("caught:"), "river catch (%s)" % res)
	res = await _fish_once(false)
	check(res == "missed", "missing the green zone loses the fish (%s)" % res)
	world.fishing.fast = true
	world.start_fishing()
	var tw := 0.0
	while world.fishing.phase != "wait" and tw < 3.0:
		await get_tree().process_frame
		tw += get_process_delta_time()
	world.fishing.press()
	check(world.fishing.last_result == "early", "pressing before the bite reels in empty")
	check(not world.player.locked, "player free again after fishing")
	var pool: Array = GS.fish_available("river", 18.5)
	check("ikan_lele" in pool and "ikan_arwana" in pool and not "ikan_kakap" in pool, "river fish at dusk: " + str(pool))
	check("ikan_kakap" in GS.fish_available("sea", 12.0), "kakap in the sea")
	var m0: int = GS.money
	var val: int = GS.fish_value()
	var got: int = d.sell_fish()
	check(got == val and got > 0 and GS.money == m0 + got and GS.fish_count() == 0, "sold fish for %d" % got)
	d.open_warung()
	ui.close()
	d.open_toko()
	ui.close()
	# --- the bag
	GS.catch_fish("ikan_arwana")
	ui.show_bag()
	check(ui.is_bag_open(), "bag opens")
	var n_slots: int = ui.modal.find_children("slot_*", "Button", true, false).size()
	check(n_slots == ui.bag_entries().size() and n_slots >= 6, "bag shows %d items" % n_slots)
	ui.show_bag_select("ikan_arwana")
	await get_tree().process_frame
	check(ui.is_bag_open() and ui.modal.get_meta("bag_select") == "ikan_arwana", "bag item selection")
	ui.show_bag()
	await get_tree().process_frame
	check(ui.modal == null, "bag closes (toggle)")
	# --- houses: a villager's, then the player's own
	check(world.door_points.has("rumah_juragan"), "player house exists")
	var dp: Vector3 = world.door_points["rumah_ibu"]
	tp(dp.x, dp.z + 0.4, Vector3(0, 0, -1))
	world._update_target()
	check(world.target.get("door", false) and str(world.target["prompt"].call()).begins_with("Masuk rumah"), "door prompt: " + str(world.target.get("prompt", func(): return "").call()))
	GS.hour = 18.0
	world.try_action()
	await wait(0.9)
	check(world.inside == "rumah_ibu" and world.player.global_position.x > 300.0, "entered Bu Sari's house")
	check(world._inside_vid == "ibu" and world.interior.owner_node() != null, "Bu Sari is at home in the evening")
	var on: Node3D = world.interior.owner_node()
	tp(on.global_position.x, on.global_position.z + 1.2, Vector3(0, 0, -1))
	world._update_target()
	check(str(world.target.get("prompt", func(): return "").call()).contains("Bu Sari"), "can talk to the owner inside")
	world.target["act"].call()
	check(ui.modal != null, "talk dialog opens inside")
	ui.close()
	tp(world.interior.bed_pos().x, world.interior.bed_pos().z, Vector3(1, 0, 0))
	world._update_target()
	check(not world.target.get("ok", func(): return true).call(), "no sleeping in someone else's bed")
	var ex: Vector3 = world.interior.door_pos()
	tp(ex.x, ex.z + 0.2, Vector3(0, 0, 1))
	world._update_target()
	check(str(world.target.get("prompt", func(): return "").call()) == "Keluar rumah", "exit prompt")
	world.try_action()
	await wait(0.9)
	check(world.inside == "" and world.player.global_position.distance_to(dp) < 1.5, "left the house at its door")
	# the kantor no longer has a bed
	d.open_kantor()
	var has_sleep := false
	for b in ui.modal.find_children("*", "Button", true, false):
		if (b as Button).text == "Tidur":
			has_sleep = true
	ui.close()
	check(not has_sleep, "kantor menu has no sleep any more")
	# sleep in the bed at home
	world.enter_house("rumah_juragan", true)
	check(world.inside == "rumah_juragan" and world._inside_vid == "", "entered own house")
	var bp: Vector3 = world.interior.bed_pos()
	tp(bp.x, bp.z, Vector3(1, 0, -0.5))
	world._update_target()
	check(str(world.target.get("prompt", func(): return "").call()) == "Tidur di kasur" and world.target["ok"].call(), "bed prompt Tidur")
	var day0: int = GS.day
	GS.hour = 21.0
	world.try_action()
	await get_tree().process_frame
	check(GS.day == day0 + 1 and GS.last_slept, "sleeping in bed advances the day")
	check(world.inside == "rumah_juragan" and world.player.global_position.distance_to(bp) < 1.0, "wake up beside the bed")
	check(FileAccess.file_exists(GS.SAVE_PATH), "autosaved")
	ui.close()
	# pass out at midnight inside a villager's house -> taken home, outside
	world.exit_house(true)
	world.enter_house("rumah_kades", true)
	GS.hour = 23.99
	GS.advance(1.0)
	await get_tree().process_frame
	check(GS.day == day0 + 2 and not GS.last_slept and world.inside == "", "pass out after 24:00")
	check(world.player.global_position.distance_to(world.door_points["rumah_juragan"]) < 1.5, "woke at own house door")
	ui.close()
	# save keeps the fish / rod keys
	GS.save_game()
	GS.load_game()
	check(int(GS.inv.get("pancing", 0)) == 1 and int(GS.inv.get("ikan_arwana", 0)) == 1, "save keeps rod and fish")
	await _logic_fish_and_rooms()
	print("features logic: %s (%d failed)" % ["OK" if _fails == 0 else "FAIL", _fails])
	GS.hour = 8.0


func _house_of_type(t: String) -> String:
	for hid in world.door_points:
		var h := String(hid)
		if h.begins_with("rumah") and h != "rumah_juragan" and world.interior.room_type(h) == t:
			var vid: String = world.house_owner(h)
			if vid == "" or not GS.villagers.get(vid, {}).get("evicted", false):
				return h
	return ""


func _logic_fish_and_rooms() -> void:
	var ui: Node = world.ui
	# --- bait: 10 at the start, one per cast, none left -> no fishing
	GS.inv["umpan"] = 0
	check(not world.fishing.start(world.player.global_position + Vector3(0, 0, 3), "river"), "no bait -> cannot cast")
	GS.inv["umpan"] = 500   # plenty for the casts below
	# --- 20 species in four rarity tiers
	check(GS.FISH.size() == 20, "20 fish species (%d)" % GS.FISH.size())
	var tiers := {"N": 0, "R": 0, "SR": 0, "SSR": 0}
	for id in GS.FISH:
		tiers[GS.fish_rarity(id)] += 1
		check(ResourceLoader.exists("res://assets/icons/%s.png" % id), "icon for " + id)
	check(tiers["N"] == 8 and tiers["R"] == 6 and tiers["SR"] == 4 and tiers["SSR"] == 2, "tiers 8/6/4/2: " + str(tiers))
	for w in ["river", "sea"]:
		for h in [3.0, 7.0, 12.0, 18.5, 23.0]:
			check(not GS.fish_available(w, h).is_empty(), "something bites in %s at %.1f" % [w, h])
	var hits := {"N": 0, "R": 0, "SR": 0, "SSR": 0}
	GS.rng.seed = 42
	for i in 6000:
		hits[GS.fish_rarity(GS.roll_fish("sea", 18.5))] += 1
	print("rarity hits (sea 18:30, 6000 rolls): ", hits)
	check(hits["N"] > hits["R"] and hits["R"] > hits["SR"] and hits["SR"] > hits["SSR"] and hits["SSR"] > 0, "rarity weights N > R > SR > SSR > 0")
	check(float(hits["SSR"]) / 6000.0 < 0.03, "SSR stays rare")
	var price_ok := true
	var hard_ok := true
	for id in GS.FISH:
		var t: int = GS.RARITY[GS.fish_rarity(id)]["order"]
		for id2 in GS.FISH:
			var t2: int = GS.RARITY[GS.fish_rarity(id2)]["order"]
			if t2 > t and int(GS.FISH[id2]["price"]) <= int(GS.FISH[id]["price"]):
				price_ok = false
			if t2 > t and float(GS.FISH[id2]["hard"]) <= float(GS.FISH[id]["hard"]) and t2 >= 2:
				hard_ok = false
	check(price_ok, "every rarer tier sells for more")
	check(hard_ok, "SR / SSR are harder than lower tiers")
	check("ikan_raja_sawit" in GS.fish_available("river", 23.5) and not "ikan_raja_sawit" in GS.fish_available("river", 12.0), "Ikan Raja Sawit only at midnight")
	# a forced SSR catch through the minigame
	var br: Array = world.bridges[0]
	find_fish_spot(Vector3(br[0], 0, br[1]), "river", 30.0)
	world.fishing.force_fish = "ikan_raja_sawit"
	var before := int(GS.fish_log.get("ikan_raja_sawit", 0))
	var res: String = await _fish_once(true)
	check(res == "caught:ikan_raja_sawit", "forced SSR catch (%s)" % res)
	check(int(GS.fish_log.get("ikan_raja_sawit", 0)) == before + 1, "collection logs the catch")
	check(ui.root.get_node_or_null("CatchCard") != null and ui.root.get_node("CatchCard").find_child("Rarity_SSR", true, false) != null, "catch card with SSR badge")
	# --- the collection panel
	ui.show_bag()
	var dexb: Button = ui.modal.find_child("FishDexButton", true, false)
	check(dexb != null and dexb.text.contains("/20"), "bag has the Koleksi Ikan button")
	dexb.pressed.emit()
	await get_tree().process_frame
	check(ui.is_fish_collection_open(), "collection opens from the bag")
	check(ui.modal.find_children("dex_*", "Button", true, false).size() == 20, "collection shows 20 species")
	ui.show_fish_collection("ikan_napoleon")
	await get_tree().process_frame
	check(ui.is_fish_collection_open() and ui.modal.get_meta("dex_select") == "ikan_napoleon", "collection selection")
	ui.close()
	var n_sp: int = GS.fish_caught_species()
	GS.save_game()
	GS.fish_log = {}
	GS.load_game()
	check(GS.fish_caught_species() == n_sp and n_sp >= 2, "save keeps the collection (%d species)" % n_sp)
	# an old save without fish_log still loads (collection seeded from the bag)
	var f := FileAccess.open(GS.SAVE_PATH, FileAccess.READ)
	var data: Dictionary = JSON.parse_string(f.get_as_text())
	f.close()
	data.erase("fish_log")
	f = FileAccess.open(GS.SAVE_PATH, FileAccess.WRITE)
	f.store_string(JSON.stringify(data))
	f.close()
	check(GS.load_game() and GS.fish_log.has("ikan_arwana"), "old save loads, collection from the bag")
	# --- every room type builds its own interior, the door and bed work in each
	var sigs := {}
	for t in ["kayu", "jahit", "dapur", "panggung", "limas", "bata", "pondok"]:
		var hid := _house_of_type(t)
		check(hid != "", "a house of type " + t)
		if hid == "":
			continue
		world.enter_house(hid, true)
		var it: Node3D = world.interior
		check(world.inside == hid and it.kind == t, "entered %s (%s)" % [hid, it.kind])
		var dp: Vector3 = it.door_pos()
		check(world.is_walkable(dp.x, dp.z), t + ": door spot walkable")
		var bp: Vector3 = it.bed_pos()
		check(world.is_walkable(bp.x, bp.z), t + ": bed side walkable")
		var room: Node = it.get_node_or_null("Room")
		check(room != null and room.get_child_count() > 40, "%s: room built (%d parts)" % [t, room.get_child_count() if room else 0])
		sigs[t] = "%s|%d" % [it.half, room.get_child_count() if room else 0]
		tp(dp.x, dp.z + 0.2, Vector3(0, 0, 1))
		world._update_target()
		check(str(world.target.get("prompt", func(): return "").call()) == "Keluar rumah", t + ": exit prompt")
		world.exit_house(true)
		check(world.interior.get_node_or_null("Room") == null, t + ": room freed on exit")
	var uniq := {}
	for k in sigs:
		uniq[sigs[k]] = true
	check(uniq.size() == sigs.size(), "room types differ: " + str(sigs))
	# two houses of the same type differ (seeded variation)
	var same: Array = []
	for hid in world.door_points:
		if String(hid).begins_with("rumah") and hid != "rumah_juragan" and world.interior.room_type(hid) == "limas":
			same.append(hid)
	if same.size() >= 2:
		var a := _room_sig(same[0])
		var b := _room_sig(same[1])
		check(a != b, "two limas houses look different")
	world.enter_house("rumah_juragan", true)
	check(world.interior.kind == "juragan", "own house is the juragan room")
	var bp2: Vector3 = world.interior.bed_pos()
	tp(bp2.x, bp2.z, Vector3(1, 0, -0.5))
	world._update_target()
	check(str(world.target.get("prompt", func(): return "").call()) == "Tidur di kasur", "juragan room: bed prompt")
	world.exit_house(true)


func _room_sig(hid: String) -> String:
	world.enter_house(hid, true)
	var room: Node = world.interior.get_node("Room")
	var parts: Array = []
	for c in room.get_children():
		if c is MeshInstance3D:
			parts.append("%.1f,%.1f" % [c.position.x, c.position.z])
	world.exit_house(true)
	return ";".join(parts)


func _features_shots() -> void:
	world.start_game(false)
	world.ui.close()
	GS.hour = 9.0
	var fi: Node = world.fishing
	var j: Vector3 = world.building_nodes["dermaga"].global_position
	find_fish_spot(j, "sea")
	world._update_target()
	await shot("fish_prompt", 30)
	fi.fast = false
	world.start_fishing()
	await wait(1.4)
	await shot("fish_wait", 2)
	fi._wait = 0.0
	await wait(0.15)
	await shot("fish_bite", 2)
	fi.press()
	await wait(0.4)
	await shot("fish_reel", 2)
	fi.cursor = fi.zone_c
	fi.press()
	await wait(0.45)
	await shot("fish_catch", 2)
	GS.catch_fish("ikan_kakap")
	GS.catch_fish("udang_galah")
	GS.catch_fish("ikan_arwana")
	await wait(1.5)
	world.ui.show_bag()
	await shot("bag", 20)
	world.ui.show_bag_select("ikan_arwana")
	await shot("bag_arwana", 10)
	world.ui.close()
	# the player's house from outside, then inside
	var dp: Vector3 = world.door_points["rumah_juragan"]
	tp(dp.x, dp.z + 1.5, Vector3(0, 0, -1))
	await shot("house_outside", 40)
	world.enter_house("rumah_juragan", true)
	await shot("house_own", 40)
	var bp: Vector3 = world.interior.bed_pos()
	tp(bp.x, bp.z, Vector3(1, 0, -0.4))
	await shot("bed_prompt", 30)
	GS.hour = 21.0
	await shot("house_night", 30)
	world.try_action()
	await shot("morning_in_bed", 30)
	world.ui.close()
	world.exit_house(true)
	# a villager at home in the evening
	GS.hour = 18.0
	world.enter_house("rumah_kades", true)
	var on: Node3D = world.interior.owner_node()
	if on:
		tp(on.global_position.x + 0.3, on.global_position.z + 1.4, Vector3(0, 0, -1))
	await shot("house_villager", 40)
	world.exit_house(true)
	# more room types
	GS.hour = 10.0
	for t in ["panggung", "limas", "bata", "pondok", "jahit", "dapur"]:
		var hid := _house_of_type(t)
		if hid == "":
			continue
		world.enter_house(hid, true)
		var ip: Vector3 = world.interior.door_pos()
		tp(ip.x + 0.4, ip.z - 0.6, Vector3(0, 0, -1))
		await shot("interior_" + t, 40)
		world.exit_house(true)
	await shot("after_exit", 30)
	# a rare catch with its rarity card, then the collection
	GS.hour = 23.0
	find_fish_spot(j, "sea")
	fi.fast = true
	fi.force_fish = "ikan_raja_sawit"
	world.start_fishing()
	var tw := 0.0
	while fi.phase != "bite" and tw < 4.0:
		await get_tree().process_frame
		tw += get_process_delta_time()
	fi.press()
	fi.cursor = fi.zone_c
	fi.press()
	await wait(0.5)
	await shot("fish_catch_ssr", 2)
	GS.hour = 9.0
	for id in ["ikan_nila", "ikan_napoleon", "ikan_patin", "ikan_todak", "ikan_bandeng"]:
		GS.catch_fish(id)
	await wait(3.5)
	world.ui.show_bag("ikan_raja_sawit")
	await shot("bag_rarity", 20)
	world.ui.close()
	world.ui.show_fish_collection("ikan_raja_sawit")
	await shot("fish_collection", 20)
	world.ui.show_fish_collection("ikan_kerapu")
	await shot("fish_collection_unknown", 10)
	world.ui.close()


# ------------------------------------------------------------------ soundtrack (sfx.gd)
func _music_check() -> void:
	## context tracks, crossfades, voice ducking, stingers and the music toggle; the
	## fades are stepped by hand (Sfx._process) so the check is quick and deterministic
	var S: Node = Sfx
	for n in ["title", "day", "evening", "night", "indoor", "rare", "newday"]:
		check(ResourceLoader.exists("res://assets/audio/music_%s.ogg" % n), "music_%s.ogg" % n)
	var mb := AudioServer.get_bus_index("Music")
	var ab := AudioServer.get_bus_index("Ambience")
	check(mb != -1 and ab != -1, "Music and Ambience buses")

	var settle := func(sec: float) -> void:
		for i in int(sec / 0.25):
			S._process(0.25)
	var audible := func() -> Array:
		var out := []
		for i in S._decks.size():
			if S._decks[i].playing and S._decks[i].volume_db > S.MUSIC_DB - 3.0:
				out.append(S._deck_track[i])
		return out
	S._update_context()
	settle.call(2.0)
	check(S.current_track() == "title" and audible.call() == ["title"], "title music on the title screen %s" % [audible.call()])
	world.start_game(false)
	world.ui.close()
	for c in [[8.0, "day"], [17.6, "evening"], [21.0, "night"], [12.0, "day"]]:
		GS.hour = c[0]
		S._update_context()
		S._process(0.5)
		var mid := 0
		for d in S._decks:
			if d.playing:
				mid += 1
		check(mid == 2, "%s: two decks crossfading (%d)" % [c[1], mid])
		settle.call(S.XFADE + 0.5)
		check(audible.call() == [c[1]], "%.1f h -> %s music %s" % [c[0], c[1], audible.call()])
	world.inside = "rumah_juragan"
	S._update_context()
	settle.call(S.XFADE + 0.5)
	check(audible.call() == ["indoor"], "indoor music inside a house %s" % [audible.call()])
	world.inside = ""
	S._update_context()
	settle.call(S.XFADE + 0.5)
	check(audible.call() == ["day"], "back outside -> day %s" % [audible.call()])
	# voice ducking: music -7 dB, ambience -4 dB, both back afterwards
	world.ui.close()
	settle.call(1.0)
	var m0 := AudioServer.get_bus_volume_db(mb)
	var a0 := AudioServer.get_bus_volume_db(ab)
	S.duck_voice(true)
	settle.call(0.5)
	check(absf(AudioServer.get_bus_volume_db(mb) - (m0 - 7.0)) < 0.3 and absf(AudioServer.get_bus_volume_db(ab) - (a0 - 4.0)) < 0.3,
		"voice ducks music/ambience: %.1f / %.1f dB" % [AudioServer.get_bus_volume_db(mb) - m0, AudioServer.get_bus_volume_db(ab) - a0])
	S.duck_voice(false)
	settle.call(0.5)
	check(absf(AudioServer.get_bus_volume_db(mb) - m0) < 0.05 and absf(AudioServer.get_bus_volume_db(ab) - a0) < 0.05, "voice duck released")
	# stingers duck the loop and hand it back
	S.stinger("rare")
	check(S._stinger.playing and str(S._stinger.stream.resource_path).ends_with("music_rare.ogg"), "rare-catch stinger plays")
	settle.call(0.5)
	check(audible.call().is_empty(), "loop ducked under the stinger")
	settle.call(4.0)
	check(audible.call() == ["day"], "loop back after the stinger %s" % [audible.call()])
	GS.sleep()
	world.ui.close()
	check(S._stinger.playing and str(S._stinger.stream.resource_path).ends_with("music_newday.ogg"), "new-day jingle when the day starts")
	# the music toggle
	S.set_music(false)
	settle.call(1.0)
	var any := false
	for d in S._decks:
		any = any or d.playing
	check(not any and S.current_track() == "", "music off stops every deck")
	S.set_music(true)
	settle.call(2.5)
	check(audible.call().size() == 1, "music back on %s" % [audible.call()])
	print("music check: %s (%d failed)" % ["OK" if _fails == 0 else "FAILED", _fails])
	await wait(0.5)   # let the audio thread pick up the last play() calls before quitting


# ------------------------------------------------------------------ voice acting (voice.gd)
func _voice_check() -> void:
	## Every line of the voice manifest resolves to a clip in its own speaker's voice,
	## every bank exists, the game's real dialog paths never fall back to silence, and
	## speaking a line starts its clip on the Voice bus (the native file path).
	var bad: Array = Voice.check_manifest()
	for b in bad.slice(0, 12):
		print("  unresolved: ", b)
	check(bad.is_empty(), "every manifest line has its own clip (%d unresolved)" % bad.size())
	var idx: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/voice_index.json"))
	var missing: Array = []
	var clips := 0
	var nfiles := 0
	for cid in idx["banks"]:
		clips += idx["banks"][cid]["clips"].size()
		for f in idx["banks"][cid]["files"]:
			nfiles += 1
			if not FileAccess.file_exists("res://voices/" + str(f)):
				missing.append(f)
	check(missing.is_empty(), "%d characters / %d bank files / %d clips on disk %s" % [idx["banks"].size(), nfiles, clips, missing])
	var r := Voice.resolve("player", "Kamu", "Masih jam 10:20. Yakin mau tidur sekarang?")
	check(r["char"] == "player" and r["kind"] == "template", "clock line -> the hour's clip %s" % r)
	r = Voice.resolve("petani", "Pak Tarno", "Pohon dewasa di kebun saya: 7. Utang saya ke Juragan: Rp 1.234.567. Bunganya kok cepat sekali naiknya ya...")
	check(r["char"] == "petani" and r["kind"] == "template", "open-ended debt line -> generic clip %s" % r)
	r = Voice.resolve("ibu", "Bu Sari", "Kalimat baru yang belum pernah direkam!")
	check(r["char"] == "ibu" and r["kind"] == "bark", "unknown line -> the speaker's own bark %s" % r)
	r = Voice.resolve("petani", "Warga", "Permisi, Juragan. Lewat, lewat...")
	check(r["char"] == "warga_petani" and r["kind"] == "line", "passer-by voice by portrait %s" % r)
	r = Voice.resolve("preman", "Orang Asing", "Minggir!")
	check(r["kind"] != "none", "unknown speaker falls back to a portrait voice %s" % r)
	# the real dialog paths (as in the logic scenario) resolve to exact or template clips
	for k in Voice.stats:
		Voice.stats[k] = 0
	world.start_game(false)
	await wait(0.4)
	var node: Node = get_tree().root.get_node_or_null("VoicePlayer")
	check(node != null and Voice.bank_ready("hq"), "HQ bank loaded from voices/")
	var p: AudioStreamPlayer = node.player if node else null
	check(p != null and p.bus == "Voice", "voice player on the Voice bus")
	check(p != null and p.playing and Voice.is_speaking(), "the intro phone call is spoken")
	var pos0: float = p.get_playback_position() if p else 0.0
	await wait(0.6)
	var pos1: float = p.get_playback_position() if p else 0.0
	print("  intro clip position %.2f -> %.2f s" % [pos0, pos1])
	check(p != null and p.playing and pos1 > pos0, "the clip advances")
	world.ui.close()
	check(p != null and not p.playing and not Voice.is_speaking(), "closing the dialog stops the voice")
	var d: Node = world.deals
	GS.money = 60000000
	GS.inv["surat"] = 3
	GS.upgrades["preman"] = 2
	d.rng.seed = 3
	for vid in GS.VILLAGERS:
		d.talk(vid)
		await wait(0.05)
		world.ui.close()
		d._chat(vid)
		world.ui.close()
		d.land_menu(vid)
		world.ui.close()
		d._offer_franchise(vid)
		world.ui.close()
	d._buy_fair("kakek")
	world.ui.close()
	d._lowball("ibu")
	world.ui.close()
	d._fraud("nenek")
	world.ui.close()
	d._bribe_kades("kades", 5500000)
	world.ui.close()
	d._sign_franchise("petani")
	world.ui.close()
	d.plasma_menu("petani")
	world.ui.close()
	GS.upgrades["mesin"] = true
	GS.add_item("minyak", 30)
	for vid in GS.VILLAGERS:
		d._sell_oil(vid)
		world.ui.close()
	d._extort("somad")
	world.ui.close()
	d._hire_villager("kakek")
	world.ui.close()
	d._seize_for_debt("petani")
	world.ui.close()
	for eid in d.EXTRAS:
		d.talk_extra(eid)
		world.ui.close()
	d.talk_extra("anak")
	world.ui.close()
	for i in world.walkers.size():
		d.talk_walker(i)
		world.ui.close()
	d.open_warung()
	world.ui.close()
	d.open_calo()
	world.ui.close()
	GS.hour = 10.3
	d._sleep()
	world.ui.close()
	for ev in ["demo", "wartawan", "harga_naik", "hujan"]:
		GS.pending_events = [ev]
		d.run_morning_events()
		world.ui.close()
	print("  voice lines resolved: ", Voice.stats)
	check(int(Voice.stats["none"]) == 0 and int(Voice.stats["bark"]) == 0,
		"every dialog of the game plays its own clip (none=%d, bark=%d)" % [Voice.stats["none"], Voice.stats["bark"]])
	# a villager on the native path: bank loads, the line plays, ducking follows
	d.talk("dullah")
	await wait(0.4)
	check(Voice.bank_ready("dullah") and p.playing, "villager greeting plays (Kakek Dullah)")
	world.ui.close()
	Voice.enabled = false
	d.talk("dullah")
	await wait(0.2)
	check(not p.playing, "'Suara warga: Mati' silences dialog")
	world.ui.close()
	Voice.enabled = true
	print("voice check: %s (%d failed)" % ["OK" if _fails == 0 else "FAILED", _fails])


# ------------------------------------------------------------------ nature ambience (ambience.gd)
func _land_near(x: float, z: float, r := 12.0) -> Vector2:
	## a walkable, free spot at or near (x, z)
	var rr := 0.0
	while rr <= r:
		var n := maxi(1, int(rr * 2.0))
		for i in n:
			var a := TAU * i / n
			var px := x + cos(a) * rr
			var pz := z + sin(a) * rr
			if world.is_walkable(px, pz) and world.is_free(px, pz, 0.4):
				return Vector2(px, pz)
		rr += 1.0
	return Vector2(x, z)


func _ambience_check() -> void:
	## Teleports to typical places at day and at night, prints the ambience mix heard
	## there (dB per loop, -80 = silent) and checks that it follows the place: the river
	## at its bank, the surf at the beach, the forest bed in the forest, muffled indoors.
	var A: Node = world.ambience
	check(A != null, "ambience node exists")
	var frames := 0
	while not A.geo_ready and frames < 600:
		await get_tree().process_frame
		frames += 1
	check(A.geo_ready, "island analysed over %d frames" % frames)
	for n in ["sea", "river", "lake", "forest", "field", "village", "night", "frogs", "bird_kutilang", "bird_takur",
			"frog_a", "tokek", "owl", "rooster", "chicken", "splash_a", "tonggeret"]:
		check(ResourceLoader.exists("res://assets/audio/amb_%s.ogg" % n), "amb_%s.ogg" % n)
	var inf: Dictionary = A.info
	print("  island: %d coast, %d river bank, %d lagoon/pond bank points (analysed in %.0f ms)" % [inf["coast_points"],
		inf["river_points"], inf["pool_points"], inf.get("island_ms", 0.0)])
	check(int(inf["coast_points"]) > 200 and int(inf["river_points"]) > 100 and int(inf["pool_points"]) > 5, "sea / river / lagoon shores found")
	world.start_game(false)
	world.ui.close()
	var jr: Array = world.walk_rects[0] if world.walk_rects.size() > 0 else [73, 13, 73, 13]
	# the jetty's far end: the end of its long side that is over deeper water
	var ja := Vector2(jr[0] + 0.8, (jr[1] + jr[3]) * 0.5) if jr[2] - jr[0] > jr[3] - jr[1] else Vector2((jr[0] + jr[2]) * 0.5, jr[1] + 0.8)
	var jb := Vector2(jr[2] - 0.8, (jr[1] + jr[3]) * 0.5) if jr[2] - jr[0] > jr[3] - jr[1] else Vector2((jr[0] + jr[2]) * 0.5, jr[3] - 0.8)
	var jetty := ja if world.terrain_height(ja.x, ja.y) < world.terrain_height(jb.x, jb.y) else jb
	var br: Array = world.bridges[0]
	var spots := [
		["river bank", _land_near(83, -40)],
		["bridge", Vector2(br[0], br[1])],
		["beach", _land_near(0, 123, 4.0)],
		["jetty", jetty],
		["forest", _land_near(-80, 100)],
		["village", _land_near(0, 6)],
		["kebun (open)", _land_near(-80, 72)],
	]
	var beds: Array = A.BEDS.keys()
	var rows := {}
	# --dwell=<s>: stay that long at each place (to listen, or to record the mix with
	# --write-movie; the "[listen]" lines give each place's start in movie seconds)
	var dwell := 0.0
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--dwell="):
			dwell = float(a.get_slice("=", 1))
	var listen := func(label: String) -> void:
		if dwell > 0.0:
			print("[listen] %s frame %d" % [label, Engine.get_process_frames()])
			await wait(dwell)
	var head := "  %-16s" % "place"
	for b in beds:
		head += "%8s" % b
	head += "   sea m  riv m  lag m  trees  vill  lowpass"
	for hour in [10.0, 21.5]:
		GS.hour = hour
		await get_tree().process_frame
		await get_tree().process_frame
		for s in spots:
			var at: Vector2 = s[1]
			tp(at.x, at.y)
			await get_tree().process_frame
			A.snap()
			rows["%s %s" % [s[0], "day" if hour < 12.0 else "night"]] = _amb_row(A)
			await listen.call("%s %s" % [s[0], "day" if hour < 12.0 else "night"])
		# inside the player's house (heard from its door, muffled)
		world.enter_house("rumah_juragan", true)
		await get_tree().process_frame
		A.snap()
		rows["house %s" % ("day" if hour < 12.0 else "night")] = _amb_row(A)
		await listen.call("house %s" % ("day" if hour < 12.0 else "night"))
		var door: Vector3 = world.door_points["rumah_juragan"]
		world.exit_house(true)
		tp(door.x, door.z)
		await get_tree().process_frame
		A.snap()
		rows["house door %s" % ("day" if hour < 12.0 else "night")] = _amb_row(A)
	print("ambience mix (dB per loop as heard; -80 = silent):")
	print(head)
	for k in rows:
		var r: Dictionary = rows[k]
		var line := "  %-16s" % k
		for b in beds:
			line += "%8.1f" % r[b]
		line += "  %6.0f %6.0f %6.0f  %5.2f %5.2f  %s" % [minf(r["d_sea"], 999), minf(r["d_river"], 999), minf(r["d_pool"], 999),
			r["forest_density"], r["near_houses"], "ON %.0f Hz" % r["cutoff"] if r["lowpass"] else "off"]
		print(line)
	var R := func(k: String, b: String) -> float: return float(rows[k][b])
	check(R.call("river bank day", "river") > -12.0 and R.call("river bank day", "river") > R.call("village day", "river") + 15.0,
		"river loud at its bank (%.1f dB) and quiet in the village (%.1f dB)" % [R.call("river bank day", "river"), R.call("village day", "river")])
	check(R.call("bridge day", "river") > -12.0, "river under the bridge (%.1f dB)" % R.call("bridge day", "river"))
	check(R.call("beach day", "sea") > -8.0 and R.call("beach day", "sea") > R.call("river bank day", "sea") + 12.0
		and R.call("beach day", "sea") > R.call("house door day", "sea") + 20.0, "surf loud at the beach (%.1f dB)" % R.call("beach day", "sea"))
	check(R.call("beach day", "sea") > R.call("beach day", "river"), "at the beach the sea is louder than the river")
	check(R.call("jetty day", "lake") > -12.0, "lapping water at the jetty (%.1f dB)" % R.call("jetty day", "lake"))
	check(R.call("forest day", "forest") > -8.0 and R.call("forest day", "forest") > R.call("village day", "forest") + 12.0
		and R.call("forest day", "forest") > R.call("beach day", "forest") + 6.0, "forest bed in the forest (%.1f dB)" % R.call("forest day", "forest"))
	check(R.call("village day", "village") > -10.0 and R.call("village day", "village") > R.call("forest day", "village") + 6.0, "village bed in the village")
	check(R.call("forest night", "forest") <= -79.0 and R.call("forest night", "night") > -14.0, "at night the day birds stop and the crickets start")
	check(R.call("river bank night", "frogs") > R.call("village night", "frogs") + 6.0, "frogs by the water at night")
	check(bool(rows["house day"]["lowpass"]) and not bool(rows["house door day"]["lowpass"]), "low-pass on only inside the house")
	for b in ["village", "field"]:
		check(R.call("house day", b) < R.call("house door day", b) - 6.0, "%s quieter inside the house" % b)
	# the water emitters are on the right side: river bank spot is west of the river
	tp(spots[0][1].x, spots[0][1].y)
	A.snap()
	var rp: Vector3 = A._players["river"].global_position
	check(rp.x > spots[0][1].x, "river emitter east of the west bank (%.1f > %.1f)" % [rp.x, spots[0][1].x])
	# players actually start (streams load) and stop again when silent
	GS.hour = 10.0
	await get_tree().process_frame
	tp(spots[2][1].x, spots[2][1].y)
	A.snap()
	await get_tree().process_frame
	check(A._players["sea"].playing and A._players["sea"].stream != null, "the surf loop plays at the beach")
	# one-shots: force every scheduler once and see a 3D emitter start
	for k in A._timers:
		A._timers[k] = 0.0
	tp(spots[4][1].x, spots[4][1].y)
	A.snap()
	A._tick_shots(0.1)
	var started: Array = []
	for sp in A._shots:
		if sp.playing:
			started.append(str(sp.stream.resource_path).get_file().get_basename())
	check(started.any(func(n): return n.begins_with("amb_bird_")), "a bird calls from a tree in the forest %s" % [started])
	# cost of one analysis (10 Hz)
	var t0 := Time.get_ticks_usec()
	for i in 20:
		A._analyse()
	print("  analysis: %.2f ms" % ((Time.get_ticks_usec() - t0) / 20000.0))
	print("ambience check: %s (%d failed)" % ["OK" if _fails == 0 else "FAILED", _fails])
	await wait(0.3)


func _amb_row(A: Node) -> Dictionary:
	var r := {}
	for b in A.BEDS:
		r[b] = A.level_db(b)
	for k in ["d_sea", "d_river", "d_pool", "forest_density", "lowpass", "cutoff"]:
		r[k] = A.info.get(k, 0.0)
	r["near_houses"] = A.info.get("village", 0.0)
	return r
