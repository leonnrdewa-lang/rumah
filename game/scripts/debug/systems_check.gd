class_name SystemsCheck
extends RefCounted
## Autotest for the systems round (scripts/systems/, world/weather_fx.gd, ui/systems_ui.gd):
## - logic(at): called from the "logic" scenario (autotest._features_logic) through its
##   check(): seasons & weather, rain growth, land fires (put out / burn / spread /
##   kabut asap), floods, the TBS market + 14-day history + main mata, the gudang
##   (capacity, spoilage, compost, formalin), the crew (roles, pay, satisfaction,
##   strikes, auto-harvest into the gudang), the upgrade tree (bersih / kotor, effects,
##   truck auto-sell, mini oil mill), the menus and save / load (old saves included).
##   The game state is restored afterwards.
## - shots(at): the "systems" screenshot scenario:
##     xvfb-run -a godot --path game --rendering-driver opengl3 -- --autotest=systems --shots=<dir>
##   rain, storm + lightning, dry-season fires + smoke haze, a flooded village, the
##   pabrik menu with the price chart, the workers panel, the upgrade tree, the gudang,
##   the mogok event; prints the frame time with rain + fires on.


static func logic(at: Node) -> void:
	var world: Node = at.world
	var ui: Node = world.ui
	var S = GS.sys
	var W = S.weather
	var M = S.market
	var C = S.crew
	var T = S.tech
	GS.save_game()
	var backup := FileAccess.get_file_as_string(GS.SAVE_PATH)
	var money0: int = GS.money
	GS.money = 50000000
	ui.close()
	# --- seasons
	at.check(W.season(1) == "hujan" and W.season(10) == "hujan" and W.season(11) == "kemarau" and W.season(21) == "hujan", "seasons alternate every 10 days")
	at.check(W.season_day(15) == 5, "season day counter")
	var day0: int = GS.day
	GS.day = 14
	var counts := {}
	var rep: Array = []
	for i in 300:
		W.roll(rep)
		counts[W.today] = int(counts.get(W.today, 0)) + 1
	at.check(not counts.has("badai") and int(counts.get("cerah", 0)) > 120, "dry season: mostly sunny, no storms %s" % counts)
	GS.day = 3
	counts = {}
	for i in 300:
		W.roll(rep)
		counts[W.today] = int(counts.get(W.today, 0)) + 1
	at.check(int(counts.get("hujan", 0)) + int(counts.get("badai", 0)) > 100, "wet season: rainy %s" % counts)
	# --- rain makes palms grow
	var tiles: Array = GS.parcels[0]["tiles"]
	for i in range(6, 16):
		tiles[i] = GS._tile("palm", 0)
	W.today = "badai"
	W.fires.clear()
	S.events.clear()
	rep = []
	W.after_growth(rep)
	var grown := 0
	for i in range(6, 16):
		grown += int(tiles[i]["g"]) + int(tiles[i]["st"]) * 10
	at.check(grown > 0 and str(rep).contains("tumbuh lebih cepat"), "storm rain grows palms (%d steps)" % grown)
	# --- fires: put out
	GS.day = 14
	W.today = "cerah"
	W.fires = [{"pid": 0, "idx": 7, "age": 0}]
	var info: Dictionary = GS.tile_action_info(0, 7)
	at.check(info.get("verb", "") == "Padamkan api!" and info.get("ok", false), "burning tile prompt: " + str(info.get("verb")))
	GS.energy = 100.0
	var kind: String = GS.do_tile_action(0, 7)
	at.check(kind == "padam" and W.fires.is_empty() and GS.energy < 100.0 and W.fires_out >= 1, "Padamkan api puts the fire out")
	world._tile_action(0, 7)   # (nothing burning: a normal tile action, must not crash)
	# --- fires: left burning overnight on your land
	tiles[8] = GS._tile("palm", 1)
	W.fires = [{"pid": 0, "idx": 8, "age": 0}]
	var heat0: float = GS.heat
	S.events.clear()
	rep = []
	W.after_growth(rep)
	at.check(tiles[8]["s"] == "empty", "a fire left burning kills a young palm")
	at.check(GS.heat > heat0 and "kabut_asap" in S.events and W.haze() > 0.5, "fire on your land: heat +%d, kabut asap event, haze %.2f" % [int(GS.heat - heat0), W.haze()])
	# --- fires: rain puts them out
	W.fires = [{"pid": 1, "idx": 3, "age": 0}]
	W.today = "hujan"
	rep = []
	W.after_growth(rep)
	at.check(W.fires.is_empty(), "rain puts land fires out")
	# --- fires start in a long dry spell
	W.today = "cerah"
	W.dry_days = 9
	var started := false
	for i in 40:
		W.fires.clear()
		W._ignite(rep)
		if not W.fires.is_empty():
			started = true
			break
	at.check(started, "dry season starts land fires")
	W.fires.clear()
	# --- floods after clearing a lot of land, in a storm
	var parcels_bak: Array = GS.parcels.duplicate(true)
	for pid in [1, 2, 3]:
		GS.parcels[pid]["owner"] = "player"
		for t in GS.parcels[pid]["tiles"]:
			t["s"] = "empty"
	GS.day = 4
	W.today = "badai"
	var flooded := false
	for i in 30:
		S.events.clear()
		W.flood = ""
		W._flood(rep)
		if W.flood != "":
			flooded = true
			break
	at.check(flooded and "banjir" in S.events, "heavy rain after clearing floods a village (%s)" % W.flood)
	var fl: Node = null
	world.weather_fx._sync_flood()
	fl = world.weather_fx.flood_node()
	at.check(fl != null and fl.is_inside_tree(), "flood water drawn in the village")
	W.flood = ""
	world.weather_fx._sync_flood()
	GS.parcels = parcels_bak
	tiles = GS.parcels[0]["tiles"]
	# --- market
	M.reset()
	GS.tbs_price = 150000
	for i in 20:
		GS.day = 30 + i
		M.new_day(rep)
	at.check(M.history.size() == 14 and int(M.history[-1]) == GS.tbs_price, "14-day price history (%d)" % M.history.size())
	var ok_range := true
	for v in M.history:
		ok_range = ok_range and int(v) >= M.MIN_PRICE and int(v) <= M.MAX_PRICE
	at.check(ok_range, "prices stay in range " + str(M.history))
	GS.tbs_price = 160000
	var heat1: float = GS.heat
	var res: String = M.bribe()
	at.check(res != "" and M.sale_price() == 184000 and GS.heat > heat1, "main mata: +15%% price (%d), heat up" % M.sale_price())
	at.check(M.bribe() == "", "only one bribe a day")
	GS.inv["tbs"] = 4
	world.deals._sell_tbs()
	ui.close()
	at.check(int(GS.inv["tbs"]) == 0, "TBS sold at the bribed price")
	# --- gudang
	M.gudang.clear()
	at.check(M.store(55) == 40 and M.stock() == 40, "gudang holds 40")
	var v0: int = M.value()
	var pupuk0 := int(GS.inv["pupuk"])
	M._spoil(rep)
	at.check(M.value() < v0, "older fruit is worth less (sortasi)")
	for i in 3:
		M._spoil(rep)
	at.check(M.stock() == 0 and int(GS.inv["pupuk"]) == pupuk0 + 10, "TBS rots after 4 days, becomes compost")
	M.store(10)
	var m0: int = GS.money
	var got: int = M.sell_gudang()
	at.check(got > 0 and GS.money == m0 + got and M.stock() == 0, "sell the gudang (%d)" % got)
	# --- upgrades
	for k in GS.upgrades.keys():
		if str(k).begins_with("t_"):
			GS.upgrades.erase(k)
	at.check(not T.unlocked("pupuk") and not T.buy("pupuk", "bersih"), "pupuk premium needs bibit unggul first")
	var heat2: float = GS.heat
	at.check(T.buy("bibit", "kotor") and GS.heat >= heat2 + 9.0 and T.level("bibit") == "kotor", "bibit selundupan: cheap, heat +10")
	at.check(GS.stage_need(0, false) == 1, "bibit unggul: the bibit stage takes 1 day")
	var duds := 0
	for i in 200:
		var t: Dictionary = GS._tile("palm", 0)
		T.on_planted(t)
		if t.get("dud", false):
			duds += 1
	at.check(duds > 10 and duds < 60, "15%% of smuggled seedlings are fakes (%d/200)" % duds)
	at.check(T.buy("bibit", "bersih") and T.level("bibit") == "bersih", "legalise: kotor -> bersih")
	at.check(T.buy("pupuk", "bersih") and T.fert_yield() == 3, "pupuk premium: 3 bunches")
	at.check(T.buy("jalan", "kotor") and T.walk_mult() > 1.3, "jalan kebun: faster walking")
	at.check(T.buy("gudang", "bersih") and M.capacity() == 150, "gudang besar: 150")
	at.check(T.buy("truk", "bersih") and T.buy("pabrik", "kotor"), "truk angkut + pabrik mini")
	# the mini mill
	GS.inv["tbs"] = 2
	M.store(5)
	var oil0 := int(GS.inv["minyak"])
	at.check(T.mill(10) == 7 and int(GS.inv["minyak"]) == oil0 + 28 and int(GS.inv["tbs"]) == 0 and M.stock() == 0, "pabrik mini: 7 TBS -> 28 jerigen")
	at.check(T.sell_oil_agent() == (oil0 + 28) * T.OIL_AGENT_PRICE, "oil sold to the city agent")
	# --- crew
	for w in GS.workers:
		if str(w.get("vid", "")) != "":
			GS.villagers[w["vid"]]["worker"] = false
	GS.workers.clear()
	GS.workers.append({"id": "old", "name": "Buruh harian", "wage": 150000, "vid": ""})   # pre-systems entry
	C.normalize()
	at.check(GS.workers[0]["role"] == "buruh" and is_equal_approx(float(GS.workers[0]["sat"]), 70.0), "old worker entries become buruh panen")
	for i in 6:
		C.hire("buruh")
	at.check(C.count("buruh") == 6 and not C.can_hire("buruh"), "at most 6 buruh")
	at.check(not C.hire("mandor").is_empty() and not C.hire("sopir").is_empty() and GS.workers.size() == 8, "hire mandor + sopir")
	C.set_pay(0)
	at.check(C.target_sat(GS.workers[0]) < 50.0, "low pay -> unhappy (%.0f)" % C.target_sat(GS.workers[0]))
	C.set_pay(2)
	at.check(C.target_sat(GS.workers[0]) >= 95.0, "fair pay -> happy")
	# auto-harvest into the gudang + truck auto-sell
	C.set_pay(1)
	for w in GS.workers:
		w["sat"] = 80.0
	for i in 12:
		tiles[i] = GS._tile("palm", 3)
		tiles[i]["fr"] = true
	M.gudang.clear()
	var lw: Dictionary = C.work(rep)
	at.check(int(lw["harvest"]) >= 12 and M.stock() == int(lw["stored"]) and int(lw["stored"]) > 0, "crew harvests into the gudang (%s)" % str(lw))
	GS.tbs_price = M.average() + 10000
	var sold0: int = T.truck_sold
	rep = []
	T.new_day(rep)
	at.check(T.truck_sold > sold0 and M.stock() == 0, "sopir + truk sell the gudang when the price is good")
	# a strike: very low pay for a few days
	C.set_pay(0)
	C.fire(GS.workers.size() - 2)   # (the mandor makes strikes rarer)
	for w in GS.workers:
		w["sat"] = 10.0
	var struck := false
	GS.rng.seed = 5
	for i in 12:
		S.events.clear()
		rep = []
		C.new_day(rep)
		if C.strike:
			struck = true
			break
	at.check(struck and "mogok" in S.events, "underpaid buruh go on strike")
	var msg: String = C.end_strike("naik")
	at.check(C.pay_level == 1 and not C.strike and msg != "", "naikkan gaji ends the strike")
	# --- menus
	world.deals.open_pabrik()
	at.check(ui.modal != null and ui.modal.find_child("PriceChart", true, false) != null, "pabrik menu shows the price chart")
	ui.close()
	world.sys_ui.open_workers()
	at.check(ui.modal != null and ui.modal.find_children("*", "ProgressBar", true, false).size() >= GS.workers.size(), "workers panel with satisfaction bars")
	ui.close()
	world.sys_ui.open_upgrades()
	at.check(ui.modal != null, "upgrade menu")
	ui.close()
	world.sys_ui.open_gudang()
	at.check(ui.modal != null, "gudang menu")
	ui.close()
	world.deals.open_kantor()
	var labels := ""
	for l in ui.modal.find_children("*", "Label", true, false):
		labels += (l as Label).text + "|"
	at.check(labels.contains("Kelola pekerja") and labels.contains("Upgrade kebun"), "kantor links workers + upgrades")
	ui.close()
	for ev in ["mogok", "kabut_asap", "banjir", "ikan_mati"]:
		var opened: bool = world.sys_ui.run_event(ev)
		at.check(opened and ui.modal != null, "event dialog " + ev)
		ui.close()
	world.sys_ui._sig = ""
	world.sys_ui._refresh()
	at.check(world.sys_ui.wx_label.text.contains("Musim") and world.sys_ui.price_label.text.contains("TBS"), "HUD weather pill: " + world.sys_ui.wx_label.text)
	ui.show_status()
	ui.close()
	# --- a full night with everything on
	GS.day = 12
	GS.heat = 20.0
	GS.workers.clear()
	C.hire("buruh")
	GS.sleep()
	for i in 6:
		ui.close()
	GS.pending_events.clear()
	at.check(GS.day == 13 and M.history.size() >= 1 and GS.game_active, "new day runs every system")
	# --- save / load
	W.today = "badai"
	W.fires = [{"pid": 0, "idx": 2, "age": 1}]
	M.gudang = [[7, 2]]
	C.set_pay(2)
	GS.workers[0]["sat"] = 33.0
	GS.save_game()
	W.reset()
	M.reset()
	C.reset()
	GS.load_game()
	at.check(W.today == "badai" and W.fires.size() == 1 and M.stock() == 7 and C.pay_level == 2
		and is_equal_approx(float(GS.workers[0]["sat"]), 33.0) and T.level("pabrik") == "kotor", "systems survive save / load")
	# an old save (no "sys" block, old worker entries) loads with defaults
	var data = JSON.parse_string(FileAccess.get_file_as_string(GS.SAVE_PATH))
	data.erase("sys")
	for w in data["workers"]:
		w.erase("role")
		w.erase("sat")
		w.erase("base")
	var f := FileAccess.open(GS.SAVE_PATH, FileAccess.WRITE)
	f.store_string(JSON.stringify(data))
	f.close()
	at.check(GS.load_game() and W.today == "cerah" and M.stock() == 0 and GS.workers[0]["role"] == "buruh", "old saves load (systems default)")
	# --- restore the game as it was
	f = FileAccess.open(GS.SAVE_PATH, FileAccess.WRITE)
	f.store_string(backup)
	f.close()
	GS.load_game()
	GS.day = day0
	GS.money = money0
	world.refresh_all()
	ui.close()


