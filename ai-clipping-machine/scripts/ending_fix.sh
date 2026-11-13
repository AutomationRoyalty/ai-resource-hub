#!/bin/bash
# ending_fix.sh — fix a reel's ending after the appended CTA is removed.
#
# When a reel loses its appended CTA, it now ends on the demo. If the final word is soft/rushed
# (sped-up) or the tail is a frozen frame, it reads as "cut off." This tool keeps the tight body
# but lands the final sentence: body stays sped, FINAL SENTENCE plays at NORMAL speed, the final
# word gets an ADAPTIVE boost toward ~-9 dB, and the tail is a gentle push-in on the last frame
# (no freeze). Optional music bed.
#
# Work from the PRE-SPEED composite (demo-comp: voice-only, captions + headline already burned).
#
# Usage:
#   ending_fix.sh <demo-comp.mp4> <split_sec> <speed> <out.mp4> [music.mp3] [music_start_sec]
#
#   split_sec  = last CLEAN acoustic pause BEFORE the final sentence. Find it with silencedetect,
#                NOT the word JSON (it's start-only; inter-word gaps read as 0):
#                  ffmpeg -i demo-comp.mp4 -af silencedetect=noise=-25dB:d=0.18 -f null - 2>&1 \
#                    | grep silence_start
#                Pick the pause that leaves a ~2-4s final sentence; the SEAM must land in silence.
#   speed      = body speed factor (e.g. 1.19). Same as the approved reel's demo speed.
#   music.mp3  = optional bed (must be licensed for your use). -30 dB, 1s fade-in, 1.5s fade-out.
#   music_start_sec = where in the mp3 to start (e.g. 45). Default 0.
#
# CRITICAL: splice with trim/atrim INSIDE the filtergraph, never -t (an output-side -t while
# speeding leaves the whole clip -> the tail plays TWICE).
set -e
COMP="$1"; SPLIT="$2"; SPEED="$3"; OUT="$4"; MP3="${5:-}"; MSTART="${6:-0}"
[ -z "$OUT" ] && { echo "usage: ending_fix.sh <demo-comp.mp4> <split_sec> <speed> <out.mp4> [music.mp3] [music_start_sec]"; exit 1; }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ENC="-c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -ar 44100 -ac 2"
END=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$COMP")
PB=$(awk -v e="$END" -v s="$SPLIT" 'BEGIN{printf "%.3f", e-s}')
BASE=$(ffmpeg -hide_banner -nostats -ss "$(awk -v e="$END" 'BEGIN{printf "%.3f",e-1.1}')" -t 0.85 -i "$COMP" -af volumedetect -f null - 2>&1 | awk -F': ' '/max_volume/{gsub(/ dB/,"",$2);print $2}')
# BOOST DEFAULT = OFF. A naturally-soft trailing word should land at its own level. Boosting it
# amplifies noise, and a ramp WITHIN the word swells/glitches and easily ends up louder-than-usual.
# Opt in only when the word is genuinely inaudible (MAXBOOST>0) — then a small gain is applied
# UNIFORMLY across the whole final sentence (Part B is bounded by silence, so no click, no swell).
TARGET="${TARGET:--14}"; MAXBOOST="${MAXBOOST:-0}"
GAIN=$(awk -v b="$BASE" -v t="$TARGET" -v mx="$MAXBOOST" 'BEGIN{g=t-b; if(g<0)g=0; if(g>mx)g=mx; printf "%.1f",g}')
echo "[ending_fix] split=$SPLIT speed=$SPEED  final-word=${BASE}dB  uniform boost +${GAIN}dB (MAXBOOST=$MAXBOOST)  music=${MP3:-none}"

# Part A: tight body sped (trim the INPUT, not -t)
ffmpeg -y -hide_banner -loglevel error -i "$COMP" \
  -filter_complex "[0:v]trim=0:${SPLIT},setpts=(PTS-STARTPTS)/${SPEED},fps=30[v];[0:a]atrim=0:${SPLIT},asetpts=PTS-STARTPTS,atempo=${SPEED}[a]" \
  -map "[v]" -map "[a]" $ENC "$TMP/a.mp4"
# Part B: final sentence at NORMAL speed. Optional UNIFORM gain (constant across Part B; the seams
# are in silence so no click) — GAIN is 0 unless MAXBOOST>0, i.e. no boost by default.
ffmpeg -y -hide_banner -loglevel error -i "$COMP" \
  -filter_complex "[0:v]trim=${SPLIT}:${END},setpts=PTS-STARTPTS,fps=30[v];[0:a]atrim=${SPLIT}:${END},asetpts=PTS-STARTPTS,volume=${GAIN}dB[a]" \
  -map "[v]" -map "[a]" $ENC "$TMP/b.mp4"
# Part C: gentle push-in on the last frame (real motion, NOT a tpad freeze, NOT a source shot-change)
LASTF=$(awk -v e="$END" 'BEGIN{printf "%.3f",e-0.10}')
ffmpeg -y -hide_banner -loglevel error -ss "$LASTF" -i "$COMP" -frames:v 1 "$TMP/last.png"
ffmpeg -y -hide_banner -loglevel error -loop 1 -i "$TMP/last.png" -f lavfi -i anullsrc=r=44100:cl=stereo \
  -filter_complex "[0:v]scale=2160:3840,zoompan=z='min(1+0.0022*in,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=18:s=1080x1920:fps=30[v]" \
  -map "[v]" -map 1:a -t 0.6 $ENC "$TMP/c.mp4"

printf "file '%s'\nfile '%s'\nfile '%s'\n" "$TMP/a.mp4" "$TMP/b.mp4" "$TMP/c.mp4" > "$TMP/cat.txt"
ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i "$TMP/cat.txt" $ENC "$TMP/body.mp4"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$TMP/body.mp4")

if [ -n "$MP3" ]; then
  FO=$(awk -v d="$DUR" 'BEGIN{printf "%.3f", d-1.5}')
  ffmpeg -y -hide_banner -loglevel error -i "$TMP/body.mp4" -ss "$MSTART" -i "$MP3" \
    -filter_complex "[1:a]atrim=0:${DUR},asetpts=PTS-STARTPTS,volume=-30dB,afade=t=in:st=0:d=1,afade=t=out:st=${FO}:d=1.5[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]" \
    -map 0:v -map "[a]" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -ar 44100 -ac 2 -movflags +faststart "$OUT"
else
  ffmpeg -y -hide_banner -loglevel error -i "$TMP/body.mp4" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -ar 44100 -ac 2 -movflags +faststart "$OUT"
fi
echo "[ending_fix] wrote $OUT  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")s"
