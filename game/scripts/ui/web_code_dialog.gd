extends Node
## Web build: the save code ("Kode Save") in an HTML <dialog> over the game canvas.
##
## Why not Godot controls or window.prompt(): the game runs inside the claude.ai
## Artifact iframe, which is sandboxed without allow-modals, so prompt() returns null
## at once (the title button "Masukkan Kode Save" did nothing), and the iframe does
## not grant the Clipboard API that copying out of a Godot LineEdit relies on. A real
## <textarea> gets the phone's own keyboard, long-press Tempel/Salin (Paste/Copy) and
## Ctrl+V / Ctrl+C on PC; "Salin kode" falls back to document.execCommand("copy"),
## which works in the sandbox.
##
## showModal() puts the dialog in the browser's top layer, above the canvas even while
## the canvas is fullscreen, and makes the canvas inert (no taps reach the game). The
## dialog also stops its key / pointer / paste events from bubbling to the window
## listeners Godot uses. While it is open an empty modal holds the Godot side (world
## paused, player locked, HUD out of the way); either side closing closes the other.
## ui.gd creates this node on first use (_web_code) and keeps the Godot panels for
## the other platforms.

## Installed once into the page as window.sawitCode = {open, close, fail}.
## open(mode, code, cb, hasSave) -> bool; cb(kind, text) with kind "submit" (import:
## the pasted text), "cancel" (Batal / Esc) or "closed" (export closed).
const JS := r"""
(function () {
  if (window.sawitCode) return;
  var ID = "sawit-code";
  var CSS = [
    "#sawit-code{position:fixed;inset:auto;top:0;left:0;width:100%;height:100%;max-width:none;max-height:none;margin:0;padding:0;border:0;background:transparent;overflow:hidden;box-sizing:border-box;color:#4a2f1d;font-family:'Fredoka','Trebuchet MS','Segoe UI',system-ui,sans-serif;-webkit-text-size-adjust:100%}",
    "#sawit-code[open],#sawit-code.sc-fallback{display:flex;align-items:center;justify-content:center}",
    "#sawit-code.sc-fallback{z-index:2147483647;background:rgba(34,20,8,.55)}",
    "#sawit-code::backdrop{background:rgba(34,20,8,.55)}",
    "#sawit-code .sc-card{box-sizing:border-box;width:min(560px,calc(100% - 24px));max-height:calc(100% - 20px);overflow:auto;overscroll-behavior:contain;background:#fcf2dd;border:3px solid #d8c29a;border-radius:24px;padding:16px 20px 16px;box-shadow:0 8px 28px rgba(40,22,8,.35);display:flex;flex-direction:column;gap:9px;outline:none}",
    "#sawit-code h2{margin:0;font-size:27px;line-height:1.15;font-weight:600;color:#6a3a18;text-align:center}",
    "#sawit-code p{margin:0;font-size:16.5px;line-height:1.35;font-weight:500}",
    "#sawit-code p.sc-warn{color:#a0452c}",
    "#sawit-code textarea{box-sizing:border-box;width:100%;min-height:88px;flex:none;resize:none;margin:2px 0 0;font:16px/1.35 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#3e2617;background:#fffaf0;border:2px solid #b8986a;border-radius:14px;padding:8px 11px;word-break:break-all;overflow-wrap:anywhere;white-space:pre-wrap;-webkit-user-select:text;user-select:text}",
    "#sawit-code textarea:focus{outline:none;border-color:#e8953a;box-shadow:0 0 0 3px rgba(232,149,58,.25)}",
    "#sawit-code .sc-msg{min-height:1.3em;font-size:15.5px;font-weight:600;color:#8a6a4a}",
    "#sawit-code .sc-msg.good{color:#4f7d2c}",
    "#sawit-code .sc-msg.bad{color:#c9563c}",
    "#sawit-code .sc-row{display:flex;flex-wrap:wrap;gap:10px;justify-content:center}",
    "#sawit-code button{font:inherit;font-size:19px;font-weight:600;min-height:48px;min-width:112px;padding:6px 22px;border-radius:999px;border:2px solid #d8c29a;background:#fffaf0;color:#4a2f1d;box-shadow:0 2px 5px rgba(60,35,12,.18);cursor:pointer;touch-action:manipulation;-webkit-tap-highlight-color:transparent}",
    "#sawit-code button:hover{border-color:#e8953a;background:#fff5dc}",
    "#sawit-code button:active{background:#f1e0bd;border-color:#b8986a}",
    "#sawit-code button:focus-visible{outline:3px solid #e8953a;outline-offset:2px}",
    "#sawit-code button.sc-primary{background:#7fa047;border-color:#5f8336;color:#fffaf0}",
    "#sawit-code button.sc-primary:hover{background:#8db552;border-color:#e8953a}",
    "#sawit-code button.sc-primary:active{background:#6b8a3a}",
    "#sawit-code button:disabled{opacity:.55;cursor:default}",
    "@media (max-height:480px){#sawit-code .sc-card{padding:10px 16px 12px;gap:6px;border-radius:20px}#sawit-code h2{font-size:22px}#sawit-code p{font-size:15px;line-height:1.3}#sawit-code textarea{min-height:66px}#sawit-code button{min-height:44px;font-size:18px}}"
  ].join("\n");
  var HINT_COPY = "Tidak bisa menyalin otomatis di sini. Tekan lama kotak kode (atau blok semua isinya), lalu pilih Salin / Copy.";
  var HINT_PASTE = "Tekan lama kotak di atas, lalu pilih Tempel / Paste.";
  var st = {dlg: null, cb: null, mode: "", ta: null, msg: null, btns: [], timer: 0};
  var STOP = ["keydown", "keyup", "keypress", "pointerdown", "pointermove", "pointerup", "pointercancel",
    "mousedown", "mousemove", "mouseup", "click", "dblclick", "wheel", "touchstart", "touchmove", "touchend",
    "touchcancel", "paste", "copy", "cut", "input", "contextmenu", "focusin", "focusout"];

  function mk(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function say(text, kind) {
    if (!st.msg) return;
    st.msg.textContent = text || "";
    st.msg.className = "sc-msg" + (kind ? " " + kind : "");
  }
  function busy(on) {
    st.btns.forEach(function (b) { b.disabled = on; });
    if (st.ta && st.mode === "import") st.ta.readOnly = on;
    clearTimeout(st.timer);
    if (on) st.timer = setTimeout(function () { busy(false); say("Game tidak menjawab. Coba tekan Pakai kode lagi.", "bad"); }, 8000);
  }
  function emit(kind, text) {
    if (!st.cb) return;
    try { st.cb(kind, text || ""); } catch (e) { console.error(e); }
  }
  function allowed(feature) {
    // Permissions Policy (Chrome): a cross-origin iframe without allow="clipboard-read" is refused
    var p = document.permissionsPolicy || document.featurePolicy;
    try { return !p || typeof p.allowsFeature !== "function" || p.allowsFeature(feature); } catch (e) { return true; }
  }
  function gameCanvas() { return document.getElementById("canvas") || document.querySelector("canvas"); }
  function fit() {
    // keep the card inside the visible area while a phone keyboard is up
    var d = st.dlg, vv = window.visualViewport;
    if (!d || !vv) return;
    d.style.top = vv.offsetTop + "px";
    d.style.left = vv.offsetLeft + "px";
    d.style.width = vv.width + "px";
    d.style.height = vv.height + "px";
    if (st.ta && document.activeElement === st.ta && st.ta.scrollIntoView) st.ta.scrollIntoView({block: "nearest"});
  }
  function close(kind) {
    var d = st.dlg;
    if (!d) return false;
    var cb = st.cb;
    clearTimeout(st.timer);
    st.dlg = null; st.ta = null; st.msg = null; st.btns = []; st.cb = null;
    if (window.visualViewport) {
      window.visualViewport.removeEventListener("resize", fit);
      window.visualViewport.removeEventListener("scroll", fit);
    }
    try { if (d.open && typeof d.close === "function") d.close(); } catch (e) {}
    if (d.parentNode) d.parentNode.removeChild(d);
    var c = gameCanvas();
    if (c) { try { c.focus({preventScroll: true}); } catch (e) {} }
    if (kind && cb) { try { cb(kind, ""); } catch (e) { console.error(e); } }
    return true;
  }
  function selectAll() {
    var ta = st.ta;
    if (!ta) return;
    try { ta.focus({preventScroll: true}); } catch (e) {}
    try { ta.select(); ta.setSelectionRange(0, ta.value.length); } catch (e) {}
  }
  function copy(auto) {
    var ta = st.ta;
    if (!ta) return;
    var text = ta.value;
    selectAll();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    var good = auto ? "Kode sudah disalin. Tempel di chat atau catatan untuk disimpan."
                    : "Tersalin! Tempel di chat atau catatan untuk disimpan.";
    if (ok) { say(good, "good"); return; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { if (st.ta === ta) say(good, "good"); },
        function () { if (st.ta === ta && !auto) say(HINT_COPY, "bad"); });
    } else if (!auto) {
      say(HINT_COPY, "bad");
    }
  }
  function paste() {
    var ta = st.ta;
    if (!ta) return;
    if (!navigator.clipboard || !navigator.clipboard.readText) { say(HINT_PASTE); ta.focus(); return; }
    navigator.clipboard.readText().then(function (t) {
      if (st.ta !== ta) return;
      t = (t || "").trim();
      if (!t) { say("Clipboard kosong. Salin dulu kodenya dari perangkat lama.", "bad"); return; }
      ta.value = t;
      if (t.indexOf("SAWIT1-") === 0) say("Kode ditempel. Tekan Pakai kode.", "good");
      else say("Teks ditempel, tapi sepertinya bukan kode save (harus diawali SAWIT1-).", "bad");
    }, function () {
      if (st.ta !== ta) return;
      say("Browser tidak mengizinkan tombol Tempel di sini. " + HINT_PASTE, "bad");
      try { ta.focus(); } catch (e) {}
    });
  }
  function submit() {
    var ta = st.ta;
    if (!ta || ta.readOnly) return;
    var t = ta.value.replace(/\s+/g, "");
    if (!t) { say("Kotaknya masih kosong. Tempel kode save dulu.", "bad"); ta.focus(); return; }
    busy(true);
    say("Memeriksa kode...");
    emit("submit", t);
  }
  function button(text, primary, fn) {
    var b = mk("button", primary ? "sc-primary" : "", text);
    b.type = "button";
    b.addEventListener("click", function (e) { e.preventDefault(); fn(); });
    st.btns.push(b);
    return b;
  }

  function open(mode, code, cb, hasSave) {
    close(null);
    var style = document.getElementById(ID + "-css");
    if (!style) {
      style = mk("style");
      style.id = ID + "-css";
      style.textContent = CSS;
      (document.head || document.body).appendChild(style);
    }
    var modal = typeof HTMLDialogElement === "function" && typeof document.createElement("dialog").showModal === "function";
    var d = mk(modal ? "dialog" : "div");
    d.id = ID;
    d.setAttribute("role", "dialog");
    d.setAttribute("aria-modal", "true");
    d.setAttribute("aria-labelledby", ID + "-title");
    var card = mk("div", "sc-card");
    card.tabIndex = -1;
    card.setAttribute("autofocus", "");
    d.appendChild(card);
    st.dlg = d; st.cb = cb || null; st.mode = mode; st.btns = [];
    var h = mk("h2", "", mode === "import" ? "Masukkan Kode Save" : "Kode Save");
    h.id = ID + "-title";
    card.appendChild(h);
    var ta = mk("textarea");
    ta.rows = 3;
    ta.spellcheck = false;
    ta.setAttribute("autocomplete", "off");
    ta.setAttribute("autocorrect", "off");
    ta.setAttribute("autocapitalize", "off");
    ta.setAttribute("aria-label", "Kode save");
    st.ta = ta;
    var row = mk("div", "sc-row");
    if (mode === "import") {
      card.appendChild(mk("p", "", "Tempel kode save (diawali SAWIT1-) dari HP atau browser lain ke kotak di bawah, lalu tekan Pakai kode. Di HP: tekan lama kotaknya, pilih Tempel."));
      if (hasSave) card.appendChild(mk("p", "sc-warn", "Save yang ada di perangkat ini akan diganti dengan save dari kode."));
      ta.placeholder = "SAWIT1-...";
      ta.addEventListener("input", function () { if (st.msg && / bad/.test(st.msg.className)) say(""); });
      ta.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); }
      });
      if (navigator.clipboard && navigator.clipboard.readText && allowed("clipboard-read")) row.appendChild(button("Tempel", false, paste));
      row.appendChild(button("Batal", false, function () { close("cancel"); }));
      row.appendChild(button("Pakai kode", true, submit));
    } else {
      card.appendChild(mk("p", "", "Kode ini berisi seluruh progresmu. Salin lalu simpan, misalnya kirim ke chat sendiri."));
      card.appendChild(mk("p", "", "Di HP atau browser lain: buka game ini, pilih “Masukkan Kode Save” di layar judul, lalu tempel kodenya."));
      ta.readOnly = true;
      ta.value = code || "";
      ta.addEventListener("focus", function () { setTimeout(selectAll, 0); });
      row.appendChild(button("Tutup", false, function () { close("closed"); }));
      row.appendChild(button("Salin kode", true, function () { copy(false); }));
    }
    card.appendChild(ta);
    st.msg = mk("div", "sc-msg");
    st.msg.setAttribute("aria-live", "polite");
    card.appendChild(st.msg);
    card.appendChild(row);
    // the game listens on window (pointermove, mouseup, paste): keep the dialog's events to itself
    STOP.forEach(function (n) { d.addEventListener(n, function (e) { e.stopPropagation(); }); });
    d.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); close(st.mode === "import" ? "cancel" : "closed"); }
    });
    d.addEventListener("cancel", function (e) { e.preventDefault(); close(st.mode === "import" ? "cancel" : "closed"); });
    document.body.appendChild(d);
    if (modal) {
      try { d.showModal(); } catch (e) { modal = false; }
    }
    if (!modal) {
      d.classList.add("sc-fallback");
      // a plain page element cannot draw over a fullscreen canvas
      var fs = document.fullscreenElement || document.webkitFullscreenElement;
      if (fs && fs.tagName === "CANVAS") {
        try { (document.exitFullscreen || document.webkitExitFullscreen).call(document); } catch (e) {}
      }
    }
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", fit);
      window.visualViewport.addEventListener("scroll", fit);
      fit();
    }
    if (mode === "import") {
      // PC: ready for Ctrl+V; phones: no keyboard until the box is tapped
      if (window.matchMedia && matchMedia("(pointer: fine)").matches) ta.focus();
      else card.focus({preventScroll: true});
    } else {
      copy(true);
    }
    return true;
  }

  window.sawitCode = {
    open: open,
    close: function () { return close(null); },
    fail: function (text) {
      if (!st.dlg) return;
      busy(false);
      say(text, "bad");
      if (st.ta) { try { st.ta.focus({preventScroll: true}); st.ta.select(); } catch (e) {} }
    },
    isOpen: function () { return !!st.dlg; }
  };
})();
"""

