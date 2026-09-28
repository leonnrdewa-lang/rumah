extends Node3D
## Farm and village animals, created by world.gd: Bali cattle (sapi) grazing in the
## fields, water buffalo (kerbau) on the river banks (they wade into the shallows), goats
## (kambing) by the yard fences, flocks of chickens (ayam, each with a rooster) around the
## houses, ducks (bebek) paddling on the rivers, frogs (kodok) on the banks (more of them
## at night), village cats (kucing) on the porches and kampung dogs (anjing).
##
## Models: assets/models/animal_<id>.glb from blender/animals.py; data/animal_models.json
## has each clip's length, the ground speed the walk/run clips cover at 1x and the colour
## variants. At load every model's surfaces are merged into one (each material's colour
## baked into the vertex colour, which the world shader multiplies anyway): one draw + its
## ink outline per animal, and every animal shares the same toon material (with the
## characters' rim light and bold outline).
##
## Behaviour: a small state machine per animal (idle / wander around its home / eat / call
## / flee from a player running up / look at the player / species extras: frogs hop in
## bursts, ducks swim in lazy curves and keep to the water, cats sit on the porches, dogs
## trot after the player for a while, chickens peck and scatter), all run from this node's
## _process, no script per animal. Animals on screen within FULL_RANGE m are updated every
## frame and their AnimationPlayer advanced by hand (walk/run playback rate = ground speed
## / the clip's own speed, so the feet do not slide); the others think every LOD_STEP s
## with their animation paused, and those beyond SHOW_RANGE are hidden. At night they sleep
## near home (the frogs come out instead).
##
## Sounds: assets/audio/animals/<id>_1..3.ogg (+ ayam_crow.ogg) from
## tools/make_animal_sounds.py, on the "SFX" bus through MAX_VOICES AudioStreamPlayer3D
## (heard at the ambience's listener: the player, or the door of the house they are in).
## Petting: world.gd asks pet_target() when nothing else is in reach ("Elus <nama>").

const DATA_PATH := "res://data/animal_models.json"
const SND_DIR := "res://assets/audio/animals/"
const SEED := 240917
const INTERIOR_X := 300.0
## on screen and within FULL_RANGE m of the camera focus: think + animate every frame
const FULL_RANGE := 45.0
## drawn within SHOW_RANGE m of the focus (+ SHOW_MARGIN hysteresis): the play camera sees
## ~40 m around the player, the title fly-over ~45 m around its centre
const SHOW_RANGE := 66.0
const SHOW_MARGIN := 4.0
const VIEW_MARGIN := 2.5
## everyone else thinks about every LOD_STEP s, their animation paused
const LOD_STEP := 0.45
## the near / far lists and the visibility are refreshed every SCAN_STEP s
const SCAN_STEP := 0.2
## on screen beyond HALF_RATE m: think + animate every other frame
const HALF_RATE := 18.0
## a walking animal checks the ground ahead every CHECK_STEP m
const CHECK_STEP := 0.25
## models are built when an animal first comes within SHOW_RANGE, this many per scan
const BUILD_PER_SCAN := 2
const MAX_VOICES := 3
const PET_RANGE := 1.6
const NIGHT_SLEEP := 0.6        # world.night_k above which the animals sleep near home
const NIGHT_FROGS := 0.45       # ... and the night frogs come out
const DAWN_END := 7.6           # roosters crow until then (the game day starts at 06:00)
const INDOOR_DB := -10.0        # heard from inside a house
const RIM := 0.35
const LOOP_CLIPS := ["idle", "walk", "run", "eat", "swim", "sit", "wag"]
const ONE_SHOT := ["call", "hop"]
const RANDOM_START := ["idle", "eat", "sit", "swim", "wag"]

## Behaviour per species. walk/run: stroll / flee playback rate of the walk / run clip
## (speed = the clip's own ground speed x this); turn: rad/s; radius: wander radius around
## home; pad: obstacle clearance; body: ~half length (separation, pet reach); flee_r /
## flee_v: bolts when the player comes closer than flee_r m faster than flee_v m/s toward
## it (0 = never; the keyboard run is 5.2 m/s, the sprint 7.8); flee_d: how far; look_r:
## looks at the player within; w: weights of the next activity; t_*: how long; call: s
## between calls; db / unit / maxd: sound level (dB at `unit` m) and hearing range; blob:
## contact shadow radii (x, z); small: prefers bare ground (roads, yards) where the
## undergrowth does not hide it, and turns to face the player.
const B := {
	"sapi": {"walk": 1.2, "run": 1.0, "turn": 1.3, "accel": 0.9, "radius": 7.0, "pad": 0.75, "body": 0.8,
		"flee_r": 2.2, "flee_v": 6.0, "flee_d": 4.0, "look_r": 7.0, "look_max": 0.9,
		"w": {"idle": 0.25, "walk": 0.3, "eat": 0.45}, "t_idle": Vector2(3.0, 8.0), "t_eat": Vector2(6.0, 16.0),
		"call": Vector2(25.0, 70.0), "db": -5.0, "unit": 10.0, "maxd": 50.0,
		"shadow": true, "blob": Vector2(0.5, 0.95), "scale": 1.0, "small": false},
	"kerbau": {"walk": 1.15, "run": 1.0, "turn": 1.1, "accel": 0.8, "radius": 6.0, "pad": 0.75, "body": 0.85,
		"flee_r": 2.0, "flee_v": 6.5, "flee_d": 3.5, "look_r": 7.0, "look_max": 0.85,
		"w": {"idle": 0.35, "walk": 0.25, "eat": 0.4}, "t_idle": Vector2(4.0, 10.0), "t_eat": Vector2(6.0, 16.0),
		"call": Vector2(30.0, 80.0), "db": -5.0, "unit": 10.0, "maxd": 50.0,
		"shadow": true, "blob": Vector2(0.55, 1.0), "scale": 1.0, "small": false},
	"kambing": {"walk": 1.2, "run": 1.1, "turn": 2.6, "accel": 2.0, "radius": 4.5, "pad": 0.45, "body": 0.45,
		"flee_r": 2.0, "flee_v": 5.0, "flee_d": 3.5, "look_r": 6.0, "look_max": 1.0,
		"w": {"idle": 0.3, "walk": 0.3, "eat": 0.4}, "t_idle": Vector2(2.0, 6.0), "t_eat": Vector2(4.0, 10.0),
		"call": Vector2(18.0, 50.0), "db": -7.0, "unit": 7.0, "maxd": 40.0,
		"shadow": true, "blob": Vector2(0.28, 0.5), "scale": 1.0, "small": false},
	"ayam": {"walk": 1.1, "run": 1.1, "turn": 5.0, "accel": 3.0, "radius": 4.5, "pad": 0.3, "body": 0.25,
		"flee_r": 1.8, "flee_v": 4.2, "flee_d": 3.0, "look_r": 4.0, "look_max": 1.1,
		"w": {"idle": 0.2, "walk": 0.35, "eat": 0.45}, "t_idle": Vector2(1.5, 4.0), "t_eat": Vector2(2.0, 6.0),
		"call": Vector2(10.0, 30.0), "db": -10.0, "unit": 5.0, "maxd": 30.0,
		"shadow": true, "blob": Vector2(0.18, 0.26), "scale": 1.0, "small": true},
	"bebek": {"walk": 1.0, "run": 1.1, "turn": 3.0, "accel": 1.5, "radius": 7.0, "pad": 0.3, "body": 0.22,
		"flee_r": 1.8, "flee_v": 4.0, "flee_d": 3.0, "look_r": 4.0, "look_max": 1.1,
		"w": {"idle": 0.3, "walk": 0.55, "eat": 0.15}, "t_idle": Vector2(2.0, 6.0), "t_eat": Vector2(3.0, 7.0),
		"call": Vector2(10.0, 28.0), "db": -9.0, "unit": 6.0, "maxd": 35.0,
		"shadow": true, "blob": Vector2(0.15, 0.22), "scale": 1.0, "small": true},
	"kodok": {"walk": 1.0, "run": 1.0, "turn": 7.0, "accel": 3.0, "radius": 2.5, "pad": 0.15, "body": 0.15,
		"flee_r": 1.4, "flee_v": 2.5, "flee_d": 1.4, "look_r": 3.0, "look_max": 0.0,
		"w": {"idle": 0.6, "walk": 0.25, "eat": 0.15}, "t_idle": Vector2(3.0, 9.0), "t_eat": Vector2(1.6, 3.2),
		"call": Vector2(40.0, 120.0), "db": -12.0, "unit": 4.0, "maxd": 28.0,
		"shadow": true, "blob": Vector2(0.14, 0.16), "scale": 1.4, "small": true},
	"kucing": {"walk": 1.15, "run": 1.0, "turn": 4.0, "accel": 2.5, "radius": 4.5, "pad": 0.3, "body": 0.3,
		"flee_r": 1.6, "flee_v": 4.5, "flee_d": 3.0, "look_r": 5.0, "look_max": 1.1,
		"w": {"idle": 0.15, "walk": 0.25, "eat": 0.1, "sit": 0.5}, "t_idle": Vector2(2.0, 5.0), "t_eat": Vector2(2.0, 5.0),
		"call": Vector2(35.0, 90.0), "db": -10.0, "unit": 5.0, "maxd": 30.0,
		"shadow": true, "blob": Vector2(0.17, 0.3), "scale": 1.0, "small": true},
	"anjing": {"walk": 1.3, "run": 1.0, "turn": 4.0, "accel": 3.0, "radius": 6.0, "pad": 0.35, "body": 0.4,
		"flee_r": 0.0, "flee_v": 99.0, "flee_d": 2.0, "look_r": 7.0, "look_max": 1.1,
		"w": {"idle": 0.35, "walk": 0.4, "eat": 0.1, "wag": 0.15}, "t_idle": Vector2(2.0, 6.0), "t_eat": Vector2(2.0, 5.0),
		"call": Vector2(30.0, 80.0), "db": -7.0, "unit": 8.0, "maxd": 45.0,
		"shadow": true, "blob": Vector2(0.22, 0.42), "scale": 1.0, "small": true},
}
const FROG_NIGHT_W := {"idle": 0.35, "walk": 0.5, "eat": 0.15}
## what the prompt calls them ("Elus <nama>"), by colour variant
const LABEL := {"sapi": "sapi bali", "kerbau": "kerbau", "kambing": "kambing", "ayam": "ayam", "bebek": "bebek",
	"kodok": "kodok", "kucing": "kucing", "anjing": "anjing kampung"}
