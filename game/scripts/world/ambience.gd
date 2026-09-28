extends Node3D
## Location-based nature ambience, created by world.gd. Everything plays on the
## "Ambience" bus; the sounds come from tools/make_ambience.py (assets/audio/amb_*.ogg).
##
##   * the sea (surf) and the water (river / lagoon + pond lapping) are AudioStreamPlayer3D
##     emitters that sit at the nearest shore / bank point and slide along it as the player
##     walks, so they come from the right side and swell as you get closer
##   * 2D beds cross-fade with the place and the hour: forest (wind in the leaves, birds),
##     open land (wind), village (hens, sparrows, doves, bamboo chimes), night (crickets)
##     and frogs (at night near water)
##   * one-shots at real spots around the player: birds in the trees by day, frogs by the
##     water and a tokek at the houses at night, roosters at dawn, owls, fish splashing
##   * inside a house: everything is heard from the door, quieter and muffled (the bus
##     low-pass, effect 0 of "Ambience")
## The island is analysed once at start (a 3 m grid of the height map: sea = water reached
## from the map edge without crossing a river channel; coast / bank points; a forest
## density grid from the layout's trees; the houses); the mix is re-evaluated at 10 Hz.
## Per frame only the listener is moved and the volumes glide.

const BUS := "Ambience"
const POLL := 0.1                  # s between analyses
const CELL := 3.0                  # water classification grid (m)
const BUCKET := 24.0               # nearest-point search buckets (m)
const FOREST_CELL := 8.0
const SLICE_US := 4000             # the start-up analysis runs in slices of this much CPU per frame
const GLIDE := 1.1                 # s, time constant of the bed cross-fades
const EMITTER_GLIDE := 0.6         # s, the water emitters sliding along the shore

## full-level volume of each loop (the files are mastered to -24 LUFS; the music sits
## at about -26 LUFS): the sea at the water line, the river at its bank, a bed at weight 1
const BEDS := {
	"sea": 0.0, "river": -1.0, "lake": -4.0,
	"forest": -5.0, "field": -9.0, "village": -6.0, "night": -9.0, "frogs": -6.0,
}
const EMITTERS := ["sea", "river", "lake"]
const SEA_RANGE := 110.0           # m, fully faded out
const WATER_RANGE := 60.0
const INDOOR_DB := -9.0            # inside a house: quieter and low-passed
const INDOOR_WEB_DB := -14.0       # web sample playback has no bus effects: quieter still
const INDOOR_CUTOFF := 900.0

## one-shots: file -> volume (dB at the 3D player, 0 dB at UNIT_SIZE metres)
const SHOT_DB := {
	"bird_kutilang": -13.0, "bird_kacer": -14.0, "bird_takur": -9.0, "bird_tekukur": -10.0,
	"bird_perkutut": -10.0, "bird_koel": -12.0, "bird_cinenen": -15.0, "bird_cucak": -14.0,
	"frog_a": -9.0, "frog_b": -11.0, "tokek": -8.0, "owl": -10.0, "splash_a": -6.0, "splash_b": -8.0,
	"rooster": -9.0, "chicken": -9.0, "tonggeret": -9.0,
}
const FOREST_BIRDS := ["bird_kutilang", "bird_kacer", "bird_takur", "bird_tekukur", "bird_koel",
	"bird_cinenen", "bird_cucak", "bird_perkutut"]
const VILLAGE_BIRDS := ["bird_kutilang", "bird_tekukur", "bird_perkutut", "bird_cinenen"]
const UNIT_SIZE := 12.0
const SHOT_RANGE := 70.0
const SHOT_PLAYERS := 3

var world: Node
var enabled := true
var geo_ready := false                     # the island analysis is done (it runs over the first frames)
## the last analysis and mix (read by the autotest and handy in a debugger)
var info := {}

