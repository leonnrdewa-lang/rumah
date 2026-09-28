class_name AnimBench
extends RefCounted
## Numeric animation checks on a bare, lit floor (autotest "anim", part "bench"):
## planted-foot slide at game speeds (also with the gait extras stripped),
## action lock times and tools in the hand, harvesting pole steadiness and
## gentle starts, tools growing/shrinking, the carried pole clearing the back
## basket, pops in the cross-fades, off-screen timers and resume, plus frame
## sequences 0.1 s apart from a side camera.
## Characters are stepped at a fixed 1/60 s (or 1/30 s), so the numbers do not
## depend on how fast the machine renders.

const DT := 1.0 / 60.0
const SLIDE_MAX := 0.10          # planted foot speed / ground speed (gated speeds)
const POLE_CARRY_MAX_DEG := 4.0  # pole direction change per 1/60 s frame while carried
const POLE_MOVE_MAX_DEG := 8.0   # ... while harvesting and when picking it up / shouldering it
const LOCK_TOL := 0.05           # s
const FADE_WINDOW := 0.35        # s after a clip change in which a spike counts as a fade pop


static func run(at: Node) -> Array:
	var world: Node3D = at.world
	var fails: Array = []
	var shots := not "--anim-noshots" in OS.get_cmdline_user_args()
	world.process_mode = Node.PROCESS_MODE_DISABLED
	world.visible = false
	world.ui.visible = false
	var stage := _build_stage(at)
	print("[bench] ---- planted-foot slide (identity-tracked lowest sole vertex; ankle for reference)")
	_slide_tests(stage, fails)
	print("[bench] ---- gait without the exported extras (fallback measurement)")
	_noextras_tests(stage, fails)
	print("[bench] ---- actions: lock time, tools")
	_action_tests(stage, fails)
	print("[bench] ---- harvesting pole")
	_pole_tests(stage, fails)
	print("[bench] ---- pops in cross-fades")
	_pop_tests(stage, fails)
	print("[bench] ---- off-screen timers")
	_tick_test(stage, fails)
	if shots:
		await _film(at, stage)
	stage.queue_free()
	world.visible = true
	world.ui.visible = true
	world.process_mode = Node.PROCESS_MODE_INHERIT
	world.camera.current = true
	return fails


# ------------------------------------------------------------------ stage
static func _build_stage(at: Node) -> Node3D:
	var stage := Node3D.new()
	stage.name = "AnimBench"
	at.add_child(stage)
	var fl := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(240, 240)
	fl.mesh = pm
	var img := Image.create(2, 2, false, Image.FORMAT_RGB8)
	img.fill(Color("8fa45c"))
	img.set_pixel(1, 0, Color("74884a"))
	img.set_pixel(0, 1, Color("74884a"))
	var m := StandardMaterial3D.new()
	m.albedo_texture = ImageTexture.create_from_image(img)
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	m.uv1_scale = Vector3(120, 120, 1)   # 1 m squares
	fl.material_override = m
	stage.add_child(fl)
	var sun := DirectionalLight3D.new()
	sun.rotation = Vector3(deg_to_rad(-48), deg_to_rad(-35), 0)
	sun.shadow_enabled = true
	sun.light_energy = 0.9
	sun.light_color = Color("fff1d8")
	stage.add_child(sun)
	var cam := Camera3D.new()
	cam.fov = 34.0
	# its own sky and ambient light (the island's environment expects the island's sun)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("b9d3e2")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("a9bccb")
	env.ambient_light_energy = 0.7
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	cam.environment = env
	stage.add_child(cam)
	cam.current = true
	stage.set_meta("cam", cam)
	return stage


static func _rig(stage: Node3D, model_name: String, pos := Vector3.ZERO) -> Dictionary:
	var model := ModelLib.instance(model_name, false)
	model.position = pos
	model.rotation.y = PI * 0.5    # walks toward +X, seen from the side by a camera at +Z
	stage.add_child(model)
	var anim := CharAnim.new(model)
	return {"model": model, "anim": anim, "t": 0.0}


static func _step(r: Dictionary, dt: float, speed: float) -> void:
	var anim: CharAnim = r["anim"]
	var m: Node3D = r["model"]
	r["t"] = float(r["t"]) + dt
	m.position += Vector3(sin(anim._yaw), 0.0, cos(anim._yaw)) * speed * dt
	anim.update(dt, speed, r["t"])


static func _free(r: Dictionary) -> void:
	(r["model"] as Node3D).free()


