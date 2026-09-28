extends Node
## Web-only test hook for tools/web_test.js. The game is one <canvas>, so a browser
## test cannot find buttons in the DOM; calling window.sawitProbe() from the page
## writes window.sawitButtons: every visible, enabled button as
## {text, x, y, w, h} in CSS pixels of the page. The test then taps by label
## ("Lanjut", "Siap, Juragan!") instead of guessing coordinates.
## It only reads the scene tree; nothing is registered outside the web build.

var _cb: JavaScriptObject
var _cb_audio: JavaScriptObject
var _cb_talk: JavaScriptObject
var _dpr := 1.0


func _ready() -> void:
	if not OS.has_feature("web"):
		return
	_cb = JavaScriptBridge.create_callback(_probe)
	var win := JavaScriptBridge.get_interface("window")
	if win:
		win.sawitProbe = _cb
		# window.sawitAudio() -> window.sawitAudioState: JSON {bus: [playing stream names]}
		_cb_audio = JavaScriptBridge.create_callback(_audio)
		win.sawitAudio = _cb_audio
		# window.sawitTalk() opens a talk dialog with the first land-owning villager
		_cb_talk = JavaScriptBridge.create_callback(_talk)
		win.sawitTalk = _cb_talk


func _exit_tree() -> void:
	_cb = null
	_cb_audio = null
	_cb_talk = null


func _audio(_args: Array) -> void:
	var st := {}
	_collect_audio(get_tree().root, st)
	st["voice_stats"] = Voice.stats
	var win := JavaScriptBridge.get_interface("window")
	if win:
		win.sawitAudioState = JSON.stringify(st)


func _collect_audio(n: Node, st: Dictionary) -> void:
	var playing := false
	var bus := ""
	var sname := ""
	if n is AudioStreamPlayer:
		playing = (n as AudioStreamPlayer).playing
		bus = str((n as AudioStreamPlayer).bus)
		sname = (n as AudioStreamPlayer).stream.resource_path.get_file() if (n as AudioStreamPlayer).stream else ""
	elif n is AudioStreamPlayer3D:
		playing = (n as AudioStreamPlayer3D).playing
		bus = str((n as AudioStreamPlayer3D).bus)
		sname = (n as AudioStreamPlayer3D).stream.resource_path.get_file() if (n as AudioStreamPlayer3D).stream else ""
	if playing:
		if not st.has(bus):
			st[bus] = []
		st[bus].append(sname if sname != "" else str(n.name))
	for c in n.get_children():
		_collect_audio(c, st)


func _talk(_args: Array) -> void:
	var w := _find_world(get_tree().root)
	var win := JavaScriptBridge.get_interface("window")
	if w == null or w.get("deals") == null:
		if win:
			win.sawitTalked = ""
		return
	for vid in GS.villagers:
		if w.npcs.has(vid):
			w.deals.talk(vid)
			if win:
				win.sawitTalked = str(vid)
			return


func _find_world(n: Node) -> Node:
	if n.has_method("try_action") and n.has_method("start_game"):
		return n
	for c in n.get_children():
		var r := _find_world(c)
		if r:
			return r
	return null


func _probe(_args: Array) -> void:
	var out: Array = []
	_dpr = maxf(0.1, float(JavaScriptBridge.eval("window.devicePixelRatio || 1", true)))
	_collect(get_tree().root, out)
	var win := JavaScriptBridge.get_interface("window")
	if win:
		win.sawitButtons = JSON.stringify(out)


func _collect(n: Node, out: Array) -> void:
	if n is CanvasItem and not (n as CanvasItem).is_visible_in_tree():
		return
	if n is BaseButton and not (n as BaseButton).disabled:
		var b := n as BaseButton
		var t: Transform2D = b.get_screen_transform()
		var r := Rect2(t.origin, b.size * t.get_scale())
		# canvas pixels -> CSS pixels
		var dpr := _dpr
		out.append({"text": _label(b), "x": r.position.x / dpr, "y": r.position.y / dpr,
			"w": r.size.x / dpr, "h": r.size.y / dpr})
	for c in n.get_children():
		_collect(c, out)


static func _label(n: Node) -> String:
	var t := ""
	if n is Button:
		t = (n as Button).text
	if t == "":
		for c in n.get_children():
			if c is Label:
				t += (c as Label).text + " "
			elif c is RichTextLabel:
				t += (c as RichTextLabel).get_parsed_text() + " "
			else:
				t += _label(c) + " "
	return t.strip_edges()
