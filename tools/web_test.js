// Smoke-tests the exported web build in headless Chromium (desktop + Android phone emulation).
// Usage: NODE_PATH=$(npm root -g) node tools/web_test.js <url> <out_dir>
const { chromium, devices } = require("playwright");

const url = process.argv[2] || "http://127.0.0.1:8060/";
const out = process.argv[3] || "/tmp";

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
    console.log(`${name}: loader still visible after timeout`);
  }
  await steps(page);
  console.log(logs.filter((l) => !l.includes("[verbose]")).slice(-25).join("\n"));
  await browser.close();
}

(async () => {
  await run("desktop", { viewport: { width: 1280, height: 720 } }, async (page) => {
    await page.waitForTimeout(4000);
    await page.screenshot({ path: `${out}/web_desktop_title.png` });
    // click "Main Baru" (centre of screen, roughly)
    const box = await page.locator("#canvas").boundingBox();
    await page.mouse.click(box.width / 2, box.height * 0.66);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${out}/web_desktop_game.png` });
    for (let i = 0; i < 3; i++) { await page.keyboard.press("Space"); await page.waitForTimeout(600); }
    await page.keyboard.down("KeyA");
    await page.waitForTimeout(1500);
    await page.keyboard.up("KeyA");
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${out}/web_desktop_walk.png` });
  });
  const phone = devices["Pixel 7"];
  await run("android", { ...phone, viewport: { width: 915, height: 412 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true }, async (page) => {
    await page.waitForTimeout(4000);
    await page.screenshot({ path: `${out}/web_phone_title.png` });
    const vp = page.viewportSize();
    await page.touchscreen.tap(vp.width / 2, vp.height * 0.66);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${out}/web_phone_game.png` });
  });
})();
