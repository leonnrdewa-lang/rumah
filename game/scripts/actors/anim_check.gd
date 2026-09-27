class_name AnimCheck
extends RefCounted
## Autotest scenario "anim" (run through scripts/debug/autotest.gd):
##   godot --path game -- --autotest=anim --shots=<dir>
## First the numeric bench on a bare floor (AnimBench: foot slide, action lock,
## tools, pole steadiness, fades; prints "[anim] BENCH PASS/FAIL"), then in the
## island: walks, runs, stops, turns, harvests, chops, plants, talks, cheers and
## gets waved at, capturing short frame sequences (0.1 s apart) from a close
## follow camera (undergrowth hidden), an off-screen villager check and 120 s
## of village life (chats, visits).


static func run(at: Node) -> void:
	## Optional `--anim-only=title,bench,loco,work,talk,wave,worker,village,offscreen`
	## runs a subset; `--anim-noshots` skips the bench's frame captures.
	var only := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--anim-only="):
			only = a.get_slice("=", 1)
	var world: Node = at.world
	if _on(only, "title"):
		await _title_check(at)
	world.start_game(false)
	world.ui.close()
	GS.hour = 9.0   # villagers are up and about
	var pl: Player = world.player
	var tree: SceneTree = at.get_tree()
	if _on(only, "bench"):
		var fails: Array = await AnimBench.run(at)
		print("[anim] BENCH %s" % ("PASS" if fails.is_empty() else "FAIL: " + ", ".join(fails)))
	if only != "" and only.split(",").size() == 1 and _on(only, "bench"):
		return
	if _on(only, "offscreen"):
		await _offscreen_check(at)
	# the dense undergrowth hides the close follow camera: off while filming
	var ug: Node3D = world.get("undergrowth")
	if ug:
		ug.visible = false
	var cam := Camera3D.new()
	cam.fov = 38.0
	world.add_child(cam)
	cam.current = true
	var cam_state := {"off": Vector3(2.4, 1.7, 3.4), "node": pl, "behind": false}
	var follow := func() -> void:
		var node: Node3D = cam_state["node"]
		var target: Vector3 = node.global_position + Vector3(0, 0.55, 0)
		var off: Vector3 = cam_state["off"]
		if cam_state["behind"]:
			var f := Vector3(pl.velocity.x, 0, pl.velocity.z)
			f = f.normalized() if f.length() > 0.1 else pl.facing
			off = -f * 3.6 + Vector3(0, 1.2, 0)
		cam.global_position = node.global_position + off
		cam.look_at(target, Vector3.UP)
	tree.process_frame.connect(follow)
	print("[anim] player skinned=%s clips=%s nat=%s" % [pl.anim.skinned,
		pl.anim.ap.get_animation_list() if pl.anim.skinned else [], pl.anim._nat])

	var seq := func(tag: String, n: int, dt := 0.1) -> void:
		for i in n:
			await at.wait(dt)
			await at.shot("%s_%d" % [tag, i], 1)
			print("[anim]   %s_%d clip=%s kind=%s rate=%.2f speed=%.2f busy=%s tool=%s" % [tag, i,
				pl.anim._cur, pl.anim._cur_kind, pl.anim._rate, Vector2(pl.velocity.x, pl.velocity.z).length(),
				pl.anim.is_busy(), _tool_state(pl)])

	if _on(only, "loco"):
		# open ground by the start of the road
		at.tp(-3, 22, Vector3(1, 0, 0))
		await at.wait(0.6)
		await seq.call("idle", 3, 0.3)
		pl.touch_vec = Vector2(0.4, 0)
		await seq.call("walk", 6)
		pl.touch_vec = Vector2(0.9, 0)
		await seq.call("jog", 4)
		pl.touch_vec = Vector2(1.0, 0)
		await seq.call("run", 4)
		pl.touch_vec = Vector2.ZERO
		await seq.call("stop", 6)
		pl.touch_vec = Vector2(-0.9, 0.3)
		await seq.call("turn", 6, 0.06)
		pl.touch_vec = Vector2.ZERO
		await at.wait(0.6)
		# run a circle, seen from behind: the body must lean into the turn (left)
		cam_state["behind"] = true
		var ang := 0.0
		for i in 70:
			ang += 0.05
			pl.touch_vec = Vector2(cos(-ang), sin(-ang))
			await at.wait(0.02)
			if i % 10 == 9:
				await at.shot("circle_%d" % (i / 10), 1)
				print("[anim]   circle lean=%.3f turn_rate=%.2f" % [pl.anim._lean, pl.anim._turn_rate])
		pl.touch_vec = Vector2.ZERO
		cam_state["behind"] = false
		await at.wait(0.6)

	if _on(only, "work"):
		# work on the first plot (tile 0 of parcel 0 has a ripe palm at game start)
		var tv: Node3D = world.tile_views.get("0:0")
		if tv:
			at.tp(tv.global_position.x - 1.2, tv.global_position.z + 0.6, Vector3(1, 0, -0.5).normalized())
			cam_state["off"] = Vector3(-2.6, 2.2, 3.4)
			await at.wait(0.5)
			var x0 := pl.global_position
			world._tile_action(0, 0)
			pl.touch_vec = Vector2(0, 1)   # try to walk away: must stay locked
			var lock_t := 0.0
			while pl.anim.is_busy():
				await tree.physics_frame
				lock_t += pl.get_physics_process_delta_time()
			print("[anim] harvest lock %.2f s (game time), moved during lock: %.2f m" % [lock_t,
				Vector2(pl.global_position.x - x0.x, pl.global_position.z - x0.z).length()])
			pl.touch_vec = Vector2.ZERO
			await at.wait(0.5)
		# the rest on open ground, seen from the side (the player faces +X)
		at.tp(-3, 22, Vector3(1, 0, 0))
		cam_state["off"] = Vector3(0.6, 1.4, 4.2)
		await at.wait(0.5)
		pl.do_action_anim("harvest")
		await seq.call("harvest", 12)
		await at.wait(0.4)
		cam_state["off"] = Vector3(2.4, 1.7, 3.4)
		for kind in ["clear", "plant", "fert"]:
			pl.do_action_anim(kind)
			await seq.call(kind, 9)
			await at.wait(0.3)
		pl.anim.play_action("cheer", 1.2)
		await seq.call("cheer", 8, 0.15)
		# the harvest basket on the back, full, walking away from the camera
		GS.inv["tbs"] = 9
		pl.update_carry(9)
		cam_state["off"] = Vector3(-3.0, 1.6, 1.2)
		await seq.call("carry", 2, 0.2)
		pl.touch_vec = Vector2(0.5, 0)
		await seq.call("carrywalk", 4, 0.15)
		pl.touch_vec = Vector2.ZERO
		# a tool kept in hand between actions (hotbar selection)
		pl.anim.hold_tool("harvest")
		cam_state["off"] = Vector3(0.6, 1.6, 4.4)
		pl.touch_vec = Vector2(0.4, 0)
		await seq.call("hold", 3, 0.2)
		pl.touch_vec = Vector2.ZERO
		pl.anim.hold_tool("")
		await at.wait(0.4)
		cam_state["off"] = Vector3(2.4, 1.7, 3.4)

	if _on(only, "talk"):
		# talk to a villager
		var npc: Npc = world.npcs.get("ibu")
		if npc:
			at.tp(npc.global_position.x + 1.4, npc.global_position.z + 0.4, Vector3(-1, 0, 0))
			await at.wait(0.2)
			world.deals.talk("ibu")
			cam_state["off"] = Vector3(0.6, 1.8, 3.8)
			await at.wait(0.5)
			print("[anim] npc talking=%s clip=%s" % [npc.talking, npc.anim._cur])
			await seq.call("talk", 6, 0.2)
			world.ui.close()
			await at.wait(0.5)
			print("[anim] after talk: npc talking=%s clip=%s" % [npc.talking, npc.anim._cur])

	if _on(only, "wave"):
		# walk up to a villager who has not seen us yet: they should wave
		var waver: Npc = null
		for vid in ["kakek", "nenek", "petani", "pemuda", "kades"]:
			var n: Npc = world.npcs.get(vid)
			if n and n.visible and n.global_position.distance_to(pl.global_position) > 12.0:
				waver = n
				break
		if waver:
			waver._wave_cd = 0.0
			waver._greeted = false
			var wp := waver.global_position
			at.tp(wp.x + 6.0, wp.z + 1.0, Vector3(-1, 0, 0))
			cam_state["off"] = Vector3(-1.5, 2.0, 5.0)
			await at.wait(0.3)
			pl.touch_vec = Vector2(-0.5, 0)
			for i in 40:
				await at.wait(0.05)
				if waver.anim.is_busy():
					break
			pl.touch_vec = Vector2.ZERO
			print("[anim] waver=%s action=%s" % [waver.display_name, waver.anim.action_kind_playing()])
			cam_state["node"] = waver
			cam_state["off"] = Vector3(1.2, 1.6, 3.6)
			await seq.call("wave", 8, 0.15)
			cam_state["node"] = pl

	if _on(only, "worker"):
		# a hired hand works the palms; a villager who lost his land slumps
		GS.workers.append({"id": "buruh_test", "name": "Buruh harian", "wage": 1, "vid": ""})
		world.refresh_workers()
		if not world.worker_npcs.is_empty():
			var w: Npc = world.worker_npcs[0]
			w._wait = 0.0
			w._work_cd = 0.0
			at.tp(w.global_position.x + 3.0, w.global_position.z + 3.0)
			cam_state["node"] = w
			cam_state["off"] = Vector3(1.6, 1.8, 3.6)
			for i in 60:
				await at.wait(0.1)
				if w.anim.is_busy():
					break
			print("[anim] worker action=%s" % w.anim.action_kind_playing())
			await seq.call("worker", 6, 0.15)
		var sad: Npc = world.npcs.get("nenek")
		if sad:
			GS.villagers["nenek"]["status"] = "landless"
			at.tp(sad.global_position.x + 7.0, sad.global_position.z + 7.0)
			cam_state["node"] = sad
			cam_state["off"] = Vector3(1.2, 1.6, 3.4)
			await at.wait(1.0)
			print("[anim] landless nenek clip=%s" % sad.anim._cur)
			await seq.call("sad", 3, 0.3)
			GS.villagers["nenek"]["status"] = "owner"
		cam_state["node"] = pl

	# village life with the normal game camera: chats, work, glances
	tree.process_frame.disconnect(follow)
	world.camera.current = true
	if ug:
		ug.visible = true
	if not _on(only, "village"):
		cam.queue_free()
		return
	at.tp(-4, 4)
	if world.worker_npcs.is_empty():
		GS.workers.append({"id": "buruh_village", "name": "Buruh harian", "wage": 1, "vid": ""})
		world.refresh_workers()
	GS.hour = 8.0
	# count chats that start, visits that end in a chat or fail, trips to the
	# warung (and back) and how much of the time the hired hands are working
	var partner_prev := {}
	var chat_starts := 0
	var pairs := {}
	var visits := {}
	var visit_ok := 0
	var visit_fail := 0
	var away_prev := {}
	var trips := []
	var trips_back := 0
	var work_busy := 0
	var work_n := 0
	var steps := int(120.0 / 0.25)
	for i in steps:
		await at.wait(0.25)
		var chat := 0
		var busy := 0
		var visit := 0
		for w in world.worker_npcs:
			work_n += 1
			work_busy += 1 if w.anim.is_busy() else 0
		for n in world.npcs.values() + world.extras.values():
			var away: bool = n._away
			if away and not away_prev.get(n, false):
				trips.append("%s (%.0f m)" % [n.display_name, n._route_length()])
			if not away and away_prev.get(n, false):
				trips_back += 1
			away_prev[n] = away
		for n in world.npcs.values() + world.extras.values() + world.worker_npcs:
			var partner: Npc = n._chat_with
			if partner != null:
				chat += 1
				if partner_prev.get(n) != partner and n.display_name < partner.display_name:
					chat_starts += 1
					pairs[n.display_name + "+" + partner.display_name] = true
			partner_prev[n] = partner
			if n._visit != null:
				visit += 1
				visits[n] = n._visit
			elif visits.has(n):
				if n._chat_with == visits[n]:
					visit_ok += 1
				else:
					visit_fail += 1
				visits.erase(n)
			if n.anim.is_busy():
				busy += 1
		if i % 8 == 7:
			print("[anim] village t=%d chatting=%d visiting=%d busy=%d" % [(i + 1) / 4, chat, visit, busy])
		if i == 0 or i == steps - 1:
			for n in world.npcs.values() + world.extras.values():
				print("[anim]     %s pos=(%.0f,%.0f) idle=%s cd=%.1f wait=%.1f vis=%s" % [n.display_name, n.position.x, n.position.z,
					n.is_idle(), n._social_cd, n._wait, n.visible])
	print("[anim] village 120 s (game hour now %.1f): chats started=%d between %d pairs %s; visits ok=%d failed=%d" % [GS.hour, chat_starts,
		pairs.size(), pairs.keys(), visit_ok, visit_fail])
	print("[anim] village trips to the warung started=%d %s, headed back=%d; hired hands working %.0f%% of the time" % [
		trips.size(), trips, trips_back, 100.0 * work_busy / maxf(work_n, 1)])
	if DisplayServer.get_name() != "headless":
		await at.shot("village", 1)

	# every character model in the village, sanity-checked
	var n_skinned := 0
	var all: Array = world.npcs.values() + world.extras.values()
	for n in all:
		if n.anim.skinned:
			n_skinned += 1
	print("[anim] npcs skinned=%d / %d" % [n_skinned, all.size()])
	cam.queue_free()


