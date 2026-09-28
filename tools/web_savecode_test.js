// Save code ("Kode Save") on the exported web build, in headless Chromium: top-level, and inside a
// cross-origin iframe sandboxed like the claude.ai Artifact host (no allow-modals, no clipboard
// permission), on a desktop and on an Android phone (touch).
//
// Each run plays a little (new game, intro, walk; money/day set through the ?sawit_test hook of
// scripts/debug/web_probe.gd so the save differs from a new game), opens Menu -> "Kode Save (pindah
// HP)", reads the code from the page <dialog> (scripts/ui/web_code_dialog.gd), presses "Salin kode",
// checks that keys / pointer moves / paste inside the dialog never reach the game's listeners and that
// "Tutup" / Esc hand the game back. Then a fresh browser context (empty storage) presses "Masukkan
// Kode Save" on the title screen, tries "Batal" and a broken code, pastes the real code (Ctrl+V from
// the clipboard at top level, typed into the textarea elsewhere) and checks that the game continues
// with the same money, day and time.
//
// Usage: NODE_PATH=$(npm root -g) node tools/web_savecode_test.js <build_dir> [out_dir] [--only=top,iframe,phone]
//   <build_dir>: docs/ or dist/artifact/ (an artifact page without <html> is wrapped the way the host does)
const { chromium } = require("playwright");
const http = require("http");
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
const DIR = path.resolve(args.find((a) => !a.startsWith("--")) || "docs");
const OUT = args.filter((a) => !a.startsWith("--"))[1] || "/tmp";
const ONLY = (args.find((a) => a.startsWith("--only=")) || "--only=top,iframe,phone").slice(7).split(",");
const GAME_PORT = 8093, HOST_PORT = 8094;
const GAME = `http://127.0.0.1:${GAME_PORT}`;
const MONEY = 1234567, DAY = 4;
let failures = 0;
const browsers = new Set();  // closed after each run, also when a step throws

function check(ok, name, what) {
  console.log(`${name}: ${ok ? "ok" : "FAIL"} - ${what}`);
  if (!ok) failures++;
  return ok;
}

// ------------------------------------------------------------------ servers
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".png": "image/png",
  ".txt": "text/plain", ".gz": "application/octet-stream", ".ogg": "audio/ogg", ".json": "application/json" };

function page(root) {
  const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
  if (/^\s*<!doctype/i.test(html)) return html;
  // dist/artifact is a page body; the Artifact host wraps it in a document skeleton
  return "<!doctype html>\n<html lang=\"id\"><head><meta charset=\"utf-8\">\n" +
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"></head><body>\n" + html + "\n</body></html>\n";
}

function serve(port, handler) {
  return new Promise((res) => { const s = http.createServer(handler); s.listen(port, "127.0.0.1", () => res(s)); });
}

function gameServer() {
  const index = page(DIR);
  return serve(GAME_PORT, (req, rsp) => {
    const u = decodeURIComponent(req.url.split("?")[0]);
    if (u === "/" || u === "/index.html") { rsp.writeHead(200, { "Content-Type": TYPES[".html"] }); rsp.end(index); return; }
    const f = path.join(DIR, path.normalize(u));
    if (!f.startsWith(DIR)) { rsp.writeHead(403); rsp.end(); return; }
    fs.readFile(f, (err, data) => {
      if (err) { rsp.writeHead(404); rsp.end(); return; }
      rsp.writeHead(200, { "Content-Type": TYPES[path.extname(f)] || "application/octet-stream" });
      rsp.end(data);
    });
  });
}

