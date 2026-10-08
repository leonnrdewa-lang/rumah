class_name CharLook
extends RefCounted
## Villager variants: the 12 character GLBs are shared by ~45 people, so each one is
## dressed differently at load time (no extra downloads, ~60 KB of shared pieces):
##   * skin tone, hair colour, clothes colours: per-instance copies of the toon
##     materials (cached per colour, so equal colours share one material)
##   * hair style / hat / hijab / glasses / beard / towel: the character's own `Look`
##     mesh (hair, hat, hijab; blender/characters.py) is hidden and pieces from
##     char_looks.glb are fixed to its head / chest bone, fitted with the head size
##     the GLB exports (glTF extras head_c / head_r / chest_k / neck_z)
##   * body height and width (model scale; CharAnim reads it for the gait speeds)
## apply(model, model_name, key) picks a look from `key` (villager id, extra id,
## "walker3"...): hand-made for the named villagers in NAMED, otherwise seeded from
## the key within what suits the base model (RULES).

const LIB := "char_looks"
const REF_HEAD_R := 0.228   # head radius the library pieces are modelled on

const SKIN := ["f6c9a0", "f2b98a", "e8ab7c", "dca06e", "d59a6a", "c78a58", "b67a4a", "9c6639"]
const HAIR := ["2e2724", "211b19", "3b2a22", "4d3528", "2a2a33", "5e4532"]
const HAIR_OLD := ["c4c0b8", "e9e5dc", "9a948c", "d8d4cc"]
const SHIRT := ["e05a47", "f08a3a", "f2c14e", "6cbf5a", "3fa38f", "4c8fd6", "7a6fd0", "d46aa0", "f4f0e4",
	"9bc4e8", "c9e36b", "b5532f", "2f6f9f", "e8d3a8", "8fbf9f", "f29b9b"]
const DARK := ["3b4155", "5079b0", "56502c", "6b4a33", "2f4f4f", "5a5e69", "7f7e46", "4a3b5c", "8b4f2e"]
const HIJAB := ["d08791", "6fa3d6", "f4f0e4", "7fbf8f", "e6b45a", "9b7fd0", "e07a5f", "3f6f9a", "c4a7d8", "e8c7a0"]
const HAT_STRAW := ["d8a95c", "e2be7a", "c9944e"]
const HAT_CLOTH := ["7f7e46", "3274d9", "d2521b", "2f7d73", "f4f0e4", "b8322c", "4a4a4a", "e8c34a"]

## per base model: cloth materials to recolour (+ palette) and the look kinds that suit it
const RULES := {
	"char_ibu": {"cloth": {"M_Dress": SHIRT, "M_Floral": ["fff4de", "f4f0e4", "ffe7a8", "e9f3ff"]},
		"kind": "woman", "height": Vector2(0.95, 1.04)},
	"char_nenek": {"cloth": {"M_Kebaya": SHIRT, "M_Kain": DARK}, "kind": "old_woman", "height": Vector2(0.94, 1.0)},
	"char_kakek": {"cloth": {"M_FadedShirt": ["dcd7c6", "f4f0e4", "c9d8e6", "e8d3a8", "b9cfa8"],
		"M_Sarong": ["8b4f2e", "3f6f9a", "6b3a5c", "2f6f4f", "a33b2b", "5c4a3b"]}, "kind": "old_man",
		"height": Vector2(0.94, 1.02)},
	"char_petani": {"cloth": {"M_WorkBlue": SHIRT, "M_Olive": DARK}, "kind": "man", "height": Vector2(0.94, 1.07)},
	"char_pemuda": {"cloth": {"M_GreenTee": SHIRT, "M_Jeans": DARK, "M_SarongRed": ["ac3c4f", "3f6f9a", "2f7d73", "c98a3a"]},
		"kind": "young_man", "height": Vector2(0.96, 1.07)},
	"char_buruh": {"cloth": {"M_Dusty": ["b1a78f", "9bb0c4", "c4a882", "8f9a7a", "d0c7b0", "a0705a"], "M_WorkPants": DARK},
		"kind": "worker", "height": Vector2(0.95, 1.06)},
	"char_anak": {"cloth": {"M_TeeOrange": SHIRT, "M_Jeans": DARK}, "kind": "child", "height": Vector2(0.92, 1.08)},
	"char_kades": {"cloth": {"M_White": ["fbf7ee", "e8d3a8", "c9d8e6", "d9c3a5"], "M_Trousers": DARK},
		"kind": "official", "height": Vector2(0.96, 1.04)},
}