# ------------------------------------------------------------------ slide
static func _slide_tests(stage: Node3D, fails: Array) -> void:
	# the player at stick speeds (normal 5.2, sprint 7.8; acceleration 30 m/s^2),
	# villagers at their own stroll and hurry-home speeds (Npc.gait_speeds, 3.5)
	var cases := [["char_player", [1.25, 2.0, 3.0, 5.2, 7.8], 30.0, [1.25, 5.2, 7.8]]]
	for nm in ["char_kakek", "char_nenek", "char_anak", "char_ibu", "char_kades", "char_preman"]:
		var r0 := _rig(stage, nm)
		var gs := Npc.gait_speeds(r0["anim"], nm)
		_free(r0)
		cases.append([nm, [gs.x, gs.y], 3.5, [gs.x, gs.y]])
	for c in cases:
		for v in c[1]:
			var r := _rig(stage, c[0])
			var anim: CharAnim = r["anim"]
			var sp := 0.0
			for i in 90:
				sp = move_toward(sp, v, float(c[2]) * DT)
				_step(r, DT, sp)
			var probe := FootProbe.new(r["model"])
			for i in 240:
				_step(r, DT, v)
				probe.sample(DT, v, 0.0)
			var res := probe.result()
			var gate: bool = v in c[3]
			var bad: bool = gate and float(res["mean"]) > SLIDE_MAX
			var what := ""
			if c[0] != "char_player":
				what = "stroll" if v == c[1][0] else "hurry"
			print("[bench] slide %-12s %.2f m/s %-6s clip=%-4s rate=%.2f (%.1f steps/s) stride=%.2f  stance mean=%4.1f%% p90=%4.1f%% (n=%d)  incl. touchdown=%4.1f%%  ankle=%4.1f%%  src=%s%s" % [
				c[0], v, what, anim._cur_kind, anim._rate, 2.0 * anim._rate / maxf(anim.ap.current_animation_length, 0.01),
				anim._stride_k, 100.0 * float(res["mean"]), 100.0 * float(res["p90"]), res["n"], 100.0 * float(res["loose"]),
				100.0 * float(res["ankle"]), anim._gait_src, "  <-- FAIL" if bad else ""])
			if bad:
				fails.append("slide %s %.2f" % [c[0], v])
			_free(r)


static func _noextras_tests(stage: Node3D, fails: Array) -> void:
	## The fallback gait measurement (a GLB exported without walk_speed/run_speed):
	## strip the extras and check the feet still stay planted.
	for c in [["char_player", [0.9, 5.2]], ["char_kakek", [0.82, 1.22]], ["char_preman", [0.95, 2.0]]]:
		var model := ModelLib.instance(c[0], false)
		model.rotation.y = PI * 0.5
		stage.add_child(model)
		var ref := CharAnim.new(model).walk_run_speeds()
		for n in model.find_children("*", "", true, false) + [model]:
			if n.has_meta("extras"):
				n.remove_meta("extras")
		model.scene_file_path = ""   # bypass the per-file gait cache
		var anim := CharAnim.new(model)
		var r := {"model": model, "anim": anim, "t": 0.0}
		var got := anim.walk_run_speeds()
		for v in c[1]:
			var sp := 0.0
			for i in 120:
				sp = move_toward(sp, v, 30.0 * DT)
				_step(r, DT, sp)
			var probe := FootProbe.new(model)
			for i in 240:
				_step(r, DT, v)
				probe.sample(DT, v, 0.0)
			var res := probe.result()
			var bad: bool = float(res["mean"]) > SLIDE_MAX
			print("[bench] no extras %-12s src=%s walk %.3f run %.3f m/s (exported %.3f / %.3f)  %.2f m/s clip=%s rate=%.2f slide=%4.1f%% p90=%4.1f%% %s" % [
				c[0], anim._gait_src, got.x, got.y, ref.x, ref.y, v, anim._cur_kind, anim._rate,
				100.0 * float(res["mean"]), 100.0 * float(res["p90"]), "<-- FAIL" if bad else "ok"])
			if bad:
				fails.append("no extras %s %.2f" % [c[0], v])
		model.free()


