class_name FacesCheck
extends RefCounted
## Autotest scenario "faces" (run through scripts/debug/autotest.gd):
##   xvfb-run -a godot --path game --rendering-driver opengl3 -- --autotest=faces --shots=<dir>
## Lines up every character model (and a spread of villager variants) on a road in the
## island light and films them: a front close-up of the line, head close-ups, the game
## camera over the line, and the real villagers in a hamlet (game camera).

const MODELS := ["char_player", "char_kakek", "char_ibu", "char_kades", "char_nenek", "char_pemuda",
	"char_petani", "char_anak", "char_preman", "char_calo", "char_petugas", "char_buruh"]


static func _line(world: Node, items: Array, origin: Vector3, gap: float) -> Array:
	var out: Array = []
	for i in items.size():
		var it = items[i]
		var model: String = it if it is String else it[0]
		var n := ModelLib.instance(model, false)
		world.add_child(n)
		var x := origin.x + (i - (items.size() - 1) * 0.5) * gap
		n.global_position = Vector3(x, world.height_at(x, origin.z), origin.z)
		if not (it is String):
			CharLook.apply(n, model, it[1])
		var ap := n.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if ap and ap.has_animation("idle"):
			ap.play("idle")
			ap.seek(randf() * 2.0, true)
		out.append(n)
	return out


static func run(at: Node) -> void:
	var world: Node = at.world
	var tree: SceneTree = at.get_tree()
	world.start_game(false)
	world.ui.close()
	GS.hour = 10.0
	var ug: Node3D = world.get("undergrowth")
	if ug:
		ug.visible = false
	at.tp(8, 14)
	world.player.visible = false
	var origin := Vector3(8, 0, 8.2)
	var nodes := _line(world, MODELS, origin, 0.75)
	var cam := Camera3D.new()
	cam.fov = 30.0
	world.add_child(cam)
	cam.current = true
	var hz := origin.z
	var hy: float = world.height_at(origin.x, hz)
	# 1. the whole line from the front, a bit above eye level
	cam.global_position = Vector3(origin.x, hy + 1.6, hz + 9.0)
	cam.look_at(Vector3(origin.x, hy + 0.6, hz), Vector3.UP)
	await at.shot("faces_line", 30)
	# 2. head close-ups, three at a time
	for k in range(0, MODELS.size(), 3):
		var c: Vector3 = nodes[k + 1].global_position
		cam.global_position = c + Vector3(0, 1.15, 2.6)
		cam.look_at(c + Vector3(0, 0.82, 0), Vector3.UP)
		await at.shot("faces_close_%d" % (k / 3), 12)
	# 3. the game camera over the line
	cam.current = false
	world.camera.current = true
	at.tp(origin.x, origin.z + 0.5)
	await at.shot("faces_game_cam", 30)
	for n in nodes:
		n.queue_free()
	# 4. villager variants (CharLook) of the shared base models
	var vs: Array = []
	for i in 14:
		var base: String = ["char_ibu", "char_petani", "char_kakek", "char_pemuda", "char_buruh", "char_nenek", "char_anak"][i % 7]
		vs.append([base, "v%d" % i])
	world.camera.current = false
	cam.current = true
	nodes = _line(world, vs, origin, 0.72)
	cam.global_position = Vector3(origin.x, hy + 1.8, hz + 10.5)
	cam.look_at(Vector3(origin.x, hy + 0.6, hz), Vector3.UP)
	await at.shot("faces_variants", 30)
	for k in [2, 7, 11]:
		var c: Vector3 = nodes[k].global_position
		cam.global_position = c + Vector3(0, 1.1, 2.4)
		cam.look_at(c + Vector3(0, 0.8, 0), Vector3.UP)
		await at.shot("faces_variant_close_%d" % k, 12)
	for n in nodes:
		n.queue_free()
	cam.current = false
	world.camera.current = true
	if ug:
		ug.visible = true
	world.player.visible = true
	# 5. the real villagers in their hamlets (game camera)
	for vid in ["ibu", "somad", "wati"]:
		var npc: Node3D = world.npcs[vid]
		at.tp(npc.global_position.x, npc.global_position.z + 1.5)
		await at.shot("faces_npc_" + vid, 40)
	# 6. talking (the villager turns to the player and looks up towards the camera), game
	# camera pulled in to ~10 m
	var d0: float = world.cam_distance
	world.cam_distance = 10.0
	for vid in ["wati", "somad", "lastri"]:
		var npc: Node3D = world.npcs[vid]
		at.tp(npc.global_position.x, npc.global_position.z + 1.6, Vector3(0, 0, -1))
		await at.wait(0.3)
		world.deals.talk(vid)
		await at.shot("faces_talk_" + vid, 50)
		world.ui.close()
	world.cam_distance = d0
	cam.queue_free()
	await tree.process_frame
