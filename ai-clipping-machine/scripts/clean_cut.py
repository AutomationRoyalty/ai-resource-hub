#!/usr/bin/env python3
"""
Frame-accurate cut + rejoin with NO micro-frames and NO audio clicks.

Replaces the `select`/`setpts` jump-cut (which renumbers video frames and audio
samples independently -> stray boundary frames + click at every cut). Instead each
kept segment is `trim`/`atrim`'d, PTS-reset, given a 12 ms audio fade in/out
(declick), then joined with the `concat` filter (operates on raw frames, so no
AAC-priming gaps).

Usage:
  clean_cut.py <input> <output> <keeplist.json>
  keeplist.json = [[start,end], ...] in INPUT seconds
"""
import sys, json, subprocess, os

inp, out, kj = sys.argv[1], sys.argv[2], sys.argv[3]
keep = json.load(open(kj))
K = len(keep)
FADE = 0.012  # 12 ms — inaudible, kills the click

vin = "".join(f"[sv{i}]" for i in range(K))
ain = "".join(f"[sa{i}]" for i in range(K))
L = [f"[0:v]split={K}{vin}", f"[0:a]asplit={K}{ain}"]
cc = ""
for i, (a, b) in enumerate(keep):
    fo = max(0.0, (b - a) - FADE)
    L.append(f"[sv{i}]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]")
    L.append(f"[sa{i}]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
             f"afade=t=in:st=0:d={FADE},afade=t=out:st={fo:.3f}:d={FADE}[a{i}]")
    cc += f"[v{i}][a{i}]"
L.append(f"{cc}concat=n={K}:v=1:a=1[v][a]")

gp = out + ".graph"
open(gp, "w").write(";".join(L))
subprocess.run(
    ["ffmpeg", "-y", "-i", inp, "-/filter_complex", gp, "-map", "[v]", "-map", "[a]",
     "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "30",
     "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out],
    check=True, stderr=subprocess.DEVNULL)
os.remove(gp)
print(f"clean_cut: {K} segments -> {os.path.basename(out)}")
