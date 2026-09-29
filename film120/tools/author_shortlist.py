#!/usr/bin/env python3
"""Author data/shortlist.json (the curated edit: clips, excerpts with spans/labels, cast per sequence) from the verified pool data/shortlist_draft.json.
usage: author_shortlist.py [POOL.json] [OUT.json]
Only clips that survived BOTH the hunter and the adversarial verifier (strictest verdict) are in the pool; every excerpt id used in a cast is validated here."""
import json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'data/shortlist_draft.json'); OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'data/shortlist.json')
pool = json.load(open(POOL)); C = pool['clips']

# excerpt id -> (clip id, in, out, role, label overrides)
X = {
 # ---- early research / early experiments
 'tgan_ucf':   ('tgan_ucf101_label_conditional_2016', 0, .8, 'early research: 64x64 video GAN samples', dict(model='TGAN', year='2016', creator='Saito et al. / Preferred Networks', license='MIT (repo)')),
 'tgan_golf':  ('tgan_golf_2016', 0, .8, 'early research', dict(model='TGAN', year='2016', creator='Saito et al. / Preferred Networks', license='MIT (repo)')),
 'tgan_mnist': ('tgan_moving_mnist_2016', 0, .8, 'early research', dict(model='TGAN', year='2016', creator='Saito et al. / Preferred Networks', license='MIT (repo)')),
 'tats_ucf':   ('tats_ucf101_gif_2022', 0, 6, 'early research 2022', dict(model='TATS', year='2022', creator='Ge et al. / UMD, Meta AI', license='MIT (repo)')),
 'dcgan_anime': ('dcgan_anime128_63k_2021', 0, 8, 'GAN-era animation (image GAN latent walk)', dict(model='DCGAN (ANIME)', year='2021', creator='Zisaac33', license='CC BY-SA 4.0')),
 'deepdream':  ('deepdream_ouroboros_2021', 2, 12, 'pre-diffusion hallucination look (5 fps)', dict(model='DEEPDREAM (2015 METHOD)', year='2021', creator='PantheraLeo1359531', license='CC0')),
 'sd_park_a':  ('sd14_benlisquare_park_2022', .5, 5.5, 'HOOK early: frame-by-frame SD animation, identity drift', dict(model='STABLE DIFFUSION 1.4', year='2022', creator='Benlisquare', license='CC BY-SA 4.0')),
 'sd_park_b':  ('sd14_benlisquare_park_2022', 4.5, 10.0, 'annotation / frame-stack early', dict(model='STABLE DIFFUSION 1.4', year='2022', creator='Benlisquare', license='CC BY-SA 4.0')),
 'sd_flowers': ('sd14_flowers_img2img_animation_2022', 0, 10.0, 'early experiments panel', dict(model='STABLE DIFFUSION 1.4', year='2022', creator='Benlisquare', license='CC BY-SA 4.0')),
 'gen1_eleph': ('runway_gen1_watercolor_elephants_2023', 0, 5.1, 'Runway Gen-1 video-to-video (2023)', dict(model='RUNWAY GEN-1', year='2023', creator='Oronbb', license='CC BY-SA 4.0')),
 'gen2_dog':   ('runway_gen2_dog_podium_2023', 0, 4.0, 'Runway Gen-2 (2023)', dict(model='RUNWAY GEN-2', year='2023', creator='Lwneal', license='CC BY-SA 4.0')),
 'cogv_swans': ('cogvideox_late_afternoon_swans_2024', 0, 6.1, 'open model, 8 fps (2024)', dict(model='COGVIDEOX', year='2024', creator='VulcanSphere', license='CC0')),
 'cogv_paint': ('cogvideox_painting_with_the_breeze_2024', 0, 6.1, 'open model, 8 fps (2024)', dict(model='COGVIDEOX', year='2024', creator='VulcanSphere', license='CC0')),
 't2vz_horse': ('t2vzero_horse_galloping', 0, 2.6, 'matched subject: horse (2023, 3 fps)', dict(model='TEXT2VIDEO-ZERO', year='2023', creator='Khachatryan et al.', license='OpenRAIL-M (repo)')),
 # ---- Rapidata same-prompt benchmark clips (Hugging Face, Apache-2.0 dataset-card licence)
 'rap_veo2_violin': ('rapidata_veo2_violinist_same_prompt', 0, 5.0, 'same prompt as Veo 3.1 clip', dict(model='VEO 2', year='2024', creator='Rapidata dataset', license='Apache-2.0 (dataset)')),
 'rap_veo31_violin': ('rapidata_veo31_violinist_same_prompt', 0, 6.0, 'same prompt as Veo 2 clip', dict(model='VEO 3.1', year='2025', creator='Rapidata dataset', license='Apache-2.0 (dataset)')),
 'rap_wan21': ('rapidata_wan21_wolf_phoenix_crowd_glitch', 0, 5.0, 'open model, crowd-ranked glitch example (same prompt as Runway clip)', dict(model='WAN 2.1', year='2025', creator='Rapidata dataset', license='Apache-2.0 (dataset)')),
 'rap_runway': ('rapidata_runway_alpha_wolf_phoenix_crowd_glitch', 0, 5.3, 'Runway Gen-3 Alpha family, same prompt as Wan clip', dict(model='RUNWAY GEN-3 ALPHA', year='2024', creator='Rapidata dataset', license='Apache-2.0 (dataset)')),
 # ---- Sora (2024 preview demos)
 'sora_mammoth': ('sora_wooly_mammoth', 0, 10.0, 'Sora preview demo', dict(model='SORA', year='2024')),
 'sora_bigsur': ('sora_big_sur_drone', .3, 8.3, 'Sora preview demo: aerial camera move', dict(model='SORA', year='2024')),
 'sora_ships': ('sora_ships_in_coffee', 0, 15.0, 'Sora preview demo: surreal physics', dict(model='SORA', year='2024')),
 'sora_train': ('sora_photoreal_train_glenfinnan', 0, 8.5, 'Sora preview demo', dict(model='SORA', year='2024')),
 'sora_pigeon': ('sora_victoria_pigeon_vertical', 2.0, 23.5, 'Sora preview demo, native vertical', dict(model='SORA', year='2024')),
 'sora_gold':  ('sora_gold_rush_fake_archive', 0, 24.0, 'Sora preview demo: fake archive look', dict(model='SORA', year='2024')),
 # ---- Google Veo
 'veo2_clock': ('veo2_clock_gemini_advanced', 0, 8.0, 'Veo 2 close-up (2024 model)', dict(model='VEO 2', year='2024', creator='FallingGravity', license='CC0')),
 'veo3_lemon': ('veo3_visual_kei_lemonade_gemini', 0, 8.0, 'Veo 3 (native audio) - Veo watermark stays visible', dict(model='VEO 3', year='2025', creator='VulcanSphere', license='CC0')),
 'veo31_lemon': ('veo31_visual_kei_lemonade_flow', 0, 8.0, 'Veo 3.1 Fast in Flow - Veo watermark stays visible', dict(model='VEO 3.1', year='2025', creator='VulcanSphere', license='CC0')),
 # ---- other developers / open models
 'hailuo_nuns': ('hailuo_i2v_japanese_nuns_1902', 0, 5.6, 'image-to-video from a historic still', dict(model='HAILUO AI', year='2025', creator='Nesnad', license='PD (Commons: AI output)')),
 'ltx_cyber':  ('ltxv2b_cybertruck_from_photos', 0, 5.0, 'image-to-video from two photos (references)', dict(model='LTX-VIDEO 2B', year='2025', creator='Premeditated · photos OWS Photography', license='CC BY 4.0')),
 'kand5':      ('kandinsky5_sft_10s_example3', 0, 7.0, 'open model 2025', dict(model='KANDINSKY 5.0', year='2025', creator='Kandinsky Lab', license='MIT (repo)')),
 'lance':      ('lance_t2v_demo_01', 0, 9.9, 'recent open model (2026 repo demo)', dict(model='LANCE', year='2026', creator='ByteDance', license='Apache-2.0 (repo)')),
 'ovi':        ('ovi_two_women_audio_video', 0, 5.1, 'joint audio-video open model', dict(model='OVI', year='2025', creator='Character.AI / Yale', license='Apache-2.0 (repo)')),
}
# manual overlay overrides = watermarks/logos that MUST stay visible (normalised x,y,w,h); the profile heuristic is not authoritative
OVERLAYS = {
 'veo3_visual_kei_lemonade_gemini': [dict(x=.935, y=.92, w=.055, h=.05, note='burned-in white "Veo" mark, bottom-right (verifier)')],
 'veo31_visual_kei_lemonade_flow': [dict(x=.945, y=.94, w=.055, h=.045, note='burned-in white "Veo" mark, bottom-right (verifier)')],
}

