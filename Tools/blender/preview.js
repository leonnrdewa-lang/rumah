// Contact sheets of building GLBs rendered like the game (toon + ink), for eyeballing with an image viewer.
//   NODE_PATH=$(npm root -g) node Tools/blender/preview.js out.png Web/models/bld/ruko_*.glb
//   ... --street       also writes out_street.png (the models in a row, game camera) and out_street_back.png
// Needs Tools/blender/.vendor/{three.min.js,GLTFLoader.js} from three@0.128.0 (npm pack three@0.128.0).
const { chromium } = require('playwright'); const http = require('http'), fs = require('fs'), path = require('path');
const args = process.argv.slice(2), street = args.includes('--street'), files = args.filter(a => a !== '--street');
const out = files.shift(); const root = '/';
const srv = http.createServer((q, s) => { const f = decodeURIComponent(q.url.split('?')[0]); fs.readFile(f, (e, d) => { if (e) { s.writeHead(404); s.end(); return; } s.end(d); }); }).listen(0, async () => {
  const port = srv.address().port, base = 'http://127.0.0.1:' + port;
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const p = await b.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(base + path.join(__dirname, 'preview.html')); await p.waitForFunction(() => window.ready);
  const man = {}; for (const f of files) { const mp = path.join(path.dirname(path.resolve(f)), 'manifest.json'); if (fs.existsSync(mp)) for (const e of JSON.parse(fs.readFileSync(mp))) man[e.file] = e; }
  const list = files.map(f => { const e = man[path.basename(f)]; return { url: base + path.resolve(f), label: path.basename(f) + (e ? `  ${e.tris} tris  ${e.w}x${e.d}x${e.h}m  [${e.roles}]` : '') }; });
  const write = (file, data) => fs.writeFileSync(file, Buffer.from(data.split(',')[1], 'base64'));
  write(out, await p.evaluate(l => window.sheet(l), list));
  if (street) { write(out.replace(/\.png$/, '') + '_street.png', await p.evaluate(l => window.street(l, false), list));
    write(out.replace(/\.png$/, '') + '_street_back.png', await p.evaluate(l => window.street(l, true), list)); }
  if (errs.length) console.error(errs.join('\n'));
  await b.close(); srv.close(); console.log('wrote', out);
});
