#!/usr/bin/env python3
"""Build the v4 Higgsfield pack (runs in the Higgsfield sandbox).

Inputs: raw/ downloads named after the keys of art/hf_assets_v4.json
(img/..., voice/<md5 key>, vo/..., rig/..., model/indrajit) and the site's
current public/hf directory. Writes into public/hf and patches manifest.json:
  - portraits: Indrajit, Kumbakarna and mood variants (green screen keyed out)
  - images: title painting, cutscene stills, wayang UI frames, weapon icons
  - floors: samudra, argasoka, alengka
  - voice: English dialogue (replaces the Indonesian recordings)
  - sfx: Hanoman's combat barks (vo_*)
  - models: Hanoman gains spin / victory / getup clips, Wil / Cakil / Buto Ijo
    gain a "special" clip, Indrajit (new, idle + attack)

  python3 process_v4.py RAW_DIR PUBLIC_DIR
"""
import json, os, subprocess, sys
from PIL import Image

RAW, PUB = sys.argv[1], sys.argv[2]
HF = os.path.join(PUB, "hf")
WF = os.environ.get("HF_WORKFLOWS", "/home/user/.higgsfield/workflows") + "/website-builder-flow/scripts/"
HERE = os.path.dirname(os.path.abspath(__file__))
OLD = "https://d8j0ntlcm91z4.cloudfront.net/user_2vqT0Ah9P4GmOaY4MT4rr1viFY5/hf_20260928_"


def raw(key, ext):
    return os.path.join(RAW, key.replace("/", "__") + "." + ext)


def key_green(im):
    """Green-screen portrait -> RGBA with soft edges and no green spill."""
    im = im.convert("RGB")
    px = im.load()
    out = Image.new("RGBA", im.size)
    po = out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            green = g - max(r, b)
            a = 255 if green < 30 else (0 if green > 90 else int(255 * (90 - green) / 60))
            if a < 255:
                g = min(g, max(r, b))   # despill
            po[x, y] = (r, g, b, a)
    return out


man = json.load(open(os.path.join(HF, "manifest.json")))
for sec in ("portraits", "images", "floors", "voices", "sfx", "models"):
    man.setdefault(sec, {})
J = json.load(open(os.path.join(HERE, "..", "..", "art", "hf_assets_v4.json")))
for d in ("portraits", "images", "floors", "voice", "sfx", "models"):
    os.makedirs(os.path.join(HF, d), exist_ok=True)

# --- 2D art ---------------------------------------------------------------------
for k in J:
    if not k.startswith("img/"):
        continue
    name = k[4:]
    path = raw(k, "png")
    if not os.path.exists(path):
        print("missing", k)
        continue
    im = Image.open(path)
    if name.startswith("portrait/"):
        pid = name.split("/", 1)[1]
        p = key_green(im)
        p.thumbnail((900, 1350), Image.LANCZOS)
        p.save(os.path.join(HF, "portraits", pid + ".png"), optimize=True)
        man["portraits"][pid] = "hf/portraits/%s.png" % pid
    elif name.startswith("floor/"):
        fid = name.split("/", 1)[1]
        im = im.convert("RGB")
        im.thumbnail((1024, 1024), Image.LANCZOS)
        im.save(os.path.join(HF, "floors", fid + ".jpg"), quality=86)
        man["floors"][fid] = "hf/floors/%s.jpg" % fid
    elif name == "indrajit_concept":
        continue
    else:
        im = im.convert("RGB")
        size = {"ui/panel": (384, 384), "ui/button": (420, 180), "ui/card": (600, 257)}.get(name)
        if size:
            im = im.resize(size, Image.LANCZOS)
        elif name.startswith("icon/"):
            im.thumbnail((256, 256), Image.LANCZOS)
        else:
            im.thumbnail((1600, 1600), Image.LANCZOS)
        fn = name.replace("/", "_") + ".jpg"
        im.save(os.path.join(HF, "images", fn), quality=88)
        man["images"][name] = "hf/images/" + fn
    print("img", name)