var _coast := PackedVector2Array()        # sea water line
var _coast_b := {}
var _river := PackedVector2Array()        # river banks
var _river_b := {}
var _pool := PackedVector2Array()         # lagoon / pond banks
var _pool_b := {}
var _trees := PackedVector2Array()
var _trees_b := {}
var _houses := PackedVector2Array()
var _forest := PackedFloat32Array()
var _fn := 0
var _half := 225.0

var _players := {}                         # bed -> AudioStreamPlayer / AudioStreamPlayer3D
var _streams := {}
var _gain := {}                            # current linear weight 0..1
var _target := {}
var _idle := {}
var _emit_to := {}                         # emitter -> target position
var _shots: Array[AudioStreamPlayer3D] = []
var _timers := {}
var _listener: AudioListener3D
var _poll_t := 0.0
var _rng := RandomNumberGenerator.new()
var _bus := -1
var _lp: AudioEffectLowPassFilter
var _lp_k := 0.0                           # 0 = open, 1 = muffled
var _indoor_db := 0.0
var _web_samples := false
var _hear := Vector3.ZERO                  # where the ambience is heard from
var _slice_t := 0
var _cpu_us := 0


func _ready() -> void:
	_rng.randomize()
	_bus = AudioServer.get_bus_index(BUS)
	if _bus != -1 and AudioServer.get_bus_effect_count(_bus) > 0:
		_lp = AudioServer.get_bus_effect(_bus, 0) as AudioEffectLowPassFilter
	# the web export plays streams as Web Audio samples by default: no bus effects there
	_web_samples = OS.has_feature("web") and int(ProjectSettings.get_setting("audio/general/default_playback_type.web", 1)) == 1
	_half = float(world.world_size) * 0.5
	_analyse_island()      # a coroutine: sliced over the first frames (the title screen)
	_listener = AudioListener3D.new()
	add_child(_listener)
	_listener.make_current()
	var bus := BUS if _bus != -1 else "Master"
	for b in BEDS:
		var p: Node
		if b in EMITTERS:
			var p3 := AudioStreamPlayer3D.new()
			p3.attenuation_model = AudioStreamPlayer3D.ATTENUATION_DISABLED   # the level is ours
			p3.panning_strength = 0.6
			p3.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
			p3.bus = bus
			p3.position = Vector3(0, -50, 0)
			p = p3
		else:
			var p2 := AudioStreamPlayer.new()
			p2.bus = bus
			p = p2
		p.set("volume_db", -80.0)
		add_child(p)
		_players[b] = p
		_gain[b] = 0.0
		_target[b] = 0.0
		_idle[b] = 0.0
	for i in SHOT_PLAYERS:
		var s := AudioStreamPlayer3D.new()
		s.bus = bus
		s.unit_size = UNIT_SIZE
		s.max_distance = SHOT_RANGE
		s.panning_strength = 0.75
		s.attenuation_filter_db = -12.0
		s.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
		add_child(s)
		_shots.append(s)
	for k in ["bird", "tonggeret", "frog", "tokek", "owl", "rooster", "chicken", "splash"]:
		_timers[k] = _rng.randf_range(2.0, 8.0)


# ------------------------------------------------------------------ island analysis
func _next_slice() -> void:
	_cpu_us += Time.get_ticks_usec() - _slice_t
	await get_tree().process_frame
	_slice_t = Time.get_ticks_usec()