const VARIANT_LABEL := {
	"sapi": {"jantan": "sapi bali jantan"},
	"kerbau": {"bule": "kerbau bule"},
	"kambing": {"putih": "kambing putih", "coklat": "kambing coklat", "hitam": "kambing hitam"},
	"ayam": {"betina": "ayam betina", "jago": "ayam jago", "putih": "ayam putih", "hitam": "ayam hitam"},
	"kucing": {"oren": "kucing oren", "belang_tiga": "kucing belang tiga", "hitam": "kucing hitam", "abu": "kucing abu-abu"},
	"anjing": {"hitam": "anjing hitam", "putih": "anjing putih", "belang": "anjing belang"},
}
## undergrowth weight per plant (tall thickets hide a chicken, the low carpet barely)
const COVER_W := {"shrub_a": 3.0, "shrub_b": 3.0, "keladi": 2.0, "fern_a": 2.0, "fern_b": 2.0, "grass_a": 0.6,
	"grass_b": 0.8, "pile_fronds": 1.0, "vine_log": 1.0}

enum Kind { LAND, DUCK, BUFFALO, FROG }


class Animal:
	extends RefCounted
	var id := ""
	var idx := 0
	var kind := 0
	var cfg: Dictionary
	var node: Node3D
	var model: Node3D
	var ap: AnimationPlayer
	var skel: Skeleton3D
	var blob: MeshInstance3D
	var look_bones: Array[int] = []
	var look_w: Array[float] = []
	var look_up: Array[Vector3] = []     # yaw / pitch axes in each bone's parent space (rest pose)
	var look_right: Array[Vector3] = []
	var head_z := 0.3                    # the head's rest position (model space, scaled)
	var head_y := 0.5
	var head := -1
	var sk_up := Vector3.UP
	var sk_fwd := Vector3.BACK
	var sk_right := Vector3.LEFT
	var home := Vector3.ZERO       # centre of the wander area (shared by the group)
	var nest := Vector3.ZERO       # where it sleeps / starts the day
	var radius := 4.0
	var group: Array = []
	var variant := {}
	var display := ""
	var rooster := false
	var night_only := false
	var out := true                # a night frog that is out
	var voice := 1.0
	var vi := 0                    # colour variant
	var scale := 1.0
	var height := 0.5
	# copied from the config / model data
	var walk_v := 0.5
	var run_v := 1.2
	var cruise := 0.5
	var flee_speed := 1.2
	var turn := 2.0
	var accel := 2.0
	var body := 0.3
	var pad := 0.3
	var flee_r := 0.0
	var flee_v := 99.0
	var look_r := 5.0
	var look_max := 1.0
	var small := false
	var db := -8.0
	var unit := 6.0
	var maxd := 35.0
	var call_len := 1.0
	var call_open := 0.3
	var tilt_len := 0.0
	var idle_rate := 1.0
	# state
	var state := "idle"
	var t := 0.0
	var target := Vector3.ZERO
	var yaw := 0.0
	var speed := 0.0
	var tilt := 0.0
	var clip := ""
	var rate := 1.0
	var alt := false
	var run_clip := false
	var call_t := 10.0
	var sound_in := -1.0
	var sound_force := false
	var sound_crow := false
	var look_on := false
	var look_at := Vector3.ZERO
	var look_yaw := 0.0
	var look_pitch := 0.0
	var last_t := 0.0              # _clock of its last update
	var in_view := false
	var shown := true
	var far := false
	var d2 := 0.0                  # squared distance to the camera focus at the last scan
	var gx := INF                  # where the ground was last sampled
	var gz := INF
	var gyaw := 0.0
	var chk := 0.0                 # m to walk before the next look-ahead check
	var on_water := false
	var flee_cd := 0.0
	var follow_cd := 0.0
	var pet_cd := 0.0
	var stuck := 0.0
	var odo := 0.0                 # metres walked (autotest)
	# frog hops
	var hop_t := -1.0
	var hop_wait := 0.0
	var hop_from := Vector3.ZERO
	var hop_dir := Vector3.ZERO
	var hop_len := 0.3
	var hop_dist := 0.3
	var hop_time := 0.6
	var hop_rate := 1.0
	var air0 := 0.167
	var air1 := 0.417
	var hops := 0
	var new_hop := false
	var item := {}


var world: Node
var animals: Array[Animal] = []
var counts := {}
## autotest / debug
var sounds_played := 0
var last_sound := ""
var pets := 0
var flees := 0      # bolted from a running player (autotest)
var follows := 0    # dogs that set off after the player
var perf_us := 0
var perf_frames := 0
var cover_ms := 0.0
var spawn_ms := 0.0
## (autotest) split the cost of the fully updated animals: think / ground / animate us, count
var profile := false
var prof := PackedInt64Array([0, 0, 0, 0])

var _data := {}
var _rng := RandomNumberGenerator.new()
var _meshes := {}
var _mats := {}
var _alt_libs := {}
var _voices: Array[AudioStreamPlayer3D] = []
var _voice_t: Array[float] = []
var _streams := {}
var _crow: AudioStream
var _last_idx := {}
var _last_sound := -10.0
var _clock := 0.0
var _planes: Array = []
var _cover := {}
var _parcels: Array[Rect2] = []
var _taken: Array[Vector3] = []
var _trees := {}
var _rpts: Array = []       # river sample points (spawning)
var _edges := {}            # river point index * 2 + side -> the dry bank's first point
var _geoms := {}            # species|part -> merged geometry (shared by the colour variants)
var _doors := {}            # 8 m cell -> the doors in it (spawning)
var _hearts: Array[Sprite3D] = []
var _heart_tex: Texture2D
var _night := 0.0
var _wl := -0.3
var _half := 225.0
var _none := {}
var _ranges_done := false
var _frame := 0
var _live := false          # in play and outdoors (the player counts)
var _pp := Vector3.ZERO     # the player's position / ground velocity / speed this frame
var _pv := Vector3.ZERO
var _ps := 0.0
var _focus := Vector3.ZERO
var _scan_t := 0.0
var _near: Array[Animal] = []
var _far: Array[Animal] = []
var _pending: Array[Animal] = []
var _cursor := 0


func _ready() -> void:
	_rng.seed = SEED
	_wl = float(world.water_level)
	_half = float(world.world_size) * 0.5
	var f := FileAccess.open(DATA_PATH, FileAccess.READ)
	if f:
		var js = JSON.parse_string(f.get_as_text())
		if js is Dictionary:
			_data = (js as Dictionary).get("species", {})
	if _data.is_empty():
		push_warning("animals: %s is missing, no animals" % DATA_PATH)
		return
	_load_sounds()
	_index_world()
	var t0 := Time.get_ticks_usec()
	_spawn_all()
	spawn_ms = (Time.get_ticks_usec() - t0) / 1000.0
	GS.day_started.connect(_on_day_started)


# ------------------------------------------------------------------ world queries
func _index_world() -> void:
	var ph: Array = world.layout.get("parcel_half", [8.3, 4.8])
	for p in world.layout.get("parcels", []):
		var c: Array = p["center"]
		var hx := float(ph[0]) + 1.4
		var hz := float(ph[1]) + 1.4
		_parcels.append(Rect2(float(c[0]) - hx, float(c[1]) - hz, hx * 2.0, hz * 2.0))
	# how much undergrowth stands in each 4 m cell, from the layout's plant list (the same
	# on every renderer; roads, doors and yards are cleared in cover_at)
	var t0 := Time.get_ticks_usec()
	var ug: Dictionary = world.layout.get("undergrowth", {})
	for model in ug:
		var w: float = COVER_W.get(model, 0.0)
		if w <= 0.0:
			continue
		var arr: Array = ug[model]
		w /= 16.0
		for k in range(0, arr.size() - 4, 5):
			var key := Vector2i(floori(float(arr[k]) / 4.0), floori(float(arr[k + 2]) / 4.0))
			_cover[key] = float(_cover.get(key, 0.0)) + w
	cover_ms = (Time.get_ticks_usec() - t0) / 1000.0


func cover_at(x: float, z: float) -> float:
	## undergrowth density around (x, z) (plants-weight per m2; 0 on roads, sand and yards)
	var img: Image = world.data_img
	if img:
		var px := clampi(int((x + _half) / (_half * 2.0) * img.get_width()), 0, img.get_width() - 1)
		var pz := clampi(int((z + _half) / (_half * 2.0) * img.get_height()), 0, img.get_height() - 1)
		var d := img.get_pixel(px, pz)
		if d.b > 0.5 or d.g > 0.5:
			return 0.0   # road or sand (the beaches, the river banks)
	if world.plant_blocked(x, z):
		return 0.0
	return float(_cover.get(Vector2i(floori(x / 4.0), floori(z / 4.0)), 0.0))


func in_parcel(x: float, z: float) -> bool:
	for r in _parcels:
		if r.has_point(Vector2(x, z)):
			return true
	return false


func land_ok(x: float, z: float, pad: float, strict := true) -> bool:
	## dry ground clear of obstacles and bridge decks; strict: also off the farm parcels
	if x > INTERIOR_X - 30.0:
		return false
	var th: float = world.terrain_height(x, z)
	if th < _wl + 0.1:
		return false
	if not world.is_free(x, z, pad):
		return false
	if float(world.height_at(x, z)) > th + 0.05:
		return false   # under a bridge deck / the jetty
	if strict and in_parcel(x, z):
		return false
	return true


func water_ok(x: float, z: float, depth := 0.1) -> bool:
	## open water (not under a bridge deck)
	if x > INTERIOR_X - 30.0:
		return false
	var th: float = world.terrain_height(x, z)
	return th < _wl - depth and float(world.height_at(x, z)) < _wl


func _shallow(x: float, z: float) -> bool:
	if x > INTERIOR_X - 30.0:
		return false
	var th: float = world.terrain_height(x, z)
	return th > _wl - 0.35 and th < _wl + 0.12 and float(world.height_at(x, z)) < _wl + 0.12


func near_water(x: float, z: float, r: float) -> bool:
	for k in 8:
		var a := k * TAU / 8.0
		if water_ok(x + cos(a) * r, z + sin(a) * r, 0.02) or water_ok(x + cos(a) * r * 0.5, z + sin(a) * r * 0.5, 0.02):
			return true
	return false


func _ok(a: Animal, x: float, z: float, strict: bool) -> bool:
	match a.kind:
		Kind.DUCK:
			if water_ok(x, z, 0.08):
				return true
			return land_ok(x, z, a.pad, strict) and (not strict or near_water(x, z, 3.0))
		Kind.BUFFALO:
			return land_ok(x, z, a.pad, strict) or _shallow(x, z)
		Kind.FROG:
			return land_ok(x, z, a.pad, strict) and (not strict or near_water(x, z, 1.8))
	return land_ok(x, z, a.pad, strict)


func _path_ok(a: Animal, p: Vector3, q: Vector3, water_only := false) -> bool:
	var n := maxi(1, ceili(Vector2(q.x - p.x, q.z - p.z).length() / 0.5))
	for k in range(1, n + 1):
		var s := p.lerp(q, float(k) / n)
		if water_only:
			if not water_ok(s.x, s.z, 0.08):
				return false
		elif not _ok(a, s.x, s.z, false):
			return false
	return true


