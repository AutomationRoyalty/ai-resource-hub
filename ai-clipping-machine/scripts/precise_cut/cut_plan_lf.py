"""Step 5: the tight-cut plan (long-form): keep the last take, trim every pause >= GAP_T to PAD of air on each side.
1. voiced runs on the 5 ms energy envelope (> CORE dB, dips < 60 ms bridged);
2. a run is kept only if it overlaps a transcribed word's aligned span -> breaths, mouth noise and a
   retake whisper skipped are dropped automatically;
3. breath guard: an unvoiced >= 80 ms lead/tail bridged to the words is trimmed to onset - 60 ms / offset + 150 ms;
4. kept runs get a soft consonant tail/onset (<= 30 ms above SOFT) and a released stop burst ("pos-T") within 150 ms;
5. gaps between kept speech >= GAP_T are cut leaving PAD each side; shorter gaps stay natural;
6. fixes.json 'keep' windows (a scripted pause/breath) are kept whole; word-end guard keeps an audible final fricative.
Guard: every word keeps >= 90 % of its voiced frames. Reads <work>/words_final.json (build_words.py), writes
<work>/cut_plan.json (segments + words on the cut timeline). Long-form default PAD = 15 ms (since "17 Tips on Design").
usage: python -I cut_plan_lf.py <project>/work [--pad <ms>=15] [--gap <ms>=200]"""
import json, os, sys, numpy as np
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
args = sys.argv[1:]
def opt(name, default):
    if name in args: k = args.index(name); v = float(args[k + 1]); del args[k:k + 2]; return v
    return default
PAD, GAP_T, HOP = opt('--pad', 15) / 1000, opt('--gap', 200) / 1000, 0.005
if not args: raise SystemExit(__doc__)
W = args[0]
CORE, SOFT, BURST, DIP = -40.0, -50.0, -46.0, 0.060
db = np.load(f'{W}/db5ms.npy'); N = len(db)
words = json.load(open(f'{W}/words_final.json', encoding='utf-8'))
T = lambda i: round(float(i) * HOP, 4); I = lambda t: int(round(t / HOP))
core = db > CORE
d = np.diff(np.r_[0, core.astype(int), 0]); st, en = np.where(d == 1)[0], np.where(d == -1)[0]
runs = []
for a, b in zip(st, en):
    if runs and a - runs[-1][1] < I(DIP): runs[-1][1] = b
    else: runs.append([a, b])
runs = [r for r in runs if r[1] - r[0] >= 3]
spans = [(I(w['s']), I(w['e'] + 0.12)) for w in words]   # +120 ms: final s/t releases the aligner ends early
kept = [r for r in runs if any(min(r[1], b) - max(r[0], a) > 0 for a, b in spans)]
dropped = [r for r in runs if r not in kept]
for r in dropped: print(f'  drop non-word audio {T(r[0]):.3f}-{T(r[1]):.3f} peak {db[r[0]:r[1]].max():.0f} dB')
# --- long-form breath guard (2026-10-20): a kept run may start with an in-breath (or end with an exhale) that is
# bridged to the word by a < 60 ms dip. If the audio between the run edge and the first word's aligned onset
# (minus LEAD) is >= 80 ms and unvoiced (no pitch), it is breath -> the run starts at onset - LEAD instead.
from scipy.io import wavfile
_sr, _a = wavfile.read(f'{W}/src48k.wav'); _a = _a.astype(np.float32) / 32768
LEAD, TAILK = 0.06, 0.15
def voiced_frac(t0, t1):
    x = _a[int(t0 * _sr):int(t1 * _sr)]; n, h = int(0.03 * _sr), int(0.01 * _sr); v = k = 0
    for i in range(0, max(0, len(x) - n) + 1, h):
        f = x[i:i + n] - x[i:i + n].mean(); e = float((f ** 2).sum())
        if e < 1e-7: k += 1; continue
        r = np.correlate(f, f, 'full')[n - 1:]; r = r / r[0]
        k += 1; v += r[int(_sr / 400):int(_sr / 75)].max() > 0.5
    return v / k if k else 0.0
wsI = sorted((I(w['s']), I(w['e'])) for w in words)
nclamp = 0
for r in kept:
    inside = [(s, e) for s, e in wsI if min(r[1], e + I(0.12)) - max(r[0], s) > 0]
    if not inside: continue
    on, off = inside[0][0], max(e for s, e in inside)
    a2 = on - I(LEAD)
    if a2 - r[0] >= I(0.08) and voiced_frac(T(r[0]), T(a2)) < 0.3:
        r.append('in'); print(f'  BREATH in {T(r[0]):.3f}-{T(a2):.3f} ({(a2 - r[0]) * HOP * 1000:.0f} ms) before "{next(w["w"] for w in words if I(w["s"]) == on)}"'); r[0] = a2; nclamp += 1
    b2 = off + I(TAILK)
    if r[1] - b2 >= I(0.08) and voiced_frac(T(b2), T(r[1])) < 0.3:
        r.append('out'); print(f'  BREATH out {T(b2):.3f}-{T(r[1]):.3f} ({(r[1] - b2) * HOP * 1000:.0f} ms)'); r[1] = b2; nclamp += 1
