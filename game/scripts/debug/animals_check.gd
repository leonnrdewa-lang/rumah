class_name AnimalsCheck
extends RefCounted
## Autotest scenario "animals" (run through scripts/debug/autotest.gd):
##   xvfb-run -a godot --path game --rendering-driver opengl3 -- --autotest=animals --shots=<dir>
## (headless works too, without the screenshots).
## The animals of scripts/world/animals.gd: counts per species; nobody spawned inside a
## building, fence, tree or the water (ducks on the water, frogs and buffalo at its edge);
## a few in-game minutes later still nobody there; walk/run playback matches the ground
## speed (no foot sliding); a player running at a flock scatters it, a dog trots after a
## passing player, petting ("Elus") plays the call with its sound and a heart; the frame
## cost. Screenshots from the game camera (and a closer one): a cattle herd, goats and
## chickens by the houses, ducks on the river, frogs on a bank at night, a cat and a dog
## in the village, the pet. Prints "[animals] PASS" / "FAIL (n)".

static var fails: Array = []


static func _check(ok: bool, what: String) -> void:
	if not ok:
		fails.append(what)
		print("[animals]   FAIL ", what)


static func _shot(at: Node, name: String, frames: int) -> void:
	## screenshots need a renderer (xvfb-run ... --rendering-driver opengl3); headless runs only wait
	if DisplayServer.get_name() == "headless":
		for i in frames:
			await at.get_tree().process_frame
		return
	await at.shot(name, frames)


static func _placed_ok(A: Node, a) -> String:
	## "" when the animal stands where it may, else why not
	var p: Vector3 = a.node.position
	var w: Node = A.world
	var th: float = w.terrain_height(p.x, p.z)
	match a.id:
		"bebek":
			if A.water_ok(p.x, p.z, 0.02) or (A.land_ok(p.x, p.z, 0.0, false) and A.near_water(p.x, p.z, 4.0)):
				return ""
			return "duck neither on the water nor on a bank (h=%.2f)" % th
		"kerbau":
			if A.land_ok(p.x, p.z, 0.0, false) or (th > w.water_level - 0.4 and w.is_free(p.x, p.z, 0.0)):
				return ""
			return "buffalo in deep water or an obstacle (h=%.2f)" % th
	if th < w.water_level + 0.05:
		return "in the water (h=%.2f)" % th
	if not w.is_free(p.x, p.z, 0.0):
		return "inside an obstacle"
	return ""


static func _all_placed(A: Node, when: String) -> int:
	var bad := 0
	for a in A.animals:
		if not a.node.visible and a.night_only:
			continue
		var why := _placed_ok(A, a)
		if why != "":
			bad += 1
			_check(false, "%s %s at (%.1f, %.1f) %s: %s" % [when, a.id, a.node.position.x, a.node.position.z, a.state, why])
	return bad


static func _view(at: Node, target: Vector3, dist := 4.0) -> void:
	## the player on dry, free ground about `dist` m south of target (the game camera looks
	## north over the player's head), facing it; the camera snaps there
	var w: Node = at.world
	var best := target + Vector3(0, 0, dist)
	var bs := INF
	for i in range(-16, 17):
		for j in range(0, 34):
			var q := target + Vector3(i * 0.5, 0.0, 1.1 + j * 0.5)
			if not (w.is_walkable(q.x, q.z) and w.is_free(q.x, q.z, 0.45) and float(w.terrain_height(q.x, q.z)) > w.water_level + 0.1):
				continue
			var sc := absf(q.z - target.z - dist) + absf(q.x - target.x) * 0.8
			if sc < bs:
				bs = sc
				best = q
	var face := target - best
	face.y = 0.0
	at.tp(best.x, best.z, face.normalized() if face.length() > 0.1 else Vector3(0, 0, -1))
	w.player.velocity = Vector3.ZERO


