class_name Npc
extends Node3D
## A villager (or any other character) that idles and wanders around an anchor
## point, goes home at night and turns to face the player while talking.
## Small touches keep the village alive: villagers glance at and wave to the
## player, neighbours stop for a chat, hired hands work the palms, and people
## who lost their land shuffle around slumped.

const WAVE_RANGE := 4.5
const LOOK_RANGE := 6.0
## Only characters the camera sees (or nearly: VIEW_MARGIN m past the frustum,
## for feet and shadows at the screen edge) are animated; the rest keep their
## clocks and heading running (CharAnim.tick). Without a camera: within
## ANIM_RANGE m of the camera focus.
const VIEW_MARGIN := 3.0
const ANIM_RANGE := 32.0
const NO_WAVE := ["char_preman", "char_petugas"]
const VISIT_RANGE := 20.0  # m: farthest neighbour a villager strolls over to
const VISIT_LEASH := 10.0  # m: how far past its wander radius a villager goes visiting
## Villagers with nobody nearby now and then walk to the warung (a neighbour who
## minds a post: small wander radius) for a chat, along the roads, at a brisker
## TRIP_PACE, and back. The game day is short (~2.5 min awake), so the walk is
## too, and rare (TRIP_COOLDOWN): the player should still find people at home.
const TRIP_RANGE := 60.0   # m: longest walk (along the route) to get there
const TRIP_CHANCE := 0.6   # per social check with nobody within VISIT_RANGE
const TRIP_COOLDOWN := Vector2(240.0, 420.0)   # s between trips
const TRIP_LAST_HOUR := 14.5
const TRIP_PACE := 1.2
## Stroll at about this multiple of the walk clip's own ground speed (1.4x: an
## unhurried ~3 steps/s); at night they hurry home with a brisk walk (HURRY_RATE x,
## ~4.7 steps/s; the run clip at ~1x lets the landing foot skim the ground).
const STROLL_RATE := 1.4
const HURRY_RATE := 2.1

static var _vf_frame := -1
static var _vf_planes: Array = []
static var _roads := {}    # road graph shared by all villagers (see _road_graph)

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
var speed := 0.9          # stroll (set per character from its walk clip in _ready)
var hurry_speed := 1.5    # going home at night
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
var _route: Array[Vector3] = []   # waypoints still to walk after _target
var _away := false       # out on a trip: walk back (to _trip_from) when done
var _trip_from := Vector3.ZERO
var _trip_cd := 0.0
var _night_nav := false  # following a route home after dark


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
	var sp := gait_speeds(anim, model_name)
	speed = sp.x
	hurry_speed = sp.y
	position = anchor
	_target = anchor
	_wait = randf_range(0.5, 3.0)
	_wave_cd = randf_range(0.0, 6.0)
	_social_cd = randf_range(3.0, 10.0)
	_trip_cd = randf_range(5.0, 30.0)
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


static func gait_speeds(a: CharAnim, _model_name: String = "") -> Vector2:
	## (stroll, hurry home) in m/s for a character, from its walk clip's own
	## ground speed so every model walks at the same relaxed cadence.
	if not a.skinned:
		return Vector2(0.9, 1.5)
	var walk := a.walk_run_speeds().x
	var stroll := clampf(walk * STROLL_RATE, 0.7, 0.95)
	# brisk, but below the switch to the run clip (CharAnim.WALK_TO_RUN)
	var hurry := maxf(stroll, walk * minf(HURRY_RATE, CharAnim.WALK_TO_RUN * 0.92))
	return Vector2(stroll, hurry)


