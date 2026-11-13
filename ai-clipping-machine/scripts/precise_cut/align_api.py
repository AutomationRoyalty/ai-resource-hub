"""ElevenLabs Forced Alignment API: precise word timing for transcribe_phrases.py, build_words.py and align_words.py.

API: POST https://api.elevenlabs.io/v1/forced-alignment, header xi-api-key, multipart `file` (audio) + `text`
(plain string). Response: characters [{text, start, end}], words [{text, start, end, loss}], loss (seconds).
Key: env ELEVENLABS_API_KEY, else the repo-root .env (or REEL_ENV_FILE) (ELEVENLABS_API_KEY=...).

align_one(audio16k, words) -> [(start, end, score) | None per input word], seconds relative to the audio start;
score = exp(-loss) (higher = better). Mapping back to the caller's words:
by character index when the API returns one character per input character, else by word order, else difflib."""
import difflib, io, math, os, re, time, wave
from concurrent.futures import ThreadPoolExecutor
import numpy as np

SR = 16000
URL = 'https://api.elevenlabs.io/v1/forced-alignment'
WORKERS = 4   # parallel API requests
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
_KEY = None


def _key():
    global _KEY
    if _KEY: return _KEY
    k = os.environ.get('ELEVENLABS_API_KEY')
    if not k and os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding='utf-8'):
            if line.strip().startswith('ELEVENLABS_API_KEY='): k = line.split('=', 1)[1].strip().strip('"\'')
    if not k:
        raise SystemExit(f'ElevenLabs alignment API: no key. Put ELEVENLABS_API_KEY=... in {ENV_FILE} (chmod 600) '
                         'or the environment.')
    _KEY = k.strip(); return _KEY


def _wav_bytes(a):
    a = np.clip(np.asarray(a, dtype=np.float32), -1.0, 1.0)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * 32767).astype('<i2').tobytes())
    return buf.getvalue()


def _post(audio, text):
    import requests
    data = _wav_bytes(audio)
    for attempt in range(8):
        try:
            r = requests.post(URL, headers={'xi-api-key': _key()}, data={'text': text},
                              files={'file': ('audio.wav', data, 'audio/wav')}, timeout=180)
        except requests.RequestException as e:
            err = str(e); time.sleep(min(30, 2 ** attempt)); continue
        if r.status_code == 200: return r.json()
        err = f'{r.status_code} {r.text[:300]}'
        if r.status_code in (429, 500, 502, 503, 504): time.sleep(min(30, 2 ** attempt)); continue
        raise RuntimeError(f'ElevenLabs forced alignment failed: {err}')
    raise RuntimeError(f'ElevenLabs forced alignment failed after retries: {err}')


def _norm(t):
    return re.sub(r"[^a-z0-9']", '', t.lower().replace('’', "'"))


def align_one(audio, words):
    words = [w for w in words]
    if not words: return []
    text = ' '.join(words)
    j = _post(audio, text)
    chars, rw = j.get('characters') or [], j.get('words') or []
    out = [None] * len(words)
    # word scores from the API words (by order) when the counts agree
    rw_tok = [w for w in rw if w.get('text', '').strip()]
    loss_by_word = [float(w.get('loss', 0) or 0) for w in rw_tok] if len(rw_tok) == len(words) else None
    # 1) character index map (with or without the spaces)
    cmap = None
    if len(chars) == len(text): cmap = list(range(len(text)))
    elif len(chars) == len(text.replace(' ', '')):
        cmap, k = [], 0
        for ch in text:
            cmap.append(None if ch == ' ' else k); k += ch != ' '
    if cmap is not None:
        pos = 0
        for i, w in enumerate(words):
            idx = [cmap[p] for p in range(pos, pos + len(w)) if cmap[p] is not None]
            pos += len(w) + 1
            if not idx: continue
            st, en = float(chars[idx[0]]['start']), float(chars[idx[-1]]['end'])
            sc = math.exp(-loss_by_word[i]) if loss_by_word else math.exp(-float(j.get('loss', 0) or 0))
            out[i] = (st, en, sc)
        return out
    # 2) word order
    if len(rw_tok) == len(words):
        return [(float(w['start']), float(w['end']), math.exp(-float(w.get('loss', 0) or 0))) for w in rw_tok]
    # 3) difflib on normalised tokens
    sm = difflib.SequenceMatcher(a=[_norm(w) for w in words], b=[_norm(w['text']) for w in rw_tok], autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            w = rw_tok[blk.b + k]
            out[blk.a + k] = (float(w['start']), float(w['end']), math.exp(-float(w.get('loss', 0) or 0)))
    return out


def fill_gaps(res, t0, t1):
    """Interpolate None entries between their aligned neighbours (callers that need a time for every word)."""
    n = len(res); out = list(res)
    for i in range(n):
        if out[i] is None:
            prev = next((out[k][1] for k in range(i - 1, -1, -1) if out[k]), t0)
            nxt = next((out[k][0] for k in range(i + 1, n) if out[k]), t1)
            out[i] = (prev, max(prev, nxt), 0.0)
    return out


def align_many(jobs, workers=None):
    """jobs = [(audio16k, [word, ...]), ...] -> [align_one result, ...] in order, `workers` requests at a time."""
    done = [0]
    def one(job):
        r = align_one(*job); done[0] += 1
        if done[0] % 50 == 0: print(f'  alignment API: {done[0]}/{len(jobs)}', flush=True)
        return r
    with ThreadPoolExecutor(workers or WORKERS) as ex: return list(ex.map(one, jobs))
