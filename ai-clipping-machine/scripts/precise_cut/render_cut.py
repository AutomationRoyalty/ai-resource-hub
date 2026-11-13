"""Step 7: render the tight cut from cut_plan.json (the source must be the synced, constant-frame-rate recording).
Audio: sample-accurate segment concat (48 kHz stereo) with 4 ms fades at every join (no clicks) -> work/cut_audio.wav
and work/cut/cut16k.wav (align_words.py + qa_output.py read it).
Video: conformed per output frame -> nearest source frame (sync error <= half a frame, never accumulates);
work/cut_frames.json = {frames, runs}: each run = one kept segment's source frames, so every run start after the first
is a jump cut (make_words.py data turns them into <prefix>_takes.json). h264 crf 15 + AAC 320k.
usage: python -I render_cut.py <project>/work <source.mp4> "<project>/<Title> - TIGHT CUT.mp4" [--fps 30]"""
import json, math, os, subprocess, sys
import numpy as np
from scipy.io import wavfile
args = sys.argv[1:]
FPS = 30
if '--fps' in args: k = args.index('--fps'); FPS = int(args[k + 1]); del args[k:k + 2]
if len(args) < 3: raise SystemExit(__doc__)
W, SRC, OUT = args[:3]
plan = json.load(open(f'{W}/cut_plan.json', encoding='utf-8'))
SR = 48000
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', SRC, '-vn', '-ac', '2', '-ar', str(SR), '-c:a', 'pcm_s16le', f'{W}/src_st.wav'], check=True)
sr, a = wavfile.read(f'{W}/src_st.wav'); a = a.astype(np.float32)
fade = int(0.004 * SR); ramp = np.linspace(0, 1, fade)[:, None]
parts = []
for m in plan['segments']:
    p = a[int(round(m['src0'] * SR)):int(round(m['src1'] * SR))].copy()
    p[:fade] *= ramp; p[-fade:] *= ramp[::-1]; parts.append(p)
aud = np.concatenate(parts)
nfr = math.ceil(len(aud) / SR * FPS)
aud = np.concatenate([aud, np.zeros((int(round(nfr / FPS * SR)) - len(aud), 2), np.float32)])
wavfile.write(f'{W}/cut_audio.wav', SR, np.clip(aud, -32768, 32767).astype(np.int16))
os.makedirs(f'{W}/cut', exist_ok=True)  # align_words.py + qa_output.py read the cut at 16 kHz mono
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{W}/cut_audio.wav', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', f'{W}/cut/cut16k.wav'], check=True)
# video frame map
segs = plan['segments']; runs = []
for k in range(nfr):
    t = (k + 0.5) / FPS                                   # sample the middle of each output frame
    m = next((m for m in segs if m['out0'] <= t < m['out0'] + m['src1'] - m['src0']), segs[-1])
    sf = int(math.floor(k + 0.5 + (m['src0'] - m['out0']) * FPS + 1e-6))   # constant integer offset per segment
    if runs and runs[-1][1] + 1 == sf: runs[-1][1] = sf
    else: runs.append([sf, sf])
if sum(b - a + 1 for a, b in runs) != nfr or len(runs) != len(segs):
    raise SystemExit(f'frame map mismatch: {len(runs)} frame runs for {len(segs)} segments (a segment shorter than a frame, or two segments '
                     f'landing on consecutive source frames) - merge or drop it with patch_segments.py. runs: {runs}')
def _tree(t):   # balanced (a+b) nesting: a flat 200+ term sum fails in ffmpeg's parser ("Cannot allocate memory")
    return t[0] if len(t) == 1 else f'({_tree(t[:len(t) // 2])}+{_tree(t[len(t) // 2:])})'
expr = _tree([rf'between(n\,{a}\,{b})' for a, b in runs])
json.dump(dict(frames=nfr, runs=runs), open(f'{W}/cut_frames.json', 'w'), indent=0)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', SRC, '-i', f'{W}/cut_audio.wav',
                '-filter_complex', f"[0:v]select='{expr}',setpts=N/{FPS}/TB[v]", '-map', '[v]', '-map', '1:a',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-pix_fmt', 'yuv420p', '-r', str(FPS),
                '-c:a', 'aac', '-b:a', '320k', '-movflags', '+faststart', OUT], check=True)
print('frames', nfr, 'runs', len(runs), 'audio s', round(len(aud) / SR, 3))