# ------------------------------------------------------------------ actions
static func _action_tests(stage: Node3D, fails: Array) -> void:
	var r := _rig(stage, "char_player")
	var anim: CharAnim = r["anim"]
	for i in 30:
		_step(r, DT, 0.0)
	for kind in ["harvest", "clear", "plant", "fert", "cheer"]:
		anim.play_action(kind)
		var spec: Array = CharAnim.ACTIONS[kind]
		var clip := anim._resolve(spec[0])
		var expect: float = anim.ap.get_animation(clip).length / float(spec[1]) - CharAnim.BLEND_ACTION_OUT
		var lock := 0.0
		var tool_ok: bool = spec[2] == ""
		var tool_d := 0.0
		while anim.is_busy() and lock < 5.0:
			_step(r, DT, 0.0)
			lock += DT
			if spec[2] != "" and absf(lock - expect * 0.5) < DT * 0.5:
				var tn: Node3D = anim._tools.get(spec[2])
				if tn and tn.visible:
					var hand := "hand_L" if spec[2] == "sack" else "hand_R"
					var hp := anim.skel.global_transform * anim.skel.get_bone_global_pose(anim.skel.find_bone(hand)).origin
					tool_d = _tool_world(anim, tn).origin.distance_to(hp)
					tool_ok = tool_d < 0.12
		for i in 36:
			_step(r, DT, 0.0)
		var gone := true
		for k in anim._tools:
			if (anim._tools[k] as Node3D).visible:
				gone = false
		var ok: bool = absf(lock - expect) <= LOCK_TOL and tool_ok and gone
		print("[bench] action %-7s clip=%-7s lock=%.3f s (clip %.3f s - fade) tool=%s in hand (%.3f m from the wrist) gone after=%s %s" % [
			kind, clip, lock, expect, spec[2] if spec[2] != "" else "-", tool_d, gone, "ok" if ok else "<-- FAIL"])
		if not ok:
			fails.append("action " + kind)
	_free(r)


static func _tool_world(anim: CharAnim, tool: Node3D) -> Transform3D:
	## Where the tool is drawn this frame (bone attachments catch up at the end
	## of the frame, so compose from the current pose instead of reading them).
	var par := tool.get_parent() as Node3D
	var bone := anim.skel.find_bone((par.get_parent() as BoneAttachment3D).bone_name)
	return anim.skel.global_transform * anim.skel.get_bone_global_pose(bone) * par.transform * tool.transform


# ------------------------------------------------------------------ pole
static func _pole_dir(anim: CharAnim) -> Vector3:
	var tn: Node3D = anim._tools.get("egrek")
	if tn == null or not tn.visible:
		return Vector3.ZERO
	return _tool_world(anim, tn).basis.y.normalized()


static func _pole_tests(stage: Node3D, fails: Array) -> void:
	for fps in [60, 30]:
		var dt: float = 1.0 / fps
		var r := _rig(stage, "char_player")
		var anim: CharAnim = r["anim"]
		anim.hold_tool("harvest")
		# phase name, seconds, target speed
		var plan := [["stand", 0.6, 0.0], ["walk 2.0", 2.0, 2.0], ["walk 1.25", 1.5, 1.25], ["run 5.2", 2.0, 5.2],
			["sprint 7.8", 1.5, 7.8], ["stop", 0.8, 0.0], ["harvest", -1.0, 0.0], ["after", 0.8, 0.0]]
		var sp := 0.0
		var prev := Vector3.ZERO
		var prev_step := -1.0
		# the pole's angular speed may only build up gradually: its per-frame
		# change grows by at most POLE_ACCEL * dt^2 (plus slack for body motion)
		var ramp_lim := rad_to_deg(CharAnim.POLE_ACCEL * dt * dt) * 1.3 + 0.3
		for ph in plan:
			var worst := 0.0
			var hand_worst := 0.0
			var prev_hand := Vector3.ZERO
			var low := INF
			var t := 0.0
			var speedup := 0.0
			var lag := 0.0
			var lag_n := 0
			var steps := []
			if ph[0] == "harvest":
				anim.play_action("harvest")
			while (ph[1] < 0.0 and (anim.is_busy() or t < 0.1)) or t < ph[1]:
				sp = move_toward(sp, ph[2], (30.0 if ph[2] > sp else 40.0) * dt)
				_step(r, dt, sp)
				t += dt
				var d := _pole_dir(anim)
				if d != Vector3.ZERO and prev != Vector3.ZERO:
					var step := rad_to_deg(prev.angle_to(d))
					worst = maxf(worst, step)
					if prev_step >= 0.0:
						speedup = maxf(speedup, step - prev_step)
					prev_step = step
					if steps.size() < 8:
						steps.append("%.1f" % step)
				prev = d
				if ph[0] == "harvest" and anim.pole_working():
					lag += rad_to_deg(anim._pole_dir.angle_to(anim._pole_target))
					lag_n += 1
				var gw := anim.skel.global_transform * anim.skel.get_bone_global_pose(anim._hand_idx) * anim._grip_root.transform
				var hd := gw.basis.y.normalized()
				if prev_hand != Vector3.ZERO:
					hand_worst = maxf(hand_worst, rad_to_deg(prev_hand.angle_to(hd)))
				prev_hand = hd
				var tn: Node3D = anim._tools.get("egrek")
				if tn and tn.visible:
					low = minf(low, (_tool_world(anim, tn) * Vector3(0, -CharAnim.POLE_BUTT, 0)).y)
			var lim := POLE_MOVE_MAX_DEG if ph[0] in ["harvest", "after"] else POLE_CARRY_MAX_DEG
			lim *= 60.0 / fps
			var ok := worst <= lim and speedup <= ramp_lim
			var extra := ""
			if lag_n > 0:
				extra = "  lag behind the grip %.1f deg mean" % (lag / lag_n)
			if ph[0] == "after":
				extra = "  first frames %s" % " ".join(steps)
			print("[bench] pole %d fps %-10s max change %5.1f deg/frame (limit %.0f; the hand's own grip axis %5.1f)  speed-up %4.2f deg/frame^2 (limit %.2f)  pole butt lowest %.2f m%s %s" % [
				fps, ph[0], worst, lim, hand_worst, speedup, ramp_lim, low, extra, "ok" if ok else "<-- FAIL"])
			if not ok:
				fails.append("pole %d fps %s" % [fps, ph[0]])
		_free(r)
	# a harvest from empty hands: the pole's elevation frame by frame (30 fps)
	var r2 := _rig(stage, "char_player")
	var a2: CharAnim = r2["anim"]
	for i in 20:
		_step(r2, 1.0 / 30.0, 0.0)
	a2.play_action("harvest")
	var elev := []
	for i in 40:
		_step(r2, 1.0 / 30.0, 0.0)
		var d := _pole_dir(a2)
		elev.append("-" if d == Vector3.ZERO else "%.0f" % rad_to_deg(asin(clampf(d.y, -1.0, 1.0))))
	print("[bench] pole elevation during a harvest (deg, 30 fps): ", " ".join(elev))
	_free(r2)
	_grow_test(stage, fails)
	_basket_test(stage, fails)


