#!/usr/bin/env python3
"""Local test harness: synthetic stand-ins (same ids/size/fps/duration) so layout/typography can be checked without the real Commons files."""
import json, os, subprocess, sys
out = sys.argv[1]; FF = os.environ.get('FFMPEG', 'ffmpeg'); os.makedirs(out, exist_ok=True)
src = json.load(open(os.path.join(os.path.dirname(__file__), 'footage_sources.json')))['clips']
dims = dict(e_sd_park=(1024, 1024, 30, 10), e_2022_a=(512, 512, 24, 12), e_2022_b=(812, 1280, 25, 18), e_gen1=(896, 512, 25, 5.1), e_gen2_dog=(896, 512, 24, 4), e_vp_cat=(512, 896, 8, 2.2), e_vp_dog=(512, 896, 8, 2.2),
            e_head=(832, 640, 24, 4), m_sora_tokyo=(1920, 1080, 30, 60), m_sora_pup=(1920, 1080, 30, 10), m_sora_gold=(1280, 720, 30, 25), m_sora_mammoth=(1920, 1080, 30, 10), m_sora_ant=(1280, 720, 30, 9.6),
            m_gen3=(1280, 768, 24, 10.5), m_hailuo=(1280, 720, 25, 5.6), n_veo3_owl=(1920, 1080, 24, 22.7), n_veo3_b=(1920, 1080, 60, 30), n_veo3_cafe=(1280, 720, 24, 8), n_veo31=(1920, 1088, 24, 8), n_sora2=(1920, 1080, 24, 30), n_seedance=(1280, 720, 30, 15))
man = {}
for i, c in enumerate(src):
    w, h, fps, dur = dims[c['id']]; p = os.path.join(out, c['id'] + '.mp4')
    if not os.path.exists(p):
        subprocess.run([FF, '-y', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc2=s={w}x{h}:r={fps},hue=h={i * 17}', '-f', 'lavfi', '-i', 'sine=f=220:r=44100', '-t', str(min(dur, 12)), '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', p], check=True)
    m = dict(c); m.update(dict(width=w, height=h, fps=fps, duration=dur, cuts=[], local=p, license='mock')); man[c['id']] = m
json.dump(man, open(os.path.join(out, 'footage_manifest.json'), 'w'), indent=1)
