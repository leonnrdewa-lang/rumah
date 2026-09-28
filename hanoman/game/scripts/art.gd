class_name Art
extends RefCounted
## Model loading and the painted look: every imported GLB material is swapped for
## the toon shader (reading the original base colour) plus an ink-outline pass.
## Materials named M_Glow* become emissive accents without outline.

const TOON := preload("res://shaders/toon.gdshader")
const OUTLINE := preload("res://shaders/outline.gdshader")
const FX := preload("res://shaders/fx_add.gdshader")
const RING := preload("res://shaders/ring.gdshader")
const BRUSH := preload("res://assets/textures/brush.png")

static var _shared := {}
static var _outline_cache := {}
static var _scene_cache := {}


static func model_path(id: String) -> String:
	return "res://assets/models/%s.glb" % id


static func has_model(id: String) -> bool:
	return ResourceLoader.exists(model_path(id))


## Instance a model with the painted material. `unique` gives the instance its own
## materials (needed for the per-actor hit flash / fade).
static func model(id: String, unique := false, outline := 2.4) -> Node3D:
	var n: Node3D
	if Hf.has_model(id):
		n = Hf.instance(id)
		paint(n, unique, outline)
		return n
	if has_model(id):
		if not _scene_cache.has(id):
			_scene_cache[id] = load(model_path(id))
		n = (_scene_cache[id] as PackedScene).instantiate()
	else:
		n = placeholder(id)
	paint(n, unique, outline)
	return n


static func outline_mat(width: float) -> ShaderMaterial:
	var key := snappedf(width, 0.1)
	if not _outline_cache.has(key):
		var o := ShaderMaterial.new()
		o.shader = OUTLINE
		o.set_shader_parameter("width", width)
		_outline_cache[key] = o
	return _outline_cache[key]


static func toon(color: Color, glow := 0.0, outline := 2.4, unique := false) -> ShaderMaterial:
	var key := "%s|%s|%s" % [color.to_html(), glow, outline]
	if not unique and _shared.has(key):
		return _shared[key]
	var m := ShaderMaterial.new()
	m.shader = TOON
	m.set_shader_parameter("albedo", color)
	m.set_shader_parameter("glow", glow)
	m.set_shader_parameter("brush", BRUSH)
	if glow <= 0.0 and outline > 0.0:
		m.next_pass = outline_mat(outline) if not unique else outline_mat(outline).duplicate()
	if not unique:
		_shared[key] = m
	return m


static func paint(root: Node, unique := false, outline := 2.4) -> void:
	for mi in meshes(root):
		var mesh := mi.mesh
		if mesh == null:
			continue
		for s in mesh.get_surface_count():
			var src := mi.get_surface_override_material(s)
			if src == null:
				src = mesh.surface_get_material(s)
			var col := Color(0.8, 0.8, 0.8)
			var glow := 0.0
			var name := ""
			var tex: Texture2D = null
			if src:
				name = src.resource_name
			if src is StandardMaterial3D:
				col = (src as StandardMaterial3D).albedo_color
				tex = (src as StandardMaterial3D).albedo_texture
				if (src as StandardMaterial3D).emission_enabled and name == "":
					glow = 1.5
			elif src is ShaderMaterial and (src as ShaderMaterial).shader == TOON:
				continue
			if name.begins_with("M_Glow"):
				glow = 1.8
			if tex:
				var tm := toon(col, 0.0, outline, true)
				tm.set_shader_parameter("albedo_tex", tex)
				tm.set_shader_parameter("use_tex", 1.0)
				mi.set_surface_override_material(s, tm)
				continue
			mi.set_surface_override_material(s, toon(col, glow, outline, unique))
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON


static func meshes(root: Node) -> Array[MeshInstance3D]:
	var out: Array[MeshInstance3D] = []
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n is MeshInstance3D:
			out.append(n)
		for c in n.get_children():
			stack.append(c)
	return out


## Procedural part rig for built-in models, keyframed AnimRig for Higgsfield
## rigged models.
static func make_rig(m: Node3D, style: String) -> Rig:
	if m.has_meta("hf") and m.find_child("AnimationPlayer", true, false):
		return AnimRig.new(m, style)
	return Rig.new(m, style)


