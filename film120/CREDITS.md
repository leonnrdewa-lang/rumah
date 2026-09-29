# Credits and rights notes

**Film:** FROM MELTING PIXELS TO MOVING WORLDS - 120.000 s, 9:16, 1080x1920, 30 fps. Production date 2026-09-29.

| Layer | Source | Where the full list is |
|---|---|---|
| Narration | ElevenLabs Eleven v4 text-to-speech (through Higgsfield), preset voice "Arthur"; original 230-word script | `data/script.json`, `data/vo/` |
| Footage | 32 excerpts from 31 distinct source pages, 19 model families / projects (2016 GAN experiments to Sora, Veo 3.1, Kandinsky 5, Lance, Ovi) | `FOOTAGE_SOURCES.md`, `footage_sources.csv` |
| Music | original procedural score + two low-level licensed beds | `AUDIO_CREDITS.md` |
| Sound design | original procedural SFX + 60 licensed recordings (CC0, Mixkit free licence, CC BY 4.0) | `AUDIO_CREDITS.md` |
| Facts | 6 research files, 319 distinct source pages, every claim with a verbatim quote | `data/research/`, `docs/RESEARCH_SOURCES.md` |
| Motion design, edit, code | this repository | `engine/`, `seq/`, `tools/` |

Every clip carries its own on-screen source label (model, year, creator, licence). Watermarks and credits that exist inside a source are preserved: the source is shown letterboxed rather than cropped when a mark would be cut.

## Footage licences used (excerpts)

PD - Wikimedia Commons "PD-algorithm" AI output: 8 clips (Sora demos re-uploaded to Commons, Hailuo, one Stable Diffusion animation) - CC0: 6 - MIT (repo assets): 5 - Apache-2.0: 6 (Rapidata Hugging Face dataset x4, Lance, Ovi) - CC BY-SA 4.0: 4 - CC BY 4.0: 1 - CreativeML OpenRAIL-M: 1.

## Residual rights risks (stated, not hidden)

* **"Public domain" AI output is a community assertion.** The Commons PD-algorithm / CC0 tags on Sora, Hailuo, Veo and Stable Diffusion clips are uploader or community statements, not licences from the developer. Some jurisdictions (UK, Hong Kong and others) protect computer-generated works, and OpenAI/Google/Runway terms differ. Each clip's `license_basis` and conditions are in `data/verified/H*.json`; the strictest verdict of independent verifiers decided inclusion ("clear with conditions").
* **Rapidata clips** (Veo 2, Veo 3.1, Wan 2.1, Runway Gen-3 Alpha comparisons) are covered by the dataset card's Apache-2.0 statement plus the upstream terms quoted in the verification record; the chain needs written confirmation from the dataset owner before any commercial use.
* **CC BY-SA 4.0 clips** (Benlisquare, Oronbb, Lwneal, Zisaac33) require attribution (on screen and in the source list) and share-alike for adaptations; a distribution of the film should offer those parts under CC BY-SA 4.0.
* **MIT repo assets** (TGAN, TATS, Kandinsky 5): the MIT grant covers "software and associated documentation"; the GIF/MP4 demos are documentation assets, not an explicit media grant. Copyright notices are kept in the source list.
* **Audio:** every licensed sound is layered under (never in place of) an original one; nothing licensed was listened to before mixing - selection was by metadata and measurements. Mixkit files are downloaded at build time and are not redistributed here. CC0 tags on OpenGameArt / archive.org / Commons are uploader assertions.
* **Newest systems** (Sora 2, Veo 3.1 flagship output, Kling 3.0, Seedance 2.x, Gemini Omni, ...) have no reusable footage licence; they appear only as dated developer facts on data cards, never with stand-in footage. Sora itself was shut down (app 2026-04-26, API 2026-09-24) - the film says so.
* Upscaled or low-resolution sources are shown at their native pixels (see the `Native` column) and are never described as native 1080p.