func _near_door(p: Vector3, r: float) -> bool:
	## (r <= 8 m: the doors are listed in an 8 m grid)
	if _doors.is_empty():
		for id in world.door_points:
			var d: Vector3 = world.door_points[id]
			var k := Vector2i(floori(d.x / 8.0), floori(d.z / 8.0))
			if not _doors.has(k):
				_doors[k] = PackedVector2Array()
			var list: PackedVector2Array = _doors[k]
			list.append(Vector2(d.x, d.z))
			_doors[k] = list
	var c := Vector2i(floori(p.x / 8.0), floori(p.z / 8.0))
	for i in range(-1, 2):
		for j in range(-1, 2):
			for d in _doors.get(c + Vector2i(i, j), PackedVector2Array()):
				if d.distance_to(Vector2(p.x, p.z)) < r:
					return true
	return false


func _spot_ok(p: Vector3, pad: float) -> bool:
	var sp: Array = world.layout.get("player_spawn", [0, 0])
	return Vector2(p.x - float(sp[0]), p.z - float(sp[1])).length() > 3.0 and land_ok(p.x, p.z, pad, true) \
		and not _near_door(p, 1.6)


func _tree_near(p: Vector3, r: float) -> bool:
	## a tree (whose crown would hide the herd) within r m
	if _trees.is_empty():
		for d in world.layout.get("decor", []):
			if str(d.get("model", "")) in ["tree_big", "coconut", "sawit_wild", "banana"]:
				var dp: Array = d["pos"]
				var k := Vector2i(floori(float(dp[0]) / 16.0), floori(float(dp[2]) / 16.0))
				if not _trees.has(k):
					_trees[k] = PackedVector2Array()
				var list: PackedVector2Array = _trees[k]
				list.append(Vector2(float(dp[0]), float(dp[2])))
				_trees[k] = list
	var c := Vector2i(floori(p.x / 16.0), floori(p.z / 16.0))
	var rr := ceili(r / 16.0)
	for i in range(-rr, rr + 1):
		for j in range(-rr, rr + 1):
			for t in _trees.get(c + Vector2i(i, j), PackedVector2Array()):
				if t.distance_to(Vector2(p.x, p.z)) < r:
					return true
	return false


func _crowded(p: Vector3, r: float) -> bool:
	for q in _taken:
		if Vector2(q.x - p.x, q.z - p.z).length() < r:
			return true
	return false


# ------------------------------------------------------------------ spawning
func _houses() -> Array:
	## [{id, door, out (unit, away from the house), right, village}] for every house
	var cent := {}
	for v in world.layout.get("villages", []):
		var c: Array = v["center"]
		cent[str(v["id"])] = Vector2(float(c[0]), float(c[1]))
	var out: Array = []
	for b in world.layout.get("buildings", []):
		var hid := str(b["id"])
		if not hid.begins_with("rumah") or not world.door_points.has(hid) or not world.building_nodes.has(hid):
			continue
		var n: Node3D = world.building_nodes[hid]
		var o := n.transform.basis.z
		o.y = 0.0
		o = o.normalized()
		var door: Vector3 = world.door_points[hid]
		var best := ""
		var bd := INF
		for vid in cent:
			var d: float = (cent[vid] as Vector2).distance_to(Vector2(door.x, door.z))
			if d < bd:
				bd = d
				best = vid
		out.append({"id": hid, "door": door, "out": o, "right": Vector3(o.z, 0.0, -o.x), "village": best})
	return out


func _village_center(vid: String) -> Vector3:
	for v in world.layout.get("villages", []):
		if str(v["id"]) == vid:
			var c: Array = v["center"]
			return Vector3(float(c[0]), 0.0, float(c[1]))
	return Vector3.ZERO


func _spawn_all() -> void:
	var houses := _houses()
	var by_v := {}
	for h in houses:
		if not by_v.has(h["village"]):
			by_v[h["village"]] = []
		by_v[h["village"]].append(h)
	var sp: Array = world.layout.get("player_spawn", [0, 0])
	var start := Vector3(float(sp[0]), 0.0, float(sp[1]))
	# --- chickens: the juragan's own flock in front of the player's house, one per hamlet
	var jh := []
	for h in houses:
		if h["id"] == "rumah_juragan":
			jh.append(h)
	for c in [["", jh, 3], ["sukamakmur", [], 3], ["seberang", [], 3], ["muara", [], 3], ["barat", [], 4], ["bukit", [], 3],
			["utara", [], 3], ["selatan", [], 3]]:
		var list: Array = c[1] if not (c[1] as Array).is_empty() else by_v.get(c[0], [])
		var y := _yard_spot(list, 2.4, 3.6, 0.5)
		if y != Vector3.INF:
			var vs := [1]
			for i in int(c[2]) - 1:
				vs.append([0, 0, 0, 2, 2, 3][_rng.randi() % 6])
			_group("ayam", y, 4.5, vs, 1.2)
	# --- cattle: a herd in the fields near the start, two more by the hamlets
	for c in [[start, 10.0, 34.0, [0, 1, 2]], [_village_center("selatan"), 14.0, 45.0, [2, 0, 0]],
			[_village_center("barat"), 14.0, 45.0, [0, 2, 1]]]:
		var h := _find_open(c[0], c[1], c[2], 2.5, 5.0)
		if h != Vector3.INF:
			_group("sapi", h, 7.0, c[3], 2.2)
	# --- buffalo on the river banks (they wade into the shallows)
	for c in [[_village_center("seberang"), 60.0, [0, 1]], [_village_center("barat"), 60.0, [1, 2]],
			[_village_center("muara"), 60.0, [0, 0]]]:
		var b := _find_bank(c[0], c[1], 2.2, 0.9, 24.0)
		if not b.is_empty():
			_group("kerbau", b[0], 6.0, c[2], 1.8)
	# --- goats by the yard fences
	for c in [["sukamakmur", [0, 1]], ["utara", [1, 0, 2]], ["selatan", [0, 2]], ["bukit", [2, 1]], ["muara", [1, 0]]]:
		var g := _find_fence_spot(_village_center(c[0]), 55.0)
		if g == Vector3.INF and by_v.has(c[0]):
			g = _yard_spot(by_v[c[0]], 2.5, 4.0, 0.7)
		if g != Vector3.INF:
			_group("kambing", g, 4.5, c[1], 1.4)
	# --- ducks on the rivers (the pond by the jetty, Muara, Dusun Barat)
	for c in [[Vector3(88, 0, 8), 30.0, [0, 0, 1]], [_village_center("muara"), 60.0, [0, 2, 0]],
			[_village_center("barat"), 60.0, [1, 0, 0]]]:
		var w := _find_water(c[0], c[1])
		if w != Vector3.INF:
			_group("bebek", w, 7.0, c[2], 1.0)
	# --- frogs on the banks: one out by day at each site, another comes out at night
	for c in [[Vector3(88, 0, 8), 35.0], [Vector3(80, 0, 30), 40.0], [_village_center("barat"), 60.0],
			[_village_center("muara"), 60.0], [_village_center("seberang"), 60.0]]:
		var b := _find_bank(c[0], c[1], 0.5, 0.15, 12.0)
		if not b.is_empty():
			var g := _group("kodok", b[0], 2.5, [_rng.randi() % 3, _rng.randi() % 3], 0.6)
			if g.size() > 1:
				(g[1] as Animal).night_only = true
				(g[1] as Animal).out = false
	# --- cats on the porches: Mak Inah's warung and four hamlets
	var cat_houses: Array = []
	if world.door_points.has("warung") and world.building_nodes.has("warung"):
		var n: Node3D = world.building_nodes["warung"]
		var o := n.transform.basis.z
		o.y = 0.0
		o = o.normalized()
		cat_houses.append({"id": "warung", "door": world.door_points["warung"], "out": o, "right": Vector3(o.z, 0, -o.x)})
	for vid in ["seberang", "selatan", "barat", "utara"]:
		var list: Array = by_v.get(vid, [])
		if not list.is_empty():
			cat_houses.append(list[_rng.randi() % list.size()])
	var ci := 0
	for h in cat_houses:
		var y := _yard_spot([h], 0.2, 2.2, 0.25, 2.2, 3.5)
		if y != Vector3.INF:
			_group("kucing", y, 4.5, [ci % 4], 0.0)
			ci += 1
	# --- kampung dogs
	for vid in ["sukamakmur", "seberang", "selatan", "bukit"]:
		var list: Array = by_v.get(vid, [])
		var y := _yard_spot(list, 2.6, 4.0, 0.6)
		if y != Vector3.INF:
			_group("anjing", y, 6.0, [[0, 3, 1, 2][counts.get("anjing", 0) % 4]], 0.0)
	for a in animals:
		a.last_t = -_rng.randf() * LOD_STEP


func _group(id: String, home: Vector3, radius: float, variants: Array, spread: float) -> Array:
	var g: Array = []
	_taken.append(home)
	for i in variants.size():
		var p := home
		if i > 0 or spread > 0.0:
			for k in 12:
				var a := _rng.randf() * TAU
				var r := spread * sqrt(_rng.randf()) if i > 0 else spread * 0.3 * _rng.randf()
				var q := home + Vector3(cos(a) * r, 0.0, sin(a) * r)
				var ok := water_ok(q.x, q.z, 0.2) if id == "bebek" else land_ok(q.x, q.z, 0.3, true)
				if ok:
					p = q
					break
		var an := _add(id, p, home, radius, int(variants[i]))
		if an:
			an.group = g
			g.append(an)
	return g


func _find_open(center: Vector3, rmin: float, rmax: float, pad: float, ring: float) -> Vector3:
	## an open, flat patch of land (a pasture) rmin..rmax m from center
	var best := Vector3.INF
	var bs := INF
	var step := 4.0
	var n := int(rmax / step)
	for i in range(-n, n + 1):
		for j in range(-n, n + 1):
			var p := center + Vector3(i * step, 0.0, j * step)
			var dd := Vector2(i, j).length() * step
			if dd < rmin or dd > rmax or _crowded(p, 20.0) or _tree_near(p, 8.0) or not _spot_ok(p, pad):
				continue
			var good := 0
			for k in 8:
				var a := k * TAU / 8.0
				if land_ok(p.x + cos(a) * ring, p.z + sin(a) * ring, 0.8, true):
					good += 1
			if good < 7:
				continue
			var h0: float = world.terrain_height(p.x, p.z)
			var slope := absf(float(world.terrain_height(p.x + 3.0, p.z)) - h0) + absf(float(world.terrain_height(p.x, p.z + 3.0)) - h0)
			var s := cover_at(p.x, p.z) * 0.8 + dd * 0.02 + slope * 2.0 + _rng.randf() * 0.8
			if s < bs:
				bs = s
				best = p
	return best


