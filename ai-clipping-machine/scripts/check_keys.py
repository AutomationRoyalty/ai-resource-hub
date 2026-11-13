"""Test both API keys with a 3-second spoken clip, using the same code the cutter uses.
Prints a plain-language fix for each kind of failure. Exit 1 if either key fails."""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'precise_cut'))
import numpy as np
from scipy.io import wavfile

tmp = tempfile.mkdtemp()
aiff, wav = os.path.join(tmp, 't.aiff'), os.path.join(tmp, 't.wav')
subprocess.run(['say', '-o', aiff, 'Hello, this is a quick test of the reel workflow.'], check=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', aiff, '-ac', '1', '-ar', '16000', wav], check=True)
_, a = wavfile.read(wav)
audio = a.astype(np.float32) / 32768
ok = True

# OpenAI (transcription)
try:
    from whisper_api import load_whisper
    text = load_whisper().transcribe(audio, language='en')['text'].strip()
    print(f'  OpenAI key works. It heard: "{text}"')
except SystemExit:
    print('  OpenAI key is missing from .env.'); ok = False
except Exception as e:
    msg = str(e).lower(); ok = False
    if 'invalid_api_key' in msg or 'incorrect api key' in msg or '401' in msg:
        print('  OpenAI key is wrong. Copy it again from platform.openai.com (API keys) into .env.')
    elif 'quota' in msg or 'billing' in msg or '429' in msg:
        print('  OpenAI key works, but the account has no credit. Add billing at platform.openai.com (Billing).')
    else:
        print(f'  OpenAI test failed: {e}')

# ElevenLabs (word timing)
try:
    from align_api import align_one
    res = align_one(audio, 'Hello, this is a quick test of the reel workflow.'.split())
    if not any(res): raise RuntimeError('no words aligned')
    print(f'  ElevenLabs key works. Timed {sum(1 for r in res if r)} words.')
except SystemExit:
    print('  ElevenLabs key is missing from .env.'); ok = False
except Exception as e:
    msg = str(e).lower(); ok = False
    if 'forced_alignment' in msg or 'missing_permissions' in msg:
        print('  ElevenLabs key is missing the "Forced Alignment" permission. On elevenlabs.io, open your\n'
              '  API Keys page, edit this key, and allow Forced Alignment and Speech to Text.\n'
              '  Then run setup again.')
    elif '401' in msg:
        print('  ElevenLabs key is wrong. Copy it again from your API Keys page on elevenlabs.io into .env.')
    elif 'quota' in msg or 'credits' in msg or '402' in msg:
        print('  ElevenLabs key works, but the account is out of credits. Check your plan at elevenlabs.io.')
    else:
        print(f'  ElevenLabs test failed: {e}')

sys.exit(0 if ok else 1)
