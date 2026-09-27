class_name Player
extends CharacterBody3D
## The palm-oil tycoon. Top-down movement (keyboard, gamepad or the on-screen
## joystick) with a little acceleration, stays on land, stands still while a
## work animation plays and carries the harvest on their back.

const SPEED := 5.2
const RUN_MULT := 1.5
const ACCEL := 30.0     # m/s^2 speeding up
const DECEL := 40.0     # m/s^2 slowing down
const TURN_RATE := 13.0 # rad/s

var world: Node
var model: Node3D
var anim: CharAnim
var touch_vec := Vector2.ZERO
var locked := false
var facing := Vector3(0, 0, 1)
var _t := 0.0
var _step_t := 0.0
var _carry: Node3D
var _face_pos := Vector3.ZERO
var _face_t := 0.0
var _last_pos := Vector3.ZERO


func _ready() -> void:
	motion_mode = CharacterBody3D.MOTION_MODE_FLOATING
	collision_layer = 2
	collision_mask = 1
	var shape := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.32
	cap.height = 1.2
	shape.shape = cap
	shape.position.y = 0.6
	add_child(shape)
	model = ModelLib.instance("char_player", false)
	add_child(model)
	anim = CharAnim.new(model)
	_build_carry()


func _build_carry() -> void:
	# a little stack of fruit bunches on the back that grows with the load;
	# rides on the chest bone of skinned models so it sways with the body
	_carry = Node3D.new()
	_carry.name = "Carry"
	for i in 3:
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLib.merged_mesh("tbs", false)
		mi.scale = Vector3.ONE * 0.55
		mi.position = Vector3((i - 1) * 0.12, i * 0.1, 0)
		mi.rotation = Vector3(0.3 * i, i * 1.3, 0.2)
		_carry.add_child(mi)
	if not anim.attach_to_bone("chest", _carry, Vector3(0, -0.02, -0.21)):
		_carry.position = Vector3(0, 0.55, -0.22)
		model.add_child(_carry)
	_carry.visible = false


func update_carry(tbs: int) -> void:
	if _carry == null:
		return
	_carry.visible = tbs > 0
	for i in _carry.get_child_count():
		_carry.get_child(i).visible = tbs > i * 3


func face_point(p: Vector3, seconds := 0.2) -> void:
	## Turn toward a point while standing (e.g. the villager you talk to).
	_face_pos = p
	_face_t = seconds


func _physics_process(delta: float) -> void:
	_t += delta
	var iv := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if touch_vec.length() > 0.08:
		iv = touch_vec
	if locked or anim.is_busy():
		iv = Vector2.ZERO
	var dir := Vector3(iv.x, 0, iv.y)
	var amount := minf(1.0, dir.length())
	var spd := SPEED * amount
	if Input.is_action_pressed("run") or touch_vec.length() > 0.95:
		spd *= RUN_MULT
	var want := Vector3.ZERO
	if amount > 0.05:
		facing = dir.normalized()
		want = facing * spd
	elif _face_t > 0.0:
		var fd := _face_pos - global_position
		fd.y = 0.0
		if fd.length() > 0.2:
			facing = fd.normalized()
	_face_t -= delta
	var hv := Vector3(velocity.x, 0, velocity.z)
	if global_position.distance_to(_last_pos) > 2.5:
		hv = Vector3.ZERO   # teleported (new day, cutscene, debug): no momentum
	hv = hv.move_toward(want, (ACCEL if want.length() > hv.length() else DECEL) * delta)
	velocity = hv
	# keep out of the sea: slide along the shoreline instead (probe with the
	# wanted velocity so the look-ahead matches full speed while accelerating)
	if velocity != Vector3.ZERO and world:
		var p := global_position
		var px := want.x if absf(want.x) > absf(velocity.x) else velocity.x
		var pz := want.z if absf(want.z) > absf(velocity.z) else velocity.z
		var nx := p + Vector3(px, 0, 0) * delta * 3.0
		var nz := p + Vector3(0, 0, pz) * delta * 3.0
		if not world.is_walkable(nx.x, nx.z):
			velocity.x = 0.0
		if not world.is_walkable(nz.x, nz.z):
			velocity.z = 0.0
	move_and_slide()
	if world:
		global_position.y = world.height_at(global_position.x, global_position.z)
	_last_pos = global_position
	var ground_speed := Vector2(velocity.x, velocity.z).length()
	anim.turn_towards(atan2(facing.x, facing.z), delta, TURN_RATE)
	_update_look()
	anim.update(delta, ground_speed, _t)
	if ground_speed > 0.5:
		_step_t -= delta * ground_speed
		if _step_t <= 0.0:
			_step_t = 1.7
			Sfx.play("step", randf_range(0.9, 1.1), -18.0)


func _update_look() -> void:
	# glance at whatever the action prompt points at (a palm, a villager, a door)
	if _face_t > 0.0:
		anim.look_at_point(_face_pos + Vector3(0, 0.9, 0))
		return
	if world == null or anim.is_busy():
		return
	var tg = world.get("target")
	if tg is Dictionary and not tg.is_empty() and tg.has("_pos"):
		var p: Vector3 = tg["_pos"]
		anim.look_at_point(p + Vector3(0, 0.9 if tg.has("npc") else 0.5, 0))


func do_action_anim(kind: String) -> void:
	## Work animation for a tile action (clear/plant/fert/harvest): plays the
	## clip, shows the tool in hand and holds the player still until it ends.
	anim.play_action(kind)