static func _in_frame(at: Node) -> Dictionary:
	## animals whose middle is inside the camera frame, per species
	var cam: Camera3D = at.world.camera
	var vp: Vector2 = at.get_viewport().get_visible_rect().size
	var out := {}
	for a in at.world.animals.animals:
		if not a.node.visible:
			continue
		var p: Vector3 = a.node.position + Vector3(0, a.height * 0.5, 0)
		if cam.is_position_behind(p):
			continue
		var sp := cam.unproject_position(p)
		if sp.x > 0 and sp.y > 0 and sp.x < vp.x and sp.y < vp.y:
			out[a.id] = int(out.get(a.id, 0)) + 1
	return out


static func _centre(list: Array) -> Vector3:
	var c := Vector3.ZERO
	for a in list:
		c += a.node.position
	return c / maxf(list.size(), 1)


static func _grab(at: Node) -> Image:
	for i in 3:
		await at.get_tree().process_frame
	return at.get_viewport().get_texture().get_image()


static func merge_compare(at: Node) -> void:
	## Each species as imported (ModelLib, one material per part) and as animals.gd merges
	## it (colours baked into the vertex colours, one surface), same pose, same place, same
	## camera: the mean colour difference over the model must be small.
	var world: Node = at.world
	var A: Node = world.animals
	var ug: Node3D = world.undergrowth
	ug.visible = false
	world.ambient.visible = false
	GS.hour = 11.0
	# (the small animals draw a thinner ink line than the stock character-style one:
	# compare the colours without outlines)
	ModelLib.set_outlines(false)
	var cx := -3.0
	var cz := 22.0
	at.tp(cx, cz + 6.0, Vector3(0, 0, -1))
	world.player.visible = false
	var cam := Camera3D.new()
	cam.fov = 30.0
	world.add_child(cam)
	cam.current = true
	var rows: Array[Image] = []
	for id in ["sapi", "kerbau", "kambing", "ayam", "bebek", "kodok", "kucing", "anjing"]:
		var info: Dictionary = A._data[id]
		var h: float = float(info.get("height", 0.5))
		var y: float = world.height_at(cx, cz)
		var target := Vector3(cx, y + h * 0.5, cz)
		cam.global_position = target + Vector3(h * 1.1, h * 1.0, h * 2.6)
		cam.look_at(target, Vector3.UP)
		var imgs: Array[Image] = []
		for which in 2:
			var n: Node3D
			if which == 0:
				n = ModelLib.scene("animal_" + id).instantiate()
				ModelLib.stylize(n, false, 0.35)
				var r := n.find_child("Rooster", true, false) as Node3D
				if r:
					r.visible = false
			else:
				n = A._make_model(id, 0, info)
			n.position = Vector3(cx, y, cz)
			n.rotation.y = deg_to_rad(35.0)
			world.add_child(n)
			var ap := n.find_child("AnimationPlayer", true, false) as AnimationPlayer
			ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
			ap.play("idle")
			ap.seek(0.5, true)
			imgs.append(await _grab(at))
			n.queue_free()
			await at.get_tree().process_frame
		# the difference where either render differs from the empty ground (the model)
		var bg: Image = await _grab(at)
		var w := imgs[0].get_width()
		var hh := imgs[0].get_height()
		var sum := 0.0
		var cnt := 0
		for py in range(0, hh, 3):
			for px in range(0, w, 3):
				var b := bg.get_pixel(px, py)
				var c0 := imgs[0].get_pixel(px, py)
				var c1 := imgs[1].get_pixel(px, py)
				var m0 := absf(c0.r - b.r) + absf(c0.g - b.g) + absf(c0.b - b.b)
				var m1 := absf(c1.r - b.r) + absf(c1.g - b.g) + absf(c1.b - b.b)
				if m0 > 0.06 and m1 > 0.06:
					sum += (absf(c0.r - c1.r) + absf(c0.g - c1.g) + absf(c0.b - c1.b)) / 3.0
					cnt += 1
		var diff := sum / maxf(cnt, 1)
		print("[animals] merge %s: mean colour difference %.4f over %d px" % [id, diff, cnt])
		_check(diff < 0.03, "merged %s looks different (%.3f)" % [id, diff])
		var row := Image.create(w, hh / 2, false, Image.FORMAT_RGBA8)
		var half0 := imgs[0].get_region(Rect2i(w / 4, hh / 4, w / 2, hh / 2))
		var half1 := imgs[1].get_region(Rect2i(w / 4, hh / 4, w / 2, hh / 2))
		half0.convert(Image.FORMAT_RGBA8)
		half1.convert(Image.FORMAT_RGBA8)
		row.blit_rect(half0, Rect2i(0, 0, w / 2, hh / 2), Vector2i(0, 0))
		row.blit_rect(half1, Rect2i(0, 0, w / 2, hh / 2), Vector2i(w / 2, 0))
		row.resize(w / 2, hh / 4)
		rows.append(row)
	var sheet := Image.create(rows[0].get_width() * 2, rows[0].get_height() * 4, false, Image.FORMAT_RGBA8)
	for i in rows.size():
		sheet.blit_rect(rows[i], Rect2i(Vector2i.ZERO, rows[i].get_size()), Vector2i((i % 2) * rows[0].get_width(), (i / 2) * rows[0].get_height()))
	sheet.save_png("%s/animals_merge_compare.png" % at.shots_dir)
	cam.queue_free()
	ModelLib.set_outlines(true)
	ug.visible = true
	world.ambient.visible = true
	world.player.visible = true


