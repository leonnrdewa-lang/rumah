extends Node
## Higgsfield asset pack loaded at runtime. When the game is served from the
## Higgsfield site, `hf/manifest.json` sits next to index.html and lists painted
## portraits, painted arena floors and rigged/animated GLB characters made with
## Higgsfield (GPT Image 2.5 + image-to-3D with auto-rig). Everything is optional:
## without the manifest the game uses its built-in Blender assets. Autoloaded as `Hf`.

signal progress(done: int, total: int)
signal ready_loaded

var base := ""
var manifest := {}
var loaded := false
var models := {}       # id -> PackedScene (from GLB bytes)
var model_info := {}   # id -> manifest entry
var textures := {}     # key -> Texture2D ("portrait/<id>", "floor/<biome>")
var _pending := 0
var _total := 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if OS.has_feature("web"):
		var href := str(JavaScriptBridge.eval("location.href.split('?')[0].split('#')[0]", true))
		base = href.substr(0, href.rfind("/") + 1)
	else:
		for a in OS.get_cmdline_user_args():
			if a.begins_with("--hf="):
				base = a.substr(5)
	if base == "":
		_finish()
		return
	_fetch(base + "hf/manifest.json", func(ok: bool, body: PackedByteArray):
		if not ok:
			_finish()
			return
		var d = JSON.parse_string(body.get_string_from_utf8())
		if not d is Dictionary:
			_finish()
			return
		manifest = d
		_load_all())


func _finish() -> void:
	if base != "":
		print("HF ready: models=%s textures=%s" % [str(models.keys()), str(textures.keys())])
	loaded = true
	ready_loaded.emit()


func _fetch(url: String, cb: Callable) -> void:
	if url.begins_with("/") or url.begins_with("file://"):
		var path := url.trim_prefix("file://")
		var f := FileAccess.open(path, FileAccess.READ)
		cb.call(f != null, f.get_buffer(f.get_length()) if f else PackedByteArray())
		return
	var r := HTTPRequest.new()
	r.download_chunk_size = 262144
	add_child(r)
	r.request_completed.connect(func(result, code, _h, body):
		r.queue_free()
		cb.call(result == HTTPRequest.RESULT_SUCCESS and code == 200, body))
	if r.request(url) != OK:
		r.queue_free()
		cb.call(false, PackedByteArray())


func _load_all() -> void:
	var jobs := []
	for id in manifest.get("portraits", {}):
		jobs.append(["portrait/" + id, manifest.portraits[id]])
	for b in manifest.get("floors", {}):
		jobs.append(["floor/" + b, manifest.floors[b]])
	for id in manifest.get("models", {}):
		jobs.append(["model/" + id, manifest.models[id].file])
		model_info[id] = manifest.models[id]
	_total = jobs.size()
	print("HF manifest: %d portraits, %d floors, %d models, %d voices" % [manifest.get("portraits", {}).size(),
		manifest.get("floors", {}).size(), manifest.get("models", {}).size(), manifest.get("voices", {}).size()])
	_pending = _total
	if _total == 0:
		_finish()
		return
	for j in jobs:
		var key: String = j[0]
		_fetch(base + String(j[1]), func(ok: bool, body: PackedByteArray): _on_file(key, ok, body))


func _on_file(key: String, ok: bool, body: PackedByteArray) -> void:
	if ok:
		if key.begins_with("model/"):
			var scene := _glb_scene(body)
			if scene:
				models[key.substr(6)] = scene
				var probe := scene.instantiate()
				var ap := probe.find_child("AnimationPlayer", true, false) as AnimationPlayer
				print("HF model %s: %d bytes, clips=%s" % [key.substr(6), body.size(), str(ap.get_animation_list()) if ap else "[]"])
				probe.free()
			else:
				print("HF model %s: FAILED to parse" % key.substr(6))
		else:
			var img := Image.new()
			var err := img.load_png_from_buffer(body)
			if err != OK:
				err = img.load_webp_from_buffer(body)
			if err != OK:
				err = img.load_jpg_from_buffer(body)
			if err == OK:
				img.generate_mipmaps()
				textures[key] = ImageTexture.create_from_image(img)
	_pending -= 1
	progress.emit(_total - _pending, _total)
	if _pending <= 0:
		_finish()


func _glb_scene(bytes: PackedByteArray) -> PackedScene:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_buffer(bytes, "", state) != OK:
		return null
	var root := doc.generate_scene(state)
	if root == null:
		return null
	_own(root, root)
	var ps := PackedScene.new()
	var ok := ps.pack(root) == OK
	root.free()
	return ps if ok else null