## hand-made looks for the named villagers (the original six keep their portrait look)
const NAMED := {
	"kakek": {"keep": true}, "ibu": {"keep": true}, "kades": {"keep": true}, "nenek": {"keep": true},
	"pemuda": {"keep": true}, "petani": {"keep": true}, "anak": {"keep": true}, "calo": {"keep": true},
	"somad": {"hair": "hair_sides", "hat": "hat_peci", "hat_a": "f4f0e4", "face": ["beard"], "hair_col": "e9e5dc",
		"skin": "c78a58", "cloth": {"M_FadedShirt": "f4f0e4", "M_Sarong": "2f6f4f"}, "w": 1.1},
	"karim": {"hair": "hair_sides", "hat": "hat_peci", "hat_a": "26211e", "face": ["beard", "glasses"],
		"hair_col": "d8d4cc", "skin": "dca06e", "cloth": {"M_FadedShirt": "f4f0e4", "M_Sarong": "3f6f9a"}},
	"dullah": {"hair": "hair_sides", "hat": "hat_caping", "face": ["moustache"], "hair_col": "c4c0b8",
		"skin": "b67a4a", "cloth": {"M_FadedShirt": "c9d8e6", "M_Sarong": "a33b2b"}, "h": 0.95},
	"ucok": {"hair": "hair_short", "hat": "hat_cap", "hat_a": "b8322c", "hat_b": "f4f0e4", "skin": "b67a4a",
		"cloth": {"M_WorkBlue": "e05a47", "M_Olive": "3b4155"}, "w": 1.12, "h": 1.03},
	"rian": {"hair": "hair_messy", "hair_col": "4d3528", "skin": "e8ab7c",
		"cloth": {"M_GreenTee": "4c8fd6", "M_Jeans": "2f4f4f", "M_SarongRed": "c98a3a"}},
	"wati": {"hair": "hair_pony", "hair_col": "211b19", "skin": "e8ab7c",
		"cloth": {"M_Dress": "f2c14e", "M_Floral": "fff4de"}, "h": 1.02},
	"slamet": {"hair": "hair_band", "hat": "hat_bucket", "hat_a": "2f7d73", "hat_b": "3b4155", "face": ["moustache"],
		"skin": "c78a58", "cloth": {"M_WorkBlue": "e8d3a8", "M_Olive": "5a5e69"}, "w": 1.08},
	"lastri": {"hijab": "6fa3d6", "skin": "f2b98a", "cloth": {"M_Dress": "f4f0e4", "M_Floral": "9bc4e8"}},
	"romlah": {"hijab": "f4f0e4", "skin": "dca06e", "face": ["glasses"],
		"cloth": {"M_Kebaya": "7a6fd0", "M_Kain": "4a3b5c"}},
	"darsih": {"hair": "hair_bun", "hair_col": "9a948c", "skin": "c78a58", "hat": "hat_caping",
		"cloth": {"M_Kebaya": "e05a47", "M_Kain": "56502c"}},
	"yanto": {"hair": "hair_short", "hat": "hat_bandana", "hat_a": "3274d9", "skin": "9c6639",
		"cloth": {"M_Dusty": "9bb0c4", "M_WorkPants": "3b4155"}, "h": 1.05},
	"karta": {"hair": "hair_band", "hat": "hat_straw", "hat_a": "e2be7a", "hat_b": "8b4f2e", "face": ["goatee"],
		"skin": "c78a58", "cloth": {"M_WorkBlue": "6cbf5a", "M_Olive": "6b4a33"}, "w": 0.94},
	"bidan": {"hijab": "f4f0e4", "skin": "f6c9a0", "cloth": {"M_Dress": "9bc4e8", "M_Floral": "f4f0e4"}, "h": 1.02},
	"rt": {"face": ["glasses_sq"], "skin": "dca06e", "cloth": {"M_White": "e8d3a8", "M_Trousers": "6b4a33"},
		"w": 1.08, "h": 0.97},
	"tini": {"hijab": "7fbf8f", "skin": "dca06e", "cloth": {"M_Dress": "f08a3a", "M_Floral": "ffe7a8"}},
	"neneng": {"hair": "hair_long", "hair_col": "2a2a33", "skin": "f2b98a", "cloth": {"M_Dress": "d46aa0", "M_Floral": "fff4de"}},
	"ipah": {"hijab": "e6b45a", "skin": "c78a58", "face": ["glasses"], "cloth": {"M_Kebaya": "3fa38f", "M_Kain": "8b4f2e"}},
	"sari": {"hair": "hair_pony", "hair_col": "211b19", "cloth": {"M_TeeOrange": "f29b9b", "M_Jeans": "4a3b5c"}},
	"budi": {"hair": "hair_short", "hat": "hat_cap", "hat_a": "3274d9", "hat_b": "f2c14e", "skin": "b67a4a",
		"cloth": {"M_TeeOrange": "6cbf5a", "M_Jeans": "5079b0"}},
	"eko": {"hair": "hair_short", "face": ["sunglasses"], "skin": "c78a58",
		"cloth": {"M_GreenTee": "2f6f9f", "M_Jeans": "3b4155", "M_SarongRed": "3f6f9a"}},
	"tigor": {"hair": "hair_short", "hat": "hat_cap", "hat_a": "e8c34a", "hat_b": "3b4155", "face": ["moustache"],
		"skin": "b67a4a", "cloth": {"M_Dusty": "c4a882", "M_WorkPants": "56502c"}, "w": 1.15, "h": 1.05},
	"asep": {"hair": "hair_messy", "hat": "hat_bandana", "hat_a": "2f7d73", "skin": "e8ab7c",
		"cloth": {"M_Dusty": "d0c7b0", "M_WorkPants": "2f4f4f"}},
	"rahmat": {"hair": "hair_band", "hat": "hat_bucket", "hat_a": "f4f0e4", "hat_b": "3f6f9a", "skin": "9c6639",
		"cloth": {"M_WorkBlue": "3fa38f", "M_Olive": "3b4155"}},
	"mak": {"hijab": "b5532f", "skin": "dca06e", "cloth": {"M_Dress": "e8d3a8", "M_Floral": "b5532f"}, "w": 1.12},
}

