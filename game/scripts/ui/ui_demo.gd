extends Node
## UI screenshot scenarios (developer tool, lives with the UI so it does not
## touch the shared autotest):
##   godot --path game --rendering-driver opengl3 --resolution 1280x720 -- --uidemo=dialogs --shots=/tmp/shots
## Scenarios: dialogs (HUD, villager dialog with 4+ choices, speaker change,
## shop menus, morning report, pause, status), touch (shorter, touch layout),
## quick (dialog layouts only), title, layers / layers_touch (lean modal
## layering check on low graphics, ~30 s: run at 1280x720, 915x412, 720x1280;
## drop stand-in PNGs into assets/portraits/ of a test copy to see the
## half-body layout). Each layers shot also prints a line with the modal's
## rect, the HUD pieces left on screen and whether the toasts overlap any
## visible HUD piece or card ("overlap=none" is the pass). Quits when done.

var ui: Node
var scenario := "dialogs"
var shots_dir := "/tmp"
var _i := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--uidemo="):
			scenario = a.get_slice("=", 1)
		elif a.begins_with("--shots="):
			shots_dir = a.get_slice("=", 1)
	await get_tree().process_frame
	await get_tree().process_frame
	await _run()
	await wait(0.6)  # let closing tweens finish before quitting
	get_tree().quit()


func shot(name: String, frames := 20) -> void:
	for i in frames:
		await get_tree().process_frame
	var img := get_viewport().get_texture().get_image()
	img.save_png("%s/%02d_%s.png" % [shots_dir, _i, name])
	_i += 1
	print("[shot] ", name, " ", img.get_size())


func wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func key(k: Key) -> void:
	var ev := InputEventKey.new()
	ev.keycode = k
	ev.physical_keycode = k
	ev.pressed = true
	Input.parse_input_event(ev)
	await get_tree().process_frame
	var up := ev.duplicate()
	up.pressed = false
	Input.parse_input_event(up)
	await get_tree().process_frame


func tp(x: float, z: float, face := Vector3(0, 0, 1)) -> void:
	var w: Node = ui.world
	w.player.global_position = Vector3(x, w.height_at(x, z), z)
	w.player.facing = face
	w.cam_rig.global_position = w.player.global_position