# --- English voices (replace the Indonesian set) ----------------------------------
voices = {}
for k in J:
    if k.startswith("voice/"):
        vk = k[6:]
        src = raw(k, "mp3")
        if os.path.exists(src):
            dst = os.path.join(HF, "voice", vk + ".mp3")
            subprocess.call(["cp", src, dst])
            voices[vk] = "hf/voice/%s.mp3" % vk
man["voices"] = voices
print("voices", len(voices))

# --- Hanoman's barks: peak-normalised OGG ----------------------------------------
for k in J:
    if k.startswith("vo/"):
        name = k[3:]
        dst = os.path.join(HF, "sfx", name + ".ogg")
        subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", raw(k, "mp3"), "-af",
                               "silenceremove=start_periods=1:start_threshold=-60dB,loudnorm=I=-12:TP=-1.0",
                               "-ac", "2", "-ar", "44100", "-c:a", "libvorbis", "-q:a", "4", dst])
        man["sfx"][name] = "hf/sfx/%s.ogg" % name
print("barks done")

# --- models -------------------------------------------------------------------------
def merge(base, parts, out, *renames):
    tmp = out + ".merged.glb"
    subprocess.check_call(["python3", WF + "glb_merge_anims.py", base] + parts + [tmp])
    subprocess.check_call(["python3", os.path.join(HERE, "glb_shrink.py"), tmp, out, "1024"] + list(renames))
    os.remove(tmp)
    subprocess.call(["python3", WF + "glb_inspect.py", out])


# Hanoman: rebuild from the raw v3 clips + the three new ones
V3 = json.load(open(os.path.join(HERE, "..", "..", "art", "hf_assets_v3.json")))["hanoman"]
hparts = []
for clip, key in V3.items():
    p = os.path.join(RAW, "v3_" + clip + ".glb")
    if not os.path.exists(p):
        subprocess.check_call(["curl", "-sfL", "-o", p, OLD + key + ".glb"])
    if clip != "idle":
        hparts.append("%s:%s" % (p, clip))
for clip, key in (("spin", "rig/hanoman_spin"), ("victory", "rig/hanoman_victory"), ("getup", "rig/hanoman_getup")):
    hparts.append("%s:%s" % (raw(key, "glb"), clip))
merge(os.path.join(RAW, "v3_idle.glb"), hparts, os.path.join(HF, "models", "hanoman3.glb"), "FIRST=idle")
man["models"]["hanoman"]["file"] = "hf/models/hanoman3.glb"
man["models"]["hanoman"]["clips"].update({"spin": "spin", "victory": "victory", "getup": "getup"})

# enemies: add a "special" clip to the GLBs already on the site
for mid, key in (("wil", "rig/wil_special"), ("cakil", "rig/cakil_special"), ("buto_ijo", "rig/buto_special")):
    cur = man["models"][mid]["file"]
    base = os.path.join(PUB, cur)
    out = os.path.join(HF, "models", mid + "_v4.glb")
    try:
        merge(base, ["%s:special" % raw(key, "glb")], out)
        man["models"][mid]["file"] = "hf/models/%s_v4.glb" % mid
        man["models"][mid].setdefault("clips", {})["special"] = "special"
    except subprocess.CalledProcessError as e:
        print("enemy merge failed", mid, e)

# Indrajit: idle base (+ attack if it rendered)
ib = raw("model/indrajit", "glb")
parts = []
if os.path.exists(raw("rig/indrajit_attack", "glb")):
    parts.append("%s:attack" % raw("rig/indrajit_attack", "glb"))
merge(ib, parts, os.path.join(HF, "models", "indrajit.glb"), "FIRST=idle")
man["models"]["indrajit"] = {"file": "hf/models/indrajit.glb", "height": 1.9,
                             "clips": {"idle": "idle", "attack": "attack", "run": "idle"}}

json.dump(man, open(os.path.join(HF, "manifest.json"), "w"), indent=1)
print("DONE", {k: len(v) for k, v in man.items() if isinstance(v, dict)})
