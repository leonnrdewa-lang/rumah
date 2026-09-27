class_name AnimBench
extends RefCounted
## Numeric animation checks on a bare, lit floor (autotest "anim", part "bench"):
## planted-foot slide at game speeds, action lock times and tools in the hand,
## harvesting pole steadiness, pops in the cross-fades, off-screen timers, plus
## frame sequences 0.1 s apart from a side camera.
## Characters are stepped at a fixed 1/60 s (or 1/30 s), so the numbers do not
## depend on how fast the machine renders.

const DT := 1.0 / 60.0
const SLIDE_MAX := 0.10          # planted foot speed / ground speed (1.25 and 5.2 m/s)
const POLE_CARRY_MAX_DEG := 4.0  # pole direction change per 1/60 s frame while carried
const POLE_WORK_MAX_DEG := 12.0  # ... while harvesting
const LOCK_TOL := 0.05           # s


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
	img.fill(Color("b7c784"))
	img.set_pixel(1, 0, Color("9aad68"))
	img.set_pixel(0, 1, Color("9aad68"))
	var m := StandardMaterial3D.new()
	m.albedo_texture = ImageTexture.create_from_image(img)
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	m.uv1_scale = Vector3(120, 120, 1)   # 1 m squares
	fl.material_override = m
	stage.add_child(fl)
	var sun := DirectionalLight3D.new()
	sun.rotation = Vector3(deg_to_rad(-48), deg_to_rad(-35), 0)
	sun.shadow_enabled = true
	sun.light_energy = 1.1
	stage.add_child(sun)
	var cam := Camera3D.new()
	cam.fov = 34.0
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
	# [model, speeds, acceleration like the game (player 30 m/s^2, villagers 3.5)]
	var cases := [
		["char_player", [1.25, 2.0, 3.0, 5.2, 7.8], 30.0],
		["char_kakek", [0.94, 1.25, 2.0], 3.5],
		["char_anak", [1.25, 2.0], 3.5],
		["char_nenek", [0.94, 1.25], 3.5],
		["char_preman", [1.25, 2.0], 3.5],
		["char_ibu", [1.25], 3.5],
	]
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
			var gate: bool = v == 1.25 or (v == 5.2 and c[0] == "char_player")
			var bad: bool = gate and float(res["mean"]) > SLIDE_MAX
			print("[bench] slide %-12s %.2f m/s  clip=%-4s rate=%.2f stride=%.2f  sole mean=%4.1f%% median=%4.1f%% p90=%4.1f%% (n=%d)  ankle mean=%4.1f%%  src=%s%s" % [
				c[0], v, anim._cur_kind, anim._rate, anim._stride_k, 100.0 * float(res["mean"]),
				100.0 * float(res["median"]), 100.0 * float(res["p90"]), res["n"], 100.0 * float(res["ankle"]),
				anim._gait_src, "  <-- FAIL" if bad else ""])
			if bad:
				fails.append("slide %s %.2f" % [c[0], v])
			_free(r)


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
		var expect: float = anim.ap.get_animation(clip).length / float(spec[1]) - CharAnim.BLEND_ACTION_OUT * 0.6
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
		for ph in plan:
			var worst := 0.0
			var hand_worst := 0.0
			var prev_hand := Vector3.ZERO
			var low := INF
			var t := 0.0
			if ph[0] == "harvest":
				anim.play_action("harvest")
			while (ph[1] < 0.0 and (anim.is_busy() or t < 0.1)) or t < ph[1]:
				sp = move_toward(sp, ph[2], (30.0 if ph[2] > sp else 40.0) * dt)
				_step(r, dt, sp)
				t += dt
				var d := _pole_dir(anim)
				if d != Vector3.ZERO and prev != Vector3.ZERO:
					worst = maxf(worst, rad_to_deg(prev.angle_to(d)))
				prev = d
				var gw := anim.skel.global_transform * anim.skel.get_bone_global_pose(anim._hand_idx) * anim._grip_root.transform
				var hd := gw.basis.y.normalized()
				if prev_hand != Vector3.ZERO:
					hand_worst = maxf(hand_worst, rad_to_deg(prev_hand.angle_to(hd)))
				prev_hand = hd
				var tn: Node3D = anim._tools.get("egrek")
				if tn and tn.visible:
					low = minf(low, (_tool_world(anim, tn) * Vector3(0, -0.5, 0)).y)
			var lim := POLE_WORK_MAX_DEG if ph[0] == "harvest" else POLE_CARRY_MAX_DEG
			lim *= 60.0 / fps
			var ok := worst <= lim
			print("[bench] pole %d fps %-10s max change %5.1f deg/frame (limit %.0f; the hand's own grip axis %5.1f)  pole butt lowest %.2f m %s" % [
				fps, ph[0], worst, lim, hand_worst, low, "ok" if ok else "<-- FAIL"])
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


