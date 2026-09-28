class_name AnimalModelsCheck
extends RefCounted
## Autotest scenario "animals_models" (run through scripts/debug/autotest.gd):
##   xvfb-run -a godot --path game --rendering-driver opengl3 -- --autotest=animals_models --shots=<dir>
## (headless works too, without the screenshots' content).
## Every animal GLB from blender/animals.py is loaded through ModelLib.instance (toon world shader +
## ink outline) and checked: the contract clips are in its AnimationPlayer with the right loop modes,
## the glTF extras (speeds, variants) came through, every surface got the stylised material with an
## outline pass (no foliage shader), the model stands on y = 0 and faces +Z like the villagers,
## triangle budget. Then the animals are posed in the island next to the player and filmed from the
## game camera and from a close camera, playing each clip. Prints "[animals_models] PASS/FAIL".

const SPECIES := ["sapi", "kerbau", "kambing", "ayam", "bebek", "kodok", "kucing", "anjing"]
const CLIPS := ["idle", "walk", "run", "eat", "call"]
const EXTRA := {"kodok": ["hop"], "bebek": ["swim"], "kucing": ["sit"], "anjing": ["wag"]}
const ONE_SHOT := ["call", "hop"]
const TRI_BUDGET := 3000


static func _find_ap(n: Node) -> AnimationPlayer:
	return n.find_child("AnimationPlayer", true, false) as AnimationPlayer


static func _find_skel(n: Node) -> Skeleton3D:
	return n.find_child("Skeleton3D", true, false) as Skeleton3D


static func _extras(n: Node) -> Dictionary:
	var stack: Array[Node] = [n]
	while not stack.is_empty():
		var c: Node = stack.pop_back()
		if c.has_meta("extras"):
			var ex = c.get_meta("extras")
			if ex is Dictionary and (ex as Dictionary).has("species"):
				return ex
		for k in c.get_children():
			stack.append(k)
	return {}


static func check_model(id: String) -> Array:
	## -> [fails (Array of String), info (String)]
	var fails: Array = []
	var n := ModelLib.instance("animal_" + id)
	if n.get_child_count() == 1 and n.get_child(0) is MeshInstance3D and (n.get_child(0) as MeshInstance3D).mesh is BoxMesh:
		n.free()
		return [["%s: model missing (placeholder)" % id], ""]
	var ap := _find_ap(n)
	var clips: Array = CLIPS + EXTRA.get(id, [])
	if ap == null:
		fails.append("%s: no AnimationPlayer" % id)
	else:
		for c in clips:
			if not ap.has_animation(c):
				fails.append("%s: missing clip %s" % [id, c])
				continue
			var a := ap.get_animation(c)
			var want := Animation.LOOP_NONE if c in ONE_SHOT else Animation.LOOP_LINEAR
			if a.loop_mode != want:
				fails.append("%s: clip %s loop_mode %d (want %d)" % [id, c, a.loop_mode, want])
			if a.length < 0.2:
				fails.append("%s: clip %s too short (%.2f s)" % [id, c, a.length])
	var ex := _extras(n)
	if ex.is_empty():
		fails.append("%s: no glTF extras" % id)
	else:
		for k in ["walk_speed", "run_speed", "variants", "call_open"]:
			if not ex.has(k) and not (id == "kodok" and k == "run_speed"):
				fails.append("%s: extras lack %s" % [id, k])
		var vs = JSON.parse_string(str(ex.get("variants", "[]")))
		if not (vs is Array) or (vs as Array).size() < 2:
			fails.append("%s: variants not a list" % id)
	var tris := 0
	var surfaces := 0
	var names := []
	var aabb := AABB()
	var first := true
	for mi in ModelLib.find_meshes(n):
		if mi.mesh == null:
			continue
		var b := mi.mesh.get_aabb()
		aabb = b if first else aabb.merge(b)
		first = false
		for i in mi.mesh.get_surface_count():
			surfaces += 1
			var arr := mi.mesh.surface_get_arrays(i)
			var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
			tris += idx.size() / 3 if idx.size() > 0 else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
			var sm := mi.get_surface_override_material(i) as ShaderMaterial
			var src := mi.mesh.surface_get_material(i)
			var nm: String = src.resource_name if src else "?"
			names.append(nm)
			if not nm.begins_with("Animal"):
				fails.append("%s: surface %d material '%s' not an Animal* material" % [id, i, nm])
			if sm == null or sm.shader != ModelLib.WORLD_SHADER:
				fails.append("%s: surface %s did not get the world toon shader" % [id, nm])
			elif sm.next_pass == null:
				fails.append("%s: surface %s has no ink outline pass" % [id, nm])
			if (mi.mesh.surface_get_format(i) & Mesh.ARRAY_FORMAT_COLOR) == 0:
				fails.append("%s: surface %s has no vertex colours (baked AO)" % [id, nm])
	if tris > TRI_BUDGET:
		fails.append("%s: %d triangles (budget %d)" % [id, tris, TRI_BUDGET])
	if absf(aabb.position.y) > 0.02:
		fails.append("%s: lowest point at y=%.3f (want 0)" % [id, aabb.position.y])
	var skel := _find_skel(n)
	var fwd := 0.0
	if skel == null:
		fails.append("%s: no Skeleton3D" % id)
	else:
		var hb := skel.find_bone("head")
		var hips := skel.find_bone("hips")
		if hb < 0 or hips < 0:
			fails.append("%s: bones head/hips missing" % id)
		else:
			var xf := _rel(skel, n)
			fwd = (xf * skel.get_bone_global_rest(hb).origin).z - (xf * skel.get_bone_global_rest(hips).origin).z
			if fwd <= 0.0:
				fails.append("%s: head is not in front (+Z) of the hips (dz=%.3f)" % [id, fwd])
	var info := "%s: tris=%d surfaces=%d size=(%.2f x %.2f x %.2f) head_dz=%.2f clips=%s walk=%.2fm/s run=%.2fm/s mats=%s" % [
		id, tris, surfaces, aabb.size.x, aabb.size.y, aabb.size.z, fwd,
		ap.get_animation_list() if ap else [], float(ex.get("walk_speed", 0.0)), float(ex.get("run_speed", 0.0)), names]
	n.free()
	return [fails, info]


