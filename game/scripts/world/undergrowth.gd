class_name Undergrowth
extends Node3D
## Dense small plants (ferns, keladi, shrubs, grass clumps, flowers, fallen
## fronds, logs, pebbles) from layout.json "undergrowth" ({model: [x, y, z,
## rot_deg, scale, ...]}), drawn as MultiMeshes chunked on a 24 m grid so the
## renderer can frustum-cull them. Instances are shuffled inside each chunk so
## the "Hemat baterai" quality can simply show the first half of every chunk.

const CHUNK := 24.0
## v1 models used when a v2 asset has not been exported (model, scale factor)
const FALLBACK := {
	"grass_a": ["grass_tuft", 1.2], "grass_b": ["grass_tuft", 1.5], "flowers_white": ["flowers", 1.0],
	"flowers_yellow": ["flowers", 1.0], "shrub_a": ["bush_a", 0.65], "shrub_b": ["bush_b", 0.65],
	"fern_a": ["bush_b", 0.45], "fern_b": ["bush_a", 0.42], "keladi": ["banana", 0.3],
	"frond_fallen": ["", 0.0], "vine_log": ["stump", 0.8], "pile_fronds": ["", 0.0], "rock_a": ["rock_a", 1.0],
}
## the larger plants keep their shadows, everything else is shadowless
const SHADOW_MODELS := ["shrub_a", "shrub_b"]
## the smallest plants are dropped a little earlier when far from the camera
const SMALL_MODELS := ["grass_a", "grass_b", "flowers_white", "flowers_yellow", "rock_a", "frond_fallen"]

var mmis: Array[MultiMeshInstance3D] = []
var total := 0
var density := 1.0


func build(data: Dictionary, is_blocked: Callable) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7331
	for model in data:
		var arr: Array = data[model]
		var mesh_name: String = model
		var sfac := 1.0
		if not ModelLib.has_model(model):
			var fb: Array = FALLBACK.get(model, ["", 0.0])
			mesh_name = fb[0]
			sfac = fb[1]
			if mesh_name == "" or not ModelLib.has_model(mesh_name):
				continue
		var mesh := ModelLib.merged_mesh(mesh_name, true)
		if mesh.get_surface_count() == 0:
			continue
		var chunks := {}
		for k in range(0, arr.size() - 4, 5):
			var x: float = arr[k]
			var z: float = arr[k + 2]
			if is_blocked.call(x, z):
				continue
			var key := Vector2i(floori(x / CHUNK), floori(z / CHUNK))
			if not chunks.has(key):
				chunks[key] = []
			var s: float = float(arr[k + 4]) * sfac
			var basis := Basis(Vector3.UP, deg_to_rad(float(arr[k + 3]))).scaled(Vector3(s, s * rng.randf_range(0.9, 1.1), s))
			var b := rng.randf_range(0.84, 1.0)
			var tint := Color(b * rng.randf_range(0.93, 1.0), b, b * rng.randf_range(0.86, 1.0))
			chunks[key].append([Transform3D(basis, Vector3(x, float(arr[k + 1]), z)), tint])
		for key in chunks:
			var list: Array = chunks[key]
			# Fisher-Yates with our own rng so the order is deterministic
			for i in range(list.size() - 1, 0, -1):
				var j := rng.randi_range(0, i)
				var tmp = list[i]
				list[i] = list[j]
				list[j] = tmp
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.use_colors = true
			mm.mesh = mesh
			mm.instance_count = list.size()
			for i in list.size():
				mm.set_instance_transform(i, list[i][0])
				mm.set_instance_color(i, list[i][1])
			var mmi := MultiMeshInstance3D.new()
			mmi.name = "%s_%d_%d" % [model, key.x, key.y]
			mmi.multimesh = mm
			mmi.set_meta("model", model)
			if not model in SHADOW_MODELS:
				mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mmi.visibility_range_end = 44.0 if model in SMALL_MODELS else 60.0
			mmi.visibility_range_end_margin = 4.0
			add_child(mmi)
			mmis.append(mmi)
			total += list.size()
	set_density(density)


func set_density(f: float) -> void:
	## 1.0 = everything, 0.5 = "Hemat baterai" (every chunk shows its first half).
	density = f
	for mmi in mmis:
		var mm := mmi.multimesh
		mm.visible_instance_count = mm.instance_count if f >= 0.999 else int(ceil(mm.instance_count * f))


func set_shadows(on: bool) -> void:
	for mmi in mmis:
		if mmi.get_meta("model", "") in SHADOW_MODELS:
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if on else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
