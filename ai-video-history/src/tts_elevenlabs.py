#!/usr/bin/env python3
"""Regenerate the narration takes with ElevenLabs (drop-in replacement for the take generation used in this build).

Why this exists: the reel was built in an environment that had no ElevenLabs credentials/tool, and Eleven v4 was only
announced, not documented as released, when it was built. The delivered narration is therefore ByteDance Seed Audio 1.0
(via Higgsfield).  Run this with your own key to swap it:

    export ELEVENLABS_API_KEY=...            # your key
    export ELEVENLABS_VOICE_ID=...           # pick a cinematic voice in your library
    export ELEVENLABS_MODEL_ID=eleven_v3     # or the v4 model id once it is published (check /v1/models)
    python3 tts_elevenlabs.py raw_takes/     # writes L1.wav ... L11.wav (24 kHz mono 16-bit)

then feed raw_takes/ to vo_prepare.py exactly as sandbox_run.sh does (the pipeline re-times captions, music ducking and cuts automatically).
"""
import json, os, sys, urllib.request, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script import LINES

KEY = os.environ['ELEVENLABS_API_KEY']; VOICE = os.environ['ELEVENLABS_VOICE_ID']; MODEL = os.environ.get('ELEVENLABS_MODEL_ID', 'eleven_v3')
out = sys.argv[1] if len(sys.argv) > 1 else 'raw_takes'; os.makedirs(out, exist_ok=True)
for n, text in LINES.items():
    body = json.dumps({'text': text, 'model_id': MODEL, 'voice_settings': {'stability': 0.45, 'similarity_boost': 0.8, 'style': 0.35}}).encode()
    req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=pcm_24000', data=body,
                                 headers={'xi-api-key': KEY, 'Content-Type': 'application/json', 'Accept': 'audio/pcm'})
    pcm = urllib.request.urlopen(req, timeout=120).read()
    with wave.open(os.path.join(out, f'L{n}.wav'), 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    print('wrote', n, len(pcm) / 48000, 's')
