extends Node
## Web-only test hook for tools/web_test.js. The game is one <canvas>, so a browser
## test cannot find buttons in the DOM; calling window.sawitProbe() from the page
## writes window.sawitButtons: every visible, enabled button as
## {text, x, y, w, h} in CSS pixels of the page. The test then taps by label
## ("Lanjut", "Siap, Juragan!") instead of guessing coordinates.
## It only reads the scene tree; nothing is registered outside the web build.

var _cb: JavaScriptObject
var _dpr := 1.0


func _ready() -> void:
	if not OS.has_feature("web"):
		return
	_cb = JavaScriptBridge.create_callback(_probe)
	var win := JavaScriptBridge.get_interface("window")
	if win:
		win.sawitProbe = _cb


func _exit_tree() -> void:
	_cb = null


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
