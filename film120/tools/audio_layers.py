#!/usr/bin/env python3
"""Licensed audio layers for the mix: fetch + cut + measure the recordings that are actually used (runs in the sandbox: internet + ffmpeg),
and add them as 'file' events next to the procedural sounds in the cue sheet.

  audio_layers.py fetch OUT_DIR                          -> OUT_DIR/<id>.wav (48 kHz stereo, slice already cut/reversed), OUT_DIR/licensed.json (mixer specs), OUT_DIR/used.json (credit records)
  audio_layers.py layer EVENTS.json LICENSED.json OUT_EVENTS.json

Every licensed sound only ever *supports* a procedural one (same event, lower gain, transient aligned to the event) or sits far below the score (music beds), so a mis-judged file
(nobody has listened to any of them - they were selected by metadata and measurements only) cannot carry a moment on its own.
Level, peak and clipping of every layer are printed by `fetch`; the mixer prints the layer/score balance."""
import hashlib, json, os, re, subprocess, sys, zipfile, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(os.path.dirname(HERE), 'data', 'audio')
UA = 'Mozilla/5.0 (film120-audio; contact leonrdewa@gmail.com)'

# event kind -> how the licensed layer is aligned to the event, and the (sound id, gain) list used in rotation.
#   peak : transient lands on t          mid : peak lands on t + dur/2 (sweeps)          end : peak lands on t + dur (builds)          start : file starts at t
LAYERS = {
    'tick':      dict(mode='peak', ids=[('tick_kenney_001', .5), ('tick_kenney_select_007', .5), ('tick_dc_stopwatch', .4), ('tick_oga_clock_1', .4)]),
    'tick_hi':   dict(mode='peak', ids=[('tick_kenney_002', .5), ('tick_kenney_004', .5), ('click_glass_kenney', .4)]),
    'data_blip': dict(mode='peak', ids=[('blip_oga_ui_2', .35), ('click_select_kenney', .4), ('tick_kenney_004', .4)]),
    'type_hit':  dict(mode='peak', ids=[('typing_oga_keypress_001', .5), ('typing_oga_keypress_004', .5), ('typing_wws_typewriter_strike', .4), ('typing_dc_space_bar', .4), ('typing_mixkit_1365', .35)]),
    'lock':      dict(mode='peak', ids=[('click_bong_kenney', .7), ('click_thump_kenney', .7), ('click_pluck_kenney', .5), ('click_oga_clickety_14', .6), ('slide_dc_sandwich_box_snap', .5), ('click_mixkit_1129', .4), ('film_splice_wws', .4), ('slide_dc_jewelry_latch', .4)]),
    'whoosh':    dict(mode='mid', dur=.4, ids=[('whoosh_short_mixkit_1462', .5), ('whoosh_short_mixkit_166', .5), ('whoosh_med_mixkit_1489', .4), ('whoosh_short_swish_oga', .5), ('whoosh_short_open_kenney', .5), ('whoosh_med_mixkit_2604', .35)]),
    'jump':      dict(mode='mid', dur=.6, ids=[('swell_air_vacuum_mixkit', .5), ('whoosh_short_open_kenney', .5), ('swell_electric_charge_mixkit', .4)]),
    'slide':     dict(mode='peak', ids=[('slide_casino_card_slide_1', .6), ('slide_casino_card_shove_1', .5), ('slide_casino_card_place_4', .5), ('slide_mixkit_paper_1530', .45), ('slide_mixkit_futuristic_1533', .4), ('slide_kenney_interface_switch_004', .4), ('film_slide_changer_dc', .4)]),
    'impact':    dict(mode='peak', ids=[('impact_low_explosion_kenney', .7), ('impact_deep_drum_mixkit', .6), ('impact_plate_heavy_kenney', .6), ('impact_cinematic_echo_mixkit', .55), ('impact_horror_hit_mixkit', .5), ('impact_explosion_crunch_kenney', .5)]),
    'sub_drop':  dict(mode='peak', ids=[('sub_muffled_boom_oga', .6), ('sub_low_explosion_001_kenney', .6), ('sub_stomp_mixkit', .5), ('sub_explosion_crunch_004_kenney', .5)]),
    'swell':     dict(mode='end', dur=1.0, ids=[('swell_rev_bell_kenney', .5), ('swell_rev_crunch_kenney', .5), ('swell_rev_low_explosion_kenney', .5), ('swell_rev_deep_drum_mixkit', .5)]),
    'riser':     dict(mode='end', dur=1.0, ids=[('riser_mixkit_790', .5), ('riser_mixkit_792', .5), ('riser_mixkit_786', .45), ('riser_mixkit_2666', .45), ('riser_mixkit_1144', .45)]),
    'shutter':   dict(mode='peak', ids=[('shutter_slr_cc0', .6), ('shutter_oga_photo', .5)]),
    'freeze':    dict(mode='end', dur=.5, ids=[('swell_rev_deep_drum_mixkit', .5)]),
    'tape_stop': dict(mode='start', ids=[('tape_kenney_zap_three_down', .5), ('tape_retro_fall2_oga', .45)]),
}
# licensed music beds (far below the score; ducked with it under the narration).  seg = seconds inside the source file; place = film time.
MUSIC = {
    'bed_drone_in_d': dict(track='macleod_drone_in_d', seg=(73.0, 103.0), place=0.0, dur=28.0, fade_in=1.5, fade_out=3.5, gain=1.0),
    'bed_above_the_clouds': dict(track='bartmann_above_the_clouds', seg=(163.0, 193.0), place=89.0, dur=30.0, fade_in=4.0, fade_out=1.5, gain=.55),
}