func _river_points(step: float) -> Array:
	## [centre, normal (unit, xz), half width] every `step` m along the rivers, away from their mouths
	if not _rpts.is_empty():
		return _rpts
	var out: Array = _rpts
	for rv in world.layout.get("rivers", []):
		var pts: Array = rv["pts"]
		var hw := float(rv.get("hw", 4.0))
		for k in pts.size() - 1:
			var a := Vector3(float(pts[k][0]), 0.0, float(pts[k][1]))
			var b := Vector3(float(pts[k + 1][0]), 0.0, float(pts[k + 1][1]))
			var dir := (b - a).normalized()
			var nrm := Vector3(-dir.z, 0.0, dir.x)
			var steps := maxi(1, int(a.distance_to(b) / step))
			for s in steps:
				var c := a.lerp(b, float(s) / steps)
				if absf(c.x) > _half - 30.0 or absf(c.z) > _half - 30.0:
					continue
				out.append([c, nrm, hw])
	return out


func _near_bridge(p: Vector3, r: float) -> bool:
	for br in world.bridges:
		if Vector2(float(br[0]) - p.x, float(br[1]) - p.z).length() < r:
			return true
	return false


func _find_bank(near: Vector3, maxd: float, off: float, pad: float, spacing: float) -> Array:
	## [a point `off` m up the bank from the water's edge, the direction to the water]
	var best: Array = []
	var bs := INF
	var pts := _river_points(4.0)
	for pi in pts.size():
		var rp: Array = pts[pi]
		var c: Vector3 = rp[0]
		var d := Vector2(c.x - near.x, c.z - near.z).length()
		if d > maxd or _near_bridge(c, 14.0):
			continue
		for si in 2:
			var n: Vector3 = rp[1] * (-1.0 if si == 0 else 1.0)
			var edge: Vector3 = _edges.get(pi * 2 + si, Vector3.ZERO)
			if edge == Vector3.ZERO:
				# walk out from the channel to the first dry ground (INF: none, or right away)
				edge = Vector3.INF
				var t := 1.0
				while t < float(rp[2]) + 8.0:
					var q := c + n * t
					if float(world.terrain_height(q.x, q.z)) > _wl + 0.03:
						edge = q
						break
					t += 0.4
				_edges[pi * 2 + si] = edge
			if edge == Vector3.INF:
				continue
			var p := edge + n * off
			if _crowded(p, spacing) or not water_ok(edge.x - n.x * 1.2, edge.z - n.z * 1.2, 0.1) or not _spot_ok(p, pad):
				continue
			var s := d * 0.05 + _rng.randf() * 1.5
			if s < bs:
				bs = s
				best = [p, -n]
	return best


func _find_water(near: Vector3, maxd: float) -> Vector3:
	## a spot of open water on a river (room to paddle around), away from the bridges
	var best := Vector3.INF
	var bs := INF
	for rp in _river_points(4.0):
		var c: Vector3 = rp[0]
		var d := Vector2(c.x - near.x, c.z - near.z).length()
		if d > maxd or _near_bridge(c, 16.0) or _crowded(c, 25.0):
			continue
		var n: Vector3 = rp[1]
		if not (water_ok(c.x, c.z, 0.3) and water_ok(c.x + n.x * 1.8, c.z + n.z * 1.8, 0.15)
				and water_ok(c.x - n.x * 1.8, c.z - n.z * 1.8, 0.15)):
			continue
		var s := d * 0.05 + _rng.randf() * 1.5
		if s < bs:
			bs = s
			best = c
	return best


func _find_fence_spot(center: Vector3, maxd: float) -> Vector3:
	## beside a yard fence of the village (a goat's favourite spot)
	var list: Array = []
	for f in world.layout.get("fences", []):
		var p: Array = f["pos"]
		var q := Vector3(float(p[0]), 0.0, float(p[2]))
		if Vector2(q.x - center.x, q.z - center.z).length() < maxd:
			list.append(f)
	var best := Vector3.INF
	var bs := INF
	for i in mini(14, list.size()):
		var f: Dictionary = list[_rng.randi() % list.size()]
		var p: Array = f["pos"]
		var q := Vector3(float(p[0]), 0.0, float(p[2]))
		var perp := Basis(Vector3.UP, deg_to_rad(float(f.get("rot", 0.0)))).z
		for side: float in [1.0, -1.0]:
			var g := q + perp * (2.2 * side)
			if _crowded(g, 14.0) or not _spot_ok(g, 0.7):
				continue
			var s := cover_at(g.x, g.z) + _rng.randf() * 0.15
			if s < bs:
				bs = s
				best = g
	return best


func _yard_spot(list: Array, dmin: float, dmax: float, pad: float, side_min := 0.0, crowd := 10.0) -> Vector3:
	## a spot in front of one of the houses (the yard or the village road): the barest of a
	## few, so the undergrowth does not hide a hen or a cat
	if list.is_empty():
		return Vector3.INF
	var best := Vector3.INF
	var bs := INF
	for i in 20:
		var h: Dictionary = list[_rng.randi() % list.size()]
		var side := _rng.randf_range(side_min, 2.8) * (1.0 if _rng.randf() < 0.5 else -1.0)
		var p: Vector3 = h["door"] + h["out"] * _rng.randf_range(dmin, dmax) + h["right"] * side
		if _crowded(p, crowd) or not _spot_ok(p, pad):
			continue
		var s := cover_at(p.x, p.z) + _rng.randf() * 0.15
		if s < bs:
			bs = s
			best = p
	return best


func _add(id: String, pos: Vector3, home: Vector3, radius: float, vi: int) -> Animal:
	var info: Dictionary = _data.get(id, {})
	if not ModelLib.has_model("animal_" + id):
		return null
	var cfg: Dictionary = B[id]
	var a := Animal.new()
	a.id = id
	a.idx = animals.size()
	a.cfg = cfg
	a.kind = {"bebek": Kind.DUCK, "kerbau": Kind.BUFFALO, "kodok": Kind.FROG}.get(id, Kind.LAND)
	var vs: Array = info.get("variants", [])
	vi = clampi(vi, 0, maxi(vs.size() - 1, 0))
	a.vi = vi
	a.variant = vs[vi] if vs.size() > 0 else {}
	a.rooster = bool(a.variant.get("rooster", false))
	a.display = str((VARIANT_LABEL.get(id, {}) as Dictionary).get(str(a.variant.get("name", "")), LABEL[id]))
	a.scale = float(cfg["scale"])
	a.height = float(info.get("height", 0.5)) * a.scale
	a.walk_v = float(info.get("walk_speed", 0.5)) * a.scale
	a.run_v = float(info.get("run_speed", a.walk_v * 2.5)) * a.scale
	a.cruise = a.walk_v * float(cfg["walk"])
	a.flee_speed = a.run_v * float(cfg["run"])
	a.turn = float(cfg["turn"])
	a.accel = float(cfg["accel"])
	a.body = float(cfg["body"])
	a.pad = float(cfg["pad"])
	a.flee_r = float(cfg["flee_r"])
	a.flee_v = float(cfg["flee_v"])
	a.look_r = float(cfg["look_r"])
	a.look_max = float(cfg["look_max"])
	a.small = bool(cfg["small"])
	a.db = float(cfg["db"])
	a.unit = float(cfg["unit"])
	a.maxd = float(cfg["maxd"])
	a.call_open = float(info.get("call_open", 0.3))
	a.tilt_len = float(info.get("length", 0.5)) * a.scale * 0.42 if a.kind != Kind.FROG else 0.0
	a.idle_rate = _rng.randf_range(0.85, 1.12)
	a.voice = _rng.randf_range(0.94, 1.07)
	if a.kind == Kind.FROG:
		a.hop_dist = float(info.get("hop_distance", 0.3)) * a.scale
		a.hop_time = float(info.get("hop_time", 0.6))
		a.air0 = float(info.get("hop_air_start", 0.167))
		a.air1 = float(info.get("hop_air_end", 0.417))
	a.home = home
	a.nest = pos
	a.radius = radius
	a.node = Node3D.new()
	a.node.name = "%s_%d" % [id, a.idx]
	a.node.visible = false      # drawn once its model is built (_scan, when it comes near)
	a.shown = false
	var bl: Vector2 = cfg["blob"]
	a.blob = GroundFx.blob(1.0, 0.4)
	a.blob.scale = Vector3(bl.x * 2.0, 1.0, bl.y * 2.0)
	a.node.add_child(a.blob)
	add_child(a.node)
	a.yaw = _rng.randf() * TAU
	a.node.position = Vector3(pos.x, world.height_at(pos.x, pos.z), pos.z)
	a.node.rotation.y = a.yaw
	if a.kind == Kind.DUCK and water_ok(pos.x, pos.z, 0.04):
		a.on_water = true
		a.node.position.y = _wl
		a.blob.visible = false
	a.call_t = _interval(a) * _rng.randf_range(0.2, 1.0)
	a.t = _rng.randf_range(0.5, 4.0)
	var an := a
	a.item = {"r": PET_RANGE, "animal": true, "pos": a.node.position, "_pos": a.node.position,
		"prompt": func(): return "Elus " + an.display, "act": func(): pet(an)}
	animals.append(a)
	counts[id] = int(counts.get(id, 0)) + 1
	return a


func _make_model(id: String, vi: int, info: Dictionary) -> Node3D:
	var s := ModelLib.scene("animal_" + id)
	if s == null:
		return null
	var m: Node3D = s.instantiate()
	var vs: Array = info.get("variants", [])
	var v: Dictionary = vs[clampi(vi, 0, vs.size() - 1)] if vs.size() > 0 else {}
	var cfg: Dictionary = B[id]
	for mi in ModelLib.find_meshes(m):
		if mi.mesh == null:
			continue
		mi.mesh = _merged(id, vi, String(mi.name), mi.mesh, v)
		var shadow := bool(cfg["shadow"]) and mi.name == "Body"
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadow else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.visibility_range_end = SHOW_RANGE + 12.0
	var r := m.find_child("Rooster", true, false) as Node3D
	if r:
		r.visible = bool(v.get("rooster", false))
	return m


func _albedo(mat: Material, v: Dictionary) -> Color:
	var nm := mat.resource_name if mat else ""
	if nm.begins_with("AnimalFur_") and v.has("fur"):
		return Color(str(v["fur"]))
	if nm.begins_with("AnimalMark2_") and v.has("mark2"):
		return Color(str(v["mark2"]))
	if nm.begins_with("AnimalMark_") and v.has("mark"):
		return Color(str(v["mark"]))
	if mat is BaseMaterial3D:
		return (mat as BaseMaterial3D).albedo_color
	return Color(0.8, 0.8, 0.8)


