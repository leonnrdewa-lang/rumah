#!/usr/bin/env python3
"""Download the shortlisted Commons clips, record license data, probe them, detect cuts.
Usage: fetch_footage.py <out_dir>   (needs internet; run inside the render sandbox)"""
import json, os, re, subprocess, sys, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else 'footage'
API = 'https://commons.wikimedia.org/w/api.php'
UA = {'User-Agent': 'ai-video-history-editor/1.0 (research; contact leonrdewa@gmail.com)'}
MAX_ORIG = 40 * 1024 * 1024
strip = lambda s: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()

def api(**p):
    p['format'] = 'json'
    req = urllib.request.Request(API + '?' + urllib.parse.urlencode(p), headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=40))

def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1000: return
    subprocess.run(['curl', '-sS', '-L', '-m', '300', '-A', UA['User-Agent'], '-o', path, url], check=True)

def probe(path):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,avg_frame_rate,nb_frames:format=duration', '-of', 'json', path], capture_output=True, text=True).stdout)
    s = j['streams'][0]; n, d = (s['avg_frame_rate'].split('/') + ['1'])[:2]
    return dict(width=s['width'], height=s['height'], fps=round(float(n) / float(d), 3) if float(d) else 0, duration=round(float(j['format']['duration']), 3))

def cuts(path, thr=0.30):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-vf', f"select='gt(scene,{thr})',showinfo", '-an', '-f', 'null', '-'], capture_output=True, text=True).stderr
    return [round(float(m), 3) for m in re.findall(r'pts_time:([0-9.]+)', r)]

def main():
    os.makedirs(OUT, exist_ok=True)
    src = json.load(open(os.path.join(HERE, 'footage_sources.json')))['clips']
    manifest = {}
    for c in src:
        title = 'File:' + c['file']
        d = api(action='query', titles=title, prop='imageinfo', iiprop='url|size|extmetadata|derivatives', iiextmetadatafilter='LicenseShortName|LicenseUrl|Artist|Credit|DateTimeOriginal|ImageDescription|Categories')
        page = list(d['query']['pages'].values())[0]; ii = page['imageinfo'][0]; em = ii.get('extmetadata', {})
        g = lambda k: strip(em.get(k, {}).get('value', ''))
        url, kind = ii['url'], 'original'
        if ii['size'] > MAX_ORIG:
            ders = [x for x in ii.get('derivatives', []) if x.get('type', '').startswith('video/webm') and x.get('height', 9999) <= 720]
            if ders: best = max(ders, key=lambda x: x['height']); url, kind = best['src'], f"transcode {best['width']}x{best['height']}"
        path = os.path.join(OUT, c['id'] + '.webm'); download(url, path)
        m = dict(c); m.update(dict(
            file_page='https://commons.wikimedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_')), download_url=url, download_kind=kind,
            original_size_bytes=ii['size'], license=g('LicenseShortName'), license_url=g('LicenseUrl'), author=g('Artist')[:160], credit=g('Credit')[:160],
            date=g('DateTimeOriginal')[:40], description=g('ImageDescription')[:240], local=path))
        m.update(probe(path)); m['cuts'] = cuts(path)
        manifest[c['id']] = m
        print(f"{c['id']:16s} {m['width']}x{m['height']} {m['fps']}fps {m['duration']}s cuts={len(m['cuts'])} lic={m['license']!r} ({kind})", flush=True)
    json.dump(manifest, open(os.path.join(OUT, 'footage_manifest.json'), 'w'), indent=1)

if __name__ == '__main__': main()