func _analyse_island() -> void:
	_slice_t = Time.get_ticks_usec()
	var ws: float = world.world_size
	var n := int(ceil(ws / CELL))
	var wl: float = world.water_level
	var img: Image = world.height_img
	var iw := img.get_width()
	var ih := img.get_height()
	var water := PackedByteArray()
	water.resize(n * n)
	for j in n:
		if Time.get_ticks_usec() - _slice_t > SLICE_US:
			await _next_slice()
		var pz := clampi(int(((j + 0.5) * CELL) / ws * ih), 0, ih - 1)
		for i in n:
			var px := clampi(int(((i + 0.5) * CELL) / ws * iw), 0, iw - 1)
			water[j * n + i] = 1 if img.get_pixel(px, pz).r < wl else 0
	# river channels (the layout's centre lines + their half width, with a margin for the
	# wobbly banks): the sea's flood fill stops there, and their banks are "river"
	var chan := PackedByteArray()
	chan.resize(n * n)
	for rv in world.layout.get("rivers", []):
		var pts: Array = rv["pts"]
		var r := float(rv.get("hw", 4.0)) + 3.0
		var rc := int(ceil(r / CELL))
		for k in pts.size() - 1:
			if Time.get_ticks_usec() - _slice_t > SLICE_US:
				await _next_slice()
			var a := Vector2(pts[k][0], pts[k][1])
			var b := Vector2(pts[k + 1][0], pts[k + 1][1])
			var steps := maxi(1, int(ceil(a.distance_to(b) / 1.5)))
			for s in steps + 1:
				var q := a.lerp(b, float(s) / steps)
				var ci := int((q.x + _half) / CELL)
				var cj := int((q.y + _half) / CELL)
				for dj in range(-rc, rc + 1):
					for di in range(-rc, rc + 1):
						var ii := ci + di
						var jj := cj + dj
						if ii < 0 or jj < 0 or ii >= n or jj >= n:
							continue
						if Vector2(-_half + (ii + 0.5) * CELL, -_half + (jj + 0.5) * CELL).distance_to(q) <= r:
							chan[jj * n + ii] = 1
	# the sea: water reached from the map edge without crossing a river channel
	var sea := PackedByteArray()
	sea.resize(n * n)
	var queue := PackedInt32Array()
	for i in n:
		for c in [i, (n - 1) * n + i, i * n, i * n + n - 1]:
			if water[c] == 1 and chan[c] == 0 and sea[c] == 0:
				sea[c] = 1
				queue.append(c)
	var head := 0
	while head < queue.size():
		var c := queue[head]
		head += 1
		if head % 1024 == 0 and Time.get_ticks_usec() - _slice_t > SLICE_US:
			await _next_slice()
		var ci := c % n
		var cj := c / n
		for d in [[1, 0], [-1, 0], [0, 1], [0, -1]]:
			var ii: int = ci + d[0]
			var jj: int = cj + d[1]
			if ii < 0 or jj < 0 or ii >= n or jj >= n:
				continue
			var k := jj * n + ii
			if sea[k] == 0 and water[k] == 1 and chan[k] == 0:
				sea[k] = 1
				queue.append(k)
	# shore points: water cells next to land
	for j in range(1, n - 1):
		if Time.get_ticks_usec() - _slice_t > SLICE_US:
			await _next_slice()
		for i in range(1, n - 1):
			var c := j * n + i
			if water[c] == 0:
				continue
			if water[c - 1] + water[c + 1] + water[c - n] + water[c + n] == 4:
				continue
			var p := Vector2(-_half + (i + 0.5) * CELL, -_half + (j + 0.5) * CELL)
			if sea[c] == 1:
				_coast.append(p)
			elif chan[c] == 1:
				_river.append(p)
			else:
				_pool.append(p)
	_coast_b = _bucket(_coast)
	_river_b = _bucket(_river)
	_pool_b = _bucket(_pool)
	# forest density (trees per 8 m cell, blurred twice) and the trees birds sit in
	_fn = int(ceil(ws / FOREST_CELL))
	var g := PackedFloat32Array()
	g.resize(_fn * _fn)
	const TREE_W := {"tree_big": 1.0, "sawit_wild": 0.8, "coconut": 0.3, "banana": 0.4, "bush_a": 0.2, "bush_b": 0.2}
	for d in world.layout.get("decor", []):
		var m: String = d.get("model", "")
		if not TREE_W.has(m):
			continue
		var pos: Array = d["pos"]
		var ci := int((float(pos[0]) + _half) / FOREST_CELL)
		var cj := int((float(pos[2]) + _half) / FOREST_CELL)
		if ci >= 0 and cj >= 0 and ci < _fn and cj < _fn:
			g[cj * _fn + ci] += TREE_W[m]
		if m in ["tree_big", "coconut", "sawit_wild", "banana"]:
			_trees.append(Vector2(float(pos[0]), float(pos[2])))
	if Time.get_ticks_usec() - _slice_t > SLICE_US:
		await _next_slice()
	g = _blur(g)
	await _next_slice()
	_forest = _blur(g)
	_trees_b = _bucket(_trees)
	for b in world.layout.get("buildings", []):
		var bp: Array = b["pos"]
		if str(b["id"]) != "dermaga":
			_houses.append(Vector2(float(bp[0]), float(bp[2])))
	info["coast_points"] = _coast.size()
	info["river_points"] = _river.size()
	info["pool_points"] = _pool.size()
	_cpu_us += Time.get_ticks_usec() - _slice_t
	info["island_ms"] = _cpu_us / 1000.0
	geo_ready = true


