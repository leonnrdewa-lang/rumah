class_name GroundFx
extends RefCounted
## Cheap ground decals: soft contact-shadow blobs under characters and props,
## rounded-rectangle ambient occlusion around building footprints, and the
## procedural piringan (mulch circle) used when the piringan model is missing.

const BLOB_SHADER := preload("res://shaders/blob.gdshader")
const SOIL_SHADER := preload("res://shaders/soil_decal.gdshader")
const MULCH_TEX_PATH := "res://assets/textures/ground/mulch.png"

static var _blob_mesh: PlaneMesh
static var _blob_mats := {}
static var _soil_mat: ShaderMaterial
static var _soil_mesh: PlaneMesh


static func _unit_plane() -> PlaneMesh:
	if _blob_mesh == null:
		_blob_mesh = PlaneMesh.new()
		_blob_mesh.size = Vector2(1, 1)
	return _blob_mesh


static func blob_material(strength := 0.42) -> ShaderMaterial:
	var key := "%.2f" % strength
	if not _blob_mats.has(key):
		var m := ShaderMaterial.new()
		m.shader = BLOB_SHADER
		m.set_shader_parameter("color", Color(0.13, 0.17, 0.07, strength))
		m.render_priority = -1
		_blob_mats[key] = m
	return _blob_mats[key]


static func blob(radius: float, strength := 0.42) -> MeshInstance3D:
	## A round soft shadow lying on the ground (child of a character, y = 0).
	var mi := MeshInstance3D.new()
	mi.name = "Blob"
	mi.mesh = _unit_plane()
	mi.scale = Vector3(radius * 2.0, 1.0, radius * 2.0)
	mi.position.y = 0.03
	mi.material_override = blob_material(strength)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


static func rect_blob(aabb: AABB, margin := 1.1, strength := 0.5) -> MeshInstance3D:
	## Ambient occlusion around a footprint (local AABB of a building/prop).
	var mi := MeshInstance3D.new()
	mi.name = "FootprintAO"
	var pm := PlaneMesh.new()
	var size := Vector2(aabb.size.x + margin * 2.0, aabb.size.z + margin * 2.0)
	pm.size = size
	mi.mesh = pm
	var c := aabb.get_center()
	mi.position = Vector3(c.x, 0.035, c.z)
	var m := ShaderMaterial.new()
	m.shader = BLOB_SHADER
	m.set_shader_parameter("color", Color(0.12, 0.16, 0.06, strength))
	m.set_shader_parameter("shape", 1.0)
	m.set_shader_parameter("quad_size", size)
	m.set_shader_parameter("inner_half", Vector2(aabb.size.x * 0.5 - 0.2, aabb.size.z * 0.5 - 0.2))
	m.set_shader_parameter("margin", margin)
	m.render_priority = -1
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


static func soil_mesh() -> PlaneMesh:
	if _soil_mesh == null:
		_soil_mesh = PlaneMesh.new()
		_soil_mesh.size = Vector2(2.5, 2.5)
		_soil_mesh.material = soil_material()
	return _soil_mesh


static func soil_material() -> ShaderMaterial:
	if _soil_mat == null:
		_soil_mat = ShaderMaterial.new()
		_soil_mat.shader = SOIL_SHADER
		_soil_mat.set_shader_parameter("noise_tex", ModelLib.NOISE_TEX)
		var t := load_tiling_texture(MULCH_TEX_PATH)
		if t:
			_soil_mat.set_shader_parameter("mulch_tex", t)
			_soil_mat.set_shader_parameter("has_tex", 1.0)
		_soil_mat.render_priority = -1
	return _soil_mat


const PIRINGAN_SHADER := preload("res://shaders/piringan.gdshader")
static var _piringan_mat: ShaderMaterial


static func piringan_material() -> ShaderMaterial:
	## Soft alpha-blended version of the piringan model's material (see piringan.gdshader);
	## null when the model has no texture.
	if _piringan_mat == null:
		var mesh := ModelLib.merged_mesh("piringan", true)
		var tex: Texture2D = null
		for i in mesh.get_surface_count():
			var sm := mesh.surface_get_material(i) as ShaderMaterial
			if sm and sm.get_shader_parameter("albedo_tex") != null:
				tex = sm.get_shader_parameter("albedo_tex")
		if tex == null:
			return null
		_piringan_mat = ShaderMaterial.new()
		_piringan_mat.resource_name = "M_Piringan"
		_piringan_mat.shader = PIRINGAN_SHADER
		_piringan_mat.set_shader_parameter("albedo_tex", tex)
		_piringan_mat.set_shader_parameter("noise_tex", ModelLib.NOISE_TEX)
		_piringan_mat.render_priority = -1
	return _piringan_mat


static var _tiling := {}


static func average_linear(tex: Texture2D) -> Vector3:
	## Mean colour of a (source_color) texture in linear space, for shaders that
	## scale detail around the average instead of sampling a 1x1 mip every pixel.
	var img := tex.get_image() if tex else null
	if img == null:
		return Vector3(0.27, 0.39, 0.065)
	img = img.duplicate()
	if img.is_compressed():
		img.decompress()
	img.clear_mipmaps()
	img.convert(Image.FORMAT_RGBA8)
	# halving with bilinear filtering is a box filter, so every texel counts
	while img.get_width() > 16 and img.get_height() > 16:
		img.resize(img.get_width() / 2, img.get_height() / 2, Image.INTERPOLATE_BILINEAR)
	img.resize(16, 16, Image.INTERPOLATE_BILINEAR)
	var acc := Vector3.ZERO
	for y in 16:
		for x in 16:
			var c := img.get_pixel(x, y).srgb_to_linear()
			acc += Vector3(c.r, c.g, c.b)
	return acc / 256.0


static func load_tiling_texture(path: String) -> Texture2D:
	## Loads a ground texture and makes sure it has mipmaps (the default PNG import
	## has none, which makes world-space tiling shimmer). null when missing.
	if _tiling.has(path):
		return _tiling[path]
	var tex: Texture2D = null
	if ResourceLoader.exists(path):
		var src: Texture2D = load(path)
		tex = src
		if src:
			var img := src.get_image()
			if img and not img.has_mipmaps():
				if img.is_compressed():
					img.decompress()
				img.generate_mipmaps()
				tex = ImageTexture.create_from_image(img)
	_tiling[path] = tex
	return tex
