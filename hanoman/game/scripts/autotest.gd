extends Node
## Headless smoke test / screenshot tour:  godot --path . -- --autotest [--shots=DIR]
## Walks through title -> hub -> run rooms, fights with scripted inputs, and
## prints errors. With --shots, saves screenshots along the way.

var shots := ""
var t := 0.0
var step := 0
var main: Node


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			shots = a.split("=")[1]
			DirAccess.make_dir_recursive_absolute(shots)
	main = get_parent()
	G.meta.seen = {"intro": true, "boss_intro": true, "kijang_intro": true}
	_run()


func _shot(name: String) -> void:
	if shots == "":
		return
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png("%s/%s.png" % [shots, name])
	print("shot ", name)


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec, true, false, true).timeout


func _press(action: String) -> void:
	Input.action_press(action)
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release(action)


func _fight(sec: float) -> void:
	var end := Time.get_ticks_msec() + int(sec * 1000)
	var p: Player = main.player
	while Time.get_ticks_msec() < end:
		var es: Array = main.enemies()
		if es.is_empty() and main.room and main.room.is_clear:
			break
		if not es.is_empty():
			var e: Node3D = es[0]
			var to: Vector3 = e.global_position - p.global_position
			p.touch_move = Vector2(to.x, to.z).normalized() if to.length() > 2.0 else Vector2.ZERO
			p.facing = to.normalized()
			await _press("attack")
			if randf() < 0.1:
				await _press("special")
			if randf() < 0.03:
				await _press("cast")
			if randf() < 0.05:
				await _press("dash")
		G.run.hp = max(float(G.run.hp), 30.0)
		await _wait(0.05)
	p.touch_move = Vector2.ZERO


## Freeze-frame each of Hanoman's skills mid-effect (VFX review).
func _showcase() -> void:
	var p: Player = main.player
	for e in main.enemies():
		e.invuln = 999.0
	var es: Array = main.enemies()
	var aim := Vector3(0, 0, -1)
	if not es.is_empty():
		aim = (es[0].global_position - p.global_position)
		aim.y = 0
		aim = aim.normalized()
	p.aim = aim
	p.facing = aim
	for step_i in 3:
		await _press("attack")
		await _wait(0.13 if step_i < 2 else 0.3)
		await _shot("fx_swing%d" % (step_i + 1))
		await _wait(0.25)
	await _wait(0.4)
	p.prana = 3.0
	p.aim = aim
	await _press("special")
	await _wait(0.16)
	await _shot("fx_laser")
	await _wait(0.6)
	await _press("cast")
	await _wait(0.35)
	await _shot("fx_ajian")
	await _press("dash")
	await _wait(0.08)
	await _shot("fx_dash")
	for e in main.enemies():
		e.invuln = 0.0
	await _wait(1.0)


func _run() -> void:
	while not Hf.loaded:
		await _wait(0.5)
	await _wait(1.0)
	await _shot("00_title")
	# press start
	main.ui.overlay.get_child(0).queue_free()
	main.area = "hub"
	main.go_hub()
	await _wait(2.5)
	await _shot("01_hub")
	main.ui.dialog([["rama", "Uji dialog: Hanoman, bawalah cincinku ke Alengka."]], func(): pass)
	await _wait(1.5)
	await _shot("02_dialog")
	for k in 2:
		if main.ui._advance.is_valid():
			main.ui._advance.call()
	main.start_run()
	await _wait(2.0)
	await _shot("03_room1")
	if OS.get_cmdline_user_args().has("--fxshots"):
		await _showcase()
	if OS.get_cmdline_user_args().has("--overview"):
		for k in 3:
			var r: Arena = main.room
			var c := r.bounds.get_center()
			var span := maxf(r.bounds.size.x, r.bounds.size.y * 1.6)
			main.cam_override = true
			main.cam.global_position = Vector3(c.x, span * 1.25, c.y + span * 0.35)
			main.cam.look_at(Vector3(c.x, 0, c.y))
			main.cam.far = 400.0
			await _wait(0.6)
			await _shot("ov_room%d" % k)
			main.cam_override = false
			main.cam.far = 120.0
			if k < 2:
				G.run.room = 0
				main.enter_room({"type": "kepeng"})
				await _wait(2.5)
	await _wait(1.5)
	await _fight(40.0)
	await _wait(1.0)
	await _shot("04_room1_clear")
	# pick up reward if boon
	for n in get_tree().get_nodes_in_group("interactable"):
		if n.get_meta("active", true) and String(n.get_meta("prompt", "")).begins_with("Terima"):
			n.interact()
			await _wait(0.8)
			await _shot("05_boon_menu")
			main.ui._menu_buttons[0].pressed.emit()
	await _wait(0.5)
	var rooms := [5, 9]
	for target in rooms:
		G.run.room = target - 1
		main.enter_room({"type": "kepeng"})
		await _wait(3.0)
		await _shot("06_room%d_start" % target)
		await _fight(6.0)
		await _shot("07_room%d_fight" % target)
	# victory flow: finish the bosses
	for b in main.enemies():
		b.take_hit(99999.0, b.global_position, 0.0)
	await _wait(7.0)
	await _shot("08_victory_dialog")
	for i in 8:
		for k in 2:
			if main.ui._advance.is_valid():
				main.ui._advance.call()
		await _wait(0.3)
	await _wait(1.0)
	await _shot("09_victory_screen")
	main.go_hub()
	await _wait(2.0)
	# death flow
	main.start_run()
	await _wait(3.0)
	G.run.death_defy = 0
	main.player.invuln = 0.0
	main.player.take_hit(999.0, main.player.global_position + Vector3(1, 0, 0))
	await _wait(2.5)
	await _shot("10_death")
	print("AUTOTEST DONE")
	get_tree().quit()
