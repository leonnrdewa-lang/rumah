class_name Player
extends CharacterBody3D
## The palm-oil tycoon. Top-down movement (keyboard, gamepad or the on-screen
## joystick) with a little acceleration, stays on land, stands still while a
## work animation plays and carries the harvest on their back.

## 5.2 m/s is a run for a 1.1 m chibi (the walk clip would need 8x playback),
## so normal movement shows the run clip on purpose; the walk shows below
## ~1.5 m/s (half-pushed stick, speeding up, villagers). See CharAnim.WALK_TO_RUN.
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
	# slide around round trunks even when walking almost straight into them
	wall_min_slide_angle = deg_to_rad(3.0)
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
	# a rattan basket on the back with fruit bunches peeking out, filling up
	# with the load; rides on the chest bone of skinned models so it sways
	_carry = Node3D.new()
	_carry.name = "Carry"
	var basket := MeshInstance3D.new()
	basket.name = "Basket"
	basket.mesh = CharAnim.tool_mesh("basket")
	_carry.add_child(basket)
	var spots := [Vector3(-0.04, -0.07, 0.01), Vector3(0.06, -0.03, -0.03), Vector3(-0.01, 0.02, -0.01)]
	for i in 3:
		var mi := MeshInstance3D.new()
		mi.name = "Bunch%d" % i
		mi.mesh = ModelLib.merged_mesh("tbs", false)
		mi.scale = Vector3.ONE * 0.36
		mi.position = spots[i]
		mi.rotation = Vector3(0.25 * (i - 1), i * 2.1, 0.15 * (1 - i))
		_carry.add_child(mi)
	if not anim.attach_to_bone("chest", _carry, Vector3(0, 0.02, -0.27)):
		_carry.position = Vector3(0, 0.5, -0.27)
		model.add_child(_carry)
	_carry.visible = false


func update_carry(tbs: int) -> void:
	if _carry == null:
		return
	_carry.visible = tbs > 0
	anim.back_load = tbs > 0   # a pole carried on the shoulder leans out past the basket
	for i in 3:
		var b := _carry.get_node_or_null("Bunch%d" % i)
		if b:
			b.visible = tbs > i * 3


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
	# speed ramps up and down (a touch of weight), but the heading follows the
	# stick at once so the controls stay as snappy as before; the model turns
	# smoothly on its own in CharAnim.turn_towards
	var hv := Vector3(velocity.x, 0, velocity.z)
	if global_position.distance_to(_last_pos) > 2.5:
		hv = Vector3.ZERO   # teleported (new day, cutscene, debug): no momentum
	var cur := hv.length()
	var target := want.length()
	var new_speed := move_toward(cur, target, (ACCEL if target > cur else DECEL) * delta)
	if target > 0.01:
		hv = want / target * new_speed
	elif cur > 0.001:
		hv = hv / cur * new_speed
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
