class_name Undergrowth
extends Node3D
## Dense small plants (ferns, keladi, shrubs, grass clumps, flowers, fallen
## fronds, logs, pebbles) from layout.json "undergrowth" ({model: [x, y, z,
## rot_deg, scale, ...]}).
##
## Drawing: ONE MultiMesh per model that only holds the plants under the camera's
## view. The plants are pre-packed into 4 m cells (MultiMesh buffer slices); when the
## view's ground footprint leaves the area built last time, the cells around it are
## concatenated into the MultiMesh buffers again (a few native array appends, ~every
## 3 m of walking). Compared with 16 m chunks, which drew ~3000 m2 of plants for the
## ~600 m2 of ground on screen, this draws ~4x fewer instances (measured at the busiest
## spot: 28 draw calls with shadows instead of 68), which pays for a ~2x denser carpet.
##
## Instances are shuffled inside each cell so the "Hemat baterai" quality can simply
## take the first part of every cell.
const CELL := 4.0
const STRIDE := 16          # floats per instance: 3x4 transform + colour
const MARGIN := 3.0         # built area = view footprint + this (m)
## a camera higher than this (the title fly-over, 25 m up) sees ~3x the gameplay ground
## area with every plant a few pixels big: it gets FAR_DENSITY of every cell (fix round:
## a third was not enough; sampled over the whole title orbit it peaked at 452k tris)
const FAR_HEIGHT := 21.0
const FAR_DENSITY := 0.3
## ... and the modelled plants (ferns, shrubs, keladi: 200-320 tris, ~10% of the plants
## but ~75% of the undergrowth triangles) only FAR_DENSITY * FAR_HEAVY
const FAR_HEAVY := 0.5
const HEAVY_TRIS := 100
## v1 models used when a v2 asset has not been exported (model, scale factor)
const FALLBACK := {
	"grass_a": ["grass_tuft", 1.2], "grass_b": ["grass_tuft", 1.5], "flowers_white": ["flowers", 1.0],
	"flowers_yellow": ["flowers", 1.0], "shrub_a": ["bush_a", 0.65], "shrub_b": ["bush_b", 0.65],
	"fern_a": ["bush_b", 0.45], "fern_b": ["bush_a", 0.42], "keladi": ["banana", 0.3],
	"frond_fallen": ["", 0.0], "vine_log": ["stump", 0.8], "pile_fronds": ["", 0.0], "rock_a": ["rock_a", 1.0],
}
## cheap ground-cover plants built here from the fern / leaf textures (~14-24 tris,
## a tenth of a modelled fern): they make up the carpet between the thickets
const PROCEDURAL := ["fern_low", "leaf_low"]
## the larger plants keep their shadows, everything else is shadowless
const SHADOW_MODELS := ["shrub_a", "shrub_b"]
## only plants tall enough to hide the player take part in the see-through hole
const FADE_MODELS := ["shrub_a", "shrub_b", "keladi", "pile_fronds"]

var mmis: Array[MultiMeshInstance3D] = []
var total := 0
var density := 1.0
var _cells: Array[Dictionary] = []    # per MultiMesh: Vector2i -> PackedFloat32Array
var _heavy: Array[bool] = []          # per MultiMesh: a modelled plant (> HEAVY_TRIS)
var _built := Rect2()
var _dirty := true
var _far := false
static var _proc_meshes := {}


