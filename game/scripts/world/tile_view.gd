class_name TileView
extends Node3D
## Visual for one planting spot of a parcel: a lush villager garden (until it is
## cleared), cleared ground with the piringan mulch circle, or an oil palm at
## growth stage 0–3 (with fruit bunches when ready to harvest).
##
## The garden plants and piringan decals of a whole parcel are batched into a few
## MultiMeshes (one per model) that are rebuilt whenever a tile changes, so a
## parcel costs a handful of draw calls instead of dozens.

## garden cluster = one main plant + small plants around it
const GARDEN_MAIN := ["shrub_a", "banana", "shrub_b", "keladi", "shrub_a", "banana", "keladi", "shrub_b"]
const GARDEN_SMALL := ["fern_a", "fern_b", "grass_a", "grass_b", "flowers_white", "flowers_yellow", "keladi", "fern_a"]
const SHADOW_MODELS := ["shrub_a", "shrub_b", "banana", "keladi", "bush_a", "bush_b"]
## piringan scale (model is 2.4 m across): empty tile, palm stage 0..3
const PIRINGAN_SCALE := [0.58, 0.62, 0.7, 0.76, 0.8]

static var _tiles := {}     # pid -> {idx: TileView}
static var _batches := {}   # pid -> Node3D holding the parcel's MultiMeshes
static var _dirty := {}     # pid -> true while a rebuild is queued

var pid := 0
var idx := 0
var _shown := ""
var _plant: Node3D
var _fruit: MeshInstance3D
var _yaw := 0.0
var _scale := 1.0


func _ready() -> void:
	var h := hash(pid * 131 + idx * 7)
	_yaw = float(h % 360) * PI / 180.0
	_scale = 0.9 + float((h / 7) % 100) / 500.0
	if not _tiles.has(pid):
		_tiles[pid] = {}
	_tiles[pid][idx] = self
	refresh()


func _exit_tree() -> void:
	if _tiles.has(pid) and _tiles[pid].get(idx) == self:
		_tiles[pid].erase(idx)


func refresh() -> void:
	var p: Dictionary = GS.parcels[pid]
	var t: Dictionary = p["tiles"][idx]
	var key := "%s%d" % [t["s"], t["st"]]
	if key != _shown:
		_shown = key
		if _plant:
			_plant.queue_free()
			_plant = null
			_fruit = null
		match t["s"]:
			"bush":
				pass  # drawn by the parcel batch
			"empty":
				_plant = _mesh_node("stump", "", "") if (idx + pid) % 3 == 0 else null
			"palm":
				var name := "sawit_%d" % int(t["st"])
				_plant = _mesh_node(name, "", "Fruits")
				if int(t["st"]) == 3:
					_fruit = MeshInstance3D.new()
					_fruit.mesh = ModelLib.merged_mesh("sawit_3", true, "Fruits", "")
					_plant.add_child(_fruit)
		if _plant:
			_plant.rotation.y = _yaw
			_plant.scale = Vector3.ONE * _scale
			add_child(_plant)
		_queue_batch()
	if _fruit:
		_fruit.visible = bool(t["fr"])


func _mesh_node(model: String, only: String, exclude: String) -> Node3D:
	var n := Node3D.new()
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLib.merged_mesh(model, true, only, exclude)
	n.add_child(mi)
	return n