static func _tip(anim: CharAnim, kind: String, local: Vector3) -> Vector3:
	var tn: Node3D = anim._tools.get(kind)
	if tn == null or not tn.visible:
		return Vector3.INF
	return _tool_world(anim, tn) * local


static func _grow_test(stage: Node3D, fails: Array) -> void:
	## Tools ease in and out of the fist: the pole's tip (2.4 m out) must not jump.
	var r := _rig(stage, "char_player")
	var anim: CharAnim = r["anim"]
	for i in 20:
		_step(r, DT, 0.0)
	for phase in ["grow", "shrink"]:
		anim.hold_tool("harvest" if phase == "grow" else "")
		var prev := _tip(anim, "egrek", Vector3(0, 2.4, 0))
		if phase == "grow":
			prev = anim._grip_root.global_position   # it grows out of the fist
		var moves := []
		var worst := 0.0
		for i in 24:
			_step(r, DT, 0.0)
			var p := _tip(anim, "egrek", Vector3(0, 2.4, 0))
			if p == Vector3.INF or prev == Vector3.INF:
				prev = p
				continue
			var m := p.distance_to(prev)
			worst = maxf(worst, m)
			moves.append("%.2f" % m)
			prev = p
		var ok := worst <= 0.35
		print("[bench] pole %s: tip moves per 1/60 s frame %s (max %.2f m, limit 0.35) %s" % [phase, " ".join(moves), worst, "ok" if ok else "<-- FAIL"])
		if not ok:
			fails.append("pole " + phase)
	_free(r)


static func _basket_test(stage: Node3D, fails: Array) -> void:
	## A pole carried on the shoulder must pass beside the harvest basket on the
	## back (Player: chest bone, 0.27 m back; open rim r 0.155 m, bunches peek out).
	for loaded in [false, true]:
		var r := _rig(stage, "char_player")
		var anim: CharAnim = r["anim"]
		var basket := Node3D.new()
		if not anim.attach_to_bone("chest", basket, Vector3(0, 0.02, -0.27)):
			_free(r)
			return
		anim.back_load = loaded
		anim.hold_tool("harvest")
		var sp := 0.0
		var clear := INF
		for ph in [[0.8, 0.0], [1.5, 1.25], [1.5, 5.2], [1.0, 7.8], [1.0, 0.0]]:
			var t := 0.0
			while t < ph[0]:
				sp = move_toward(sp, ph[1], 30.0 * DT)
				_step(r, DT, sp)
				t += DT
				var tn: Node3D = anim._tools.get("egrek")
				if tn == null or not tn.visible:
					continue
				var pole := _tool_world(anim, tn)
				var ba := basket.get_parent() as BoneAttachment3D
				var bxf := anim.skel.global_transform * anim.skel.get_bone_global_pose(anim.skel.find_bone(ba.bone_name)) * basket.transform
				var inv := bxf.affine_inverse()
				for k in 25:
					var q := inv * (pole * Vector3(0, lerpf(-0.5, 2.3, k / 24.0) + 0.0, 0))
					if q.y < -0.22 or q.y > 0.22:
						continue
					var rad := lerpf(0.12, 0.155, clampf((q.y + 0.2) / 0.27, 0.0, 1.0))
					clear = minf(clear, Vector2(q.x, q.z).length() - rad)
		var ok: bool = not loaded or clear >= 0.02
		print("[bench] pole beside the back basket (back_load=%s): closest %.3f m from the basket wall %s" % [loaded, clear,
			("ok" if ok else "<-- FAIL") if loaded else "(reference)"])
		if not ok:
			fails.append("pole basket")
		_free(r)