def sh(cmd, **kw): return subprocess.run(cmd, capture_output=True, text=True, **kw)


def download(url, cache):
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or '.bin'; dst = os.path.join(cache, hashlib.md5(url.encode()).hexdigest()[:12] + ext)
    if not (os.path.exists(dst) and os.path.getsize(dst) > 500):
        r = sh(['curl', '-sS', '-L', '-m', '300', '-A', UA, '-o', dst, '-w', '%{http_code}', url])
        if r.stdout.strip() != '200': raise RuntimeError(f'http {r.stdout.strip()} {url}')
    return dst


def source_file(s, cache):
    p = download(s['url'], cache)
    if p.endswith('.zip'):
        d = p[:-4]; os.makedirs(d, exist_ok=True); z = zipfile.ZipFile(p)
        if s['file_in_pack'] not in z.namelist(): raise RuntimeError('member missing ' + s['file_in_pack'])
        z.extract(s['file_in_pack'], d); return os.path.join(d, s['file_in_pack'])
    if p.endswith('.7z'): raise RuntimeError('7z not supported')
    return p


def cut(src, dst, t0, t1, reverse=False):
    af = ['-af', 'areverse'] if reverse else []
    r = sh(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t0:.3f}', '-t', f'{t1 - t0:.3f}', '-i', src] + af + ['-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', dst])
    if r.returncode: raise RuntimeError(r.stderr[-300:])


def measure(wav):
    import numpy as np
    from scipy.io import wavfile
    sr, x = wavfile.read(wav); x = x.astype(np.float32) / 32768.0; m = np.abs(x).max(1) if x.ndim > 1 else np.abs(x); hop = int(.005 * sr); n = len(m) // hop
    env = np.sqrt((m[:n * hop].reshape(n, hop) ** 2).mean(1)) if n else np.zeros(1)
    pk = float(m.max()); return dict(dur=round(len(m) / sr, 3), peak_t=round(float(env.argmax()) * .005 + .0025, 3), peak_db=round(20 * np.log10(max(pk, 1e-6)), 1), clip_pct=round(float((m >= .999).mean()) * 100, 4))


