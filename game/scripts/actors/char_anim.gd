class_name CharAnim
extends RefCounted
## Procedural chibi animation: swings the ArmL/ArmR/LegL/LegR/Head nodes that
## the Blender character scripts create, plus a little body bob.

var root: Node3D
var hips: Node3D
var arm_l: Node3D
var arm_r: Node3D
var leg_l: Node3D
var leg_r: Node3D
var head: Node3D
var hand_r: Node3D
var hips_y := 0.3
var phase := 0.0
var action_t := 0.0   # >0 while doing an action (tool swing)
var action_kind := ""
var talk_t := 0.0
var idle_seed := randf() * 10.0


func _init(model: Node3D) -> void:
	root = model
	hips = model.find_child("Hips", true, false)
	arm_l = model.find_child("ArmL", true, false)
	arm_r = model.find_child("ArmR", true, false)
	leg_l = model.find_child("LegL", true, false)
	leg_r = model.find_child("LegR", true, false)
	head = model.find_child("Head", true, false)
	hand_r = model.find_child("HandR", true, false)
	if hips:
		hips_y = hips.position.y


func play_action(kind: String, duration := 0.45) -> void:
	action_kind = kind
	action_t = duration


func update(delta: float, speed: float, t: float) -> void:
	var moving := speed > 0.15
	if moving:
		phase += delta * (5.0 + speed * 1.6)
	else:
		phase = lerpf(phase, round(phase / PI) * PI, delta * 8.0)
	var swing := sin(phase) * (0.75 if moving else 0.0)
	var bob := absf(sin(phase)) * 0.05 if moving else sin(t * 2.0 + idle_seed) * 0.008
	if hips:
		hips.position.y = hips_y + bob
		hips.rotation.z = sin(phase) * 0.04 if moving else 0.0
	if leg_l:
		leg_l.rotation.x = swing
	if leg_r:
		leg_r.rotation.x = -swing
	var arm_swing := swing * 0.9
	var arm_l_x := -arm_swing
	var arm_r_x := arm_swing
	var arm_r_z := 0.0
	if action_t > 0.0:
		action_t -= delta
		var k := clampf(action_t / 0.45, 0.0, 1.0)
		match action_kind:
			"chop", "harvest":
				arm_r_x = lerpf(0.4, -2.6, k)
				arm_l_x = lerpf(0.2, -1.2, k) * 0.5
			"plant", "fert":
				arm_r_x = -1.2 * sin(k * PI)
				arm_l_x = -1.2 * sin(k * PI)
				if hips:
					hips.rotation.x = 0.35 * sin(k * PI)
			"cheer":
				arm_r_z = 2.6 * sin(k * PI)
				arm_r_x = -0.3
				arm_l_x = -0.3
	elif hips:
		hips.rotation.x = lerpf(hips.rotation.x, 0.0, delta * 10.0)
	if arm_l:
		arm_l.rotation.x = arm_l_x
		arm_l.rotation.z = lerpf(arm_l.rotation.z, 0.0, delta * 10.0)
	if arm_r:
		arm_r.rotation.x = arm_r_x
		arm_r.rotation.z = -arm_r_z
	if head:
		if talk_t > 0.0:
			talk_t -= delta
			head.rotation.x = sin(t * 9.0) * 0.08
		else:
			head.rotation.x = lerpf(head.rotation.x, 0.0, delta * 6.0)
		head.rotation.y = sin(t * 0.7 + idle_seed) * (0.05 if moving else 0.18)