func _merged(id: String, vi: int, part: String, src: Mesh, v: Dictionary) -> ArrayMesh:
	## The model's surfaces merged into one: each material's colour (the variant's for the
	## coat and markings) is multiplied into the baked AO vertex colour, which the world
	## shader multiplies with its (now white) albedo. The colour is baked as authored (sRGB):
	## the renderer treats the vertex colour like the albedo uniform (verified side by side,
	## AnimalsCheck.merge_compare), and 8-bit sRGB keeps dark coats smooth. The geometry is
	## merged once per species; a colour variant only recomputes the colours.
	var key := "%s|%d|%s" % [id, vi, part]
	if _meshes.has(key):
		return _meshes[key]
	var g := _geometry(id + "|" + part, src)
	var ao: PackedColorArray = g["ao"]
	var ranges: Array = g["ranges"]
	var pc := PackedColorArray()
	pc.resize(ao.size())
	for r in ranges:
		var tint := _albedo(r[2], v)
		for i in range(int(r[0]), int(r[1])):
			var c := ao[i]
			pc[i] = Color(c.r * tint.r, c.g * tint.g, c.b * tint.b, c.a)
	var out: Array = (g["arrays"] as Array).duplicate()
	out[Mesh.ARRAY_COLOR] = pc
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, out, [], {}, int(g["flags"]))
	mesh.surface_set_material(0, _material(bool(B[id]["small"])))
	_meshes[key] = mesh
	return mesh


func _geometry(key: String, src: Mesh) -> Dictionary:
	## {arrays (colour slot empty), ao (the baked AO colours), ranges [[first, end, material]], flags}
	if _geoms.has(key):
		return _geoms[key]
	var pv := PackedVector3Array()
	var pn := PackedVector3Array()
	var ao := PackedColorArray()
	var pb := PackedInt32Array()
	var pw := PackedFloat32Array()
	var pi := PackedInt32Array()
	var ranges: Array = []
	var flags := 0
	for si in src.get_surface_count():
		var arr := src.surface_get_arrays(si)
		flags |= src.surface_get_format(si) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var base := pv.size()
		pv.append_array(verts)
		pn.append_array(arr[Mesh.ARRAY_NORMAL])
		var cols = arr[Mesh.ARRAY_COLOR]
		if cols is PackedColorArray and (cols as PackedColorArray).size() == verts.size():
			ao.append_array(cols)
		else:
			for i in verts.size():
				ao.append(Color.WHITE)
		pb.append_array(arr[Mesh.ARRAY_BONES])
		pw.append_array(arr[Mesh.ARRAY_WEIGHTS])
		var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
		if base == 0:
			pi.append_array(idx)
		else:
			for i in idx:
				pi.append(i + base)
		ranges.append([base, pv.size(), src.surface_get_material(si)])
	var out := []
	out.resize(Mesh.ARRAY_MAX)
	out[Mesh.ARRAY_VERTEX] = pv
	out[Mesh.ARRAY_NORMAL] = pn
	out[Mesh.ARRAY_BONES] = pb
	out[Mesh.ARRAY_WEIGHTS] = pw
	out[Mesh.ARRAY_INDEX] = pi
	var g := {"arrays": out, "ao": ao, "ranges": ranges, "flags": flags}
	_geoms[key] = g
	return g


func _material(small: bool) -> Material:
	## the toon material every animal shares (white albedo: the colour is in the vertices),
	## with the characters' rim light; the villager-sized ones (cattle, buffalo, goats) get
	## the characters' bold ink outline, the small ones the thinner one of the props (the
	## bold line swallowed a half-metre duck seen from the game camera)
	var key := "small" if small else "big"
	if not _mats.has(key):
		var src := StandardMaterial3D.new()
		src.resource_name = "AnimalMerged"
		src.albedo_color = Color.WHITE
		if small:
			_mats[key] = ModelLib.retuned(ModelLib.convert_material(src, false, 0.0), "animal_rim", {"rim_strength": RIM})
		else:
			_mats[key] = ModelLib.convert_material(src, false, RIM)
	return _mats[key]


func _setup_anim(a: Animal) -> void:
	a.ap = a.model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	a.skel = a.model.find_child("Skeleton3D", true, false) as Skeleton3D
	if a.ap == null or a.skel == null:
		return
	a.ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	# every clip keys the same bones (blender/animals.py): normalised cross-fades land
	# exactly on the new clip (see CharAnim._init_v2)
	a.ap.deterministic = false
	for n in a.ap.get_animation_list():
		var an := a.ap.get_animation(n)
		if n in LOOP_CLIPS:
			an.loop_mode = Animation.LOOP_LINEAR
		elif n in ONE_SHOT:
			an.loop_mode = Animation.LOOP_NONE
	# a second name for the one-shots, so a repeated call / hop cross-fades from its own pose
	if not _alt_libs.has(a.id):
		var lib := AnimationLibrary.new()
		for n in ONE_SHOT:
			if a.ap.has_animation(n):
				lib.add_animation(n, a.ap.get_animation(n))
		_alt_libs[a.id] = lib
	if not a.ap.has_animation_library("alt"):
		a.ap.add_animation_library("alt", _alt_libs[a.id])
	if a.ap.has_animation("call"):
		a.call_len = a.ap.get_animation("call").length
	var xf := Transform3D.IDENTITY
	var n: Node = a.skel
	while n != null and n != a.model:
		if n is Node3D:
			xf = (n as Node3D).transform * xf
		n = n.get_parent()
	a.sk_up = (xf.basis.inverse() * Vector3.UP).normalized()
	a.sk_fwd = (xf.basis.inverse() * Vector3.BACK).normalized()
	a.sk_right = a.sk_fwd.cross(a.sk_up).normalized()
	a.head = a.skel.find_bone("head")
	if a.look_max > 0.0:
		var shares := []
		if a.skel.find_bone("neck") >= 0:
			shares = [["neck", 0.4], ["head", 0.6]]
		elif a.skel.find_bone("neck_1") >= 0:
			shares = [["neck_1", 0.25], ["neck_2", 0.35], ["head", 0.4]]
		else:
			shares = [["head", 1.0]]
		for s in shares:
			var bi := a.skel.find_bone(s[0])
			if bi >= 0:
				a.look_bones.append(bi)
				a.look_w.append(float(s[1]))
				var par := a.skel.get_bone_parent(bi)
				var pb := a.skel.get_bone_global_rest(par).basis.orthonormalized() if par >= 0 else Basis.IDENTITY
				var inv := pb.inverse()
				a.look_up.append((inv * a.sk_up).normalized())
				a.look_right.append((inv * a.sk_right).normalized())
	if a.head >= 0:
		var hp := xf * a.skel.get_bone_global_rest(a.head).origin
		a.head_z = hp.z * a.scale
		a.head_y = hp.y * a.scale
	a.clip = "idle"
	a.ap.play("idle")
	a.ap.seek(randf() * a.ap.get_animation("idle").length, true)


# ------------------------------------------------------------------ sounds
func _load_sounds() -> void:
	for id in B:
		var list: Array[AudioStream] = []
		for i in range(1, 4):
			var path := "%s%s_%d.ogg" % [SND_DIR, id, i]
			if ResourceLoader.exists(path):
				var s: AudioStream = load(path)
				if s is AudioStreamOggVorbis:
					(s as AudioStreamOggVorbis).loop = false
				list.append(s)
		_streams[id] = list
	var cp := SND_DIR + "ayam_crow.ogg"
	if ResourceLoader.exists(cp):
		_crow = load(cp)
		if _crow is AudioStreamOggVorbis:
			(_crow as AudioStreamOggVorbis).loop = false
	var bus := "SFX" if AudioServer.get_bus_index("SFX") != -1 else "Master"
	for i in MAX_VOICES:
		var p := AudioStreamPlayer3D.new()
		p.bus = bus
		p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
		p.panning_strength = 0.7
		p.attenuation_filter_db = -12.0
		p.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
		add_child(p)
		_voices.append(p)
		_voice_t.append(-10.0)


func _hear() -> Vector3:
	var ins: String = world.inside
	if ins != "" and world.door_points.has(ins):
		return world.door_points[ins]
	return world.player.global_position


func _dawn() -> bool:
	return GS.hour < DAWN_END and _night < 0.5


func _interval(a: Animal) -> float:
	var c: Vector2 = a.cfg["call"]
	if a.kind == Kind.FROG:
		c = Vector2(2.5, 9.0) if _night > NIGHT_FROGS else c
	elif a.rooster and _dawn():
		c = Vector2(12.0, 30.0)
	return randf_range(c.x, c.y)


func _queue_sound(a: Animal, delay: float, force: bool, crow: bool) -> void:
	a.sound_in = maxf(delay, 0.0)
	a.sound_force = force
	a.sound_crow = crow


func _sound(a: Animal, force: bool) -> void:
	if world.state != "play" or not Sfx.sfx_on:
		return
	var crow := a.sound_crow and _crow != null
	var p := a.node.position
	var maxd := a.maxd * (1.3 if crow else 1.0)
	if _hear().distance_to(p) > maxd:
		return
	if not force and _clock - _last_sound < (0.35 if a.kind == Kind.FROG else 1.1):
		return
	var list: Array = _streams.get(a.id, [])
	if list.is_empty() and not crow:
		return
	var vi := -1
	for i in _voices.size():
		if not _voices[i].playing:
			vi = i
			break
	if vi < 0:
		if not force:
			return          # three at once is plenty
		vi = 0
		for i in _voices.size():
			if _voice_t[i] < _voice_t[vi]:
				vi = i
	var s: AudioStream = _crow
	if not crow:
		var k := randi() % list.size()
		if list.size() > 1 and k == int(_last_idx.get(a.id, -1)):
			k = (k + 1) % list.size()
		_last_idx[a.id] = k
		s = list[k]
	var v := _voices[vi]
	v.stop()
	v.stream = s
	v.global_position = p + Vector3(0, a.height * 0.8, 0)
	v.unit_size = a.unit * (1.4 if crow else 1.0)
	v.max_distance = maxd
	v.volume_db = a.db + (3.0 if crow else 0.0) + (INDOOR_DB if world.inside != "" else 0.0)
	v.pitch_scale = a.voice * randf_range(0.97, 1.03)
	v.play()
	_voice_t[vi] = _clock
	_last_sound = _clock
	sounds_played += 1
	last_sound = "ayam_crow" if crow else a.id