func build(data: Dictionary, is_blocked: Callable) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7331
	for model in data:
		var arr: Array = data[model]
		var sfac := 1.0
		var mesh: Mesh
		if model in PROCEDURAL:
			mesh = procedural_mesh(model)
		else:
			var mesh_name: String = model
			if not ModelLib.has_model(model):
				var fb: Array = FALLBACK.get(model, ["", 0.0])
				mesh_name = fb[0]
				sfac = fb[1]
				if mesh_name == "" or not ModelLib.has_model(mesh_name):
					continue
			mesh = ModelLib.merged_mesh(mesh_name, model in FADE_MODELS)
		if mesh == null or mesh.get_surface_count() == 0:
			continue
		var cells := {}
		for k in range(0, arr.size() - 4, 5):
			var x: float = arr[k]
			var z: float = arr[k + 2]
			if is_blocked.call(x, z):
				continue
			var key := Vector2i(floori(x / CELL), floori(z / CELL))
			if not cells.has(key):
				cells[key] = []
			var s: float = float(arr[k + 4]) * sfac
			# soft patches (~15-30 m) where the plants run a little bigger and yellower or
			# smaller and bluer, so the rosettes do not repeat evenly across a field
			var pa := 0.5 + 0.5 * sin(x * 0.21 + 1.7 * sin(z * 0.15)) * cos(z * 0.18 - 0.9 * sin(x * 0.11))
			var pb := 0.5 + 0.5 * sin(z * 0.17 + 1.3 * cos(x * 0.13) + 2.0)
			s *= lerpf(0.86, 1.12, pb)
			var basis := Basis(Vector3.UP, deg_to_rad(float(arr[k + 3]))).scaled(Vector3(s, s * rng.randf_range(0.9, 1.1), s))
			var b := rng.randf_range(0.86, 1.0) * lerpf(0.96, 1.05, pa)
			var tint := Color(b * rng.randf_range(0.93, 1.0) * lerpf(0.93, 1.04, pa), b,
				b * rng.randf_range(0.88, 1.0) * lerpf(0.98, 0.84, pa))
			cells[key].append([Transform3D(basis, Vector3(x, float(arr[k + 1]), z)), tint])
		# pack: one scratch MultiMesh with every instance, cell after cell (each cell
		# shuffled with our own rng so the order is deterministic), then slice its buffer
		var n := 0
		for key in cells:
			n += cells[key].size()
		if n == 0:
			continue
		var tmp := MultiMesh.new()
		tmp.transform_format = MultiMesh.TRANSFORM_3D
		tmp.use_colors = true
		tmp.instance_count = n
		var ranges := {}
		var i := 0
		for key in cells:
			var list: Array = cells[key]
			for a in range(list.size() - 1, 0, -1):
				var j := rng.randi_range(0, a)
				var t = list[a]
				list[a] = list[j]
				list[j] = t
			ranges[key] = Vector2i(i, list.size())
			for it in list:
				tmp.set_instance_transform(i, it[0])
				tmp.set_instance_color(i, it[1])
				i += 1
		var buf := tmp.buffer
		var packed := {}
		for key in ranges:
			var r: Vector2i = ranges[key]
			packed[key] = buf.slice(r.x * STRIDE, (r.x + r.y) * STRIDE)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = mesh
		var mmi := MultiMeshInstance3D.new()
		mmi.name = model
		mmi.multimesh = mm
		mmi.set_meta("model", model)
		if not model in SHADOW_MODELS:
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mmi)
		mmis.append(mmi)
		_cells.append(packed)
		var tris := 0
		var am := mesh as ArrayMesh
		for si in mesh.get_surface_count():
			if am:
				var idx: int = am.surface_get_array_index_len(si)
				tris += (idx if idx > 0 else am.surface_get_array_len(si)) / 3
		_heavy.append(tris > HEAVY_TRIS)
		total += n
	_dirty = true


func set_density(f: float) -> void:
	## 1.0 = everything, 0.5 = "Hemat baterai" (every cell shows its first half).
	density = f
	_dirty = true


func set_shadows(on: bool) -> void:
	for mmi in mmis:
		if mmi.get_meta("model", "") in SHADOW_MODELS:
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if on else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _process(_delta: float) -> void:
	var cam := get_viewport().get_camera_3d()
	if cam == null or not is_visible_in_tree():
		return
	var far := cam.global_position.y > FAR_HEIGHT
	if far != _far:
		_far = far
		_dirty = true
	var fp := _footprint(cam)
	if _dirty or not _built.encloses(fp):
		_rebuild(fp.grow(MARGIN))