func set_anchor(p: Vector3, r: float, teleport := false) -> void:
	var moved := p.distance_to(anchor) > 0.05
	anchor = p
	radius = r
	if teleport:
		position = p
		_cur_speed = 0.0
		_target = p
		_route.clear()
		_away = false
		_night_nav = false
		return
	if not moved:
		return   # the same post again (villager_changed fires often): carry on
	_away = false
	_night_nav = false
	if not _route_to(p):
		_route.clear()
		_target = p


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
	_trip_cd -= delta
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
		_animate(delta)
		return
	# a player walking up gets a wave (the dispossessed just stare)
	if awake and pl and world.state == "play" and pdist < WAVE_RANGE and not _greeted:
		_greeted = true
		if not sad and _wave_cd <= 0.0 and not model_name in NO_WAVE:
			_end_chat()
			_wave_cd = randf_range(35.0, 70.0)
			_face_player_t = 1.4
			anim.play_action("wave")
			_animate(delta)
			return
	if _chat_with != null:
		_update_chat(delta)
		return
	if awake:
		_night_nav = false
	elif (_away or not _route.is_empty()) and not _night_nav:
		# out on a trip at nightfall: back home along the roads
		_away = false
		_visit = null
		_night_nav = _route_to(home)
		if not _night_nav:
			_route.clear()
	var nav := awake or _night_nav
	var goal := _target if nav else home
	var to := goal - position
	to.y = 0.0
	while nav and not _route.is_empty() and to.length() < 0.6:
		# next waypoint (no stop at the corners)
		_target = _route.pop_front()
		goal = _target
		to = goal - position
		to.y = 0.0
	var want := 0.0
	if to.length() > 0.25 and ((_wait <= 0.0 and not is_expecting()) or not awake):
		want = hurry_speed if not awake else speed * (0.75 if sad else 1.0)
		if awake and (_away or not _route.is_empty()):
			want *= TRIP_PACE   # on an errand
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
	_animate(delta)


func _animate(delta: float) -> void:
	if not visible or not in_view():
		# not drawn: skip the pose work but keep the clocks and the heading
		# running, so a work clip started on screen still ends (is_busy() goes
		# false) and the villager comes back into view facing where it walks
		anim.tick(delta, _cur_speed)
		return
	anim.update(delta, _cur_speed, _t)


func in_view() -> bool:
	## On screen (or within VIEW_MARGIN m of it) for the camera that renders the
	## frame - the follow camera in play, the orbit on the title screen.
	var f := Engine.get_process_frames()
	if f != _vf_frame:
		_vf_frame = f
		_vf_planes = []
		var vp := get_viewport()
		var cam := vp.get_camera_3d() if vp else null
		if cam and cam.is_inside_tree():
			_vf_planes = cam.get_frustum()
	if _vf_planes.is_empty():
		var c := global_position
		var rig = world.get("cam_rig") if world else null
		if rig is Node3D:
			c = (rig as Node3D).global_position
		return c.distance_to(global_position) < ANIM_RANGE
	var p := global_position + Vector3(0, 0.7, 0)
	for pl: Plane in _vf_planes:
		if pl.distance_to(p) > VIEW_MARGIN:
			return false
	return true


func _face(p: Vector3, delta: float) -> void:
	var d := p - global_position
	if Vector2(d.x, d.z).length() > 0.1:
		anim.turn_towards(atan2(d.x, d.z), delta, 7.0)


func _idle_behaviour(_pl: Node3D, _pdist: float) -> void:
	## Runs on and off screen alike, so the village is in the same state
	## wherever the camera goes (clips off screen only tick, see _animate).
	if _moving or anim.is_busy():
		return
	# hired hands work the palms while they wait
	if is_worker() and _work_cd <= 0.0:
		if _work_left <= 0 and randf() < 0.85:
			_work_left = randi_range(2, 4)
		if _work_left > 0:
			_work_left -= 1
			_work_cd = randf_range(0.2, 0.7)
			anim.play_action(["harvest", "chop", "plant", "harvest"][randi() % 4])
			_wait = maxf(_wait, 1.5)
			return
		_work_cd = randf_range(2.0, 5.0)
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
			_try_trip()
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
				_route.clear()
				_target = spot
				_wait = 0.0
				_visit = best
				_expect_me(best, position.distance_to(spot))


func _expect_me(other: Npc, walk: float) -> void:
	## The neighbour waits for as long as the walk takes (plus a margin).
	var eta := walk / maxf(speed, 0.3) + 3.0
	other._expect = self
	other._expect_t = eta + 6.0
	other._wait = maxf(other._wait, eta)