static var _lib_meshes := {}
static var _lib_loaded := false
static var _pieces_mats := {}


static func _lib_mesh(piece: String) -> Mesh:
	if not _lib_loaded:
		_lib_loaded = true
		var s := ModelLib.scene(LIB)
		if s:
			var root := s.instantiate()
			for mi in ModelLib.find_meshes(root):
				_lib_meshes[String(mi.name)] = mi.mesh
			root.free()
	return _lib_meshes.get(piece)


static func pick(rng: RandomNumberGenerator, arr: Array) -> String:
	return arr[rng.randi() % arr.size()]


static func spec_for(model: String, key: String) -> Dictionary:
	## The look of `key` on `model`: NAMED entry, or generated from the key.
	if NAMED.has(key):
		return NAMED[key]
	if not RULES.has(model):
		return {"keep": true}
	var rule: Dictionary = RULES[model]
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(key + "|look")
	var s := {"skin": pick(rng, SKIN), "cloth": {}}
	for m in rule["cloth"]:
		s["cloth"][m] = pick(rng, rule["cloth"][m])
	var hr: Vector2 = rule["height"]
	s["h"] = rng.randf_range(hr.x, hr.y)
	s["w"] = rng.randf_range(0.92, 1.12)
	var face: Array = []
	match String(rule["kind"]):
		"woman":
			var r := rng.randf()
			if r < 0.6:
				s["hijab"] = pick(rng, HIJAB)
			else:
				s["hair"] = pick(rng, ["hair_bun", "hair_pony", "hair_long"])
				s["hair_col"] = pick(rng, HAIR)
				if rng.randf() < 0.3:
					s["hat"] = "hat_caping"
					s["hair"] = "hair_band"
		"old_woman":
			if rng.randf() < 0.5:
				s["hijab"] = pick(rng, HIJAB)
			else:
				s["hair"] = "hair_bun"
				s["hair_col"] = pick(rng, HAIR_OLD)
			if rng.randf() < 0.35:
				face.append("glasses")
		"old_man":
			s["hair"] = "hair_sides"
			s["hair_col"] = pick(rng, HAIR_OLD)
			s["hat"] = pick(rng, ["hat_peci", "hat_peci", "hat_caping", "", "hat_bucket"])
			if s["hat"] == "hat_peci":
				s["hat_a"] = pick(rng, ["26211e", "26211e", "f4f0e4"])
			face.append(pick(rng, ["beard", "moustache", "goatee", ""]))
			if rng.randf() < 0.35:
				face.append("glasses")
		"man", "worker", "young_man":
			var hats := ["hat_caping", "hat_bucket", "hat_cap", "hat_straw", "hat_bandana", "hat_peci", "", ""]
			if rule["kind"] == "young_man":
				hats = ["hat_cap", "hat_bandana", "", "", "hat_bucket"]
			s["hat"] = pick(rng, hats)
			s["hair"] = "hair_band" if s["hat"] in ["hat_caping", "hat_bucket", "hat_straw", "hat_peci"] else \
				pick(rng, ["hair_short", "hair_messy"])
			s["hair_col"] = pick(rng, HAIR)
			if rng.randf() < 0.3:
				face.append(pick(rng, ["moustache", "goatee"]))
			if rng.randf() < 0.12:
				face.append("glasses_sq")
		"child":
			var girl := rng.randf() < 0.45
			s["hair"] = pick(rng, ["hair_pony", "hair_bun"]) if girl else pick(rng, ["hair_short", "hair_messy"])
			s["hair_col"] = pick(rng, HAIR)
			if not girl and rng.randf() < 0.4:
				s["hat"] = "hat_cap"
		"official":
			s["face"] = []
			if rng.randf() < 0.4:
				face.append("glasses_sq")
			s["keep_look"] = true
	if s.get("hat", "") != "" and not s.has("hat_a"):
		s["hat_a"] = pick(rng, HAT_STRAW if s["hat"] in ["hat_caping", "hat_straw"] else HAT_CLOTH)
		s["hat_b"] = pick(rng, DARK)
	s["face"] = face.filter(func(f): return f != "")
	return s


