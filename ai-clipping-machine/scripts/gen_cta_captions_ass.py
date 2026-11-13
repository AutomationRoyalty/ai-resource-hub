#!/usr/bin/env python3
"""Captions for the recorded CTA face clip. Bottom-anchored (shared baseline),
white with black outline. COMMENT and 'BUILD' are enlarged; BUILD wrapped in
single quotes."""
import json
DROP = {"uh"}

def ts(s):
    cs=int(round(s*100)); h,cs=divmod(cs,360000); m,cs=divmod(cs,6000); sec,cs=divmod(cs,100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"

ev=[]
for l in json.load(open("cta_face_plan.json")):
    words=[w["text"] for w in l["words"] if w["text"].lower() not in DROP]
    if not words: continue
    key=" ".join(words).lower().strip(".,!?")
    text=" ".join(words).upper()
    # per-line styling
    if key == "comment":
        body = r"{\fnMontserrat ExtraBold\fs104}" + text
    elif key == "build":
        body = r"{\fnMontserrat ExtraBold\fs122}" + "'BUILD'"
    elif l.get("emphasis"):
        body = r"{\fnMontserrat ExtraBold\fs82}" + text
    else:
        body = text
    ev.append(f"Dialogue: 0,{ts(l['start_sec'])},{ts(l['end_sec'])},Cap,,0,0,0,,{body}")

header="""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Montserrat SemiBold,66,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0.5,0,1,5,1,2,80,80,470,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open("cta_face.ass","w").write(header+"\n".join(ev)+"\n")
print(f"wrote cta_face.ass: {len(ev)} lines (COMMENT + 'BUILD' enlarged)")