func _try_trip() -> void:
	## Nobody around: now and then walk over to the warung (whoever minds a post
	## there) for a chat, along the roads, and come back afterwards.
	if vid == "" or radius < 2.0 or _trip_cd > 0.0 or _away or is_worker() or GS.hour > TRIP_LAST_HOUR \
			or randf() > TRIP_CHANCE:
		return
	_trip_cd = randf_range(10.0, 20.0)   # try again a little later if nobody is free
	for other in _neighbours():
		if other == self or not is_instance_valid(other) or other.radius >= 2.0 or other.model_name in NO_WAVE \
				or other.vid != "" or not other.is_idle() or other._visit != null or other.is_expecting():
			continue
		if other.global_position.distance_to(global_position) > TRIP_RANGE:
			continue
		# stand in front of them, on the side the road comes from
		var op: Vector3 = other.position
		var rn := _road_nearest(op)
		var rp: Vector3 = rn[0] if not rn.is_empty() else global_position
		var away: Vector3 = rp - op
		away.y = 0.0
		away = away.normalized() if away.length() > 0.3 else (global_position - op).normalized()
		for turn in [0.0, 0.7, -0.7]:
			var spot: Vector3 = op + away.rotated(Vector3.UP, turn) * 1.3
			if not world.is_free(spot.x, spot.z, 0.3):
				continue
			var from := position
			if _route_to(spot, TRIP_RANGE):
				_away = true
				_trip_from = from
				_trip_cd = randf_range(TRIP_COOLDOWN.x, TRIP_COOLDOWN.y)
				_wait = 0.0
				_visit = other
				_expect_me(other, _route_length())
				return
		return


func _route_length() -> float:
	var l := position.distance_to(_target)
	var p := _target
	for w in _route:
		l += p.distance_to(w)
		p = w
	return l


func _route_to(dest: Vector3, max_len := INF) -> bool:
	## Head for dest: straight when nothing is in the way, else along the roads
	## (off the road at the nearest points). Sets _target and _route; false (and
	## nothing changed) when there is no way within max_len.
	var pts: Array[Vector3] = []
	if position.distance_to(dest) <= max_len and _clear_path(position, dest):
		pts.append(dest)
	else:
		var g := _road_graph()
		var a := _road_nearest(position)
		var b := _road_nearest(dest)
		if a.is_empty() or b.is_empty():
			return false
		var ap: Vector3 = a[0]
		var bp: Vector3 = b[0]
		if not _clear_path(position, ap) or not _clear_path(bp, dest):
			return false
		pts.append(ap)
		if a[1] != b[1]:
			var path := _road_path(g, a, b)
			if path.is_empty():
				return false
			pts.append_array(path)
		pts.append(bp)
		pts.append(dest)
		var l := position.distance_to(pts[0])
		for i in pts.size() - 1:
			l += pts[i].distance_to(pts[i + 1])
		if l > max_len:
			return false
	_target = pts.pop_front()
	_route = pts
	return true


func _road_graph() -> Dictionary:
	## Nodes: the road polylines' vertices plus the points where a road's end
	## meets another road; edges between neighbours along a road. Each segment
	## lists the nodes on it (its ends and any junctions). Built once per world.
	if not _roads.is_empty() and _roads.get("world") == world:
		return _roads
	var lines: Array = []
	if world and world.get("layout") is Dictionary:
		lines = (world.get("layout") as Dictionary).get("roads", [])
	var nodes: Array[Vector3] = []
	var line_of: Array[int] = []
	var segs: Array = []      # [node a, node b, [nodes on it]]
	var ends: Array[int] = []
	for li in lines.size():
		var first := nodes.size()
		for q in lines[li]:
			nodes.append(Vector3(float(q[0]), 0.0, float(q[1])))
			line_of.append(li)
		if nodes.size() > first:
			ends.append(first)
			ends.append(nodes.size() - 1)
		for i in range(first, nodes.size() - 1):
			segs.append([i, i + 1, [i, i + 1]])
	var edges: Array = []
	for sg in segs:
		edges.append([sg[0], sg[1]])
	for e in ends:
		for sg in segs:
			if line_of[sg[0]] == line_of[e]:
				continue
			var q := Geometry3D.get_closest_point_to_segment(nodes[e], nodes[sg[0]], nodes[sg[1]])
			if q.distance_to(nodes[e]) > 4.0:
				continue
			nodes.append(q)
			line_of.append(line_of[sg[0]])
			var j := nodes.size() - 1
			edges.append_array([[e, j], [sg[0], j], [j, sg[1]]])
			(sg[2] as Array).append(j)
	var adj := []
	for i in nodes.size():
		adj.append([])
	for ed in edges:
		adj[ed[0]].append(ed[1])
		adj[ed[1]].append(ed[0])
	_roads = {"world": world, "nodes": nodes, "adj": adj, "segs": segs}
	return _roads


