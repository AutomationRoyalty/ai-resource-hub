"""Step 4: final SOURCE-timeline word list for the tight cut: words_raw.json minus retakes.json ranges minus fixes.json
'drop' windows, with fixes 'realign' windows replaced by force-aligned text (the kept take); split tokens merged
("$3"+",000", "2"+".0", "16"+"-year"+"-old"); spellings fixed (FIX below + fixes 'spell' [[regex, replacement]]);
a sentence a retake cut now starts on a lowercase word gets its capital back. Writes <work>/words_final.json [{w,s,e}].
Reads <project>/retakes.json + <project>/fixes.json (see the *_example.json files). The batch layout also works:
<batch root> <project name> with <batch root>/_closeout_tools/*.json keyed by project folder name.
usage: python -I build_words.py <project dir>"""
import json, os, re, sys
import numpy as np
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from align_api import align_one, fill_gaps
from scipy.io import wavfile
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

P = project(sys.argv[1:]); d = os.path.basename(P); W = os.path.join(P, 'work')
raw = json.load(open(f'{W}/words_raw.json', encoding='utf-8'))['words']
R = pjson(P, 'retakes.json'); drops = R.get('retakes', []) if isinstance(R, dict) else R
fx = pjson(P, 'fixes.json')
gone = set(i for a, b, *_ in drops for i in range(a, b + 1))
wins = [(a, b) for a, b, *_ in fx.get('drop', [])] + [(a, b) for a, b, *_ in fx.get('realign', [])]
words = [dict(w=w['w'], s=w['s'], e=w['e']) for i, w in enumerate(raw) if i not in gone and not any(a <= w['s'] < b for a, b in wins)]

if fx.get('realign'):
    sr, wav = wavfile.read(f'{W}/cut16k.wav'); wav = wav.astype(np.float32) / 32768
    print('alignment: ElevenLabs Forced Alignment API', flush=True)
    for a, b, text, *_ in fx['realign']:
        toks = text.split()
        res = fill_gaps(align_one(wav[int(a * sr):int(b * sr)], toks), 0.0, b - a)
        new = [dict(w=t, s=round(a + r[0], 3), e=round(a + r[1], 3)) for t, r in zip(toks, res)]
        print(f'  realign {a}-{b}: ' + ' '.join(f"{w['w']}@{w['s']:.2f}" for w in new))
        words += new
words.sort(key=lambda w: w['s'])
# merge split tokens
out = []
for w in words:
    t = w['w']
    if out and (re.match(r'^[,.]\d', t) or t == '%' or re.match(r'^-\w', t) or re.match(r'^&\w', t)):
        out[-1]['w'] += t; out[-1]['e'] = w['e']; continue
    out.append(dict(w))
# whisper's usual mishears (brands, course names, numbers); add per-video ones in fixes.json 'spell'
FIX = [(r'\bSAS\b', 'SaaS'), (r'\bSass\b', 'SaaS'), (r'\bImangaji\b', 'Iman Gadzhi'), (r'^Gaji', 'Gadzhi'), (r'^Fox$', 'Vox'),
       (r'\$2000\b', '$2,000'), (r'^1000$', '1,000'), (r'^Enter,$', 'Inter,'), (r'^slopped$', 'slop'), (r'^wear$', 'where'),
       (r'^Extra$', 'extra'), (r'\bTalking Head\b', 'talking head')]
FIX += [tuple(x[:2]) for x in fx.get('spell', [])]
for w in out:
    for a, b in FIX: w['w'] = re.sub(a, b, w['w'])
# 'Talking' 'Head' split across tokens
for i in range(len(out) - 1):
    if out[i]['w'] == 'Talking' and out[i + 1]['w'].startswith('Head'): out[i]['w'] = 'talking'; out[i + 1]['w'] = out[i + 1]['w'].replace('Head', 'head')
# a retake cut can start a sentence on a lowercase word ("both long form ...")
for i in range(1, len(out)):
    if re.search(r'[.?!]$', out[i - 1]['w']) and out[i]['w'][:1].islower(): out[i]['w'] = out[i]['w'][0].upper() + out[i]['w'][1:]
if out and out[0]['w'][:1].islower(): out[0]['w'] = out[0]['w'][0].upper() + out[0]['w'][1:]
json.dump(out, open(f'{W}/words_final.json', 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
print(f'{d}: {len(out)} words ({len(gone)} retake words dropped, {len(fx.get("drop", []))} drop / {len(fx.get("realign", []))} realign windows)')
print('  ' + ' '.join(w['w'] for w in out))