# ------------------------------------------------------------------ per frame
func _process(delta: float) -> void:
	if world == null or animals.is_empty():
		return
	var t0 := Time.get_ticks_usec()
	_clock += delta
	_frame += 1
	_night = float(world.night_k)
	if not _ranges_done and world.state == "play":
		# world.start_game's LOD pass set every small mesh to 75 m: back to ours
		_ranges_done = true
		for a in animals:
			if a.model:
				for mi in ModelLib.find_meshes(a.model):
					mi.visibility_range_end = SHOW_RANGE + 12.0
	# the player, once per frame (read by every animal's _react)
	var pl: Node3D = world.player
	_live = world.state == "play" and world.inside == ""
	_pp = pl.global_position
	var v: Vector3 = pl.get("velocity")
	_pv = Vector3(v.x, 0.0, v.z)
	_ps = _pv.length()
	var cam: Camera3D = world.camera
	_planes = cam.get_frustum() if cam and cam.is_inside_tree() else []
	_focus = world.cam_rig.global_position
	# who is near (and who is drawn at all) is sorted out 5x a second
	_scan_t -= delta
	if _scan_t <= 0.0:
		_scan_t = SCAN_STEP
		_scan()
	for a in _near:
		var p := a.node.position
		var full := a.shown and _in_view(p)
		a.in_view = full
		if not full:
			if _clock - a.last_t >= LOD_STEP:
				_lod(a)
			continue
		# on screen: every frame, or every other one beyond HALF_RATE m
		var dt := _clock - a.last_t
		if dt < delta * 1.5 and a.far and (_frame + a.idx) % 2 == 1:
			continue
		a.last_t = _clock
		if profile:
			var u0 := Time.get_ticks_usec()
			_think(a, dt)
			var u1 := Time.get_ticks_usec()
			_ground(a, true)
			var u2 := Time.get_ticks_usec()
			_animate(a, dt)
			var u3 := Time.get_ticks_usec()
			prof[0] += u1 - u0
			prof[1] += u2 - u1
			prof[2] += u3 - u2
			prof[3] += 1
			continue
		_think(a, dt)
		_ground(a, true)
		_animate(a, dt)
	# the far ones think in turn, each about every LOD_STEP s
	var n := _far.size()
	if n > 0:
		var k := mini(n, ceili(n * delta / LOD_STEP))
		for i in k:
			_cursor = (_cursor + 1) % n
			_lod(_far[_cursor])
	perf_us += Time.get_ticks_usec() - t0
	perf_frames += 1


func _lod(a: Animal) -> void:
	var dt := minf(_clock - a.last_t, 2.0)
	a.last_t = _clock
	a.in_view = false
	_think(a, dt)
	_ground(a, false)


func _scan() -> void:
	## visibility (with hysteresis) and the near / far lists, from the camera focus; the
	## models of animals coming near are built here, nearest first, BUILD_PER_SCAN at a time
	_near.clear()
	_far.clear()
	_pending.clear()
	for a in animals:
		var p := a.node.position
		var dx := p.x - _focus.x
		var dz := p.z - _focus.z
		var d2 := dx * dx + dz * dz
		a.d2 = d2
		var lim := SHOW_RANGE + (SHOW_MARGIN if a.shown else 0.0)
		var show := d2 < lim * lim
		if show and a.model == null and (not a.night_only or a.out or _night > NIGHT_FROGS):
			_pending.append(a)
			show = false
		if a.night_only:
			var want := _night > NIGHT_FROGS
			if want != a.out and (not a.in_view or not show):
				a.out = want
				if want:
					_reset(a)
					a.last_t = _clock
			if not a.out:
				a.in_view = false
				show = false
				if a.shown:
					a.shown = false
					a.node.visible = false
				continue
		if a.shown != show:
			a.shown = show
			a.node.visible = show
		a.far = d2 > HALF_RATE * HALF_RATE
		if show and d2 < FULL_RANGE * FULL_RANGE:
			_near.append(a)
		else:
			a.in_view = false
			_far.append(a)
	if not _pending.is_empty():
		_pending.sort_custom(func(x: Animal, y: Animal) -> bool: return x.d2 < y.d2)
		for i in mini(BUILD_PER_SCAN, _pending.size()):
			_build(_pending[i])


func _build(a: Animal) -> void:
	## the animal's model (merged mesh in its colours, animation player set up)
	var model := _make_model(a.id, a.vi, _data.get(a.id, {}))
	if model == null:
		return
	a.model = model
	model.scale = Vector3.ONE * a.scale
	model.rotation.x = a.tilt
	a.node.add_child(model)
	_setup_anim(a)


func _in_view(p: Vector3) -> bool:
	if _planes.is_empty():
		return true
	var q := Vector3(p.x, p.y + 0.4, p.z)
	for pl: Plane in _planes:
		if pl.distance_to(q) > VIEW_MARGIN:
			return false
	return true


func _think(a: Animal, dt: float) -> void:
	a.t -= dt
	a.call_t -= dt
	a.flee_cd -= dt
	a.follow_cd -= dt
	a.pet_cd -= dt
	if a.sound_in >= 0.0:
		a.sound_in -= dt
		if a.sound_in < 0.0:
			_sound(a, a.sound_force)
	var sleepy := _night > NIGHT_SLEEP and a.kind != Kind.FROG
	_react(a)
	match a.state:
		"walk", "home":
			if _step(a, dt, a.cruise):
				_arrived(a)
		"flee":
			if _step(a, dt, a.flee_speed):
				_arrived(a)
		"follow":
			_follow(a, dt)
		_:
			a.speed = move_toward(a.speed, 0.0, dt * 4.0)
			if a.look_on and (a.small or a.state == "pet") and a.state != "sit" and a.state != "eat":
				_turn_to(a, a.look_at, dt, 0.8)
			if a.t <= 0.0:
				_next(a)
	if sleepy and not (a.state in ["sleep", "home", "flee", "pet", "call"]):
		_go_home(a)
	elif not sleepy and a.state == "sleep":
		a.state = "idle"
		a.t = randf_range(0.5, 4.0)
	if a.call_t <= 0.0:
		_try_call(a)
	if a.node.rotation.y != a.yaw:
		a.node.rotation.y = a.yaw


func _turn_to(a: Animal, p: Vector3, dt: float, min_diff: float) -> void:
	var diff := wrapf(atan2(p.x - a.node.position.x, p.z - a.node.position.z) - a.yaw, -PI, PI)
	if absf(diff) > min_diff or (a.state == "pet" and absf(diff) > 0.2):
		var r := a.turn * 0.6 * dt
		a.yaw = wrapf(a.yaw + clampf(diff, -r, r), -PI, PI)


func _react(a: Animal) -> void:
	## the player: bolt when they run up, step aside when they bump in, dogs tag along,
	## everyone nearby watches them
	a.look_on = false
	if not _live or a.state == "pet":
		return
	var dx := a.node.position.x - _pp.x
	var dz := a.node.position.z - _pp.z
	var d2 := dx * dx + dz * dz
	if d2 > 81.0:
		return
	var d := sqrt(d2)
	if a.state != "flee" and a.state != "follow" and a.flee_cd <= 0.0:
		var bump := d < a.body + 0.45
		var toward := (_pv.x * dx + _pv.z * dz) / maxf(d, 0.01)
		if bump or (a.flee_r > 0.0 and d < a.flee_r and _ps > a.flee_v and toward > _ps * 0.45):
			_flee(a, _pp, not (a.flee_r > 0.0 and _ps > a.flee_v))
			return
	if a.id == "anjing" and a.follow_cd <= 0.0 and d < 7.0 and _ps > 1.0 and _night < NIGHT_SLEEP \
			and a.state in ["idle", "walk", "eat", "wag", "alert"]:
		a.state = "follow"
		follows += 1
		a.t = randf_range(8.0, 16.0)
		a.follow_cd = randf_range(40.0, 80.0)
		a.call_t = minf(a.call_t, randf_range(0.4, 1.5))   # a happy bark
		return
	if d < a.look_r and a.state != "sleep":
		a.look_on = true
		a.look_at = _pp + Vector3(0, 0.8, 0)


func _flee(a: Animal, from: Vector3, gentle: bool) -> void:
	var p := a.node.position
	var away := Vector3(p.x - from.x, 0.0, p.z - from.z)
	away = away.normalized() if away.length() > 0.05 else Vector3(sin(a.yaw), 0.0, cos(a.yaw))
	var dist: float = randf_range(1.0, 1.6) if gentle else float(a.cfg["flee_d"]) * randf_range(0.8, 1.3)
	var best := Vector3.INF
	for ang in [0.0, 0.5, -0.5, 1.0, -1.0, 1.6, -1.6, 2.2, -2.2]:
		var dir := away.rotated(Vector3.UP, float(ang) + randf_range(-0.25, 0.25))
		var q := p + dir * dist
		if _ok(a, q.x, q.z, false) and _path_ok(a, p, q):
			best = q
			break
	a.flee_cd = 2.0 if gentle else 3.0
	if best == Vector3.INF:
		return
	a.state = "flee" if not gentle else "walk"
	a.target = best
	a.stuck = 0.0
	if a.kind == Kind.FROG:
		a.hops = 5
	if gentle:
		return
	flees += 1
	a.speed = maxf(a.speed, a.flee_speed * 0.5)
	# a startled cluck / quack / bleat / meow now and then
	if a.id in ["ayam", "bebek", "kambing", "kucing"] and randf() < 0.55:
		_queue_sound(a, 0.05, false, false)
	# the flock scatters
	if a.id == "ayam" or a.id == "bebek":
		for o: Animal in a.group:
			if o != a and o.state != "flee" and o.node.position.distance_to(p) < 3.5:
				_flee(o, from, false)


func _follow(a: Animal, dt: float) -> void:
	## a dog trotting after the player for a while (at their heel when they stop)
	var pl: Node3D = world.player
	var pp := pl.global_position
	var f: Vector3 = pl.get("facing")
	var side := Vector3(-f.z, 0.0, f.x) * (0.8 if a.idx % 2 == 0 else -0.8)
	var goal := pp - f * 1.5 + side
	var v: Vector3 = pl.get("velocity")
	var ps := Vector2(v.x, v.z).length()
	var home_d := Vector2(a.node.position.x - a.home.x, a.node.position.z - a.home.z).length()
	if a.t <= 0.0 or home_d > 26.0 or world.state != "play" or world.inside != "" or _night > NIGHT_SLEEP:
		_go_back(a)
		return
	a.target = goal
	var d := Vector2(goal.x - a.node.position.x, goal.z - a.node.position.z).length()
	var want := clampf(maxf(ps * 0.95, (d - 0.3) * 1.8), 0.0, 3.9)
	if _move(a, dt, want) or a.speed < 0.05:
		_turn_to(a, pp, dt, 0.4)
	if a.stuck > 0.5:
		_go_back(a)
		return
	a.look_on = true
	a.look_at = pp + Vector3(0, 0.8, 0)


func _go_back(a: Animal) -> void:
	a.follow_cd = randf_range(40.0, 80.0)
	a.state = "walk"
	a.target = a.nest
	a.stuck = 0.0


func _go_home(a: Animal) -> void:
	var p := a.node.position
	if Vector2(p.x - a.nest.x, p.z - a.nest.z).length() < 0.8:
		a.state = "sleep"
		a.t = 1e6
		return
	a.state = "home"
	a.target = a.nest
	a.hops = 99
	a.stuck = 0.0


func _arrived(a: Animal) -> void:
	a.stuck = 0.0
	a.hops = 0
	match a.state:
		"home":
			if _night > NIGHT_SLEEP and a.kind != Kind.FROG:
				a.state = "sleep"
				a.t = 1e6
			else:
				a.state = "idle"
				a.t = randf_range(1.0, 3.0)
		"flee":
			a.state = "alert"
			a.t = randf_range(2.0, 4.5)
		_:
			if a.state == "walk" and randf() < 0.5 and not a.on_water:
				a.state = "eat"
				a.t = randf_range(float(a.cfg["t_eat"].x), float(a.cfg["t_eat"].y))
			else:
				a.state = "idle"
				a.t = randf_range(float(a.cfg["t_idle"].x), float(a.cfg["t_idle"].y)) * 0.6


