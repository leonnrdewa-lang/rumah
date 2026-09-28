class_name Rig
extends RefCounted
## Procedural part animation for the cut-up character models (no skeletons).
## Parts are pivot nodes named body/head/arm_l/arm_r/leg_l/leg_r/tail/jaw/...;
## each frame the rig rebuilds their rotation from the rest pose plus layered
## offsets: locomotion (walk cycle), idle breathing, and a timed "action" pose
## (swing, slam, thrust, cast, bite, hurt...). Models face +Z in Godot.

const PARTS := ["body", "head", "arm_l", "arm_r", "leg_l", "leg_r", "tail", "tail_tip",
	"jaw", "claw_l", "claw_r", "weapon"]

var root: Node3D
var p := {}
var rest := {}
var rest_pos := {}
var t := 0.0
var walk := 0.0
var speed := 0.0
var style := "biped"      # biped | quad | fish | float | crab
var action := ""
var action_t := 0.0
var action_len := 0.3
var hurt := 0.0
var lean := 0.0
var squash := 0.0
var stride := 1.0


func _init(model: Node3D, rig_style := "biped") -> void:
	root = model
	style = rig_style
	for n in PARTS:
		var node := model.find_child(n, true, false) as Node3D
		if node:
			p[n] = node
			rest[n] = node.transform.basis
			rest_pos[n] = node.position
	# static Higgsfield meshes have no parts: move the whole body instead
	if p.is_empty() and model.has_meta("hf") and model.get_child_count() > 0:
		var b := model.get_child(0) as Node3D
		p["body"] = b
		rest["body"] = b.transform.basis
		rest_pos["body"] = b.position


func has(n: String) -> bool:
	return p.has(n)


func play(a: String, length := 0.3) -> void:
	action = a
	action_t = 0.0
	action_len = max(length, 0.01)


func hit() -> void:
	hurt = 1.0


func _rot(n: String, x := 0.0, y := 0.0, z := 0.0) -> void:
	if not p.has(n):
		return
	var b: Basis = rest[n] * Basis.from_euler(Vector3(x, y, z))
	(p[n] as Node3D).transform.basis = b


func _pos(n: String, off: Vector3) -> void:
	if p.has(n):
		(p[n] as Node3D).position = rest_pos[n] + off


## `spd` = ground speed in m/s. Call every frame.
func update(delta: float, spd: float) -> void:
	t += delta
	speed = lerp(speed, spd, clamp(delta * 10.0, 0.0, 1.0))
	var moving: float = clamp(speed / 4.0, 0.0, 1.0)
	walk += delta * (4.0 + speed * 2.2) * stride
	hurt = max(0.0, hurt - delta * 4.0)
	if action != "":
		action_t += delta
		if action_t >= action_len:
			action = ""
	var k := action_t / action_len if action != "" else 0.0
	match style:
		"quad":
			_quad(moving, k)
		"fish":
			_fish(moving, k)
		"float":
			_float(k)
		"crab":
			_crab(moving, k)
		_:
			_biped(moving, k)


func _ease_strike(k: float) -> float:
	# windup (0..0.35) then fast strike (0.35..0.55) then hold/recover
	if k < 0.35:
		return -k / 0.35
	if k < 0.55:
		return -1.0 + (k - 0.35) / 0.2 * 2.0
	return 1.0 - (k - 0.55) / 0.45


func _biped(m: float, k: float) -> void:
	var s := sin(walk)
	var breathe := sin(t * 2.2) * 0.03
	var bx := 0.0
	var by := 0.0
	var bz := 0.0
	var arx := s * 0.7 * m
	var alx := -s * 0.7 * m
	var arz := 0.0
	var alz := 0.0
	var hx := 0.0
	var jaw := 0.0
	var bob: float = abs(cos(walk)) * 0.06 * m
	bx += 0.12 * m + lean
	match action:
		"swing_a", "swing_b":
			var dirn := 1.0 if action == "swing_a" else -1.0
			var e := _ease_strike(k)
			by = e * 0.9 * dirn
			arx = -1.5
			arz = -e * 0.9 * dirn
			bx += 0.15
		"slam":
			var e := _ease_strike(k)
			arx = lerp(-1.2, -2.9, clamp(-e, 0.0, 1.0)) if e < 0.0 else lerp(-2.9, -0.5, clamp(e, 0.0, 1.0))
			alx = arx
			bx += -0.25 if e < 0.0 else 0.45 * e
		"thrust":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			alx = -1.6 * e
			arx = 0.4 * e
			by = -0.4 * e
		"cast":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			arx = -2.7 * e
			alx = -2.7 * e
			arz = 0.4 * e
			alz = -0.4 * e
			hx = -0.3 * e
			bx -= 0.15 * e
		"lunge":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			arx = -1.6 * e
			bx += 0.5 * e
		"roar":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			arx = -1.2 * e
			alx = -1.2 * e
			arz = 0.9 * e
			alz = -0.9 * e
			hx = -0.5 * e
			jaw = 0.6 * e
			bx -= 0.2 * e
		"windup":
			arx = -2.6
			alx = -2.6
			bx -= 0.2
		"talk":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			arx = -0.8 * e
			hx = 0.1 * sin(t * 8.0)
	bx -= hurt * 0.4
	_rot("body", bx + breathe, by, bz)
	_pos("body", Vector3(0, bob + squash, 0))
	_rot("head", hx - bx * 0.5, -by * 0.4, 0)
	_rot("arm_r", arx, 0, arz)
	_rot("arm_l", alx, 0, alz)
	_rot("leg_l", s * 0.7 * m, 0, 0)
	_rot("leg_r", -s * 0.7 * m, 0, 0)
	_rot("tail", 0.2 * sin(t * 1.7), 0.5 * sin(t * 1.3 + walk * 0.5), 0)
	_rot("tail_tip", 0, 0.6 * sin(t * 1.9), 0)
	_rot("jaw", jaw, 0, 0)


