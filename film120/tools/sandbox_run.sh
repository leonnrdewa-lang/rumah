#!/bin/bash
# film120 pipeline stages for the Higgsfield sandbox (ephemeral: every stage is re-runnable from the public repo).
#   sandbox_run.sh <stage> [args]      stages: setup | fonts | media | plan | preview T1,T2,.. | render A B PARTOFFSET | mux | all-frames-check
# state lives in $W (default ~/film2):  repo/ (git clone at $SHA)  media/{orig,proxy}  data/  out/
set -e
W=${W:-$HOME/film2}; SHA=${SHA:-claude/eloquent-volta-o5ddg1}; REPO=https://github.com/leonnrdewa-lang/rumah.git
R=$W/repo/film120; mkdir -p $W; cd $W
stage=$1; shift || true; export PATH=$HOME/.local/bin:$PATH
case $stage in
setup)
  if [ ! -d repo/.git ]; then git clone -q $REPO repo; fi
  cd repo && git fetch -q origin && git checkout -q $SHA 2>/dev/null || git checkout -q -B work origin/$SHA; git pull -q origin $SHA 2>/dev/null || true; git log --oneline | head -1 ;;
fonts)
  if [ ! -d $HOME/fonts ]; then mkdir -p $HOME/fonts /tmp/fp && cd /tmp/fp && for p in anton archivo-narrow instrument-serif inter jetbrains-mono; do npm pack @fontsource/$p >/dev/null 2>&1; done
    for f in fontsource-*.tgz; do mkdir -p x && tar xzf $f -C x && cp x/package/files/*.woff $HOME/fonts/; rm -rf x; done; fi; ls $HOME/fonts | wc -l ;;
vo)      # narration takes (ElevenLabs v4 URLs in data/vo/takes_v4.json) -> tempo 1.06 -> tightened wavs + vo.json (word times from faster-whisper)
  mkdir -p $W/data/vo/raw && cd $W/data/vo && python3 - <<PY
import json, subprocess
t = json.load(open('$R/data/vo/takes_v4.json'))
for k, v in t.items():
    subprocess.run(['curl', '-sS', '-L', '-o', f'raw/{k}.mp3', v['url']], check=True)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', f'raw/{k}.mp3', '-af', 'atempo=1.06', '-ac', '1', '-ar', '24000', '-sample_fmt', 's16', f'raw/{k}.wav'], check=True)
print('takes', len(t))
PY
  python3 $R/tools/vo_prepare.py $R/data/script.json raw . && cp $R/data/vo/vo.json ../vo_repo.json 2>/dev/null; ls | head -3 ;;
media)   # download + proxy the shortlisted clips, then profile them
  cd $W && mkdir -p data && cp $R/data/shortlist.json data/shortlist.json
  python3 $R/tools/make_proxies.py data/shortlist.json media data/shortlist_proxied.json --pad 0.5 --max-mb 150
  python3 - <<'PY'
import json
d = json.load(open('data/shortlist_proxied.json')); json.dump({k: {'local': c['local']} for k, c in d['clips'].items() if c.get('local')}, open('data/clips_local.json', 'w')); print('proxied', sum(1 for c in d['clips'].values() if c.get('local')), 'of', len(d['clips']))
PY
  python3 $R/tools/profile_clips.py profile data/clips_local.json media data/profiles.json ;;
plan)    # shortlist + profiles + narration -> data/edit_plan.json (cues resolved from the narration)
  cd $W && python3 $R/tools/build_plan.py plan data/shortlist_proxied.json data/profiles.json data/edit_plan.json
  if [ -f $R/data/cue_spec.json ] && [ -f data/vo/vo.json ]; then python3 $R/tools/make_cues.py $R/data/cue_spec.json $R/data/script.json data/vo/vo.json data/cues.json && python3 - <<'PY'
import json
p = json.load(open('data/edit_plan.json')); p['cues'].update(json.load(open('data/cues.json'))); json.dump(p, open('data/edit_plan.json', 'w'), indent=1); print('cues merged:', len(p['cues']))
PY
  fi ;;
preview)
  export FFMPEG=$(command -v ffmpeg); cd $R && python3 render.py --plan $W/data/edit_plan.json --script $R/data/script.json --vo $W/data/vo/vo.json --out $W/prev --fonts $HOME/fonts --preview "$1" --streams 16 ;;
render)  # render frames A..B seconds into out/part_XXX.mp4 (chunks of 60 frames, 5 workers)
  export FFMPEG=$(command -v ffmpeg); mkdir -p $W/out; cd $R && python3 render.py --plan $W/data/edit_plan.json --script $R/data/script.json --vo $W/data/vo/vo.json --out $W/out --fonts $HOME/fonts --range $1,$2 --part-offset ${3:-0} --workers 5 --streams 16 ;;
mux)     # concat parts -> video.mp4 (exactly 3600 frames)
  cd $W/out && ls part_*.mp4 | sort | sed "s/^/file '/;s/$/'/" > list.txt && ffmpeg -y -v error -f concat -safe 0 -i list.txt -c copy video_raw.mp4 && ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames,width,height -of csv=p=0 video_raw.mp4 ;;
audio)   # cue sheet -> licensed layers -> mix (narration + score + procedural/licensed SFX) -> -14 LUFS / TP -1.5 master, exactly 120.000 s
  export FFMPEG=$(command -v ffmpeg); cd $R && python3 tools/dump_events.py $W/data/edit_plan.json data/script.json $W/data/vo/vo.json $W/data/events.json
  if [ -f $W/lic/licensed.json ]; then python3 tools/audio_layers.py layer $W/data/events.json $W/lic/licensed.json $W/data/events_lic.json; LIC="--licensed $W/lic/licensed.json"; EV=$W/data/events_lic.json; else EV=$W/data/events.json; LIC=""; fi
  mkdir -p $W/audio && python3 audio/mixer.py --script data/script.json --vo $W/data/vo/vo.json --vo-dir $W/data/vo --events $EV $LIC --out $W/audio/mix_raw.wav --stems $W/audio/stems
  cd $W/audio && M=$(ffmpeg -hide_banner -nostats -i mix_raw.wav -af loudnorm=I=-14:TP=-1.8:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
  echo "$M" > loudnorm1.json; IL=$(echo "$M" | python3 -c "import json,sys;print(json.load(sys.stdin)['input_i'])"); TP=$(echo "$M" | python3 -c "import json,sys;print(json.load(sys.stdin)['input_tp'])"); LR=$(echo "$M" | python3 -c "import json,sys;print(json.load(sys.stdin)['input_lra'])"); TH=$(echo "$M" | python3 -c "import json,sys;print(json.load(sys.stdin)['input_thresh'])"); OF=$(echo "$M" | python3 -c "import json,sys;print(json.load(sys.stdin)['target_offset'])")
  ffmpeg -y -v error -i mix_raw.wav -af "loudnorm=I=-14:TP=-1.8:LRA=11:measured_I=$IL:measured_TP=$TP:measured_LRA=$LR:measured_thresh=$TH:offset=$OF:linear=true:print_format=summary,aresample=48000,alimiter=limit=0.794:attack=3:release=60:level=false,apad=whole_dur=120,atrim=0:120" -ar 48000 -ac 2 -c:a pcm_s16le master.wav
  ffmpeg -hide_banner -nostats -i master.wav -af ebur128=peak=true -f null - 2>&1 | tail -12; ffprobe -v error -show_entries format=duration -of csv=p=0 master.wav ;;
final)   # concat parts -> video-only encode (kept: film_v.mp4) -> mux with the master -> film.mp4 (exactly 3600 frames / 120.000 s).  `final remux` skips the slow video encode.
  cd $W/out && if [ "$1" != "remux" ] || [ ! -f $W/film_v.mp4 ]; then ls part_*.mp4 | sort | sed "s/^/file '/;s/$/'/" > list.txt && ffmpeg -y -v error -f concat -safe 0 -i list.txt -c copy video_raw.mp4 && ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames,width,height,r_frame_rate -of csv=p=0 video_raw.mp4
    ffmpeg -y -v error -i video_raw.mp4 -an -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 -g 60 -t 120 -movflags +faststart $W/film_v.mp4; fi
  ffmpeg -y -v error -i $W/film_v.mp4 -i $W/audio/master.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -ar 48000 -t 120 -movflags +faststart $W/film.mp4
  ffprobe -v error -count_frames -show_entries stream=codec_type,nb_read_frames,duration,width,height:format=duration -of default=nw=1 $W/film.mp4 | head -20; ls -la $W/film.mp4 ;;
*) echo "unknown stage $stage"; exit 2 ;;
esac