# ------------------------------------------------------------------ fades
static func _clip_rot(anim: CharAnim, clip: String, bone: String, t: float) -> Quaternion:
	## A bone's rotation in a clip at time t, straight from the Animation resource.
	var a := anim.ap.get_animation(clip)
	var path := NodePath(str(anim.ap.get_node(anim.ap.root_node).get_path_to(anim.skel)) + ":" + bone)
	var tr := a.find_track(path, Animation.TYPE_ROTATION_3D)
	var rest := anim.skel.get_bone_rest(anim.skel.find_bone(bone)).basis.get_rotation_quaternion()
	if tr < 0:
		return rest
	var tt := fposmod(t, a.length) if a.loop_mode != Animation.LOOP_NONE else clampf(t, 0.0, a.length)
	return a.rotation_track_interpolate(tr, tt)


static func _pop_tests(stage: Node3D, fails: Array) -> void:
	## Cross-fades must not jump. For every frame of every fade and every bone:
	##  - the fade's first frame shows the old clip and the frame it ends shows
	##    the new clip (within 0.5 deg): it starts and lands without a snap;
	##  - in between, the pose moves no more per frame than the two clips do plus
	##    the weight change times their gap (x2 slack: Godot interpolates the
	##    rest-relative rotations, a slightly longer path than a slerp).
	## Godot's deterministic mixer, for one, fails this: its fade weights are not
	## normalised, so bones stray up to ~6 deg and snap back as the fade ends.
	## Clips are sampled straight from the Animation resources. Bones driven by
	## code on top (head/neck look, stride-scaled legs) are left out.
	for model_name in ["char_player", "char_kakek"]:
		var r := _rig(stage, model_name)
		var anim: CharAnim = r["anim"]
		var sk := anim.skel
		var plan := [["idle", 1.0, 0.0, ""], ["walk", 1.5, 1.25, ""], ["run", 1.5, 5.2, ""], ["sprint", 1.0, 7.8, ""],
			["stop", 1.0, 0.0, ""], ["harvest", 1.6, 0.0, "harvest"], ["harvest2", 0.7, 0.0, "harvest"],
			["plant", 1.6, 0.0, "plant"], ["walk2", 1.0, 1.25, ""], ["chop", 1.2, 0.0, "clear"], ["talk", 1.5, 0.0, "talk"],
			["cheer", 1.4, 0.0, "cheer"], ["sad walk", 1.2, 0.94, "sad"], ["sad", 1.2, 0.0, "sad"], ["wave", 1.4, 0.0, "wave"],
			["end", 0.8, 0.0, ""]]
		var skip := ["head", "neck"]
		var sp := 0.0
		var frames := 0
		var checked := 0
		var nested := 0
		var worst_end := 0.0
		var worst_end_at := ""
		var worst_step := 0.0
		var worst_step_at := ""
		var pairs := {}
		var prev := {}      # bone -> [display, from pose, to pose] last frame of the same fade
		var prev_fade := {}
		for ph in plan:
			var t := 0.0
			anim.idle_clip = "sad" if ph[3] == "sad" else "idle"
			if ph[3] in ["harvest", "plant", "clear", "cheer", "wave"]:
				anim.play_action(ph[3])
			while t < ph[1]:
				if ph[3] == "talk":
					anim.talk_t = 0.2
				var acc := 30.0 if model_name == "char_player" else 3.5
				sp = move_toward(sp, ph[2], (acc if ph[2] > sp else acc * 1.4) * DT)
				_step(r, DT, sp)
				t += DT
				frames += 1
				var f := anim.fade
				var active: bool = not f.is_empty() and f["from"] != "" and float(f["w"]) < 1.0 + 1e-4 \
					and float(f["t"]) <= float(f["len"]) + anim._rate * DT * 1.01
				if not active or f["nested"]:
					nested += 1 if active else 0
					prev = {}
					continue
				if f != prev_fade:
					prev = {}
				prev_fade = f
				checked += 1
				var from: String = f["from"]
				var to: String = anim.ap.current_animation
				var w: float = f["w"]
				var dw: float = anim._rate * DT / maxf(float(f["len"]), 0.0001)
				pairs["%s>%s" % [from.trim_prefix("alt/"), to.trim_prefix("alt/")]] = true
				var cur := {}
				for b in sk.get_bone_count():
					var bn := sk.get_bone_name(b)
					if bn in skip or (anim._stride_k > 1.005 and (b in anim._stride_bones or b in anim._swing_bones or b in anim._feet)):
						continue
					var qd := sk.get_bone_pose_rotation(b)
					var qa := _clip_rot(anim, from, bn, f["from_t"])
					var qb := _clip_rot(anim, to, bn, anim.ap.current_animation_position)
					cur[b] = [qd, qa, qb]
					if w <= 0.0 or w >= 1.0:
						var e := rad_to_deg(qd.angle_to(qa if w <= 0.0 else qb))
						if e > worst_end:
							worst_end = e
							worst_end_at = "%s %s>%s w=%.0f (%s)" % [bn, from, to, w, ph[0]]
					if prev.has(b):
						var p: Array = prev[b]
						var step := rad_to_deg((p[0] as Quaternion).angle_to(qd))
						var bound := rad_to_deg((p[1] as Quaternion).angle_to(qa) + (p[2] as Quaternion).angle_to(qb)) \
							+ rad_to_deg(qa.angle_to(qb)) * dw * 2.0 + 0.3
						if step - bound > worst_step:
							worst_step = step - bound
							worst_step_at = "%s %s>%s w=%.2f moved %.1f deg, allowed %.1f (%s)" % [bn, from, to, w, step, bound, ph[0]]
				prev = cur
		var ok := worst_end < 0.5 and worst_step <= 0.0
		print("[bench] fades %s: %d frames, %d inside single fades (%s), %d in nested fades (not checked)" % [
			model_name, frames, checked, ", ".join(pairs.keys()), nested])
		print("[bench]   fade ends off the clips by at most %.2f deg %s; worst frame step beyond the allowed %.2f deg %s  %s" % [
			worst_end, worst_end_at, maxf(worst_step, 0.0), worst_step_at, "ok" if ok else "<-- FAIL"])
		if not ok:
			fails.append("fades " + model_name)
		_free(r)