func _blur(g: PackedFloat32Array) -> PackedFloat32Array:
	var o := PackedFloat32Array()
	o.resize(g.size())
	var w := [1.0, 2.0, 1.0]
	for j in _fn:
		for i in _fn:
			var s := 0.0
			for dj in 3:
				for di in 3:
					var ii := i + di - 1
					var jj := j + dj - 1
					if ii >= 0 and jj >= 0 and ii < _fn and jj < _fn:
						s += g[jj * _fn + ii] * w[di] * w[dj]
			o[j * _fn + i] = s / 16.0
	return o


func _bucket(pts: PackedVector2Array) -> Dictionary:
	var b := {}
	for i in pts.size():
		var k := Vector2i(floori(pts[i].x / BUCKET), floori(pts[i].y / BUCKET))
		if not b.has(k):
			b[k] = PackedInt32Array()
		b[k].append(i)
	return b


func _nearest(pts: PackedVector2Array, buckets: Dictionary, p: Vector2, max_r: float) -> int:
	## index of the point nearest to p within max_r (-1 if none), ring by ring
	var c := Vector2i(floori(p.x / BUCKET), floori(p.y / BUCKET))
	var best := -1
	var bd := max_r * max_r
	for r in int(ceil(max_r / BUCKET)) + 1:
		for dz in range(-r, r + 1):
			for dx in range(-r, r + 1):
				if maxi(absi(dx), absi(dz)) != r:
					continue
				var key := c + Vector2i(dx, dz)
				if not buckets.has(key):
					continue
				for i: int in buckets[key]:
					var d := pts[i].distance_squared_to(p)
					if d < bd:
						bd = d
						best = i
		if best != -1 and bd <= float(r * r) * BUCKET * BUCKET:
			break
	return best


func forest_at(x: float, z: float) -> float:
	## tree density around (x, z), bilinear on the 8 m grid (~0 open land, ~1 deep forest)
	var fx := (x + _half) / FOREST_CELL - 0.5
	var fz := (z + _half) / FOREST_CELL - 0.5
	var i0 := clampi(int(floor(fx)), 0, _fn - 1)
	var j0 := clampi(int(floor(fz)), 0, _fn - 1)
	var i1 := mini(i0 + 1, _fn - 1)
	var j1 := mini(j0 + 1, _fn - 1)
	var tx := clampf(fx - i0, 0.0, 1.0)
	var tz := clampf(fz - j0, 0.0, 1.0)
	var a := lerpf(_forest[j0 * _fn + i0], _forest[j0 * _fn + i1], tx)
	var b := lerpf(_forest[j1 * _fn + i0], _forest[j1 * _fn + i1], tx)
	return lerpf(a, b, tz)


# ------------------------------------------------------------------ the mix
func _hear_point() -> Vector3:
	## outdoors: the player; inside a house: its door (the room is far off at x > 300)
	var ins: String = world.inside
	if ins != "" and world.door_points.has(ins):
		return world.door_points[ins]
	return world.player.global_position