func _quad(m: float, k: float) -> void:
	var s := sin(walk)
	var bx := 0.0
	var head_x := 0.0
	var jaw := 0.0
	var tail_y := 0.4 * sin(t * 1.5 + walk * 0.5)
	var body_y := 0.0
	match action:
		"bite":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			jaw = 0.8 * (1.0 - clamp((k - 0.5) * 4.0, 0.0, 1.0))
			head_x = 0.3 * e
			bx = 0.1 * e
		"spin", "tail":
			body_y = sin(k * PI) * 0.8
			tail_y = sin(k * TAU * 1.5) * 1.2
		"rear", "roar":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			bx = -0.35 * e
			head_x = -0.4 * e
			jaw = 0.7 * e
		"lunge", "charge":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			bx = 0.2 * e
			jaw = 0.5 * e
	bx -= hurt * 0.2
	_rot("body", bx + sin(t * 2.0) * 0.02, body_y, sin(walk) * 0.04 * m)
	_pos("body", Vector3(0, abs(cos(walk)) * 0.05 * m + squash, 0))
	_rot("head", head_x, sin(t * 0.9) * 0.1, 0)
	_rot("jaw", jaw, 0, 0)
	_rot("leg_l", s * 0.6 * m, 0, 0)
	_rot("leg_r", -s * 0.6 * m, 0, 0)
	_rot("arm_l", -s * 0.6 * m, 0, 0)
	_rot("arm_r", s * 0.6 * m, 0, 0)
	_rot("tail", 0, tail_y, 0)
	_rot("tail_tip", 0, tail_y * 1.2, 0)


func _fish(m: float, k: float) -> void:
	var sw := sin(walk * 0.8)
	var jaw := 0.1 + 0.05 * sin(t * 3.0)
	var bx := 0.0
	var head_x := 0.0
	match action:
		"bite", "lunge":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			jaw = 0.9 * e
			head_x = -0.2 * e
		"rear", "roar":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			bx = -0.6 * e
			jaw = 0.8 * e
	_rot("body", bx - hurt * 0.2, sw * 0.12 * (0.4 + m), 0)
	_pos("body", Vector3(0, sin(t * 1.6) * 0.08 + squash, 0))
	_rot("head", head_x, -sw * 0.1, 0)
	_rot("jaw", jaw, 0, 0)
	_rot("tail", 0, -sw * 0.5, 0)
	_rot("tail_tip", 0, -sw * 0.7, 0)
	_rot("arm_l", 0, 0, 0.2 + sw * 0.2)
	_rot("arm_r", 0, 0, -0.2 - sw * 0.2)


func _float(k: float) -> void:
	var jaw := 0.15 + 0.1 * sin(t * 5.0)
	if action != "":
		jaw = 0.7 * sin(clamp(k, 0.0, 1.0) * PI)
	_rot("body", sin(t * 2.3) * 0.12 - hurt * 0.4, sin(t * 1.1) * 0.2, sin(t * 1.7) * 0.1)
	_pos("body", Vector3(0, sin(t * 2.6) * 0.15, 0))
	_rot("jaw", jaw, 0, 0)


func _crab(m: float, k: float) -> void:
	var s := sin(walk * 1.4)
	var cl := 0.0
	var cr := 0.0
	var al := 0.0
	var ar := 0.0
	match action:
		"snap":
			var e := sin(clamp(k, 0.0, 1.0) * PI)
			ar = -0.9 * e
			al = -0.9 * e
			cl = 0.6 * (1.0 - e)
			cr = cl
		"guard":
			ar = -0.4
			al = -0.4
		"windup":
			ar = -1.2
			al = -1.2
			cl = 0.6
			cr = 0.6
	_rot("body", -hurt * 0.3, 0, s * 0.06 * m)
	_pos("body", Vector3(0, abs(s) * 0.05 * m + squash, 0))
	_rot("arm_l", al, 0, 0)
	_rot("arm_r", ar, 0, 0)
	_rot("claw_l", cl + 0.1 * sin(t * 3.0), 0, 0)
	_rot("claw_r", cr + 0.1 * sin(t * 3.3), 0, 0)
	_rot("leg_l", 0, 0, s * 0.3 * m)
	_rot("leg_r", 0, 0, -s * 0.3 * m)