CAST = {
 'seq01': dict(early='sd_park_a', recent='sora_pigeon'),
 'seq02': dict(panels=['tgan_ucf', 'dcgan_anime', 'deepdream', 'sd_flowers', 'gen1_eleph']),
 'seq03': dict(targets=[dict(ex='sd_park_b', u0=.5, zoom=2.4, tag='FRAME-BY-FRAME', note='One image per frame, per the source page.'), dict(ex='cogv_swans', u0=.3, zoom=2.2, tag='8 FPS', note='Low frame rate, stated on the source page.'),
                        dict(ex='deepdream', u0=1.5, zoom=2.2, tag='5 FPS', note='Measured frame rate of the file.')]),
 'seq05': dict(milestones=[dict(year='2022', model='MAKE-A-VIDEO', dev='META', date='SEP 29, 2022', ex='sd_flowers', note='Research paper: text to video; demo planned.', clip_note="ERA CLIP · NOT META'S"),
                           dict(year='2023', model='GEN-2', dev='RUNWAY', date='MAR 20, 2023', ex='gen2_dog', note='Text and image modes announced; public in June.'),
                           dict(year='2023', model='STABLE VIDEO DIFFUSION', dev='STABILITY AI', date='NOV 21, 2023', ex=None, note='Research-use image-to-video: 14 or 25 frames.'),
                           dict(year='2024', model='SORA', dev='OPENAI', date='FEB 15, 2024', ex='sora_mammoth', note='Research preview: up to a minute of video.')]),
 'seq04': dict(early='sd_park_b', modern='sora_mammoth', u_early=.4, u_modern=2.0),
 'seq06': dict(entries=[dict(ex=None, model='JUNE 2024', dev='KLING · LUMA · RUNWAY', year='2024', date='JUN 6-17, 2024', note='Three reveals, June 6 to 17.', hold=9.0, tr='slat', fact_cue='s6.facts',
                             facts=['KLING · SIGN-UPS OPEN · JUN 6, 2024', 'LUMA DREAM MACHINE · PUBLIC · JUN 12, 2024', 'RUNWAY GEN-3 ALPHA · ANNOUNCED · JUN 17, 2024']),
                        dict(ex='sora_bigsur', model='SORA TURBO', dev='OPENAI', year='2024', date='DEC 9, 2024', note='Public product: 1080p, 20-second clips.', clip_note='CLIP SHOWN: FEB 2024 PREVIEW DEMO', hold=2.2, tr='letters'),
                        dict(ex='veo2_clock', model='VEO 2', dev='GOOGLE', year='2024', date='DEC 16, 2024', note='Announced a week after Sora went public.', hold=1.8, tr='iris')]),
 'seq07': dict(pairs=[dict(a='rap_veo2_violin', b='rap_veo31_violin', subject='STREET VIOLINIST', ya='2024', yb='2025', ma='VEO 2', mb='VEO 3.1', same_prompt=True),
                        dict(a='sd_park_b', b='veo31_lemon', subject='PEOPLE', ya='2022', yb='2025', ma='STABLE DIFFUSION 1.4', mb='VEO 3.1', same_prompt=False)]),
 'seq08': dict(items=[dict(type='keyframes', ex='ltx_cyber', title='FIRST + LAST FRAME', product='RUNWAY GEN-3 ALPHA TURBO', date='OCT 8, 2024', note='A start image and an end image; the model fills the shot between.', src='RUNWAY CHANGELOG · OCT 8, 2024'),
                      dict(type='camera', ex='sora_bigsur', path='orbit', title='CAMERA CONTROL', product='MINIMAX DIRECTOR MODELS', date='FEB 11, 2025', note='A model with enhanced camera control.', src='MINIMAX RELEASE NOTES'),
                      dict(type='refs', ex='veo31_lemon', refs=['ltx_cyber', 'hailuo_nuns'], title='REFERENCE IMAGES', product='RUNWAY GEN-4 REFERENCES', date='APR 30, 2025', note='Reference stills keep a character or place consistent.', src='RUNWAY CHANGELOG')]),
 'seq09': dict(cols=[dict(name='RUNWAY', sub='GEN-4.5'), dict(name='GOOGLE', sub='VEO / OMNI'), dict(name='KLING', sub='3.0'), dict(name='SEEDANCE', sub='2.5')],
               rows=[dict(name='EDIT REAL FOOTAGE', cells=[dict(has=True, since='2023', src='Runway Gen-1 research page, 2023-02-06'), dict(has=True, since='2024', src='Google DeepMind Veo page, 2024-05-14 (masked editing, private preview)'), dict(has=True, since='2025', src='Kling 2.0 Multi-Elements Editor, 2025-04-15'), dict(has=True, since='2026', src='Seed blog, Seedance 2.0, 2026-02-12')]),
                     dict(name='FIRST / LAST FRAME', cells=[dict(has=True, since='2024', src='Runway Gen-3 Alpha Turbo Keyframes, 2024-10-08'), dict(has=True, since='2025', src='Google developers blog, Veo 3.1, 2025-10-15'), dict(has=True, since='2024', src='Kuaishou press release (WAIC), July 2024'), None]),
                     dict(name='CAMERA CONTROL', cells=[dict(has=True, since='2023', src='Runway Gen-2 Director Mode, 2023-09-13'), dict(has=True, since='2025', src='Google Flow camera controls, 2025-05-20'), dict(has=True, since='2024', src='Kling 1.5 camera movements, 2024-11'), dict(has=True, since='2026', src='Seed blog, Seedance 2.0 reference camera movement, 2026-02-12')]),
                     dict(name='REFERENCE IMAGES', cells=[dict(has=True, since='2025', src='Runway Gen-4, 2025-03-31'), dict(has=True, since='2025', src='Google Flow ingredients, 2025-05-20'), dict(has=True, since='2025', src='Kling 1.6 Elements, 2025-01-23'), dict(has=True, since='2026', src='Seed blog, Seedance 2.0, 2026-02-12')]),
                     dict(name='NATIVE AUDIO', cells=[dict(has=True, since='2025', src='Runway Gen-4.5, 2025-12-11'), dict(has=True, since='2025', src='Google Veo 3, 2025-05-20'), dict(has=True, since='2025', src='Kling VIDEO 2.6, 2025-12-03'), dict(has=True, since='2025', src='Seed blog, Seedance 1.5 pro, 2025-12-16')])]),
 'seq10': dict(tiles=['tgan_mnist', 'tats_ucf', 'gen1_eleph', 'cogv_swans', 't2vz_horse', 'veo2_clock', 'sora_ships', 'hailuo_nuns', 'veo3_lemon', 'ltx_cyber', 'kand5', 'lance'], hero_tile=6),
 'seq11': dict(heroes=[dict(ex='sora_ships', dur=3.5, continue_seq10=True),
                       dict(ex='sora_bigsur', dur=3.4, note='SORA: APP CLOSED APR 26, 2026 · API SHUT DOWN SEP 24, 2026', note_src='OpenAI'),
                       dict(ex='veo31_lemon', dur=3.8, note='PER KLING: FINGERS CAN WARP, TEXT CAN DISTORT.', note_src='kling.ai/blog · limitations of current AI video generation'),
                       dict(ex='lance', dur=3.4)]),
 'seq12': dict(panels=['sd_park_b', 'tgan_golf', 'deepdream', 'gen2_dog', 'sora_mammoth', 'sora_ships', 'veo2_clock', 'veo3_lemon', 'hailuo_nuns', 'lance'],
               swaps=['sora_bigsur', 'sora_gold', 'rap_runway', 'veo31_lemon', 'ovi', 'cogv_paint', 'rap_wan21', 'sora_train']),
 'seq13': dict(early='sd_park_a', recent='sora_pigeon', peak_lines=[['ONE FRAME.', 'white'], ['A WORLD.', 'volt']]),
 'seq14': dict(shot='sora_bigsur', lines=[['FROM MELTING PIXELS', 'white'], ['TO MOVING WORLDS.', 'volt']], credit=['VOICE ELEVENLABS V4 · SCORE + SFX ORIGINAL AND LICENSED · FULL CREDITS IN SOURCE LIST', 'MUSIC BED "DRONE IN D" KEVIN MACLEOD (INCOMPETECH.COM) CC BY 4.0']),
}


