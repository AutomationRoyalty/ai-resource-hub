# precise_cut: transcribe, align and cut a clip to the millisecond

The default cutter for reels. It replaces the silence-threshold jump cut (`build_jumpcuts.py` +
`clean_cut.py`) with a word-aware cut, and it hands back a millisecond transcript of the CUT that the
captions are built from. Adapted from the long-form tight-cut toolchain.

**How it works.** OpenAI Whisper API transcribes the clip phrase by phrase. ElevenLabs Forced
Alignment then times every word to the millisecond against the audio. You mark the bad takes in
`retakes.json`. The cut keeps only voiced audio that overlaps a kept word, trims every pause of
200 ms or more down to 15 ms of air each side, trims breaths, and guards word endings (+120 ms on
every word, plus an audible final s/t). Audio is joined sample-accurately with 4 ms fades (no
clicks); video is conformed frame by frame to the audio (sync error under half a frame, never
accumulates). Finally the words are re-aligned on the cut itself, so caption timing is exact.

## Requirements
- Python 3.10+ with `requirements.txt` (numpy, scipy, requests, openai; about 200 MB). Everything that
  runs a model goes through the two APIs; nothing runs locally.
- `ffmpeg` on PATH.
- Keys in the `.env` at the kit root (found by walking up from this folder; `REEL_ENV_FILE=<path>`
  overrides): `OPENAI_API_KEY` (Whisper) and `ELEVENLABS_API_KEY`. **The ElevenLabs key must have the
  `forced_alignment` permission**, or alignment fails with `401 missing_permissions`. A key made only
  for speech-to-text does not have it; edit the key's permissions in the ElevenLabs dashboard.

## Steps (`S` = this folder, `P` = the clip's cut folder, e.g. `videos/<slug>/working/<cid>/precise`)
Run every script with the venv's Python and `-I`.

| step | command | what it does |
|---|---|---|
| 1 | `python -I "S/prep.py" demo-cut.mp4 "P"` | folders, 48k + 16k source audio, 5 ms energy envelope |
| 2 | `python -I "S/transcribe_phrases.py" "P/work" "Brand Name, Product Name"` | Whisper API per phrase + ElevenLabs alignment → `work/words_raw.json`. 2nd arg = names to spell right |
| 3 | `python -I "S/show_words.py" "P/work"` | every phrase with word indices: read it and write `P/retakes.json` |
| 4 | write `P/retakes.json` (+ `P/fixes.json` if needed) | **the judgment step.** Keep the LAST take; drop false starts, restarts, repeats. Format in `retakes_example.json` / `fixes_example.json` |
| 4b | `python -I "S/qa_words.py" "P"` | flags stretched words (a hidden merged retake) and voice with no words |
| 5 | `python -I "S/build_words.py" "P"` | final source words (retakes out, spellings fixed) |
| 6 | `python -I "S/cut_plan_lf.py" "P/work"` | the cut plan (`--pad 15 --gap 200` ms are the defaults) |
| 7 | `python -I "S/check_leftovers.py" "P"` | should say `0 leftovers` (see note below) |
| 8 | `python -I "S/render_cut.py" "P/work" demo-cut.mp4 "P/cut.mp4"` | the cut mp4 (30 fps, crf 15) |
| 9 | `python -I "S/align_words.py" "P/work" "P/Transcript" "cut.mp4" "<title>"` | `Transcript/words.json` on the cut: `{w, s, e}` in SECONDS + csv/srt/md |
| 10 | `python -I "S/qa_output.py" "P"` | fresh Whisper pass on the cut: must report no repeats; agreement % |

Then convert for the caption tools:
```bash
python3 -c "import json; d=json.load(open('P/Transcript/words.json'))
json.dump([{'word':w['w'],'start':w['s'],'end':w['e']} for w in d['words']], open('P/cut-words.json','w'))"
```
and continue at WORKFLOW.md step 5 with `P/cut.mp4` and `P/cut-words.json` (lexicon pass, numerals,
`captions_plan.py --max-words 4`, composite).

**Leftovers that are fine.** Neighbouring phrases overlap slightly, so one spoken word can be
transcribed twice (e.g. `145:right?` and `146:right?`). Dropping the duplicate index leaves its audio
in, because it IS the kept word, and `check_leftovers.py` reports it. Confirm with step 10 (no
repeats) and move on. A leftover that is a real second take needs `patch_segments.py` or a `fixes.json`
`drop` window.

**Re-cut after a note:** edit `retakes.json` / `fixes.json`, then steps 5 to 10 again.

## Tested
API-only version re-run on the same excerpt in a clean venv with just `requirements.txt`: identical cut
points and word timings to the original run. 12 Nov 2026 on a 75 s excerpt of a talking-head source: 209 words, 1 retake, 75.0 s → 65.8 s
(25 joins), Whisper re-check 98.3 % agreement with no repeats, sibilant HF of the composited reel
within 0.5 dB of the source (`qa_reel.sh` PASS).