# ------------------------------------------------------------------ pops
static func _pop_tests(stage: Node3D, fails: Array) -> void:
	## A cross-fade that pops shows as one frame whose bone rotation change
	## dwarfs the frames around it.
	for model_name in ["char_player", "char_kakek"]:
		var r := _rig(stage, model_name)
		var anim: CharAnim = r["anim"]
		var sk := anim.skel
		var rows: Array = []
		var labels: Array = []
		var plan := [["idle", 1.0, 0.0, ""], ["walk", 1.5, 1.25, ""], ["run", 1.5, 5.2, ""], ["stop", 1.0, 0.0, ""],
			["harvest", 1.6, 0.0, "harvest"], ["harvest2", 0.7, 0.0, "harvest"], ["plant", 1.6, 0.0, "plant"],
			["walk2", 1.0, 1.25, ""], ["chop", 1.2, 0.0, "clear"], ["talk", 1.5, 0.0, "talk"], ["cheer", 1.4, 0.0, "cheer"],
			["sad walk", 1.2, 0.94, "sad"], ["sad", 1.2, 0.0, "sad"], ["wave", 1.4, 0.0, "wave"], ["end", 0.8, 0.0, ""]]
		var sp := 0.0
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
				var row := []
				for b in sk.get_bone_count():
					row.append(sk.get_bone_pose_rotation(b))
				row.append(sk.get_bone_pose_position(maxi(anim._hips, 0)))
				rows.append(row)
				labels.append(ph[0])
		var nb := sk.get_bone_count()
		var pops := []
		var worst := 0.0
		for b in nb + 1:
			var d := PackedFloat32Array()
			for i in range(1, rows.size()):
				if b < nb:
					d.append(rad_to_deg((rows[i - 1][b] as Quaternion).angle_to(rows[i][b])))
				else:
					d.append((rows[i - 1][b] as Vector3).distance_to(rows[i][b]) * 1000.0)   # hips: mm
			for i in range(2, d.size() - 2):
				var around := maxf(d[i - 2], d[i + 2])
				worst = maxf(worst, d[i] / maxf(around, 1.0))
				if d[i] > 3.0 and d[i] > 2.5 * around:
					pops.append("%s@%s(%.1f vs %.1f)" % [sk.get_bone_name(b) if b < nb else "hips_pos", labels[i + 1], d[i], around])
		print("[bench] pops %s: %d frames through idle/walk/run/stop/actions/talk/sad/wave; worst spike ratio %.2f; pops: %s" % [
			model_name, rows.size(), worst, "none" if pops.is_empty() else ", ".join(pops.slice(0, 8))])
		if not pops.is_empty():
			fails.append("pops " + model_name)
		_free(r)


# ------------------------------------------------------------------ tick
static func _tick_test(stage: Node3D, fails: Array) -> void:
	var r := _rig(stage, "char_buruh")
	var anim: CharAnim = r["anim"]
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
	await roll.call("harvest", 12, 0.0, 6, Vector3(0.6, 1.3, 6.2), 1.1)
	await roll.call("rest", 1, 0.0, 30, side, 0.5)
	anim.play_action("plant")
	await roll.call("plant", 8, 0.0, 9, Vector3(1.6, 0.9, 3.6), 0.4)
	anim.play_action("clear")
	await roll.call("chop", 6, 0.0, 9, Vector3(1.6, 0.9, 3.6), 0.45)
	anim.hold_tool("harvest")
	await roll.call("holdwalk", 6, 1.6, 6, Vector3(0.6, 1.2, 6.0), 1.0)
	await roll.call("holdrun", 4, 5.2, 6, Vector3(0.6, 1.2, 6.0), 1.0)
	await roll.call("holdstop", 3, 0.0, 12, Vector3(0.6, 1.2, 6.0), 1.0)
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
			rows.append([prev[c].y - ground_y, d / maxf(ground_speed, 0.01)])
		prev = p
		var ank := []
		for f in feet:
			ank.append(skel.global_transform * skel.get_bone_global_pose(f).origin)
		if prev_ankles.size() == 2:
			var lo := 0 if (prev_ankles[0] as Vector3).y <= (prev_ankles[1] as Vector3).y else 1
			var a0: Vector3 = prev_ankles[lo]
			var a1: Vector3 = ank[lo]
			ankle_rows.append([a0.y - ground_y, Vector2(a1.x - a0.x, a1.z - a0.z).length() / dt / maxf(ground_speed, 0.01)])
		prev_ankles = ank

	static func _planted(src: Array, band: float) -> Array:
		var ymin := INF
		for r in src:
			ymin = minf(ymin, r[0])
		var vals := []
		for r in src:
			if r[0] < ymin + band:
				vals.append(r[1])
		vals.sort()
		return vals

	func result() -> Dictionary:
		# planted = steps whose lowest sole point is within 1.2 cm of the lowest seen
		var vals := _planted(rows, 0.012)
		var avals := _planted(ankle_rows, 0.012)
		var n := vals.size()
		var mean := 0.0
		for x in vals:
			mean += x
		var amean := 0.0
		for x in avals:
			amean += x
		return {
			"mean": mean / maxf(n, 1), "n": n,
			"median": vals[n / 2] if n > 0 else 0.0,
			"p90": vals[int(n * 0.9)] if n > 0 else 0.0,
			"ankle": amean / maxf(avals.size(), 1),
		}
