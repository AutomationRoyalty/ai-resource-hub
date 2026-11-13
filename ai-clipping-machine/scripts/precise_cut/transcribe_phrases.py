"""Step 2: word-level transcript of the RAW recording, one phrase at a time (so retakes are never merged):
1) energy VAD (10 ms) -> speech islands; islands closer than 0.6 s join into one phrase (a retake almost always
   follows a longer pause); phrases longer than 28 s split at their quietest point
2) OpenAI Whisper API per phrase (temperature 0, word timestamps, short vocab prompt)
3) guard: drop words with no speech energy under them (breath hallucinations)
4) ElevenLabs Forced Alignment per phrase -> precise start/end
writes <work>/words_raw.json {duration, fps, phrases:[[s,e,text]], words:[{w,ws,we,p,phrase,s,e,fa}]} + phrases.txt
The vocab prompt = VOCAB below + this video's names ("extra vocab"); --vocab replaces the whole prompt. Keep it SHORT:
whisper repeats prompt words on noise blips ("Figma, Figma, ...") -> drop those phrases in retakes.json.
usage: python -I transcribe_phrases.py <project>/work ["extra vocab, comma separated"] [--vocab "<whole prompt>"]"""
import json, re, sys, warnings
import numpy as np
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from whisper_api import load_whisper
from align_api import align_many
from scipy.io import wavfile
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
args = sys.argv[1:]
VOCAB = 'Claude, Instagram, B-roll. '
if '--vocab' in args:
    k = args.index('--vocab'); VOCAB = args[k + 1] + ' '; del args[k:k + 2]
if not args: raise SystemExit(__doc__)
D = args[0]
VOCAB += args[1] if len(args) > 1 else ''
sr, wav = wavfile.read(f'{D}/cut16k.wav'); wav = wav.astype(np.float32) / 32768.0
N = len(wav); dur = N / sr
HOP = 160
fr = np.lib.stride_tricks.sliding_window_view(np.pad(wav, (200, 200)), 400)[::HOP]
db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
floor, peak = np.percentile(db, 5), np.percentile(db, 95)
thr = max(floor + 12, peak - 38)
sp = db > thr
d = np.diff(np.r_[0, sp.astype(int), 0]); isl = list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))
isl = [(a, b) for a, b in isl if b - a >= 6]
ph = []
for a, b in isl:
    if ph and a - ph[-1][1] < 60: ph[-1] = (ph[-1][0], b)
    else: ph.append((a, b))
final = []
for a, b in ph:
    while (b - a) * 0.01 > 28:
        lo, hi = a + 1200, min(b - 300, a + 2600)
        cut = lo + int(np.argmin(db[lo:hi])); final.append((a, cut)); a = cut
    final.append((a, b))
ph = final
print(f'dur {dur:.1f}s thr {thr:.1f} dB islands {len(isl)} phrases {len(ph)} vocab "{VOCAB.strip()}"', flush=True)

model = load_whisper()
PAD = 0.15
words, texts = [], []
WIN = [(max(0, a * 0.01 - PAD), min(dur, b * 0.01 + PAD)) for a, b in ph]
KW = dict(language='en', word_timestamps=True, temperature=0.0, condition_on_previous_text=False, initial_prompt=VOCAB)
if hasattr(model, 'transcribe_many'): RES = model.transcribe_many([wav[int(s0 * sr):int(s1 * sr)] for s0, s1 in WIN], **KW)
else: RES = (model.transcribe(wav[int(s0 * sr):int(s1 * sr)], **KW) for s0, s1 in WIN)
for pi, ((s0, s1), r) in enumerate(zip(WIN, RES)):
    texts.append([round(s0, 2), round(s1, 2), r['text'].strip()])
    for s in r['segments']:
        for w in s.get('words', []):
            words.append(dict(w=w['word'].strip(), ws=round(s0 + float(w['start']), 3), we=round(s0 + float(w['end']), 3), p=round(float(w.get('probability', 0)), 3), phrase=pi))
del model

def energy(t0, t1):
    i0, i1 = int(t0 * 100), max(int(t0 * 100) + 1, int(t1 * 100)); return db[i0:i1].max() if i1 > i0 else -99
kept = []
for w in words:
    if energy(w['ws'], w['we']) < thr - 6: print('DROP no-energy', w, flush=True); continue
    kept.append(w)
words = kept

def _win(pi, a, b, idx):
    s0, s1 = max(0, a * 0.01 - PAD), min(dur, b * 0.01 + PAD)
    return max(0, min(s0, words[idx[0]]['ws'] - 0.1)), min(dur, max(s1, words[idx[-1]]['we'] + 0.1))
print('alignment: ElevenLabs Forced Alignment API', flush=True)
JOBS = []
for pi, (a, b) in enumerate(ph):
    idx = [i for i, w in enumerate(words) if w['phrase'] == pi]
    if idx: s0, s1 = _win(pi, a, b, idx); JOBS.append((idx, s0, wav[int(s0 * sr):int(s1 * sr)]))
for (idx, s0, _), res in zip(JOBS, align_many([(x, [words[i]['w'] for i in idx]) for idx, s0, x in JOBS])):
    for i, r in zip(idx, res):
        if r: words[i].update(s=round(s0 + r[0], 3), e=round(s0 + r[1], 3), fa=round(r[2], 3))
for w in words:
    if 's' not in w: w['s'], w['e'], w['fa'] = w['ws'], w['we'], None
json.dump(dict(duration=dur, fps=30, phrases=texts, words=words), open(f'{D}/words_raw.json', 'w', encoding='utf-8'), indent=1)
with open(f'{D}/phrases.txt', 'w', encoding='utf-8') as f:
    for pi, (s0, s1, t) in enumerate(texts): f.write(f'P{pi:02d} {s0:7.2f}-{s1:7.2f}  {t}\n')
print('words', len(words), '| phrases written to phrases.txt (word indices: show_words.py)')
