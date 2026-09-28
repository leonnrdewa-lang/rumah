// Downloads the Higgsfield (GPT Image 2.5) generated art for the browser demo and converts it to
// game-ready WebP files in Web/assets: transparent sprites are trimmed and resized, roofs/facades/key art
// are downscaled. Uses headless Chromium (Playwright) for the image processing, so no Python/PIL needed.
//
//   NODE_PATH=$(npm root -g) node Tools/fetch-assets.js
//
// Requires network access to d8j0ntlcm91z4.cloudfront.net (Higgsfield's CDN).
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

const CDN = 'https://d8j0ntlcm91z4.cloudfront.net/user_2vqT0Ah9P4GmOaY4MT4rr1viFY5/hf_20260928_';
// name: [cdn id, mode, size]. mode: sprite = trim alpha + fit long side; rgb = resize to exact w x h.
const ASSETS = {
  ojol: ['052124_b373db9a-bc82-4551-bb46-ab5ad4c8bb26', 'sprite', 192],
  bike1: ['052124_16179f99-513c-4d8a-821f-89494b18be26', 'sprite', 160],
  bike2: ['052124_736a3299-99ab-4196-bc4f-e78f3bd66152', 'sprite', 160],
  mpv: ['052124_b3c6b259-4293-4afe-a536-1b48f365c6bf', 'sprite', 256],
  hatch: ['052124_72b889f9-e2ed-4bca-978f-2c4f9ac76d6d', 'sprite', 224],
  sedan: ['052124_947f1cbc-aae6-4ffb-82f1-220d79466f73', 'sprite', 256],
  angkot: ['052124_e3e9174d-162c-4a5c-a2d2-2217bca199f3', 'sprite', 256],
  bajaj: ['052124_8b7561c6-a6e7-430e-b59a-4809adc0a65a', 'sprite', 192],
  bus: ['052124_2dbdaec3-679d-4b6c-8467-619a03990f37', 'sprite', 448],
  gerobak: ['052124_007f73c5-cc7f-4448-bed2-cd6d571e1cfd', 'sprite', 192],
  tree: ['052148_3c01b376-f8fe-4e52-ba9e-1afe9ecd3823', 'sprite', 224],
  critters: ['052124_9df5b19b-4162-46c9-9444-4c322e25a32d', 'sheet', 128, ['cat', 'chicken', 'pax']],
  police: ['052124_4450c334-442b-48e2-906e-3f18dde999e0', 'sheet', 192, ['policecar', 'cone', 'officer']],
  roof1: ['052148_b65c0ed2-1183-4439-9c6e-e2018e9832af', 'rgb', [256, 256]],
  roof2: ['052148_4ae66d3d-c4f9-4704-b4bf-f13f3334a12e', 'rgb', [256, 256]],
  roof3: ['052148_28b863e1-98af-4ed5-a7a8-f2ecbf6fce52', 'rgb', [256, 256]],
  fac1: ['052148_2ac0470f-df82-47d2-9c69-f869d95901c0', 'rgb', [512, 286]],
  fac2: ['052148_d6e8d38c-df0e-4fcd-844e-d3cf296b04c6', 'rgb', [512, 286]],
  fac3: ['052148_cda4e892-7512-4a45-b485-f7f5e1a65155', 'rgb', [512, 286]],
  keyart: ['052148_693dd52f-5a09-4c59-a3da-2af6bf1e4ddf', 'rgb', [480, 849]],
};

(async () => {
  const out = path.join(__dirname, '..', 'Web', 'assets');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent('<canvas id="c"></canvas>');
  for (const [name, [id, mode, size, parts]] of Object.entries(ASSETS)) {
    // curl honours the environment's HTTPS proxy settings (Node's fetch does not).
    const b64 = execFileSync('curl', ['-sSfL', CDN + id + '.png'], { maxBuffer: 64 << 20 }).toString('base64');
    const results = await page.evaluate(async ({ b64, mode, size, parts, name }) => {
      const img = new Image();
      img.src = 'data:image/png;base64,' + b64;
      await img.decode();
      const W = img.width, H = img.height;
      const src = document.createElement('canvas'); src.width = W; src.height = H;
      const sx = src.getContext('2d'); sx.drawImage(img, 0, 0);
      const alpha = sx.getImageData(0, 0, W, H).data;
      const encode = (x, y, w, h, ow, oh, q) => {
        const c = document.createElement('canvas'); c.width = ow; c.height = oh;
        const g = c.getContext('2d'); g.imageSmoothingQuality = 'high';
        g.drawImage(src, x, y, w, h, 0, 0, ow, oh);
        return { data: c.toDataURL('image/webp', q).split(',')[1], w: ow, h: oh };
      };
      const bbox = (x0, x1) => {
        let minX = W, minY = H, maxX = -1, maxY = -1;
        for (let y = 0; y < H; y++) for (let x = x0; x < x1; x++) if (alpha[(y * W + x) * 4 + 3] > 20) {
          if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y;
        }
        return [minX, minY, maxX - minX + 1, maxY - minY + 1];
      };
      const fit = ([x, y, w, h], long) => { const s = long / Math.max(w, h); return encode(x, y, w, h, Math.max(1, Math.round(w * s)), Math.max(1, Math.round(h * s)), 0.8); };
      if (mode === 'rgb') return [[name, encode(0, 0, W, H, size[0], size[1], 0.68)]];
      if (mode === 'sprite') return [[name, fit(bbox(0, W), size)]];
      // sprite sheet: split on empty columns
      const cols = []; for (let x = 0; x < W; x++) { let on = false; for (let y = 0; y < H; y += 3) if (alpha[(y * W + x) * 4 + 3] > 20) { on = true; break; } cols.push(on); }
      const segs = []; for (let x = 0; x < W;) { if (cols[x]) { const s0 = x; while (x < W && cols[x]) x++; if (x - s0 > 15) segs.push([s0, x]); } else x++; }
      return segs.slice(0, parts.length).map(([a, b], i) => [parts[i], fit(bbox(a, b), size)]);
    }, { b64, mode, size, parts, name });
    for (const [n, r] of results) {
      fs.writeFileSync(path.join(out, n + '.webp'), Buffer.from(r.data, 'base64'));
      console.log(n.padEnd(10), r.w + 'x' + r.h);
    }
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
