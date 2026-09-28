"""Voice acting for Sawit The Franchise: every spoken dialog line, pre-rendered in the
speaker's own voice (Indonesian neural TTS + WORLD vocoder character transforms).

    python3 tools/make_voices.py extract        # game scripts -> game/data/voice_manifest.json
    python3 tools/make_voices.py survey         # analyse the 83 TTS speakers (pitch, brightness, ASR)
    python3 tools/make_voices.py cast           # casting table -> game/data/voice_cast.json
    python3 tools/make_voices.py render [--jobs=4] [--only=a,b] [--force]
    python3 tools/make_voices.py pack           # -> game/voices/<bank>.ogg + index.json (+ res://data copy)
    python3 tools/make_voices.py qa             # loudness / peaks / silences / pitch per character / ASR
    python3 tools/make_voices.py all

Pipeline per line: text normalisation (numbers, Rp, TBS, English words respelled) ->
g2p_id phonemes (with the glottal stops it puts between every two vowels reduced to
glides/diphthongs, which the model otherwise pronounces as a hard "k") -> Coqui VITS,
one call per sentence so the pauses between sentences are ours (the model pauses
~1.4 s at every full stop) -> WORLD analysis -> character transform (pitch, formant
warp for body size/age, breath, tremolo, roughness) + expressive intonation (wider
pitch range, question rises, exclamation lift, sad lines lower/slower) -> 2-3 takes with
different noise seeds, the best by Whisper ASR accuracy -> EQ, de-ess, compression,
-18 LUFS, peak <= -1 dBFS, silence trimmed.

Toolchain (see README "Suara"): /opt/idtts (Indonesian VITS by Wikidepia, non-commercial
licence), /opt/asr (Whisper small, sherpa-onnx), pyworld, pyloudnorm, soundfile.
Scratch files go to /tmp/audio_work/voice/.
"""
import hashlib
import json
import os
import re
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "game")
SCRIPTS = os.path.join(GAME, "scripts")
MANIFEST = os.path.join(GAME, "data", "voice_manifest.json")
CAST = os.path.join(GAME, "data", "voice_cast.json")
INDEX_RES = os.path.join(GAME, "data", "voice_index.json")
VOICES = os.path.join(GAME, "voices")
WORK = "/tmp/audio_work/voice"
SR = 22050

# ================================================================== GDScript literal parsing


def _skip_ws(s, i):
    while i < len(s):
        if s[i] in " \t\r\n":
            i += 1
        elif s[i] == "#":
            while i < len(s) and s[i] != "\n":
                i += 1
        elif s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "\n":
            i += 2
        else:
            break
    return i


def _parse_string(s, i):
    q = s[i]
    i += 1
    out = []
    while s[i] != q:
        c = s[i]
        if c == "\\":
            n = s[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "'": "'", "\\": "\\"}.get(n, "\\" + n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out), i + 1


def parse_literal(s, i=0):
    """GDScript literal (dict / array / string / number / bool) starting at s[i] -> (value, end)."""
    i = _skip_ws(s, i)
    c = s[i]
    if c in "\"'":
        v, i = _parse_string(s, i)
        # adjacent string concatenation is not GDScript; a trailing % is handled by callers
        return v, i
    if c == "[":
        out = []
        i += 1
        while True:
            i = _skip_ws(s, i)
            if s[i] == "]":
                return out, i + 1
            v, i = parse_literal(s, i)
            out.append(v)
            i = _skip_ws(s, i)
            if s[i] == ",":
                i += 1
    if c == "{":
        out = {}
        i += 1
        while True:
            i = _skip_ws(s, i)
            if s[i] == "}":
                return out, i + 1
            k, i = parse_literal(s, i)
            i = _skip_ws(s, i)
            assert s[i] in ":=", s[i - 20:i + 20]
            v, i = parse_literal(s, i + 1)
            out[k] = v
            i = _skip_ws(s, i)
            if s[i] == ",":
                i += 1
    m = re.compile(r"-?\d+(\.\d+)?").match(s, i)
    if m:
        t = m.group(0)
        return (float(t) if "." in t else int(t)), m.end()
    m = re.compile(r"[A-Za-z_][A-Za-z0-9_]*").match(s, i)
    if m:
        w = m.group(0)
        return {"true": True, "false": False, "null": None}.get(w, w), m.end()
    raise ValueError("cannot parse literal at: " + s[i:i + 40])


def gd_const(src, name):
    m = re.search(r"^const\s+" + name + r"\s*:?=\s*", src, re.M)
    if not m:
        raise KeyError(name)
    return parse_literal(src, m.end())[0]


def split_args(s, i):
    """s[i] is just after '(' -> ([arg source strings], end index after ')')."""
    args, depth, cur, start = [], 0, i, i
    while True:
        c = s[cur]
        if c in "\"'":
            _, cur = _parse_string(s, cur)
            continue
        if c == "#":
            while s[cur] != "\n":
                cur += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                args.append(s[start:cur].strip())
                return [a for a in args if a], cur + 1
            depth -= 1
        elif c == "," and depth == 0:
            args.append(s[start:cur].strip())
            start = cur + 1
        cur += 1


def func_bodies(src):
    """{func name: body source} for a GDScript file (top-level funcs)."""
    out = {}
    ms = list(re.finditer(r"^func\s+(\w+)\s*\(", src, re.M))
    for k, m in enumerate(ms):
        end = ms[k + 1].start() if k + 1 < len(ms) else len(src)
        out[m.group(1)] = src[m.start():end]
    return out


def literal_head(expr):
    """'"text %s" % [a, b]' -> ('text %s', '[a, b]'); non-literal -> (None, expr)."""
    expr = expr.strip()
    if not expr or expr[0] not in "\"'":
        return None, expr
    v, i = _parse_string(expr, 0)
    rest = expr[i:].strip()
    if rest.startswith("%"):
        return v, rest[1:].strip()
    return v, None


def dialog_calls(src):
    """Every say()/ui.dialog() call: [(func name, portrait expr, speaker expr, text expr)]."""
    out = []
    for fname, body in func_bodies(src).items():
        if fname == "say":
            continue
        for m in re.finditer(r"(?<![\w.])(?:say|ui\.dialog|deals\.say)\(", body):
            if body[max(0, m.start() - 5):m.start()].endswith("func "):
                continue
            args, _ = split_args(body, m.end())
            if len(args) >= 3:
                out.append((fname, args[0], args[1], args[2]))
    return out


def string_returns(body):
    return [parse_literal(body, m.end())[0] for m in re.finditer(r"\breturn\s+(?=[\"'])", body)]


# ================================================================== text normalisation
from_num = None


def _num(n):
    global from_num
    if from_num is None:
        from num2words import num2words
        from_num = lambda v: num2words(int(v), lang="id")
    return from_num(n)


RESPELL = [  # display spelling -> how the voice actor says it
    (r"Sawit The Franchise", "Sawit de Frencais"), (r"franchise", "frencais"),
    (r"live-kan", "laipkan"), (r"\blive\b", "laip"), (r"followers", "folowers"),
    (r"youtuber", "yutuber"), (r"WhatsApp", "wasap"), (r"\bgaes\b", "gais"),
    (r"\bTBS\b", "te be es"), (r"\bPKS\b", "pe ka es"), (r"\bRT\b", "er te"), (r"\bCSR\b", "se es er"),
    (r"di-PHK", "dipehaka"), (r"\bPHK\b", "pe ha ka"), (r"\bSD\b", "es de"), (r"\bOK\b", "oke"),
    (r"Tempo Doeloe", "Tempo Dulu"), (r"\bKlik-klik\b", "Klik klik"),
]


def money_words(num_text, unit=""):
    s = num_text.replace(".", "")
    if unit in ("jt", "juta"):
        if "," in s:
            a, b = s.split(",")
            if b == "5":
                return ("satu setengah" if a == "1" else _num(a) + " setengah") + " juta"
            return _num(a) + " koma " + " ".join(_num(c) for c in b) + " juta"
        return _num(s) + " juta"
    if unit in ("rb", "ribu"):
        return _num(s) + " ribu"
    return _num(int(s))


def canon(text):
    """Display text -> lookup key text (the runtime does the same in voice.gd: drop
    (stage directions), BBCode and line breaks, collapse spaces)."""
    t = re.sub(r"\[[^\]]*\]", "", text)
    t = re.sub(r"\([^)]*\)", "", t)
    t = t.replace("\n", " ")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 1 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1].strip()
    return t


def text_key(text):
    return hashlib.md5(canon(text).encode("utf-8")).hexdigest()[:12]