static func _title_check(at: Node) -> void:
	## The title screen: the camera orbits the island while the villagers go
	## about their day. Everyone the camera sees must be animated (not frozen on
	## a stale pose), walk with the walk clip and face where they walk. Films a
	## walking villager (crops, 0.1 s apart) when rendering.
	var world: Node = at.world
	GS.hour = 9.0
	var cam: Camera3D = world.camera
	var tree: SceneTree = at.get_tree()
	var stats := {}
	var prev_pos := {}
	var bad := 0
	var samples := 0
	var moving_samples := 0
	var head_err := 0.0
	var head_max := 0.0
	var film: Npc = null
	var film_n := 0
	var film_t := 0.0
	var t := 0.0
	var next_sample := 0.0
	var shots := "--anim-noshots" not in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless"
	while t < 30.0:
		await tree.process_frame
		var dt := at.get_process_delta_time()
		t += dt
		if shots and film != null and film_n < 8 and t >= film_t:
			var sp := cam.unproject_position(film.global_position + Vector3(0, 0.6, 0))
			var img := at.get_viewport().get_texture().get_image()
			var r := Rect2i(int(sp.x) - 70, int(sp.y) - 70, 140, 140).intersection(Rect2i(0, 0, img.get_width(), img.get_height()))
			if r.size.x == 140 and r.size.y == 140:
				img.get_region(r).save_png("%s/title_%s_%d.png" % [at.shots_dir, film.model_name, film_n])
				print("[anim]   title film %d %s speed=%.2f clip=%s t=%.3f" % [film_n, film.display_name, film._cur_speed,
					film.anim._cur, film.anim.ap.current_animation_position])
				film_n += 1
			film_t = t + 0.1
		if t < next_sample:
			continue
		next_sample = t + 0.25
		for n in world.npcs.values() + world.extras.values():
			var p: Vector3 = n.global_position
			var last: Vector3 = prev_pos.get(n, p)
			prev_pos[n] = p
			if not n.visible or not cam.is_position_in_frustum(p + Vector3(0, 0.6, 0)):
				continue
			samples += 1
			var st: Dictionary = stats.get(n.display_name, {"in": 0, "walk": 0, "bad": 0})
			st["in"] += 1
			var ok: bool = not n.anim.skinned or not n.anim._stale
			var mv := Vector2(p.x - last.x, p.z - last.z)
			if n._cur_speed > 0.3 and mv.length() > 0.1:
				moving_samples += 1
				st["walk"] += 1
				ok = ok and (not n.anim.skinned or n.anim._cur_kind in ["walk", "run"])
				var err := rad_to_deg(absf(wrapf(n.model.rotation.y - atan2(mv.x, mv.y), -PI, PI)))
				head_err += err
				head_max = maxf(head_max, err)
				if film == null and n.anim.skinned:
					# film one near the middle of the screen (it stays in frame)
					var sp := cam.unproject_position(p + Vector3(0, 0.6, 0))
					var vs := at.get_viewport().get_visible_rect().size
					if sp.x > vs.x * 0.2 and sp.x < vs.x * 0.8 and sp.y > vs.y * 0.2 and sp.y < vs.y * 0.8:
						film = n
			if not ok:
				bad += 1
				st["bad"] += 1
			stats[n.display_name] = st
	for k in stats:
		print("[anim]   title %-18s in view %d samples, walking in %d, not animated %d" % [k, stats[k]["in"], stats[k]["walk"], stats[k]["bad"]])
	var ok := bad == 0 and moving_samples > 0
	print("[anim] title %s: %d in-view samples (%d walking), %d not animated / wrong clip; heading vs. walk direction %.0f deg mean, %.0f max" % [
		"PASS" if ok else "FAIL", samples, moving_samples, bad, head_err / maxf(moving_samples, 1), head_max])


