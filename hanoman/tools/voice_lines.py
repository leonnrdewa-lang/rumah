#!/usr/bin/env python3
"""List every voiced line in the game as JSON: [{"who", "text", "key"}].

key = first 12 hex chars of md5(text) — the same key hf.gd uses to find the
recording at hf/voice/<key>.mp3.   python3 hanoman/tools/voice_lines.py > lines.json
"""
import hashlib
import json
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game", "scripts")


def main():
    out, seen = [], set()

    def add(who, text):
        if who in ("combat", "wil") or len(text) < 12 or text in seen:
            return
        seen.add(text)
        out.append({"who": who, "text": text, "key": hashlib.md5(text.encode("utf-8")).hexdigest()[:12]})

    for name in ("main.gd", "hub.gd"):
        src = open(os.path.join(ROOT, name), encoding="utf-8").read()
        for who, text in re.findall(r'\[\s*"([a-z_]+)",\s*"((?:[^"\\]|\\.)*)"\s*\]', src):
            add(who, text)
        if name == "hub.gd":
            tips = re.search(r"SUGRIWA_TIPS := \[(.*?)\n\]", src, re.S).group(1)
            for text in re.findall(r'"((?:[^"\\]|\\.)*)"', tips):
                add("sugriwa", text)
    src = open(os.path.join(ROOT, "boons.gd"), encoding="utf-8").read()
    block = re.search(r"const LINES := \{(.*?)\n\}", src, re.S).group(1)
    for god, body in re.findall(r'"(\w+)": \[(.*?)\]', block, re.S):
        for text in re.findall(r'"((?:[^"\\]|\\.)*)"', body):
            add("dewa_" + god, text)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
