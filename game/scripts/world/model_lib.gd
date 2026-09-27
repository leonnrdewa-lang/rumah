class_name ModelLib
extends RefCounted
## Loads the Blender-made GLB models, swaps their imported materials for the
## game's stylised shaders and builds merged meshes for MultiMesh decoration.

const WORLD_SHADER := preload("res://shaders/world.gdshader")
const FOLIAGE_SHADER := preload("res://shaders/foliage.gdshader")
const NOISE_TEX := preload("res://assets/textures/noise.png")
const FOLIAGE_WORDS := ["Frond", "Leaf", "Leaves", "Grass", "Foliage", "Canopy", "Bush", "Fern", "Petal", "Flower", "Plant"]
const GLOW_WORDS := ["Glass", "Lamp", "Window", "Bulb"]

static var _scenes := {}
static var _label_font: FontVariation


static func label_font() -> FontVariation:
	if _label_font == null:
		_label_font = FontVariation.new()
		_label_font.base_font = load("res://assets/fonts/Fredoka.ttf")
		_label_font.variation_opentype = {"wght": 650}
	return _label_font
static var _materials := {}
static var _merged := {}


static func has_model(name: String) -> bool:
	return ResourceLoader.exists("res://assets/models/%s.glb" % name)


static func scene(name: String) -> PackedScene:
	if not _scenes.has(name):
		var path := "res://assets/models/%s.glb" % name
		_scenes[name] = load(path) if ResourceLoader.exists(path) else null
	return _scenes[name]


static func instance(name: String, fade := true) -> Node3D:
	var s := scene(name)
	if s == null:
		return _placeholder(name)
	var n: Node3D = s.instantiate()
	stylize(n, fade)
	return n


static func _placeholder(name: String) -> Node3D:
	var mi := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = Vector3(1, 1, 1)
	mi.mesh = b
	mi.position.y = 0.5
	var root := Node3D.new()
	root.name = name
	root.add_child(mi)
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(1, 0, 1)
	mi.material_override = m
	return root


static func stylize(root: Node, fade := true) -> void:
	for mi in find_meshes(root):
		if mi.mesh == null:
			continue
		for i in mi.mesh.get_surface_count():
			mi.set_surface_override_material(i, convert_material(mi.mesh.surface_get_material(i), fade))


static func find_meshes(root: Node) -> Array[MeshInstance3D]:
	var out: Array[MeshInstance3D] = []
	if root is MeshInstance3D:
		out.append(root)
	for c in root.get_children():
		out.append_array(find_meshes(c))
	return out


static func is_foliage(mat_name: String) -> bool:
	for w in FOLIAGE_WORDS:
		if mat_name.findn(w) >= 0:
			return true
	return false


static func convert_material(m: Material, fade := true) -> Material:
	var mname := m.resource_name if m else ""
	var col := Color(0.8, 0.8, 0.8)
	if m is BaseMaterial3D:
		col = (m as BaseMaterial3D).albedo_color
	var key := "%s|%s|%s" % [mname, col.to_html(), fade]
	if _materials.has(key):
		return _materials[key]
	var sm := ShaderMaterial.new()
	sm.resource_name = mname
	if is_foliage(mname):
		sm.shader = FOLIAGE_SHADER
		var sway := 1.0
		var base := 0.4
		if mname.findn("Frond") >= 0:
			base = 1.0
		elif mname.findn("Grass") >= 0 or mname.findn("Flower") >= 0 or mname.findn("Petal") >= 0:
			sway = 2.5
			base = 0.0
		elif mname.findn("Bush") >= 0:
			sway = 0.6
			base = 0.2
		elif mname.findn("Canopy") >= 0:
			sway = 0.35
			base = 2.0
		sm.set_shader_parameter("sway", sway)
		sm.set_shader_parameter("sway_base", base)
	else:
		sm.shader = WORLD_SHADER
		for w in GLOW_WORDS:
			if mname.findn(w) >= 0:
				sm.set_shader_parameter("emission_color", Color(1.0, 0.78, 0.4))
				sm.set_shader_parameter("night_emission", 1.0)
	sm.set_shader_parameter("albedo", col)
	sm.set_shader_parameter("noise_tex", NOISE_TEX)
	sm.set_shader_parameter("fade_enabled", 1.0 if fade else 0.0)
	_materials[key] = sm
	return sm


static func _rel_xform(node: Node, root: Node) -> Transform3D:
	var t := Transform3D.IDENTITY
	var n := node
	while n != null and n != root:
		if n is Node3D:
			t = (n as Node3D).transform * t
		n = n.get_parent()
	return t


static func _under(node: Node, root: Node, ancestor_name: String) -> bool:
	var n := node
	while n != null and n != root:
		if n.name == ancestor_name:
			return true
		n = n.get_parent()
	return false


static func merged_mesh(name: String, fade := true, only_under := "", exclude_under := "") -> ArrayMesh:
	## All meshes of a model merged into one ArrayMesh (one surface per material).
	var key := "%s|%s|%s|%s" % [name, fade, only_under, exclude_under]
	if _merged.has(key):
		return _merged[key]
	var s := scene(name)
	var mesh := ArrayMesh.new()
	if s == null:
		push_warning("missing model: " + name)
		_merged[key] = mesh
		return mesh
	var root := s.instantiate()
	var tools := {}
	var mats := {}
	for mi in find_meshes(root):
		if mi.mesh == null:
			continue
		if only_under != "" and not _under(mi, root, only_under):
			continue
		if exclude_under != "" and _under(mi, root, exclude_under):
			continue
		var xf := _rel_xform(mi, root)
		for i in mi.mesh.get_surface_count():
			var m: Material = mi.mesh.surface_get_material(i)
			var mk := m.resource_name if m else "none"
			if m is BaseMaterial3D:
				mk += (m as BaseMaterial3D).albedo_color.to_html()
			if not tools.has(mk):
				var st := SurfaceTool.new()
				st.begin(Mesh.PRIMITIVE_TRIANGLES)
				tools[mk] = st
				mats[mk] = m
			(tools[mk] as SurfaceTool).append_from(mi.mesh, i, xf)
	for mk in tools:
		var st: SurfaceTool = tools[mk]
		st.set_material(convert_material(mats[mk], fade))
		st.commit(mesh)
	root.free()
	_merged[key] = mesh
	return mesh


static func mesh_aabb(name: String) -> AABB:
	return merged_mesh(name).get_aabb()