function hostServer() {
  // another origin, like claude.ai around the Artifact's iframe
  const html = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>html,body{margin:0;height:100%;overflow:hidden;background:#222}iframe{border:0;width:100%;height:100%;display:block}</style>
</head><body><iframe id="game" src="${GAME}/index.html?sawit_test=1" allow="fullscreen; autoplay"
 sandbox="allow-scripts allow-same-origin allow-pointer-lock allow-downloads allow-popups"></iframe></body></html>`;
  return serve(HOST_PORT, (req, rsp) => { rsp.writeHead(200, { "Content-Type": TYPES[".html"] }); rsp.end(html); });
}

// ------------------------------------------------------------------ game helpers
class Game {
  constructor(name, page, frame, offset, touch) {
    Object.assign(this, { name, page, frame, offset, touch });
  }

  async buttons() {
    return this.frame.evaluate(() => { window.sawitProbe(); return JSON.parse(window.sawitButtons || "[]"); });
  }

  async state() {
    return this.frame.evaluate(() => { window.sawitState(); return JSON.parse(window.sawitStateJson || "{}"); });
  }

  // taps/clicks the first canvas button whose label matches `re`; returns its label or null
  async press(re) {
    const b = (await this.buttons()).find((x) => re.test(x.text));
    if (!b) return null;
    const x = this.offset.x + b.x + b.w / 2, y = this.offset.y + b.y + b.h / 2;
    if (this.touch) await this.tapAt(x, y);
    else await this.page.mouse.click(x, y);
    return b.text;
  }

  // a held finger tap at page coordinates: at the software-GL frame rate an instant tap can start
  // and end inside one engine frame (and Playwright's locator.tap() stalls in a cross-origin iframe)
  async tapAt(x, y) {
    const cdp = await this.page.context().newCDPSession(this.page);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    await this.page.waitForTimeout(200);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await cdp.detach();
  }

  // taps/clicks a page element (the save code dialog is real HTML over the canvas)
  async tapEl(loc) {
    if (!this.touch) { await loc.click(); return; }
    await loc.waitFor({ state: "visible" });
    const r = await loc.boundingBox();  // page coordinates, iframe offset included
    await this.tapAt(r.x + r.width / 2, r.y + r.height / 2);
  }

  async until(fn, ms, step = 400) {
    const t0 = Date.now();
    for (;;) {
      const v = await fn();
      if (v) return v;
      if (Date.now() - t0 > ms) return null;
      await this.page.waitForTimeout(step);
    }
  }

  dialog() { return this.frame.locator("#sawit-code"); }
  dlgButton(text) { return this.frame.locator("#sawit-code button", { hasText: text }); }

  async hit(text) { await this.tapEl(this.dlgButton(text)); }

  async shot(tag) { await this.page.screenshot({ path: `${OUT}/savecode_${this.name}_${tag}.png` }); }

  // counts the events the game's own listeners would get (canvas keys, window pointer/paste)
  async spyOn() {
    await this.frame.evaluate(() => {
      const c = document.getElementById("canvas") || document.querySelector("canvas");
      window.__spy = { key: 0, move: 0, up: 0, paste: 0 };
      if (!window.__spyOn) {
        window.__spyOn = true;
        c.addEventListener("keydown", () => window.__spy.key++);
        window.addEventListener("pointermove", () => window.__spy.move++);
        window.addEventListener("mouseup", () => window.__spy.up++);
        window.addEventListener("paste", () => window.__spy.paste++);
      }
    });
  }

  async spy() { return this.frame.evaluate(() => window.__spy); }
}

async function launch(name, opts) {
  const browser = await chromium.launch({
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
      "--autoplay-policy=no-user-gesture-required"],
  });
  browsers.add(browser);
  const ctx = await browser.newContext(opts.ctx);
  if (opts.top && !opts.touch) await ctx.grantPermissions(["clipboard-read", "clipboard-write"], { origin: GAME });
  const pg = await ctx.newPage();
  pg.setDefaultTimeout(60000);
  const logs = [];
  pg.on("console", (m) => logs.push(`[${m.type()}] ${m.text()}`));
  pg.on("pageerror", (e) => logs.push(`[pageerror] ${e.message}`));
  const t0 = Date.now();
  await pg.goto(opts.top ? `${GAME}/index.html?sawit_test=1` : `http://127.0.0.1:${HOST_PORT}/host.html`);
  let frame = pg.mainFrame(), offset = { x: 0, y: 0 };
  if (!opts.top) {
    for (let i = 0; i < 100 && !(frame = pg.frames().find((f) => f.url().startsWith(GAME))); i++) await pg.waitForTimeout(100);
    offset = await pg.locator("#game").boundingBox();
  }
  await frame.waitForSelector("#loader", { state: "detached", timeout: 240000 });
  console.log(`${name}: engine started in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  const g = new Game(name, pg, frame, offset, opts.touch);
  g.browser = browser;
  g.logs = logs;
  await pg.waitForTimeout(3000);
  return g;
}

async function finish(g) {
  const errs = g.logs.filter((l) => /\[pageerror\]/.test(l));
  check(!errs.length, g.name, `no page errors${errs.length ? ": " + errs.join(" | ") : ""}`);
  browsers.delete(g.browser);
  await g.browser.close();
}

async function walk(g, ms) {
  if (!g.touch) {
    await g.page.keyboard.down("KeyA");
    await g.page.waitForTimeout(ms);
    await g.page.keyboard.up("KeyA");
    return;
  }
  const vp = g.page.viewportSize();
  const cdp = await g.page.context().newCDPSession(g.page);
  const sx = g.offset.x + vp.width * 0.2, sy = g.offset.y + vp.height * 0.7;
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: sx, y: sy }] });
  for (let k = 1; k <= 10; k++) {
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: sx - k * 6, y: sy }] });
    await g.page.waitForTimeout(ms / 10);
  }
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await cdp.detach();
}

// ------------------------------------------------------------------ export (old device)
async function exportCode(name, opts) {
  const g = await launch(name + " export", opts);
  const n = g.name;
  let hit = null;
  for (let k = 0; k < 3 && !hit; k++) {
    // the first tap on a fresh page can be eaten by the browser (audio unlock / focus)
    await g.press(/^Main Baru$/);
    hit = await g.until(async () => (await g.state()).state === "play", 4000);
  }
  if (!check(!!hit, n, "Main Baru starts a game")) throw new Error("the game did not start");
  const SKIP = [/Siap, (Juragan|Pak Bos)/, /^(\d+ )?Lanjut$/];
  const pressed = [];
  await g.until(async () => {
    for (const re of SKIP) {
      const l = await g.press(re);
      if (l) { pressed.push(l); return false; }
    }
    return (await g.state()).modal === "";
  }, 120000, 700);
  const s0 = await g.state();
  if (!check(s0.modal === "" && s0.state === "play", n, `intro closed after ${pressed.length} presses (${JSON.stringify(s0)})`)) {
    console.log(`${n}: pressed ${JSON.stringify(pressed)}; buttons now ${JSON.stringify(await g.buttons())}`);
    await g.shot("intro_stuck");
  }
  await walk(g, 1200);
  await g.frame.evaluate(([m, d]) => window.sawitTestSet(m, d), [MONEY, DAY]);
  await walk(g, 800);
  await g.page.waitForTimeout(500);
  const pos0 = (await g.state()).pos;
  check(!!(pos0 && s0.pos && Math.hypot(pos0[0] - s0.pos[0], pos0[1] - s0.pos[1]) > 0.3), n, `player walked ${JSON.stringify(s0.pos)} -> ${JSON.stringify(pos0)}`);

  // Menu -> "Kode Save (pindah HP)"
  check(!!(await g.press(/^Menu$/)), n, "Menu opens");
  await g.page.waitForTimeout(1200);
  const KODE = /^Kode Save \(pindah HP\)$/;
  const kb = (await g.buttons()).find((b) => KODE.test(b.text));
  const vp = g.page.viewportSize();
  check(!!kb && kb.y >= 0 && kb.y + kb.h <= vp.height, n, `pause menu button on screen ${JSON.stringify(kb)}`);
  await g.press(KODE);
  const open = await g.until(async () => g.dialog().isVisible(), 10000, 250);
  if (!check(!!open, n, "export dialog opens")) throw new Error("no export dialog");
  await g.page.waitForTimeout(500);
  await g.shot("export");
  const code = await g.frame.locator("#sawit-code textarea").inputValue();
  check(/^SAWIT1-[A-Za-z0-9+/=]{40,}$/.test(code), n, `code in the textarea (${code.length} chars)`);
  const sel = await g.frame.evaluate(() => { const t = document.querySelector("#sawit-code textarea"); return [document.activeElement === t, t.selectionEnd - t.selectionStart, t.readOnly]; });
  check(sel[0] && sel[1] === code.length && sel[2], n, `code auto-selected, read-only ${JSON.stringify(sel)}`);
  const st = await g.state();
  check(st.modal === "WebCodeHolder" && st.money === MONEY && st.day === DAY, n, `game held while open (${JSON.stringify(st)})`);

  // "Salin kode"
  await g.hit("Salin kode");
  const msg = g.frame.locator("#sawit-code .sc-msg");
  const copied = await g.until(async () => /good/.test(await msg.getAttribute("class")), 3000, 200);
  check(!!copied, n, `Salin kode: "${await msg.textContent()}"`);
  if (opts.top && !opts.touch) {
    const clip = await g.frame.evaluate(() => navigator.clipboard.readText());
    check(clip === code, n, "clipboard holds the code");
  }

  // nothing typed / moved over the dialog reaches the game's listeners
  await g.spyOn();
  if (!g.touch) {
    const bx = await g.frame.locator("#sawit-code textarea").boundingBox();
    await g.page.mouse.move(g.offset.x + bx.x + 10, g.offset.y + bx.y + 10);
    await g.page.mouse.move(g.offset.x + bx.x + 60, g.offset.y + bx.y + 20, { steps: 5 });
    await g.page.mouse.down();
    await g.page.mouse.up();
    await g.page.keyboard.down("KeyD");
    await g.page.waitForTimeout(700);
    await g.page.keyboard.up("KeyD");
  }
  const spy = await g.spy();
  const pos1 = (await g.state()).pos;
  check(spy.key === 0 && spy.move === 0 && spy.up === 0, n, `dialog keeps its events ${JSON.stringify(spy)}`);
  check(Math.hypot(pos1[0] - pos0[0], pos1[1] - pos0[1]) < 0.05, n, "player did not move while the dialog was open");

  // "Tutup" hands the game back
  await g.hit("Tutup");
  const gone = await g.until(async () => (await g.dialog().count()) === 0, 5000, 200);
  await g.page.waitForTimeout(400);
  const s2 = await g.state();
  const focus = await g.frame.evaluate(() => document.activeElement && document.activeElement.tagName);
  check(!!gone && s2.modal === "", n, `Tutup closes the dialog and the game's holder (${s2.modal})`);
  if (!g.touch) {
    check(focus === "CANVAS", n, `keyboard focus back on the canvas (${focus})`);
    await walk(g, 900);
    const pos2 = (await g.state()).pos;
    check(Math.hypot(pos2[0] - pos1[0], pos2[1] - pos1[1]) > 0.3, n, "keys move the player again");
    // Esc closes it too
    await g.press(/^Menu$/);
    await g.page.waitForTimeout(1000);
    await g.press(KODE);
    await g.until(async () => g.dialog().isVisible(), 10000, 250);
    await g.page.keyboard.press("Escape");
    const esc = await g.until(async () => (await g.dialog().count()) === 0 && (await g.state()).modal === "", 5000, 200);
    check(!!esc, n, "Esc closes the export dialog");
  } else {
    await walk(g, 900);
  }
  await g.shot("export_after");
  const saved = { money: st.money, day: st.day, hour: st.hour };
  await finish(g);
  return { code, saved };
}

// ------------------------------------------------------------------ import (new device)
async function importCode(name, opts, exp) {
  const g = await launch(name + " import", opts);
  const n = g.name;
  const titles = (await g.buttons()).map((b) => b.text);
  check(!titles.includes("Lanjutkan") && !(await g.state()).has_save, n, `fresh storage: no save (${titles.join(", ")})`);
  await g.shot("title");
  if (g.touch) {
    // phones usually play fullscreen: the dialog must still draw over the fullscreen canvas
    await g.press(/^Layar penuh$/);
    const fsEl = await g.until(async () => g.frame.evaluate(() => document.fullscreenElement && document.fullscreenElement.tagName), 5000, 250);
    check(fsEl === "CANVAS", n, `"Layar penuh" puts the canvas fullscreen (${fsEl})`);
    await g.page.waitForTimeout(800);
  }
  let open = null;
  for (let k = 0; k < 3 && !open; k++) {
    check(!!(await g.press(/^Masukkan Kode Save$/)), n, "title button Masukkan Kode Save found");
    open = await g.until(async () => g.dialog().isVisible(), 4000, 250);
  }
  if (!check(!!open, n, "import dialog opens (no window.prompt)")) throw new Error("no import dialog");
  await g.page.waitForTimeout(400);
  const onTop = await g.frame.evaluate(() => {
    const b = Array.from(document.querySelectorAll("#sawit-code button")).pop();
    const r = b.getBoundingClientRect();
    return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === b && r.bottom <= innerHeight;
  });
  check(onTop, n, "dialog buttons on top and on screen");
  await g.shot("import");

  // Batal, then open again
  await g.hit("Batal");
  const closed = await g.until(async () => (await g.dialog().count()) === 0 && (await g.state()).modal === "", 5000, 200);
  const back = (await g.buttons()).some((b) => /^Masukkan Kode Save$/.test(b.text));
  check(!!closed && back, n, "Batal closes it, title menu still there");
  await g.press(/^Masukkan Kode Save$/);
  check(!!(await g.until(async () => g.dialog().isVisible(), 5000, 250)), n, "import dialog opens again");

  // a broken code: the dialog stays and says why
  const ta = g.frame.locator("#sawit-code textarea");
  await g.spyOn();
  if (g.touch) await g.tapEl(ta);
  await ta.fill("");
  await ta.pressSequentially("SAWIT1-rusak");
  await g.hit("Pakai kode");
  const msg = g.frame.locator("#sawit-code .sc-msg");
  const bad = await g.until(async () => /bad/.test(await msg.getAttribute("class")) && /tidak valid/.test(await msg.textContent()), 5000, 200);
  check(!!bad && (await g.dialog().isVisible()), n, `broken code refused in place: "${await msg.textContent()}"`);

  // "Tempel" reads the clipboard where the page may (top level); the Artifact-like iframe is not
  // granted clipboard-read, so the button is left out there and long-press / Ctrl+V paste remains
  const tempel = await g.dlgButton("Tempel").count();
  check(tempel === (opts.top ? 1 : 0), n, `Tempel button ${tempel ? "shown" : "hidden"} (${opts.top ? "top level" : "iframe without clipboard-read"})`);
  // the real code: Tempel and Ctrl+V from the clipboard on the desktop page, typed text elsewhere
  await ta.fill("");
  if (opts.top && !opts.touch) {
    await g.frame.evaluate((c) => navigator.clipboard.writeText(c), exp.code);
    await g.hit("Tempel");
    const viaButton = await g.until(async () => (await ta.inputValue()) === exp.code, 3000, 200);
    check(!!viaButton, n, `Tempel fills the box: "${await msg.textContent()}"`);
    await ta.fill("");
    await ta.focus();
    await g.page.keyboard.press("ControlOrMeta+V");
    await g.page.waitForTimeout(300);
    const pasted = await ta.inputValue();
    check(pasted === exp.code, n, "Ctrl+V pastes the code into the textarea");
    if (pasted !== exp.code) await ta.fill(exp.code);
  } else {
    await ta.fill(exp.code);
  }
  const spy = await g.spy();
  check(spy.key === 0 && spy.paste === 0 && spy.up === 0, n, `typing/pasting stays in the dialog ${JSON.stringify(spy)}`);
  await g.shot("import_filled");
  await g.hit("Pakai kode");
  const gone = await g.until(async () => (await g.dialog().count()) === 0, 8000, 200);
  const st = await g.until(async () => { const s = await g.state(); return s.state === "play" ? s : null; }, 20000, 500);
  check(!!gone && !!st, n, "Pakai kode closes the dialog and the game starts");
  if (st) {
    check(st.money === exp.saved.money && st.day === exp.saved.day, n,
      `same money/day as the exported game: Rp ${st.money} day ${st.day} (exported Rp ${exp.saved.money} day ${exp.saved.day})`);
    check(Math.abs(st.hour - exp.saved.hour) < 0.5, n, `same time of day (${st.hour.toFixed(2)} vs ${exp.saved.hour.toFixed(2)})`);
    check(st.has_save && st.modal === "", n, "the code is now this device's save; no panel left open");
  }
  await g.page.waitForTimeout(1500);
  await g.shot("imported");
  await finish(g);
}

(async () => {
  console.log(`build: ${DIR}`);
  const servers = [await gameServer(), await hostServer()];
  const desktop = { viewport: { width: 1280, height: 720 } };
  const phone = { viewport: { width: 915, height: 412 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true,
    userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36" };
  const runs = {
    top: { top: true, touch: false, ctx: desktop },
    iframe: { top: false, touch: false, ctx: desktop },
    phone: { top: false, touch: true, ctx: phone },
  };
  for (const name of ONLY) {
    const opts = runs[name];
    if (!opts) continue;
    try {
      const exp = await exportCode(name, opts);
      await importCode(name, opts, exp);
    } catch (e) {
      check(false, name, `exception: ${e && e.stack ? e.stack : e}`);
    }
    for (const b of browsers) await b.close().catch(() => {});
    browsers.clear();
  }
  servers.forEach((s) => s.close());
  console.log(failures ? `web_savecode_test: ${failures} FAILURE(S)` : "web_savecode_test: OK");
  process.exitCode = failures ? 1 : 0;
})();