# ------------------------------------------------------------------ screenshots
static func _shot(at: Node, name: String, frames: int) -> void:
	if DisplayServer.get_name() == "headless":
		for i in frames:
			await at.get_tree().process_frame
		return
	await at.shot(name, frames)


static func _settle(world: Node) -> void:
	## skip the weather cross-fade
	var fx: Node = world.weather_fx
	var W = GS.sys.weather
	fx.cloud = fx.CLOUD.get(W.today, 0.0)
	fx.rain = fx.RAIN.get(W.today, 0.0)
	fx.haze = W.haze()
	fx._sync_t = 0.0


static func shots(at: Node) -> void:
	var world: Node = at.world
	var ui: Node = world.ui
	var W = GS.sys.weather
	var M = GS.sys.market
	world.start_game(false)
	ui.close()
	GS.hour = 10.0
	GS.money = 30000000
	var pc: Vector3 = world.v3(GS.parcels[0]["center"])
	# 1. rain over the farm
	GS.day = 3
	W.today = "hujan"
	_settle(world)
	at.tp(-17, 30, Vector3(0, 0, -1))
	await _shot(at, "rain", 40)
	# 2. storm with lightning
	W.today = "badai"
	_settle(world)
	await _shot(at, "storm", 20)
	world.weather_fx._flash = 1.0
	await _shot(at, "storm_flash", 2)
	# 3. dry season: land fires + smoke haze
	GS.day = 14
	W.today = "cerah"
	W.dry_days = 7
	W.fires = [{"pid": 0, "idx": 14, "age": 0}, {"pid": 0, "idx": 16, "age": 0}, {"pid": 0, "idx": 9, "age": 0}]
	W.smoke = 0.7
	_settle(world)
	var fc: Vector3 = world.tile_views["0:14"].global_position
	at.tp(fc.x + 1.5, fc.z + 3.0, Vector3(0, 0, -1))
	await at.wait(1.5)
	world._update_target()
	await _shot(at, "fire_smoke", 30)
	var t0 := Time.get_ticks_usec()
	for i in 60:
		await at.get_tree().process_frame
	print("[systems] frame time with rain off, 3 fires + haze: %.2f ms" % ((Time.get_ticks_usec() - t0) / 60000.0))
	# put one out
	var tv: Node3D = world.tile_views["0:14"]
	at.tp(tv.global_position.x, tv.global_position.z + 1.3, Vector3(0, 0, -1))
	await at.wait(0.3)
	world._update_target()
	print("[systems] prompt at the fire: ", world.target.get("prompt", func(): return "").call())
	world.try_action()
	await _shot(at, "fire_put_out", 12)
	W.fires.clear()
	W.smoke = 0.0
	# 4. a flooded village
	GS.day = 5
	W.today = "hujan"
	W.flood = "sukamakmur"
	_settle(world)
	var vc: Vector3 = Vector3(0, 0, 4)
	at.tp(vc.x + 3.0, vc.z + 10.0, Vector3(0, 0, -1))
	await _shot(at, "flood", 30)
	var t1 := Time.get_ticks_usec()
	for i in 60:
		await at.get_tree().process_frame
	print("[systems] frame time with rain + flood: %.2f ms" % ((Time.get_ticks_usec() - t1) / 60000.0))
	W.flood = ""
	W.today = "cerah"
	_settle(world)
	# 5. market: two weeks of prices, the pabrik menu
	var rep: Array = []
	M.reset()
	for i in 14:
		GS.day = 6 + i
		M.new_day(rep)
	GS.inv["tbs"] = 6
	M.store(18)
	var pd: Vector3 = world.door_points.get("pabrik", Vector3(50, 0, -3))
	at.tp(pd.x, pd.z + 1.0, Vector3(0, 0, -1))
	world.deals.open_pabrik()
	await _shot(at, "market_chart", 20)
	ui.close()
	# 6. gudang
	M.gudang = [[6, 3], [9, 1], [8, 0]]
	GS.upgrades["t_gudang"] = "bersih"
	GS.upgrades["t_pabrik"] = "bersih"
	world.sys_ui.open_gudang()
	await _shot(at, "gudang_menu", 20)
	ui.close()
	# 7. workers panel
	for i in 3:
		GS.sys.crew.hire("buruh")
	GS.sys.crew.hire("mandor")
	GS.sys.crew.hire("sopir")
	var sats := [88.0, 52.0, 24.0, 70.0, 64.0]
	for i in GS.workers.size():
		GS.workers[i]["sat"] = sats[i % sats.size()]
	GS.sys.crew.last_work = {"harvest": 14, "stored": 14, "planted": 3, "cleared": 2}
	world.refresh_workers()
	world.sys_ui.open_workers()
	await _shot(at, "workers_panel", 20)
	for sc in ui.modal.find_children("*", "ScrollContainer", true, false):
		(sc as ScrollContainer).scroll_vertical = 100000
	await _shot(at, "workers_panel_rows", 6)
	ui.close()
	# 8. the upgrade tree (a clean one, a dirty one, a locked one)
	GS.upgrades.erase("t_gudang")
	GS.upgrades.erase("t_pabrik")
	GS.upgrades["t_bibit"] = "bersih"
	GS.upgrades["t_jalan"] = "kotor"
	world.sys_ui.open_upgrades()
	await _shot(at, "upgrade_menu", 20)
	ui.close()
	# 9. the morning: report + a strike
	GS.day = 9
	GS.sys.events.clear()
	world.sys_ui.run_event("mogok")
	await at.wait(1.5)
	ui.finish_typing()
	await _shot(at, "mogok_event", 10)
	ui.close()
	# 10. HUD on a portrait phone with rain
	W.today = "hujan"
	_settle(world)
	GS.hour = 17.5
	at.tp(-17, 30, Vector3(0, 0, -1))
	await _shot(at, "rain_dusk", 30)
	# 11. the HUD on a phone held upright
	get_window_size(at, Vector2i(720, 1480))
	await at.wait(0.5)
	ui._layout()
	await _shot(at, "portrait_hud", 20)
	get_window_size(at, Vector2i(1280, 720))
	await at.wait(0.3)
	print("[systems] done")


static func get_window_size(at: Node, sz: Vector2i) -> void:
	at.get_window().size = sz