static func _offscreen_check(at: Node) -> void:
	## A villager whose work clip starts near the player must not freeze once the
	## player leaves (out of the camera's view it is no longer animated).
	var world: Node = at.world
	var n: Npc = world.npcs.get("petani")
	if n == null:
		return
	at.tp(n.global_position.x + 3.0, n.global_position.z + 3.0)
	await at.wait(0.3)
	n.anim.play_action("harvest")
	await at.wait(0.2)
	var busy0 := n.anim.is_busy()
	var far := Vector3.ZERO
	for p in [Vector3(-17, 0, 30), Vector3(56, 0, 20), Vector3(-3, 0, 22), Vector3(0, 0, 14), Vector3(8, 0, 5)]:
		if Vector2(p.x - n.position.x, p.z - n.position.z).length() > far.distance_to(n.position) or far == Vector3.ZERO:
			far = p
	at.tp(far.x, far.z)
	await at.wait(2.0)
	var dist: float = world.player.global_position.distance_to(n.global_position)
	var busy1 := n.anim.is_busy()
	var p0 := n.position
	var moved := 0.0
	for i in 30:
		await at.wait(0.5)
		moved = maxf(moved, n.position.distance_to(p0))
	var ok: bool = busy0 and not busy1 and not n.in_view()
	print("[anim] offscreen %s: busy at start=%s, 2 s after the player went %.0f m away (in view=%s) busy=%s, wandered %.1f m in 15 s, model faces its heading=%s" % [
		"PASS" if ok else "FAIL", busy0, dist, n.in_view(), busy1, moved, absf(wrapf(n.model.rotation.y - n.anim._yaw, -PI, PI)) < 0.001])


static func _on(only: String, part: String) -> bool:
	return only == "" or part in only.split(",")


static func _tool_state(pl: Player) -> String:
	var a := pl.anim
	for k in a._tools:
		var t: Node3D = a._tools[k]
		if t.visible:
			var hand := t.get_parent() as Node3D
			return "%s(s=%.2f d=%.2f)" % [k, t.scale.x, t.global_position.distance_to(hand.global_position)]
	return "-"
