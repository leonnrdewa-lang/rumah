extends Node
## Developer harness: `godot --path game -- --autotest=<scenario> --shots=<dir>`
## Drives the game without input and saves screenshots, for automated checks.

var world: Node
var scenario := "basic"
var shots_dir := "/tmp"
var _i := 0


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
		"logic":
			world.start_game(false)
			world.ui.close()
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
			print("owners: ", GS.parcels.map(func(p): return "%s%s" % [p["owner"], "*" if p["plasma"] else ""]))
			print("controlled=", GS.controlled_parcels(), " heat=", GS.heat, " rep=", GS.rep, " stats=", GS.stats)
			# work the land for a few days
			GS.add_item("bibit", 60)
			GS.add_item("pupuk", 20)
			for day in 8:
				for p in GS.parcels:
					if p["owner"] != "player":
						continue
					for i in 12:
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
					for i in 12:
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
			GS.hour = 8.5
			world.set_quality(false)
			tp(-17, 32.5, Vector3(0, 0, -1))
			await shot("vis_parcel_low", 30)
			world.set_quality(true)
		"pitch":
			# camera tuning: the hero spot at a few pitch / distance pairs
			world.start_game(false)
			world.ui.close()
			world.ui.visible = false
			for pd in [[45.0, 16.0], [50.0, 16.5], [52.0, 17.0], [55.0, 17.0]]:
				world.cam_pitch = pd[0]
				world.cam_distance = pd[1]
				GS.hour = 8.5
				tp(-17.4, 25.4, Vector3(-0.5, 0, -1).normalized())
				await shot("pitch_%d_%d" % [pd[0], pd[1] * 10], 30)
				tp(-3.5, 37.5, Vector3(0, 0, -1))
				await shot("spawn_%d_%d" % [pd[0], pd[1] * 10], 30)
			world.ui.visible = true
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
		"tour":
			world.start_game(false)
			world.ui.close()
			var spots := [[-3, 34], [-14, 3], [8, 5], [50, -2], [56, 22], [-44, 36], [-20, -40], [18, -40], [22, 34], [66, 13], [0, -50], [30, 45]]
			for s in spots:
				tp(s[0], s[1])
				await shot("tour_%d_%d" % [s[0], s[1]], 25)
