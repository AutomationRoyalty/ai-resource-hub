"""OpenAI Whisper API (whisper-1) transcription for the cut scripts (transcribe_phrases.py, probe.py, qa_output.py).

Key: env OPENAI_API_KEY, else the repo-root .env (or REEL_ENV_FILE) with a line OPENAI_API_KEY=... (chmod 600).
Returns: {text, segments: [{start, end, text, words: [{word, start, end, probability}]}]}.
The API has no per-word probability: `probability` = exp(avg_logprob) of the word's segment.
Audio longer than CHUNK seconds is split at its quietest 10 ms near each boundary and sent in parallel
(the API caps uploads at 25 MB). Word timing precision comes from ElevenLabs Forced Alignment in the callers."""
import io, math, os, wave
from concurrent.futures import ThreadPoolExecutor
import numpy as np

SR = 16000
CHUNK = 300.0
WORKERS = 8   # parallel API requests
def _find_env():
    """REEL_ENV_FILE if set, else the first .env found walking up from this folder (the repo root .env)."""
    p = os.environ.get('REEL_ENV_FILE')
    if p: return os.path.expanduser(p)
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(d, '.env')): return os.path.join(d, '.env')
        up = os.path.dirname(d)
        if up == d: return os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        d = up


ENV_FILE = _find_env()


def _key():
    k = os.environ.get('OPENAI_API_KEY')
    if k: return k.strip()
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding='utf-8'):
            line = line.strip()
            if line.startswith('OPENAI_API_KEY='): return line.split('=', 1)[1].strip().strip('"\'')
    raise SystemExit(f'OpenAI Whisper API: no key. Put OPENAI_API_KEY=... in {ENV_FILE} (chmod 600) or the '
                     'environment.')


def _punctuate(seg):
    """The API's word tokens carry no punctuation (the transcript's sentence split needs it):
    copy each trailing , . ? ! ; : from the segment text onto the matching word. Ellipses ('...') are skipped."""
    import difflib, re
    norm = lambda t: re.sub(r"[^a-z0-9$%']", '', t.lower().replace('’', "'"))
    src = (seg.get('text') or '').split()
    ws = seg['words']
    sm = difflib.SequenceMatcher(a=[norm(w['word']) for w in ws], b=[norm(t) for t in src], autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            m = re.search(r'[.,?!;:]+$', src[blk.b + k]); w = ws[blk.a + k]
            if m and '..' not in m.group(0) and not re.search(r'[.,?!;:]$', w['word']): w['word'] += m.group(0)


def _wav_bytes(a):
    a = np.clip(np.asarray(a, dtype=np.float32), -1.0, 1.0)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype('<i2').tobytes())
    return buf.getvalue()


class APIWhisper:
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=_key(), max_retries=8, timeout=180)

    def _one(self, a, language='en', initial_prompt=None, temperature=0.0, **_):
        a = np.asarray(a, dtype=np.float32)
        if len(a) < int(0.2 * SR): a = np.pad(a, (0, int(0.2 * SR) - len(a)))
        kw = dict(model='whisper-1', file=('audio.wav', _wav_bytes(a), 'audio/wav'), response_format='verbose_json',
                  timestamp_granularities=['word', 'segment'], language=language or 'en', temperature=temperature or 0.0)
        if initial_prompt and initial_prompt.strip(): kw['prompt'] = initial_prompt.strip()
        r = self.client.audio.transcriptions.create(**kw)
        segs = [dict(start=float(s.start), end=float(s.end), text=s.text,
                     avg_logprob=float(getattr(s, 'avg_logprob', 0) or 0),
                     no_speech_prob=float(getattr(s, 'no_speech_prob', 0) or 0), words=[]) for s in (r.segments or [])]
        if not segs:
            segs = [dict(start=0.0, end=len(a) / SR, text=r.text or '', avg_logprob=0.0, no_speech_prob=0.0, words=[])]
        for w in (r.words or []):
            ws, we = float(w.start), float(w.end); mid = (ws + we) / 2
            seg = min(segs, key=lambda s: 0 if s['start'] <= mid <= s['end'] else min(abs(mid - s['start']), abs(mid - s['end'])))
            seg['words'].append(dict(word=' ' + w.word.strip(), start=ws, end=we,
                                     probability=round(math.exp(min(0.0, seg['avg_logprob'])), 3)))
        for seg in segs: _punctuate(seg)
        return dict(text=r.text or '', segments=segs, language=language or 'en')

    def transcribe(self, audio, **kw):
        a = np.asarray(audio, dtype=np.float32); n = len(a)
        if n <= CHUNK * SR * 1.2: return self._one(a, **kw)
        fe = (a[:n // 160 * 160].reshape(-1, 160) ** 2).mean(1)
        cuts, t = [0], CHUNK
        while t < n / SR - CHUNK * 0.2:
            lo, hi = int((t - 15) * 100), int(min(n / SR, t + 15) * 100)
            c = (lo + int(np.argmin(fe[lo:hi]))) * 160
            cuts.append(c); t = c / SR + CHUNK
        cuts.append(n)
        parts = list(zip(cuts[:-1], cuts[1:]))
        with ThreadPoolExecutor(WORKERS) as ex:
            rs = list(ex.map(lambda p: self._one(a[p[0]:p[1]], **kw), parts))
        segs, texts = [], []
        for (c0, _), r in zip(parts, rs):
            off = c0 / SR; texts.append(r['text'].strip())
            for s in r['segments']:
                s['start'] += off; s['end'] += off
                for w in s['words']: w['start'] += off; w['end'] += off
                segs.append(s)
        return dict(text=' '.join(texts), segments=segs, language=kw.get('language', 'en'))

    def transcribe_many(self, audios, **kw):
        done = [0]
        def one(a):
            r = self.transcribe(a, **kw); done[0] += 1
            if done[0] % 50 == 0: print(f'  whisper API: {done[0]}/{len(audios)} phrases', flush=True)
            return r
        with ThreadPoolExecutor(WORKERS) as ex: return list(ex.map(one, audios))


def load_whisper():
    print('whisper: OpenAI API (whisper-1)', flush=True)
    return APIWhisper()
