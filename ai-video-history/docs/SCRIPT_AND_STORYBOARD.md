# Script and second-by-second storyboard

Format 1080 × 1920 (9:16), 30 fps, ≈ 72.2 s. Safe zones: nothing that matters above y = 210 or below y = 1500 (Reels/TikTok chrome); subtitles sit at y ≈ 1290.
Design system: **amber = the early era**, **cyan = today** (chips, key words in the subtitles, rules, year numerals), paper-white type, Montserrat 800/900 for headlines, Space Mono for
data chips, Inter for the prompt field. Early footage is shown small, framed, with scan-lines, timecode and a motion-tracking reticle (it follows where consecutive frames change most);
modern footage is full-bleed with a slow push-in and a cleaner grade. The window growing into a full frame is the visual argument.

## Narration (11 takes, ≈ 60 s of speech)

1. A few years ago, AI video could barely keep a face together.
2. Hands melted. Backgrounds drifted. And every clip was over in seconds.
3. In 2022, research labs showed that plain text could become moving pictures.
4. By 2023, anyone could try it. The clips were short, and shaky.
5. Then came Sora, promising a full minute of coherent video.
6. By 2025, models could add sound. Dialogue, footsteps, the hum of a room.
7. What changed? Models learned from far more video, and started modelling time itself. Light, weight, momentum, even the way a camera moves.
8. Today, a shot can keep its light, its lens, and its characters from one moment to the next.
9. Documentary. Animation. Period drama. Science fiction.
10. The first clips were curiosities. Today's can make you look twice.
11. For a century, a film began with a camera. Now, it can begin with a sentence.

Only one model is named in the voice-over (Sora). All other names appear on screen, tied to a verified date (see SOURCES.md).

## Storyboard

Times are from the processed narration (`assets/vo.json`), so picture, captions and sound share one clock (`src/storyboard.py`).

| Time (s) | Scene | Picture | Sound |
|---|---|---|---|
| 0.00 – 1.85 | **Hook, before** | Runway Gen-2 (2023) example in a small window on black, REC dot, timecode, motion reticle. "AI VIDEO / USED TO LOOK / LIKE THIS." builds line by line (last line amber). Grain, low-contrast early grade. | Unsettling drone (a beating minor second), soft tick, a riser from 0.9 s |
| 1.85 | **Impact cut** | White flash (5 frames), chromatic split, camera shake; smash cut to Veo 3 (May 2025) full-bleed 4K, slow push-in. "NOW LOOK / AT IT." slams from 155 % to 100 % with blur (cyan on the second line). | Sub boom + noise burst + long reverb tail |
| 3.55 – 8.03 | **Early faces** | Iris wipe into a framed monitor: Stable Diffusion frame-by-frame animation (Oct 2022) → a Dec 2022 painterly talking head → Dec 2023 android head. Cuts on *barely* (6.10) and *face* (6.88). Amber year "2022", tracked reticle. | Drone + high cluster; subtitles begin at 3.82 |
| 8.03 – 12.82 | **Early montage** | Glitch cut in. VideoPoet cat (2.2 s, 8 fps), Runway Gen-1 watercolour, VideoPoet dog. Cuts on *Hands* / *Backgrounds* / *And every clip*. A running "CLIP 00:0x" counter; on *seconds* (11.93) a red END OF CLIP chip and a CRT power-off collapse. | Glitch blips on each cut, tape-stop on *seconds* |
| 12.82 – 37.74 | **Timeline** | Whip-pan into the era timeline (2022 – 2026 tick bar on top, framed example clip, big year numeral, model lines). Nodes arrive slightly ahead of the words: 2022 (12.82) Make-A-Video/Imagen Video; 2023 (19.83) Runway Gen-2/Stable Video Diffusion; 2024 (25.95) Sora — the Tokyo clip's runtime clock jumps to the end on *minute* (28.57); 2025 (30.60) Veo 3 with a live waveform from the clip's own audio at *sound* (33.67), Sora 2 noted. Slat and iris masks between eras. Each example clip carries its own provenance chip. | Chime per node (rising pitch), whooshes, the arpeggio starts bit-crushed and slowly resolves |
| 37.74 – 48.71 | **What changed** | Zoom-through into a 3-D "time volume": 8 → 15 frames of one clip stacked as slabs, camera orbiting. "FRAME BY FRAME" (red strike-through) becomes "ACROSS TIME" on *modelling time itself* (41.2). Tracked labels LIGHT (44.4) WEIGHT (44.9) MOMENTUM (45.8) CAMERA (47.4) hang off the moving volume. | Pad opens, riser into the next scene, tick per keyword, shutter on *camera* |
| 48.71 – 55.81 | **Now** | Iris reveal, full-bleed shots with push, drift and slight roll: Veo 3.1 (light, 48.7), Veo 3 (lens, 51.7), Seedance 2.0 (characters, 52.9). Big kinetic word on each cue. | Kick and bass enter; whoosh per cut |
| 55.81 – 59.10 | **Styles** | Four hard cuts on the four words: documentary (Sora mammoths), animation (Veo 3), period drama (Sora gold rush), sci-fi (Hailuo). | A hit per cut |
| 59.10 – 63.96 | **Then vs now** | Slat wipe to a split screen: 2022 face (top) vs 2025 face (bottom). On *Today's* (61.3) the bottom window expands to full-bleed; on *look twice* (62.7) two punch-in double-takes. | Whoosh, two shutter clicks |
| 63.96 – 72.24 | **Finale** | Dip to black. A film strip accelerates upward, frames evolving from soft/amber (2022) to crisp (today), locks on *camera* (66.6). Then a prompt field types "a film begins with a sentence." (67.5 – 69.7); on the render (69.99) a 2.39:1 frame opens above it with a flash. Hold, then hard cut to black at 72.24. | Drums stop, sparse pad; a D-major swell and impact on the render; sub drop into black |

Subtitles: phrase-level chunks (≤ 4 words, no orphans), the active word highlighted (amber before 2024, cyan after). The same cues are exported as `assets/subtitles.srt`.
