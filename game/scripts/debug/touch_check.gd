## Touch-control check on a scaled "phone" window (joystick drag + action button tap):
## xvfb-run -a godot --path game --rendering-driver opengl3 -s res://scripts/debug/touch_check.gd
extends SceneTree
func _initialize():
	root.size = Vector2i(1830, 824)
	var main = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)
	current_scene = main
	_go.call_deferred(main)

func _find_world(n: Node) -> Node:
	if n.has_method("try_action") and n.has_method("start_game"):
		return n
	for c in n.get_children():
		var w = _find_world(c)
		if w: return w
	return null

func _touch(pos: Vector2, pressed: bool, idx := 0):
	var e := InputEventScreenTouch.new()
	e.index = idx; e.pressed = pressed; e.position = pos
	root.push_input(e)

func _drag(pos: Vector2, idx := 0):
	var e := InputEventScreenDrag.new()
	e.index = idx; e.position = pos
	root.push_input(e)

func _go(main):
	for i in 10: await process_frame
	var world = _find_world(root)
	world.start_game(false)
	world.ui.close()
	for i in 5: await process_frame
	var ui = world.ui
	# force touch mode through a first touch far from controls
	_touch(Vector2(1500, 150), true); _touch(Vector2(1500, 150), false, 0)
	for i in 5: await process_frame
	var sc: float = root.get_final_transform().get_scale().x
	print("content scale ", root.content_scale_factor, " final ", sc, " joy_home ", ui._joy_home, " vis ", ui.touch.visible, " joyvis ", ui.joy_base.visible)
	var p0: Vector3 = world.player.global_position
	var home_win: Vector2 = ui._joy_home * sc
	_touch(home_win, true)
	for k in range(1, 8):
		_drag(home_win + Vector2(k * 12, 0) * sc)
		await process_frame
	for i in 40: await process_frame
	print("touch_vec ", world.player.touch_vec, " moved ", world.player.global_position - p0)
	_touch(home_win, false)
	await process_frame
	print("after release touch_vec ", world.player.touch_vec)
	# action button: go to the ripe palm and tap
	world.player.global_position = Vector3(-17, world.height_at(-17, 30), 30)
	world.player.facing = Vector3(0, 0, -1)
	world.cam_rig.global_position = world.player.global_position
	for i in 20: await process_frame
	var tbs0 = root.get_node("GS").inv["tbs"]
	var ab: Vector2 = (ui.action_btn.position + ui.action_btn.size * 0.5) * sc
	print("target ", world.target.get("prompt", Callable()).call() if world.target.has("prompt") else world.target.keys(), " btn at ", ab)
	var hit := [0]
	world.set_process(false)
	world.target = {"act": func(): hit[0] += 1, "prompt": func(): return "stub"}
	_touch(ab, true); await process_frame; _touch(ab, false)
	await process_frame
	print("action taps reached try_action: ", hit[0])
	for i in 60: await process_frame
	print("tbs ", tbs0, " -> ", root.get_node("GS").inv["tbs"])
	quit()