func _footprint(cam: Camera3D) -> Rect2:
	## ground area (xz) seen by the camera: the screen corners cast onto y = 0, grown
	## a little for plant height and the ground's gentle relief
	var vp := get_viewport().get_visible_rect().size
	var r := Rect2()
	var first := true
	for c in [Vector2.ZERO, Vector2(vp.x, 0), Vector2(0, vp.y), vp, Vector2(vp.x * 0.5, 0)]:
		var o := cam.project_ray_origin(c)
		var d := cam.project_ray_normal(c)
		var t := 90.0
		if d.y < -0.02:
			t = minf((-0.3 - o.y) / d.y, 90.0)
		var p := o + d * t
		var q := Vector2(p.x, p.z)
		if first:
			r = Rect2(q, Vector2.ZERO)
			first = false
		else:
			r = r.expand(q)
	return r.grow(1.0)


func _rebuild(area: Rect2) -> void:
	_dirty = false
	_built = area
	var c0 := Vector2i(floori(area.position.x / CELL), floori(area.position.y / CELL))
	var c1 := Vector2i(floori(area.end.x / CELL), floori(area.end.y / CELL))
	var aabb := AABB(Vector3(area.position.x, -2.0, area.position.y), Vector3(area.size.x, 7.0, area.size.y))
	for m in mmis.size():
		var dens := density
		if _far:
			dens *= FAR_DENSITY * (FAR_HEAVY if _heavy[m] else 1.0)
		var cells: Dictionary = _cells[m]
		var out := PackedFloat32Array()
		for cz in range(c0.y, c1.y + 1):
			for cx in range(c0.x, c1.x + 1):
				var key := Vector2i(cx, cz)
				if not cells.has(key):
					continue
				var arr: PackedFloat32Array = cells[key]
				if dens >= 0.999:
					out.append_array(arr)
				else:
					# round up or down by a fixed per-cell dither, so thin densities keep
					# their average (ceil kept >= 1 plant of every model in every cell)
					var want := float(arr.size() / STRIDE) * dens
					var cnt := int(want)
					if float(absi(hash(key) + m * 7919) % 1000) * 0.001 < want - float(cnt):
						cnt += 1
					out.append_array(arr.slice(0, cnt * STRIDE))
		var n := out.size() / STRIDE
		var mm := mmis[m].multimesh
		# grow-only capacity: no GPU buffer reallocation while walking around
		if n > mm.instance_count:
			mm.instance_count = n + n / 3 + 8
		mm.visible_instance_count = n
		if mm.instance_count > 0:
			out.resize(mm.instance_count * STRIDE)
			mm.buffer = out
		mmis[m].custom_aabb = aabb


# ------------------------------------------------------------------ procedural cover plants
static func procedural_mesh(model: String) -> ArrayMesh:
	if _proc_meshes.has(model):
		return _proc_meshes[model]
	var mesh := ArrayMesh.new()
	match model:
		"fern_low":
			var tex := _texture_of("fern_a")
			if tex:
				_fern_rosette(mesh, tex)
		"leaf_low":
			var tex := _texture_of("keladi")
			if tex:
				_leaf_rosette(mesh, tex)
	_proc_meshes[model] = mesh
	return mesh


static func _texture_of(model: String) -> Texture2D:
	## the albedo texture of a model's first textured material (imported with mipmaps)
	var s := ModelLib.scene(model)
	if s == null:
		return null
	var root := s.instantiate()
	var tex: Texture2D = null
	for mi in ModelLib.find_meshes(root):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i) as BaseMaterial3D
			if m and m.albedo_texture and tex == null:
				tex = m.albedo_texture
	root.free()
	return tex


static func _cover_material(mat_name: String, tex: Texture2D) -> Material:
	var sm := StandardMaterial3D.new()
	sm.resource_name = mat_name
	sm.albedo_texture = tex
	sm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	sm.alpha_scissor_threshold = 0.5
	sm.cull_mode = BaseMaterial3D.CULL_DISABLED
	return ModelLib.convert_material(sm, false)


