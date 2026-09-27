class_name Npc
extends Node3D
## A villager (or any other character) that idles and wanders around an anchor
## point, goes home at night and turns to face the player while talking.
## Small touches keep the village alive: villagers glance at and wave to the
## player, neighbours stop for a chat, hired hands work the palms, and people
## who lost their land shuffle around slumped.

const WAVE_RANGE := 4.5
const LOOK_RANGE := 6.0
const ANIM_RANGE := 32.0   # beyond this from the player (off screen) the model is not animated
const NO_WAVE := ["char_preman", "char_petugas"]
const VISIT_RANGE := 20.0  # m: farthest neighbour a villager strolls over to
const VISIT_LEASH := 10.0  # m: how far past its wander radius a villager goes visiting

var vid := ""            # villager id in GS.villagers, or "" for extras
var display_name := ""
var model_name := ""
var world: Node
var model: Node3D
var anim: CharAnim
var anchor := Vector3.ZERO
var radius := 6.0
var home := Vector3.ZERO
var sleeps_at_night := true
var speed := 1.25         # stroll; they hurry home at night (x1.6)
var talking := false
var talk_target: Node3D
var _target := Vector3.ZERO
var _wait := 0.0
var _t := 0.0
var _moving := false
var _cur_speed := 0.0
var _emote: Label3D
var _emote_t := 0.0
var _name_label: Label3D
var _greeted := false
var _wave_cd := 0.0
var _face_player_t := 0.0
var _work_left := 0
var _work_cd := 0.0
var _chat_with: Npc
var _chat_t := 0.0
var _chat_turn := 0.0
var _social_cd := 0.0
var _visit: Npc          # neighbour this villager is walking over to chat with
var _expect: Npc         # neighbour walking over to chat with this villager
var _expect_t := 0.0     # how long to keep waiting for them


func setup(p_world: Node, p_model: String, p_name: String, p_anchor: Vector3, p_radius: float) -> void:
	world = p_world
	model_name = p_model
	display_name = p_name
	anchor = p_anchor
	home = p_anchor
	radius = p_radius


func _ready() -> void:
	model = ModelLib.instance(model_name, false)
	add_child(model)
	anim = CharAnim.new(model)
	position = anchor
	_target = anchor
	_wait = randf_range(0.5, 3.0)
	_wave_cd = randf_range(0.0, 6.0)
	_social_cd = randf_range(3.0, 10.0)
	_emote = Label3D.new()
	_emote.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_emote.font = ModelLib.label_font()
	_emote.font_size = 72
	_emote.outline_size = 14
	_emote.modulate = Color("5a3b22")
	_emote.outline_modulate = Color("fdf3dc")
	_emote.position.y = 1.75
	_emote.no_depth_test = true
	_emote.visible = false
	add_child(_emote)
	_name_label = Label3D.new()
	_name_label.text = display_name
	_name_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_name_label.font = ModelLib.label_font()
	_name_label.font_size = 36
	_name_label.outline_size = 9
	_name_label.pixel_size = 0.01
	_name_label.modulate = Color("5a3b22")
	_name_label.outline_modulate = Color("fdf3dc")
	_name_label.position.y = 1.45
	_name_label.no_depth_test = true
	_name_label.visible = false
	add_child(_name_label)


func set_anchor(p: Vector3, r: float, teleport := false) -> void:
	anchor = p
	radius = r
	_target = p
	if teleport:
		position = p
		_cur_speed = 0.0


func emote(text: String, seconds := 2.5) -> void:
	_emote.text = text
	_emote.visible = true
	_emote_t = seconds
	if anim:
		anim.bump(1.2)


func is_awake() -> bool:
	if not sleeps_at_night:
		return true
	return GS.hour >= 6.5 and GS.hour < 19.5


func is_sad() -> bool:
	return vid != "" and GS.villagers.has(vid) and GS.villagers[vid].get("status", "") == "landless"


func is_worker() -> bool:
	if model_name == "char_buruh":
		return true
	return vid != "" and GS.villagers.has(vid) and bool(GS.villagers[vid].get("worker", false))


func is_idle() -> bool:
	## Standing around with nothing to do (other villagers may start a chat).
	return not talking and not _moving and _chat_with == null and not anim.is_busy() and visible and is_awake()


