#!/usr/bin/env python3
"""
Detect low-energy pauses in a clip and build a jump-cut plan for a faster edit.

Usage:
  build_jumpcuts.py <clip.mp4> <workdir> [--words words.json] \
      [--threshold -25] [--pad 0.12] [--min-silence 0.28]

Outputs into <workdir>:
  keep_segments.json   list of [start,end] segments to KEEP
  select_expr.txt      ffmpeg select/aselect expression for those segments
  words_fast.json      (only if --words given) input words remapped to the new timeline

Then cut the clip with:
  EXPR=$(cat <workdir>/select_expr.txt)
  ffmpeg -i clip.mp4 -vf "select='$EXPR',setpts=N/FR/TB" \
                     -af "aselect='$EXPR',asetpts=N/SR/TB" clip_fast.mp4
"""
import argparse, json, re, subprocess, sys
from pathlib import Path


def detect_silences(clip, threshold, min_sil):
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", clip, "-af",
         f"silencedetect=noise={threshold}dB:d={min_sil}", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    sil, s = [], None
    for ln in out.splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", ln)
        if m: s = float(m.group(1))
        m = re.search(r"silence_end:\s*([\d.]+)", ln)
        if m and s is not None:
            sil.append((s, float(m.group(1)))); s = None
    return sil


def duration(clip):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nk=1:nw=1", clip], capture_output=True, text=True).stdout
    return float(out.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("workdir")
    ap.add_argument("--words", default=None, help="words.json to remap onto the tightened timeline")
    ap.add_argument("--threshold", type=float, default=-25.0)
    ap.add_argument("--pad", type=float, default=0.12, help="breathing room kept on each side of a cut")
    ap.add_argument("--min-silence", type=float, default=0.28)
    a = ap.parse_args()
    wd = Path(a.workdir); wd.mkdir(parents=True, exist_ok=True)

    DUR = duration(a.clip)
    sil = detect_silences(a.clip, a.threshold, a.min_silence)
    last_word_end = DUR
    if a.words:
        ws = json.load(open(a.words))
        last_word_end = max(w["end"] for w in ws)

    removed = []
    for (s, e) in sil:
        rs = 0.0 if s <= 0.02 else s + a.pad
        re_ = DUR if e >= DUR - 0.02 else e - a.pad
        if re_ > rs + 0.03:
            removed.append([rs, re_])
    removed.append([last_word_end + 0.22, DUR])          # trim trailing tail
    removed.sort()
    merged = []
    for r in removed:
        if merged and r[0] <= merged[-1][1] + 0.001:
            merged[-1][1] = max(merged[-1][1], r[1])
        else:
            merged.append(r)

    keep, cur = [], 0.0
    for (rs, re_) in merged:
        if rs > cur + 0.02:
            keep.append([round(cur, 3), round(rs, 3)])
        cur = max(cur, re_)
    if cur < DUR - 0.02:
        keep.append([round(cur, 3), round(DUR, 3)])

    new_dur = sum(b - a_ for a_, b in keep)
    json.dump(keep, open(wd / "keep_segments.json", "w"))
    expr = "+".join(f"between(t,{a_},{b})" for a_, b in keep)
    open(wd / "select_expr.txt", "w").write(expr)
    print(f"{a.clip}: {DUR:.2f}s -> {new_dur:.2f}s  (cut {DUR-new_dur:.2f}s, {len(keep)} segments)")

    if a.words:
        def remap(t):
            acc = 0.0
            for (x, y) in keep:
                if t >= y: acc += y - x
                elif t >= x: return acc + (t - x)
                else: return acc
            return acc
        wf = []
        for w in json.load(open(a.words)):
            ns, ne = round(remap(w["start"]), 3), round(remap(w["end"]), 3)
            if ne <= ns: ne = ns + 0.12
            wf.append({"word": w["word"], "start": max(0.0, ns), "end": ne})
        json.dump(wf, open(wd / "words_fast.json", "w"), indent=1)
        print(f"remapped {len(wf)} words -> words_fast.json")


if __name__ == "__main__":
    main()
