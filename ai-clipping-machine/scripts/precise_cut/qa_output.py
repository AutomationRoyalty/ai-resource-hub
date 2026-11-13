"""Step 9: QA the rendered tight cut: a fresh Whisper API pass on the cut (work/cut/cut16k.wav), then
- any 3-word sequence spoken twice within 10 s (a retake fragment that survived; scripted repeats are fine - check each
  against his script)
- word-level diff vs Transcript/words.json (what the fresh pass hears differently: a stretched word hiding a take)
usage: python -I qa_output.py <project dir>"""
import difflib, json, os, re, sys, warnings
import numpy as np
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from whisper_api import load_whisper
from scipy.io import wavfile
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if len(sys.argv) < 2: raise SystemExit(__doc__)
P = os.path.normpath(sys.argv[1])
sr, wav = wavfile.read(f'{P}/work/cut/cut16k.wav'); wav = wav.astype(np.float32) / 32768
m = load_whisper()
r = m.transcribe(wav, language='en', word_timestamps=True, temperature=0.0, condition_on_previous_text=False)
fresh = [(w['word'].strip(), float(w['start'])) for s in r['segments'] for w in s.get('words', [])]
norm = lambda t: re.sub(r"[^a-z0-9$']", '', t.lower())
fw = [(norm(w), t) for w, t in fresh if norm(w)]
reps = []
for i in range(len(fw) - 2):
    g = tuple(x[0] for x in fw[i:i + 3])
    for j in range(i + 1, len(fw) - 2):
        if fw[j][1] - fw[i][1] > 10: break
        if tuple(x[0] for x in fw[j:j + 3]) == g and j >= i + 3: reps.append((' '.join(g), round(fw[i][1], 1), round(fw[j][1], 1)))
print(os.path.basename(P), '| repeats within 10 s:', reps if reps else 'none')
ours = [norm(w['w']) for w in json.load(open(f'{P}/Transcript/words.json', encoding='utf-8'))['words']]
ours = [x for x in ' '.join(ours).split() if x]
theirs = [x[0] for x in fw]
sm = difflib.SequenceMatcher(a=ours, b=theirs, autojunk=False)
diffs = [(op, ' '.join(ours[a0:a1]), ' '.join(theirs[b0:b1])) for op, a0, a1, b0, b1 in sm.get_opcodes() if op != 'equal']
print(f'  agreement {sm.ratio() * 100:.1f} %; {len(diffs)} differences:', diffs[:25])