func _own(n: Node, owner_node: Node) -> void:
	for c in n.get_children():
		c.owner = owner_node
		_own(c, owner_node)


func has_model(id: String) -> bool:
	return models.has(id)


func portrait(id: String) -> Texture2D:
	return textures.get("portrait/" + id)


func floor_tex(biome: String) -> Texture2D:
	return textures.get("floor/" + biome)


## Instance a Higgsfield model scaled to its manifest height, feet on the floor,
## facing +Z like the built-in models.
func instance(id: String) -> Node3D:
	var info: Dictionary = model_info.get(id, {})
	var inner := (models[id] as PackedScene).instantiate() as Node3D
	var holder := Node3D.new()
	holder.name = id
	holder.add_child(inner)
	var aabb := _bounds(inner)
	# long creatures (shark, crocodile, deer): turn the long axis onto +Z and put
	# the heavier end (head/torso) in front
	if info.has("length") or bool(info.get("auto_face", false)):
		var yaw := 0.0
		var c := _vertex_centroid(inner)
		var mid := aabb.position + aabb.size * 0.5
		if aabb.size.x > aabb.size.z:
			yaw = -PI / 2 if c.x > mid.x else PI / 2
		else:
			yaw = 0.0 if c.z > mid.z else PI
		inner.rotation.y = yaw
		aabb = _bounds_rotated(inner, yaw)
	var want: float = float(info.get("height", 0.0))
	var s := 1.0
	if want > 0.0 and aabb.size.y > 0.001:
		s = want / aabb.size.y
	elif float(info.get("length", 0.0)) > 0.0:
		s = float(info.length) / max(aabb.size.x, aabb.size.z)
	inner.scale = Vector3.ONE * s
	inner.position = Vector3(-(aabb.position.x + aabb.size.x * 0.5) * s, -aabb.position.y * s + float(info.get("lift", 0.0)),
		-(aabb.position.z + aabb.size.z * 0.5) * s)
	inner.rotation.y += deg_to_rad(float(info.get("yaw", 0.0)))
	holder.set_meta("hf", true)
	holder.set_meta("hf_info", info)
	return holder


func _bounds(n: Node3D) -> AABB:
	var out := AABB()
	var first := true
	for mi in Art.meshes(n):
		if mi.mesh == null:
			continue
		var b: AABB = mi.global_transform * mi.mesh.get_aabb() if mi.is_inside_tree() else _local_xform(mi, n) * mi.mesh.get_aabb()
		out = b if first else out.merge(b)
		first = false
	return out


func _vertex_centroid(n: Node3D) -> Vector3:
	var sum := Vector3.ZERO
	var cnt := 0
	for mi in Art.meshes(n):
		if mi.mesh == null:
			continue
		var xf := _local_xform(mi, n)
		for sidx in mi.mesh.get_surface_count():
			var arr := mi.mesh.surface_get_arrays(sidx)
			var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var step: int = max(1, verts.size() / 4000)
			for i in range(0, verts.size(), step):
				sum += xf * verts[i]
				cnt += 1
	return sum / max(cnt, 1)


func _bounds_rotated(inner: Node3D, yaw: float) -> AABB:
	var r := Transform3D(Basis(Vector3.UP, yaw), Vector3.ZERO)
	return r * _bounds(inner)


func _local_xform(node: Node3D, root: Node3D) -> Transform3D:
	var t := Transform3D.IDENTITY
	var cur: Node = node
	while cur and cur != root:
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return t


# --- voiced dialogue ----------------------------------------------------------

var _voice_cache := {}
var _voice_player: AudioStreamPlayer


static func voice_key(text: String) -> String:
	return text.md5_text().substr(0, 12)


## Speak a dialogue line if the pack has a recording for it (fetched on demand).
func speak(text: String) -> void:
	stop_voice()
	var key := voice_key(text)
	var voices: Dictionary = manifest.get("voices", {})
	if not voices.has(key):
		return
	if _voice_cache.has(key):
		_play_voice(_voice_cache[key])
		return
	_fetch(base + String(voices[key]), func(ok: bool, body: PackedByteArray):
		if not ok or body.is_empty():
			return
		var s := AudioStreamMP3.new()
		s.data = body
		_voice_cache[key] = s
		_play_voice(s))


func _play_voice(s: AudioStream) -> void:
	if _voice_player == null:
		_voice_player = AudioStreamPlayer.new()
		_voice_player.bus = "SFX"
		_voice_player.volume_db = 2.0
		add_child(_voice_player)
	_voice_player.stream = s
	_voice_player.play()


func stop_voice() -> void:
	if _voice_player:
		_voice_player.stop()