func pop() -> void:
	# a small squash-and-stretch when the tile changes
	var tw := create_tween()
	scale = Vector3(1.15, 0.8, 1.15)
	tw.tween_property(self, "scale", Vector3.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


# ------------------------------------------------------------------ parcel batch
func _queue_batch() -> void:
	if _dirty.get(pid, false):
		return
	_dirty[pid] = true
	call_deferred("_flush_batch")


func _flush_batch() -> void:
	if not _dirty.get(pid, false):
		return
	_dirty[pid] = false
	var batch: Node3D = _batches.get(pid)
	if batch == null or not is_instance_valid(batch):
		batch = Node3D.new()
		batch.name = "ParcelDecor%d" % pid
		get_parent().add_child(batch)
		_batches[pid] = batch
	for c in batch.get_children():
		c.queue_free()
	var lists := {}   # model -> [[Transform3D, Color]]
	var tiles: Array = GS.parcels[pid]["tiles"]
	for i in _tiles.get(pid, {}):
		var tv: TileView = _tiles[pid][i]
		if not is_instance_valid(tv):
			continue
		var t: Dictionary = tiles[i]
		if t["s"] == "bush":
			_garden(tv, lists)
		else:
			# the weeded circle grows with the palm: a small soft patch on a cleared tile or
			# around a seedling (the v2 1.0-2.1 m brown discs read as stickers on the lawn),
			# ~1.9 m across under a grown palm
			var s: float = PIRINGAN_SCALE[0] if t["s"] == "empty" else PIRINGAN_SCALE[clampi(int(t["st"]), 0, 3) + 1]
			_add(lists, "piringan", Transform3D(Basis(Vector3.UP, tv._yaw).scaled(Vector3(s, 1.0, s)), tv.position + Vector3(0, 0.015, 0)), Color.WHITE)
	for model in lists:
		var list: Array = lists[model]
		var mesh: Mesh
		var sfac := 1.0
		if model == "piringan" and not ModelLib.has_model("piringan"):
			mesh = GroundFx.soil_mesh()
		else:
			var mname: String = model
			if not ModelLib.has_model(mname):
				var fb: Array = Undergrowth.FALLBACK.get(mname, ["", 0.0])
				mname = fb[0]
				sfac = fb[1]
				if mname == "" or not ModelLib.has_model(mname):
					continue
			mesh = ModelLib.merged_mesh(mname, true)
		if mesh == null or mesh.get_surface_count() == 0:
			continue
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = mesh
		mm.instance_count = list.size()
		for k in list.size():
			var xf: Transform3D = list[k][0]
			if sfac != 1.0:
				xf.basis = xf.basis.scaled(Vector3.ONE * sfac)
			mm.set_instance_transform(k, xf)
			mm.set_instance_color(k, list[k][1])
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		if not model in SHADOW_MODELS:
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if model == "piringan" and ModelLib.has_model("piringan"):
			var pm := GroundFx.piringan_material()
			if pm:
				mmi.material_override = pm
		batch.add_child(mmi)


static func _add(lists: Dictionary, model: String, xf: Transform3D, col: Color) -> void:
	if not lists.has(model):
		lists[model] = []
	lists[model].append([xf, col])


static func _garden(tv: TileView, lists: Dictionary) -> void:
	## A villager's garden patch: one main plant with ferns, grass and flowers around it.
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(tv.pid * 131 + tv.idx * 7 + 3)
	var main: String = GARDEN_MAIN[(tv.pid * 5 + tv.idx * 3) % GARDEN_MAIN.size()]
	var p := tv.position
	var off := Vector3(rng.randf_range(-0.25, 0.25), 0, rng.randf_range(-0.25, 0.25))
	var s := rng.randf_range(0.95, 1.2)
	_add(lists, main, Transform3D(Basis(Vector3.UP, tv._yaw).scaled(Vector3.ONE * s), p + off), _tint(rng))
	var n := rng.randi_range(4, 6)
	for k in n:
		var a := TAU * (float(k) + rng.randf_range(-0.3, 0.3)) / float(n)
		var r := rng.randf_range(0.7, 1.35)
		var m: String = GARDEN_SMALL[rng.randi_range(0, GARDEN_SMALL.size() - 1)]
		var sc := rng.randf_range(0.8, 1.2)
		var pos := p + Vector3(cos(a) * r, 0, sin(a) * r)
		_add(lists, m, Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * sc), pos), _tint(rng))


static func _tint(rng: RandomNumberGenerator) -> Color:
	var b := rng.randf_range(0.86, 1.0)
	return Color(b * rng.randf_range(0.94, 1.0), b, b * rng.randf_range(0.88, 1.0))
