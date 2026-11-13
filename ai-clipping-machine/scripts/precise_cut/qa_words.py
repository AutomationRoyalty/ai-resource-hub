"""Step 3b: flag what the retake list may have missed, on the SOURCE timeline:
- voiced runs (5 ms envelope > -40 dB, >= 120 ms) that no kept word covers (untranscribed speech: a dropped repeat?)
- kept words longer than 0.8 s (the aligner stretched a word over speech whisper skipped) -> probe.py every one,
  numbers included ("2.0" once hid a whole take)
- a > 0.9 s gap with voice in it between two consecutive kept words
Reads <project>/retakes.json (see retakes_example.json). The batch layout also works: <batch root> <project name>
with <batch root>/_closeout_tools/retakes.json keyed by project folder name.
usage: python -I qa_words.py <project dir>"""
import json, os, sys
import numpy as np
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
words = json.load(open(f'{W}/words_raw.json', encoding='utf-8'))['words']
R = pjson(P, 'retakes.json'); drops = R.get('retakes', []) if isinstance(R, dict) else R
dropped = set(i for a, b, *_ in drops for i in range(a, b + 1))
kept = [(i, w) for i, w in enumerate(words) if i not in dropped]
db = np.load(f'{W}/db5ms.npy'); HOP = 0.005
core = db > -40
dd = np.diff(np.r_[0, core.astype(int), 0]); st, en = np.where(dd == 1)[0], np.where(dd == -1)[0]
runs = []
for a, b in zip(st, en):
    if runs and a - runs[-1][1] < 12: runs[-1][1] = b
    else: runs.append([a, b])
runs = [(float(a * HOP), float(b * HOP)) for a, b in runs if (b - a) * HOP >= 0.12]
def cov(a, b, ws): return [i for i, w in ws if min(b, w['e'] + 0.12) - max(a, w['s']) > 0]
print(f'== {os.path.basename(P)}: {len(kept)} kept words, {len(dropped)} dropped, {len(runs)} voiced runs')
for a, b in runs:
    k = cov(a, b, kept); dr = cov(a, b, [(i, w) for i, w in enumerate(words) if i in dropped])
    if not k and not dr: print(f'  UNCOVERED voice {a:7.2f}-{b:7.2f} ({b - a:.2f} s)')
for i, w in kept:
    if w['e'] - w['s'] > 0.8: print(f"  LONG word {i}:{w['w']} {w['s']:.2f}-{w['e']:.2f} ({w['e'] - w['s']:.2f} s)")
for i in range(1, len(kept)):
    (pi, p), (ci, c) = kept[i - 1], kept[i]
    if c['s'] - p['e'] > 0.9 and ci == pi + 1:
        v = [(a, b) for a, b in runs if a < c['s'] and b > p['e']]
        if v: print(f"  GAP with voice between {pi}:{p['w']} and {ci}:{c['w']} ({p['e']:.2f}-{c['s']:.2f}) runs {[(round(a, 2), round(b, 2)) for a, b in v]}")
