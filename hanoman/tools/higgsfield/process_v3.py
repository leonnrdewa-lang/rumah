"""Build the v3 Higgsfield pack additions inside the Higgsfield sandbox:
painted VFX sprites (normalised so slashes bulge up, beams run horizontally and
bolts vertically), sound effects and music (Ogg Vorbis, loudness-normalised,
leading silence trimmed), new painted floors and the staff-wielding Hanoman
(clips merged, textures shrunk).   python3 process_v3.py urls.json OUT_HF_DIR"""
import re
import json, math, os, subprocess, sys
from PIL import Image

B = "https://d8j0ntlcm91z4.cloudfront.net/user_2vqT0Ah9P4GmOaY4MT4rr1viFY5/hf_20260928_"
WF = os.environ.get("HF_WORKFLOWS", "/home/user/.higgsfield/workflows") + "/website-builder-flow/scripts/"
U = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
for d in ["fx", "sfx", "music", "floors", "models"]:
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
os.makedirs("raw", exist_ok=True)


def get(key, ext):
    path = "raw/%s.%s" % (key.split("_", 1)[1], ext)
    if not os.path.exists(path):
        for i in range(5):
            if subprocess.call(["curl", "-sSfL", "-o", path, B + key + "." + ext]) == 0:
                break
    return path


def moments(im):
    """Brightness-weighted centroid and principal-axis angle (image coords)."""
    g = im.convert("L").resize((256, int(256 * im.height / im.width)))
    w, h = g.size
    px = g.load()
    s = sx = sy = sxx = syy = sxy = 0.0
    for y in range(h):
        for x in range(w):
            v = px[x, y] / 255.0
            v = max(0.0, v - 0.08) ** 2
            s += v; sx += v * x; sy += v * y
            sxx += v * x * x; syy += v * y * y; sxy += v * x * y
    cx, cy = sx / s, sy / s
    vxx, vyy, vxy = sxx / s - cx * cx, syy / s - cy * cy, sxy / s - cx * cy
    ang = 0.5 * math.atan2(2 * vxy, vxx - vyy)
    k = im.width / w
    return cx * k, cy * k, ang, math.sqrt(max(vxx, 1e-6)) * k, math.sqrt(max(vyy, 1e-6)) * k


def square(im, size):
    s = min(im.size)
    l = (im.width - s) // 2
    t = (im.height - s) // 2
    return im.crop((l, t, l + s, t + s)).resize((size, size), Image.LANCZOS)


def bright_box(im, thr=40):
    return im.convert("L").point(lambda v: 255 if v > thr else 0).getbbox() or (0, 0, im.width, im.height)