func _run() -> void:
	var w: Node = ui.world
	if scenario.begins_with("layers"):
		await _layers()
		return
	var full := scenario == "dialogs"
	if scenario == "touch":
		ui._touch_mode = true
		ui._layout()
	if scenario != "quick":
		await shot("title", 40)
	if scenario == "title":
		return
	w.start_game(false)
	await wait(2.2)
	await shot("intro_dialog", 5)
	ui.close()
	if scenario == "quick":
		# just the dialog layouts: villager greeting + 6 land choices
		GS.money = 6000000
		GS.inv["surat"] = 1
		GS.upgrades["preman"] = 1
		w.deals.talk("ibu")
		await wait(1.2)
		await shot("talk_greeting", 5)
		await key(KEY_2)
		await wait(1.6)
		await shot("land_choices", 5)
		ui.close()
		return
	# HUD next to a ripe palm: harvest prompt + egrek slot highlighted
	var tv: Node3D = w.tile_views["0:0"]
	tp(tv.global_position.x, tv.global_position.z + 1.3, Vector3(0, 0, -1))
	await shot("hud_harvest", 40)
	print("target=", w.target.get("prompt", func(): return "none").call(), " active slot=", ui.hotbar.active)
	# bush tile -> parang slot
	for idx in (12 if full else 0):
		if GS.parcels[0]["tiles"][idx]["s"] == "bush":
			var tb: Node3D = w.tile_views["0:%d" % idx]
			tp(tb.global_position.x, tb.global_position.z + 1.3, Vector3(0, 0, -1))
			await shot("hud_clear", 30)
			print("active slot=", ui.hotbar.active)
			break
	# villager dialog with 4+ choices
	GS.money = 6000000
	GS.inv["surat"] = 1
	GS.upgrades["preman"] = 1
	GS.stats_changed.emit()
	var npc: Node3D = w.npcs["ibu"]
	tp(npc.global_position.x, npc.global_position.z + 2.0, Vector3(0, 0, -1))
	w.deals.talk("ibu")
	await wait(1.4)
	await shot("talk_greeting", 5)
	await key(KEY_2)  # "Soal kebunmu..."
	await wait(1.6)
	await shot("land_choices", 5)
	print("choices=", ui._dialog_choices.size(), " modal=", ui.modal != null)
	ui.close()
	if not full:
		w.deals.open_warung()
		await shot("shop_warung", 30)
		ui.close()
		GS.sleep()
		await shot("morning", 30)
		return
	# chained lines with a speaker change (player answers the village head)
	w.deals.say("portrait_kades", "Pak Kades Harun", "Surat tanah? Bisa diatur. Semua bisa diatur di desa ini...",
		func(): w.deals.say("portrait_player", "Kamu", "Hmm, berapa 'biaya administrasinya', Pak?"))
	await wait(2.4)
	await key(KEY_E)
	await shot("speaker_change", 3)
	await wait(1.2)
	await shot("speaker_after", 5)
	ui.close()
	await wait(0.4)
	# shops
	w.deals.open_toko()
	await shot("shop_koperasi", 30)
	ui.close()
	w.deals.open_warung()
	await shot("shop_warung", 30)
	ui.close()
	# morning report
	GS.sleep()
	await shot("morning", 30)
	ui.close()
	await wait(0.3)
	GS.pending_events.clear()
	ui.toast("Kebun Bu Sari sekarang milikmu! Tebas semaknya lalu tanam sawit.", "good")
	ui.toast("Misi selesai: Jual TBS ke Pabrik (+Rp 100.000)", "quest")
	await shot("toasts", 20)
	ui.toggle_pause()
	await shot("pause", 20)
	ui.toggle_pause()
	ui.show_status()
	await shot("status", 20)
	ui.close()


func settle(sec := 0.5) -> void:
	## Tweens run on real time: wait them out, then give the GUI two frames.
	await wait(sec)
	await get_tree().process_frame
	await get_tree().process_frame


func snap(name: String) -> void:
	var img := get_viewport().get_texture().get_image()
	img.save_png("%s/%02d_%s.png" % [shots_dir, _i, name])
	_i += 1
	print("[shot] %s %s t=%.1fs fps=%d modal=%s" % [name, img.get_size(), Time.get_ticks_msec() / 1000.0, Engine.get_frames_per_second(), ui.modal.name if ui.modal else "-"])
	_report()


func _report() -> void:
	## Layout facts for the shot: modal rect, which HUD pieces are shown, and
	## whether the toast column stays inside its slot (clear of the meters).
	var shown := []
	for n in ["TopLeft", "TopRight", "Minimap", "Prompts", "Inventory"]:
		var c: Control = ui.hud.get_node(n)
		if c.visible and c.modulate.a > 0.5:
			shown.append(n)
	var line := "   hud=%s" % ",".join(shown)
	if ui.modal:
		var r := Rect2(ui.modal.position, ui.modal.size)
		if ui.modal.has_meta("self_layout"):
			r = Rect2(ui.modal.panel.position, ui.modal.panel.size)
			if ui.prompt_pill.visible:
				line += " hint='%s'" % ui.prompt_label.text
		line += " panel=(%d,%d %dx%d)" % [r.position.x, r.position.y, r.size.x, r.size.y]
	# toasts: the union of the shown pills must stay clear of the visible
	# top HUD pieces (checked against their real rects, 8 px margin)
	var pills := Rect2()
	var n := 0
	for t in ui.toast_box.get_children():
		if t.is_queued_for_deletion() or not t.visible:
			continue
		var pr := Rect2(t.global_position, t.size)
		pills = pr if n == 0 else pills.merge(pr)
		n += 1
	if n > 0:
		var hits := []
		for c in ui._hud_top():
			if c.visible and c.modulate.a > 0.5 and Rect2(c.position, c.size).grow(8.0).intersects(pills):
				hits.append(c.name)
		if ui.modal and not ui.modal.has_meta("self_layout") and Rect2(ui.modal.position, ui.modal.size).intersects(pills):
			hits.append("card")
		var tr: Control = ui.hud.get_node("TopRight")
		line += " toasts=%d pills=(%d,%d %dx%d) right=%d slot=(%d..%d) TopRight.x=%d overlap=%s" % [
			n, pills.position.x, pills.position.y, pills.size.x, pills.size.y, pills.end.x,
			ui._toast_rect().position.x, ui._toast_rect().end.x, tr.position.x, ",".join(hits) if hits else "none"]
	print(line)