static func closeups(at: Node) -> void:
	## A contact sheet: each species walking (frogs hopping, ducks swimming), eating and
	## calling, filmed three-quarter front by a camera near it (the game camera frames the
	## player; the animal is on its screen, so it gets the full update).
	var world: Node = at.world
	var A: Node = world.animals
	var cam := Camera3D.new()
	cam.fov = 38.0
	world.add_child(cam)
	var tiles: Array[Image] = []
	for id in ["sapi", "kerbau", "kambing", "ayam", "bebek", "kodok", "kucing", "anjing"]:
		var a = null
		for c in A.find(id):
			if not c.night_only and (a == null or A.cover_at(c.node.position.x, c.node.position.z) < A.cover_at(a.node.position.x, a.node.position.z)):
				a = c
		for st in ["walk", "eat", "call"]:
			at.tp(a.node.position.x, a.node.position.z + 4.0, Vector3(0, 0, -1))
			world.player.visible = false
			cam.current = true
			a.flee_cd = 99.0
			match st:
				"walk":
					var ok: bool = A._pick_target(a, "")
					for k in 6:
						if ok and a.node.position.distance_to(a.target) > 1.5:
							break
						ok = A._pick_target(a, "")
					a.state = "walk"
					a.hops = 6
				"eat":
					a.state = "eat"
					a.t = 6.0
				"call":
					A._start_call(a, true)
			await at.wait(0.75 if st != "call" else a.call_open + 0.15)
			var h: float = a.height
			var c: Vector3 = a.node.position + Vector3(0, h * 0.5, 0)
			var dir := Vector3(sin(a.yaw + 0.8), 0.0, cos(a.yaw + 0.8))
			cam.global_position = c + dir * (h * 2.3 + 0.5) + Vector3(0, h * 0.8 + 0.25, 0)
			cam.look_at(c, Vector3.UP)
			var img: Image = await _grab(at)
			img.convert(Image.FORMAT_RGBA8)
			img.resize(426, 240)
			tiles.append(img)
			print("[animals] closeup %s %s: state=%s clip=%s rate=%.2f speed=%.2f water=%s" % [id, st, a.state, a.clip, a.rate, a.speed, a.on_water])
		a.flee_cd = 0.0
	var sheet := Image.create(426 * 3, 240 * 8, false, Image.FORMAT_RGBA8)
	for i in tiles.size():
		sheet.blit_rect(tiles[i], Rect2i(0, 0, 426, 240), Vector2i((i % 3) * 426, (i / 3) * 240))
	sheet.save_png("%s/animals_closeups.png" % at.shots_dir)
	cam.queue_free()
	world.camera.current = true
	world.player.visible = true


