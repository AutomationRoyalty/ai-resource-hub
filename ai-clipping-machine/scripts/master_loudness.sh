#!/bin/bash
# master_loudness.sh — the standing loudness pass for EVERY deliverable.
#
#   Speech must sit in the -6…-12 dB window for the WHOLE runtime. Reels, ads, long-form
#   vlogs, Palmier Pro exports, intro cuts, preview renders — all of it.
#
# Usage:
#   master_loudness.sh <in.mp4 | in_dir> <out_dir>     master one file or every .mp4 in a dir
#   master_loudness.sh --verify <file.mp4> [...]        report speech-window peak distribution
#
# Recipe: two-pass loudnorm I=-14 : TP=-6 : LRA=9, applied with the measured values.
#   -c:v copy  -> the picture is never re-encoded, so an approved master can't drift.
#
# Do NOT add an alimiter on top or push TP below -6: it squashes the track (integrated drops
# to ~-17.5 LUFS) and AAC encode overshoot still leaves the odd sample peak above -6 anyway.
# A -5.7 dB sample peak on a correct master is codec overshoot, not a miss.
#
# Targets can be overridden per-project with MASTER_I / MASTER_TP / MASTER_LRA. Defaults are
# the locked recipe and should be left alone. The one case that needs an override is a source
# with a very LOW input LRA (heavily compressed on-camera mic speech, e.g. the DJI vlog mics
# at LRA ~3): there the default stacks every speech peak against the -6 ceiling, so ~10% of
# windows tip just above it and --verify fails at 89-90%. Shifting down 1 dB
# (MASTER_I=-15 MASTER_TP=-7) centres the same distribution inside the -6..-12 window and
# verifies at 97%. Always confirm with --verify rather than assuming either setting.
#
# MASTER_PRE (Week 16): an optional filter chain run AHEAD of loudnorm, ending in a comma,
# e.g. MASTER_PRE="acompressor=threshold=-24dB:ratio=3:attack=5:release=120,". Week 16's
# DJI takes were peakier than usual: the locked recipe put the talks at 58-63% in band
# (median -11), the TP ceiling binding long before the level target. A gentle 3:1 above
# -24 dB moved the same talks to 93% (median -6.8). Try the locked recipe first; use this
# only when --verify / level_audit shows the ceiling binding, and report it.
set -euo pipefail

PRE="${MASTER_PRE:-}"
I_TARGET="${MASTER_I:--14}"
TP_TARGET="${MASTER_TP:--6}"
LRA_TARGET="${MASTER_LRA:-9}"

verify() {
  python3 - "$@" <<'PY'
import subprocess, array, math, statistics, sys
for path in sys.argv[1:]:
    pcm = subprocess.run(["ffmpeg","-v","error","-i",path,"-ac","1","-ar","48000","-f","s16le","-"],
                         capture_output=True).stdout
    a = array.array('h'); a.frombytes(pcm)
    N = int(48000*0.4); rows=[]
    for i in range(0, len(a)-N, N):
        w = a[i:i+N]
        pk = max(max(w), -min(w))
        rms = sum(x*x for x in w)/N
        rows.append((20*math.log10(pk/32768) if pk else -99,
                     10*math.log10(rms/32768**2) if rms else -99))
    speech = [p for p,r in rows if r > -35]          # speech-active windows only
    if not speech:
        print(f"{path}: no speech-active windows"); continue
    speech.sort()
    inw = [p for p in speech if -12 <= p <= -6]
    ok = 100*len(inw)/len(speech)
    print(f"{path}\n  speech windows {len(speech)}/{len(rows)}  "
          f"peak p10 {speech[len(speech)//10]:.1f}  med {statistics.median(speech):.1f}  "
          f"p90 {speech[9*len(speech)//10]:.1f} dB\n"
          f"  in -6..-12 window: {ok:.0f}%   {'PASS' if ok >= 90 else 'FAIL — re-master'}")
PY
}

if [ "${1:-}" = "--verify" ]; then shift; verify "$@"; exit 0; fi

IN="${1:?usage: master_loudness.sh <in.mp4|in_dir> <out_dir>}"
OUT="${2:?usage: master_loudness.sh <in.mp4|in_dir> <out_dir>}"
mkdir -p "$OUT"

if [ -d "$IN" ]; then files=("$IN"/*.mp4); else files=("$IN"); fi

for f in "${files[@]}"; do
  b=$(basename "$f")
  echo "=== $b"
  J=$(ffmpeg -hide_banner -nostats -i "$f" -af "${PRE}loudnorm=I=$I_TARGET:TP=$TP_TARGET:LRA=$LRA_TARGET:print_format=json" \
        -f null - 2>&1 | awk '/^\{/,/^\}/')
  read -r I TP LRA TH OFF < <(echo "$J" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print(d['input_i'],d['input_tp'],d['input_lra'],d['input_thresh'],d['target_offset'])")
  ffmpeg -hide_banner -nostats -y -i "$f" -c:v copy \
    -af "${PRE}loudnorm=I=$I_TARGET:TP=$TP_TARGET:LRA=$LRA_TARGET:measured_I=$I:measured_TP=$TP:measured_LRA=$LRA:measured_thresh=$TH:offset=$OFF:linear=true" \
    -c:a aac -b:a 256k -ar 48000 "$OUT/$b" 2>&1 | tail -2
  verify "$OUT/$b"
done
