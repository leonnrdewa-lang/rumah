"""Exports the Godot project for the web and packages two ready-to-host builds:

  dist/artifact/  page body + files for a claude.ai Artifact (no <html> skeleton)
  docs/           full static site for GitHub Pages (Settings -> Pages -> /docs)

Large binaries (index.wasm, index.pck) are gzip-compressed; the page inflates them
in the browser with DecompressionStream, so any static host works.

python3 tools/build_web.py [--skip-export]
"""
import gzip
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "game")
BUILD = os.path.join(ROOT, "build", "web")
SHELL = os.path.join(ROOT, "web", "shell.html")
TARGETS = {"artifact": os.path.join(ROOT, "dist", "artifact"), "pages": os.path.join(ROOT, "docs")}
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


def package():
    cfg = godot_config()
    shell = open(SHELL, encoding="utf-8").read()
    body = shell.replace("/*GODOT_CONFIG*/{}", json.dumps(cfg)).replace("/*GZ_FILES*/[]", json.dumps(GZIP))
    for name, out in TARGETS.items():
        if os.path.isdir(out):
            shutil.rmtree(out)
        os.makedirs(out)
        for f in COPY:
            src = os.path.join(BUILD, f)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(out, f))
        for f in GZIP:
            with open(os.path.join(BUILD, f), "rb") as fi, gzip.open(os.path.join(out, f + ".gz"), "wb", 9) as fo:
                shutil.copyfileobj(fi, fo)
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
        sizes = {f: os.path.getsize(os.path.join(out, f)) for f in os.listdir(out)}
        print(name, {k: f"{v / 1e6:.2f}MB" for k, v in sorted(sizes.items())})


if __name__ == "__main__":
    if "--skip-export" not in sys.argv:
        export()
    package()