def fit_square(im, size, margin=0.08):
    l, t, r, b = bright_box(im)
    side = int(max(r - l, b - t) * (1 + 2 * margin))
    cx, cy = (l + r) // 2, (t + b) // 2
    canvas = Image.new("RGB", (side, side))
    canvas.paste(im, (side // 2 - cx, side // 2 - cy))
    return canvas.resize((size, size), Image.LANCZOS)


def tips_y(im):
    """Mean height of the bright pixels in the outer 15% columns (crescent tips)."""
    l, t, r, b = bright_box(im)
    g = im.convert("L")
    px = g.load()
    s = sy = 0.0
    band = max(1, int((r - l) * 0.15))
    for x in list(range(l, l + band)) + list(range(r - band, r)):
        for y in range(t, b, 2):
            v = max(0, px[x, y] - 40)
            s += v; sy += v * y
    return sy / s if s else im.height / 2


def fx(name, key):
    im = Image.open(get(key, "png")).convert("RGB")
    if name == "slash":
        # chord of the crescent horizontal, then make it bulge upward (tips low)
        cx, cy, ang, _, _ = moments(im)
        im = im.rotate(math.degrees(ang), resample=Image.BICUBIC, expand=True)
        im = fit_square(im, 512)
        if tips_y(im) < moments(im)[1]:
            im = im.rotate(180)
    elif name in ("beam", "lightning"):
        cx, cy, ang, _, _ = moments(im)
        rot = math.degrees(ang) + (90 if name == "lightning" else 0)
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
        cx, cy, _, sdx, sdy = moments(im)
        if name == "beam":
            half = max(24, int(sdy * 3.2))
            band = im.crop((0, int(cy - half), im.width, int(cy + half)))
            l = int(im.width * 0.08)
            im = band.crop((l, 0, band.width - l, band.height)).resize((1024, 256), Image.LANCZOS)
        else:
            half = max(24, int(sdx * 3.2))
            im = im.crop((int(cx - half), 0, int(cx + half), im.height)).resize((256, 768), Image.LANCZOS)
    else:
        im = fit_square(im, 512, 0.04) if name in ("impact", "fire", "splash", "smoke", "shards") else square(im, 512)
    im.save(os.path.join(OUT, "fx", name + ".jpg"), quality=90)
    return "hf/fx/%s.jpg" % name


def peak_db(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"max_volume: (-?[0-9.]+) dB", r.stderr)
    return float(m.group(1)) if m else -99.0


def audio(src, dst, music=False, pre=""):
    """Music: EBU loudness. SFX: peak-normalised to -1.5 dB (loudnorm leaves 1 s
    clips 20-40 dB too quiet, and silenceremove at -50 dB emptied quiet sources)."""
    if music:
        af = "loudnorm=I=-16:TP=-1.5:LRA=11"
    else:
        gain = max(0.0, min(30.0, -1.5 - peak_db(src)))
        af = pre + "silenceremove=start_periods=1:start_threshold=-70dB,volume=%.1fdB,alimiter=limit=0.9,afade=t=in:d=0.005" % gain
    out = dst + ".ogg"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", af, "-ar", "44100", "-ac", "2", "-c:a", "libvorbis",
           "-q:a", "3" if music else "4", out]
    if subprocess.call(cmd) != 0:
        raise SystemExit("ffmpeg failed for " + src)
    return out


man = {"fx": {}, "sfx": {}, "music": {}, "floors": {}}
for name, key in U["fx"].items():
    man["fx"][name] = fx(name, key)
    print("fx", name)
# swing2/3 are pitched copies of swing1 (the generated swing2 came back near-silent);
# sources that are still near-silent are left out so the game uses its own sounds
DERIVED = {"sfx_swing2": "asetrate=44100*1.07,aresample=44100,", "sfx_swing3": "asetrate=44100*0.9,aresample=44100,bass=g=4,"}
for name, key in U["sfx"].items():
    src = get(U["sfx"]["sfx_swing1"] if name in DERIVED else key, "mp3")
    if peak_db(src) < -40.0:
        print("sfx", name, "skipped (near-silent source)")
        continue
    out = audio(src, os.path.join(OUT, "sfx", name), pre=DERIVED.get(name, ""))
    man["sfx"][name] = "hf/sfx/" + os.path.basename(out)
    print("sfx", name, os.path.getsize(out))
for name, key in U["music"].items():
    out = audio(get(key, "m4a"), os.path.join(OUT, "music", name), True)
    man["music"][name] = "hf/music/" + os.path.basename(out)
    print("music", name, os.path.getsize(out))
for name, key in U["floors"].items():
    im = Image.open(get(key, "png")).convert("RGB")
    im.thumbnail((1024, 1024), Image.LANCZOS)
    im.save(os.path.join(OUT, "floors", name + ".jpg"), quality=86)
    man["floors"][name] = "hf/floors/%s.jpg" % name
    print("floor", name)
# Hanoman with the tongkat: idle base + clips
H = U["hanoman"]
base = get(H.pop("idle"), "glb")
parts = ["%s:%s" % (get(k, "glb"), clip) for clip, k in H.items()]
subprocess.check_call(["python3", WF + "glb_merge_anims.py", base] + parts + ["raw/hanoman2_merged.glb"])
subprocess.check_call(["python3", "glb_shrink.py", "raw/hanoman2_merged.glb", os.path.join(OUT, "models", "hanoman2.glb"), "1024", "FIRST=idle"])
subprocess.call(["python3", WF + "glb_inspect.py", os.path.join(OUT, "models", "hanoman2.glb")])
json.dump(man, open("v3_manifest_part.json", "w"), indent=1)
print("DONE")
