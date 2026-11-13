"""Step 1 of the tight cut: project folders, source audio (48 kHz mono + 16 kHz mono) and the 5 ms energy envelope
(float32 dBFS, 15 ms window) that cut_plan_lf.py reads. work/cut16k.wav = the SOURCE at 16 kHz (transcribe_phrases /
build_words / probe read it); render_cut.py later writes work/cut/cut16k.wav = the CUT at 16 kHz.
<project dir> = the video's tight-cut folder, e.g. "<video folder>/Tight Cut" (created if missing).
usage: python -I prep.py <source.mp4> <project dir>"""
import os, subprocess, sys
import numpy as np
from scipy.io import wavfile
if len(sys.argv) < 3: raise SystemExit(__doc__)
SRC, P = sys.argv[1], sys.argv[2]
if not os.path.isfile(SRC): raise SystemExit(f'source not found: {SRC}')
W = os.path.join(P, 'work')
for d in (P, W, os.path.join(P, 'Transcript'), os.path.join(W, 'cut')):
    os.makedirs(d, exist_ok=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', SRC, '-vn', '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', f'{W}/src48k.wav'], check=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', SRC, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', f'{W}/cut16k.wav'], check=True)
sr, a = wavfile.read(f'{W}/src48k.wav'); a = a.astype(np.float32) / 32768
hop, win = 240, 720  # 15 ms centred window, 5 ms hop
pad = np.pad(a, (win // 2, win))
fr = np.lib.stride_tricks.sliding_window_view(pad, win)[::hop][:len(a) // hop + 2]
db = (20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)).astype(np.float32)
np.save(f'{W}/db5ms.npy', db)
print(os.path.basename(os.path.normpath(P)), f'{len(a) / sr:.2f} s', 'db5ms', len(db), 'p5/p50/p95', *np.percentile(db, [5, 50, 95]).round(1))