func _analyse() -> void:
	if not geo_ready:
		return
	var hp := _hear_point()
	var p := Vector2(hp.x, hp.z)
	var inside: bool = world.inside != ""
	var hour: float = GS.hour
	var night: float = world.night_k
	var day := 1.0 - night
	# water
	var ci := _nearest(_coast, _coast_b, p, SEA_RANGE)
	var d_sea := p.distance_to(_coast[ci]) if ci != -1 else INF
	var ri := _nearest(_river, _river_b, p, WATER_RANGE)
	var d_river := p.distance_to(_river[ri]) if ri != -1 else INF
	var qi := _nearest(_pool, _pool_b, p, WATER_RANGE)
	var d_pool := p.distance_to(_pool[qi]) if qi != -1 else INF
	# land
	var dens := forest_at(p.x, p.y)
	var forest := smoothstep(0.3, 0.8, dens)
	var d_house := INF
	for h in _houses:
		d_house = minf(d_house, h.distance_to(p))
	var village := 1.0 - smoothstep(10.0, 40.0, d_house)
	var open := clampf(1.0 - forest - 0.6 * village, 0.0, 1.0)
	var near_sea := 1.0 - smoothstep(10.0, 40.0, d_sea)
	var on_beach := 1.0 - smoothstep(4.0, 16.0, d_sea)
	var near_water := 1.0 - smoothstep(8.0, 45.0, minf(d_river, d_pool))
	# levels (linear weights; BEDS holds each loop's full level)
	_target["sea"] = _water_level(d_sea, 12.0, 20.0, 45.0, SEA_RANGE)
	_target["river"] = _water_level(d_river, 5.0, 16.0, 35.0, WATER_RANGE)
	_target["lake"] = _water_level(d_pool, 4.0, 16.0, 25.0, 50.0)
	_target["forest"] = forest * day * (1.0 - 0.7 * on_beach)
	_target["village"] = village * day * (1.0 - 0.5 * forest)
	_target["field"] = (0.35 + 0.65 * open) * (day + 0.6 * night) * (1.0 - 0.4 * near_sea)
	_target["night"] = night * (0.45 + 0.55 * (1.0 - near_sea))
	_target["frogs"] = night * maxf(0.15, near_water) * (1.0 - 0.7 * near_sea)
	if not enabled or world.state == "title":
		for b in _target:
			_target[b] = 0.0
	# the water emitters sit a few metres out from the nearest shore point (a stable
	# direction, never on top of the listener)
	_emit_to["sea"] = _emitter_spot(p, _coast[ci] if ci != -1 else p, 5.0)
	_emit_to["river"] = _emitter_spot(p, _river[ri] if ri != -1 else p, 2.5)
	_emit_to["lake"] = _emitter_spot(p, _pool[qi] if qi != -1 else p, 2.0)
	info.merge({"pos": p, "inside": inside, "hour": hour, "night": night, "d_sea": d_sea, "d_river": d_river,
		"d_pool": d_pool, "forest_density": dens, "forest": forest, "village": village, "open": open,
		"d_house": d_house, "near_water": near_water}, true)


func _water_level(d: float, soft: float, slope: float, fade_from: float, fade_to: float) -> float:
	## 0 dB at the water, -slope dB per decade of (1 + d / soft), fading out from fade_from
	## to fade_to metres
	if d == INF:
		return 0.0
	return db_to_linear(-slope * log(1.0 + d / soft) / log(10.0)) * (1.0 - smoothstep(fade_from, fade_to, d))


func _emitter_spot(from: Vector2, shore: Vector2, out: float) -> Vector3:
	var dir := shore - from
	var l := dir.length()
	var q := shore + (dir / l * out if l > 0.01 else Vector2(0, out))
	return Vector3(q.x, float(world.water_level) + 0.3, q.y)


func level_db(bed: String) -> float:
	## the bed's current volume as heard (dB, -80 when silent), indoor attenuation included
	var g: float = _gain.get(bed, 0.0)
	if g < 0.0005:
		return -80.0
	return float(BEDS[bed]) + linear_to_db(g) + _indoor_db


