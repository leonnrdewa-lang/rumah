# QA report and honest limits

Final file: `from_melting_pixels_to_moving_worlds_v2_final.mp4` (Higgsfield media id `1f154b10-99ed-46f8-af23-d9c99ab99af4`,
https://d2ol7oe51mr4n9.cloudfront.net/user_2vqT0Ah9P4GmOaY4MT4rr1viFY5/1f154b10-99ed-46f8-af23-d9c99ab99af4.mp4 - open it from the Higgsfield media library).
Built from commit `1dbc60c` of this branch by `tools/sandbox_run.sh all`; the machine-readable report is `qa_report.json` (uploaded next to the video, media id `f7d09a8c-09f9-434c-afc3-57a105028455`).

## Numeric QA (tools/qa_video.py) - VERDICT PASS

| Check | Result |
|---|---|
| Geometry / rate | 1080x1920, 30 fps, yuv420p, BT.709 |
| Length | exactly 3600 frames; video 120.000 s, audio 120.000 s, container 120.000 s |
| Black / near-black frames | none (dips go through dark grey) |
| Loudness | -14.0 LUFS integrated, true peak -1.9 dBTP, sample peak -1.93 dBFS, no clipping |
| Loudness range | 1.8 LU (narration-led mix; the music arc is subtle by design) |
| Silences below -60 dB | none (the freeze beat at 3.2-3.8 s is a ~10 dB drop, not digital silence) |
| Replay seam | last vs first frame mean difference 1.5 (the film loops without a jump) |
| Chapter timing | narration-anchored cues (`data/cue_spec.json`); hook 0-8, early experiments 8-25, first leap 25-43, race 43-63, control 63-83, best examples 83-104, payoff 104-115, final line 115-120 |

Also run: fact-check by four independent hostile checkers (narration, plates, feature matrix, footage labels) against the research pool and primary sources; every actionable finding was fixed (see `git log`): L02 reworded, Sora/Make-A-Video/Kling plates corrected, capability matrix re-based on R5 dates with the legend "EARLIEST YEAR VERIFIED", clips with third-party-reupload or licensor-mismatch provenance removed, PD wording made "PD-algorithm (Commons)".

## What I could not do (be aware before publishing)

* **Nobody has watched the film end to end and nobody has listened to it.** I checked ~20 frames through low-resolution contact sheets (hook, panels, corridor, gallery, split screens, diagrams, matrix, contact sheet, hero shots, callback, end card) and all numeric measurements above, but not motion quality, text legibility at full size, mix taste, or how the sound-design layers sit. The 60 licensed sounds and two music beds were chosen by metadata and measurements only. Please do one full-screen viewing and listening pass.
* **Footage content was not reviewed by a person.** Source frames were checked with automatic captions and a few thumbnails. The deepdream excerpt now starts at 4 s (the uploader's base image is unidentified for its first seconds); the Rapidata, Hailuo and TATS clips need a human look for people/logos/ground-truth panels.
* **Rights.** "PD-algorithm" and CC0 tags on AI outputs are community/uploader assertions, not developer licences; the Rapidata dataset chain and the MIT-repo demo media are argued from licence text, not explicit media grants. `CREDITS.md` lists these and the CC BY-SA share-alike position (needs a legal decision for the whole film). No footage exists for the newest systems (Sora 2, Veo 3.1 flagship, Kling 3.0, Seedance 2.x, Gemini Omni) - they are shown only as dated developer facts.
* The second-opinion pass of the fact-check (a second checker re-judging each flagged claim) was stopped after the first pass to save time; I applied only findings that were clear from the primary quotes.
* Commons and Hugging Face source pages could not be re-opened from the checking environment; those verdicts rest on the earlier verification records (`data/verified/`).
* Higgsfield's own scene-analysis job for the draft stayed queued for over 40 minutes and was not used.