static func _rel(node: Node3D, root: Node) -> Transform3D:
	var t := Transform3D.IDENTITY
	var c: Node = node
	while c != null and c != root:
		if c is Node3D:
			t = (c as Node3D).transform * t
		c = c.get_parent()
	return t


static func _shot(at: Node, name: String, frames: int) -> void:
	## screenshots need a renderer (xvfb-run ... --rendering-driver opengl3); headless runs only wait
	if DisplayServer.get_name() == "headless":
		for i in frames:
			await at.get_tree().process_frame
		return
	await at.shot(name, frames)


static func run(at: Node) -> void:
	var world: Node = at.world
	var all_fails: Array = []
	for id in SPECIES:
		var r: Array = check_model(id)
		all_fails.append_array(r[0])
		print("[animals_models] ", r[1])
	for f in all_fails:
		print("[animals_models]   FAIL ", f)
	# ---- in the island: a row of animals beside the player, then close-ups of each clip
	world.start_game(false)
	world.ui.close()
	GS.hour = 9.5
	var cx := -3.0
	var cz := 22.0
	at.tp(cx, cz + 3.2, Vector3(0, 0, -1))
	var nodes := {}
	var aps := {}
	var xs := {"kerbau": -4.6, "sapi": -2.5, "kambing": -0.9, "anjing": 0.2, "kucing": 1.0, "ayam": 1.7,
		"bebek": 2.3, "kodok": 2.9}
	for id in SPECIES:
		var n := ModelLib.instance("animal_" + id)
		var x: float = cx + xs[id]
		var z := cz + (0.0 if id in ["kerbau", "sapi", "kambing"] else 0.9)
		n.position = Vector3(x, world.height_at(x, z), z)
		n.rotation.y = deg_to_rad(25.0)
		world.add_child(n)
		nodes[id] = n
		var ex := _extras(n)
		var vs = JSON.parse_string(str(ex.get("variants", "[]")))
		var ap := _find_ap(n)
		aps[id] = ap
		if ap:
			ap.play("idle")
		# the chicken shows the rooster parts only for rooster variants
		if id == "ayam":
			var r := n.find_child("Rooster", true, false) as Node3D
			if r:
				r.visible = false
	await at.wait(0.6)
	await _shot(at, "animals_game_view", 10)
	# a second row with the second colour variant (+ the rooster) to show the tint system
	for id in SPECIES:
		var n := ModelLib.instance("animal_" + id)
		var ex := _extras(n)
		var vs = JSON.parse_string(str(ex.get("variants", "[]")))
		var v: Dictionary = (vs as Array)[1] if vs is Array and (vs as Array).size() > 1 else {}
		for mi in ModelLib.find_meshes(n):
			for i in mi.mesh.get_surface_count():
				var src := mi.mesh.surface_get_material(i)
				var nm: String = src.resource_name if src else ""
				var key := ""
				if nm.begins_with("AnimalFur_"):
					key = "fur"
				elif nm.begins_with("AnimalMark2_"):
					key = "mark2"
				elif nm.begins_with("AnimalMark_"):
					key = "mark"
				if key != "" and v.has(key):
					var m := mi.get_surface_override_material(i)
					mi.set_surface_override_material(i, ModelLib.retuned(m, "var_%s_1" % id,
						{"albedo": Color(str(v[key]))}))
		if id == "ayam":
			var r := n.find_child("Rooster", true, false) as Node3D
			if r:
				r.visible = bool(v.get("rooster", false))
		var x: float = cx + xs[id] + 0.25
		var z := cz - (1.9 if id in ["kerbau", "sapi", "kambing"] else 0.8)
		n.position = Vector3(x, world.height_at(x, z), z)
		n.rotation.y = deg_to_rad(25.0)
		world.add_child(n)
		var ap := _find_ap(n)
		if ap:
			ap.play("idle")
			ap.seek(0.7, true)
		nodes[id + "_2"] = n
	await at.wait(0.3)
	await _shot(at, "animals_game_view_variants", 10)
	# close camera, undergrowth hidden
	var ug: Node3D = world.get("undergrowth")
	if ug:
		ug.visible = false
	var cam := Camera3D.new()
	cam.fov = 40.0
	world.add_child(cam)
	cam.current = true
	var target := Vector3(cx - 0.6, world.height_at(cx, cz) + 0.45, cz - 0.2)
	cam.global_position = target + Vector3(1.2, 2.2, 6.4)
	cam.look_at(target, Vector3.UP)
	for clip in ["idle", "walk", "run", "eat", "call", "extra"]:
		for id in SPECIES:
			for key in [id, id + "_2"]:
				var ap: AnimationPlayer = _find_ap(nodes[key])
				if ap == null:
					continue
				var c: String = clip
				if clip == "extra":
					c = (EXTRA.get(id, ["idle"]) as Array)[0]
				if ap.has_animation(c):
					ap.play(c)
					ap.seek(0.0, true)
		await at.wait(0.33 if clip != "call" else 0.45)
		await _shot(at, "animals_close_%s" % clip, 1)
	if ug:
		ug.visible = true
	cam.queue_free()
	for k in nodes:
		(nodes[k] as Node).queue_free()
	print("[animals_models] %s" % ("PASS" if all_fails.is_empty() else "FAIL (%d)" % all_fails.size()))
