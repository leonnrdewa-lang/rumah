class_name Staff
extends Node3D
## Hanoman's tongkat: a lacquered iron staff with gold bands and glowing gold
## ends, gripped in the right fist. Built from primitives so it can grow: the Jurus
## stretches it out like a laser (`extend_to`). Local +Y runs along the staff and
## the origin is the grip point.

const SHAFT := Color("5a1414")
const GOLD := Color("e8b23a")
const GLOW := Color(1.0, 0.78, 0.35)

var length := 2.2
var grip := 0.62            # grip distance from the bottom end
var _shaft: MeshInstance3D
var _top: Node3D
var _bottom: Node3D
var _glow: Array[MeshInstance3D] = []


func _init() -> void:
	name = "Staff"
	_shaft = _cyl(0.042, 1.0, SHAFT)
	add_child(_shaft)
	_bottom = _cap()
	add_child(_bottom)
	_top = _cap()
	add_child(_top)
	for f in [0.12, 0.5, 0.88]:
		var band := _cyl(0.055, 0.07, GOLD)
		band.set_meta("f", f)
		add_child(band)
	_layout()


func _cyl(r: float, h: float, col: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.top_radius = r
	c.bottom_radius = r
	c.height = h
	c.radial_segments = 10
	c.rings = 1
	mi.mesh = c
	mi.material_override = Art.toon(col, 0.0, 1.6, true)
	return mi


func _cap() -> Node3D:
	var n := Node3D.new()
	var ring := _cyl(0.062, 0.16, GOLD)
	n.add_child(ring)
	var s := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.07
	sm.height = 0.14
	sm.radial_segments = 10
	sm.rings = 5
	s.mesh = sm
	s.material_override = Art.fx_mat(GLOW, 2.4)
	s.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	n.add_child(s)
	_glow.append(s)
	return n


func _layout() -> void:
	var lo := -grip
	var hi := length - grip
	_shaft.scale = Vector3(1, hi - lo, 1)
	_shaft.position.y = (lo + hi) * 0.5
	_bottom.position.y = lo + 0.05
	_top.position.y = hi - 0.05
	for c in get_children():
		if c.has_meta("f"):
			(c as Node3D).position.y = lo + (hi - lo) * float(c.get_meta("f"))


func set_length(l: float) -> void:
	length = max(l, grip + 0.3)
	_layout()


## Grow the staff to `l` metres over `t`, hold, then shrink back.
func extend_to(l: float, t := 0.09, hold := 0.3, back := 0.2) -> void:
	var base := 2.2
	var tw := create_tween()
	tw.tween_method(set_length, length, l, t).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_EXPO)
	tw.tween_interval(hold)
	tw.tween_method(set_length, l, base, back).set_ease(Tween.EASE_IN).set_trans(Tween.TRANS_CUBIC)


func set_glow(color: Color) -> void:
	for g in _glow:
		(g.material_override as ShaderMaterial).set_shader_parameter("color", color)


## World position of the staff tip (the end the laser comes from).
func tip() -> Vector3:
	return _top.global_position


