"""Step 6 (after cut_plan_lf / patch_segments): any DROPPED word (retakes.json / fixes 'drop' windows) whose audio still
sits inside a kept segment? Every LEFTOVER needs a patch_segments.py op (or a retakes/fixes change + steps 4-5 again).
Reads <project>/retakes.json + fixes.json; the batch layout <batch root> <project name> also works.
usage: python -I check_leftovers.py <project dir>"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def project(argv):
    if not argv: raise SystemExit(__doc__)
    return os.path.normpath(os.path.join(argv[0], argv[1]) if len(argv) > 1 and os.path.isdir(os.path.join(argv[0], argv[1])) else argv[0])
def pjson(P, fn):
    for f in (os.path.join(P, fn), os.path.join(os.path.dirname(P), '_closeout_tools', fn)):
        if os.path.exists(f):
            d = json.load(open(f, encoding='utf-8'))
            if os.path.basename(P) in d: return d[os.path.basename(P)]
            if f == os.path.join(P, fn): return d
    return {}

P = project(sys.argv[1:]); W = os.path.join(P, 'work')
raw = json.load(open(f'{W}/words_raw.json', encoding='utf-8'))['words']
R = pjson(P, 'retakes.json'); drops = R.get('retakes', []) if isinstance(R, dict) else R
fx = pjson(P, 'fixes.json')
gone = set(i for a, b, *_ in drops for i in range(a, b + 1))
dw = [(a, b) for a, b, *_ in fx.get('drop', [])]
segs = [(m['src0'], m['src1']) for m in json.load(open(f'{W}/cut_plan.json', encoding='utf-8'))['segments']]
bad = 0
for i, w in enumerate(raw):
    if w.get('phrase') is not None and (i in gone or any(a <= w['s'] < b for a, b in dw)):
        ov = max((min(e, w['e']) - max(s, w['s']) for s, e in segs), default=0)
        if ov > 0.05: print(f"  LEFTOVER dropped word {i}:{w['w']} {w['s']:.2f}-{w['e']:.2f} overlaps kept audio by {ov * 1000:.0f} ms"); bad += 1
print(f'{os.path.basename(P)}: {bad} leftovers')
