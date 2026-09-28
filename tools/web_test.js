// Smoke-tests the exported web build in headless Chromium (desktop + Android phone emulation):
// title -> "Main Baru" -> clicks through the intro phone call ("Lanjut") -> closes the help
// panel ("Siap, Juragan!") -> walks (keyboard on desktop, virtual joystick on the phone).
// Buttons are found by label through window.sawitProbe() (scripts/debug/web_probe.gd); a build
// without it falls back to the 915x412 / 1280x720 coordinates of the current layout.
// Usage: NODE_PATH=$(npm root -g) node tools/web_test.js <url> <out_dir>
const { chromium, devices } = require("playwright");

const url = process.argv[2] || "http://127.0.0.1:8060/";
const out = process.argv[3] || "/tmp";
let failures = 0;

async function buttons(page) {
  return page.evaluate(() => {
    if (typeof window.sawitProbe !== "function") return null;
    window.sawitProbe();
    try { return JSON.parse(window.sawitButtons || "[]"); } catch (e) { return []; }
  });
}

// Taps/clicks the first visible button whose label matches `re`; returns its label or null.
async function press(page, re, touch, fallback) {
  const list = await buttons(page);
  let pt = null, label = null;
  if (list) {
    const b = list.find((x) => re.test(x.text));
    if (b) { pt = [b.x + b.w / 2, b.y + b.h / 2]; label = b.text; }
  } else if (fallback) {
    pt = fallback; label = `(${fallback}) no probe`;
  }
  if (!pt) return null;
  if (touch) await page.touchscreen.tap(pt[0], pt[1]);
  else await page.mouse.click(pt[0], pt[1]);
  return label;
}

// Clicks through the intro call and the help panel; true once the help panel was closed.
async function skipIntro(page, name, touch, lanjutAt, siapAt) {
  const LANJUT = /^Lanjut$/, SIAP = /Siap, Juragan/;
  let steps = 0;
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(700);
    const list = await buttons(page);
    if (list && list.some((b) => SIAP.test(b.text))) {
      await press(page, SIAP, touch, null);
      console.log(`${name}: intro done after ${steps} x Lanjut, help panel closed`);
      await page.waitForTimeout(800);
      const left = await buttons(page);
      if (left && left.some((b) => SIAP.test(b.text) || LANJUT.test(b.text))) break;
      return true;
    }
    if (await press(page, LANJUT, touch, list ? null : (i < 12 ? lanjutAt : siapAt))) steps++;
    if (!list && i >= 12) { await page.waitForTimeout(800); return true; }
  }
  console.log(`${name}: FAIL - intro/help panel still open`);
  failures++;
  return false;
}

async function run(name, contextOpts, steps) {
  const browser = await chromium.launch({
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--autoplay-policy=no-user-gesture-required"],
  });
  const ctx = await browser.newContext(contextOpts);
  const page = await ctx.newPage();
  const logs = [];
  page.on("console", (m) => logs.push(`[${m.type()}] ${m.text()}`));
  page.on("pageerror", (e) => logs.push(`[pageerror] ${e.message}`));
  const t0 = Date.now();
  await page.goto(url, { waitUntil: "load" });
  try {
    await page.waitForSelector("#loader", { state: "detached", timeout: 180000 });
    console.log(`${name}: engine started in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  } catch (e) {
    console.log(`${name}: FAIL - loader still visible after timeout`);
    failures++;
  }
  await steps(page);
  const errs = logs.filter((l) => /\[(error|pageerror)\]/.test(l));
  if (errs.length) console.log(`${name}: ${errs.length} console errors`);
  console.log(logs.filter((l) => !l.includes("[verbose]")).slice(-25).join("\n"));
  await browser.close();
}

(async () => {
  await run("desktop", { viewport: { width: 1280, height: 720 } }, async (page) => {
    await page.waitForTimeout(4000);
    await page.screenshot({ path: `${out}/web_desktop_title.png` });
    const box = await page.locator("#canvas").boundingBox();
    const hit = await press(page, /^Main Baru$/, false, [box.width / 2, box.height * 0.66]);
    console.log(`desktop: title -> ${hit}`);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${out}/web_desktop_game.png` });
    await skipIntro(page, "desktop", false, [990, 615], [640, 650]);
    await page.screenshot({ path: `${out}/web_desktop_play.png` });
    await page.keyboard.down("KeyA");
    await page.waitForTimeout(1500);
    await page.keyboard.up("KeyA");
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${out}/web_desktop_walk.png` });
  });
  const phone = devices["Pixel 7"];
  await run("android", { ...phone, viewport: { width: 915, height: 412 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true }, async (page) => {
    await page.waitForTimeout(4000);
    await page.screenshot({ path: `${out}/web_phone_title.png` });
    const vp = page.viewportSize();
    const hit = await press(page, /^Main Baru$/, true, [vp.width / 2, vp.height * 0.62]);
    console.log(`android: title -> ${hit}`);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${out}/web_phone_game.png` });
    await skipIntro(page, "android", true, [707, 352], [457, 372]);
    await page.screenshot({ path: `${out}/web_phone_play.png` });
    // drag the virtual joystick (left half of the screen) to the left
    const cdp = await page.context().newCDPSession(page);
    const sx = vp.width * 0.2, sy = vp.height * 0.7;
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: sx, y: sy }] });
    for (let k = 1; k <= 10; k++) {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: sx - k * 6, y: sy }] });
      await page.waitForTimeout(60);
    }
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${out}/web_phone_walk.png` });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${out}/web_phone_walk_end.png` });
  });
  console.log(failures ? `web_test: ${failures} FAILURE(S)` : "web_test: OK");
  process.exitCode = failures ? 1 : 0;
})();