func snap() -> void:
	## jumps straight to the current place's mix (autotest, teleports)
	if not geo_ready:
		return
	_analyse()
	_update_indoor(1000.0)
	for b in BEDS:
		_gain[b] = _target[b]
		if b in EMITTERS:
			(_players[b] as Node3D).global_position = _emit_to[b]
	_apply(0.0)


# ------------------------------------------------------------------ per frame
func _process(delta: float) -> void:
	if world == null or world.player == null:
		return
	_hear = _hear_point()
	# the listener at the player's head, facing like the camera (screen right = ear right)
	var yaw: float = world.camera.global_rotation.y if world.camera else 0.0
	_listener.global_transform = Transform3D(Basis(Vector3.UP, yaw), _hear + Vector3(0, 1.4, 0))
	_poll_t += delta
	if _poll_t >= POLL:
		var dt := _poll_t
		_poll_t = 0.0
		_analyse()
		if world.state == "play":
			_tick_shots(dt)
	_update_indoor(delta)
	var k := 1.0 - exp(-delta / GLIDE)
	for b in BEDS:
		var t: float = _target[b]
		var g: float = _gain[b]
		if absf(t - g) > 0.0005:
			_gain[b] = lerpf(g, t, k) if absf(t - g) > 0.002 else t
	var ke := 1.0 - exp(-delta / EMITTER_GLIDE)
	for b in EMITTERS:
		var p3 := _players[b] as Node3D
		var to: Vector3 = _emit_to.get(b, p3.global_position)
		if p3.global_position.distance_squared_to(to) > 400.0:
			p3.global_position = to            # a jump (teleport, door): no slide across the map
		else:
			p3.global_position = p3.global_position.lerp(to, ke)
	_apply(delta)


func _apply(delta: float) -> void:
	for b in BEDS:
		var p: Node = _players[b]
		var g: float = _gain[b]
		var vol := -80.0
		if g < 0.0005:
			_idle[b] += delta
			if _idle[b] > 1.0 and p.get("playing"):
				p.call("stop")
		else:
			_idle[b] = 0.0
			vol = float(BEDS[b]) + linear_to_db(g) + _indoor_db
			if not p.get("playing"):
				var s := _stream("amb_" + b, true)
				if s == null:
					continue
				p.set("stream", s)
				p.set("volume_db", vol)
				p.call("play", _rng.randf() * s.get_length())   # never the same stretch twice
		# only real changes reach the player (on the web each one is a Web Audio call)
		if absf(float(p.get("volume_db")) - vol) > 0.05:
			p.set("volume_db", vol)


func _update_indoor(delta: float) -> void:
	var inside: bool = world.inside != ""
	var want := 1.0 if inside else 0.0
	_lp_k = move_toward(_lp_k, want, delta / 0.35)
	_indoor_db = (INDOOR_WEB_DB if _web_samples else INDOOR_DB) * _lp_k
	if _lp and _bus != -1:
		var on := _lp_k > 0.001
		if AudioServer.is_bus_effect_enabled(_bus, 0) != on:
			AudioServer.set_bus_effect_enabled(_bus, 0, on)
		if on:
			# sweep the cutoff (log scale) so going in / out is a smooth muffle, not a click
			_lp.cutoff_hz = exp(lerpf(log(16000.0), log(INDOOR_CUTOFF), _lp_k))
	info["indoor_db"] = _indoor_db
	info["lowpass"] = _bus != -1 and AudioServer.is_bus_effect_enabled(_bus, 0)
	info["cutoff"] = _lp.cutoff_hz if _lp else 0.0


func _stream(name: String, loop: bool) -> AudioStream:
	if _streams.has(name):
		return _streams[name]
	var path := "res://assets/audio/%s.ogg" % name
	var s: AudioStream = null
	if ResourceLoader.exists(path):
		s = load(path)
		if s is AudioStreamOggVorbis:
			(s as AudioStreamOggVorbis).loop = loop
	_streams[name] = s
	return s