print(f'  breath guard trimmed {nclamp} run edges')
iv = []
for k, r in enumerate(kept):
    a, b = r[0], r[1]
    nxt = kept[k + 1][0] if k + 1 < len(kept) else N - 1
    while 'out' not in r[2:] and b < min(nxt, r[1] + I(0.03)) and db[b] > SOFT: b += 1   # soft tail
    j = b                                                                  # released stop burst
    while j < min(nxt - 1, b + I(0.15)):
        if db[j] > BURST:
            b0 = j
            while j < N - 1 and db[j] > BURST: j += 1
            if j - b0 <= I(0.08) and (db[j:j + I(0.06)] < BURST).all(): b = j   # stop burst or a soft final fricative (th, s, f)
            break
        j += 1
    lo = iv[-1][1] if iv else 0
    if 'in' not in r[2:]:
        while a > max(lo, r[0] - I(0.03)) and db[a - 1] > SOFT: a -= 1     # soft onset (not after a trimmed breath)
    iv.append([a, b])
segs = [[iv[0][0], iv[0][1]]]; cuts = []
for a, b in iv[1:]:
    if (a - segs[-1][1]) * HOP >= GAP_T: cuts.append((segs[-1][1], a)); segs.append([a, b])
    else: segs[-1][1] = b
# the very first onset and the last word's natural decay: run out until the room is quiet (max 0.2 s before / 0.5 s after)
a0 = segs[0][0]
while a0 > 0 and segs[0][0] - a0 < I(0.2) and db[a0 - 1] > -52: a0 -= 1
segs[0][0] = a0
b1 = segs[-1][1]
while b1 < N - 1 and b1 - segs[-1][1] < I(0.5) and db[b1] > -52: b1 += 1
segs[-1][1] = b1
segs = [[round(max(0, T(a) - PAD), 4), round(min(T(N - 1), T(b) + PAD), 4)] for a, b in segs]
# keep windows (fixes.json 'keep'): a scripted pause/breath is kept whole -> the segments it touches are merged
# fixes.json = <project>/fixes.json, else the batch file <project>/../_closeout_tools/fixes.json keyed by project folder name
def pjson(P, fn):
    for f in (os.path.join(P, fn), os.path.join(os.path.dirname(P), '_closeout_tools', fn)):
        if os.path.exists(f):
            d = json.load(open(f, encoding='utf-8'))
            if os.path.basename(P) in d: return d[os.path.basename(P)]
            if f == os.path.join(P, fn): return d
    return {}
for ka, kb, *_ in pjson(os.path.dirname(os.path.abspath(W)), 'fixes.json').get('keep', []):
    hit = [k for k, (x, y) in enumerate(segs) if y >= ka - 0.05 and x <= kb + 0.05]
    if not hit: continue
    x, y = min(segs[hit[0]][0], ka), max(segs[hit[-1]][1], kb)
    segs = segs[:hit[0]] + [[round(x, 4), round(y, 4)]] + segs[hit[-1] + 1:]
    print(f'  KEEP window {ka}-{kb}: merged {len(hit)} segment(s) -> {x:.3f}-{y:.3f}')
# word-end guard (long-form): a final fricative ("enough", "truth") that the run ended before keeps its tail
for w in words:
    for k, (x, y) in enumerate(segs):
        if x <= w['s'] < y:
            if y < w['e'] + 0.02:
                nx = segs[k + 1][0] if k + 1 < len(segs) else T(N - 1)
                lim = min(w['e'] + 0.02, nx - 0.01); j = I(y)
                # the aligner stretched the word across a real pause ("it, | click"): its span reaches into the next
                # kept segment -> the word really starts there; extending would keep the in-breath (2026-10-22)
                if nx < w['e'] + 0.01: print(f"  tail skipped for {w['w']} (span reaches the next segment)"); break
                while j < I(lim) and db[j] > SOFT - 6: j += 1          # only while the tail is still audible
                if T(j) + 0.01 > y + 0.005:
                    print(f"  tail kept for {w['w']} +{(T(j) + 0.01 - y) * 1000:.0f} ms"); segs[k][1] = round(T(j) + 0.01, 4)
            break
# guard
keepmask = np.zeros(N, bool)
for a, b in segs: keepmask[I(a):I(b)] = True
for w in words:
    v = db[I(w['s']):I(w['e'])] > BURST; k = keepmask[I(w['s']):I(w['e'])]
    if v.sum() and (v & k).sum() < 0.9 * v.sum(): print(f"  GUARD: {w['w']} keeps only {(v & k).sum() / v.sum():.0%} of its voice")
mp, t = [], 0.0
for x, y in segs: mp.append(dict(src0=x, src1=y, out0=round(t, 4))); t += y - x
def to_out(x, side):
    for m in mp:
        if m['src0'] <= x <= m['src1']: return m['out0'] + x - m['src0']
    if side == 's': m = next(m for m in mp if m['src0'] > x); return m['out0']
    m = [m for m in mp if m['src1'] < x][-1]; return m['out0'] + m['src1'] - m['src0']
for w in words:
    w['cs'] = round(to_out(w['s'], 's'), 3); w['ce'] = round(max(w['cs'] + 0.03, to_out(w['e'], 'e')), 3)
json.dump(dict(pad=PAD, gap_t=GAP_T, segments=mp, duration=round(t, 4), words=words),
          open(f'{W}/cut_plan.json', 'w', encoding='utf-8'), indent=1)
print(f'{len(segs)} segments, {len(cuts)} cuts -> {t:.3f}s (source {N * HOP:.2f} s)   first {segs[0]}  last {segs[-1]}  longest seg {max(b - a for a, b in segs):.2f} s')
def near(x, before):
    c = [w for w in words if (w['s'] < T(x) + 0.05 if before else w['e'] > T(x) - 0.05)]
    return (c[-1] if before else c[0])['w']
for a, b in cuts: print(f'  ...{near(a, True):>12} |{(b - a) * HOP * 1000:5.0f} ms -> {2 * PAD * 1000:.0f} ms| {near(b, False)}...')