def main():
    clips, ex, problems = {}, {}, []
    for eid, (cid, a, b, role, lab) in X.items():
        if cid not in C: problems.append(f'{eid}: clip {cid} not in the verified pool'); continue
        c = dict(C[cid]); m = c['listed_media']; probe = pool['excerpts'].get('probe_' + cid, {}).get('label', {})
        clips[cid] = c; label = dict(probe); label.update(lab); ex[eid] = dict(clip=cid, **{'in': a, 'out': b}, label=label, role=role)
    for cid, ov in OVERLAYS.items():
        if cid in clips: clips[cid]['overlays_override'] = ov
    seen = set()
    def walk(o):
        if isinstance(o, dict): [walk(v) for v in o.values()]
        elif isinstance(o, list): [walk(v) for v in o]
        elif isinstance(o, str) and o in ex: seen.add(o)
    for k, v in CAST.items():
        walk(v)
    def check(o, path):
        if isinstance(o, dict):
            for k, v in o.items(): check(v, path + [k])
        elif isinstance(o, list):
            for v in o: check(v, path)
        elif isinstance(o, str) and path and path[-1] in ('ex', 'early', 'recent', 'modern', 'shot', 'panels', 'tiles', 'swaps', 'ex2') and o not in ex: problems.append(f'{"/".join(path)}: unknown excerpt {o}')
    check(CAST, [])
    fam = {c.get('family') for c in clips.values()}; pages = {c['page'] for c in clips.values()}
    out = dict(clips=clips, excerpts=ex, cast=CAST, cues={})
    json.dump(out, open(OUT, 'w'), indent=1)
    print(f'{len(ex)} excerpts, {len(clips)} clips, {len(pages)} distinct pages, {len(fam)} families; used in casts: {len(seen)} excerpts')
    for p in problems: print('PROBLEM', p)
    sys.exit(1 if problems else 0)


if __name__ == '__main__': main()