# ------------------------------------------------------------------ one-shots
func _tick_shots(dt: float) -> void:
	var inside: bool = info.get("inside", false)
	var night: float = info.get("night", 0.0)
	var day := 1.0 - night
	var hour: float = GS.hour
	var forest: float = info.get("forest", 0.0)
	var village: float = info.get("village", 0.0)
	var near_water: float = info.get("near_water", 0.0)
	var p := Vector2(_hear.x, _hear.z)
	for k in _timers:
		_timers[k] -= dt
	# birds in the trees around by day (more in the forest, a few in the villages)
	if _timers["bird"] <= 0.0:
		var rate := day * (0.12 + 0.9 * forest + 0.25 * village)
		_timers["bird"] = _rng.randf_range(5.0, 14.0) / maxf(rate, 0.05)
		if rate > 0.1 and not inside:
			var list: Array = FOREST_BIRDS if forest > 0.3 or village < 0.3 else VILLAGE_BIRDS
			var spot := _tree_near(p, 10.0, 38.0)
			if spot != Vector2.INF:
				_play_shot(list[_rng.randi() % list.size()], Vector3(spot.x, _rng.randf_range(4.0, 8.0), spot.y), 0.94, 1.06)
	# tonggeret (cicada) swells in the trees, mostly in the late afternoon
	if _timers["tonggeret"] <= 0.0:
		var eve := 1.0 - smoothstep(0.0, 2.0, absf(hour - 17.5))
		_timers["tonggeret"] = _rng.randf_range(25.0, 60.0) / maxf(0.2, eve * 2.0 + 0.3)
		if forest > 0.25 and day > 0.5 and not inside:
			var spot := _tree_near(p, 15.0, 45.0)
			if spot != Vector2.INF:
				_play_shot("tonggeret", Vector3(spot.x, 6.0, spot.y), 0.95, 1.08)
	# frogs at the water's edge at night
	if _timers["frog"] <= 0.0:
		_timers["frog"] = _rng.randf_range(3.0, 8.0)
		if night > 0.5 and near_water > 0.2 and not inside:
			var w := _water_near(p, 6.0, 30.0)
			if w != Vector2.INF:
				_play_shot("frog_a" if _rng.randf() < 0.65 else "frog_b", Vector3(w.x, float(world.water_level) + 0.3, w.y), 0.9, 1.1)
	# a tokek on a house at night (heard from inside the house as well)
	if _timers["tokek"] <= 0.0:
		_timers["tokek"] = _rng.randf_range(35.0, 80.0)
		if night > 0.5 and (village > 0.3 or inside):
			var h := _house_near(p, 0.0, 35.0)
			if h != Vector2.INF:
				_play_shot("tokek", Vector3(h.x, 3.0, h.y), 0.95, 1.05)
	# owls at night among the trees
	if _timers["owl"] <= 0.0:
		_timers["owl"] = _rng.randf_range(25.0, 60.0)
		if night > 0.6 and forest + 0.3 * (1.0 - village) > 0.3 and not inside:
			var spot := _tree_near(p, 18.0, 45.0)
			if spot != Vector2.INF:
				_play_shot("owl", Vector3(spot.x, 7.0, spot.y), 0.95, 1.05)
	# roosters: all through the early morning, now and then later in the day
	if _timers["rooster"] <= 0.0:
		var dawn := hour < 8.5
		_timers["rooster"] = _rng.randf_range(10.0, 25.0) if dawn else _rng.randf_range(60.0, 140.0)
		if day > 0.6 and (village > 0.15 or inside):
			var h := _house_near(p, 12.0, 55.0)
			if h != Vector2.INF:
				_play_shot("rooster", Vector3(h.x, 1.0, h.y), 0.93, 1.07)
	# hens pecking about the houses
	if _timers["chicken"] <= 0.0:
		_timers["chicken"] = _rng.randf_range(14.0, 35.0)
		if day > 0.6 and village > 0.4 and not inside:
			var h := _house_near(p, 5.0, 25.0)
			if h != Vector2.INF:
				var off := Vector2(_rng.randf_range(-4, 4), _rng.randf_range(-4, 4))
				_play_shot("chicken", Vector3(h.x + off.x, 0.3, h.y + off.y), 0.92, 1.08)
	# a fish jumping
	if _timers["splash"] <= 0.0:
		_timers["splash"] = _rng.randf_range(12.0, 35.0)
		if not inside and (near_water > 0.3 or float(info.get("d_sea", INF)) < 30.0):
			var w := _water_near(p, 5.0, 25.0, true)
			if w != Vector2.INF:
				_play_shot("splash_a" if _rng.randf() < 0.6 else "splash_b", Vector3(w.x, float(world.water_level), w.y), 0.85, 1.15)