static func apply(root: Node3D, model: String, key: String) -> void:
	## Dress one character instance (call before CharAnim.new: it reads the scale).
	if key == "":
		return
	var s := spec_for(model, key)
	if s.get("keep", false):
		return
	var skel := root.find_child("Skeleton3D", true, false) as Skeleton3D
	if skel == null:
		return
	var ex := _extras(root)
	var body: MeshInstance3D = null
	var look: MeshInstance3D = null
	for mi in ModelLib.find_meshes(root):
		if String(mi.name).begins_with("Look"):
			look = mi
		elif String(mi.name).begins_with("Body"):
			body = mi
	var cols := {}
	if s.has("skin"):
		cols["M_Skin"] = s["skin"]
		cols["M_SkinTan"] = s["skin"]
	for m in s.get("cloth", {}):
		cols[m] = s["cloth"][m]
	var swap: bool = (s.has("hair") or s.has("hijab") or s.has("hat")) and not s.get("keep_look", false)
	if body:
		_recolour(body, cols)
	if look:
		if swap:
			look.visible = false
		else:
			_recolour(look, cols)
	var pal := {"M_Hair": s.get("hair_col", "2e2724"), "M_LookA": s.get("hat_a", "d8a95c"),
		"M_LookB": s.get("hat_b", "8b4f2e"), "M_Hijab": s.get("hijab", "d08791")}
	var head_pieces: Array = []
	var neck_pieces: Array = []
	if swap:
		if s.has("hijab"):
			head_pieces.append("hijab")
			neck_pieces.append("hijab_drape")
		else:
			if s.get("hair", "") != "":
				head_pieces.append(s["hair"])
			if s.get("hat", "") != "":
				head_pieces.append(s["hat"])
	for f in s.get("face", []):
		if s.has("hijab") and f in ["beard", "moustache", "goatee"]:
			continue
		head_pieces.append(f)
	if not head_pieces.is_empty():
		var hr: Array = ex.get("head_r", [REF_HEAD_R, 0.212, 0.206])
		var k := float(hr[0]) / REF_HEAD_R
		_attach(skel, "head", head_pieces, Transform3D(Basis().scaled(Vector3.ONE * k),
			Vector3(0, float(ex.get("head_c", 0.846)), 0)), pal)
	if not neck_pieces.is_empty():
		var ck := float(ex.get("chest_k", 1.0))
		_attach(skel, "chest", neck_pieces, Transform3D(Basis().scaled(Vector3.ONE * ck),
			Vector3(0, float(ex.get("neck_z", 0.598)), 0)), pal)
	var h := float(s.get("h", 1.0))
	var w := float(s.get("w", 1.0))
	root.scale = Vector3(h * w, h, h)


