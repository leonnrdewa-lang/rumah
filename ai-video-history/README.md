# "AI video used to look like this" — a 72-second vertical documentary reel

A finished 9:16 reel (1080 × 1920, 30 fps, H.264 + AAC stereo, ≈ 72 s) on the evolution of AI video generation, from the flickering 2022 experiments to today's
cinematic shots, plus every script, asset list and build script needed to re-edit it.

**Final video:** see *Delivery* below (the file is hosted in the Higgsfield media library because the build sandbox cannot push binaries back to this repository).

```
ai-video-history/
  README.md                       this file
  docs/SOURCES.md                 source-and-licence list with URLs, and the fact-check log for every date on screen
  docs/SCRIPT_AND_STORYBOARD.md   voice-over script and second-by-second storyboard
  assets/vo.json                  processed narration: per-take duration and word timings (drives captions, cuts, ducking)
  assets/subtitles.srt            the burnt-in subtitles as a sidecar file (49 cues, timed to the narration)
  src/                            the whole pipeline (Python + ffmpeg), see "Rebuild"
```

## What is in the video
| Requirement | How it was met |
|---|---|
| Hook: awkward early clip → smash cut to a stunning recent one, with the two-line on-screen hook | 0–1.85 s: Runway Gen-2 (2023) example, "AI VIDEO USED TO LOOK LIKE THIS." Impact cut at 1.85 s (flash, chromatic split, shake) to a Veo 3 4K shot, "NOW LOOK AT IT." |
| Early era, limitations visible | Real 2022–23 clips (Stable Diffusion frame-by-frame animation, Oct 2022; Dec 2022 talking head; Runway Gen-1/Gen-2; Google VideoPoet at 8 fps) in small framed monitors with scan-lines, a motion-tracking reticle and a "clip length" clock that ends in a CRT power-off |
| Breakthrough period, clean animated timeline with verified names and dates | 2022 Make-A-Video / Imagen Video → 2023 Runway Gen-2 / Stable Video Diffusion → Feb 2024 Sora (runtime clock jumps to the end of the 60 s clip) → May 2025 Veo 3 (live waveform from the clip's own audio) + Sep 2025 Sora 2. Every date checked against a primary source (docs/SOURCES.md) |
| Explains what changed in plain language | A 3-D "time volume": stacked frames become one block on *"modelling time itself"*; labels LIGHT / WEIGHT / MOMENTUM / CAMERA are tracked to the moving 3-D camera |
| Current capabilities, different styles | Full-bleed Veo 3.1, Veo 3, Seedance 2.0 shots, then documentary / animation / period drama / sci-fi on the four words |
| Escalating comparison, thought-provoking close, cut to black | Split-screen 2022 vs 2025 face, double-take on *"look twice"*, an accelerating film strip that evolves from soft/amber to crisp, then a prompt field typing "a film begins with a sentence." and a 2.39:1 frame rendering above it; hard cut to black at 72.2 s |
| Editorial techniques | Iris, whip-pan with motion blur, diagonal-slat mask, zoom-through, glitch and flash transitions (each tied to a story beat), speed-ramped clip clock, tracked type, 3-D camera move, film grain, split screen; no template effects |
| Type and safe zones | Montserrat / Space Mono / Inter; nothing important above y = 210 or below y = 1500; subtitles at y ≈ 1290 with the active word highlighted; amber = early era, cyan = today |
| Audio | Original score and sound design (below), narration ducked under, mastered to −14 LUFS integrated, true peak below −1 dBTP, no clipping |

## Read this: where the brief could not be met literally
1. **Narration is not ElevenLabs v4.** This build environment had no ElevenLabs credentials or connector, and Eleven v4 was, in the sources I could reach, announced but not documented as released.
   Rather than mislabel anything, the 11 narration takes were generated with **ByteDance Seed Audio 1.0** through the Higgsfield tool (voice preset "Arthur"). To swap in ElevenLabs:
   `src/tts_elevenlabs.py` regenerates the same 11 takes from your key/voice/model id, and `src/sandbox_run.sh` (stages `vo audio render mux`) re-times captions, cuts, ducking and SFX automatically.
2. **Music and effects are original, synthesised in code (`src/synth_audio.py`), not licensed library tracks.** Nothing to clear, but it is a procedural score, not a composer's; you may prefer to
   replace it (keep `assets/vo.json` timings and re-mix). The score is built as a device: the arpeggio starts bit-crushed and low-rate and resolves to full fidelity as the story reaches today.
3. **I could not watch the real footage myself.** The sandbox that has internet access and ffmpeg cannot send pictures back to me. I verified layout, typography and every effect frame-by-frame on
   synthetic stand-in clips, ran numeric checks on the final file (geometry, duration, brightness/motion per second, loudness, peaks), and had Higgsfield's scene analyser describe slices of the
   render. Treat a quick full watch-through as the one remaining QA step before you post.
4. **No reconstructions were needed.** Every early-era example is a real clip from Wikimedia Commons; nothing was regenerated and passed off as historical footage.
5. **Licences:** five clips are CC BY-SA 4.0 (credit required, ShareAlike may apply to adapted footage); the rest carry Commons' public-domain tag for machine-generated works, which is a US-law
   position and sits beside each model provider's own terms. Details, a caption credit line and how to swap the CC BY-SA clips are in docs/SOURCES.md.
6. **The MP4 is not in this repository**: the sandbox that renders it can upload only to Higgsfield storage, and the local session cannot download from there.

## Delivery
* Final render (1080 × 1920, ≈ 72.2 s): https://d2ol7oe51mr4n9.cloudfront.net/user_2vqT0Ah9P4GmOaY4MT4rr1viFY5/02088fe6-0761-4e73-82cb-9e66ebf81c95.mp4  (Higgsfield media id `02088fe6-0761-4e73-82cb-9e66ebf81c95`, file `ai_video_evolution_reel_1080x1920.mp4`, 130 MB, in the Higgsfield account used for this session; the link is served from your library, not a public page)
* Subtitles: `assets/subtitles.srt` (already burnt into the video; sidecar for platforms that take one)

## Rebuild
Everything runs in one place with internet + ffmpeg + Python (numpy, Pillow, faster-whisper): the Higgsfield sandbox was used.

```
export STAGES="setup vo audio render mux"    # setup: code, fonts, footage (Commons) · vo: tighten takes + word timing · audio: score/SFX/mix · render · mux: loudness master + H.264/AAC
SHA=<commit> WORKERS=5 bash src/sandbox_run.sh          # needs vo_urls.txt ("<n> <url>" per take) beside it
```
Key files: `storyboard.py` (all timing), `scenes.py` (every scene), `render_lib.py` (streaming decoder, transitions, captions), `design.py` (design system), `synth_audio.py`,
`vo_prepare.py` (pause tightening + ASR word alignment), `fetch_footage.py` + `footage_sources.json` (clips and licence data), `qa_video.py`, `make_srt.py`, `make_mock_footage.py` (layout tests without the real clips).
`render.py --smoke` composes frames across every scene boundary to catch errors quickly; `--preview 12.5,40` writes single frames.
