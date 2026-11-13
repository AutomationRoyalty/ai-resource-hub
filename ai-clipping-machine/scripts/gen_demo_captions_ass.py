#!/usr/bin/env python3
"""Branded ASS captions — 9:16 Reel, white text on black, tucked under the video.
No blue. Emphasis lines stay white but ExtraBold + slightly larger."""
import json, sys

PLAN = sys.argv[1] if len(sys.argv) > 1 else "captions_fast.json"
OUT  = sys.argv[2] if len(sys.argv) > 2 else "captions_fast.ass"

WHITE   = "&H00FFFFFF"
OUTLINE = "&H00000000"   # black (invisible on black bg, crisp edge if it overlaps)

FIX  = {"send": "sent", "seter": "setter", "seters": "setters"}
DROP = {"uh"}

def clean(words):
    out = []
    for w in words:
        t = w["text"]
        if t.lower() in DROP:
            continue
        out.append(FIX.get(t.lower(), t))
    return out

def ts(s):
    cs = int(round(s * 100)); h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000); sec, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"

lines = json.load(open(PLAN))
ev = []
for l in lines:
    words = clean(l["words"])
    if not words:
        continue
    text = " ".join(words).upper()
    if l.get("emphasis"):
        body = r"{\fnMontserrat ExtraBold\fs62}" + text
    else:
        body = text
    ev.append(f"Dialogue: 0,{ts(l['start_sec'])},{ts(l['end_sec'])},Caption,,0,0,0,,{body}")

# Alignment 8 = top-center; MarginV = px from top -> sits just under the video (video ends y=1298)
header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Montserrat SemiBold,54,{WHITE},{WHITE},{OUTLINE},&H00000000,0,0,0,0,100,100,0.4,0,1,0,0,8,90,90,1330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open(OUT, "w").write(header + "\n".join(ev) + "\n")
print(f"wrote {OUT}: {len(ev)} events")
