# QA report (final render)

Measured on the delivered file with `src/qa_video.py` and ffmpeg's `ebur128` / `astats`.

| Check | Result |
|---|---|
| Container / codecs | MP4, H.264 High (yuv420p, BT.709 tagged) 14.1 Mb/s avg, AAC-LC 320 kb/s, 48 kHz stereo, `faststart` |
| Geometry / rate / length | 1080 × 1920, 30 fps constant, 72.233 s (2167 frames), audio 72.234 s, no A/V drift |
| Blank / frozen stretches | none flagged (per-second brightness, contrast and frame-difference sampled at 10 fps; the deliberately dark prompt beat at 68–69 s still carries a moving blurred background) |
| Loudness | −14.0 LUFS integrated, LRA 1.8 LU, true peak −1.2 dBTP, no clipped samples |
| Intelligibility | narration sits ≈ 9.4 dB above the score and ≈ 12.7 dB above effects on average while it speaks (score ducked ≈ 14 dB under speech) |
| Captions | 49 cues, ≤ 4 words (≤ 5 when short), word-level highlight; timings from ASR alignment snapped to the measured pauses; text is the script, not the ASR spelling |
| Safe zones | type inside x 64–1016; subtitles at y ≈ 1290; chips ≥ y 226; nothing meaningful below y 1500 |
| Layout / typography / transitions | inspected frame by frame on synthetic stand-in footage (same ids, sizes, frame rates) at every scene and transition; `render.py --smoke` renders 150+ frames around all boundaries without error |
| Footage framing | **not inspected by eye** (see README §3); the full render was described by Higgsfield's scene analyser, notes below if available |

Known limitations
* The narration voice is Seed Audio 1.0 (see README §1); a few words carry the slightly flat delivery of a general TTS. Re-cut with ElevenLabs or a human read for a premium finish.
* Word timings are ASR-derived (±≈ 60 ms); the captions are conservative (chunk starts 40 ms early, held 350 ms).
* The score is procedural; it was checked by level and spectrum, not by a musician's ear.