def normalize(text):
    """Display text -> what the voice actor says (numbers and abbreviations spelled out)."""
    t = canon(text)
    t = t.replace("™", "").replace("*", "").replace("…", "...")
    t = re.sub(r"[\"“”]", "", t)
    t = re.sub(r"(?<!\w)'|'(?!\w)", "", t)
    for pat, rep in RESPELL:
        t = re.sub(pat, rep, t, flags=re.I)
    t = re.sub(r"-?Rp\s?(\d[\d.,]*\d|\d)(?:\s?(jt|rb|juta|ribu)\b)?", lambda m: money_words(m.group(1), m.group(2) or "") + " rupiah", t)
    t = re.sub(r"(\d+)%\s*/\s*hari", lambda m: _num(m.group(1)) + " persen per hari", t)
    t = re.sub(r"(\d+)\s?%+", lambda m: _num(m.group(1)) + " persen", t)
    t = re.sub(r"(\d{1,2}):(\d{2})", lambda m: "jam " + _num(m.group(1)), t)
    t = re.sub(r"\d+", lambda m: _num(m.group(0)), t)
    t = t.replace(":", ",").replace(";", ",")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([.,!?])", r"\1", t)
    t = re.sub(r"([.!?])\s*\.\.\.\s*", r"\1 ", t)      # "Juragan? ...Oh" -> "Juragan? Oh"
    t = re.sub(r"^[.,\s]+", "", t)
    return t


def fmt_rp(amount):
    s = f"{abs(int(amount)):,}".replace(",", ".")
    return ("-Rp " if amount < 0 else "Rp ") + s


def fmt_short(amount):
    if abs(amount) >= 1000000:
        v = amount / 1000000.0
        t = ("%.1f" % v).replace(".0", "").replace(".", ",")
        return "Rp " + t + " jt"
    if abs(amount) >= 1000:
        return "Rp " + str(int(amount / 1000)) + " rb"
    return "Rp " + str(amount)


def gd_format(fmt, *vals):
    out, k, i = [], 0, 0
    while i < len(fmt):
        c = fmt[i]
        if c == "%" and i + 1 < len(fmt):
            n = fmt[i + 1]
            if n == "%":
                out.append("%")
            elif n in "sd":
                v = vals[k]
                k += 1
                out.append(str(int(v)) if n == "d" else str(v))
            else:
                out.append(c + n)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def fmt_regex(fmt):
    """A GDScript format string -> regex matching every text it can produce (%s/%d captured)."""
    parts = re.split(r"(%%|%s|%d)", canon(fmt))
    rx = ""
    for p in parts:
        if p == "%%":
            rx += "%"
        elif p == "%s":
            rx += "(.+?)"
        elif p == "%d":
            rx += r"(-?\d+)"
        else:
            rx += re.escape(p)
    return "^" + rx + "$"


# ================================================================== extract: who says what

WALKER_CHAR = "warga_%s"          # passers-by: "Warga" + their portrait key
SPECIAL = {  # speaker display name -> character id (non-villagers)
    "Telepon dari Pusat": "hq", "Kamu": "player", "Dik Udin": "udin",
    "Wartawan Investigasi": "wartawan", "Kabar Pasar": "calo", "Mas Joko (Demo Warga)": "pemuda",
    "Warung Mak Inah": "mak", "Mak Inah": "mak", "Bang Jeki, Calo Serba Bisa": "calo", "Bang Jeki (Calo)": "calo",
}
# the generic lines that stand in for sentences with open-ended numbers (the dialog box
# shows the exact amount; the voice says it the way a person pointing at it would)
GENERIC = {
    "_offer_franchise": "Jadi saya tetap pemilik, tapi kebunnya ditanami sawit, hasilnya dibagi enam puluh untuk Juragan, "
                        "empat puluh untuk saya? Biaya waralabanya dua setengah juta rupiah... uang saya tidak cukup.",
    "plasma_debt": "Pohon dewasa di kebun saya ada segini. Utang saya ke Juragan segini. Bunganya kok cepat sekali naiknya ya...",
    "plasma_paid": "Pohon dewasa di kebun saya ada segini. Utang saya ke Juragan sudah lunas. Alhamdulillah.",
    "harga_naik": "Tengkulak dari kota memborong! Harga te be es naik dua puluh lima persen hari ini!",
    "gossip_price": "Pabrik di timur buka sampai malam, Juragan. Harga te be es hari ini lumayan.",
    "gossip_polos": "Ada warga yang polos sekali, Juragan. Surat apa saja pasti ditandatangani.",
}
# lines the recogniser (and so probably a listener) found hard, re-worded for the voice
# only: the dialog box keeps the written text
SPOKEN_OVERRIDE = {
}
BARKS = {  # per character: mood -> line (the fallback for a line that has no clip)
    "neutral": "Hmm, begitu.", "yes": "Iya, Juragan.", "surprise": "Wah!", "annoyed": "Hah? Apa-apaan ini?",
    "sad": "Aduh... ya sudah.", "laugh": "Hahaha!",
}
BARK_ADDRESS = {"udin": "Om", "sari": "Kak", "budi": "Om", "warga_anak": "Om", "hq": "Juragan", "player": "Pak",
                "calo": "Bos", "tigor": "Bos", "pemuda": "Bang", "rian": "Bang", "wartawan": "Pak"}


def _load_sources():
    src = {}
    for rel in ["world/deals.gd", "autoload/gs.gd", "ui/ui_demo.gd", "ui/ui.gd"]:
        p = os.path.join(SCRIPTS, rel)
        src[rel] = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    return src