func _process(delta: float) -> void:
	_t += delta
	if _emote_t > 0.0:
		_emote_t -= delta
		_emote.position.y = 1.75 + sin(_t * 4.0) * 0.05
		if _emote_t <= 0.0:
			_emote.visible = false
	if talking and world and world.ui and world.ui.modal == null:
		talking = false
	var pl: Node3D = world.player if world else null
	var pdist := INF
	if pl:
		pdist = pl.global_position.distance_to(global_position)
	if pl and _name_label:
		var near: bool = world.state == "play" and pdist < 5.5
		_name_label.visible = near and not talking and not _emote.visible
	var awake := is_awake()
	visible = awake or talking or position.distance_to(home) > 1.0
	var sad := is_sad()
	anim.idle_clip = "sad" if sad else "idle"
	_wave_cd -= delta
	_social_cd -= delta
	_work_cd -= delta
	_expect_t -= delta
	if talking and talk_target:
		_end_chat()
		_visit = null
		var d := talk_target.global_position - global_position
		anim.turn_towards(atan2(d.x, d.z), delta, 7.0)
		anim.talk_t = 0.2
		anim.look_at_point(talk_target.global_position + Vector3(0, 0.9, 0))
		if talk_target.has_method("face_point"):
			talk_target.face_point(global_position)
		_cur_speed = 0.0
		_moving = false
		anim.update(delta, 0.0, _t)
		return
	if pdist > 8.0:
		_greeted = false
	if anim.is_busy():
		# waving or working: stand still and finish the clip
		_cur_speed = 0.0
		_moving = false
		if _face_player_t > 0.0 and pl:
			_face_player_t -= delta
			_face(pl.global_position, delta)
			anim.look_at_point(pl.global_position + Vector3(0, 0.9, 0))
		_animate(delta, pdist)
		return
	# a player walking up gets a wave (the dispossessed just stare)
	if awake and pl and world.state == "play" and pdist < WAVE_RANGE and not _greeted:
		_greeted = true
		if not sad and _wave_cd <= 0.0 and not model_name in NO_WAVE:
			_end_chat()
			_wave_cd = randf_range(35.0, 70.0)
			_face_player_t = 1.4
			anim.play_action("wave")
			_animate(delta, pdist)
			return
	if _chat_with != null:
		_update_chat(delta, pdist)
		return
	var goal := _target if awake else home
	var to := goal - position
	to.y = 0.0
	var want := 0.0
	if to.length() > 0.25 and ((_wait <= 0.0 and not is_expecting()) or not awake):
		want = speed * (1.6 if not awake else (0.75 if sad else 1.0))
		want = minf(want, 0.5 + to.length() * 1.6)   # ease into the stop
	_cur_speed = move_toward(_cur_speed, want, delta * (3.5 if want > _cur_speed else 5.0))
	if _cur_speed > 0.01 and to.length() > 0.02:
		var step := to.normalized() * _cur_speed * delta
		if step.length() > to.length():
			step = to
		position += step
		anim.turn_towards(atan2(to.x, to.z), delta, 6.0)
	_moving = _cur_speed > 0.05
	if want == 0.0 and awake:
		_wait -= delta
		if _visit != null:
			_arrive_visit()
		elif is_expecting():
			# a neighbour is on the way over: stay put and watch them come
			if _expect.global_position.distance_to(global_position) < 7.0:
				_face(_expect.global_position, delta)
				anim.look_at_point(_expect.global_position + Vector3(0, 0.85, 0))
		else:
			_idle_behaviour(pl, pdist)
		if _wait <= 0.0 and to.length() <= 0.25 and not anim.is_busy() and _chat_with == null and _visit == null \
				and not is_expecting():
			_pick_target()
	elif not awake:
		_visit = null
	if world:
		position.y = world.height_at(position.x, position.z)
	if pl and awake and pdist < LOOK_RANGE and world.state == "play":
		anim.look_at_point(pl.global_position + Vector3(0, 0.9, 0))
	_animate(delta, pdist)


func _animate(delta: float, pdist: float) -> void:
	if not visible or pdist > ANIM_RANGE:
		# not drawn: skip the pose work but keep the clocks running, so a work
		# clip started near the player still ends (is_busy() goes false)
		anim.tick(delta)
		return
	anim.update(delta, _cur_speed, _t)


func _face(p: Vector3, delta: float) -> void:
	var d := p - global_position
	if Vector2(d.x, d.z).length() > 0.1:
		anim.turn_towards(atan2(d.x, d.z), delta, 7.0)


