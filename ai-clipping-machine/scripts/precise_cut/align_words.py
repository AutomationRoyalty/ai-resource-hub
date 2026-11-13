"""Step 8: final word-level timing on the CUT: the verified word list (cut_plan.json) is CTC force-aligned
(ElevenLabs Forced Alignment API) to the cut audio (work/cut/cut16k.wav from render_cut.py) one cut-segment at a time (no drift).
Writes <Transcript dir>/words.json {source, duration, fps, pad_ms, words:[{w,s,e,i,f0,f1}]} (s/e = seconds on the cut,
f0/f1 = 1-based frames) + words.csv + words.srt + transcript.md. The padding / pause numbers come from cut_plan.json.
usage: python -I align_words.py <project>/work <project>/Transcript "<Title> - TIGHT CUT.mp4" "<Title>" [--fps 30]"""
import csv, json, os, re, sys
import numpy as np
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from align_api import align_one, align_many, fill_gaps
from scipy.io import wavfile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
args = sys.argv[1:]
FPS = 30
if '--fps' in args: k = args.index('--fps'); FPS = int(args[k + 1]); del args[k:k + 2]
if len(args) < 4: raise SystemExit(__doc__)
W, OUTD, CUTNAME, TITLE = args[:4]
plan = json.load(open(f'{W}/cut_plan.json', encoding='utf-8'))
PAD_MS, GAP_MS = round(plan.get('pad', 0.015) * 1000), round(plan.get('gap_t', 0.2) * 1000)
sr, wav = wavfile.read(f'{W}/cut/cut16k.wav'); wav = wav.astype(np.float32) / 32768
words = [dict(w=w['w'], cs=w['cs']) for w in plan['words']]
_CACHE = {}
def _api_align(seg0, seg1, ws):
    key = (round(seg0, 4), round(seg1, 4), tuple(w['w'] for w in ws))
    if key not in _CACHE:
        s0, s1 = max(0, seg0 - 0.03), min(len(wav) / sr, seg1 + 0.03)
        _CACHE[key] = (s0, align_one(wav[int(s0 * sr):int(s1 * sr)], [w['w'] for w in ws]))
    s0, r = _CACHE[key]; r = fill_gaps(r, 0.0, seg1 + 0.03 - s0)
    return {i: [s0 + x[0], s0 + x[1]] for i, x in enumerate(r)}, float(np.mean([x[2] for x in r])) if r else 0.0
print('alignment: ElevenLabs Forced Alignment API', flush=True)
_SEGS = []
for m in plan['segments']:
    o0, o1 = m['out0'], m['out0'] + m['src1'] - m['src0']
    _ws = [w for w in words if o0 - 1e-6 <= w['cs'] < o1 - 1e-6]
    if _ws: _SEGS.append((o0, o1, _ws))
_RES = align_many([(wav[int(max(0, a - 0.03) * sr):int(min(len(wav) / sr, b + 0.03) * sr)], [w['w'] for w in ws]) for a, b, ws in _SEGS])
for (a, b, ws), r in zip(_SEGS, _RES): _CACHE[(round(a, 4), round(b, 4), tuple(w['w'] for w in ws))] = (max(0, a - 0.03), r)
align = _api_align
# a word whose mapped onset sits in the last 60 ms of a segment really starts in the next one
# (e.g. "Look": the aligner put its onset 540 ms early, inside the pause that was cut)
ends = [m['out0'] + m['src1'] - m['src0'] for m in plan['segments']]
for w in words:
    for e in ends:
        if e - 0.06 < w['cs'] < e: w['cs'] = e
VARIANTS = set()
out = []
for m in plan['segments']:
    o0, o1 = m['out0'], m['out0'] + m['src1'] - m['src0']
    ws = [w for w in words if o0 - 1e-6 <= w['cs'] < o1 - 1e-6]
    res, score = align(o0, o1, ws)
    # articles the script and whisper disagree on: keep the reading the audio scores higher
    for k, w in enumerate(ws):
        if w['w'] in ('a', 'the') and 0 < k < len(ws) - 1 and (ws[k - 1]['w'], ws[k + 1]['w'].strip('.,')) in VARIANTS:
            alt = [dict(x, w=('the' if w['w'] == 'a' else 'a')) if j == k else x for j, x in enumerate(ws)]
            res2, score2 = align(o0, o1, alt)
            print(f'  "{ws[k-1]["w"]} {w["w"]} {ws[k+1]["w"]}" {score:.4f} vs "{alt[k]["w"]}" {score2:.4f}')
            if score2 > score: ws, res, score = alt, res2, score2
    for i, w in enumerate(ws): out.append(dict(w=w['w'], s=round(res[i][0], 3), e=round(res[i][1], 3)))
# merge split tokens: "high" + "-quality", "95" + "%"
ws = []
for w in out:
    if ws and (w['w'].startswith('-') or w['w'] in ('%',)): ws[-1]['w'] += w['w']; ws[-1]['e'] = w['e']; continue
    ws.append(dict(w))
for i, w in enumerate(ws):
    w['i'] = i; w['f0'] = int(w['s'] * FPS) + 1; w['f1'] = int(w['e'] * FPS) + 1     # 1-based frame containing the time
os.makedirs(OUTD, exist_ok=True)
dur = plan['duration']
json.dump(dict(source=CUTNAME, duration=round(len(wav) / sr, 3), fps=FPS, pad_ms=PAD_MS,
               words=ws), open(f'{OUTD}/words.json', 'w', encoding='utf-8'), indent=1)
with open(f'{OUTD}/words.csv', 'w', newline='', encoding='utf-8') as f:
    c = csv.writer(f); c.writerow(['i', 'word', 'start_ms', 'end_ms', 'frame_in', 'frame_out'])
    for w in ws: c.writerow([w['i'], w['w'], int(round(w['s'] * 1000)), int(round(w['e'] * 1000)), w['f0'], w['f1']])
def ts(t):
    ms = int(round(t * 1000)); return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'
with open(f'{OUTD}/words.srt', 'w', encoding='utf-8') as f:
    for k, w in enumerate(ws, 1): f.write(f"{k}\n{ts(w['s'])} --> {ts(w['e'])}\n{w['w']}\n\n")
sents, cur = [], []
for w in ws:
    cur.append(w)
    if re.search(r'[.?!]$', w['w']): sents.append(cur); cur = []
if cur: sents.append(cur)
with open(f'{OUTD}/transcript.md', 'w', encoding='utf-8') as f:
    f.write(f'# {TITLE} — word-level transcript of the tight cut\n\n'
            f'Cut: `{CUTNAME}` · {len(wav) / sr:.3f} s · {len(ws)} words · '
            f'{len(ws) / (len(wav) / sr) * 60:.0f} wpm · every pause >= {GAP_MS} ms trimmed to {PAD_MS} ms each side · '
            f'times in ms on the cut timeline, frames 1-based @{FPS} fps (word-by-word in words.csv / words.json / words.srt)\n\n'
            '| # | start–end (ms) | frames | sentence |\n|---|---|---|---|\n')
    for k, s in enumerate(sents, 1):
        f.write(f"| {k} | {int(s[0]['s'] * 1000)}–{int(s[-1]['e'] * 1000)} | {s[0]['f0']}–{s[-1]['f1']} | {' '.join(x['w'] for x in s)} |\n")
print(len(ws), 'words;', len(sents), 'sentences')
for s in sents: print(f"  {s[0]['s']:6.3f}-{s[-1]['e']:6.3f}  {' '.join(x['w'] for x in s)}")