# ------------------------------------------------------------------ tick
static func _tick_test(stage: Node3D, fails: Array) -> void:
	var r := _rig(stage, "char_buruh")
	var anim: CharAnim = r["anim"]
	var m: Node3D = r["model"]
	anim.play_action("harvest")
	_step(r, DT, 0.0)
	var t := 0.0
	while anim.is_busy() and t < 5.0:
		anim.tick(DT)
		t += DT
	_step(r, DT, 0.0)
	var ok := not anim.is_busy() and t < 1.3
	print("[bench] tick: an action ends after %.2f s without update() (busy=%s) %s" % [t, anim.is_busy(), "ok" if ok else "<-- FAIL"])
	if not ok:
		fails.append("tick")
	for i in 30:
		_step(r, DT, 0.0)
	print("[bench] tick: back to %s" % anim._cur)
	# off screen the villager keeps turning toward where it walks, and comes back
	# on screen on the right clip at the right time, not fading from a stale pose
	var yaw0 := anim._yaw
	for i in 90:
		anim.turn_towards(yaw0 + PI * 0.75, DT, 6.0)
		m.position += Vector3(sin(anim._yaw), 0.0, cos(anim._yaw)) * 0.8 * DT
		anim.tick(DT, 0.8)
	var yaw_err := rad_to_deg(absf(wrapf(m.rotation.y - anim._yaw, -PI, PI)))
	var turned := rad_to_deg(absf(wrapf(anim._yaw - yaw0, -PI, PI)))
	_step(r, DT, 0.8)
	var res_ok: bool = anim._cur_kind == "walk" and anim.fade.is_empty() and yaw_err < 0.01 and turned > 120.0
	var worst := 0.0
	for bn in ["thigh_L", "shin_R", "upperarm_L", "spine"]:
		var bi := anim.skel.find_bone(bn)
		if bi < 0:
			continue
		var q := anim.skel.get_bone_pose_rotation(bi)
		worst = maxf(worst, rad_to_deg(q.angle_to(_clip_rot(anim, anim._cur, bn, anim.ap.current_animation_position))))
	res_ok = res_ok and worst < 0.5
	print("[bench] tick: turned %.0f deg while off screen, model yaw off by %.3f deg; back on screen: clip=%s fade=%s pose off the clip by %.2f deg %s" % [
		turned, yaw_err, anim._cur_kind, "none" if anim.fade.is_empty() else "yes", worst, "ok" if res_ok else "<-- FAIL"])
	if not res_ok:
		fails.append("tick resume")
	# an action started on screen, off screen for a while, back mid-action
	for i in 30:
		_step(r, DT, 0.0)
	anim.play_action("harvest")
	_step(r, DT, 0.0)
	for i in 24:
		anim.tick(DT)
	_step(r, DT, 0.0)
	var pos := anim.ap.current_animation_position
	var mid_ok: bool = anim._cur_kind == "action" and absf(pos - 26.0 * DT) < 0.02 and anim.fade.is_empty()
	print("[bench] tick: back mid-action at clip time %.3f s (expected %.3f) %s" % [pos, 26.0 * DT, "ok" if mid_ok else "<-- FAIL"])
	if not mid_ok:
		fails.append("tick mid-action")
	_free(r)