static func _fern_rosette(mesh: ArrayMesh, tex: Texture2D) -> void:
	## 7 arching fern fronds (fern.png: one frond, stem at the bottom), 2 segments each:
	## 28 triangles for a ~1.2 m wide plant. The fronds are deliberately uneven (short
	## and long, low and raised, bunched to one side) so the randomly rotated copies do
	## not read as the same regular star (fix round review: "rosettes repeat visibly")
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	var u0 := 22.0 / 256.0
	var u1 := 241.0 / 256.0
	var n := 7
	for k in n:
		var a := TAU * (float(k) + rng.randf_range(-0.34, 0.34)) / float(n) * 0.92
		var dir := Vector3(cos(a), 0, sin(a))
		var side := Vector3(-dir.z, 0, dir.x)
		var ln := rng.randf_range(0.36, 0.7)
		var hw := ln * 0.215
		var rise := rng.randf_range(0.14, 0.36)
		# [distance out, height, v, AO]
		var secs := [[0.03, 0.03, 1.0, 0.62], [ln * 0.5, rise, 0.5, 0.9], [ln, rise * 0.45, 0.0, 1.0]]
		var pts := []
		for sc in secs:
			var c: Vector3 = dir * float(sc[0]) + Vector3(0, float(sc[1]), 0)
			# the frond's edges droop a little below its rib
			var droop := Vector3(0, -hw * 0.25, 0)
			pts.append([c - side * hw + droop, c + side * hw + droop, float(sc[2]), float(sc[3])])
		for sgi in 2:
			var p: Array = pts[sgi]
			var q: Array = pts[sgi + 1]
			var e0: Vector3 = q[0] - p[0]
			var e1: Vector3 = p[1] - p[0]
			var nrm := e0.cross(e1).normalized()
			if nrm.y < 0.0:
				nrm = -nrm
			nrm = (nrm + Vector3.UP).normalized()
			var quad := [[p[0], Vector2(u0, p[2]), p[3]], [p[1], Vector2(u1, p[2]), p[3]],
				[q[1], Vector2(u1, q[2]), q[3]], [q[0], Vector2(u0, q[2]), q[3]]]
			for idx in [0, 1, 2, 0, 2, 3]:
				var v: Array = quad[idx]
				st.set_color(Color(v[2], v[2], v[2]))
				st.set_normal(nrm)
				st.set_uv(v[1])
				st.add_vertex(v[0])
	st.set_material(_cover_material("M_FernLow", tex))
	st.commit(mesh)


static func _leaf_rosette(mesh: ArrayMesh, tex: Texture2D) -> void:
	## a low broad-leaf clump: 7 pointed leaves (leaves.png, bottom-left sprite, stem
	## down) splayed around the centre, 2 of them more upright: 14 triangles
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rng := RandomNumberGenerator.new()
	rng.seed = 23
	var uv0 := Vector2(67.0, 270.0) / 512.0
	var uv1 := Vector2(189.0, 505.0) / 512.0
	var n := 7
	for k in n:
		var a := TAU * (float(k) + rng.randf_range(-0.25, 0.25)) / float(n)
		var dir := Vector3(cos(a), 0, sin(a))
		var side := Vector3(-dir.z, 0, dir.x)
		var upright := k >= n - 2
		var ln := rng.randf_range(0.26, 0.36) * (1.15 if upright else 1.0)
		var hw := ln * 0.26
		var tilt := deg_to_rad(rng.randf_range(55.0, 70.0) if upright else rng.randf_range(18.0, 34.0))
		var base := dir * 0.03 + Vector3(0, 0.02, 0)
		var tip := base + (dir * cos(tilt) + Vector3.UP * sin(tilt)) * ln
		var nrm := (tip - base).cross(side).normalized()
		if nrm.y < 0.0:
			nrm = -nrm
		nrm = (nrm + Vector3.UP * 0.6).normalized()
		var quad := [[base - side * hw, Vector2(uv0.x, uv1.y), 0.62], [base + side * hw, Vector2(uv1.x, uv1.y), 0.62],
			[tip + side * hw, Vector2(uv1.x, uv0.y), 1.0], [tip - side * hw, Vector2(uv0.x, uv0.y), 1.0]]
		for idx in [0, 1, 2, 0, 2, 3]:
			var v: Array = quad[idx]
			st.set_color(Color(v[2], v[2], v[2]))
			st.set_normal(nrm)
			st.set_uv(v[1])
			st.add_vertex(v[0])
	st.set_material(_cover_material("M_PlantLeafLow", tex))
	st.commit(mesh)