func _layers() -> void:
	## Lean modal-layering check (one run per resolution): HUD + prompt, dialog
	## lines (4 / 6 choices, chained speaker change), tall and short shop menus,
	## morning report, status, pause. "layers_touch" forces the touch layout.
	## Low graphics keep llvmpipe runs short; the UI does not depend on it.
	var w: Node = ui.world
	if scenario.ends_with("touch"):
		ui._touch_mode = true
		ui._layout()
	w.set_quality(false)
	w.start_game(false)
	await settle(0.8)
	await snap("intro_dialog")
	ui.close()
	GS.money = 6000000
	GS.inv["surat"] = 1
	GS.upgrades["preman"] = 1
	GS.stats_changed.emit()
	var tv: Node3D = w.tile_views["0:0"]
	tp(tv.global_position.x, tv.global_position.z + 1.3, Vector3(0, 0, -1))
	await settle(0.6)
	await snap("hud_harvest")
	var npc: Node3D = w.npcs["ibu"]
	tp(npc.global_position.x, npc.global_position.z + 2.0, Vector3(0, 0, -1))
	await settle(0.3)
	w.deals.talk("ibu")
	await settle(1.2)
	await snap("talk_greeting")
	ui.finish_typing()
	ui._choose(ui._dialog_choices[1])  # "Soal kebunmu..."
	await settle(1.6)
	await snap("land_choices")
	ui.close()
	w.deals.say("portrait_kades", "Pak Kades Harun", "Surat tanah? Bisa diatur. Semua bisa diatur di desa ini...",
		func(): w.deals.say("portrait_player", "Kamu", "Hmm, berapa 'biaya administrasinya', Pak?"))
	await settle(1.4)
	await snap("say_kades")
	ui.finish_typing()
	ui._choose(ui._dialog_choices[0])
	await settle(0.9)
	await snap("say_player")
	ui.close()
	ui.dialog("portrait_kakek", "Kakek Darman", "Nak, jangan lupa mampir. Kopi di rumah masih ada.",
		[{"text": "Nanti saya mampir, Kek"}, {"text": "Kopinya kopi sachet?", "hint": "energi +12"}, {"text": "Pamit"}])
	await settle(1.2)
	await snap("three_choices")
	ui.close()
	await settle(0.3)
	w.deals.open_toko()
	await settle(0.5)
	await snap("shop_koperasi")
	# a toast raised inside a card, then a fresh one after it closed: both must
	# come back to the HUD slot (they used to stay card-wide over the meters)
	ui.toast("Uangmu kurang!", "bad")
	await settle(0.3)
	await snap("toast_in_card")
	ui.close()
	await settle(0.5)
	await snap("toast_after_card")
	ui.toast("Misi selesai: Jual TBS ke Pabrik (+Rp 100.000)", "quest")
	await settle(0.5)
	await snap("toast_fresh")
	w.deals.open_warung()
	await settle(0.5)
	await snap("shop_warung")
	ui.close()
	GS.sleep()
	await settle(0.5)
	await snap("morning")
	GS.pending_events.clear()
	ui.close()
	await settle(0.3)
	ui.show_status()
	await settle(0.5)
	await snap("status")
	ui.close()
	ui.toggle_pause()
	await settle(0.5)
	await snap("pause")
	ui.toggle_pause()
	ui.toast("Kebun Bu Sari sekarang milikmu! Tebas semaknya lalu tanam sawit.", "good")
	await settle(0.6)
	await snap("toast_hud")