# ------------------------------------------------------------------ film
static func _film(at: Node, stage: Node3D) -> void:
	## Frame sequences 0.1 s apart (6 steps of 1/60 s between shots).
	var cam: Camera3D = stage.get_meta("cam")
	# lambdas capture locals by value: keep the rig being filmed in a dictionary
	var st := {"sp": 0.0, "r": _rig(stage, "char_player")}
	var roll := func(tag: String, n: int, speed: float, steps: int, off: Vector3, look_up: float) -> void:
		var r: Dictionary = st["r"]
		var m: Node3D = r["model"]
		for i in n:
			for k in steps:
				st["sp"] = move_toward(st["sp"], speed, (30.0 if speed > st["sp"] else 40.0) * DT)
				_step(r, DT, st["sp"])
			cam.global_position = m.global_position + off
			cam.look_at(m.global_position + Vector3(0, look_up, 0), Vector3.UP)
			await at.shot("bench_%s_%d" % [tag, i], 2)
	var anim: CharAnim = st["r"]["anim"]
	var side := Vector3(0.0, 0.75, 4.0)
	await roll.call("idle", 2, 0.0, 30, side, 0.5)
	await roll.call("walk", 6, 1.25, 6, side, 0.5)
	await roll.call("run", 6, 5.2, 6, side, 0.5)
	await roll.call("stop", 6, 0.0, 6, side, 0.5)
	anim.play_action("harvest")
	await roll.call("harvest", 12, 0.0, 6, Vector3(0.8, 1.2, 5.2), 1.05)
	await roll.call("rest", 1, 0.0, 30, side, 0.5)
	anim.play_action("plant")
	await roll.call("plant", 8, 0.0, 9, Vector3(1.6, 0.9, 3.6), 0.4)
	anim.play_action("clear")
	await roll.call("chop", 6, 0.0, 9, Vector3(1.6, 0.9, 3.6), 0.45)
	anim.hold_tool("harvest")
	await roll.call("holdwalk", 6, 1.25, 6, Vector3(0.8, 1.2, 5.2), 1.05)
	await roll.call("holdrun", 4, 5.2, 6, Vector3(0.8, 1.2, 5.2), 1.05)
	await roll.call("holdstop", 3, 0.0, 12, Vector3(0.8, 1.2, 5.2), 1.05)
	anim.play_action("harvest")
	await roll.call("holdharvest", 6, 0.0, 12, Vector3(0.8, 1.2, 5.2), 1.05)
	anim.hold_tool("")
	_free(st["r"])
	st["r"] = _rig(stage, "char_kakek")
	st["sp"] = 0.0
	await roll.call("kakek", 6, 1.25, 6, side, 0.5)
	_free(st["r"])


