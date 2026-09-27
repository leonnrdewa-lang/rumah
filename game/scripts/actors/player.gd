class_name Player
extends CharacterBody3D
## The palm-oil tycoon. Top-down movement (keyboard, gamepad or the on-screen
## joystick), stays on land, and carries a tool while working.

const SPEED := 5.2
const RUN_MULT := 1.5

var world: Node
var model: Node3D
var anim: CharAnim
var touch_vec := Vector2.ZERO
var locked := false
var facing := Vector3(0, 0, 1)
var _t := 0.0
var _step_t := 0.0
var _tool: Node3D
var _tool_timer := 0.0
var _carry: Node3D


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
	# a little stack of fruit bunches on the back that grows with the load
	_carry = Node3D.new()
	_carry.position = Vector3(0, 0.55, -0.22)
	model.add_child(_carry)
	for i in 3:
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLib.merged_mesh("tbs", false)
		mi.scale = Vector3.ONE * 0.55
		mi.position = Vector3((i - 1) * 0.12, i * 0.1, 0)
		mi.rotation = Vector3(0.3 * i, i * 1.3, 0.2)
		_carry.add_child(mi)
	_carry.visible = false


func update_carry(tbs: int) -> void:
	if _carry == null:
		return
	_carry.visible = tbs > 0
	for i in _carry.get_child_count():
		_carry.get_child(i).visible = tbs > i * 3


func _physics_process(delta: float) -> void:
	_t += delta
	var iv := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if touch_vec.length() > 0.08:
		iv = touch_vec
	if locked:
		iv = Vector2.ZERO
	var dir := Vector3(iv.x, 0, iv.y)
	var amount := minf(1.0, dir.length())
	var spd := SPEED * amount
	if Input.is_action_pressed("run") or touch_vec.length() > 0.95:
		spd *= RUN_MULT
	if amount > 0.05:
		facing = dir.normalized()
		velocity = facing * spd
	else:
		velocity = Vector3.ZERO
	# keep out of the sea: slide along the shoreline instead
	if velocity != Vector3.ZERO and world:
		var p := global_position
		var nx := p + Vector3(velocity.x, 0, 0) * delta * 3.0
		var nz := p + Vector3(0, 0, velocity.z) * delta * 3.0
		if not world.is_walkable(nx.x, nx.z):
			velocity.x = 0.0
		if not world.is_walkable(nz.x, nz.z):
			velocity.z = 0.0
	move_and_slide()
	if world:
		global_position.y = world.height_at(global_position.x, global_position.z)
	var target_yaw := atan2(facing.x, facing.z)
	model.rotation.y = lerp_angle(model.rotation.y, target_yaw, clampf(delta * 14.0, 0.0, 1.0))
	anim.update(delta, velocity.length(), _t)
	if velocity.length() > 0.5:
		_step_t -= delta * velocity.length()
		if _step_t <= 0.0:
			_step_t = 1.7
			Sfx.play("step", randf_range(0.9, 1.1), -18.0)
	if _tool_timer > 0.0:
		_tool_timer -= delta
		if _tool_timer <= 0.0 and _tool:
			_tool.queue_free()
			_tool = null


func do_action_anim(kind: String) -> void:
	var anim_kind := kind
	if kind == "clear":
		anim_kind = "chop"
	anim.play_action(anim_kind)
	_show_tool(kind)


func _show_tool(kind: String) -> void:
	if _tool:
		_tool.queue_free()
		_tool = null
	var hand: Node3D = anim.hand_r if anim.hand_r else model
	_tool = Node3D.new()
	var handle := MeshInstance3D.new()
	var bm := CylinderMesh.new()
	bm.top_radius = 0.025
	bm.bottom_radius = 0.025
	var blade := MeshInstance3D.new()
	var blade_mesh := BoxMesh.new()
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color("8a5a32")
	var steel := StandardMaterial3D.new()
	steel.albedo_color = Color("c9d2d4")
	match kind:
		"harvest":
			bm.height = 2.2
			handle.position.y = 0.9
			blade_mesh.size = Vector3(0.05, 0.28, 0.12)
			blade.position = Vector3(0, 2.0, 0.08)
		"clear":
			bm.height = 0.3
			handle.position.y = 0.1
			blade_mesh.size = Vector3(0.04, 0.45, 0.1)
			blade.position = Vector3(0, 0.45, 0.02)
		_:
			return
	handle.mesh = bm
	handle.material_override = wood
	blade.mesh = blade_mesh
	blade.material_override = steel
	_tool.add_child(handle)
	_tool.add_child(blade)
	hand.add_child(_tool)
	_tool.rotation.x = PI * 0.5 if hand == anim.hand_r else 0.0
	_tool_timer = 0.6