def extract():
    src = _load_sources()
    deals, gs = src["world/deals.gd"], src["autoload/gs.gd"]
    VILL = gd_const(gs, "VILLAGERS")
    PRICE = gd_const(gs, "PRICE")
    OIL = gd_const(gs, "OIL_PRICES")
    CHAT = gd_const(deals, "CHAT")
    EXTRAS = gd_const(deals, "EXTRAS")
    KID = gd_const(deals, "KID")
    WLINES = gd_const(deals, "WALKER_LINES")
    WMODELS = gd_const(deals, "WALKER_MODELS")
    LANDLESS = gd_const(deals, "CHAT_LANDLESS")
    layout = json.load(open(os.path.join(GAME, "data", "layout.json")))
    tiles = int(layout.get("parcel_cols", 4)) * int(layout.get("parcel_rows", 3))
    bodies = func_bodies(deals)

    chars, lines, templates, warnings = {}, [], [], []
    seen = set()

    def char(cid, name, portrait, kind):
        chars.setdefault(cid, {"name": name, "portrait": portrait, "kind": kind})

    def add(cid, text, src_tag, spoken=None):
        k = (cid, text_key(text))
        if k in seen:
            return text_key(text)
        seen.add(k)
        sp = spoken or SPOKEN_OVERRIDE.get(canon(text)) or normalize(text)
        if not re.search(r"[A-Za-z]", sp):
            return None
        lines.append({"char": cid, "text": canon(text), "key": text_key(text), "spoken": sp, "src": src_tag})
        return text_key(text)

    def template(cids, fmt, src_tag, variants=None, default_spoken=None, group=1):
        """runtime fallback for texts built with %: regex on the display text; the capture
        `group` picks a pre-rendered variant, else the generic default line."""
        t = {"chars": cids, "re": fmt_regex(fmt), "group": group, "src": src_tag, "variants": {}, "default": None}
        if default_spoken:
            t["default_spoken"] = default_spoken
        for key, text in (variants or {}).items():
            t["variants"][str(key)] = canon(text)
        templates.append(t)
        return t

    villagers = list(VILL.keys())
    for vid, d in VILL.items():
        char(vid, d["name"], d["model"].replace("char_", ""), "villager")
    for eid, e in EXTRAS.items():
        char(eid, e["name"], e["model"].replace("char_", ""), "extra")
    char("udin", "Dik Udin", "anak", "extra")
    char("hq", "Telepon dari Pusat", "hq", "special")
    char("player", "Kamu", "player", "special")
    char("wartawan", "Wartawan Investigasi", "petugas", "special")
    char("calo", "Bang Jeki", "calo", "special")
    char("mak", "Mak Inah", "mak", "special")
    for m in dict.fromkeys(WMODELS):
        p = m.replace("char_", "")
        char(WALKER_CHAR % p, "Warga", p, "walker")

    def speaker_chars(expr, fname):
        expr = expr.strip()
        if expr.startswith("GS.vname("):
            return villagers
        if expr in ('e["name"]',):
            return list(EXTRAS.keys())
        lit, _ = literal_head(expr)
        if lit is not None:
            if lit == "Warga":
                return [WALKER_CHAR % m.replace("char_", "") for m in dict.fromkeys(WMODELS)]
            for vid, d in VILL.items():
                if d["name"] == lit:
                    return [vid]
            for eid, e in EXTRAS.items():
                if e["name"] == lit:
                    return [eid]
            if lit in SPECIAL:
                return [SPECIAL[lit]]
        warnings.append("unknown speaker %s in %s" % (expr, fname))
        return []

    time_words = string_returns(bodies.get("_time_word", ""))
    for fname, portrait, speaker, text in dialog_calls(deals) + [("ui_demo:" + f, a, b, c) for f, a, b, c in dialog_calls(src["ui/ui_demo.gd"])]:
        who = speaker_chars(speaker, fname)
        lit, fmt_args = literal_head(text)
        if lit is not None and fmt_args is None:
            for c in who:
                add(c, lit, fname)
            continue
        if fname == "talk" and text == "greet":
            for g in string_returns(bodies["_greeting"]):
                if "%s" in g:
                    var = {w: gd_format(g, w) for w in time_words}
                    for c in who:
                        for w, t in var.items():
                            add(c, t, "_greeting")
                    template(who, g, "_greeting", var)
                else:
                    for c in who:
                        add(c, g, "_greeting")
        elif fname == "_chat":
            for vid in who:
                for l in CHAT.get(vid, []):
                    add(vid, l, "CHAT")
                for l in LANDLESS:
                    add(vid, l, "CHAT_LANDLESS")
        elif fname == "talk_extra":
            if "KID" in text:
                for l in KID:
                    add("udin", l, "KID")
            else:
                for eid, e in EXTRAS.items():
                    for l in e["lines"]:
                        add(eid, l, "EXTRAS")
        elif fname == "talk_walker":
            for c in who:
                for l in WLINES:
                    add(c, l, "WALKER_LINES")
        elif fname == "_sell_oil" and text == "line":
            b = bodies["_sell_oil"]
            for m in re.finditer(r"(?:var\s+line\s*:=|line\s*=)\s*(.+)", b):
                for lm in re.finditer(r"\"((?:[^\"\\]|\\.)*)\"", m.group(1)):
                    for c in who:
                        add(c, lm.group(1), "_sell_oil")
        elif lit is not None and fname == "_sleep":
            var = {("%02d" % h): gd_format(lit, "%02d:00" % h) for h in range(6, 16)}
            for h, t in var.items():
                add("player", t, "_sleep", normalize(t).replace("jam jam", "jam"))
            template(["player"], lit.replace("%s", "%s"), "_sleep", {h: t for h, t in var.items()})
            templates[-1]["re"] = fmt_regex(lit).replace("(.+?)", r"(\d\d):\d\d")
        elif lit is not None and fname == "land_menu":
            for vid in who:
                add(vid, gd_format(lit, tiles, fmt_rp(VILL[vid]["value"]), "x"), "land_menu")
        elif lit is not None and fname == "_fraud":
            for vid in who:
                add(vid, gd_format(lit, fmt_short(int(VILL[vid]["value"] * 0.1))), "_fraud")
        elif lit is not None and fname == "_sell_oil":
            var = {fmt_rp(p): gd_format(lit, fmt_rp(p)) for p in OIL}
            for c in who:
                for t in var.values():
                    add(c, t, "_sell_oil")
            template(who, lit, "_sell_oil", var)
        elif lit is not None and fname == "_hire_villager":
            for c in who:
                add(c, gd_format(lit, fmt_short(PRICE["buruh_murah"])), "_hire_villager")
        elif lit is not None and fname in ("_extort", "_sign_franchise"):
            for c in who:
                add(c, gd_format(lit, "Rp 0"), fname)
        elif lit is not None and fname == "_offer_franchise":
            fee = fmt_rp(PRICE["franchise_fee"])
            for vid in who:
                add(vid, gd_format(lit, fee, fmt_rp(VILL[vid]["savings"])), fname)
            template(who, lit, fname, None, GENERIC[fname])
        elif lit is not None and fname == "plasma_menu":
            t = template(who, lit, fname, None, None, group=3)
            t["default_spoken_by"] = {"Bunganya kok cepat sekali naiknya ya...": GENERIC["plasma_debt"],
                                      "Alhamdulillah sudah lunas.": GENERIC["plasma_paid"]}
        elif lit is not None and fname == "run_morning_events":
            template(who, lit, fname, None, GENERIC["harga_naik"])
        else:
            warnings.append("unhandled dynamic line in %s: %s" % (fname, text[:60]))
            if lit is not None:
                template(who, lit, fname, None, normalize(re.sub(r"%[sd]", "", lit)))
    # bribes only reach villagers that take them
    lines[:] = [l for l in lines if not (l["src"] == "_bribe_kades" and not VILL.get(l["char"], {}).get("sogok"))]

    # menus with a quoted line from their keeper (ui.menu subtitle): Mak Inah's gossip, Bang Jeki
    gossip = bodies.get("_gossip", "")
    for g in string_returns(gossip):
        if "%s itu polos" in g:
            var = {VILL[v]["name"]: gd_format(g, VILL[v]["name"]) for v in villagers if VILL[v].get("tipu", 0) >= 0.8}
            for t in var.values():
                add("mak", t, "_gossip")
            template(["mak"], g, "_gossip", var, GENERIC["gossip_polos"])
        elif "%s" in g:
            var = {fmt_rp(p): gd_format(g, fmt_rp(p)) for p in range(90000, 230001, 5000)}
            for t in var.values():
                add("mak", t, "_gossip")
            template(["mak"], g, "_gossip", var, GENERIC["gossip_price"])
        else:
            add("mak", g, "_gossip")
    m = re.search(r"ui\.menu\(\"Bang Jeki[^\"]*\",\s*(\"(?:[^\"\\]|\\.)*\")", deals)
    if m:
        add("calo", parse_literal(m.group(1))[0], "open_calo")

    # barks: every character, every mood
    barks = {}
    for cid in chars:
        addr = BARK_ADDRESS.get(cid, "Juragan")
        barks[cid] = {}
        for mood, b in BARKS.items():
            t = b.replace("Juragan", addr)
            barks[cid][mood] = t
            add(cid, t, "bark:" + mood)

    # template defaults and variant keys resolve to line keys
    for t in templates:
        for c in t["chars"]:
            if t.get("default_spoken"):
                add(c, "generic:%s: %s" % (t["src"], t["default_spoken"]), "generic", t["default_spoken"])
            for sp in t.get("default_spoken_by", {}).values():
                add(c, "generic:%s: %s" % (t["src"], sp), "generic", sp)
        if t.get("default_spoken"):
            t["default"] = text_key("generic:%s: %s" % (t["src"], t["default_spoken"]))
        if t.get("default_spoken_by"):
            t["by_capture"] = {k: text_key("generic:%s: %s" % (t["src"], sp)) for k, sp in t["default_spoken_by"].items()}
        t["variants"] = {k: text_key(v) for k, v in t["variants"].items()}

    speakers = {c["name"]: cid for cid, c in chars.items() if c["kind"] != "walker"}
    speakers.update(SPECIAL)
    for l in lines:
        l["emotion"] = emotion_of(l)
    man = {"generated_by": "tools/make_voices.py extract", "characters": chars, "speakers": speakers,
           "lines": lines, "templates": templates, "barks": barks}
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    json.dump(man, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    by = {}
    for l in lines:
        by[l["char"]] = by.get(l["char"], 0) + 1
    print("manifest: %d characters, %d lines, %d templates -> %s" % (len(chars), len(lines), len(templates), MANIFEST))
    print("  per character:", by)
    for w in warnings:
        print("  WARNING:", w)
    return man


EMO_RULES = [  # (emotion, regex on the display text) - first match wins
    ("angry", r"palsu!|Tidak!|Segitu\?|^Kamu lagi|Mau apa lagi|Mahal sekali!|laporkan|Apa-apaan|Jangan macam-macam|Hah\?"),
    ("scared", r"^Ampun|Ambil, ambil saja"),
    ("sad", r"Aduh|menghela|Dulu saya punya kebun|Hidup makin berat|daripada tidak makan|Terpaksa beli|disita\? Tapi|"
            r"uang saya tidak cukup|Uang saya habis|bingung jawabnya|Kalau ada kerjaan|yang terakhir|sudah habis|kurus|"
            r"sudah tidak ada|harganya jatuh|Lucu ya|Kebun saya sekarang sudah jadi milikmu|Ya sudah, saya butuh"),
    ("sly", r"hehe|amplop|'uang|diatur|bilang-bilang|nggak bilang|Klik-klik|advertorial|dokumennya|uang rokok|Abang bisa atur|"
            r"Piagamnya|penurut kok|Masyarakat yang punya|Terserah kamu|Siapa ya\?|Gosip|polos sekali"),
    ("laugh", r"^Hahaha"),
    ("excited", r"^Halo|^Eh, |Wah!|Seru!|Sayur, sayur|Selamat, kamu|memborong|main layangan|Aku mau jadi|berani lompat|"
                r"Om, main|Target pusat|live-kan|terbuka untuk investasi|tinggal panen|Ojek, Bang"),
    ("worried", r"Hati-hati|Satgas|demo|Mereka menunggu|asal-usul|jangan tanda tangan|Jangan disewa"),
    ("warm", r"Terima kasih|Alhamdulillah|Mampir|Mau pisang|Rempeyek|Assalamualaikum|rezeki|Semoga|Jamu|kopinya|berkah|"
             r"Mau tikar|harga teman|Masih hangat|sedekah"),
]


def emotion_of(line):
    t = line["text"]
    src = line["src"]
    if src.startswith("bark:"):
        return {"neutral": "neutral", "yes": "warm", "surprise": "excited", "annoyed": "angry",
                "sad": "sad", "laugh": "laugh"}[src[5:]]
    if src == "CHAT_LANDLESS":
        return "sad"
    for emo, rx in EMO_RULES:
        if re.search(rx, t):
            return emo
    return "neutral"


# ================================================================== engine (TTS + ASR), one per worker process

class Engine:
    def __init__(self, asr=True):
        sys.modules.setdefault("pkg_resources", types.SimpleNamespace(
            get_distribution=lambda n: types.SimpleNamespace(version="0.3.5")))  # pyworld 0.3.5 wants it
        import numpy as np
        import torch
        torch.set_num_threads(1)
        self.np, self.torch = np, torch
        cwd = os.getcwd()
        os.chdir("/opt/idtts")  # the model config names speakers.pth relatively
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            from TTS.utils.synthesizer import Synthesizer
            self.syn = Synthesizer(tts_checkpoint="/opt/idtts/checkpoint_1260000-inference.pth",
                                   tts_config_path="/opt/idtts/config.json",
                                   tts_speakers_file="/opt/idtts/speakers.pth", use_cuda=False)
            from g2p_id import G2p
            self.g2p = G2p()
        os.chdir(cwd)
        self.speakers = list(self.syn.tts_model.speaker_manager.name_to_id.keys())
        self._g2p_cache = {}
        self.rec = None
        if asr:
            import glob
            import sherpa_onnx
            d = glob.glob("/opt/asr/*/")[0]
            self.rec = sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=d + "small-encoder.int8.onnx", decoder=d + "small-decoder.int8.onnx",
                tokens=d + "small-tokens.txt", language="id", task="transcribe", num_threads=1)

    # ---- phonemes
    @staticmethod
    def fix_vowels(p):
        # g2p_id puts a glottal stop between any two vowels; the model says it as a hard
        # "k" ("dijual" -> "dijukal"). Keep diphthongs, and glide the rest like speakers do.
        p = re.sub(r"aʔi(?![aeiouə])", "ai", p)
        p = re.sub(r"aʔu(?![aeiouə])", "au", p)
        p = re.sub(r"oʔi(?![aeiouə])", "oi", p)
        for a, b in [("uʔa", "uwa"), ("uʔi", "uwi"), ("uʔe", "uwe"), ("uʔo", "uwo"), ("uʔə", "uwə"),
                     ("oʔa", "owa"), ("iʔa", "ija"), ("iʔu", "iju"), ("iʔo", "ijo"), ("iʔe", "ije"), ("eʔa", "eja")]:
            p = p.replace(a, b)
        return p

    def word(self, w):
        lw = w.lower()
        if lw in LEXICON:
            return LEXICON[lw]
        if lw not in self._g2p_cache:
            r = self.g2p(lw)
            s = "".join("".join(x) for x in r if x and x[0] not in ".,!?")
            self._g2p_cache[lw] = self.fix_vowels(s).replace("v", "f").replace("q", "k").replace("c", "tʃ")
        return self._g2p_cache[lw]

    def phonemes(self, text):
        toks = re.findall(r"[A-Za-z0-9'\-]+|[.,!?]", text)
        out = []
        for t in toks:
            if t in ".,!?":
                if out and out[-1][-1] not in ".,!?":
                    out[-1] += t
                continue
            for part in t.split("-"):
                if part:
                    # the training transcripts mark stress before every word; with the
                    # marks Whisper understands the voice far better (WER 0.15 vs 0.25)
                    out.append("ˈ" + self.word(part))
        return " ".join(out)

    def tts(self, text, spk, length_scale=1.0, ns=0.33, nsdp=0.33, seed=0):
        m = self.syn.tts_model
        m.length_scale, m.inference_noise_scale, m.inference_noise_scale_dp = length_scale, ns, nsdp
        self.torch.manual_seed(seed)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            w = self.syn.tts(self.phonemes(text), speaker_name=spk)
        return self.np.asarray(w, dtype=self.np.float32)

    def asr(self, wav, sr=SR):
        st = self.rec.create_stream()
        st.accept_waveform(sr, wav.astype(self.np.float32))
        self.rec.decode_stream(st)
        return st.result.text


