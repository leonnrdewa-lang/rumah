class_name CharAnim
extends RefCounted
## Character animation.
##
## v2 models (one skinned mesh + an AnimationPlayer holding the clips named in
## ART_DIRECTION_V2.md: idle walk run harvest chop plant talk cheer sad wave)
## are cross-faded here. The AnimationPlayer is advanced manually from update()
## so procedural secondary motion can be layered on top of the clips: turn lean,
## start/stop squash, head look-at, idle variety, and hand tools that ride on
## BoneAttachment3Ds.
##
## v1 models (rigid ArmL/LegL/Head nodes, no AnimationPlayer) fall back to the
## old procedural limb swinging, so nothing breaks while assets are replaced.

const LOOP_CLIPS := ["idle", "walk", "run", "talk", "sad"]
## action kind -> [clip, playback rate, tool]
const ACTIONS := {
	"harvest": ["harvest", 1.0, "egrek"],
	"chop": ["chop", 1.0, "parang"],
	"clear": ["chop", 1.0, "parang"],
	"plant": ["plant", 1.0, "trowel"],
	"fert": ["plant", 1.45, "sack"],
	"cheer": ["cheer", 1.0, ""],
	"wave": ["wave", 1.0, ""],
}
## what to play when a model lacks a clip
const CLIP_FALLBACK := {
	"run": "walk", "talk": "idle", "sad": "idle", "plant": "harvest", "chop": "harvest",
	"harvest": "chop", "cheer": "wave", "wave": "cheer",
}
const BLEND_LOCO := 0.2
const BLEND_ACTION_IN := 0.12
const BLEND_ACTION_OUT := 0.25
## Locomotion playback. Every v2 GLB carries the ground speed its walk and run
## clips cover at 1x (glTF extras on the armature node: walk_speed, run_speed);
## playback rate = velocity / that speed, so a planted foot keeps pace with the
## ground. The run clip takes over once the walk would need more than
## WALK_TO_RUN x (about 1.5 m/s on the player: the normal keyboard speed of
## 5.2 m/s would need an 8x walk, so the player runs on purpose and the walk shows
## on villagers and with a half-pushed stick).
const WALK_TO_RUN := 2.35
const RUN_TO_WALK := 0.85   # hysteresis: back to walk below this share of the switch speed
const MIN_RATE := 0.35
## Beyond these rates the cadence looks frantic, so the stride is lengthened
## instead (leg swing scaled, calibrated per clip, up to STRIDE_MAX) and only the
## rest is made up with a faster cadence, up to HARD_RATE.
const MAX_RATE := {"walk": 2.5, "run": 2.45}
const HARD_RATE := 3.4
const STRIDE_MAX := 1.5
const STRIDE_KS := [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
## Fallback when a GLB has no gait extras: the speed is estimated from the ankle's
## travel, which covers this share of a cycle's ground travel (v2 clips).
const STANCE := {"walk": 0.55, "run": 0.30}
const STRIDE_BONES := ["thigh_L", "shin_L", "thigh_R", "shin_R"]
const SWING_BONES := ["upperarm_L", "upperarm_R", "forearm_L", "forearm_R"]
## The harvesting pole: while harvesting it follows the two-handed grip of the
## clip; carried outside an action it rests against the right shoulder, leaning
## back (model space: +Z front, -X the character's right). Its direction is eased
## over time (exponential, POLE_FOLLOW per second, at most POLE_MAX_SPEED rad/s).
const POLE_CARRY_DIR := Vector3(0.1, 1.0, -0.42)
const POLE_CARRY_SLIDE := 0.28   # m the pole rides up in the fist when carried
const POLE_FOLLOW := 16.0
const POLE_MAX_SPEED := 7.0

static var _gait_cache := {}
static var _tool_meshes := {}
static var _tool_mats := {}

# ---------------------------------------------------------------- public
var root: Node3D
var hand_r: Node3D          # BoneAttachment3D on hand_R (v2) or the HandR node (v1)
var talk_t := 0.0           # >0: play the talk loop instead of idle (callers refresh it each frame)
var idle_clip := "idle"     # "sad" for villagers who lost their land
var skinned := false        # true when driving a v2 AnimationPlayer
var idle_seed := randf() * 10.0
var held_tool := ""         # tool kept in hand between actions (see hold_tool)

# ---------------------------------------------------------------- v2 state
var ap: AnimationPlayer
var skel: Skeleton3D
var _cur := ""              # animation name currently playing (resolved)
var _cur_kind := ""         # "idle" / "walk" / "run" / "talk" / "sad" / "action"
var _rate := 1.0
var _act_left := 0.0
var _act_rate := 1.0
var _act_alt := false
var _act_kind := ""
var _nat := {"walk": 1.1, "run": 2.6}   # m/s each clip covers at 1x (model units, unscaled)
var _gain := {}                          # clip -> stride gain per STRIDE_KS entry
var _pivots := {}                        # clip -> {bone: cycle-mean rotation} for stride scaling
var _gait_src := "default"               # "extras" / "measured" / "default"
var _grip_offset := -1.0                 # fist centre past the wrist (m), from the extras
var _run_on := 2.9
var _run_off := 2.4
var _running := false
var _idle_rate := 1.0
var _head := -1
var _neck := -1
var _hips := -1
var _feet: Array[int] = []
var _override_bones: Array[int] = []
var _rest_rot := {}
var _stride_bones: Array[int] = []
var _swing_bones: Array[int] = []
var _stride_k := 1.0
var fade := {}                           # the cross-fade in progress (read by the anim bench)
var _pole_dir := Vector3.UP              # model space
var _pole_slide := 0.0
var _pole_fresh := true
var _sk_xf := Transform3D.IDENTITY   # skeleton -> model space
var _sk_up := Vector3.UP
var _sk_fwd := Vector3.BACK
var _grip_root: Node3D
var _grip_l_root: Node3D
var _hand_idx := -1
var _tools := {}
var _tool_kind := ""
var _tool_s := 0.0
var _tool_timer := 0.0

# ---------------------------------------------------------------- secondary motion
var _yaw := 0.0
var _yaw_applied := 0.0
var _yaw_vel := 0.0
var _yaw_prev := 0.0
var _turn_rate := 0.0
var _turned := false
var _lean := 0.0
var _pitch := 0.0
var _prev_speed := 0.0
var _accel := 0.0
var _was_moving := false
var _sq := 0.0
var _sq_vel := 0.0
var _base_scale := Vector3.ONE
var _look_pos := Vector3.ZERO
var _look_on := false
var _look_yaw := 0.0
var _look_pitch := 0.0
var _idle_look := 0.0
var _idle_look_t := 0.0

# ---------------------------------------------------------------- v1 state
var hips: Node3D
var arm_l: Node3D
var arm_r: Node3D
var leg_l: Node3D
var leg_r: Node3D
var head: Node3D
var hips_y := 0.3
var phase := 0.0
var action_t := 0.0   # >0 while doing an action (tool swing)
var action_kind := ""


func _init(model: Node3D) -> void:
	root = model
	_base_scale = model.scale
	_yaw = model.rotation.y
	_yaw_applied = _yaw
	_yaw_prev = _yaw
	_idle_look_t = randf_range(1.0, 4.0)
	ap = _find_type(model, "AnimationPlayer") as AnimationPlayer
	skel = _find_type(model, "Skeleton3D") as Skeleton3D
	if ap and skel and not ap.get_animation_list().is_empty():
		_init_v2()
	else:
		_init_v1()


# ======================================================================= API
func play_action(kind: String, duration := -1.0) -> void:
	var spec: Array = ACTIONS.get(kind, [kind, 1.0, ""])
	if not skinned:
		action_kind = "chop" if kind == "clear" else kind
		action_t = duration if duration > 0.0 else 0.45
		_show_tool(spec[2], action_t + 0.15)
		return
	var clip := _resolve(spec[0])
	if clip == "":
		_show_tool(spec[2], 0.6)
		return
	var a := ap.get_animation(clip)
	var rate: float = spec[1]
	if duration > 0.0 and a.length > 0.0:
		rate = clampf(a.length / duration, 0.5, 2.5)
	# alternate between two names for the same clip so a repeated action
	# still cross-fades from its own pose instead of snapping to frame 0
	_act_alt = not _act_alt
	var nm := ("alt/" + clip) if _act_alt and ap.has_animation("alt/" + clip) else clip
	if nm == _cur:
		nm = clip if nm != clip else "alt/" + clip
	_rate = rate
	_act_rate = rate
	_note_fade(nm, BLEND_ACTION_IN * rate)
	ap.play(nm, BLEND_ACTION_IN * rate)
	_cur = nm
	_cur_kind = "action"
	_act_kind = kind
	_act_left = a.length / rate
	_show_tool(spec[2], _act_left - BLEND_ACTION_OUT * 0.6)
	bump(0.5)


func hold_tool(kind: String) -> void:
	## Keep a tool in hand between actions (e.g. the hotbar selection): an action
	## kind ("harvest", "clear", "plant", "fert") or a tool name ("egrek",
	## "parang", "trowel", "sack"); "" for empty hands.
	var spec: Array = ACTIONS.get(kind, ["", 1.0, kind])
	held_tool = spec[2] if spec[2] in ["egrek", "parang", "trowel", "sack"] else ""


func is_busy() -> bool:
	## True while an action clip plays and the character should stand still
	## (until the clip starts fading out, BLEND_ACTION_OUT before its end).
	return skinned and _act_left > 0.0


func action_kind_playing() -> String:
	return _act_kind if is_busy() else ""


func tick(delta: float) -> void:
	## Call instead of update() while the character is not animated (off screen,
	## hidden): timers keep running, so an action still ends on time and gameplay
	## never waits on a frozen clip. The next update() blends back to locomotion.
	talk_t = maxf(0.0, talk_t - delta)
	action_t = maxf(0.0, action_t - delta)
	if _act_left > 0.0:
		_act_left -= delta
		if _act_left <= BLEND_ACTION_OUT:
			_act_left = 0.0
			_act_kind = ""
			if _cur_kind == "action":
				_cur_kind = ""
	if _tool_kind != "":
		_tool_timer -= delta
		if _tool_timer <= 0.0:
			if _tools.has(_tool_kind):
				(_tools[_tool_kind] as Node3D).visible = false
			_tool_kind = ""
			_tool_s = 0.0
			_pole_fresh = true


func walk_run_speeds() -> Vector2:
	## Ground speed (m/s) the walk and run clips cover at 1x playback, and
	## (debug) where they come from: see _gait_src.
	return Vector2(_speed_of("walk"), _speed_of("run"))


func turn_towards(target_yaw: float, delta: float, max_rate := 10.0) -> void:
	## Smooth, speed-limited turn of the model (call every frame instead of
	## setting model.rotation.y); the turn rate also drives the lean.
	_sync_external_yaw()
	var diff := wrapf(target_yaw - _yaw, -PI, PI)
	var want := clampf(diff * 12.0, -max_rate, max_rate)
	_yaw_vel = lerpf(_yaw_vel, want, clampf(delta * 16.0, 0.0, 1.0))
	var step := _yaw_vel * delta
	if absf(diff) < 0.002:
		step = diff
		_yaw_vel = 0.0
	elif signf(step) == signf(diff) and absf(step) > absf(diff):
		step = diff
	_yaw = wrapf(_yaw + step, -PI, PI)
	_turned = true


func look_at_point(p: Vector3) -> void:
	## Turn the head toward a world position this frame (call every frame).
	_look_pos = p
	_look_on = true


func bump(amount := 1.0) -> void:
	## Kick the squash-and-stretch spring (start/stop, surprise, hops).
	_sq_vel += amount


func attach_to_bone(bone: String, node: Node3D, offset := Vector3.ZERO) -> bool:
	## Parent `node` to a BoneAttachment3D on `bone`, placed at the bone's rest
	## head + `offset` (model axes) and kept upright relative to the model at
	## rest. Returns false when the model has no such bone (caller falls back).
	if not skinned:
		return false
	var bi := skel.find_bone(bone)
	if bi < 0:
		return false
	var ba := _attachment(bone)
	var rest := skel.get_bone_global_rest(bi)
	var head_model := _sk_xf * rest.origin
	var target_skel := _sk_xf.affine_inverse() * Transform3D(Basis.IDENTITY, head_model + offset)
	ba.add_child(node)
	node.transform = rest.affine_inverse() * target_skel
	return true


# ======================================================================= update
func update(delta: float, speed: float, t: float) -> void:
	_sync_external_yaw()
	if not _turned:
		_yaw_vel = lerpf(_yaw_vel, 0.0, clampf(delta * 10.0, 0.0, 1.0))
	_turned = false
	if skinned:
		_update_v2(delta, speed, t)
	else:
		_update_v1(delta, speed, t)
	_update_secondary(delta, speed)
	_update_tool(delta)
	_look_on = false


func _update_secondary(delta: float, speed: float) -> void:
	# lean into turns (centripetal), pitch with acceleration, squash on start/stop
	var yr := wrapf(_yaw - _yaw_prev, -PI, PI) / maxf(delta, 0.001)
	_yaw_prev = _yaw
	if absf(yr) > 30.0:
		yr = 0.0   # teleport / snap, not a turn
	_turn_rate = lerpf(_turn_rate, yr, clampf(delta * 10.0, 0.0, 1.0))
	var lean_target := clampf(-_turn_rate * speed * 0.022, -0.16, 0.16)
	_lean = lerpf(_lean, lean_target, clampf(delta * 8.0, 0.0, 1.0))
	var acc := (speed - _prev_speed) / maxf(delta, 0.001)
	_prev_speed = speed
	_accel = lerpf(_accel, acc, clampf(delta * 12.0, 0.0, 1.0))
	var pitch_target := clampf(_accel * 0.01, -0.09, 0.11)
	_pitch = lerpf(_pitch, pitch_target, clampf(delta * 8.0, 0.0, 1.0))
	var moving := speed > 0.35
	if moving != _was_moving:
		bump(0.75 if moving else 0.6)
		_was_moving = moving
	var f := -170.0 * _sq - 11.0 * _sq_vel
	_sq_vel += f * minf(delta, 0.05)
	_sq = clampf(_sq + _sq_vel * minf(delta, 0.05), -0.1, 0.1)
	root.rotation = Vector3(_pitch, _yaw, _lean)
	_yaw_applied = _yaw
	root.scale = _base_scale * Vector3(1.0 + _sq * 0.5, 1.0 - _sq, 1.0 + _sq * 0.5)


func _sync_external_yaw() -> void:
	# someone else rotated the model directly (old code, cutscene): adopt it
	if absf(wrapf(root.rotation.y - _yaw_applied, -PI, PI)) > 0.0001:
		_yaw = root.rotation.y
		_yaw_applied = _yaw


# ======================================================================= v2
func _init_v2() -> void:
	skinned = true
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	# Cross-fades: Godot's deterministic mode does not normalise the fade
	# weights, which pushes every bone off the path between the two clips by up
	# to ~6-12 degrees and snaps it back when the fade ends (a pop on both ends
	# of every blend, worst on bones far from their rest pose). With normalised
	# weights the fade starts exactly on the old clip, lands exactly on the new
	# one and moves continuously in between (AnimBench checks this). That needs
	# every clip to key the same bones (a bone missing from one clip would hold
	# its other value until the fade ends), which the v2 exports do. Bones are
	# reset to rest before each advance, so an unkeyed bone never keeps a stale
	# pose.
	ap.deterministic = not _same_tracks()
	for n in LOOP_CLIPS:
		if ap.has_animation(n):
			ap.get_animation(n).loop_mode = Animation.LOOP_LINEAR
	# a second library pointing at the same clips (see play_action)
	var alt := AnimationLibrary.new()
	for n in ap.get_animation_list():
		if not "/" in n:
			alt.add_animation(n, ap.get_animation(n))
	if not ap.has_animation_library("alt"):
		ap.add_animation_library("alt", alt)
	_sk_xf = _rel_xform(skel, root)
	_sk_up = (_sk_xf.basis.inverse() * Vector3.UP).normalized()
	_sk_fwd = (_sk_xf.basis.inverse() * Vector3.BACK).normalized()
	_head = skel.find_bone("head")
	_neck = skel.find_bone("neck")
	for bi in [_neck, _head]:
		if bi >= 0:
			_override_bones.append(bi)
	for n in STRIDE_BONES + SWING_BONES:
		var bi := skel.find_bone(n)
		if bi >= 0:
			(_stride_bones if n in STRIDE_BONES else _swing_bones).append(bi)
			_override_bones.append(bi)
	for bi in _override_bones:
		_rest_rot[bi] = skel.get_bone_rest(bi).basis.get_rotation_quaternion()
	_hips = skel.find_bone("hips")
	for n in ["foot_L", "foot_R"]:
		var fi := skel.find_bone(n)
		if fi >= 0:
			_feet.append(fi)
	_measure_gait()
	_hand_idx = skel.find_bone("hand_R")
	if _hand_idx >= 0:
		hand_r = _attachment("hand_R")
		_grip_root = Node3D.new()
		_grip_root.name = "Grip"
		hand_r.add_child(_grip_root)
		_grip_root.transform = _grip_xform(_hand_idx)
	var hl := skel.find_bone("hand_L")
	if hl >= 0:
		_grip_l_root = Node3D.new()
		_grip_l_root.name = "GripL"
		_attachment("hand_L").add_child(_grip_l_root)
		_grip_l_root.transform = _grip_xform(hl)
	_idle_rate = randf_range(0.88, 1.12)
	var idle := _resolve("idle")
	if idle != "":
		ap.play(idle)
		ap.seek(randf() * ap.get_animation(idle).length, true)
		_cur = idle
		_cur_kind = "idle"
		_rate = _idle_rate


func _update_v2(delta: float, speed: float, t: float) -> void:
	var moving := speed > 0.12
	if moving:
		_running = speed > (_run_off if _running else _run_on)
	var want_kind := "idle"
	if moving:
		want_kind = "run" if _running else "walk"
	elif talk_t > 0.0:
		want_kind = "talk"
	elif idle_clip != "idle":
		want_kind = idle_clip
	talk_t = maxf(0.0, talk_t - delta)
	# stride warping: when even the fastest sensible cadence can't keep up with
	# the ground speed, swing the legs (and arms) further; the playback rate is
	# then set from the stride actually shown, so the planted foot never skates
	var gait := "run" if _running else "walk"
	var target_k := 1.0
	if moving:
		var need := speed / (_speed_of(gait) * float(MAX_RATE[gait]))
		if need > 1.0:
			target_k = _k_for_gain(gait, need)
	_stride_k = lerpf(_stride_k, target_k, clampf(delta * 6.0, 0.0, 1.0))
	var want_rate := _idle_rate
	if want_kind == "walk" or want_kind == "run":
		want_rate = clampf(speed / (_speed_of(want_kind) * _gain_at(want_kind, _stride_k)), MIN_RATE, HARD_RATE)
	if _act_left > 0.0:
		_act_left -= delta
		if _act_left <= BLEND_ACTION_OUT:
			_act_left = 0.0
			_act_kind = ""
			_switch(want_kind, want_rate, BLEND_ACTION_OUT)
	elif want_kind != _cur_kind:
		_switch(want_kind, want_rate, BLEND_LOCO)
	if _cur_kind == "walk" or _cur_kind == "run":
		# follow the ground speed closely (it is already smooth: characters accelerate)
		_rate = lerpf(_rate, want_rate, clampf(delta * 25.0, 0.0, 1.0))
	elif _cur_kind != "action":
		_rate = lerpf(_rate, want_rate, clampf(delta * 8.0, 0.0, 1.0))
	# the mixer rewrites only bones that have tracks: start from rest so the
	# procedural layers below (look, stride) never accumulate
	skel.reset_bone_poses()
	if not fade.is_empty():
		fade["w"] = clampf(float(fade["t"]) / maxf(float(fade["len"]), 0.0001), 0.0, 1.0)
		fade["t"] = float(fade["t"]) + delta * _rate
		fade["from_t"] = float(fade["from_t"]) + delta * _rate
	ap.advance(delta * _rate)
	if _stride_k > 1.005:
		var y0 := _lowest_foot()
		var piv: Dictionary = _pivots.get(gait, {})
		_scale_swing(_stride_bones, _stride_k, piv)
		_scale_swing(_swing_bones, 1.0 + (_stride_k - 1.0) * 0.6, piv)
		# longer swings lift the planted foot (the leg reaches further out):
		# sink the hips by as much so it stays on the ground
		var lift := _lowest_foot() - y0
		if lift > 0.0 and _hips >= 0:
			var d := _sk_xf.basis.inverse() * Vector3(0.0, -lift, 0.0)
			skel.set_bone_pose_position(_hips, skel.get_bone_pose_position(_hips) + d)
	_apply_look(delta, moving)


func _speed_of(kind: String) -> float:
	return float(_nat.get(kind, 1.0)) * absf(_base_scale.z)


func _lowest_foot() -> float:
	var y := INF
	for f in _feet:
		y = minf(y, (_sk_xf * skel.get_bone_global_pose(f).origin).y)
	return 0.0 if y == INF else y


func _scale_swing(bones: Array[int], k: float, pivots: Dictionary) -> void:
	## Scale each bone's rotation away from its cycle-mean rotation in the clip
	## (the centre of the swing) by k: a longer swing, same posture.
	for bi in bones:
		var r: Quaternion = pivots.get(bi, _rest_rot[bi])
		var d := (r.inverse() * skel.get_bone_pose_rotation(bi)).normalized()
		if d.w < 0.0:
			d = -d   # the short way round
		var ang := d.get_angle()
		if ang < 0.0001 or ang > PI * 0.9:
			continue
		var axis := d.get_axis().normalized()
		skel.set_bone_pose_rotation(bi, (r * Quaternion(axis, minf(ang * k, PI * 0.8))).normalized())


func _gain_at(kind: String, k: float) -> float:
	## How much longer the stride is when the leg swing is scaled by k.
	var g: PackedFloat32Array = _gain.get(kind, PackedFloat32Array())
	if k <= 1.0 or g.size() < 2:
		return maxf(k, 1.0) if g.size() < 2 else 1.0
	var x := (k - float(STRIDE_KS[0])) / (float(STRIDE_KS[1]) - float(STRIDE_KS[0]))
	var i := clampi(int(floor(x)), 0, g.size() - 2)
	return lerpf(g[i], g[i + 1], clampf(x - i, 0.0, 1.0))


func _k_for_gain(kind: String, need: float) -> float:
	## Smallest leg swing scale (<= STRIDE_MAX) whose stride gain reaches `need`.
	var g: PackedFloat32Array = _gain.get(kind, PackedFloat32Array())
	if g.size() < 2:
		return clampf(need, 1.0, STRIDE_MAX)
	for i in g.size() - 1:
		if need <= g[i + 1]:
			var span := g[i + 1] - g[i]
			var u := (need - g[i]) / span if span > 0.0001 else 1.0
			return minf(lerpf(float(STRIDE_KS[i]), float(STRIDE_KS[i + 1]), clampf(u, 0.0, 1.0)), STRIDE_MAX)
	return STRIDE_MAX


func _switch(kind: String, rate: float, blend: float) -> void:
	var nm := _resolve(kind)
	if nm == "":
		_cur_kind = kind
		return
	var phase := -1.0
	var from_loco := _cur_kind == "walk" or _cur_kind == "run"
	if from_loco and (kind == "walk" or kind == "run") and ap.current_animation_length > 0.0:
		phase = fposmod(ap.current_animation_position / ap.current_animation_length, 1.0)
	_rate = rate
	if nm == _cur and ap.is_playing():
		_cur_kind = kind
		return
	# blend times are in clip time (advance() scales them by the rate): size them
	# for the rate, but not below 0.8x - a walk starting from rest speeds up
	# during the fade, which would otherwise make it too short
	_note_fade(nm, blend * maxf(rate, 0.8))
	ap.play(nm, blend * maxf(rate, 0.8))
	var len := ap.get_animation(nm).length
	if phase >= 0.0:
		ap.seek(phase * len, false)
	elif kind == "talk" or kind == "idle" or kind == "sad":
		# start loops somewhere random so a crowd never moves in sync
		ap.seek(randf() * len, false)
	_cur = nm
	_cur_kind = kind


func _note_fade(to: String, blend: float) -> void:
	var nested: bool = not fade.is_empty() and float(fade["t"]) < float(fade["len"])
	fade = {"from": _cur, "from_t": ap.current_animation_position if ap.is_playing() else 0.0,
		"to": to, "t": 0.0, "len": blend, "w": 0.0, "nested": nested}


func _same_tracks() -> bool:
	## True when every clip keys the same bone channels.
	var ref := {}
	var first := true
	for n in ap.get_animation_list():
		if "/" in n:
			continue
		var a := ap.get_animation(n)
		var s := {}
		for t in a.get_track_count():
			s[str(a.track_get_path(t)) + "|" + str(a.track_get_type(t))] = true
		if first:
			ref = s
			first = false
		elif s.size() != ref.size() or not s.keys().all(func(k): return ref.has(k)):
			return false
	return true


func _resolve(clip: String) -> String:
	var c := clip
	for i in 4:
		if ap.has_animation(c):
			return c
		c = CLIP_FALLBACK.get(c, "")
		if c == "":
			break
	if clip == "idle" or clip == "walk":
		var names := ap.get_animation_list()
		for n in names:
			if not "/" in n:
				return n
	return ""


func _measure_gait() -> void:
	## Ground speed each locomotion clip covers at 1x (playback rate = velocity /
	## this, so feet don't skate), how much a scaled leg swing lengthens the
	## stride, and the grip offset. Cached per model file.
	var key := root.scene_file_path
	var g: Dictionary
	if key != "" and _gait_cache.has(key):
		g = _gait_cache[key]
	else:
		g = _build_gait()
		if key != "":
			_gait_cache[key] = g
	_nat = (g["nat"] as Dictionary).duplicate()
	_gain = g["gain"]
	_pivots = g["pivots"]
	_gait_src = g["src"]
	_grip_offset = g["grip"]
	_run_on = _speed_of("walk") * WALK_TO_RUN
	_run_off = _run_on * RUN_TO_WALK


func _gait_extras() -> Dictionary:
	## The numbers blender/characters.py exports as glTF extras on the armature
	## node (Godot: "extras" metadata of the Skeleton3D's parent).
	var n: Node = skel
	while n != null:
		if n.has_meta("extras"):
			var ex = n.get_meta("extras")
			if ex is Dictionary and (ex as Dictionary).has("walk_speed"):
				return ex
		if n == root:
			break
		n = n.get_parent()
	return {}


func _build_gait() -> Dictionary:
	var nat := {"walk": 1.1, "run": 2.6}
	var gain := {}
	var pivots := {}
	var src := "default"
	var ex := _gait_extras()
	var foot := skel.find_bone("foot_L")
	if foot < 0:
		foot = skel.find_bone("shin_L")
	for clip: String in ["walk", "run"]:
		var nm := _resolve(clip)
		if nm == "" or nm != clip and clip == "run":
			continue
		var a := ap.get_animation(nm)
		if a.length <= 0.0 or foot < 0:
			continue
		ap.play(nm)
		# centre of each limb's swing: the mean rotation over the cycle
		var acc := {}
		for i in 20:
			skel.reset_bone_poses()
			ap.seek(a.length * i / 20.0, true)
			for bi in _stride_bones + _swing_bones:
				var q := skel.get_bone_pose_rotation(bi)
				var v := Vector4(q.x, q.y, q.z, q.w)
				if acc.has(bi) and (acc[bi] as Vector4).dot(v) < 0.0:
					v = -v
				acc[bi] = (acc[bi] as Vector4) + v if acc.has(bi) else v
		var piv := {}
		for bi in acc:
			var v: Vector4 = (acc[bi] as Vector4).normalized()
			piv[bi] = Quaternion(v.x, v.y, v.z, v.w)
		pivots[clip] = piv
		var spans := PackedFloat32Array()
		for k in STRIDE_KS:
			var zmin := INF
			var zmax := -INF
			for i in 20:
				skel.reset_bone_poses()
				ap.seek(a.length * i / 20.0, true)
				if k > 1.0:
					_scale_swing(_stride_bones, k, piv)
				var p := _sk_xf * skel.get_bone_global_pose(foot).origin
				zmin = minf(zmin, p.z)
				zmax = maxf(zmax, p.z)
			spans.append(zmax - zmin)
		var g := PackedFloat32Array()
		for s in spans:
			g.append(s / spans[0] if spans[0] > 0.001 else 1.0)
		gain[clip] = g
		var key: String = clip + "_speed"
		if ex.has(key) and float(ex[key]) > 0.05:
			nat[clip] = float(ex[key])
			src = "extras"
		elif spans[0] > 0.02:
			# the ankle covers ~stance share of a cycle's ground travel
			var st := float(ex.get(clip + "_stance", STANCE[clip]))
			nat[clip] = clampf(spans[0] / (a.length * st), 0.3, 8.0)
			src = "measured"
	ap.stop()
	skel.reset_bone_poses()
	if _resolve("run") != "run":
		nat["run"] = maxf(nat["walk"] * 2.0, 2.0)
	var grip := float(ex.get("grip_offset", -1.0))
	return {"nat": nat, "gain": gain, "pivots": pivots, "src": src, "grip": grip}


func _apply_look(delta: float, moving: bool) -> void:
	var want_yaw := 0.0
	var want_pitch := -0.32 if idle_clip == "sad" and moving else 0.0
	if _look_on and _head >= 0:
		var hp := skel.global_transform * skel.get_bone_global_pose(_head).origin
		var d := root.global_transform.basis.inverse() * (_look_pos - hp)
		var yaw := atan2(d.x, d.z)
		if absf(yaw) < 2.3:
			want_yaw = clampf(yaw, -1.05, 1.05)
			want_pitch = clampf(atan2(d.y, Vector2(d.x, d.z).length()), -0.45, 0.35)
	elif not moving and _cur_kind != "action":
		_idle_look_t -= delta
		if _idle_look_t <= 0.0:
			_idle_look = randf_range(-0.7, 0.7) if randf() < 0.65 else 0.0
			_idle_look_t = randf_range(1.2, 4.0)
		want_yaw = _idle_look
	var k := clampf(delta * 5.0, 0.0, 1.0)
	_look_yaw = lerpf(_look_yaw, want_yaw, k)
	_look_pitch = lerpf(_look_pitch, want_pitch, k)
	if absf(_look_yaw) < 0.001 and absf(_look_pitch) < 0.001:
		return
	var right := _sk_fwd.cross(_sk_up).normalized()
	var shares := [[_neck, 0.35], [_head, 0.65]] if _neck >= 0 else [[_head, 1.0]]
	for s in shares:
		var bi: int = s[0]
		if bi < 0:
			continue
		var w: float = s[1]
		var par := skel.get_bone_parent(bi)
		var pb := skel.get_bone_global_pose(par).basis.orthonormalized() if par >= 0 else Basis.IDENTITY
		var inv := pb.inverse()
		var q := Quaternion((inv * _sk_up).normalized(), _look_yaw * w) * Quaternion((inv * right).normalized(), _look_pitch * w)
		skel.set_bone_pose_rotation(bi, q * skel.get_bone_pose_rotation(bi))


func _attachment(bone: String) -> BoneAttachment3D:
	var nm := "Attach_" + bone
	var ex := skel.get_node_or_null(NodePath(nm))
	if ex:
		return ex as BoneAttachment3D
	var ba := BoneAttachment3D.new()
	ba.name = nm
	skel.add_child(ba)
	ba.bone_name = bone
	return ba


func _grip_xform(bi: int) -> Transform3D:
	## Where a fist holds a tool, in bone space: tool +Y runs along the thumb
	## side of the fist (model-forward at rest for a hanging or T-posed arm, i.e.
	## the bone's local +Z in the v2 rigs), tool +Z points where the fingers
	## point (the edge of a blade), origin in the fist.
	var rest := skel.get_bone_global_rest(bi)
	var by := rest.basis.y.normalized()
	var g := _sk_fwd - by * _sk_fwd.dot(by)
	if g.length() < 0.2:
		g = rest.basis.z
	g = g.normalized()
	var z := (by - g * by.dot(g)).normalized()
	var x := g.cross(z).normalized()
	var local := rest.basis.orthonormalized().inverse() * Basis(x, g, z)
	# the fist sits ~37% of a forearm past the wrist (0.036 m on the default
	# villager, same as the proxy tools in blender/characters.py)
	var sc: float = _sk_xf.basis.get_scale().x
	var grip := 0.036 / maxf(sc, 0.0001)
	var par := skel.get_bone_parent(bi)
	if _grip_offset > 0.0:
		grip = _grip_offset / maxf(sc, 0.0001)   # exported by blender/characters.py
	elif par >= 0:
		grip = rest.origin.distance_to(skel.get_bone_global_rest(par).origin) * 0.37
	# tools are modelled in metres: undo any armature scale
	return Transform3D(local.scaled(Vector3.ONE / maxf(sc, 0.0001)), Vector3(0, grip, 0))


# ======================================================================= tools
func _show_tool(kind: String, seconds: float) -> void:
	_tool_kind = kind
	_tool_timer = maxf(seconds, 0.2)
	for k in _tools:
		if k != kind:
			(_tools[k] as Node3D).visible = false
	if kind == "":
		return
	if not _tools.has(kind):
		var parent: Node3D = null
		if skinned:
			parent = _grip_l_root if kind == "sack" else _grip_root
		elif kind != "sack":
			parent = hand_r if hand_r else root
		if parent == null:
			# nowhere to hold it (a v1 model has no left fist): no tool, and no
			# stale kind either, so a held tool comes back after the action
			_tool_kind = ""
			return
		var mi := MeshInstance3D.new()
		mi.name = "Tool_" + kind
		mi.mesh = tool_mesh(kind)
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		mi.visible = false
		parent.add_child(mi)
		_tools[kind] = mi
	if not (_tools[kind] as Node3D).visible:
		_tool_s = 0.0
		_pole_fresh = true


func _update_tool(delta: float) -> void:
	if held_tool != "" and (_tool_kind == "" or _tool_kind == held_tool) and _act_left <= 0.0 and action_t <= 0.0:
		if _tool_kind == "":
			_show_tool(held_tool, 0.3)
		_tool_timer = 0.3
	if _tool_kind == "" or not _tools.has(_tool_kind):
		return
	_tool_timer -= delta
	var tool: MeshInstance3D = _tools[_tool_kind]
	var on := _tool_timer > 0.0
	_tool_s = move_toward(_tool_s, 1.0 if on else 0.0, delta / 0.12)
	var s := ease(_tool_s, 0.4) if _tool_s > 0.0 else 0.0
	tool.visible = _tool_s > 0.01
	if not tool.visible:
		_pole_fresh = true
		if not on:
			_tool_kind = ""
		return
	var b := Basis.IDENTITY
	var origin := Vector3.ZERO
	if not skinned:
		b = Basis(Vector3.RIGHT, PI * 0.5) if tool.get_parent() == hand_r else Basis.IDENTITY
	elif _tool_kind == "egrek":
		b = _egrek_basis(delta)
		origin = b.y * _pole_slide
	tool.transform = Transform3D(b.scaled(Vector3.ONE * maxf(s, 0.001)), origin)


func pole_working() -> bool:
	## True while the harvest clip steers the pole. Otherwise a pole kept in hand
	## (hold_tool) is carried; one shown only for the harvest keeps following the
	## hands while it fades out.
	if _act_left > 0.0 and ACTIONS.get(_act_kind, ["", 1.0, ""])[2] == "egrek":
		return true
	return held_tool != "egrek"


func _egrek_basis(delta: float) -> Basis:
	## While harvesting the pole runs along the grip axis (hand_R local +Z in the
	## v2 rigs, whose harvest clip steers both hands along the pole); where a
	## rig's hand points it down or backwards it leans toward the crown in front
	## instead, blended over a wide band. Carried outside an action it rests on
	## the right shoulder. The direction is eased over time (model space, so the
	## pole turns rigidly with the body) and never jumps between frames. The
	## sickle hook always faces back toward the harvester.
	var grip_w := skel.global_transform * skel.get_bone_global_pose(_hand_idx) * _grip_root.transform
	var mb := root.global_transform.basis.orthonormalized()
	var mb_inv := mb.inverse()
	var target := POLE_CARRY_DIR.normalized()
	var slide := POLE_CARRY_SLIDE
	if pole_working():
		var fwd := mb * Vector3.BACK
		fwd.y = 0.0
		fwd = fwd.normalized() if fwd.length() > 0.01 else Vector3.BACK
		var hand_dir := grip_w.basis.y.normalized()
		var aim := (root.global_position + fwd * 1.0 + Vector3.UP * 3.0 - grip_w.origin).normalized()
		var q := smoothstep(-0.45, 0.1, hand_dir.y) * smoothstep(-0.6, 0.0, hand_dir.dot(fwd))
		target = (mb_inv * aim.slerp(hand_dir, q)).normalized()
		slide = 0.0
	if _pole_fresh:
		_pole_dir = target
		_pole_slide = slide
		_pole_fresh = false
	else:
		var ang := _pole_dir.angle_to(target)
		if ang > 0.0001:
			var step := minf(ang * (1.0 - exp(-POLE_FOLLOW * delta)), POLE_MAX_SPEED * delta)
			_pole_dir = _pole_dir.slerp(target, step / ang).normalized()
		_pole_slide = move_toward(_pole_slide, slide, delta * 1.5)
	var y := (mb * _pole_dir).normalized()
	var back := mb * Vector3.FORWARD
	var z := back - y * back.dot(y)
	z = z.normalized() if z.length() > 0.01 else (mb * Vector3.DOWN)
	var x := y.cross(z).normalized()
	return grip_w.basis.orthonormalized().inverse() * Basis(x, y, z)


static func _tool_mat(nm: String, col: Color) -> Material:
	if not _tool_mats.has(nm):
		var m := StandardMaterial3D.new()
		m.resource_name = nm
		m.albedo_color = col
		_tool_mats[nm] = ModelLib.convert_material(m, false)
	return _tool_mats[nm]


static func tool_mesh(kind: String) -> ArrayMesh:
	## Small hand tools built in code. Local space: the fist grips the origin,
	## the handle runs along +Y, blade edges / hooks face +Z.
	if _tool_meshes.has(kind):
		return _tool_meshes[kind]
	var mb := _MeshBuilder.new()
	match kind:
		"egrek":
			# long bamboo pole with node rings and a curved sickle on top
			var bamboo := mb.part("M_Tool_Bamboo", Color("c9a95e"))
			var node := mb.part("M_Tool_BambooNode", Color("97793a"))
			var steel := mb.part("M_Tool_Steel", Color("cfd6d8"))
			var dark := mb.part("M_Tool_SteelDark", Color("6f7474"))
			mb.cyl(bamboo, Vector3(0, -0.5, 0), Vector3(0, 2.2, 0), 0.019, 7)
			for i in 6:
				var y := -0.3 + i * 0.44
				mb.cyl(node, Vector3(0, y, 0), Vector3(0, y + 0.025, 0), 0.023, 7)
			mb.cyl(dark, Vector3(0, 2.18, 0), Vector3(0, 2.3, 0), 0.022, 7)
			# sickle: rises from the ferrule, arcs over and hooks down toward +Z
			var c := Vector3(0, 2.3, 0.1)
			var inner: Array[Vector3] = []
			var outer: Array[Vector3] = []
			var n := 12
			for i in n + 1:
				var u := float(i) / n
				var ang := lerpf(PI, -0.35, u)
				var w := lerpf(0.035, 0.004, pow(u, 1.3))
				var r := 0.1
				var dirv := Vector3(0, sin(ang), cos(ang))
				inner.append(c + dirv * (r - w * 0.5))
				outer.append(c + dirv * (r + w * 0.5))
			mb.blade(steel, inner, outer, 0.004)
		"parang":
			# machete: dark wooden grip, short guard, wide slightly curved blade
			var wood := mb.part("M_Tool_WoodDark", Color("5b3b24"))
			var steel := mb.part("M_Tool_Steel", Color("d3dadc"))
			var dark := mb.part("M_Tool_SteelDark", Color("6f7474"))
			mb.cyl(wood, Vector3(0, -0.07, 0), Vector3(0, 0.08, 0), 0.02, 7)
			mb.cyl(dark, Vector3(0, 0.08, 0), Vector3(0, 0.1, 0), 0.026, 7)
			var back: Array[Vector3] = []
			var edge: Array[Vector3] = []
			var n := 10
			for i in n + 1:
				var u := float(i) / n
				var y := 0.1 + u * 0.36
				var zb := -0.012 - 0.015 * u * u
				var ze := lerpf(0.022, 0.05, smoothstep(0.0, 0.75, u))
				if u > 0.8:
					ze = lerpf(0.05, zb + 0.004, smoothstep(0.8, 1.0, u))
				back.append(Vector3(0, y, zb))
				edge.append(Vector3(0, y, ze))
			mb.blade(steel, back, edge, 0.005)
		"trowel":
			# cetok: wooden handle, thin shank, pointed leaf-shaped blade
			var wood := mb.part("M_Tool_Wood", Color("9a6437"))
			var steel := mb.part("M_Tool_Steel", Color("c7cfd2"))
			mb.cyl(wood, Vector3(0, -0.06, 0), Vector3(0, 0.07, 0), 0.017, 7)
			mb.cyl(steel, Vector3(0, 0.07, 0), Vector3(0, 0.12, 0.012), 0.006, 5)
			var l: Array[Vector3] = []
			var r: Array[Vector3] = []
			var n := 8
			for i in n + 1:
				var u := float(i) / n
				var y := 0.12 + u * 0.15
				var hw := 0.042 * pow(sin(PI * lerpf(0.12, 1.0, u)), 0.7)
				var z := 0.012 + 0.012 * sin(PI * u)
				l.append(Vector3(-hw, y, z))
				r.append(Vector3(hw, y, z))
			mb.sheet(steel, l, r, 0.004)
		"basket":
			# rattan back basket (bakul) for carrying the harvested bunches
			var rattan := mb.part("M_Tool_Rattan", Color("b88c52"))
			var band := mb.part("M_Tool_RattanDark", Color("7d5a32"))
			mb.tube(rattan, -0.2, 0.06, 0.12, 0.155, 12)
			mb.cyl(band, Vector3(0, -0.13, 0), Vector3(0, -0.11, 0), 0.134, 12)
			mb.cyl(band, Vector3(0, -0.03, 0), Vector3(0, -0.01, 0), 0.146, 12)
			mb.cyl(band, Vector3(0, 0.045, 0), Vector3(0, 0.07, 0), 0.162, 12)
			# shoulder straps running forward over the shoulders
			for sx in [-1.0, 1.0]:
				mb.cyl(band, Vector3(0.08 * sx, 0.07, 0.1), Vector3(0.1 * sx, 0.1, 0.24), 0.012, 4)
		"sack":
			# small fertiliser sack held in the left hand
			var cloth := mb.part("M_Tool_Sack", Color("e9dcbc"))
			var tie := mb.part("M_Tool_Rope", Color("8a6a3a"))
			mb.blob(cloth, Vector3(0, 0.0, 0.07), Vector3(0.06, 0.075, 0.055), 8, 6)
			mb.cyl(tie, Vector3(0, 0.0, 0.0), Vector3(0, 0.0, 0.03), 0.018, 6)
	var mesh := mb.commit()
	_tool_meshes[kind] = mesh
	return mesh


class _MeshBuilder:
	var tools := {}
	var mats := {}

	func part(nm: String, col: Color) -> SurfaceTool:
		if not tools.has(nm):
			var st := SurfaceTool.new()
			st.begin(Mesh.PRIMITIVE_TRIANGLES)
			tools[nm] = st
			mats[nm] = CharAnim._tool_mat(nm, col)
		return tools[nm]

	func tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, na: Vector3, nb: Vector3, nc: Vector3) -> void:
		# Godot front faces wind clockwise: flip when the winding disagrees with the normals
		var fn := (na + nb + nc)
		if (b - a).cross(c - a).dot(fn) > 0.0:
			var tv := b
			b = c
			c = tv
			var tn := nb
			nb = nc
			nc = tn
		st.set_normal(na)
		st.add_vertex(a)
		st.set_normal(nb)
		st.add_vertex(b)
		st.set_normal(nc)
		st.add_vertex(c)

	func quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, n: Vector3) -> void:
		tri(st, a, b, c, n, n, n)
		tri(st, a, c, d, n, n, n)

	func cyl(st: SurfaceTool, a: Vector3, b: Vector3, r: float, sides: int) -> void:
		var ax := (b - a).normalized()
		var u := ax.cross(Vector3.RIGHT if absf(ax.x) < 0.9 else Vector3.UP).normalized()
		var v := ax.cross(u).normalized()
		for i in sides:
			var a0 := TAU * i / sides
			var a1 := TAU * (i + 1) / sides
			var n0 := u * cos(a0) + v * sin(a0)
			var n1 := u * cos(a1) + v * sin(a1)
			tri(st, a + n0 * r, b + n0 * r, b + n1 * r, n0, n0, n1)
			tri(st, a + n0 * r, b + n1 * r, a + n1 * r, n0, n1, n1)
			tri(st, b, b + n0 * r, b + n1 * r, ax, ax, ax)
			tri(st, a, a + n1 * r, a + n0 * r, -ax, -ax, -ax)

	func tube(st: SurfaceTool, y0: float, y1: float, r0: float, r1: float, sides: int) -> void:
		## open-topped tapered shell (outer + inner wall) with a bottom
		var slope := (r1 - r0) / (y1 - y0)
		for i in sides:
			var a0 := TAU * i / sides
			var a1 := TAU * (i + 1) / sides
			var d0 := Vector3(cos(a0), 0, sin(a0))
			var d1 := Vector3(cos(a1), 0, sin(a1))
			var n0 := (d0 - Vector3.UP * slope).normalized()
			var n1 := (d1 - Vector3.UP * slope).normalized()
			var b0 := d0 * r0 + Vector3.UP * y0
			var b1 := d1 * r0 + Vector3.UP * y0
			var t0 := d0 * r1 + Vector3.UP * y1
			var t1 := d1 * r1 + Vector3.UP * y1
			tri(st, b0, t0, t1, n0, n0, n1)
			tri(st, b0, t1, b1, n0, n1, n1)
			var k := 0.93
			tri(st, b0 * Vector3(k, 1, k), t1 * Vector3(k, 1, k), t0 * Vector3(k, 1, k), -n0, -n1, -n0)
			tri(st, b0 * Vector3(k, 1, k), b1 * Vector3(k, 1, k), t1 * Vector3(k, 1, k), -n0, -n1, -n1)
			tri(st, Vector3(0, y0, 0), b1, b0, Vector3.DOWN, Vector3.DOWN, Vector3.DOWN)
			tri(st, Vector3(0, y0 + 0.01, 0), b0 * Vector3(k, 1, k) + Vector3.UP * 0.01,
				b1 * Vector3(k, 1, k) + Vector3.UP * 0.01, Vector3.UP, Vector3.UP, Vector3.UP)

	func blade(st: SurfaceTool, back: Array[Vector3], edge: Array[Vector3], thick: float) -> void:
		## flat blade in the YZ plane (faces +-X) with a thick back rim
		var off := Vector3(thick * 0.5, 0, 0)
		for i in back.size() - 1:
			quad(st, back[i] + off, back[i + 1] + off, edge[i + 1] + off * 0.3, edge[i] + off * 0.3, Vector3.RIGHT)
			quad(st, back[i] - off, edge[i] - off * 0.3, edge[i + 1] - off * 0.3, back[i + 1] - off, Vector3.LEFT)
			var rim := (back[i] - edge[i]).normalized()
			quad(st, back[i] + off, back[i] - off, back[i + 1] - off, back[i + 1] + off, rim)

	func sheet(st: SurfaceTool, left: Array[Vector3], right: Array[Vector3], thick: float) -> void:
		## flat sheet facing +-Z
		var off := Vector3(0, 0, thick * 0.5)
		for i in left.size() - 1:
			quad(st, left[i] + off, right[i] + off, right[i + 1] + off, left[i + 1] + off, Vector3.BACK)
			quad(st, left[i] - off, left[i + 1] - off, right[i + 1] - off, right[i] - off, Vector3.FORWARD)

	func blob(st: SurfaceTool, c: Vector3, radii: Vector3, seg: int, rings: int) -> void:
		for j in rings:
			var t0 := PI * j / rings
			var t1 := PI * (j + 1) / rings
			for i in seg:
				var p0 := TAU * i / seg
				var p1 := TAU * (i + 1) / seg
				var d := [
					Vector3(sin(t0) * cos(p0), cos(t0), sin(t0) * sin(p0)),
					Vector3(sin(t1) * cos(p0), cos(t1), sin(t1) * sin(p0)),
					Vector3(sin(t1) * cos(p1), cos(t1), sin(t1) * sin(p1)),
					Vector3(sin(t0) * cos(p1), cos(t0), sin(t0) * sin(p1)),
				]
				var p: Array[Vector3] = []
				var n: Array[Vector3] = []
				for q in d:
					p.append(c + Vector3(q.x * radii.x, q.y * radii.y, q.z * radii.z))
					n.append(Vector3(q.x / radii.x, q.y / radii.y, q.z / radii.z).normalized())
				if j > 0:
					tri(st, p[0], p[1], p[2], n[0], n[1], n[2])
				if j < rings - 1:
					tri(st, p[0], p[2], p[3], n[0], n[2], n[3])

	func commit() -> ArrayMesh:
		var mesh := ArrayMesh.new()
		for nm in tools:
			var st: SurfaceTool = tools[nm]
			st.set_material(mats[nm])
			st.commit(mesh)
		return mesh


