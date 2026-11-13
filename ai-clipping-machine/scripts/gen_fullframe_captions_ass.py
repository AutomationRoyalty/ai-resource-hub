#!/usr/bin/env python3
"""Generic full-frame (vertical talking-head) captions -> libass .ass.

For the "vertical CTA / talking-head" layout: bottom-anchored lower-third,
white Montserrat SemiBold with a black outline (reads over any footage).
Emphasis lines (flagged by captions_plan --emphasis) render ExtraBold + larger.

Usage: gen_fullframe_captions_ass.py <plan.json> <out.ass> [--marginv 470]

Unlike gen_cta_captions_ass.py this hardcodes NO keyword ('BUILD'/'COMMENT');
it's the neutral talking-head caption style used for multi-clip selfie reels.
"""
import argparse, json

def ts(s):
    cs = int(round(s * 100)); h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000); sec, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"

ap = argparse.ArgumentParser()
ap.add_argument("plan"); ap.add_argument("out")
ap.add_argument("--marginv", type=int, default=470)
# Defaults below reproduce the original hardcoded style, so existing videos are unaffected.
ap.add_argument("--preserve-case", action="store_true",
                help="keep the plan's own casing instead of forcing UPPERCASE "
                     "(for mixed-case captions with selective emphasis caps)")
ap.add_argument("--fontsize", type=int, default=60)
ap.add_argument("--outline", type=float, default=5, help="border width; 5 is the heavy default")
ap.add_argument("--shadow", type=float, default=1)
ap.add_argument("--bold", action="store_true", help="set the Bold flag on the style")
ap.add_argument("--popup", action="store_true",
                help="pop-up fade-in per line: rise + scale-up while fading, eased out "
                     "(the house caption animation -- see SOP-reel-edit.md phase 2)")
ap.add_argument("--rise", type=int, default=22, help="px the line travels up, with --popup")
a = ap.parse_args()

# The pop-up needs explicit coordinates because libass can only animate position via \move,
# which takes literal points -- \t cannot touch position at all. Safe here only because our
# captions are validated single-line (<=4 words inside the 800px box); with wrapping, an
# explicit \pos would fight the auto-layout.
#
# Easing note: \move is LINEAR with no accel parameter, but \t does take one. So the rise is
# linear (imperceptible over 150ms) and the ease-out lives on the scale, where it reads. That
# split is deliberate -- it's the closest libass gets to "fast then slow".
POP_Y = 1920 - a.marginv          # \an2 anchors the text BOTTOM at this y
POP = (f"\\move(540,{POP_Y + a.rise},540,{POP_Y},0,150)\\fad(100,0)"
       f"\\fscx92\\fscy92\\t(0,180,0.6,\\fscx100\\fscy100)")

DROP = {"uh", "um"}
ev = []
for l in json.load(open(a.plan)):
    words = [w["text"] for w in l["words"] if w["text"].lower() not in DROP]
    if not words:
        continue
    text = " ".join(words) if a.preserve_case else " ".join(words).upper()
    # One merged override block: emphasis font swap first, then the animation.
    tags = r"\fnMontserrat ExtraBold\fs70" if l.get("emphasis") else ""
    if a.popup:
        tags += POP
    body = ("{" + tags + "}" + text) if tags else text
    ev.append(f"Dialogue: 0,{ts(l['start_sec'])},{ts(l['end_sec'])},Cap,,0,0,0,,{body}")

header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Montserrat SemiBold,{a.fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,{1 if a.bold else 0},0,0,0,100,100,0.5,0,1,{a.outline},{a.shadow},2,140,140,{a.marginv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open(a.out, "w").write(header + "\n".join(ev) + "\n")
print(f"wrote {a.out}: {len(ev)} events")