## Set a shader parameter on every (unique) painted material under root.
static func set_param(root: Node, param: String, value) -> void:
	for mi in meshes(root):
		if mi.mesh == null:
			continue
		for s in mi.mesh.get_surface_count():
			var m := mi.get_surface_override_material(s) as ShaderMaterial
			if m:
				m.set_shader_parameter(param, value)
				if m.next_pass is ShaderMaterial and param == "fade":
					(m.next_pass as ShaderMaterial).set_shader_parameter("fade", value)


static func fx_mat(color: Color, intensity := 1.5) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = FX
	m.set_shader_parameter("color", color)
	m.set_shader_parameter("intensity", intensity)
	return m


static func ring_mat(color: Color, runes := false) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = RING
	m.set_shader_parameter("color", color)
	m.set_shader_parameter("runes", 1.0 if runes else 0.0)
	return m


## Stand-in built from primitives with the same part names as the real rigs, so
## gameplay works (and reads) before the Blender models exist.
static func placeholder(id: String) -> Node3D:
	var spec := {
		"hanoman": [1.7, Color("f4f1ea")], "rama": [1.8, Color("3f8a5a")],
		"jembawan": [1.5, Color("6b5a4a")], "sugriwa": [1.7, Color("b0503a")],
		"wil": [1.1, Color("b0453a")], "cakil": [1.8, Color("8fa0b0")],
		"buto_ijo": [3.0, Color("4f8a3a")], "banaspati": [1.2, Color("f28a2a")],
		"yuyu": [1.2, Color("8a2a24")], "kijang": [1.6, Color("e0b040")],
		"kijang_raksasa": [2.4, Color("5a3a3a")],
		"sura": [2.2, Color("5a7080")], "baya": [2.0, Color("5a6a3a")],
	}
	var root := Node3D.new()
	root.name = id
	if not spec.has(id):
		var mi := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(1, 1, 1)
		mi.mesh = bm
		mi.position.y = 0.5
		root.add_child(mi)
		return root
	var h: float = spec[id][0]
	var col: Color = spec[id][1]
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col
	var body := Node3D.new()
	body.name = "body"
	body.position.y = h * 0.45
	root.add_child(body)
	_prim(body, CapsuleMesh.new(), Vector3(0, h * 0.18, 0), Vector3(h * 0.35, h * 0.45, h * 0.3), mat)
	var head := Node3D.new()
	head.name = "head"
	head.position.y = h * 0.42
	body.add_child(head)
	_prim(head, SphereMesh.new(), Vector3(0, h * 0.1, 0), Vector3.ONE * h * 0.26, mat)
	var eye := StandardMaterial3D.new()
	eye.resource_name = "M_GlowEye"
	eye.albedo_color = Color(1, 0.85, 0.3)
	_prim(head, SphereMesh.new(), Vector3(0.06 * h, 0.12 * h, 0.11 * h), Vector3.ONE * h * 0.05, eye)
	_prim(head, SphereMesh.new(), Vector3(-0.06 * h, 0.12 * h, 0.11 * h), Vector3.ONE * h * 0.05, eye)
	for side in [-1, 1]:
		var arm := Node3D.new()
		arm.name = "arm_l" if side > 0 else "arm_r"
		arm.position = Vector3(side * h * 0.22, h * 0.32, 0)
		body.add_child(arm)
		_prim(arm, CapsuleMesh.new(), Vector3(0, -h * 0.16, 0), Vector3(h * 0.1, h * 0.34, h * 0.1), mat)
		var leg := Node3D.new()
		leg.name = "leg_l" if side > 0 else "leg_r"
		leg.position = Vector3(side * h * 0.1, h * 0.45, 0)
		root.add_child(leg)
		_prim(leg, CapsuleMesh.new(), Vector3(0, -h * 0.22, 0), Vector3(h * 0.12, h * 0.45, h * 0.12), mat)
	return root


static func _prim(parent: Node3D, mesh: PrimitiveMesh, pos: Vector3, size: Vector3, mat: Material) -> void:
	var mi := MeshInstance3D.new()
	if mesh is CapsuleMesh:
		(mesh as CapsuleMesh).radius = 0.5
		(mesh as CapsuleMesh).height = 1.0
	elif mesh is SphereMesh:
		(mesh as SphereMesh).radius = 0.5
		(mesh as SphereMesh).height = 1.0
	mesh.surface_set_material(0, mat)
	mi.mesh = mesh
	mi.position = pos
	mi.scale = size
	parent.add_child(mi)
