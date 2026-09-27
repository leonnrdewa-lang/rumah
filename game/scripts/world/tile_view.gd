class_name TileView
extends Node3D
## Visual for one planting spot of a parcel: garden scrub, tilled soil, or an
## oil palm at growth stage 0–3 (with fruit bunches when ready to harvest).

const GARDEN := ["banana", "bush_a", "bush_b", "bush_a", "flowers", "bush_b"]
const SOIL_COLOR := Color("745d48")

static var _soil_mesh: Mesh
static var _soil_mat: Material

var pid := 0
var idx := 0
var _shown := ""
var _plant: Node3D
var _fruit: MeshInstance3D
var _soil: MeshInstance3D
var _yaw := 0.0
var _scale := 1.0


func _ready() -> void:
	var h := hash(pid * 131 + idx * 7)
	_yaw = float(h % 360) * PI / 180.0
	_scale = 0.9 + float((h / 7) % 100) / 500.0
	if _soil_mesh == null:
		var c := CylinderMesh.new()
		c.top_radius = 0.82
		c.bottom_radius = 1.0
		c.height = 0.1
		c.radial_segments = 14
		c.rings = 1
		_soil_mesh = c
		var m := ShaderMaterial.new()
		m.shader = ModelLib.WORLD_SHADER
		m.set_shader_parameter("albedo", SOIL_COLOR)
		m.set_shader_parameter("noise_tex", ModelLib.NOISE_TEX)
		m.set_shader_parameter("tint_strength", 0.35)
		m.set_shader_parameter("fade_enabled", 0.0)
		_soil_mat = m
	_soil = MeshInstance3D.new()
	_soil.mesh = _soil_mesh
	_soil.material_override = _soil_mat
	_soil.position.y = 0.0
	_soil.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_soil)
	refresh()


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
		_soil.visible = t["s"] != "bush"
		match t["s"]:
			"bush":
				var model: String = GARDEN[(pid * 5 + idx * 3) % GARDEN.size()]
				_plant = _mesh_node(model, "", "")
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