func _road_nearest(p: Vector3) -> Array:
	## [closest point on any road, its segment index], or [] without roads.
	var g := _road_graph()
	var nodes: Array = g["nodes"]
	var segs: Array = g["segs"]
	var best: Array = []
	var bd := INF
	var flat := Vector3(p.x, 0.0, p.z)
	for si in segs.size():
		var q := Geometry3D.get_closest_point_to_segment(flat, nodes[segs[si][0]], nodes[segs[si][1]])
		var d := q.distance_to(flat)
		if d < bd:
			bd = d
			best = [q, si]
	return best


static func _road_path(g: Dictionary, a: Array, b: Array) -> Array[Vector3]:
	## Road nodes between two points on the roads (a, b from _road_nearest), on
	## the shortest way (Dijkstra over a few dozen nodes).
	var nodes: Array = g["nodes"]
	var adj: Array = g["adj"]
	var segs: Array = g["segs"]
	var n := nodes.size()
	var dist := []
	var prev := []
	var done := []
	for i in n:
		dist.append(INF)
		prev.append(-1)
		done.append(false)
	var ap: Vector3 = a[0]
	var bp: Vector3 = b[0]
	for k in segs[a[1]][2]:
		dist[k] = minf(dist[k], ap.distance_to(nodes[k]))
	while true:
		var u := -1
		for i in n:
			if not done[i] and dist[i] < INF and (u < 0 or dist[i] < dist[u]):
				u = i
		if u < 0:
			break
		done[u] = true
		for v in adj[u]:
			var nd: float = dist[u] + (nodes[u] as Vector3).distance_to(nodes[v])
			if nd < dist[v]:
				dist[v] = nd
				prev[v] = u
	var end := -1
	var ed := INF
	for k in segs[b[1]][2]:
		var d: float = dist[k] + bp.distance_to(nodes[k])
		if d < ed:
			ed = d
			end = k
	var out: Array[Vector3] = []
	if end < 0 or ed == INF:
		return out
	var k := end
	while k >= 0:
		out.push_front(nodes[k])
		k = prev[k]
	return out


func _clear_path(a: Vector3, b: Vector3) -> bool:
	## No pathfinding: only stroll where the straight line misses buildings
	## (checked every ~1.5 m).
	var n := maxi(6, ceili(a.distance_to(b) / 1.5))
	for k in n:
		var p := a.lerp(b, (k + 1) / float(n))
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


func _update_chat(delta: float) -> void:
	_chat_t -= delta
	if _chat_t <= 0.0 or not is_instance_valid(_chat_with) or not is_awake() or _chat_with.talking:
		_end_chat()
		_animate(delta)
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
	_animate(delta)


func _pick_target() -> void:
	_wait = randf_range(2.0, 7.0)
	_route.clear()
	if _away:
		# back from a trip the way we came (then wander around the anchor again)
		_away = false
		if _route_to(_trip_from):
			return
		if _route_to(anchor):
			return
	for i in 12:
		var a := randf() * TAU
		var r := sqrt(randf()) * radius
		var p := anchor + Vector3(cos(a) * r, 0, sin(a) * r)
		if world == null or (world.is_walkable(p.x, p.z) and world.is_free(p.x, p.z, 0.6)
				and world.is_free((p.x + position.x) * 0.5, (p.z + position.z) * 0.5, 0.4)):
			_target = p
			return
	_target = anchor