var ui: Node
var _cb: JavaScriptObject
var _holder: Control
var _open := false
var _serial := 0  ## one per dialog, so a late event from a closed one is ignored


func open(mode: String, code := "") -> bool:
	## mode "export": shows `code` to copy; "import": asks for a code and, when it is
	## valid, continues that game. False when the page could not show the dialog
	## (ui.gd then uses its Godot panel).
	if not OS.has_feature("web") or not _install():
		return false
	var sc = JavaScriptBridge.get_interface("sawitCode")
	if sc == null:
		return false
	_close_page()
	_release_holder()
	_serial += 1
	_cb = JavaScriptBridge.create_callback(_on_js)
	var h := Control.new()
	h.name = "WebCodeHolder"
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_holder = h
	ui._open_modal(h, false, _on_holder_closed.bind(h))
	_open = bool(sc.open(mode, code, _cb, GS.has_save()))
	if not _open:
		_release_holder()
	return _open


func _install() -> bool:
	if not bool(JavaScriptBridge.eval("typeof window.sawitCode === 'object'", true)):
		JavaScriptBridge.eval(JS, true)
	return bool(JavaScriptBridge.eval("typeof window.sawitCode === 'object'", true))


func _on_js(args: Array) -> void:
	# runs inside the browser's click handler: act on it in the next frame
	var kind := str(args[0]) if args.size() > 0 else ""
	var text := str(args[1]) if args.size() > 1 else ""
	call_deferred("_handle", kind, text, _serial)


func _handle(kind: String, text: String, serial: int) -> void:
	if not _open or serial != _serial:
		return
	match kind:
		"submit":
			if GS.import_code(text):
				_close_page()
				_release_holder()
				ui.toast("Kode save diterima! Melanjutkan permainan...", "good")
				ui.world.start_game(true)
			else:
				var sc = JavaScriptBridge.get_interface("sawitCode")
				if sc:
					sc.fail("Kode save tidak valid atau rusak. Pastikan kodenya lengkap, dari SAWIT1- sampai huruf terakhir.")
		_:
			# Batal / Tutup / Esc: the page already closed its dialog
			_open = false
			_release_holder()


func _close_page() -> void:
	if _open:
		_open = false
		var sc = JavaScriptBridge.get_interface("sawitCode")
		if sc:
			sc.close()


func _release_holder() -> void:
	var h := _holder
	_holder = null
	if h and is_instance_valid(h) and ui.modal == h:
		ui._close_modal()


func _on_holder_closed(h: Control) -> void:
	# the Godot side closed first (another panel opened, back to the title...)
	if h != _holder:
		return
	_holder = null
	_close_page()