# ------------------------------------------------------------------ probe
class FootProbe:
	## CPU-skins the vertices weighted to the feet. Each step, the lowest one
	## (the sole in contact) is tracked to the next step: its ground-plane speed
	## over the character's speed is the slide (0 = planted, 1 = skating).
	var mi: MeshInstance3D
	var skel: Skeleton3D
	var bind_bone := PackedInt32Array()
	var bind_pose: Array[Transform3D] = []
	var verts := PackedVector3Array()
	var vb := PackedInt32Array()
	var vw := PackedFloat32Array()
	var feet := PackedInt32Array()
	var prev := PackedVector3Array()
	var prev_ankles: Array = []
	var rows: Array = []      # [lowest sole height, slide ratio]
	var ankle_rows: Array = []

	func _init(model: Node3D) -> void:
		skel = CharAnim._find_type(model, "Skeleton3D") as Skeleton3D
		for c in ModelLib.find_meshes(model):
			if c.skin != null:
				mi = c
				break
		if mi == null or skel == null:
			return
		feet = PackedInt32Array([skel.find_bone("foot_L"), skel.find_bone("foot_R")])
		var skin := mi.skin
		for i in skin.get_bind_count():
			var nm := String(skin.get_bind_name(i))
			bind_bone.append(skel.find_bone(nm) if nm != "" else skin.get_bind_bone(i))
			bind_pose.append(skin.get_bind_pose(i))
		var mesh := mi.mesh
		for s in mesh.get_surface_count():
			var arr := mesh.surface_get_arrays(s)
			var nw := 8 if (mesh.surface_get_format(s) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS) != 0 else 4
			var vs: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			if arr[Mesh.ARRAY_BONES] == null or arr[Mesh.ARRAY_WEIGHTS] == null:
				continue
			var bs: PackedInt32Array = arr[Mesh.ARRAY_BONES]
			var ws: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
			for v in vs.size():
				var fw := 0.0
				for j in nw:
					var b: int = bs[v * nw + j]
					if b >= 0 and b < bind_bone.size() and bind_bone[b] in feet:
						fw += ws[v * nw + j]
				if fw < 0.5:
					continue
				verts.append(vs[v])
				for j in 4:
					vb.append(bs[v * nw + j])
					vw.append(ws[v * nw + j])

	func positions() -> PackedVector3Array:
		var out := PackedVector3Array()
		out.resize(verts.size())
		var mats: Array[Transform3D] = []
		for i in bind_bone.size():
			mats.append(skel.get_bone_global_pose(bind_bone[i]) * bind_pose[i] if bind_bone[i] >= 0 else Transform3D.IDENTITY)
		var xf := mi.global_transform
		for v in verts.size():
			var p := Vector3.ZERO
			for j in 4:
				var w := vw[v * 4 + j]
				if w > 0.0:
					p += (mats[vb[v * 4 + j]] * verts[v]) * w
			out[v] = xf * p
		return out

	func sample(dt: float, ground_speed: float, ground_y: float) -> void:
		if mi == null:
			return
		var p := positions()
		if prev.size() == p.size() and p.size() > 0:
			var c := 0
			for i in prev.size():
				if prev[i].y < prev[c].y:
					c = i
			var d := Vector2(p[c].x - prev[c].x, p[c].z - prev[c].z).length() / dt
			rows.append([prev[c].y - ground_y, d / maxf(ground_speed, 0.01), p[c].y - ground_y])
		prev = p
		var ank := []
		for f in feet:
			ank.append(skel.global_transform * skel.get_bone_global_pose(f).origin)
		if prev_ankles.size() == 2:
			var lo := 0 if (prev_ankles[0] as Vector3).y <= (prev_ankles[1] as Vector3).y else 1
			var a0: Vector3 = prev_ankles[lo]
			var a1: Vector3 = ank[lo]
			ankle_rows.append([a0.y - ground_y, Vector2(a1.x - a0.x, a1.z - a0.z).length() / dt / maxf(ground_speed, 0.01), a1.y - ground_y])
		prev_ankles = ank

	static func _planted(src: Array, band: float, both_ends: bool) -> Array:
		## Slide ratios of the steps where the tracked point is on the ground:
		## within `band` of the lowest height seen (at the start of the step, and
		## with both_ends also at its end, which leaves out lift-off and the
		## last airborne frame before touchdown).
		var ymin := INF
		for r in src:
			ymin = minf(ymin, r[0])
		var vals := []
		for r in src:
			if r[0] < ymin + band and (not both_ends or r[2] < ymin + band):
				vals.append(r[1])
		vals.sort()
		return vals

	static func _mean(vals: Array) -> float:
		var m := 0.0
		for x in vals:
			m += x
		return m / maxf(vals.size(), 1)

	func result() -> Dictionary:
		var vals := _planted(rows, 0.008, true)
		var n := vals.size()
		return {
			"mean": _mean(vals), "n": n,
			"median": vals[n / 2] if n > 0 else 0.0,
			"p90": vals[int(n * 0.9)] if n > 0 else 0.0,
			"loose": _mean(_planted(rows, 0.012, false)),
			"ankle": _mean(_planted(ankle_rows, 0.012, false)),
		}