def fetch(out):
    os.makedirs(out, exist_ok=True); cache = os.path.join(out, '_cache'); os.makedirs(cache, exist_ok=True)
    sfx = {s['id']: s for s in json.load(open(os.path.join(DATA, 'licensed_sfx.json')))['sounds']}; srcs = {s['id']: s for s in json.load(open(os.path.join(DATA, 'licensed_sfx.json')))['sources']}
    mus = {t['id']: t for t in json.load(open(os.path.join(DATA, 'licensed_music.json')))['tracks']}
    spec = {}; used = {}; want = sorted({i for L in LAYERS.values() for i, _ in L['ids']})
    for i in want:
        s = sfx.get(i)
        if not s: print('UNKNOWN', i); continue
        try:
            src = source_file(s, cache); dst = os.path.join(out, i + '.wav'); cut(src, dst, s['trim'][0], s['trim'][1], bool(s.get('reverse'))); m = measure(dst)
        except Exception as e: print('FAIL', i, str(e)[:160]); continue
        norm = min(4.0, max(.25, 10 ** ((-3.0 - m['peak_db']) / 20)))                             # bring every layer to ~ -3 dBFS peak before its per-kind gain
        spec[i] = dict(file=dst, gain=round(norm, 3), **m); sr_ = srcs.get(s['source_id'], {})
        used[i] = dict(kind='sfx', id=i, source=s['source'], creator=sr_.get('creator', ''), licence=s['licence'], page=sr_.get('page_url', s.get('listing_page', '')), url=s['url'], attribution=sr_.get('attribution', ''), modified='trimmed' + (', reversed' if s.get('reverse') else ''))
        print('ok', i, m, 'norm', spec[i]['gain'], flush=True)
    for name, M in MUSIC.items():
        t = mus[M['track']]
        try:
            src = download(t['url'], cache); dst = os.path.join(out, name + '.wav'); cut(src, dst, M['seg'][0], M['seg'][1]); m = measure(dst)
        except Exception as e: print('FAIL', name, str(e)[:160]); continue
        spec[name] = dict(file=dst, gain=M['gain'], music=True, fade_in=M['fade_in'], fade_out=M['fade_out'], **m)
        used[name] = dict(kind='music', id=M['track'], source=t['source'], creator=t['artist'], title=t['title'], licence=t['licence'], page=t['page_url'], url=t['url'], attribution=t.get('attribution') or t.get('courtesy_credit', ''), modified=f"segment {M['seg'][0]:.0f}-{M['seg'][1]:.0f} s, faded")
        print('ok', name, m, flush=True)
    json.dump(spec, open(os.path.join(out, 'licensed.json'), 'w'), indent=1); json.dump(used, open(os.path.join(out, 'used.json'), 'w'), indent=1); print('fetched', len(spec))


def layer(events, lic, out):
    ev = json.load(open(events)); spec = json.load(open(lic)); add = []; cnt = {}
    for e in ev:
        L = LAYERS.get(e['kind'])
        if not L: continue
        ids = [(i, g) for i, g in L['ids'] if i in spec]
        if not ids: continue
        n = cnt.get(e['kind'], 0); cnt[e['kind']] = n + 1; i, g = ids[n % len(ids)]; s = spec[i]; p = e.get('params', {}); dur = float(p.get('dur', L.get('dur', .4)))
        t0 = {'peak': e['t'] - s['peak_t'], 'mid': e['t'] + dur / 2 - s['peak_t'], 'end': e['t'] + dur - s['peak_t'], 'start': e['t']}[L['mode']]
        add.append(dict(kind='file', t=round(max(0.0, t0), 3), params=dict(name=i, gain=g)))
    for name, M in MUSIC.items():
        if name in spec: add.append(dict(kind='file', t=M['place'], params=dict(name=name)))
    json.dump(sorted(ev + add, key=lambda e: e['t']), open(out, 'w'), indent=0); print(len(add), 'licensed layers added', {k: v for k, v in cnt.items()})


if __name__ == '__main__':
    if sys.argv[1] == 'fetch': fetch(sys.argv[2])
    elif sys.argv[1] == 'layer': layer(*sys.argv[2:5])
