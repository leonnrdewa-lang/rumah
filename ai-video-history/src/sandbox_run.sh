#!/bin/bash
# Full pipeline, run inside the Higgsfield sandbox (the only place with internet + ffmpeg). Usage: STAGES="setup vo audio render mux" SHA=<commit> bash sandbox_run.sh
# Inputs expected in $W: vo_urls.txt ("<line> <url>" per line, the raw TTS takes).  Output: $W/out/*
set -e
W=/home/user/proj; mkdir -p $W/src $W/out; cd $W
R=https://raw.githubusercontent.com/leonnrdewa-lang/rumah/${SHA:-claude/eloquent-volta-o5ddg1}/ai-video-history/src
STAGES=${STAGES:-"setup vo audio render mux"}
has(){ [[ " $STAGES " == *" $1 "* ]]; }
if has setup; then
  for f in script.py vo_prepare.py storyboard.py design.py render_lib.py scenes.py render.py synth_audio.py fetch_footage.py footage_sources.json make_srt.py; do curl -fsS -m 30 -o src/$f $R/$f; done
  if [ ! -d /home/user/fonts ]; then mkdir -p /home/user/fonts /tmp/fp && cd /tmp/fp && for p in montserrat inter space-mono; do npm pack @fontsource/$p >/dev/null 2>&1; done
    for f in fontsource-*.tgz; do mkdir -p x && tar xzf $f -C x && cp x/package/files/*latin-*-normal.woff /home/user/fonts/; rm -rf x; done; cd $W; fi
  [ -f footage/footage_manifest.json ] || python3 src/fetch_footage.py footage > out/fetch.log 2>&1
  echo "setup done"
fi
if has vo; then
  mkdir -p vo_raw; while read n u; do curl -fsS -m 60 -o vo_raw/L$n.wav "$u"; done < vo_urls.txt
  python3 src/vo_prepare.py vo_raw vo_clean 2>&1 | grep -v Warning > out/vo.log; cp vo_clean/vo.json out/vo.json; echo "vo done"
fi
if has audio; then
  python3 src/synth_audio.py --vo vo_clean/vo.json --vo-dir vo_clean --out out/mix_raw.wav --stems out/stems > out/audio.log 2>&1; cat out/audio.log | tail -3
  python3 src/make_srt.py vo_clean/vo.json out/subtitles.srt
fi
if has render; then
  python3 src/render.py --footage footage --vo vo_clean/vo.json --out out --fonts /home/user/fonts --workers ${WORKERS:-6} ${RANGE:+--range $RANGE} > out/render.log 2>&1; tail -3 out/render.log
fi
if has mux; then
  # two-pass loudness normalisation to -14 LUFS / -1 dBTP, then mux
  M=$(ffmpeg -hide_banner -nostats -i out/mix_raw.wav -af loudnorm=I=-14:TP=-1.0:LRA=9:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
  echo "$M" > out/loudnorm_pass1.json
  g(){ echo "$M" | python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
  ffmpeg -y -v error -i out/mix_raw.wav -af "loudnorm=I=-14:TP=-1.0:LRA=9:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true,alimiter=limit=0.89:level=false" -ar 48000 out/mix.wav
  ffmpeg -y -v error -i out/video_silent.mp4 -i out/mix.wav -c:v copy -c:a aac -b:a 320k -ar 48000 -movflags +faststart -shortest out/final.mp4
  ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,duration,bit_rate,sample_rate,channels -of default=nw=1 out/final.mp4
  ffmpeg -hide_banner -nostats -i out/final.mp4 -af ebur128=peak=true -f null - 2>&1 | tail -12
  echo "mux done"
fi
