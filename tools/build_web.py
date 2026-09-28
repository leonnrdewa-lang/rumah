"""Exports the Godot project for the web and packages two ready-to-host builds:

  dist/artifact/  page body + files for a claude.ai Artifact (no <html> skeleton;
                  big files as base64 text because the host only serves web types)
  docs/           full static site for GitHub Pages (Settings -> Pages -> /docs)

Large binaries (index.wasm, index.pck) are gzip-compressed; the page inflates them
in the browser with DecompressionStream, so any static host works.

python3 tools/build_web.py [--skip-export] [--game=DIR] [--out=DIR] [--only=pages|artifact]

  --game=DIR   export this copy of the project instead of game/ (e.g. a test copy)
  --out=DIR    write build/, dist/artifact/ and docs/ under DIR instead of the repo
               (test builds then do not touch the committed docs/)
  --only=X     package only one target

Note: docs/index.pck.gz and docs/index.wasm.gz are committed for GitHub Pages, so
every committed rebuild adds their full size (~10 + 9 MB) to the git history.
Commit docs/ only for releases, and use --out for test builds.
"""
import base64
import gzip
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _arg(name, default):
    for a in sys.argv[1:]:
        if a.startswith("--" + name + "="):
            return os.path.abspath(a.split("=", 1)[1]) if name != "only" else a.split("=", 1)[1]
    return default


GAME = _arg("game", os.path.join(ROOT, "game"))
OUT = _arg("out", ROOT)
BUILD = os.path.join(OUT, "build", "web")
SHELL = os.path.join(ROOT, "web", "shell.html")
TARGETS = {"artifact": os.path.join(OUT, "dist", "artifact"), "pages": os.path.join(OUT, "docs")}
if _arg("only", ""):
    TARGETS = {k: v for k, v in TARGETS.items() if k == _arg("only", "")}
GODOT = os.environ.get("GODOT", "godot")
COPY = ["index.js", "index.audio.worklet.js", "index.audio.position.worklet.js"]
GZIP = ["index.wasm", "index.pck"]


def export():
    os.makedirs(BUILD, exist_ok=True)
    for f in os.listdir(BUILD):
        os.remove(os.path.join(BUILD, f))
    subprocess.run([GODOT, "--headless", "--path", GAME, "--import"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    r = subprocess.run([GODOT, "--headless", "--path", GAME, "--export-release", "Web", os.path.join(BUILD, "index.html")],
                       capture_output=True, text=True, timeout=900)
    if not os.path.exists(os.path.join(BUILD, "index.wasm")):
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit("export failed")


def godot_config():
    html = open(os.path.join(BUILD, "index.html"), encoding="utf-8").read()
    m = re.search(r"const GODOT_CONFIG = (\{.*?\});", html, re.S)
    if not m:
        sys.exit("GODOT_CONFIG not found in exported index.html")
    cfg = json.loads(m.group(1))
    cfg["canvasResizePolicy"] = 2
    cfg["focusCanvas"] = True
    return cfg


def copy_voices(out):
    """Voice acting (tools/make_voices.py) is not in the pack: one Ogg bank per character,
    fetched by the game when that character is near (voice.gd). Served as plain files
    (audio/ogg is a standard web type) next to index.html, with index.json kept as JSON."""
    src = os.path.join(GAME, "voices")
    if not os.path.isdir(src):
        return
    dst = os.path.join(out, "voices")
    os.makedirs(dst, exist_ok=True)
    for f in sorted(os.listdir(src)):
        if f.endswith(".ogg") or f == "index.json":
            shutil.copy(os.path.join(src, f), os.path.join(dst, f))


def package():
    cfg = godot_config()
    shell = open(SHELL, encoding="utf-8").read()
    total = {}
    for name, out in TARGETS.items():
        if os.path.isdir(out):
            shutil.rmtree(out)
        os.makedirs(out)
        for f in COPY:
            src = os.path.join(BUILD, f)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(out, f))
        packed = {}
        for f in GZIP:
            raw = open(os.path.join(BUILD, f), "rb").read()
            gz = gzip.compress(raw, 9)
            if name == "artifact":
                # the Artifact host only serves known web types: ship gzip bytes as base64 text
                data = base64.b64encode(gz)
                # the host caps each file at 16 MB: split the text into ~12 MB parts
                # (index.pck.gz.part0.txt, ...) that the shell fetches and joins
                part = 12 * 1024 * 1024
                if len(data) > part:
                    fname = []
                    for i in range(0, len(data), part):
                        pn = "%s.gz.part%d.txt" % (f, i // part)
                        open(os.path.join(out, pn), "wb").write(data[i:i + part])
                        fname.append(pn)
                    packed[f] = {"src": fname, "size": len(data), "b64": True}
                    continue
                fname = f + ".gz.txt"
            else:
                data = gz
                fname = f + ".gz"
            open(os.path.join(out, fname), "wb").write(data)
            packed[f] = {"src": fname, "size": len(data), "b64": name == "artifact"}
        body = shell.replace("/*GODOT_CONFIG*/{}", json.dumps(cfg)).replace("/*PACKED*/{}", json.dumps(packed))
        if name == "artifact":
            page = body
        else:
            head, rest = body.split("<canvas", 1)
            page = ("<!doctype html>\n<html lang=\"id\">\n<head>\n<meta charset=\"utf-8\">\n"
                    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no\">\n"
                    "<link rel=\"icon\" href=\"favicon.png\">\n" + head + "</head>\n<body>\n<canvas" + rest + "</body>\n</html>\n")
            icon = os.path.join(GAME, "assets", "icons", "app_icon.png")
            if os.path.exists(icon):
                shutil.copy(icon, os.path.join(out, "favicon.png"))
            open(os.path.join(out, ".nojekyll"), "w").close()
        open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(page)
        copy_voices(out)
        sizes = {f: os.path.getsize(os.path.join(out, f)) for f in os.listdir(out) if os.path.isfile(os.path.join(out, f))}
        vdir = os.path.join(out, "voices")
        if os.path.isdir(vdir):
            sizes["voices/"] = sum(os.path.getsize(os.path.join(vdir, f)) for f in os.listdir(vdir))
        print(name, {k: f"{v / 1e6:.2f}MB" for k, v in sorted(sizes.items())})
        total[name] = sum(v for k, v in sizes.items() if k != "voices/")
    for name, t in total.items():
        print(f"{name}: {t / 1e6:.2f} MB to download ({TARGETS[name]}; voices/ load on demand)")


if __name__ == "__main__":
    if "--skip-export" not in sys.argv:
        export()
    package()