static func run(at: Node) -> void:
	fails = []
	var world: Node = at.world
	var A: Node = world.animals
	if A == null or A.animals.is_empty():
		_check(false, "no animals at all")
		print("[animals] FAIL (%d)" % fails.size())
		return
	# the title screen's fly-over over Desa Sukamakmur
	await at.wait(4.0)
	print("[animals] title fly-over: in frame %s" % [_in_frame(at)])
	await _shot(at, "animals_title", 4)
	world.start_game(false)
	world.ui.close()
	GS.hour = 9.0
	if DisplayServer.get_name() != "headless":
		await merge_compare(at)
		await closeups(at)
	# ---- counts and spawn places
	var total := 0
	var line := ""
	for id in ["sapi", "kerbau", "kambing", "ayam", "bebek", "kodok", "kucing", "anjing"]:
		var n := int(A.counts.get(id, 0))
		total += n
		line += "%s=%d " % [id, n]
		_check(n >= 2 if id != "anjing" else n >= 1, "too few %s (%d)" % [id, n])
	var roosters := 0
	var night_frogs := 0
	for a in A.animals:
		roosters += 1 if a.rooster else 0
		night_frogs += 1 if a.night_only else 0
	print("[animals] counts: %stotal=%d roosters=%d night_frogs=%d" % [line, total, roosters, night_frogs])
	_check(total >= 50 and total <= 85, "total %d outside 50..85" % total)
	var bad0 := _all_placed(A, "spawn")
	var in_parcel := 0
	for a in A.animals:
		if A.in_parcel(a.nest.x, a.nest.z):
			in_parcel += 1
	_check(in_parcel == 0, "%d animals start on a farm parcel" % in_parcel)
	print("[animals] spawn: %d misplaced, %d on parcels" % [bad0, in_parcel])
	var csum := 0.0
	for k in A._cover:
		csum += float(A._cover[k])
	var nests := ""
	for a in A.animals:
		nests += "%s(%.0f,%.0f) " % [a.id[0], a.nest.x, a.nest.z]
	print("[animals] start-up: cover grid %.1f ms, spawning %.1f ms; cover cells=%d sum=%.1f; nests: %s" % [
		A.cover_ms, A.spawn_ms, A._cover.size(), csum, nests.left(300)])
	# ---- frame cost of the whole manager at a few typical places (60 frames each)
	var costs := []
	for spot in [Vector2(-3.5, 37.5), Vector2(0, 8), A.find("sapi")[0].node.position, A.find("ayam")[3].node.position]:
		at.tp(spot.x, spot.y if spot is Vector2 else spot.z + 4.0, Vector3(0, 0, -1))
		await at.wait(0.5)
		var us0: int = A.perf_us
		var f0: int = A.perf_frames
		A.profile = true
		A.prof = PackedInt64Array([0, 0, 0, 0])
		for i in 60:
			await at.get_tree().process_frame
		A.profile = false
		var n: float = maxf(A.prof[3], 1)
		costs.append("%.3f (%d full/frame: think %.0f ground %.0f anim %.0f us each)" % [(A.perf_us - us0) / 1000.0 / maxf(A.perf_frames - f0, 1),
			A.prof[3] / 60, A.prof[0] / n, A.prof[1] / n, A.prof[2] / n])
	print("[animals] frame cost at start / village / herd / flock: %s ms (frame time %.1f ms)" % [costs, 1000.0 / maxf(Engine.get_frames_per_second(), 1.0)])
	# ---- a few minutes of village life (3x speed), sampled for places and foot sliding
	at.tp(-3.5, 37.5, Vector3(0, 0, -1))
	var slide_max := 0.0
	var slide_n := 0
	var slide_sum := 0.0
	var states := {}
	var clips := {}
	var bad := 0
	Engine.time_scale = 3.0
	for s in 40:
		await at.wait(0.5)
		for a in A.animals:
			states[a.state] = int(states.get(a.state, 0)) + 1
			if a.in_view:
				clips[a.id + ":" + a.clip] = true
				if (a.clip == "walk" or a.clip == "run") and a.speed > 0.15 and not a.on_water:
					var nat: float = a.walk_v if a.clip == "walk" else a.run_v
					var sl: float = absf(a.speed - nat * a.rate) / a.speed
					slide_max = maxf(slide_max, sl)
					slide_sum += sl
					slide_n += 1
		if s % 10 == 9:
			bad += _all_placed(A, "t=%ds" % ((s + 1) * 3 / 2))
			# wander the camera over the island so other animals get the full update too
			var who = A.animals[(s * 7) % A.animals.size()]
			at.tp(who.node.position.x, who.node.position.z + 6.0, Vector3(0, 0, -1))
	Engine.time_scale = 1.0
	var moved := 0
	for a in A.animals:
		if a.odo > 0.5:
			moved += 1
	print("[animals] after ~60 s: moved=%d/%d misplaced=%d states=%s" % [moved, A.animals.size(), bad, states])

	_check(moved > A.animals.size() / 3, "only %d animals moved" % moved)

	GS.hour = 9.5
	# ---- screenshots from the game camera (and a closer one), each framing one group
	var ug: Node3D = world.undergrowth
	var hens: Array = A.find("ayam")
	var goats: Array = A.find("kambing")
	# the goats with a flock of chickens nearest to them
	var goat_g: Array = goats[0].group
	var gd := INF
	for g in goats:
		for h in hens:
			var d: float = g.home.distance_to(h.home)
			if d < gd:
				gd = d
				goat_g = g.group
	var jh: Vector3 = world.door_points.get("rumah_juragan", Vector3.ZERO)
	var flock: Array = hens[0].group
	for h in hens:
		if h.home.distance_to(jh) < 8.0:
			flock = h.group
	# (a cat away from the doors: a door's prompt rightly wins over petting)
	var cat = A.find("kucing")[0]
	var cat_door := 0.0
	for c in A.find("kucing"):
		var dd := INF
		for did in world.door_points:
			dd = minf(dd, (world.door_points[did] as Vector3).distance_to(c.node.position))
		if dd > cat_door:
			cat_door = dd
			cat = c
	var dogs: Array = A.find("anjing")
	# the duck with dry ground nearest to its south (the game camera looks north)
	var duck = A.find("bebek")[0]
	var dbest := INF
	for d in A.find("bebek"):
		for k in 30:
			var q: Vector3 = d.node.position + Vector3(0, 0, 1.0 + k * 0.5)
			if world.is_walkable(q.x, q.z) and world.is_free(q.x, q.z, 0.45):
				if k < dbest:
					dbest = k
					duck = d
				break
	var subjects := [
		["herd", A.find("sapi")[0].group, 5.0],
		["goats", goat_g, 4.0],
		["chickens", flock, 3.5],
		["ducks", [duck], 4.0],
		["buffalo", A.find("kerbau")[0].group, 5.0],
		["cat", [cat], 3.0],
		["dog", [dogs[0]], 3.5],
	]
	for sj in subjects:
		var grp: Array = sj[1]
		_view(at, _centre(grp), sj[2])
		# (meanwhile: walk / run playback against the ground speed of those on screen)
		for f in 40:
			await at.wait(0.05)
			for a in A.animals:
				if a.in_view:
					clips[a.id + ":" + a.clip] = true
					if (a.clip == "walk" or a.clip == "run") and a.speed > 0.15 and not a.on_water:
						var nat: float = a.walk_v if a.clip == "walk" else a.run_v
						var sl: float = absf(a.speed - nat * a.rate) / a.speed
						slide_max = maxf(slide_max, sl)
						slide_sum += sl
						slide_n += 1
		# re-frame on where they wandered to
		_view(at, _centre(grp), sj[2])
		await at.wait(0.4)
		print("[animals] shot %s: in frame %s" % [sj[0], _in_frame(at)])
		await _shot(at, "animals_" + sj[0], 8)
		world.cam_distance = 8.0
		await at.wait(0.5)
		print("[animals] shot %s_close: in frame %s" % [sj[0], _in_frame(at)])
		await _shot(at, "animals_%s_close" % sj[0], 8)
		world.cam_distance = 15.5
	print("[animals] clips seen on screen: %s" % [clips.keys()])
	print("[animals] foot slide (|speed - clip speed x rate| / speed): mean %.3f max %.3f over %d samples" % [
		slide_sum / maxf(slide_n, 1), slide_max, slide_n])
	_check(slide_n > 20, "too few walking samples on screen (%d)" % slide_n)
	_check(slide_sum / maxf(slide_n, 1) < 0.08, "feet slide (mean %.3f)" % (slide_sum / maxf(slide_n, 1)))
	# ---- petting: face the cat within reach
	# (away from the doors, whose prompt rightly wins: move the cat if it wandered up to one)
	var near_door := false
	for did in world.door_points:
		if (world.door_points[did] as Vector3).distance_to(cat.node.position) < 3.2:
			near_door = true
	if near_door:
		for k in 40:
			var q: Vector3 = cat.nest + Vector3(0, 0, 1.0 + k * 0.25).rotated(Vector3.UP, k * 2.4)
			var ok: bool = A.land_ok(q.x, q.z, 0.4, false)
			for did in world.door_points:
				if (world.door_points[did] as Vector3).distance_to(q) < 3.2:
					ok = false
			if ok:
				cat.node.position = q
				break
	# (a free spot within reach, on any side)
	var cp: Vector3 = cat.node.position
	var spot := cp + Vector3(0, 0, 1.2)
	for k in 24:
		var q := cp + Vector3(0, 0, 1.0 + (k / 12) * 0.35).rotated(Vector3.UP, (k % 12) * TAU / 12.0)
		if world.is_walkable(q.x, q.z) and world.is_free(q.x, q.z, 0.4):
			spot = q
			break
	var fc2 := cp - spot
	fc2.y = 0.0
	at.tp(spot.x, spot.z, fc2.normalized())
	world.player.velocity = Vector3.ZERO
	cat.state = "idle"
	cat.t = 5.0
	# (the teleport lands before the next visibility scan: give it a moment)
	await at.wait(0.3)
	cat.state = "idle"
	cat.t = 5.0
	await at.get_tree().process_frame
	await at.get_tree().process_frame
	var tg: Dictionary = world.target
	if not tg.has("animal"):
		var pp: Vector3 = world.player.global_position
		print("[animals]   (pet debug: cat at %s visible=%s shown=%s, player at %s facing %s, d=%.2f, pet_target=%s, state=%s)" % [
			cat.node.position, cat.node.visible, cat.shown, pp, world.player.facing,
			Vector2(cat.node.position.x - pp.x, cat.node.position.z - pp.z).length(), A.pet_target().keys(), world.state])
	_check(tg.has("animal"), "no pet prompt in front of the cat (target %s)" % [tg.keys()])
	var prompt: String = tg["prompt"].call() if tg.has("prompt") else ""
	print("[animals] prompt in front of the cat: '%s'" % prompt)
	_check(prompt.begins_with("Elus "), "prompt '%s'" % prompt)
	var snd0: int = A.sounds_played
	world.try_action()
	await at.wait(0.1)
	_check(cat.state == "pet" and cat.clip == "call", "the cat did not react to petting (%s / %s)" % [cat.state, cat.clip])
	world.cam_distance = 8.0
	await at.wait(0.45)
	await _shot(at, "animals_pet", 4)
	world.cam_distance = 15.5
	_check(A.sounds_played > snd0, "petting played no sound")
	_check(A.pets == 1, "pets=%d" % A.pets)
	print("[animals] pet: state=%s clip=%s sounds %d -> %d last=%s" % [cat.state, cat.clip, snd0, A.sounds_played, A.last_sound])
	await at.wait(1.5)
	# priorities: a palm tile beside an animal wins over the animal
	var tile: Node3D = world.tile_views["0:0"]
	var hen = hens[0]
	var hen_pos: Vector3 = hen.node.position
	var tp_: Vector3 = tile.global_position
	hen.node.position = tp_ + Vector3(0.6, 0, 0.9)
	hen.state = "idle"
	hen.t = 10.0
	_view(at, tp_, 1.2)
	await at.get_tree().process_frame
	await at.get_tree().process_frame
	_check(world.target.has("tile"), "an animal took the tile's prompt (target %s)" % [world.target.keys()])
	hen.node.position = hen_pos
	# ---- a player running at a flock scatters it
	var fl: Array = []
	for h in hens:
		if h.group == hen.group:
			fl.append(h)
	var run_dir := Vector3.ZERO
	var start := Vector3.INF
	for h in fl:
		h.flee_cd = 0.0
		h.state = "idle"
		h.t = 10.0
		h.speed = 0.0
	for k in 16:
		var dir := Vector3(0, 0, 1).rotated(Vector3.UP, k * TAU / 16.0)
		var st: Vector3 = fl[0].node.position + dir * 5.5
		var clear := true
		for m in 22:
			var q: Vector3 = st.lerp(fl[0].node.position, m / 22.0)
			if not world.is_walkable(q.x, q.z) or not world.is_free(q.x, q.z, 0.4):
				clear = false
				break
		if clear:
			start = st
			run_dir = -dir
			break
	_check(start != Vector3.INF, "no clear run at the flock")
	if start != Vector3.INF:
		at.tp(start.x, start.z, run_dir)
	await at.wait(0.3)
	var fl0: int = A.flees
	var closest := INF
	for i in 16:
		var to: Vector3 = fl[0].node.position - world.player.global_position
		to.y = 0.0
		if to.length() > 0.3:
			world.player.touch_vec = Vector2(to.x, to.z).normalized() * 0.9
		await at.wait(0.05)
		for h in fl:
			closest = minf(closest, Vector2(h.node.position.x - world.player.global_position.x,
				h.node.position.z - world.player.global_position.z).length())
	var run_v: float = Vector2(world.player.velocity.x, world.player.velocity.z).length()
	world.player.touch_vec = Vector2.ZERO
	print("[animals] flock run: player speed %.1f, closest %.2f m, states %s" % [run_v, closest, fl.map(func(h): return h.state)])
	var fled: int = A.flees - fl0
	print("[animals] running at a flock of %d: %d scattered" % [fl.size(), fled])
	_check(fled >= 2, "the flock did not scatter")
	# ---- a dog trots after a passing player
	var dg = dogs[0]
	dg.follow_cd = 0.0
	dg.state = "idle"
	_view(at, dg.node.position, 4.0)
	await at.wait(0.3)
	var fo0: int = A.follows
	world.player.touch_vec = Vector2(0.8, 0.0)
	await at.wait(0.6)
	world.player.touch_vec = Vector2.ZERO
	await at.wait(0.1)
	print("[animals] dog after the player passed: %s (follows %d)" % [dg.state, A.follows - fo0])
	_check(A.follows > fo0, "the dog did not follow (%s)" % dg.state)
	# ---- frogs on a bank at night (the night frogs come out)
	GS.hour = 21.5
	var frogs: Array = A.find("kodok")
	var fg = frogs[0]
	await at.wait(0.3)
	var outs := 0
	for f in frogs:
		if f.night_only and f.out:
			outs += 1
	print("[animals] night: %d night frogs out" % outs)
	_check(outs >= 1, "no night frogs came out")
	# the frog (by day or by night) on the barest bank
	var fbest := INF
	for f in frogs:
		if f.night_only and not f.out:
			continue
		var cv: float = A.cover_at(f.node.position.x, f.node.position.z)
		if cv < fbest:
			fbest = cv
			fg = f
	_view(at, fg.node.position, 2.5)
	await at.wait(2.5)
	await _shot(at, "animals_frogs_night", 8)
	world.cam_distance = 7.0
	await at.wait(0.8)
	await _shot(at, "animals_frogs_night_close", 8)
	world.cam_distance = 15.5
	var sleeping := 0
	var awake_frogs := 0
	await at.wait(6.0)
	for a in A.animals:
		if a.state == "sleep" or a.state == "home":
			sleeping += 1
		if a.id == "kodok" and a.state != "sleep":
			awake_frogs += 1
	print("[animals] night: %d asleep / going home, %d frogs about, sounds so far %d" % [sleeping, awake_frogs, A.sounds_played])
	_check(sleeping > A.animals.size() / 2, "only %d asleep at night" % sleeping)
	GS.hour = 9.0
	_check(bad == 0, "%d misplaced during the run" % bad)
	print("[animals] frame cost: %.3f ms (mean over %d frames)" % [A.perf_ms(), A.perf_frames])
	if ug:
		ug.visible = true
	print("[animals] %s" % ("PASS" if fails.is_empty() else "FAIL (%d)" % fails.size()))