static func _extras(root: Node) -> Dictionary:
	if root.has_meta("extras") and (root.get_meta("extras") as Dictionary).has("head_c"):
		return root.get_meta("extras")
	for c in root.get_children():
		var e := _extras(c)
		if not e.is_empty():
			return e
	return {}


static func _tinted(m: Material, col: String) -> Material:
	return ModelLib.retuned(m, "look" + col, {"albedo": Color(col)})


static func _recolour(mi: MeshInstance3D, cols: Dictionary) -> void:
	for i in mi.mesh.get_surface_count():
		var src := mi.mesh.surface_get_material(i)
		if src == null:
			continue
		var n := src.resource_name
		var col := ""
		if cols.has(n):
			col = cols[n]
		elif n.begins_with("M_Hair") and cols.has("M_Hair"):
			col = cols["M_Hair"]
		if col == "":
			continue
		var cur := mi.get_surface_override_material(i)
		mi.set_surface_override_material(i, _tinted(cur if cur else src, col))


static func _attach(skel: Skeleton3D, bone: String, pieces: Array, place: Transform3D, pal: Dictionary) -> void:
	var bi := skel.find_bone(bone)
	if bi < 0:
		return
	var ba := BoneAttachment3D.new()
	ba.bone_name = bone
	skel.add_child(ba)
	var local := skel.get_bone_global_rest(bi).affine_inverse() * place
	for p in pieces:
		var mesh := _lib_mesh(p)
		if mesh == null:
			continue
		var mi := MeshInstance3D.new()
		mi.name = "Look_" + p
		mi.mesh = mesh
		mi.transform = local
		for i in mesh.get_surface_count():
			var m := mesh.surface_get_material(i)
			var conv := ModelLib.convert_material(m, false, 0.35)
			var n := m.resource_name if m else ""
			if pal.has(n):
				conv = _tinted(conv, pal[n])
			mi.set_surface_override_material(i, conv)
		ba.add_child(mi)