# ======================================================================= helpers
static func _find_type(n: Node, cls: String) -> Node:
	if n.is_class(cls):
		return n
	for c in n.get_children():
		var r := _find_type(c, cls)
		if r:
			return r
	return null


static func _rel_xform(node: Node, top: Node) -> Transform3D:
	var t := Transform3D.IDENTITY
	var n := node
	while n != null and n != top:
		if n is Node3D:
			t = (n as Node3D).transform * t
		n = n.get_parent()
	return t


# ======================================================================= v1
func _init_v1() -> void:
	hips = root.find_child("Hips", true, false)
	arm_l = root.find_child("ArmL", true, false)
	arm_r = root.find_child("ArmR", true, false)
	leg_l = root.find_child("LegL", true, false)
	leg_r = root.find_child("LegR", true, false)
	head = root.find_child("Head", true, false)
	hand_r = root.find_child("HandR", true, false)
	if hips:
		hips_y = hips.position.y


func _update_v1(delta: float, speed: float, t: float) -> void:
	## The original procedural animation for rigid v1 models.
	var moving := speed > 0.15
	if moving:
		phase += delta * (5.0 + speed * 1.6)
	else:
		phase = lerpf(phase, round(phase / PI) * PI, delta * 8.0)
	var swing := sin(phase) * (0.75 if moving else 0.0)
	var bob := absf(sin(phase)) * 0.05 if moving else sin(t * 2.0 + idle_seed) * 0.008
	if hips:
		hips.position.y = hips_y + bob
		hips.rotation.z = sin(phase) * 0.04 if moving else 0.0
	if leg_l:
		leg_l.rotation.x = swing
	if leg_r:
		leg_r.rotation.x = -swing
	var arm_swing := swing * 0.9
	var arm_l_x := -arm_swing
	var arm_r_x := arm_swing
	var arm_r_z := 0.0
	if action_t > 0.0:
		action_t -= delta
		var k := clampf(action_t / 0.45, 0.0, 1.0)
		match action_kind:
			"chop", "harvest":
				arm_r_x = lerpf(0.4, -2.6, k)
				arm_l_x = lerpf(0.2, -1.2, k) * 0.5
			"plant", "fert":
				arm_r_x = -1.2 * sin(k * PI)
				arm_l_x = -1.2 * sin(k * PI)
				if hips:
					hips.rotation.x = 0.35 * sin(k * PI)
			"cheer", "wave":
				arm_r_z = 2.6 * sin(k * PI)
				arm_r_x = -0.3
				arm_l_x = -0.3
	elif hips:
		hips.rotation.x = lerpf(hips.rotation.x, 0.0, delta * 10.0)
	if arm_l:
		arm_l.rotation.x = arm_l_x
		arm_l.rotation.z = lerpf(arm_l.rotation.z, 0.0, delta * 10.0)
	if arm_r:
		arm_r.rotation.x = arm_r_x
		arm_r.rotation.z = -arm_r_z
	if head:
		if talk_t > 0.0:
			talk_t -= delta
			head.rotation.x = sin(t * 9.0) * 0.08
		else:
			head.rotation.x = lerpf(head.rotation.x, 0.0, delta * 6.0)
		var want := 0.0
		if _look_on:
			var d := root.global_transform.basis.inverse() * (_look_pos - head.global_position)
			if absf(atan2(d.x, d.z)) < 2.3:
				want = clampf(atan2(d.x, d.z), -0.9, 0.9)
		_look_yaw = lerpf(_look_yaw, want, clampf(delta * 5.0, 0.0, 1.0))
		head.rotation.y = sin(t * 0.7 + idle_seed) * (0.05 if moving else 0.18) + _look_yaw