func _next(a: Animal) -> void:
	if _night > NIGHT_SLEEP and a.kind != Kind.FROG:
		_go_home(a)
		return
	if a.state == "pet":
		match a.id:
			"anjing":
				a.state = "wag"
				a.t = randf_range(2.5, 4.0)
				a.follow_cd = minf(a.follow_cd, 0.0)
			"kucing":
				a.state = "sit"
				a.t = randf_range(6.0, 12.0)
			_:
				a.state = "idle"
				a.t = randf_range(2.0, 4.0)
		return
	# a duck on the bank goes back into the water before long
	if a.kind == Kind.DUCK and not a.on_water and randf() < 0.6 and _pick_target(a, "water"):
		a.state = "walk"
		return
	# too close to a flock mate: shuffle a step away
	for o: Animal in a.group:
		if o != a and o.node.position.distance_to(a.node.position) < (a.body + o.body) * 0.6 and _pick_target(a, ""):
			a.state = "walk"
			return
	var w: Dictionary = a.cfg["w"]
	if a.kind == Kind.FROG and _night > NIGHT_FROGS:
		w = FROG_NIGHT_W
	var total := 0.0
	for k in w:
		total += float(w[k])
	var r := randf() * total
	var pick := "idle"
	for k in w:
		r -= float(w[k])
		if r <= 0.0:
			pick = k
			break
	match pick:
		"walk":
			if _pick_target(a, ""):
				a.state = "walk"
				a.hops = randi_range(1, 4) if _night <= NIGHT_FROGS else randi_range(2, 6)
				return
		"eat":
			a.state = "eat"
			a.t = randf_range(float(a.cfg["t_eat"].x), float(a.cfg["t_eat"].y))
			return
		"sit":
			a.state = "sit"
			a.t = randf_range(8.0, 22.0)
			return
		"wag":
			a.state = "wag"
			a.t = randf_range(2.0, 4.0)
			return
	a.state = "idle"
	a.t = randf_range(float(a.cfg["t_idle"].x), float(a.cfg["t_idle"].y))


func _pick_target(a: Animal, mode: String) -> bool:
	## a reachable spot around home (small animals: the barest of a few, so the
	## undergrowth does not swallow them)
	var p := a.node.position
	var best := Vector3.INF
	var bs := INF
	var found := 0
	var water := false
	if a.kind == Kind.DUCK:
		water = mode == "water" or (mode == "" and (randf() < 0.8 or _night > NIGHT_SLEEP))
	for i in 10:
		var ang := randf() * TAU
		var r := sqrt(randf()) * a.radius
		var q := a.home + Vector3(cos(ang) * r, 0.0, sin(ang) * r)
		if Vector2(q.x - p.x, q.z - p.z).length() < (0.35 if a.kind == Kind.FROG else 0.9):
			continue
		if a.kind == Kind.DUCK:
			if water:
				if not water_ok(q.x, q.z, 0.15) or not _path_ok(a, p, q, a.on_water):
					continue
			elif not (land_ok(q.x, q.z, 0.3, true) and near_water(q.x, q.z, 2.5)) or not _path_ok(a, p, q):
				continue
		elif a.kind == Kind.BUFFALO and randf() < 0.3:
			if not _shallow(q.x, q.z) or not _path_ok(a, p, q):
				continue
		elif not _ok(a, q.x, q.z, true) or not _path_ok(a, p, q):
			continue
		var s := randf()
		if a.small and not water:
			s = cover_at(q.x, q.z) + randf() * 0.4
		if s < bs:
			bs = s
			best = q
		found += 1
		if not a.small or found >= 3:
			break
	if best == Vector3.INF:
		return false
	a.target = best
	a.stuck = 0.0
	return true


func _step(a: Animal, dt: float, spd: float) -> bool:
	if a.kind == Kind.FROG:
		return _hop(a, dt)
	if a.on_water:
		spd = minf(spd, 0.6 if a.state == "flee" else 0.3)
	return _move(a, dt, spd)


func _move(a: Animal, dt: float, spd: float) -> bool:
	## walk / run / swim toward a.target along a smooth curve; true when there (or stuck).
	## The way was checked when the target was picked; on the move the ground a little
	## ahead is checked every CHECK_STEP m (curves, flock mates, the player).
	var p := a.node.position
	var tx := a.target.x - p.x
	var tz := a.target.z - p.z
	var d := sqrt(tx * tx + tz * tz)
	var acc := a.accel * (2.0 if a.state == "flee" else 1.0)
	if d < 0.15 + a.speed * 0.3:
		a.speed = move_toward(a.speed, 0.0, dt * acc * 1.5)
		return true
	var diff := wrapf(atan2(tx, tz) - a.yaw, -PI, PI)
	var turn := a.turn * (1.6 if a.state == "flee" else 1.0)
	if a.on_water:
		turn = 1.0 if a.state != "flee" else 2.2
	a.yaw = wrapf(a.yaw + clampf(diff, -turn * dt, turn * dt), -PI, PI)
	var align := clampf(cos(diff), 0.0, 1.0)
	var want := minf(spd, 0.2 + d * 0.8) * lerpf(0.3, 1.0, align)
	a.speed = move_toward(a.speed, want, dt * acc)
	var fx := sin(a.yaw)
	var fz := cos(a.yaw)
	var push := _push(a)
	var sx := fx * a.speed * dt + push.x * dt
	var sz := fz * a.speed * dt + push.y * dt
	var step := sqrt(sx * sx + sz * sz)
	a.chk -= step
	if a.chk <= 0.0:
		var ahead := minf(0.3, d)
		if not _ok(a, p.x + sx, p.z + sz, false) or not _ok(a, p.x + sx + fx * ahead, p.z + sz + fz * ahead, false):
			a.speed = 0.0
			a.chk = 0.0
			a.stuck += dt
			return a.stuck > 0.7
		a.chk = CHECK_STEP
		a.stuck = 0.0
	a.node.position.x = p.x + sx
	a.node.position.z = p.z + sz
	a.odo += step
	return false


func _push(a: Animal) -> Vector2:
	## keep off the flock mates (and out of the player's way)
	var px := 0.0
	var pz := 0.0
	var p := a.node.position
	for o: Animal in a.group:
		if o == a:
			continue
		var dx := p.x - o.node.position.x
		var dz := p.z - o.node.position.z
		var r := (a.body + o.body) * 0.85
		var dd := dx * dx + dz * dz
		if dd < r * r and dd > 0.0001:
			var d := sqrt(dd)
			var k := (r - d) / d * 1.5
			px += dx * k
			pz += dz * k
	return Vector2(px, pz)


func _hop(a: Animal, dt: float) -> bool:
	## frogs get about in hops: the clip hops in place, the node moves during its air time
	if a.hop_t >= 0.0:
		a.hop_t += dt * a.hop_rate
		var k := clampf((a.hop_t - a.air0) / maxf(a.air1 - a.air0, 0.01), 0.0, 1.0)
		var np := a.hop_from + a.hop_dir * (a.hop_len * k)
		a.odo += Vector2(np.x - a.node.position.x, np.z - a.node.position.z).length()
		a.node.position.x = np.x
		a.node.position.z = np.z
		if a.hop_t >= a.hop_time:
			a.hop_t = -1.0
			a.hop_wait = randf_range(0.02, 0.1) if a.state == "flee" else randf_range(0.15, 0.7)
		return false
	a.hop_wait -= dt
	var p := a.node.position
	var tx := a.target.x - p.x
	var tz := a.target.z - p.z
	var d := sqrt(tx * tx + tz * tz)
	if a.hops <= 0 or d < 0.12:
		return true
	var diff := wrapf(atan2(tx, tz) - a.yaw, -PI, PI)
	a.yaw = wrapf(a.yaw + clampf(diff, -a.turn * dt, a.turn * dt), -PI, PI)
	if a.hop_wait > 0.0 or absf(diff) > 0.35:
		return false
	var len := minf(a.hop_dist, d)
	var dir := Vector3(sin(a.yaw), 0.0, cos(a.yaw))
	var q := p + dir * len
	if not _ok(a, q.x, q.z, false) or not _ok(a, p.x + dir.x * len * 0.5, p.z + dir.z * len * 0.5, false):
		a.hops = 0
		return true
	a.hop_t = 0.0
	a.hop_from = p
	a.hop_dir = dir
	a.hop_len = len
	a.hops -= 1
	a.new_hop = true
	a.hop_rate = 1.35 if a.state == "flee" else 1.0
	return false


func _try_call(a: Animal) -> void:
	a.call_t = _interval(a)
	if a.state in ["flee", "pet", "call", "follow", "home"] or (a.state == "sleep" and a.kind != Kind.FROG):
		return
	if world.ui and world.ui.is_blocking():
		return
	if a.state == "walk" and not a.on_water:
		a.call_t = randf_range(2.0, 6.0)   # finish the walk first
		return
	_start_call(a, false)


func _start_call(a: Animal, force: bool) -> void:
	var crow := a.rooster and (_dawn() or randf() < 0.25)
	if a.kind == Kind.DUCK and a.on_water:
		_queue_sound(a, 0.0, force, false)   # a quack while paddling on
		return
	a.state = "call"
	a.speed = 0.0
	a.hop_t = -1.0
	a.hops = 0
	_once(a, "call", 0.2)
	a.t = a.call_len + 0.05
	_queue_sound(a, a.call_open, force, crow)


func pet(a: Animal) -> void:
	## "Elus": it looks up at the player, makes its sound, and a heart pops up
	if a.pet_cd > 0.0:
		return
	a.pet_cd = 1.0
	pets += 1
	var pl: Node3D = world.player
	if pl.has_method("face_point"):
		pl.call("face_point", a.node.position, 0.6)
	_heart(a)
	a.flee_cd = 3.0
	a.call_t = _interval(a)
	if a.kind == Kind.DUCK and a.on_water:
		_queue_sound(a, 0.05, true, false)
		return
	a.state = "pet"
	a.speed = 0.0
	a.hop_t = -1.0
	a.hops = 0
	a.look_on = true
	a.look_at = pl.global_position + Vector3(0, 0.8, 0)
	_once(a, "call", 0.18)
	a.t = a.call_len + 0.3
	_queue_sound(a, a.call_open, true, a.rooster and randf() < 0.5)