# words the g2p gets wrong for this model (checked with ASR)
LEXICON = {
    "lho": "lo", "hmm": "hm", "sih": "sih",
}


def wer_words(t):
    t = t.lower().replace("-", " ")
    t = re.sub(r"[^a-z0-9' ]", " ", t)
    t = re.sub(r"\d+", lambda m: " " + _num(m.group(0)) + " ", t)
    out = []
    for w in t.split():
        out.extend(ASR_EQUIV.get(w, w).split())
    return out


ASR_EQUIV = {  # how Whisper may write what the voice said -> the normalised spelling
    "franchise": "frencais", "frensais": "frencais", "live": "laip", "tbs": "te be es", "pks": "pe ka es", "rt": "er te", "csr": "se es er",
    "phk": "pe ha ka", "sd": "es de", "gaes": "gais", "guys": "gais", "whatsapp": "wasap", "enggak": "nggak",
    "gak": "nggak", "ga": "nggak", "hm": "hmm", "mm": "hmm", "hmmm": "hmm", "youtuber": "yutuber",
    "followers": "folowers", "the": "de", "ok": "oke", "okay": "oke", "rp": "rupiah", "persen": "persen",
    "dipehaka": "dipehaka", "haha": "hahaha", "hahahaha": "hahaha", "ha": "hahaha",
}


def wer_plain(ref, hyp):
    r, h = wer_words(ref), wer_words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (0 if r[i - 1] == h[j - 1] else 1))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r))


def wer(ref, hyp):
    """Word error rate that does not count the recogniser's word splits and joins
    ("di tanam" for "ditanam", "Pahkades" for "Pak Kades"): the texts are aligned letter
    by letter without spaces, and a reference word is wrong when any of its letters is
    substituted, dropped or has letters inserted next to it."""
    r, h = wer_words(ref), wer_words(hyp)
    if not r:
        return 0.0
    rs, hs = "".join(r), "".join(h)
    owner = [k for k, w in enumerate(r) for _ in w]
    n, m = len(rs), len(hs)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (rs[i - 1] != hs[j - 1]))
    bad = set()
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (rs[i - 1] != hs[j - 1]):
            if rs[i - 1] != hs[j - 1]:
                bad.add(owner[i - 1])
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            bad.add(owner[i - 1])
            i -= 1
        else:
            bad.add(owner[min(max(i - 1, 0), n - 1)])
            j -= 1
    return len(bad) / len(r)


# ================================================================== survey: what the 83 speakers sound like

SURVEY_TEXT = ["Selamat pagi, Juragan. Kebun saya ada di dekat sungai.",
               "Kamu mau beli kebun ini? Harganya tidak murah!"]
_ENG = None


def _engine(asr=True):
    global _ENG
    if _ENG is None:
        _ENG = Engine(asr)
    return _ENG


def _pw():
    sys.modules.setdefault("pkg_resources", types.SimpleNamespace(
        get_distribution=lambda n: types.SimpleNamespace(version="0.3.5")))
    import pyworld
    return pyworld


def voice_stats(wav, sr=SR):
    import numpy as np
    pw = _pw()
    x = wav.astype(np.float64)
    f0, t = pw.dio(x, sr, f0_floor=60, f0_ceil=600, frame_period=5.0)
    f0 = pw.stonemask(x, f0, t, sr)
    v = f0[f0 > 0]
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    centroid = float((spec * freqs).sum() / max(1e-9, spec.sum()))
    st = 12 * np.log2(v / np.median(v)) if len(v) else np.zeros(1)
    return {"f0_med": float(np.median(v)) if len(v) else 0.0, "f0_sd_st": float(np.std(st)),
            "voiced": float(len(v) / max(1, len(f0))), "centroid": centroid}


def _survey_one(spk):
    import numpy as np
    e = _engine()
    out = {"speaker": spk, "wer": [], "dur": 0.0}
    wavs = []
    for i, t in enumerate(SURVEY_TEXT):
        parts = [trim(e.tts(c, spk, seed=7), SR, 0.02) for c in sentences(t)]
        w = np.concatenate([np.concatenate([p, np.zeros(int(0.25 * SR), np.float32)]) for p in parts])
        wavs.append(w)
        out["wer"].append(wer(t, e.asr(w)))
        out["hyp%d" % i] = e.asr(w)
    w = np.concatenate(wavs)
    out.update(voice_stats(w))
    out["dur"] = float(sum(len(x) for x in wavs) / SR)
    out["wer_mean"] = float(np.mean(out["wer"]))
    return out


def sentences(text):
    """Split a line into sentence chunks, each keeping its end punctuation ("..." kept)."""
    return [c.strip() for c in re.findall(r"[^.!?]+(?:\.\.\.|[.!?]+)?", text) if re.search(r"[A-Za-z]", c)]