## Put a staff in `model`'s right hand. Built-in (Blender) models carry a
## "weapon" pivot in the fist; Higgsfield models get a BoneAttachment3D on the
## right hand bone, oriented so the staff points forward and a little up at rest
## (like a sword gripped in an A-pose fist) and scaled back to metres.
static func attach(model: Node3D) -> Staff:
	var st := Staff.new()
	var weapon := model.find_child("weapon", true, false) as Node3D
	if weapon:
		for c in weapon.get_children():
			if c is GeometryInstance3D:
				(c as GeometryInstance3D).visible = false
		weapon.add_child(st)
		st.basis = _basis_along(Vector3(0, 0.83, 0.55).normalized())
		return st
	var skels := model.find_children("*", "Skeleton3D", true, false)
	if skels.is_empty():
		var arm := model.find_child("arm_r", true, false) as Node3D
		(arm if arm else model).add_child(st)
		st.position = Vector3(0, -0.5, 0.1)
		st.basis = _basis_along(Vector3(0, 0.83, 0.55).normalized())
		return st
	var sk := skels[0] as Skeleton3D
	var hand := _find_bone(sk, ["righthand", "hand_r", "hand.r", "r_hand", "rhand"])
	if hand < 0:
		# no hand bone: carry it at the right hip (own right = -X)
		model.add_child(st)
		st.position = Vector3(-0.35, 1.0, 0.15)
		st.basis = _basis_along(Vector3(0, 0.83, 0.55).normalized())
		return st
	var ba := BoneAttachment3D.new()
	ba.bone_name = sk.get_bone_name(hand)
	sk.add_child(ba)
	ba.add_child(st)
	# skeleton space -> model space (Meshy: Armature scaled 0.01, bones in cm)
	var to_model := Hf._local_xform(sk, model)
	var unit := to_model.basis.get_scale().x
	var inv := to_model.basis.inverse()
	var fwd := (inv * Vector3(0, 0, 1)).normalized()
	var up := (inv * Vector3(0, 1, 0)).normalized()
	var hand_rest := sk.get_bone_global_rest(hand)
	var want_dir := (fwd * 0.8 + up * 0.6).normalized()
	var local_dir := (hand_rest.basis.inverse() * want_dir).normalized()
	# grip a few centimetres past the wrist, toward the fingers
	var parent := sk.get_bone_parent(hand)
	var along := Vector3.ZERO
	if parent >= 0:
		along = (hand_rest.origin - sk.get_bone_global_rest(parent).origin).normalized()
	var grip_skel := hand_rest.origin + along * (0.07 / maxf(unit, 0.0001))
	st.position = hand_rest.affine_inverse() * grip_skel
	var bs := hand_rest.basis.get_scale()
	st.basis = _basis_along(local_dir) * Basis.from_scale(Vector3.ONE / (maxf(unit, 0.0001) * bs.x))
	return st


static func _basis_along(dir: Vector3) -> Basis:
	return Basis(Quaternion(Vector3.UP, dir.normalized()))


static func _find_bone(sk: Skeleton3D, keys: Array) -> int:
	var best := -1
	for i in sk.get_bone_count():
		var n := sk.get_bone_name(i).to_lower().replace("mixamorig:", "").replace(" ", "")
		for k in keys:
			if n == k or n.ends_with(k):
				return i
		if best < 0 and n.contains("hand") and (n.contains("right") or n.ends_with("_r") or n.ends_with(".r")) \
				and not (n.contains("thumb") or n.contains("index") or n.contains("middle") or n.contains("ring") or n.contains("pinky")):
			best = i
	return best


var style := "tongkat"
var _extra: Node3D


## Restyle the held weapon (see Weapons): mace, bow or chakra instead of the staff.
func set_style(s: String) -> void:
	style = s
	if _extra:
		_extra.queue_free()
		_extra = null
	for c in get_children():
		(c as Node3D).visible = s == "tongkat" or s == "gada"
	if s == "tongkat":
		set_length(2.2)
		return
	_extra = Node3D.new()
	add_child(_extra)
	match s:
		"gada":
			set_length(1.15)
			var head := MeshInstance3D.new()
			var sm := SphereMesh.new()
			sm.radius = 0.2
			sm.height = 0.46
			sm.radial_segments = 12
			sm.rings = 6
			head.mesh = sm
			head.material_override = Art.toon(GOLD, 0.2, 1.6, true)
			head.position.y = length - grip + 0.1
			_extra.add_child(head)
			for k in 6:
				var spike := _cyl(0.035, 0.18, GOLD)
				var a := TAU * k / 6.0
				spike.position = head.position + Vector3(cos(a), 0, sin(a)) * 0.2
				spike.rotation = Vector3(0, -a, PI / 2)
				_extra.add_child(spike)
		"panah":
			var bow := MeshInstance3D.new()
			var t := TorusMesh.new()
			t.inner_radius = 0.6
			t.outer_radius = 0.66
			t.rings = 20
			t.ring_segments = 6
			bow.mesh = t
			bow.material_override = Art.toon(GOLD, 0.15, 1.6, true)
			bow.scale = Vector3(0.45, 1.0, 1.0)
			bow.rotation = Vector3(0, 0, PI / 2)
			_extra.add_child(bow)
			var string := _cyl(0.008, 1.3, Color(0.95, 0.9, 0.8))
			string.position.x = -0.22
			_extra.add_child(string)
		"cakra":
			var disc := MeshInstance3D.new()
			var c := CylinderMesh.new()
			c.top_radius = 0.32
			c.bottom_radius = 0.32
			c.height = 0.05
			c.radial_segments = 16
			disc.mesh = c
			disc.material_override = Art.toon(GOLD, 0.4, 1.6, true)
			disc.rotation.x = PI / 2
			disc.position.y = 0.2
			_extra.add_child(disc)