func _idle_behaviour(pl: Node3D, pdist: float) -> void:
	if _moving or anim.is_busy() or pdist > ANIM_RANGE:
		return
	# hired hands work the palms while they wait
	if is_worker() and _work_cd <= 0.0:
		if _work_left <= 0 and randf() < 0.5:
			_work_left = randi_range(1, 3)
		if _work_left > 0:
			_work_left -= 1
			_work_cd = randf_range(0.2, 0.8)
			anim.play_action(["harvest", "chop", "plant", "harvest"][randi() % 4])
			_wait = maxf(_wait, 1.5)
			return
		_work_cd = randf_range(3.0, 8.0)
	# neighbours stop for a chat, or stroll over to someone standing nearby
	if _social_cd <= 0.0 and world and _chat_with == null and _visit == null and not model_name in NO_WAVE:
		_social_cd = randf_range(7.0, 15.0)
		var best: Npc = null
		var bd := VISIT_RANGE
		for other in _neighbours():
			if other == self or not is_instance_valid(other) or not other.is_idle() or other.is_worker() \
					or other._visit != null or other.is_expecting() or other.model_name in NO_WAVE:
				continue
			var d: float = other.global_position.distance_to(global_position)
			if d < bd:
				best = other
				bd = d
		if best == null:
			return
		if bd < 2.6:
			_chat(best)
		elif radius >= 2.0 and randf() < 0.7:
			# stroll over (people minding a post - the warung, the calo's corner -
			# stay there and only chat with whoever comes by)
			var away := global_position - best.global_position
			away.y = 0.0
			away = away.normalized() if away.length() > 0.01 else Vector3.RIGHT
			var spot := best.position + away * 1.3
			var home_d := Vector2(spot.x - anchor.x, spot.z - anchor.z).length()
			if home_d <= radius + VISIT_LEASH and _clear_path(position, spot):
				_target = spot
				_wait = 0.0
				_visit = best
				# the neighbour waits for as long as the walk takes (plus a margin)
				var eta := position.distance_to(spot) / maxf(speed, 0.3) + 3.0
				best._expect = self
				best._expect_t = eta + 6.0
				best._wait = maxf(best._wait, eta)


func _clear_path(a: Vector3, b: Vector3) -> bool:
	## No pathfinding: only stroll where the straight line misses buildings.
	for k in 6:
		var p := a.lerp(b, (k + 1) / 6.0)
		if not world.is_walkable(p.x, p.z) or not world.is_free(p.x, p.z, 0.4):
			return false
	return true


func _chat(other: Npc) -> void:
	var secs := randf_range(5.0, 9.0)
	_start_chat(other, secs, true)
	other._start_chat(self, secs, false)


func _arrive_visit() -> void:
	if _cur_speed > 0.3:
		return
	var v := _visit
	_visit = null
	if not is_instance_valid(v):
		return
	if v._expect == self:
		v._expect = null
	if v.is_idle() and v.global_position.distance_to(global_position) < 2.8:
		_chat(v)


func is_expecting() -> bool:
	## A neighbour is walking over to chat: stay put until they arrive or give up.
	if _expect == null:
		return false
	if not is_instance_valid(_expect) or _expect._visit != self or _expect_t <= 0.0 or not is_awake():
		_expect = null
		return false
	return true


func _neighbours() -> Array:
	var out: Array = []
	if world == null:
		return out
	var n = world.get("npcs")
	if n is Dictionary:
		out.append_array(n.values())
	var e = world.get("extras")
	if e is Dictionary:
		out.append_array(e.values())
	return out


func _start_chat(other: Npc, secs: float, first: bool) -> void:
	_chat_with = other
	_chat_t = secs
	_chat_turn = 0.0 if first else 1.6


func _end_chat() -> void:
	if _chat_with != null and is_instance_valid(_chat_with) and _chat_with._chat_with == self:
		_chat_with._chat_with = null
		_chat_with._social_cd = randf_range(12.0, 25.0)
	if _chat_with != null:
		_social_cd = randf_range(12.0, 25.0)
	_chat_with = null


func _update_chat(delta: float, pdist: float) -> void:
	_chat_t -= delta
	if _chat_t <= 0.0 or not is_instance_valid(_chat_with) or not is_awake() or _chat_with.talking:
		_end_chat()
		_animate(delta, pdist)
		return
	_cur_speed = 0.0
	_moving = false
	_face(_chat_with.global_position, delta)
	anim.look_at_point(_chat_with.global_position + Vector3(0, 0.85, 0))
	# take turns: talk ~1.6 s, listen ~1.6 s
	_chat_turn += delta
	if fmod(_chat_turn, 3.2) < 1.6:
		anim.talk_t = 0.15
	if world:
		position.y = world.height_at(position.x, position.z)
	_animate(delta, pdist)


func _pick_target() -> void:
	_wait = randf_range(2.0, 7.0)
	for i in 12:
		var a := randf() * TAU
		var r := sqrt(randf()) * radius
		var p := anchor + Vector3(cos(a) * r, 0, sin(a) * r)
		if world == null or (world.is_walkable(p.x, p.z) and world.is_free(p.x, p.z, 0.6)
				and world.is_free((p.x + position.x) * 0.5, (p.z + position.z) * 0.5, 0.4)):
			_target = p
			return
	_target = anchor