def trim(w, sr=SR, keep=0.03, thr_db=-42.0):
    import numpy as np
    if len(w) == 0:
        return w
    fr = int(sr * 0.01)
    n = max(1, len(w) // fr)
    e = np.array([np.sqrt(np.mean(w[i * fr:(i + 1) * fr] ** 2) + 1e-12) for i in range(n)])
    db = 20 * np.log10(e / (np.max(e) + 1e-12))
    on = np.where(db > thr_db)[0]
    if len(on) == 0:
        return w[:0]
    a = max(0, on[0] * fr - int(keep * sr))
    b = min(len(w), (on[-1] + 1) * fr + int(keep * sr))
    return w[a:b]


def survey(jobs=4):
    from multiprocessing import Pool
    e = Engine(asr=False)
    spk = e.speakers
    del e
    os.makedirs(WORK, exist_ok=True)
    with Pool(jobs) as p:
        res = p.map(_survey_one, spk, chunksize=2)
    res.sort(key=lambda r: r["f0_med"])
    json.dump(res, open(os.path.join(WORK, "survey.json"), "w"), indent=1)
    for r in res:
        print("%-9s f0 %5.0f Hz  sd %4.1f st  centroid %5.0f  dur %4.1fs  wer %.2f | %s" % (
            r["speaker"], r["f0_med"], r["f0_sd_st"], r["centroid"], r["dur"], r["wer_mean"], r["hyp0"][:50]))


# ================================================================== acting: prosody + character transform

EMOTION = {  # rate (length scale x), pitch shift (semitones), range (x), energy (dB), breath (+), pause (x)
    "neutral": dict(ls=1.00, st=0.0, rng=1.30, db=0.0, br=0.00, pz=1.0),
    "warm":    dict(ls=1.03, st=0.5, rng=1.35, db=0.0, br=0.05, pz=1.05),
    "excited": dict(ls=0.90, st=1.5, rng=1.50, db=1.5, br=0.00, pz=0.8),
    "laugh":   dict(ls=0.90, st=2.0, rng=1.50, db=1.0, br=0.10, pz=0.8),
    "angry":   dict(ls=0.92, st=1.0, rng=1.45, db=2.0, br=0.00, pz=0.85),
    "scared":  dict(ls=0.88, st=1.8, rng=1.40, db=1.0, br=0.12, pz=0.8),
    "sad":     dict(ls=1.14, st=-1.3, rng=1.05, db=-1.5, br=0.15, pz=1.35),
    "worried": dict(ls=0.97, st=0.8, rng=1.30, db=0.0, br=0.08, pz=1.0),
    "sly":     dict(ls=1.06, st=-0.6, rng=1.40, db=0.0, br=0.05, pz=1.1),
}
PAUSE = {".": 0.26, "?": 0.30, "!": 0.22, "...": 0.50, "": 0.2}
WH = re.compile(r"\b(apa|siapa|kenapa|mengapa|bagaimana|gimana|berapa|kapan|mana|di mana|ke mana)\b", re.I)


def end_punct(chunk):
    c = chunk.rstrip()
    if c.endswith("..."):
        return "..."
    return c[-1] if c and c[-1] in ".?!" else ""


def render_take(e, spoken, cast, emotion, seed):
    """One performance of a line: raw TTS chunks with our pauses + intonation marks."""
    import numpy as np
    emo = EMOTION[emotion]
    chunks = sentences(spoken)
    pieces, marks, t = [], [], 0
    for k, c in enumerate(chunks):
        p = end_punct(c)
        ls = cast["rate"] * emo["ls"] * {"...": 1.08, "!": 0.96, "?": 1.0}.get(p, 1.0)
        w = trim(e.tts(c, cast["speaker"], length_scale=ls, ns=cast.get("ns", 0.5), nsdp=cast.get("nsdp", 0.6),
                       seed=seed * 101 + k), SR, 0.015)
        if len(w) == 0:
            continue
        marks.append((t, t + len(w), p, bool(WH.search(c))))
        pieces.append(w)
        t += len(w)
        if k < len(chunks) - 1:
            gap = int(PAUSE.get(p, 0.2) * emo["pz"] * cast.get("pause", 1.0) * SR)
            pieces.append(np.zeros(gap, np.float32))
            t += gap
    if not pieces:
        return None, []
    return np.concatenate(pieces), marks


def act(wav, marks, cast, emotion, seed=0):
    """WORLD resynthesis: character voice (pitch, formants, breath, tremolo, roughness) and
    a livelier intonation than the TTS gives (range, question rise, exclamation lift)."""
    import numpy as np
    pw = _pw()
    rng = np.random.default_rng(seed)
    emo = EMOTION[emotion]
    x = wav.astype(np.float64)
    fp = 5.0
    f0, tt = pw.dio(x, SR, f0_floor=55, f0_ceil=650, frame_period=fp)
    f0 = pw.stonemask(x, f0, tt, SR)
    sp = pw.cheaptrick(x, f0, tt, SR)
    ap = pw.d4c(x, f0, tt, SR)
    n = len(f0)
    voiced = f0 > 0
    lf = np.zeros(n)
    lf[voiced] = np.log2(f0[voiced])
    if voiced.sum() > 10:
        # smooth tiny octave glitches, then widen the melody around each phrase's own mean
        mu = np.median(lf[voiced])
        dev = lf - mu
        dev[voiced] = np.clip(dev[voiced], -0.8, 0.8)
        lf[voiced] = mu + dev[voiced] * cast.get("range", 1.0) * (1.0 + (emo["rng"] - 1.3) * 0.5)
        # phrase intonation
        for a, b, p, wh in marks:
            fa, fb = int(a / SR * 1000 / fp), min(n, int(b / SR * 1000 / fp))
            idx = np.arange(fa, fb)
            vi = idx[voiced[idx]] if len(idx) else idx
            if len(vi) < 4:
                continue
            last = vi[-1]
            if p == "?":
                rise = (1.5 if wh else 3.5) / 12.0
                span = int(260 / fp)
                r = np.clip((np.arange(n) - (last - span)) / span, 0, 1)
                lf[voiced] += (r * rise)[voiced] * ((np.arange(n) <= last + 2) & (np.arange(n) >= fa))[voiced]
            elif p == "!":
                lift = np.zeros(n)
                lift[fa:fb] = 0.8 / 12.0
                first = vi[: max(4, len(vi) // 3)]
                lift[first] += 0.6 / 12.0  # the push on the first stressed words
                lf[voiced] += lift[voiced]
            elif p == "...":
                span = int(320 / fp)
                r = np.clip((np.arange(n) - (last - span)) / span, 0, 1)
                lf[voiced] -= (r * 1.5 / 12.0)[voiced] * ((np.arange(n) >= fa) & (np.arange(n) <= last + 2))[voiced]
        shift = (cast.get("pitch", 0.0) + emo["st"]) / 12.0
        lf[voiced] += shift
        ts = np.arange(n) * fp / 1000.0
        if cast.get("tremolo", 0) > 0:  # elders: a slow wobble
            lf[voiced] += (cast["tremolo"] / 12.0 * np.sin(2 * np.pi * 5.3 * ts + rng.uniform(0, 6)))[voiced]
        if cast.get("rough", 0) > 0:  # gruff voices: jitter
            lf[voiced] += (rng.normal(0, cast["rough"] / 12.0, n))[voiced]
        f0 = np.where(voiced, np.clip(2.0 ** lf, 55.0, 620.0), 0.0)
    # formants: warp the spectral envelope along frequency (alpha > 1: smaller body)
    alpha = cast.get("formant", 1.0)
    if abs(alpha - 1.0) > 1e-3:
        bins = sp.shape[1]
        src = np.arange(bins) / alpha
        src = np.clip(src, 0, bins - 1)
        i0 = np.floor(src).astype(int)
        i1 = np.minimum(i0 + 1, bins - 1)
        fr = src - i0
        lsp = np.log(sp + 1e-16)
        lsp = lsp[:, i0] * (1 - fr) + lsp[:, i1] * fr
        sp = np.exp(lsp)
    # breath: more aperiodic energy in the upper bands
    br = cast.get("breath", 0.0) + emo["br"]
    if br > 0:
        bins = ap.shape[1]
        fr = np.linspace(0, SR / 2, bins)
        wgt = np.clip((fr - 1200) / 2500, 0, 1) * min(0.9, br)
        ap = ap + (1 - ap) * wgt[None, :]
    ap = np.clip(ap, 0.0, 1.0)
    y = pw.synthesize(f0, np.ascontiguousarray(sp), np.ascontiguousarray(ap), SR, fp)
    return y.astype(np.float32), float(emo["db"])


def master(y, gain_db=0.0, lufs=-18.0):
    """EQ (high-pass, a little presence, de-ess), gentle compression, loudness, peak <= -1 dBFS,
    silence trimmed to <= 150 ms, short fades."""
    import numpy as np
    import pyloudnorm
    from scipy import signal
    y = y.astype(np.float64)
    sos = signal.butter(2, 75, "highpass", fs=SR, output="sos")
    y = signal.sosfilt(sos, y)
    # presence: +2 dB bell around 3 kHz (parallel band)
    sos_p = signal.butter(2, [2200, 4200], "bandpass", fs=SR, output="sos")
    y = y + (10 ** (2 / 20) - 1) * signal.sosfilt(sos_p, y)
    # de-ess: duck the 5.5-9 kHz band where it dominates
    sos_s = signal.butter(2, [5500, 9500], "bandpass", fs=SR, output="sos")
    s = signal.sosfilt(sos_s, y)
    env_s = np.sqrt(signal.sosfilt(signal.butter(1, 30, fs=SR, output="sos"), s ** 2) + 1e-12)
    env_a = np.sqrt(signal.sosfilt(signal.butter(1, 30, fs=SR, output="sos"), y ** 2) + 1e-12)
    ratio = env_s / (env_a + 1e-9)
    red = np.clip((ratio - 0.35) / 0.4, 0, 1) * 0.6
    y = y - s * red
    # compression 2.5:1 above -22 dBFS RMS (10 ms attack, 120 ms release)
    lvl = np.abs(y)
    env = np.zeros_like(lvl)
    a_att, a_rel = np.exp(-1 / (0.010 * SR)), np.exp(-1 / (0.120 * SR))
    e_ = 0.0
    for i in range(len(lvl)):
        v = lvl[i]
        c = a_att if v > e_ else a_rel
        e_ = c * e_ + (1 - c) * v
        env[i] = e_
    thr = 10 ** (-22 / 20)
    over = np.maximum(env / thr, 1.0)
    y = y * over ** (1 / 2.5 - 1)
    # trim: keep 60 ms before the first sound, 110 ms after the last
    y = trim(y.astype(np.float32), SR, 0.0, -38.0).astype(np.float64)
    lead, tail = np.zeros(int(0.06 * SR)), np.zeros(int(0.11 * SR))
    fade = int(0.008 * SR)
    if len(y) > 2 * fade:
        y[:fade] *= np.linspace(0, 1, fade)
        y[-fade:] *= np.linspace(1, 0, fade)
    y = np.concatenate([lead, y, tail])
    meter = pyloudnorm.Meter(SR, block_size=0.2 if len(y) / SR < 0.5 else 0.4)
    try:
        loud = meter.integrated_loudness(y)
    except Exception:
        loud = -30.0
    if not np.isfinite(loud):
        loud = -30.0
    y = y * 10 ** ((lufs + gain_db * 0.5 - loud) / 20)
    peak = np.max(np.abs(y)) + 1e-12
    lim = 10 ** (-1.2 / 20)
    if peak > lim:  # soft-knee peak limiter (tanh above the knee)
        k = lim * 0.7
        a = np.abs(y)
        m = a > k
        y[m] = np.sign(y[m]) * (k + (lim - k) * np.tanh((a[m] - k) / (lim - k)))
    return y.astype(np.float32)


# ================================================================== casting
# base speaker (survey: median F0 / brightness / liveliness) + WORLD transform:
# pitch (semitones), formant (spectral envelope warp, >1 = smaller body / younger),
# rate (VITS length scale, >1 = slower), range (melody widening), breath, tremolo
# (semitones, elders), rough (jitter, gruff voices), pause (x sentence gaps),
# phone (band-limited like a phone call).
CASTING = {
    # the phone boss: slick and fast, heard through a phone
    "hq":       dict(speaker="ardi", pitch=1.0, formant=1.0, rate=0.86, range=1.25, pause=0.7, phone=True,
                     feel="slick corporate boss on the phone, fast"),
    "player":   dict(speaker="wibowo", pitch=0.0, formant=1.0, rate=0.97, range=1.05, feel="the Juragan: confident young man"),
    "kades":    dict(speaker="JV-00027", pitch=-1.5, formant=0.94, rate=1.15, range=1.45, pause=1.2,
                     feel="village head: pompous, slow, deep"),
    "rt":       dict(speaker="SU-00060", pitch=0.5, formant=0.98, rate=0.95, range=1.35, feel="RT head: eager, a little nasal"),
    "calo":     dict(speaker="JV-01932", pitch=-0.5, formant=0.96, rate=0.95, range=1.3, rough=0.35, breath=0.1,
                     feel="broker Bang Jeki: sly and gravelly"),
    "mak":      dict(speaker="gadis", pitch=-1.5, formant=0.97, rate=1.02, range=1.2, breath=0.08,
                     feel="Mak Inah: warm stall keeper"),
    "wartawan": dict(speaker="SU-00691", pitch=0.0, formant=1.0, rate=0.93, range=1.2, feel="investigative reporter: crisp"),
    # land owners
    "kakek":    dict(speaker="SU-01596", pitch=1.0, formant=0.97, rate=1.22, range=1.35, tremolo=0.35, breath=0.25, pause=1.3,
                     feel="old farmer: gentle, slow, shaky"),
    "ibu":      dict(speaker="SU-05051", pitch=0.0, formant=1.0, rate=1.0, range=1.3, feel="careful mother"),
    "nenek":    dict(speaker="JV-00658", pitch=-2.0, formant=0.99, rate=1.22, range=1.25, tremolo=0.4, breath=0.3, pause=1.25,
                     feel="kind grandmother: slow, breathy"),
    "pemuda":   dict(speaker="JV-04175", pitch=1.0, formant=1.0, rate=0.9, range=1.4, feel="young activist: quick, defiant"),
    "petani":   dict(speaker="SU-01552", pitch=0.0, formant=1.0, rate=1.05, range=1.25, breath=0.05, feel="hard-working farmer"),
    "somad":    dict(speaker="SU-09243", pitch=-0.5, formant=0.95, rate=1.12, range=1.3, tremolo=0.1, feel="stingy haji: measured"),
    "ucok":     dict(speaker="JV-02326", pitch=-0.5, formant=0.97, rate=0.95, range=1.65, rough=0.1, feel="boatman: loud, sing-song"),
    "rian":     dict(speaker="JV-05522", pitch=2.0, formant=1.02, rate=0.86, range=1.5, feel="content creator: fast, bright"),
    "wati":     dict(speaker="JV-02884", pitch=1.5, formant=1.03, rate=0.9, range=1.5, feel="jamu seller: chatty gossip"),
    "slamet":   dict(speaker="JV-07765", pitch=-0.5, formant=1.0, rate=1.15, range=1.15, breath=0.1, feel="patient rubber tapper: soft"),
    "dullah":   dict(speaker="SU-03650", pitch=-1.5, formant=0.94, rate=1.25, range=1.2, tremolo=0.2, breath=0.15, pause=1.35,
                     feel="customary elder: deep, dignified"),
    "lastri":   dict(speaker="SU-02092", pitch=0.0, formant=1.0, rate=0.98, range=1.35, feel="teacher: clear, articulate"),
    "romlah":   dict(speaker="SU-02953", pitch=-3.0, formant=0.98, rate=1.28, range=1.2, tremolo=0.5, breath=0.35, pause=1.3,
                     feel="frail grandmother"),
    "darsih":   dict(speaker="JV-02059", pitch=-3.5, formant=0.95, rate=1.15, range=1.4, tremolo=0.2, breath=0.25,
                     feel="village midwife-healer: low, mystical"),
    "yanto":    dict(speaker="SU-02716", pitch=0.0, formant=1.0, rate=1.05, range=1.3, breath=0.12, feel="laid-off worker: tired"),
    "karta":    dict(speaker="SU-03391", pitch=0.5, formant=1.0, rate=0.97, range=1.55, feel="goat farmer: jolly"),
    "bidan":    dict(speaker="SU-01359", pitch=0.0, formant=1.0, rate=0.95, range=1.45, feel="midwife: firm, precise"),
    # hamlet folk without land
    "karim":    dict(speaker="SU-09757", pitch=0.0, formant=0.99, rate=1.12, range=1.3, pause=1.15, feel="ustad: calm, measured"),
    "tini":     dict(speaker="JV-01392", pitch=1.0, formant=1.01, rate=0.92, range=1.6, feel="vegetable seller: loud, cheerful"),
    "sari":     dict(speaker="SU-03887", pitch=4.0, formant=1.16, rate=0.95, range=1.4, feel="girl, about eight"),
    "budi":     dict(speaker="JV-07638", pitch=2.0, formant=1.12, rate=0.93, range=1.4, feel="boy, about nine"),
    "udin":     dict(speaker="JV-04679", pitch=3.0, formant=1.14, rate=0.9, range=1.5, feel="cheeky boy"),
    "eko":      dict(speaker="JV-05219", pitch=0.5, formant=1.0, rate=0.88, range=1.35, feel="ojek driver: quick, casual"),
    "tigor":    dict(speaker="SU-08659", pitch=-1.5, formant=0.93, rate=1.0, range=1.5, rough=0.3, feel="foreman: gruff, loud"),
    "ipah":     dict(speaker="SU-04748", pitch=-2.5, formant=0.98, rate=1.18, range=1.2, tremolo=0.45, breath=0.3,
                     feel="old weaver: wistful"),
    "rahmat":   dict(speaker="JV-03424", pitch=-0.5, formant=0.99, rate=1.02, range=1.3, rough=0.15, breath=0.1,
                     feel="fisherman: weathered"),
    "asep":     dict(speaker="SU-04511", pitch=0.0, formant=1.0, rate=0.98, range=1.45, feel="Sundanese carpenter: friendly"),
    "neneng":   dict(speaker="SU-05507", pitch=1.0, formant=1.01, rate=0.94, range=1.5, feel="Sundanese coffee stall: lively"),
    # passers-by
    "warga_petani": dict(speaker="SU-06003", pitch=0.0, formant=1.0, rate=1.05, range=1.25, feel="passer-by farmer"),
    "warga_ibu":    dict(speaker="JV-06510", pitch=0.0, formant=1.0, rate=1.02, range=1.3, feel="passer-by woman"),
    "warga_buruh":  dict(speaker="JV-06080", pitch=-1.0, formant=0.97, rate=1.0, range=1.3, rough=0.1, feel="passer-by labourer"),
    "warga_pemuda": dict(speaker="JV-03314", pitch=1.0, formant=1.0, rate=0.92, range=1.35, feel="passer-by young man"),
    "warga_nenek":  dict(speaker="JV-04982", pitch=-2.5, formant=0.99, rate=1.2, range=1.2, tremolo=0.35, breath=0.25,
                         feel="passer-by grandmother"),
    "warga_kakek":  dict(speaker="SU-01899", pitch=0.5, formant=0.97, rate=1.2, range=1.2, tremolo=0.3, breath=0.2,
                         feel="passer-by grandfather"),
    "warga_anak":   dict(speaker="SU-00297", pitch=4.0, formant=1.15, rate=0.95, range=1.4, feel="passer-by child"),
}
# a portrait with no named speaker still gets a fitting voice
PORTRAIT_VOICE = {"kakek": "warga_kakek", "nenek": "warga_nenek", "ibu": "warga_ibu", "petani": "warga_petani",
                  "buruh": "warga_buruh", "pemuda": "warga_pemuda", "anak": "warga_anak", "kades": "kades",
                  "calo": "calo", "hq": "hq", "uang": "hq", "player": "player", "mak": "mak", "petugas": "wartawan",
                  "preman": "tigor"}
RENDER_VERSION = 3


def cast():
    man = json.load(open(MANIFEST, encoding="utf-8"))
    survey = {}
    sp = os.path.join(WORK, "survey.json")
    if os.path.exists(sp):
        survey = {r["speaker"]: r for r in json.load(open(sp))}
    missing = [c for c in man["characters"] if c not in CASTING]
    if missing:
        sys.exit("no casting for: " + ", ".join(missing))
    combos = {}
    out = {}
    for cid, c in CASTING.items():
        key = (c["speaker"], c.get("pitch", 0), c.get("formant", 1), c.get("rate", 1))
        if key in combos:
            sys.exit("same voice for %s and %s" % (cid, combos[key]))
        combos[key] = cid
        s = survey.get(c["speaker"], {})
        f0 = s.get("f0_med", 0) * 2 ** (c.get("pitch", 0) / 12)
        out[cid] = dict(c, name=man["characters"].get(cid, {}).get("name", cid),
                        base_f0=round(s.get("f0_med", 0), 1), target_f0=round(f0, 1))
    json.dump({"generated_by": "tools/make_voices.py cast", "cast": out}, open(CAST, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("cast: %d characters, %d distinct base speakers -> %s" % (
        len(out), len({c["speaker"] for c in out.values()}), CAST))
    for cid, c in out.items():
        print("  %-13s %-9s f0 %5.0f -> %5.0f Hz  formant %.2f  rate %.2f  %s" % (
            cid, c["speaker"], c["base_f0"], c["target_f0"], c.get("formant", 1), c.get("rate", 1), c.get("feel", "")))
    return out


# ================================================================== render

LEX0 = {"lho": "lo", "hmm": "hm", "sih": "sih"}


def _sig(line, c):
    """What a clip was rendered from: re-rendered when the text, mood, casting or a
    lexicon entry for one of its words changes."""
    words = set(re.findall(r"[a-z']+", line["spoken"].lower()))
    extra = sorted((k, v) for k, v in LEXICON.items() if k in words and LEX0.get(k) != v)
    payload = [RENDER_VERSION, line["spoken"], line["emotion"], {k: v for k, v in c.items() if k not in ("feel", "name")},
               sorted(LEX0.items())] + ([extra] if extra else [])
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:10]


def phone_fx(y):
    import numpy as np
    from scipy import signal
    sos = signal.butter(2, [220, 4800], "bandpass", fs=SR, output="sos")
    z = signal.sosfilt(sos, y.astype(np.float64))
    z = np.tanh(z / (np.max(np.abs(z)) + 1e-9) * 1.2) * 0.8
    return z.astype(np.float32)


def perform(e, line, c, seed, careful=False):
    import numpy as np
    c = dict(c)
    if careful:  # a slower, steadier read for lines the recogniser stumbles on
        c["rate"] = c.get("rate", 1.0) * 1.1
        c["ns"], c["nsdp"] = 0.33, 0.3
    raw, marks = render_take(e, line["spoken"], c, line["emotion"], seed)
    if raw is None:
        return None
    y, gain = act(raw, marks, c, line["emotion"], seed)
    if c.get("phone"):
        y = phone_fx(y)
    y = master(y, gain)
    hyp = e.asr(y)
    w = wer(line["spoken"], hyp)
    return {"wav": y, "hyp": hyp, "wer": w, "seed": seed, "careful": careful}


FEATURED = {"intro", "CHAT", "EXTRAS", "KID", "WALKER_LINES", "_greeting", "CHAT_LANDLESS", "open_calo",
            "run_morning_events"}


def _render_one(job):
    import numpy as np
    import soundfile as sf
    line, c, out = job
    e = _engine()
    takes = []
    plan = [(1, False), (2, False), (3, False), (4, True), (5, True), (6, True)]
    is_bark = line["src"].startswith("bark")
    # the lines players hear most get at least two performances to choose from
    min_takes = 2 if line["src"] in FEATURED else 1
    for seed, careful in plan:
        t = perform(e, line, c, seed, careful)
        if t is None:
            continue
        takes.append(t)
        best_w = min(x["wer"] for x in takes)
        if len(takes) >= min_takes and best_w <= 0.1:
            break
        if len(takes) >= 2 and best_w <= 0.2:
            break
        if len(takes) >= 3 and best_w <= 0.25:
            break
        if is_bark and len(takes) >= 3:
            break
    if not takes:
        return {"key": line["key"], "char": line["char"], "error": "no audio"}
    # the most intelligible take; among equals the one with the liveliest melody
    best = min(takes, key=lambda x: (round(x["wer"], 3), -_f0_sd(x["wav"])))
    y = best["wav"]
    sf.write(out + ".wav", y, SR, subtype="PCM_16")
    qa = {"key": line["key"], "char": line["char"], "spoken": line["spoken"], "hyp": best["hyp"], "wer": best["wer"],
          "takes": len(takes), "seed": best["seed"], "careful": best["careful"], "dur": len(y) / SR,
          "peak_db": float(20 * np.log10(np.max(np.abs(y)) + 1e-9)), "sig": _sig(line, c), "emotion": line["emotion"],
          "src": line["src"], **{k: v for k, v in voice_stats(y).items() if k in ("f0_med", "f0_sd_st")}}
    json.dump(qa, open(out + ".json", "w"), ensure_ascii=False)
    return qa


def _f0_sd(y):
    try:
        return voice_stats(y)["f0_sd_st"]
    except Exception:
        return 0.0


def render(jobs=4, only=None, force=False, limit=None):
    from multiprocessing import Pool
    man = json.load(open(MANIFEST, encoding="utf-8"))
    cast_ = json.load(open(CAST, encoding="utf-8"))["cast"]
    todo = []
    for l in man["lines"]:
        if only and l["char"] not in only:
            continue
        c = cast_[l["char"]]
        d = os.path.join(WORK, "clips", l["char"])
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, l["key"])
        if not force and os.path.exists(out + ".json") and os.path.exists(out + ".wav"):
            try:
                if json.load(open(out + ".json")).get("sig") == _sig(l, c):
                    continue
            except Exception:
                pass
        todo.append((l, c, out))
    if limit:
        todo = todo[:limit]
    print("render: %d clips to do" % len(todo), flush=True)
    done = 0
    worst = []
    with Pool(jobs) as p:
        for qa in p.imap_unordered(_render_one, todo, chunksize=1):
            done += 1
            if qa.get("wer", 1) > 0.25:
                worst.append(qa)
            if done % 20 == 0 or done == len(todo):
                print("  %d/%d  (%d over 0.25 WER so far)" % (done, len(todo), len(worst)), flush=True)
    for q in worst:
        print("  WER %.2f %s: %s | %s" % (q.get("wer", 1), q["char"], q.get("spoken", ""), q.get("hyp", "")))


# ================================================================== pack: one Ogg bank per character + index

GAP = 0.12        # silence between clips inside a bank (the player seeks to each start)
OGG_QUALITY = 2   # libvorbis -q:a (22 kHz mono speech: ~30 kbit/s)


def pack():
    import subprocess
    import numpy as np
    import soundfile as sf
    man = json.load(open(MANIFEST, encoding="utf-8"))
    cast_ = json.load(open(CAST, encoding="utf-8"))["cast"]
    os.makedirs(VOICES, exist_ok=True)
    open(os.path.join(VOICES, ".gdignore"), "w").write("")  # served as files, never imported into the pack
    by_char = {}
    for l in man["lines"]:
        by_char.setdefault(l["char"], []).append(l)
    banks, report, missing = {}, [], []
    total_bytes = 0
    qa_all = []
    for cid, lines in by_char.items():
        parts, clips, t = [], {}, 0.0
        for l in lines:
            base = os.path.join(WORK, "clips", cid, l["key"])
            if not os.path.exists(base + ".wav"):
                missing.append("%s %s" % (cid, l["text"][:40]))
                continue
            y, sr = sf.read(base + ".wav", dtype="float32")
            assert sr == SR
            qa = json.load(open(base + ".json"))
            qa_all.append(qa)
            clips[l["key"]] = [round(t, 3), round(len(y) / SR, 3)]
            parts.append(y)
            parts.append(np.zeros(int(GAP * SR), np.float32))
            t += len(y) / SR + GAP
        if not parts:
            continue
        wav = np.concatenate(parts)
        tmp = os.path.join(WORK, "bank_%s.wav" % cid)
        sf.write(tmp, wav, SR, subtype="PCM_16")
        out = os.path.join(VOICES, cid + ".ogg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-ac", "1", "-ar", str(SR),
                        "-c:a", "libvorbis", "-q:a", str(OGG_QUALITY), out], check=True)
        os.remove(tmp)
        size = os.path.getsize(out)
        total_bytes += size
        barks = {mood: text_key(txt) for mood, txt in man["barks"].get(cid, {}).items()
                 if text_key(txt) in clips}
        banks[cid] = {"file": cid + ".ogg", "bytes": size, "dur": round(t, 2), "clips": clips, "barks": barks}
        report.append((cid, len(clips), t, size))
    portraits = {k: v for k, v in PORTRAIT_VOICE.items() if v in banks}
    index = {"version": RENDER_VERSION, "generated_by": "tools/make_voices.py pack", "sample_rate": SR,
             "speakers": man["speakers"], "portraits": portraits, "banks": banks,
             "templates": [{k: v for k, v in t.items() if k in ("chars", "re", "group", "variants", "default", "by_capture")}
                           for t in man["templates"]]}
    for p in (os.path.join(VOICES, "index.json"), INDEX_RES):
        json.dump(index, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    # QA summary
    wers = [q["wer"] for q in qa_all]
    passed = sum(1 for w in wers if w <= 0.25)
    print("pack: %d banks, %d clips, %.1f min of speech, %.2f MB Ogg -> %s" % (
        len(banks), sum(r[1] for r in report), sum(r[2] for r in report) / 60, total_bytes / 1e6, VOICES))
    print("  ASR (Whisper small) WER <= 0.25: %d/%d clips (%.1f%%), mean WER %.3f, exact %d" % (
        passed, len(wers), 100.0 * passed / max(1, len(wers)), float(np.mean(wers)) if wers else 0, sum(1 for w in wers if w == 0)))
    peaks = [q["peak_db"] for q in qa_all]
    print("  peak max %.2f dBFS, clips over -1 dBFS: %d" % (max(peaks), sum(1 for p in peaks if p > -1.0)))
    for cid, n, t, size in sorted(report, key=lambda r: -r[3]):
        c = cast_.get(cid, {})
        print("  %-13s %3d clips %6.1fs %7.0f KB  %s" % (cid, n, t, size / 1024, c.get("speaker", "")))
    if missing:
        print("  MISSING %d clips (run render):" % len(missing), missing[:10])
    fails = [q for q in qa_all if q["wer"] > 0.25]
    for q in sorted(fails, key=lambda q: -q["wer"]):
        print("  WER %.2f %-10s %s | heard: %s" % (q["wer"], q["char"], q["spoken"], q["hyp"]))
    json.dump({"clips": len(wers), "pass": passed, "mean_wer": float(np.mean(wers)) if wers else 0,
               "fails": [(q["char"], q["spoken"], q["hyp"], q["wer"]) for q in fails],
               "mb": total_bytes / 1e6}, open(os.path.join(WORK, "qa_summary.json"), "w"), ensure_ascii=False, indent=1)
    return index


def qa(png=True):
    """Objective checks on the final clips: loudness, peaks, lead/tail silence, pitch and
    brightness per character (how different the voices are), ASR pass rate; a spectrogram
    sheet (one line per character) goes to /tmp/audio_work/voice/qa_voices.png."""
    import glob
    import numpy as np
    import pyloudnorm
    import soundfile as sf
    man = json.load(open(MANIFEST, encoding="utf-8"))
    cast_ = json.load(open(CAST, encoding="utf-8"))["cast"]
    meter = pyloudnorm.Meter(SR)
    per = {}
    louds, leads, tails, peaks = [], [], [], []
    for l in man["lines"]:
        base = os.path.join(WORK, "clips", l["char"], l["key"])
        if not os.path.exists(base + ".wav"):
            continue
        y, _ = sf.read(base + ".wav", dtype="float64")
        q = json.load(open(base + ".json"))
        if len(y) / SR >= 0.6:
            louds.append(meter.integrated_loudness(y))
        peaks.append(20 * np.log10(np.max(np.abs(y)) + 1e-12))
        on = np.where(np.abs(y) > 0.01)[0]
        if len(on):
            leads.append(on[0] / SR * 1000)
            tails.append((len(y) - on[-1]) / SR * 1000)
        p_ = per.setdefault(l["char"], {"f0": [], "sd": [], "cent": [], "wer": [], "n": 0, "dur": 0.0})
        p_["n"] += 1
        p_["dur"] += len(y) / SR
        p_["wer"].append(q["wer"])
        if q.get("f0_med"):
            p_["f0"].append(q["f0_med"])
            p_["sd"].append(q["f0_sd_st"])
        spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
        fr = np.fft.rfftfreq(len(y), 1 / SR)
        p_["cent"].append(float((spec * fr).sum() / (spec.sum() + 1e-9)))
    allw = [w for p_ in per.values() for w in p_["wer"]]
    print("QA: %d clips, %d characters" % (len(allw), len(per)))
    print("  loudness: median %.1f LUFS (%.1f .. %.1f)" % (np.median(louds), np.min(louds), np.max(louds)))
    print("  peaks: max %.2f dBFS  | lead silence median %.0f ms (max %.0f) | tail median %.0f ms (max %.0f)" % (
        max(peaks), np.median(leads), max(leads), np.median(tails), max(tails)))
    print("  ASR: %d/%d clips WER <= 0.25 (%.1f%%), %d exact, mean %.3f" % (
        sum(w <= 0.25 for w in allw), len(allw), 100 * np.mean([w <= 0.25 for w in allw]), sum(w == 0 for w in allw), np.mean(allw)))
    print("  melody: median F0 spread per line %.1f semitones (TTS speakers before acting: %.1f)" % (
        np.median([x for p_ in per.values() for x in p_["sd"]]), _survey_sd()))
    print("  %-13s %-9s %4s %6s %6s %6s %6s  %s" % ("character", "speaker", "n", "F0", "sd st", "bright", "WER", "feel"))
    for cid, p_ in sorted(per.items(), key=lambda kv: np.median(kv[1]["f0"]) if kv[1]["f0"] else 0):
        c = cast_.get(cid, {})
        print("  %-13s %-9s %4d %6.0f %6.1f %6.0f %6.3f  %s" % (cid, c.get("speaker", ""), p_["n"], np.median(p_["f0"]),
              np.median(p_["sd"]), np.median(p_["cent"]), np.mean(p_["wer"]), c.get("feel", "")))
    if png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        chars = sorted(per.keys())
        cols = 3
        rows = (len(chars) + cols - 1) // cols
        fig, axs = plt.subplots(rows, cols, figsize=(18, rows * 1.9))
        for ax, cid in zip(axs.flat, chars):
            ls = [l for l in man["lines"] if l["char"] == cid and l["src"] in ("CHAT", "EXTRAS", "KID", "WALKER_LINES", "intro", "_gossip", "open_calo", "_sleep", "run_morning_events")]
            l = (ls or [l for l in man["lines"] if l["char"] == cid])[0]
            y, _ = sf.read(os.path.join(WORK, "clips", cid, l["key"]) + ".wav")
            ax.specgram(y, NFFT=512, Fs=SR, noverlap=384, cmap="magma", vmin=-110)
            ax.set_ylim(0, 8000)
            ax.set_title("%s (%s): %s" % (cid, cast_[cid]["speaker"], l["text"][:48]), fontsize=8)
            ax.tick_params(labelsize=6)
        for ax in list(axs.flat)[len(chars):]:
            ax.axis("off")
        plt.tight_layout()
        plt.savefig(os.path.join(WORK, "qa_voices.png"), dpi=60)
        print("  sheet ->", os.path.join(WORK, "qa_voices.png"))


def _survey_sd():
    import numpy as np
    sp = os.path.join(WORK, "survey.json")
    return float(np.median([r["f0_sd_st"] for r in json.load(open(sp))])) if os.path.exists(sp) else float("nan")


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "all"
    opt = {a.split("=")[0].lstrip("-"): (a.split("=", 1)[1] if "=" in a else True) for a in args[1:]}
    jobs = int(opt.get("jobs", 4))
    only = set(str(opt["only"]).split(",")) if "only" in opt else None
    if cmd in ("extract", "all"):
        extract()
    if cmd == "survey":
        survey(jobs)
    if cmd in ("cast", "all"):
        cast()
    if cmd in ("render", "all"):
        render(jobs, only, bool(opt.get("force", False)), int(opt["limit"]) if "limit" in opt else None)
    if cmd in ("pack", "all"):
        pack()
    if cmd in ("qa", "all"):
        qa()


if __name__ == "__main__":
    main()
