#!/usr/bin/env python3
"""Download the Higgsfield paintings listed in hanoman/art/higgsfield.json.

Each image is saved as hanoman/game/assets/portraits/hf_<name>.png, scaled to at
most 1024 px tall. The game prefers hf_<name>.png over the Blender-rendered
fallback <name>.png. Needs only the standard library + Pillow.

    python3 hanoman/tools/fetch_art.py [--force]
"""
import io
import json
import os
import sys
import urllib.request

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = os.path.join(ROOT, "art", "higgsfield.json")
OUT = os.path.join(ROOT, "game", "assets", "portraits")


def main():
    force = "--force" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    for it in json.load(open(LIST)):
        dst = os.path.join(OUT, "hf_%s.png" % it["name"])
        if os.path.exists(dst) and not force:
            print("skip", it["name"])
            continue
        req = urllib.request.Request(it["url"], headers={"User-Agent": "hanoman-fetch-art/1.0"})
        try:
            data = urllib.request.urlopen(req, timeout=60).read()
        except Exception as e:  # noqa: BLE001 - report and keep going
            print("FAIL", it["name"], e)
            continue
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        if img.height > 1024:
            img = img.resize((round(img.width * 1024 / img.height), 1024), Image.LANCZOS)
        img.save(dst, optimize=True)
        print("ok", it["name"], img.size)


if __name__ == "__main__":
    main()
