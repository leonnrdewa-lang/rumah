class_name Interactable
extends Node3D
## Anything Hanoman can press Interact on (NPCs, the well, gates, reward orbs,
## shop items). `action` is called with this node.

var action: Callable
var prompt := ""
var active := true:
	set(v):
		active = v
		set_meta("active", v)


static func make(p_prompt: String, p_action: Callable) -> Interactable:
	var i := Interactable.new()
	i.prompt = p_prompt
	i.action = p_action
	i.set_meta("prompt", p_prompt)
	i.set_meta("active", true)
	i.add_to_group("interactable")
	return i


func set_prompt(p: String) -> void:
	prompt = p
	set_meta("prompt", p)


func interact() -> void:
	if active and action.is_valid():
		action.call(self)
