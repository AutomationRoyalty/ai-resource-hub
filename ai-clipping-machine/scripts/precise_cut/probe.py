"""Step 3b: re-transcribe small SOURCE windows with no prompt (and each voiced island alone) to see what whisper skipped
or merged (a LONG word from qa_words.py, a repeated sentence opener, a gap with voice). Times = source seconds.
usage: python -I probe.py <project dir> '[[t0, t1], ...]'
       python -I probe.py <batch root> '{"<project name>": [[t0, t1], ...], ...}'   (batch layout)"""
import json, os, sys, warnings
import numpy as np
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from whisper_api import load_whisper
from scipy.io import wavfile
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if len(sys.argv) < 3: raise SystemExit(__doc__)
E, J = sys.argv[1], json.loads(sys.argv[2])
J = {os.path.join(E, k): v for k, v in J.items()} if isinstance(J, dict) else {E: J}
model = load_whisper()
for P, wins in J.items():
    d = os.path.basename(os.path.normpath(P))
    sr, wav = wavfile.read(f'{P}/work/cut16k.wav'); wav = wav.astype(np.float32) / 32768
    db = np.load(f'{P}/work/db5ms.npy')
    for t0, t1 in wins:
        r = model.transcribe(wav[int(t0 * sr):int(t1 * sr)], language='en', word_timestamps=True, temperature=0.0, condition_on_previous_text=False)
        ws = [f"{w['word'].strip()}@{t0 + w['start']:.2f}" for s in r['segments'] for w in s.get('words', [])]
        print(f'[{d}] {t0}-{t1}: ' + ' '.join(ws))
        # each voiced island alone
        core = db[int(t0 / 0.005):int(t1 / 0.005)] > -40
        dd = np.diff(np.r_[0, core.astype(int), 0]); st, en = np.where(dd == 1)[0], np.where(dd == -1)[0]
        isl = []
        for a, b in zip(st, en):
            if isl and a - isl[-1][1] < 30: isl[-1][1] = b
            else: isl.append([a, b])
        for a, b in isl:
            a_, b_ = t0 + a * 0.005, t0 + b * 0.005
            if b_ - a_ < 0.12: continue
            seg = wav[int(max(0, a_ - 0.1) * sr):int((b_ + 0.1) * sr)]
            rr = model.transcribe(seg, language='en', temperature=0.0, condition_on_previous_text=False)
            print(f'    island {a_:7.2f}-{b_:7.2f}: {rr["text"].strip()!r}')
