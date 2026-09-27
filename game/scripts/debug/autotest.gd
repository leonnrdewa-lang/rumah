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


func tp(x: float, z: float, face := Vector3(0, 0, 1)) -> void:
	world.player.global_position = Vector3(x, world.height_at(x, z), z)
	world.player.facing = face
	world.cam_rig.global_position = world.player.global_position


func _run() -> void:
	match scenario:
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
		"tour":
			world.start_game(false)
			world.ui.close()
			var spots := [[-3, 34], [-14, 3], [8, 5], [50, -2], [56, 22], [-44, 36], [-20, -40], [18, -40], [22, 34], [66, 13], [0, -50], [30, 45]]
			for s in spots:
				tp(s[0], s[1])
				await shot("tour_%d_%d" % [s[0], s[1]], 25)
