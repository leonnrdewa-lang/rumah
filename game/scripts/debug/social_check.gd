class_name SocialCheck
extends RefCounted
## Autotest for village life (scripts/world/social.gd and its modules):
## - logic(at): called from the "logic" scenario (autotest._features_logic) through its
##   check(): calendar & festivals (sponsor, panjat pinang, balap karung, pasar malam,
##   kondangan, pengajian, villagers gathering), friendship (hearts, gifts, requests,
##   tips, harga sahabat, reports to the Satgas, the Warga panel), the journalist (arrive,
##   leads, newspaper, bribe, fake tour, truth), protests (crowd, signs, ganti rugi,
##   negotiation, preman, ignoring) and the LSM, house decor (catalog, grid, move /
##   rotate / store, aquarium, upgrades), badges, the endings and save / load (old saves
##   included). The game state is restored afterwards.
## - shots(at): the "social" screenshot scenario:
##     xvfb-run -a godot --path game --rendering-driver opengl3 -- --autotest=social --shots=<dir>


static func _restore(backup: String) -> void:
	var f := FileAccess.open(GS.SAVE_PATH, FileAccess.WRITE)
	f.store_string(backup)
	f.close()
	GS.load_game()


static func logic(at: Node) -> void:
	var world: Node = at.world
	var ui: Node = world.ui
	var d: Node = world.deals
	var S: Node = world.social
	GS.save_game()
	var backup := FileAccess.get_file_as_string(GS.SAVE_PATH)
	ui.close()
	await at.get_tree().process_frame
	at.check(S != null and S.rel != null and S.decor != null, "village life hub exists")
	GS.money = 90000000
	GS.hour = 9.0
	# --- calendar
	var F: Node = S.fest
	at.check(F.date_text(1) == "10 Agustus" and F.date_text(8) == "17 Agustus" and F.date_text(23) == "1 September", "calendar: day 1 = 10 Agustus")
	at.check("tujuhbelas" in F.events_on(8) and "pasar" in F.events_on(10) and "kondangan" in F.events_on(9) and "pengajian" in F.events_on(11), "festival calendar")
	var rep_lines: Array = []
	var day0: int = GS.day
	GS.day = 8
	F.day_roll(rep_lines)
	at.check(str(rep_lines).contains("17 Agustus") and "festival" in GS.pending_events, "morning report announces Tujuhbelasan")
	GS.pending_events.clear()
	# --- relationships
	var R: Node = S.rel
	at.check(R.hearts("kakek") == 1 and R.f("kakek") == 30.0, "friendship starts at 30 (1 heart)")
	var f0: float = R.f("kakek")
	GS.villagers["kakek"]["talk_day"] = 0
	d._chat("kakek")
	ui.close()
	at.check(R.f("kakek") == f0 + 5.0, "chatting raises friendship")
	GS.add_item("kopi", 2)
	R.give("kakek", "kopi")
	ui.close()
	at.check(R.f("kakek") == f0 + 5.0 + 16.0 and int(R.rec("kakek")["gift"]) == GS.day, "a liked gift counts double (kopi for Kakek)")
	GS.add_item("tbs", 1)
	var fp: float = R.f("pemuda")
	R.give("pemuda", "tbs")
	ui.close()
	at.check(R.f("pemuda") < fp, "Mas Joko hates a TBS gift")
	R.rec("ibu")["req"] = {"item": "kopi", "n": 1, "text": "test", "due": GS.day + 2, "reward": 50000}
	var fi: float = R.f("ibu")
	var m0: int = GS.money
	at.check(R.fulfil("ibu") and R.rec("ibu")["req"].is_empty() and R.f("ibu") == fi + 15.0 and GS.money == m0 + 50000, "fetch request fulfilled (+15, reward)")
	var q: Dictionary = R.make_request("lastri")
	at.check(not q.is_empty() and int(q["due"]) == GS.day + 3, "new request made")
	d.talk("lastri")
	await at.get_tree().process_frame
	await at.get_tree().process_frame
	var texts: Array = ui._dialog_choices.map(func(c): return str(c.get("text", "")))
	at.check("Kasih hadiah" in texts and "Soal permintaanmu..." in texts, "talk menu has gift + request: " + str(texts))
	at.check(ui.modal != null and ui.modal.find_child("HeartsRow", true, false) != null, "hearts shown next to the villager's name")
	ui.close()
	R.rec("somad")["f"] = 90.0
	d.land_menu("somad")
	texts = ui._dialog_choices.map(func(c): return str(c.get("text", "")))
	at.check(texts[0] == "Beli harga sahabat", "best friend offers 'harga sahabat'")
	ui.close()
	var kind: String = R.give_tip("somad")
	ui.close()
	at.check(kind != "" and int(R.rec("somad")["tip"]) == GS.day, "secret tip (%s)" % kind)
	R.on_event("evict", "rt")
	at.check(R.hearts("rt") == 0 and int(R.rec("rt")["wronged"]) == 1, "eviction makes an enemy")
	var heat0: float = GS.heat
	var reported := false
	for k in 40:
		var rl: Array = []
		R.day_roll(rl)
		if str(rl).contains("[LAPOR]"):
			reported = true
			break
	at.check(reported and GS.heat > heat0, "enemies report you to the Satgas")
	R.show_panel()
	await at.get_tree().process_frame
	at.check(ui.modal != null and ui.modal.name == "WargaPanel" and ui.modal.find_children("warga_*", "", true, false).size() == GS.VILLAGERS.size(), "Warga panel lists every villager")
	ui.close()
	# --- the journalist
	var J: Node = S.jour
	GS.heat = 80.0
	GS.pending_events.clear()
	J.day_roll([])
	at.check("jurnalis" in GS.pending_events, "high Kecurigaan brings the journalist")
	d.run_morning_events()
	at.check(J.active() and J.npc != null and ui._dialog_choices.size() == 4, "journalist arrives with 4 choices")
	ui.finish_typing()
	ui._choose(ui._dialog_choices[1])   # hindari
	at.check(J.active() and J.lead() == 0, "hindari: he keeps digging")
	for k in 3:
		J.day_roll([])
	at.check("koran" in GS.pending_events, "3 leads: the story runs")
	var rep0: float = GS.rep
	heat0 = GS.heat
	GS.pending_events.erase("koran")
	GS.pending_events.push_front("koran")
	d.run_morning_events()
	at.check(ui.modal != null and ui.modal.has_meta("koran") and GS.rep < rep0 and GS.heat > heat0 and not J.active(), "Koran Sukamakmur headline popup")
	at.check(S.stat("headlines") == 1, "headline counted")
	ui.close()
	var hushed := false
	for k in 12:
		J.arrive()
		ui.close()
		if J.bribe():
			hushed = true
			break
		ui.close()
	ui.close()
	at.check(hushed and int(J.s()["hushed"]) >= 1 and not J.active(), "bribe hushes the journalist")
	J.arrive()
	ui.close()
	J._tour_score = 0
	J.tour_step(1, 1)
	ui.close()
	J.tour_step(2, 1)
	ui.close()
	J.tour_step(3, 1)
	at.check(int(J.s()["fooled"]) == 1 and ui.modal != null and str(ui.modal.get_meta("koran", "")).begins_with("ADVERTORIAL"), "fake garden tour fools him")
	ui.close()
	J.arrive()
	ui.close()
	var honest0: int = S.stat("honest")
	J.truth()
	at.check(S.stat("honest") == honest0 + 1 and not J.active() and ui.modal != null and ui.modal.has_meta("koran"), "telling the truth")
	ui.close()
	# --- protests
	var P: Node = S.prot
	R.on_event("fraud_ok", "kakek")
	R.rec("kakek")["f"] = 10.0
	GS.rep = -30.0
	GS.pending_events.clear()
	P.ps()["last"] = -9
	P.day_roll([])
	at.check("demo" in GS.pending_events and P.grievers().size() >= 2, "wronged villagers plan a demo")
	GS.pending_events.erase("demo")
	GS.pending_events.push_front("demo")
	d.run_morning_events()
	await at.get_tree().process_frame
	var who: Array = P.ps()["who"]
	at.check(P.active() and who.size() >= 2 and P.crowd.size() >= 2 and P.signs.size() >= 4 and not P.banners.is_empty(), "protest crowd with signs & banner")
	var kd: Vector3 = world.door_points["kantor"]
	at.check(world.npcs[who[0]].anchor.distance_to(kd) < 9.0, "protesters stand in front of the Kantor")
	ui.close()
	d.open_kantor()
	var has_meet := false
	for b in ui.modal.find_children("*", "Label", true, false):
		if (b as Label).text == "Temui pendemo di depan kantor":
			has_meet = true
	ui.close()
	at.check(has_meet, "Kantor menu: meet the protesters")
	m0 = GS.money
	var cost: int = P.comp_cost()
	P.compensate()
	at.check(not P.active() and P.crowd.is_empty() and GS.money == m0 - cost and int(P.ps()["comp"]) == 1, "ganti rugi ends the demo")
	at.check(world.npcs[who[0]].anchor.distance_to(kd) > 2.0 or who[0] == "", "protesters go home")
	var nego := false
	for k in 15:
		R.on_event("fraud_ok", "kakek")
		R.on_event("evict", "rt")
		P.start_protest()
		ui.close()
		for vid in P.ps()["who"]:
			R.rec(vid)["f"] = 40.0
		if P.negotiate():
			nego = true
			break
	at.check(nego and int(P.ps()["nego"]) >= 1, "negotiation can end a demo")
	if P.active():
		P.compensate()
	R.on_event("evict", "rt")
	R.on_event("fraud_ok", "kakek")
	P.start_protest()
	ui.close()
	GS.heat = 40.0
	heat0 = GS.heat
	at.check(P.active(), "a new demo starts")
	P.preman()
	at.check(not P.active() and GS.heat > heat0, "preman break up the demo (Kecurigaan up)")
	R.on_event("evict", "rt")
	R.on_event("fraud_ok", "kakek")
	P.start_protest()
	ui.close()
	at.check(P.active(), "another demo starts")
	P.ignore()
	GS.heat = 40.0
	heat0 = GS.heat
	P.day_roll([])
	at.check(not P.active() and int(P.ps()["ignored"]) == 1 and GS.heat > heat0, "an ignored demo costs Kecurigaan")
	world.refresh_all()
	# the LSM
	GS.stats["cleared"] = 40
	GS.day = 12
	P.ls()["last"] = -9
	var came := false
	for k in 40:
		GS.pending_events.clear()
		P.day_roll([])
		if "lsm" in GS.pending_events:
			came = true
			break
	at.check(came, "the LSM comes when the forest goes")
	GS.pending_events.clear()
	P.lsm_arrive()
	ui.close()
	at.check(P.lsm_active() and P.lsm_npc != null and P.lsm_banners.size() == 2, "LSM: Mbak Laras + banners")
	GS.heat = 40.0
	heat0 = GS.heat
	var sign0: int = int(P.ls()["sign"])
	var lr: Array = []
	P.day_roll(lr)
	GS.pending_events.clear()
	at.check(int(P.ls()["sign"]) > sign0 and GS.heat > heat0 and str(lr).contains("[LSM]"), "LSM petition adds Kecurigaan daily")
	GS.energy = 100.0
	var tp0: int = S.stat("tobat_pts")
	P.lsm_commit()
	at.check(not P.lsm_active() and P.lsm_npc == null and S.stat("tobat_pts") == tp0 + 1, "planting trees ends the campaign")
	# --- festivals
	GS.day = 8
	GS.hour = 10.0
	GS.rep = 0.0
	F.refresh()
	at.check(F._built.has("tujuhbelas") and F.is_open("tujuhbelas"), "Tujuhbelasan decorations up and open")
	F._gather("tujuhbelas")
	var sp: Vector3 = F.spot("tujuhbelas")
	var g: Array = F.gathered("tujuhbelas")
	at.check(g.size() >= 5 and world.npcs[g[0]].anchor.distance_to(sp) < 5.0, "villagers gather at the event (%d)" % g.size())
	var rep1: float = GS.rep
	at.check(F.sponsor("tujuhbelas") and GS.rep > rep1 and not F.sponsor("tujuhbelas"), "sponsoring (once a day)")
	F.open("tujuhbelas")
	await at.get_tree().process_frame
	at.check(ui.modal != null and ui.modal.has_meta("closable") and ui.modal.find_children("*", "Button", true, false).size() >= 3, "festival menu opens")
	ui.close()
	GS.energy = 100.0
	F.pinang_start()
	await at.get_tree().process_frame
	var pin: Control = F.pinang
	at.check(pin != null and ui.modal == pin, "panjat pinang minigame opens")
	for k in 25:
		pin.climb()
	await at.wait(1.2)
	at.check(int(F.fs()["pinang"]) == 1, "panjat pinang won by tapping fast")
	ui.close()
	F.pinang_start()
	await at.get_tree().process_frame
	F.pinang.time_left = 0.05
	await at.wait(1.2)
	at.check(int(F.fs()["pinang"]) == 1 and ui.modal != null, "panjat pinang lost when too slow")
	ui.close()
	at.check(F.karung_finish(5) and int(F.fs()["karung"]) == 1 and not F.karung_finish(1), "balap karung outcome")
	ui.close()
	F._release("tujuhbelas")
	at.check(world.npcs[g[0]].anchor.distance_to(sp) > 1.0, "villagers go back after the event")
	GS.day = 10
	GS.hour = 19.0
	F.refresh()
	at.check(F._built.has("pasar") and F.is_open("pasar") and F._wheel != null, "pasar malam with a bianglala")
	F.lempar()
	ui.close()
	GS.day = 9
	GS.hour = 11.0
	F.refresh()
	var h: String = F.host(9)
	var fh: float = R.f(h)
	F.amplop(h, 100000)
	ui.close()
	at.check(F._built.has("kondangan") and R.f(h) > fh and int(F.fs()["kondangan"]) == 1, "kondangan amplop pleases the host")
	GS.day = 11
	GS.hour = 19.0
	F.refresh()
	rep1 = GS.rep
	F.ngaji()
	ui.close()
	at.check(F._built.has("pengajian") and GS.rep > rep1, "pengajian")
	GS.day = day0
	GS.hour = 9.0
	F.refresh()
	# --- house decor
	var D: Node = S.decor
	at.check(D.level() == 0 and D.hs()["placed"].size() == 2, "rumah mungil starts with a rug and a chair")
	at.check(D.buy("sofa") and D.buy("akuarium") and D.buy("tv") and D.hs()["placed"].size() == 5, "furniture bought and placed")
	at.check(not D.buy("meja_billiar"), "biliar needs the gedongan")
	GS.catch_fish("ikan_napoleon")
	GS.catch_fish("ikan_arwana")
	world.enter_house("rumah_juragan", true)
	await at.get_tree().process_frame
	var furn: Array = world.interior._room.find_children("Furn_*", "", false, false)
	at.check(furn.size() == 5, "furniture in the room (%d)" % furn.size())
	at.check("ikan_arwana" in D.aquarium_fish() and "ikan_napoleon" in D.aquarium_fish(), "aquarium shows the SR/SSR catch")
	var k_kursi := -1
	var k_tv := -1
	for k in D.hs()["placed"].size():
		if D.hs()["placed"][k]["id"] == "kursi_rotan":
			k_kursi = k
		if D.hs()["placed"][k]["id"] == "tv":
			k_tv = k
	var free: Vector2i = D.find_spot("kursi_rotan", 0, k_kursi)
	at.check(free.x >= 0 and D.move_to(k_kursi, free.x, free.y) and int(D.hs()["placed"][k_kursi]["c"]) == free.x, "furniture moves on the grid")
	at.check(not D.fits("sofa", 0, 0, 0) or not D.fits("sofa", -1, 0, 0), "grid keeps furniture off the walls / bed")
	at.check(D.rotate(k_kursi) and int(D.hs()["placed"][k_kursi]["rot"]) == 1, "furniture rotates")
	var tv_rot: bool = D.rotate(k_tv)
	at.check(not tv_rot or D.footprint(D.hs()["placed"][k_tv]) == Vector2i(1, 2), "a rotated 2x1 piece takes 1x2 cells")
	at.check(D.store(k_tv) and int(D.hs()["own"].get("tv", 0)) == 1 and D.place_from_store("tv"), "store in gudang and place again")
	D.show_editor()
	await at.get_tree().process_frame
	at.check(ui.modal != null and ui.modal.has_meta("decor") and ui.modal.find_child("Grid", true, false) != null, "decor editor with grid")
	ui.close()
	at.check(D.upgrade() and D.level() == 1 and world.interior.half == D.LEVELS[1]["half"], "upgrade to Rumah Kayu rebuilds the room")
	at.check(world._bed_item["pos"].distance_to(world.interior.bed_world()) < 0.01, "bed spot follows the new room")
	D.upgrade()
	D.upgrade()
	at.check(D.level() == 3 and D.level_name() == "Rumah Gedongan" and not D.upgrade(), "Rumah Gedongan is the top")
	at.check(D.buy("meja_billiar") and D.buy("patung_singa"), "gedongan furniture")
	at.check(world.interior.is_walkable(world.interior.door_pos().x, world.interior.door_pos().z), "door still walkable")
	var bp: Vector3 = world.interior.bed_pos()
	at.check(world.interior.is_walkable(bp.x, bp.z), "bed side walkable")
	world.exit_house(true)
	# --- badges & endings
	var E: Node = S.endings
	E.check_badges(true)
	at.check(E.unlocked("panen_perdana") and E.unlocked("masuk_koran") and E.unlocked("gedongan") and E.unlocked("juara_pinang") and E.unlocked("lolos_wartawan"), "badges unlock")
	at.check(E.BADGES.size() >= 20, "%d badges" % E.BADGES.size())
	E.show_book()
	await at.get_tree().process_frame
	at.check(ui.modal != null and ui.modal.find_children("badge_*", "", true, false).size() == E.BADGES.size(), "Buku Prestasi shows every badge")
	ui.close()
	GS.heat = 70.0
	var calo: Array = []
	E.calo_items(calo)
	at.check(calo.size() == 1 and calo[0]["enabled"], "Bang Jeki sells the escape when the heat is on")
	var kan: Array = []
	S.add_stat("tobat_pts", 2)
	GS.rep = 40.0
	E.kantor_items(kan)
	at.check(kan.size() == 1 and kan[0]["enabled"], "tobat available after good deeds")
	# save / load
	GS.save_game()
	var lvl: int = D.level()
	var fk: float = R.f("kakek")
	var placed_n: int = D.hs()["placed"].size()
	var exp_n: int = int(J.s()["exposed"])
	GS.load_game()
	await at.get_tree().process_frame
	at.check(D.level() == lvl and is_equal_approx(R.f("kakek"), fk) and D.hs()["placed"].size() == placed_n and int(J.s()["exposed"]) == exp_n, "save roundtrip keeps village life")
	# an old save without the "social" block
	var raw = JSON.parse_string(FileAccess.get_file_as_string(GS.SAVE_PATH))
	raw.erase("social")
	var fo := FileAccess.open(GS.SAVE_PATH, FileAccess.WRITE)
	fo.store_string(JSON.stringify(raw))
	fo.close()
	at.check(GS.load_game() and GS.social.is_empty(), "old save loads")
	await at.get_tree().process_frame
	at.check(R.hearts("kakek") == 1 and D.level() == 0 and not J.active() and not P.active(), "old save: village life defaults")
	# endings (tobat, OTT, kabur) - each ends the game; restored after
	S.add_stat("tobat_pts", 2)
	GS.rep = 40.0
	E.do_tobat()
	await at.get_tree().process_frame
	at.check(world.state == "over" and ui.modal != null and ui.modal.get_meta("ending", "") == "tobat" and "tobat" in E.endings_seen(), "tobat ending screen")
	ui.close()
	_restore(backup)
	world.state = "play"
	GS.stats["bribes"] = 5
	GS.heat = 95.0
	var ott := false
	for k in 30:
		E.day_roll([])
		if not GS.game_active:
			ott = true
			break
	await at.get_tree().process_frame
	at.check(ott and ui.modal != null and ui.modal.get_meta("ending", "") == "kpk", "Operasi Tangkap Tangan -> Ditangkap KPK")
	ui.close()
	_restore(backup)
	world.state = "play"
	GS.money = 30000000
	GS.heat = 75.0
	E.confirm_kabur()
	ui.finish_typing()
	ui._choose(ui._dialog_choices[0])
	await at.get_tree().process_frame
	at.check(ui.modal != null and ui.modal.get_meta("ending", "") == "kabur" and GS.money == 15000000, "kabur ke luar negeri ending")
	ui.close()
	_restore(backup)
	world.state = "play"
	GS.money = 40000000
	ui.show_ending()
	await at.get_tree().process_frame
	at.check(ui.modal != null and ui.modal.get_meta("ending", "") == "raja" and ui.modal.find_child("ShareButton", true, false) != null, "Raja Sawit ending screen with share button")
	ui.close()
	# --- restore the game as it was
	_restore(backup)
	world.state = "play"
	world.refresh_all()
	S.refresh_visuals()
	ui.close()