func pet_target() -> Dictionary:
	## the animal the player faces within reach (world.gd, when nothing else is), or {}
	if world.inside != "" or world.player == null:
		return _none
	var pl: Node3D = world.player
	var pp := pl.global_position
	var f: Vector3 = pl.get("facing")
	var best: Animal = null
	var bs := INF
	for a in _near:   # (all within FULL_RANGE of the camera focus, which follows the player)
		if not a.shown:
			continue
		var dx := a.node.position.x - pp.x
		var dz := a.node.position.z - pp.z
		var reach := PET_RANGE + a.body
		var dd := dx * dx + dz * dz
		if dd > reach * reach:
			continue
		var d := sqrt(dd)
		var dot := (dx * f.x + dz * f.z) / maxf(d, 0.01)
		if dot < 0.25 and d > a.body + 0.35:
			continue
		var s := d - a.body - dot * 0.9
		if s < bs:
			bs = s
			best = a
	if best == null:
		return _none
	best.item["pos"] = best.node.position
	best.item["_pos"] = best.node.position
	return best.item


func _on_day_started(_report: Array) -> void:
	for a in animals:
		_reset(a)


func _reset(a: Animal) -> void:
	a.node.position = Vector3(a.nest.x, world.height_at(a.nest.x, a.nest.z), a.nest.z)
	a.state = "idle"
	a.t = randf_range(0.5, 3.0)
	a.speed = 0.0
	a.hop_t = -1.0
	a.hops = 0
	a.stuck = 0.0
	a.sound_in = -1.0
	a.follow_cd = randf_range(5.0, 20.0)
	a.gx = INF
	_ground(a, false)


# ------------------------------------------------------------------ pose
func _ground(a: Animal, full: bool) -> void:
	## stand on the terrain (swimming ducks on the water), tilted with the slope; the
	## ground is sampled again only after the animal moved
	var p := a.node.position
	if absf(p.x - a.gx) < 0.004 and absf(p.z - a.gz) < 0.004 and absf(a.yaw - a.gyaw) < 0.01:
		if a.on_water and full:
			a.node.position.y = _wl + 0.012 * sin(_clock * 2.2 + a.idx)
		return
	a.gx = p.x
	a.gz = p.z
	a.gyaw = a.yaw
	var th: float = world.terrain_height(p.x, p.z)
	var water := a.kind == Kind.DUCK and th < _wl - 0.04
	if water != a.on_water:
		a.on_water = water
		a.blob.visible = not water
	if water:
		a.node.position.y = _wl + 0.012 * sin(_clock * 2.2 + a.idx)
		return
	a.node.position.y = th
	if full and a.tilt_len > 0.0:
		var fx := sin(a.yaw) * a.tilt_len
		var fz := cos(a.yaw) * a.tilt_len
		var hf: float = world.terrain_height(p.x + fx, p.z + fz)
		var hb: float = world.terrain_height(p.x - fx, p.z - fz)
		var want := clampf(atan2(hb - hf, 2.0 * a.tilt_len), -0.3, 0.3)
		if absf(want - a.tilt) > 0.004:
			a.tilt = lerpf(a.tilt, want, 0.3)
			a.model.rotation.x = a.tilt


func _clip(a: Animal, name: String, rate: float, blend := 0.25) -> void:
	a.rate = rate
	if a.clip == name or not a.ap.has_animation(name):
		return
	var phase := -1.0
	if (a.clip == "walk" or a.clip == "run") and (name == "walk" or name == "run") and a.ap.current_animation_length > 0.0:
		phase = fposmod(a.ap.current_animation_position / a.ap.current_animation_length, 1.0)
	a.ap.play(name, blend)
	var len := a.ap.get_animation(name).length
	if phase >= 0.0:
		a.ap.seek(phase * len, false)
	elif name in RANDOM_START:
		a.ap.seek(randf() * len, false)
	a.clip = name


func _once(a: Animal, name: String, blend: float) -> void:
	## (re)start a one-shot clip, cross-faded from whatever plays now
	if a.ap == null or not a.ap.has_animation(name):
		return
	a.alt = not a.alt
	var nm := ("alt/" + name) if a.alt else name
	a.ap.play(nm, blend)
	a.ap.seek(0.0, false)
	a.clip = name
	a.rate = 1.0


func _animate(a: Animal, dt: float) -> void:
	if a.ap == null:
		return
	var name := ""
	var rate := a.idle_rate
	var blend := 0.25
	if a.kind == Kind.FROG and (a.new_hop or a.hop_t >= 0.0):
		if a.new_hop or a.clip != "hop":
			_once(a, "hop", 0.06)
			if not a.new_hop:
				a.ap.seek(a.hop_t, false)
			a.new_hop = false
		a.rate = a.hop_rate
	elif a.state == "call" or a.state == "pet":
		pass   # the one-shot started by _start_call / pet
	elif a.speed > 0.04 and a.kind != Kind.FROG:
		if a.on_water:
			name = "swim"
			rate = clampf(0.7 + a.speed * 3.0, 0.7, 2.4)
		else:
			if a.run_clip:
				a.run_clip = a.speed > a.run_v * 0.6
			else:
				a.run_clip = a.speed > a.walk_v * 1.8
			name = "run" if a.run_clip else "walk"
			rate = clampf(a.speed / (a.run_v if a.run_clip else a.walk_v), 0.4, 2.4)
			blend = 0.2
	else:
		match a.state:
			"eat":
				name = "swim" if a.on_water else "eat"
				rate = 0.5 if a.on_water else a.idle_rate
			"sit":
				name = "sit"
			"wag":
				name = "wag"
			"follow":
				name = "wag"
			"sleep":
				name = "sit" if a.id == "kucing" else ("swim" if a.on_water else "idle")
				rate = 0.4
			_:
				name = "swim" if a.on_water else "idle"
				rate = 0.45 if a.on_water else a.idle_rate
		if name != "" and not a.ap.has_animation(name):
			name = "idle"
	if name != "":
		_clip(a, name, rate, blend)
	# (every clip keys every bone, so each advance rewrites the whole pose, the head look
	# layered on last time included: no reset needed)
	a.ap.advance(minf(dt, 0.25) * a.rate)
	_look(a, dt)


func _look(a: Animal, dt: float) -> void:
	## turn the head (neck + head bones) toward what it watches, on top of the clip (about
	## axes taken from the rest pose: no skeleton pose queries per frame)
	if a.look_bones.is_empty():
		return
	var want_yaw := 0.0
	var want_pitch := 0.0
	if a.look_on and a.state != "eat" and a.state != "sleep":
		var fx := sin(a.yaw)
		var fz := cos(a.yaw)
		var hx := a.node.position.x + fx * a.head_z
		var hz := a.node.position.z + fz * a.head_z
		var dx := a.look_at.x - hx
		var dz := a.look_at.z - hz
		var yaw := wrapf(atan2(dx, dz) - a.yaw, -PI, PI)
		if absf(yaw) < 2.2:
			want_yaw = clampf(yaw, -a.look_max, a.look_max)
			want_pitch = clampf(atan2(a.look_at.y - a.node.position.y - a.head_y, sqrt(dx * dx + dz * dz)), -0.35, 0.3)
	var k := clampf(dt * 4.0, 0.0, 1.0)
	a.look_yaw = lerpf(a.look_yaw, want_yaw, k)
	a.look_pitch = lerpf(a.look_pitch, want_pitch, k)
	if absf(a.look_yaw) < 0.002 and absf(a.look_pitch) < 0.002:
		return
	for i in a.look_bones.size():
		var bi := a.look_bones[i]
		var w := a.look_w[i]
		var q := Quaternion(a.look_up[i], a.look_yaw * w) * Quaternion(a.look_right[i], a.look_pitch * w)
		a.skel.set_bone_pose_rotation(bi, q * a.skel.get_bone_pose_rotation(bi))


# ------------------------------------------------------------------ heart emote
func _heart(a: Animal) -> void:
	if _heart_tex == null:
		_heart_tex = _make_heart()
	var s: Sprite3D = null
	for h in _hearts:
		if not h.visible:
			s = h
			break
	if s == null:
		if _hearts.size() < 4:
			s = Sprite3D.new()
			s.texture = _heart_tex
			s.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			s.no_depth_test = true
			s.shaded = false
			s.double_sided = true
			s.pixel_size = 0.0068
			s.render_priority = 10
			s.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
			s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(s)
			_hearts.append(s)
		else:
			s = _hearts[0]
	if s.has_meta("tw"):
		var old = s.get_meta("tw")
		if old is Tween and (old as Tween).is_valid():
			(old as Tween).kill()
	var top := a.node.position + Vector3(0, a.height + 0.28, 0)
	s.position = top
	s.scale = Vector3.ONE * 0.2
	s.modulate = Color(1, 1, 1, 1)
	s.visible = true
	var tw := create_tween()
	tw.tween_property(s, "scale", Vector3.ONE * 1.15, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(s, "scale", Vector3.ONE, 0.12)
	tw.parallel().tween_property(s, "position:y", top.y + 0.55, 1.3).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_SINE)
	tw.tween_property(s, "modulate:a", 0.0, 0.3)
	tw.tween_callback(s.hide)
	s.set_meta("tw", tw)


static func _heart_f(x: float, y: float) -> float:
	var q := x * x + y * y - 1.0
	return q * q * q - x * x * y * y * y


func _make_heart() -> Texture2D:
	## a plump red heart with a cream rim and a highlight, anti-aliased (3x3 samples)
	var n := 64
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	var red := Color("e8506a")
	var cream := Color("fdf3dc")
	var shine := Color("ff9fb0")
	for py in n:
		for px in n:
			var c_out := 0.0
			var c_in := 0.0
			var c_hi := 0.0
			for sy in 3:
				for sx in 3:
					var x := ((px + (sx + 0.5) / 3.0) / n - 0.5) * 2.75
					var y := -((py + (sy + 0.5) / 3.0) / n - 0.5) * 2.75 + 0.12
					if _heart_f(x / 1.2, y / 1.2) <= 0.0:
						c_out += 1.0
					if _heart_f(x, y) <= 0.0:
						c_in += 1.0
						if (x + 0.45) * (x + 0.45) + (y - 0.42) * (y - 0.42) < 0.06:
							c_hi += 1.0
			if c_out <= 0.0:
				img.set_pixel(px, py, Color(cream.r, cream.g, cream.b, 0.0))
				continue
			var col := red.lerp(shine, c_hi / maxf(c_in, 1.0))
			col = cream.lerp(col, c_in / c_out)
			col.a = c_out / 9.0
			img.set_pixel(px, py, col)
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _exit_tree() -> void:
	# the flocks list their members and the pet prompts capture their animal: break the
	# cycles, and stop the streams (see Sfx._exit_tree)
	for a in animals:
		a.group = []
		a.item = {}
	animals.clear()
	for v in _voices:
		v.stop()
		v.stream = null
	_streams.clear()
	_crow = null


# ------------------------------------------------------------------ debug / autotest
func find(id: String) -> Array:
	var out: Array = []
	for a in animals:
		if a.id == id:
			out.append(a)
	return out


func perf_ms() -> float:
	return perf_us / 1000.0 / maxf(perf_frames, 1)