func _play_shot(name: String, pos: Vector3, pmin: float, pmax: float) -> void:
	var s := _stream("amb_" + name, false)
	if s == null:
		return
	var free: AudioStreamPlayer3D = null
	for sp in _shots:
		if not sp.playing:
			free = sp
			break
	if free == null:
		return          # three at once is plenty
	free.stream = s
	free.global_position = pos
	free.volume_db = float(SHOT_DB.get(name, -10.0)) + _indoor_db
	free.pitch_scale = _rng.randf_range(pmin, pmax)
	free.play()
	info["last_shot"] = name
	info["shots_played"] = int(info.get("shots_played", 0)) + 1


func _pick(pts: PackedVector2Array, buckets: Dictionary, p: Vector2, rmin: float, rmax: float) -> Vector2:
	## a random point of pts at rmin..rmax from p (Vector2.INF if none)
	var c := Vector2i(floori(p.x / BUCKET), floori(p.y / BUCKET))
	var rr := int(ceil(rmax / BUCKET))
	var found := PackedInt32Array()
	for dz in range(-rr, rr + 1):
		for dx in range(-rr, rr + 1):
			var key := c + Vector2i(dx, dz)
			if not buckets.has(key):
				continue
			for i: int in buckets[key]:
				var d := pts[i].distance_to(p)
				if d >= rmin and d <= rmax:
					found.append(i)
	if found.is_empty():
		return Vector2.INF
	return pts[found[_rng.randi() % found.size()]]


func _tree_near(p: Vector2, rmin: float, rmax: float) -> Vector2:
	var t := _pick(_trees, _trees_b, p, rmin, rmax)
	if t == Vector2.INF:
		# open land: a bird somewhere out there
		var a := _rng.randf() * TAU
		var d := _rng.randf_range(rmin, rmax)
		return p + Vector2(cos(a), sin(a)) * d
	return t


func _water_near(p: Vector2, rmin: float, rmax: float, with_sea := false) -> Vector2:
	var w := _pick(_river, _river_b, p, rmin, rmax)
	if w == Vector2.INF:
		w = _pick(_pool, _pool_b, p, rmin, rmax)
	if w == Vector2.INF and with_sea:
		w = _pick(_coast, _coast_b, p, rmin, rmax)
	return w


func _house_near(p: Vector2, rmin: float, rmax: float) -> Vector2:
	var best := Vector2.INF
	var n := 0
	for h in _houses:
		var d := h.distance_to(p)
		if d >= rmin and d <= rmax:
			n += 1
			if _rng.randi() % n == 0:      # reservoir pick: any house in range, evenly
				best = h
	return best


func _exit_tree() -> void:
	if _bus != -1 and AudioServer.get_bus_effect_count(_bus) > 0:
		AudioServer.set_bus_effect_enabled(_bus, 0, false)
	for b in _players:
		var p: Node = _players[b]
		p.call("stop")
		p.set("stream", null)
	for s in _shots:
		s.stop()
		s.stream = null
	_streams.clear()
