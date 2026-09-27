#!/usr/bin/env python3
"""Download the Higgsfield dialog portraits listed in art/reference/portraits.json.

Each entry is {"name", "job_id", "url", "prompt"}. For every entry the image at
"url" is saved to game/assets/portraits/<name>.png after trimming transparent
margins and scaling to 1024 px tall (transparent background kept).

Existing files are skipped unless --force is given. Only stdlib + Pillow.

    python3 tools/fetch_portraits.py            # fetch missing portraits
    python3 tools/fetch_portraits.py --force    # re-download everything
    python3 tools/fetch_portraits.py --only player,kakek
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.request

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, "art", "reference", "portraits.json")
OUT_DIR = os.path.join(ROOT, "game", "assets", "portraits")
TARGET_H = 1024
PAD = 8            # px of transparent padding kept around the trimmed figure
ALPHA_CUTOFF = 8   # alpha below this counts as empty when trimming


def download(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "sawit-fetch-portraits/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def process(data):
    img = Image.open(io.BytesIO(data))
    img.load()
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    if alpha.getextrema()[0] >= 250:
        print("    warning: image has no transparency (background not removed)")
    mask = alpha.point(lambda a: 255 if a >= ALPHA_CUTOFF else 0)
    bbox = mask.getbbox()
    if bbox:
        l, t, r, b = bbox
        l, t = max(0, l - PAD), max(0, t - PAD)
        r, b = min(img.width, r + PAD), min(img.height, b + PAD)
        img = img.crop((l, t, r, b))
    scale = TARGET_H / img.height
    new_w = max(1, round(img.width * scale))
    return img.resize((new_w, TARGET_H), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="overwrite existing PNGs")
    ap.add_argument("--only", default="", help="comma-separated names to fetch")
    ap.add_argument("--json", default=JSON_PATH, help="path to portraits.json")
    ap.add_argument("--out", default=OUT_DIR, help="output directory")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    with open(args.json, encoding="utf-8") as f:
        entries = json.load(f)
    only = {n.strip() for n in args.only.split(",") if n.strip()}
    os.makedirs(args.out, exist_ok=True)

    ok, skipped, failed = [], [], []
    for e in entries:
        name, url = e.get("name"), e.get("url")
        if only and name not in only:
            continue
        dst = os.path.join(args.out, f"{name}.png")
        if not url:
            print(f"[fail] {name}: no url in json")
            failed.append(name)
            continue
        if os.path.exists(dst) and not args.force:
            print(f"[skip] {name}: {os.path.relpath(dst, ROOT)} exists")
            skipped.append(name)
            continue
        try:
            print(f"[get ] {name}: {url}")
            img = process(download(url, args.timeout))
            tmp = dst + ".tmp.png"
            img.save(tmp, optimize=True)
            os.replace(tmp, dst)
            print(f"[ ok ] {name}: {img.width}x{img.height} -> {os.path.relpath(dst, ROOT)}")
            ok.append(name)
        except (urllib.error.URLError, OSError, ValueError) as ex:
            print(f"[fail] {name}: {ex}")
            failed.append(name)

    print(f"\ndownloaded {len(ok)}, skipped {len(skipped)}, failed {len(failed)}")
    if failed:
        print("failed: " + " ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
