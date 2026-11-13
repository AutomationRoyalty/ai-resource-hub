#!/bin/bash
# qa_reel.sh — pre-delivery QA for a finished reel. Prints PASS / WARN per check.
# Usage: qa_reel.sh <reel.mp4> [source_or_democut.mp4]
#   Pass the raw source (or demo-cut) as arg 2 to also check sibilant (HF) preservation.
F="$1"; SRC="${2:-}"
[ -z "$F" ] && { echo "usage: qa_reel.sh <reel.mp4> [source.mp4]"; exit 1; }
p(){ printf "  %-28s %s\n" "$1" "$2"; }
echo "QA: $F"

read W H PF FR <<<"$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,pix_fmt,r_frame_rate -of default=nw=1:nk=1 "$F" | tr '\n' ' ')"
[ "$W" = 1080 ] && [ "$H" = 1920 ] && [ "$PF" = yuv420p ] && [ "$FR" = 30/1 ] && p "format 1080x1920/30/yuv420p" PASS || p "format" "WARN ($W x$H $PF $FR)"

NA=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$F" | grep -c .)
[ "$NA" = 1 ] && p "single audio stream" PASS || p "audio streams" "WARN ($NA — a player will stack them)"
read AC SR CH <<<"$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels -of default=nw=1:nk=1 "$F" | tr '\n' ' ')"
[ "$AC" = aac ] && [ "$SR" = 44100 ] && [ "$CH" = 2 ] && p "audio aac/44.1k/stereo" PASS || p "audio codec" "WARN ($AC $SR $CH)"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$F")
WE=$(ffmpeg -hide_banner -nostats -i "$F" -af "silencedetect=noise=-30dB:d=0.2" -f null - 2>&1 | awk '/silence_start/{v=$NF} END{print v}')
[ -z "$WE" ] && WE=$DUR
FW=$(ffmpeg -hide_banner -nostats -ss "$(awk -v w=$WE 'BEGIN{printf "%.2f",(w-0.4<0)?0:w-0.4}')" -t 0.4 -i "$F" -af volumedetect -f null - 2>&1 | awk -F': ' '/max_volume/{gsub(/ dB/,"",$2);print $2}')
awk -v v="$FW" 'BEGIN{exit !(v>=-14)}' && p "final word audible (${FW}dB)" PASS || p "final word" "WARN (${FW}dB — soft/clipped; boost it)"
BEAT=$(awk -v d="$DUR" -v w="$WE" 'BEGIN{printf "%.2f",d-w}')
awk -v b="$BEAT" 'BEGIN{exit !(b>=0.2 && b<=1.5)}' && p "tail beat after last word (${BEAT}s)" PASS || p "tail beat" "WARN (${BEAT}s — too abrupt or too long)"

MEAN=$(ffmpeg -hide_banner -nostats -i "$F" -af volumedetect -f null - 2>&1 | awk -F': ' '/mean_volume/{print $2}')
p "loudness mean" "$MEAN (voice should sit -6..-12 dB after master)"

if [ -n "$SRC" ] && [ -f "$SRC" ]; then
  RH=$(ffmpeg -hide_banner -nostats -i "$SRC" -af "highpass=f=6500,volumedetect" -f null - 2>&1 | awk -F': ' '/mean_volume/{gsub(/ dB/,"",$2);print $2}')
  FH=$(ffmpeg -hide_banner -nostats -i "$F"  -af "highpass=f=6500,volumedetect" -f null - 2>&1 | awk -F': ' '/mean_volume/{gsub(/ dB/,"",$2);print $2}')
  awk -v s="$RH" -v f="$FH" 'BEGIN{d=(f>s)?f-s:s-f; exit !(d<=3)}' && p "sibilant HF vs source" "PASS (src ${RH} / reel ${FH})" || p "sibilant HF vs source" "WARN (src ${RH} / reel ${FH} — tails may be clipped; use -25 --pad 0.20)"
fi
echo "  (manual: watch the WHOLE cut — payoff intact, final word spoken ONCE, no frozen tail, safe-zone)"