# ------------------------------------------------------------------ screenshots
static func _shot(at: Node, name: String, frames := 20) -> void:
	await at.shot(name, frames)


static func shots(at: Node) -> void:
	var world: Node = at.world
	var ui: Node = world.ui
	var S: Node = world.social
	world.start_game(false)
	ui.close()
	GS.money = 90000000
	GS.energy = 100.0
	# --- Tujuhbelasan (17 Agustus = day 8)
	GS.day = 8
	GS.hour = 10.0
	S.refresh_visuals()
	await at.wait(1.2)
	var sp: Vector3 = S.fest.spot("tujuhbelas")
	S.fest._gather("tujuhbelas", true)
	at.tp(sp.x + 0.5, sp.z + 3.5, Vector3(0, 0, -1))
	await at.wait(2.5)
	await _shot(at, "festival_tujuhbelas", 30)
	S.fest.open("tujuhbelas")
	await _shot(at, "festival_menu", 15)
	ui.close()
	S.fest.pinang_start()
	for k in 6:
		S.fest.pinang.climb()
	await _shot(at, "panjat_pinang", 10)
	ui.close()
	# --- pasar malam at night
	GS.day = 10
	GS.hour = 20.5
	S.refresh_visuals()
	await at.wait(1.5)
	sp = S.fest.spot("pasar")
	S.fest._gather("pasar", true)
	at.tp(sp.x + 0.5, sp.z + 3.8, Vector3(0, 0, -1))
	await at.wait(2.5)
	await _shot(at, "pasar_malam", 30)
	# --- kondangan
	GS.day = 9
	GS.hour = 11.0
	S.refresh_visuals()
	await at.wait(1.5)
	sp = S.fest.spot("kondangan")
	S.fest._gather("kondangan", true)
	at.tp(sp.x + 0.5, sp.z + 5.0, Vector3(0, 0, -1))
	await at.wait(3.0)
	await _shot(at, "kondangan", 30)
	GS.day = 2
	GS.hour = 9.0
	S.refresh_visuals()
	# --- protest in front of the Kantor
	for vid in ["kakek", "nenek", "pemuda", "romlah"]:
		S.rel.on_event("fraud_ok", vid)
	world.deals._evict("pemuda")
	ui.close()
	S.prot.start_protest()
	ui.close()
	var kd: Vector3 = world.door_points["kantor"]
	at.tp(kd.x + 0.5, kd.z + 8.0, Vector3(0, 0, -1))
	await at.wait(3.0)
	S.prot._chant_t = 0.0
	await at.wait(0.3)
	await _shot(at, "protest_crowd", 20)
	S.prot.meet()
	await _shot(at, "protest_dialog", 30)
	ui.close()
	S.prot.compensate()
	# --- the LSM
	S.prot.lsm_arrive()
	await _shot(at, "lsm_dialog", 30)
	ui.close()
	var ln: Node3D = S.prot.lsm_npc
	at.tp(ln.global_position.x + 0.5, ln.global_position.z + 4.0, Vector3(0, 0, -1))
	await at.wait(1.5)
	await _shot(at, "lsm_banners", 20)
	S.prot.lsm_donate()
	# --- the journalist
	GS.heat = 80.0
	S.jour.arrive()
	await _shot(at, "journalist_arrives", 30)
	ui.close()
	var jn: Node3D = S.jour.npc
	at.tp(jn.global_position.x + 0.4, jn.global_position.z + 2.2, Vector3(0, 0, -1))
	await at.wait(1.5)
	await _shot(at, "journalist_npc", 20)
	S.jour.publish("gusur")
	await _shot(at, "koran_headline", 20)
	ui.close()
	# --- relationships
	S.rel.rec("ibu")["f"] = 75.0
	S.rel.make_request("ibu")
	at.tp(world.npcs["ibu"].global_position.x + 0.4, world.npcs["ibu"].global_position.z + 1.8, Vector3(0, 0, -1))
	world.deals.talk("ibu")
	await _shot(at, "talk_hearts", 35)
	ui.close()
	S.rel.rec("somad")["f"] = 95.0
	S.rel.rec("wati")["f"] = 62.0
	S.rel.show_panel()
	await _shot(at, "warga_panel", 15)
	ui.close()
	# --- the house
	for id in ["ikan_arwana", "ikan_raja_sawit", "ikan_napoleon", "ikan_pari", "ikan_todak"]:
		GS.catch_fish(id)
	var D: Node = S.decor
	for id in ["sofa", "akuarium", "tv", "monstera", "rak_buku", "kipas"]:
		D.buy(id)
	world.enter_house("rumah_juragan", true)
	GS.hour = 15.0
	var dp: Vector3 = world.interior.door_pos()
	at.tp(dp.x, dp.z - 0.6, Vector3(0, 0, -1))
	await at.wait(1.0)
	await _shot(at, "house_mungil", 25)
	D.upgrade()
	D.upgrade()
	for id in ["lampu_hias", "karaoke", "foto_juragan"]:
		D.buy(id)
	dp = world.interior.door_pos()
	at.tp(dp.x, dp.z - 0.6, Vector3(0, 0, -1))
	await at.wait(1.0)
	await _shot(at, "house_bata", 25)
	D.upgrade()
	for id in ["patung_singa", "meja_billiar", "dispenser", "kulkas"]:
		D.buy(id)
	dp = world.interior.door_pos()
	at.tp(dp.x, dp.z - 0.6, Vector3(0, 0, -1))
	await at.wait(1.0)
	await _shot(at, "house_gedongan", 25)
	# close-up of the aquarium
	for k in D.hs()["placed"].size():
		if D.hs()["placed"][k]["id"] == "akuarium":
			var p: Dictionary = D.hs()["placed"][k]
			var fp: Vector2i = D.footprint(p)
			var c: Vector3 = world.interior.to_world(D.cell_center(int(p["c"]), int(p["r"]), fp.x, fp.y))
			at.tp(c.x, c.z + 1.6, Vector3(0, 0, -1))
	await at.wait(0.8)
	world.cam_rig.global_position = world.player.global_position
	await _shot(at, "house_aquarium", 20)
	D.sel = 0
	D.show_editor()
	await _shot(at, "decor_editor", 15)
	ui.close()
	world.exit_house(true)
	# --- badges & endings
	S.endings.check_badges(true)
	S.endings.show_book()
	await _shot(at, "buku_prestasi", 15)
	ui.close()
	for e in ["raja", "kpk", "tobat", "kabur"]:
		S.endings.show_screen(e, "Satgas Sawit menggerebek kantormu untuk ketiga kalinya." if e == "kpk" else "")
		await _shot(at, "ending_" + e, 40)
		ui.close()
	var img: Image = await S.endings.render_card("raja")
	if img and not img.is_empty():
		img.save_png("%s/%02d_result_card.png" % [at.shots_dir, at._i])
		at._i += 1
		print("[shot] result_card ", img.get_size())
	else:
		print("[shot] result_card FAILED")
	# phone portrait: the Warga panel and an ending
	get_window_size(at, Vector2i(412, 915))
	await at.wait(0.5)
	S.rel.show_panel()
	await _shot(at, "phone_warga", 15)
	ui.close()
	S.endings.show_screen("tobat")
	await _shot(at, "phone_ending", 40)
	ui.close()
	get_window_size(at, Vector2i(1280, 720))
	await at.wait(0.3)


static func get_window_size(at: Node, sz: Vector2i) -> void:
	at.get_window().size = sz
