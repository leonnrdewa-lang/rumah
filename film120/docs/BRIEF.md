# BRIEF — "From melting pixels to moving worlds" (120 s vertical film about the evolution of generative AI video)

Read this whole file before doing anything. Today is **2026-09-29**. "Verified through the production date" means the newest models/events up to this date must be checked
against primary sources (anything that only appears in a blog/aggregator is *unverified* and must be marked so).

## The film (what your work feeds)
* Exactly 120.000 s, 1080x1920 (9:16), English narration (ElevenLabs Eleven v4 - verified available: https://elevenlabs.io/docs/changelog, entry "September 28, 2026 - Eleven v4 and Eleven v4 Turbo"), burnt-in subtitles, original + licensed music/SFX, real historical footage, 10-14 bespoke motion-design sequences.
* Story chapters: 0-8 hook (early clip -> smash cut to exceptional recent clip) | 8-25 early experiments (flicker, warped anatomy, changing identities) | 25-43 first major leap (chronological verified milestones, 4-6 excerpts, frame-consistency explainer) | 43-63 race accelerates (6-8 excerpts from many developers) | 63-83 more control (image-to-video, camera control, character references, editing controls, only where verified) | 83-104 what the best examples can do (hero shots, 3-5 s each) | 104-115 payoff | 115-120 final line.
* Visual identity: deep charcoal, warm white, one vivid electric accent (volt #D2FF3C). Every excerpt carries a source label (model, year, creator, licence).
* Nothing may imply the technology is flawless or that curated demos represent every generation. No invented benchmarks or scores.

## Hard rules for footage and facts
1. **Publicly accessible is NOT free to reuse.** A clip qualifies only if there is written evidence of a compatible licence or explicit permission: Creative Commons (CC0, CC BY, CC BY-SA - NOT NC, NOT ND), public-domain tags with a stated basis, permissive open-source licences (Apache-2.0/MIT/BSD/OpenRAIL noted precisely) that clearly cover the *media files themselves*, or an explicit promotional/press permission. For every candidate record the **exact licence text or tag, the URL where you saw it, and a short quote**.
2. Prefer: Wikimedia Commons files (licence tag + uploader + prompt/model in the description), official demo galleries that state reuse terms, permissively-licensed project repositories, Internet Archive items with a CC/PD licence.
3. Never use: social-media rips, YouTube downloads, generic stock as evidence of a model's capabilities, clips of real identifiable people (likeness/right-of-publicity), brand/IP-heavy ads (e.g. Coca-Cola, Star Wars, Disney characters), political/election/propaganda clips, sexual/violent shock content, clips whose only licence is "NC"/"ND"/"all rights reserved".
4. Keep source watermarks and required credits. Record whether a clip has a visible watermark/logo/burnt-in caption and where (corner), because vertical crops must not remove it.
5. Verify the **model name/version and creation date** of every clip from the source page (title, description, category, upload date) AND cross-check the model's release date in a primary source. If the page's claim cannot be corroborated, say so.
6. Dates/claims: primary sources only (developer blog/docs/paper/archived official page). Give the URL and a verbatim quote (<= 25 words). Secondary sources may only be used as leads and must be labelled `secondary`.
7. Do not invent. `null`/"unknown" beats a guess. Report failures honestly.

## Environment facts (learned the hard way)
* Your local Bash has **no general internet** (only npm/pypi registries; every other host returns 403 CONNECT). WebSearch works (US-only, returns summaries+links). WebFetch is blocked for many hosts (Wikipedia, openai.com, ...) - try it, but expect EGRESS_BLOCKED.
* The **Higgsfield sandbox** has open internet and ffmpeg 5.1, python3 (numpy, Pillow, faster-whisper), curl, jq, 8 cores, 7 GB RAM. Use it through the MCP tool `mcp__Higgsfield__sandbox_exec` (load the schema first with ToolSearch `select:mcp__Higgsfield__sandbox_exec`).
  - **Every sandbox_exec call must finish in < 50 s** (the MCP layer kills calls at 60 s even if you pass a larger timeout). For anything longer use `background:true` (or `nohup ... &` inside the command and poll a log file in later calls).
  - Command length limit 16,000 chars. Files persist between calls for a while but the sandbox can be reset at any time: keep anything valuable by printing it and saving it locally with your Write tool. Work in `/home/user/scratch/<yourname>/`.
  - Sites that work from the sandbox: commons.wikimedia.org (API), archive.org, arxiv.org, en.wikipedia.org (API and `index.php?action=raw`), raw.githubusercontent.com, github.com/api.github.com, blog.google, deepmind.google, runwayml.com, stability.ai, ai.meta.com, seed.bytedance.com, elevenlabs.io, web.archive.org. **openai.com returns 403 - use the Wayback Machine with the `id_` flag**, e.g. `https://web.archive.org/web/20240216000000id_/https://openai.com/sora`. pixabay.com/pexels.com return 403.
  - Fetch text pages with curl `-L -A 'Mozilla/5.0'` and strip tags with python (`re.sub(r'<script.*?</script>|<style.*?</style>','',t,flags=re.S)` then `re.sub(r'<[^>]+>',' ',t)`).
  - Commons API pattern (send a real User-Agent): `https://commons.wikimedia.org/w/api.php?action=query&titles=File:NAME&prop=imageinfo&iiprop=url|size|mime|extmetadata|derivatives&iiextmetadatafilter=LicenseShortName|LicenseUrl|Artist|Credit|DateTimeOriginal|ImageDescription|UsageTerms|Attribution&format=json` ; category listing `list=categorymembers&cmtitle=Category:X&cmtype=file|subcat&cmlimit=500`; full-text `list=search&srsearch=...&srnamespace=6`. Original file URL = `imageinfo.url`; files > 40 MB also have `derivatives` (transcoded webm/mp4) - use those.
  - Nothing binary can be moved from the sandbox to your local disk (local cannot reach any Higgsfield host). So **you cannot view video frames**. Reason from metadata: Commons description/prompt text, categories, ffprobe numbers, scene-cut lists, and (where available) Higgsfield's video analysis (`video_analysis_create` on a `media_import_url` of the clip; takes 25+ min). Never claim you "saw" a clip unless a tool actually described it.
* Only **two subagents run at once** on this machine, so be efficient: do the whole job you were given, write results to disk, return a compact summary.
* Local files: repository root is `/home/user/rumah`; this project lives in `/home/user/rumah/film120/` (`data/`, `docs/`, `tools/`, `engine/`, `seq/`). Do NOT run `git commit/push` unless your task says so. Do not edit files outside the paths your task names.

## Output conventions
* Write your full JSON result to the path named in your task (valid JSON, UTF-8, no comments) with the Write tool, then return a SHORT summary (counts, ids, blockers) as your final message - not the JSON itself.
* IDs: lowercase snake_case, stable (e.g. `veo3_owl_badger`). Dates ISO (`2025-05-20`, or `2025-05`, or `2025` with `date_precision`).
* URLs must be exact, copy-pasteable, and each verified to have been retrieved (say `retrieved: true/false`).
