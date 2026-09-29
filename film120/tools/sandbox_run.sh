#!/bin/bash
# film120 pipeline stages for the Higgsfield sandbox (ephemeral: every stage is re-runnable from the public repo).
#   sandbox_run.sh <stage> [args]      stages: setup | fonts | media | plan | preview T1,T2,.. | render A B PARTOFFSET | mux | all-frames-check
# state lives in $W (default ~/film2):  repo/ (git clone at $SHA)  media/{orig,proxy}  data/  out/
set -e
W=${W:-$HOME/film2}; SHA=${SHA:-claude/eloquent-volta-o5ddg1}; REPO=https://github.com/leonnrdewa-lang/rumah.git
R=$W/repo/film120; mkdir -p $W; cd $W
stage=$1; shift || true
case $stage in
setup)
  if [ ! -d repo/.git ]; then git clone -q $REPO repo; fi
  cd repo && git fetch -q origin && git checkout -q $SHA 2>/dev/null || git checkout -q -B work origin/$SHA; git pull -q origin $SHA 2>/dev/null || true; git log --oneline | head -1 ;;
fonts)
  if [ ! -d $HOME/fonts ]; then mkdir -p $HOME/fonts /tmp/fp && cd /tmp/fp && for p in anton archivo-narrow instrument-serif inter jetbrains-mono; do npm pack @fontsource/$p >/dev/null 2>&1; done
    for f in fontsource-*.tgz; do mkdir -p x && tar xzf $f -C x && cp x/package/files/*.woff $HOME/fonts/; rm -rf x; done; fi; ls $HOME/fonts | wc -l ;;
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
*) echo "unknown stage $stage"; exit 2 ;;
esac
