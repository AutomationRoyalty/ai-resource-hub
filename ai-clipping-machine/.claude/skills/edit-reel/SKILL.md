---
name: edit-reel
description: >-
  Turn a long video (+ a recorded CTA) into a branded 9:16 Instagram Reel for your
  brand. Use for ANY reel/short-form video editing task in this repo: cutting a demo window,
  jump-cutting dead air, compositing the bar layout + headline + burned captions, prepping the
  CTA face clip, and concatenating to the final <slug>.mp4. Follow this whenever asked to edit,
  cut, caption, or assemble a reel/ad video.
---

# Edit a reel (video editing)

> **The brand rules in this skill are a default house style** (black background, white Montserrat
> captions, Instagram safe zones). To change the look, ask Claude to update this file.

**Source of truth: `docs/WORKFLOW.md` — read it
before editing any video.** The locked brand spec and standing gotchas below are authoritative and OVERRIDE anything stale
in WORKFLOW.md.
This skill is the operational index; those two docs are the detail.

## When to use
Editing/cutting/captioning/assembling a reel or ad — long video → branded 9:16 reel, or grafting
a recorded CTA onto a demo. (Swapping an existing spoken CTA with zero slip frames is the `clean-cta-swap` skill.)

## A video lives in `videos/<slug>/`
Fixed sub-layout — `source/` (git-ignored raw), `captions/` (words.json → captions.json → .ass),
`working/` (intermediate renders + jump-cut plans), `config.md` (exact params for THIS video),
final `<slug>.mp4` at the root. Read an existing `config.md` as the template for a new one.
Reusable logic lives at the folder root: `scripts/` and `fonts/`.

## Pipeline (scripts in `scripts/`)
1. `yt-dlp` the source at full 1080p (keep yt-dlp current or it silently drops to 360p).
2. `ffmpeg` cut the demo window.
3. **Precise cut (default): `scripts/precise_cut/`** (full steps in its `README.md`). Whisper API
   transcribes the clip, ElevenLabs Forced Alignment times every word to the ms, you mark bad takes in
   `retakes.json` (keep the LAST take), then the cut keeps only voiced audio overlapping kept words,
   trims pauses of 200 ms or more to 15 ms each side, trims breaths, guards word endings, and joins
   audio sample-accurately with 4 ms fades. `align_words.py` re-times the words on the CUT, so the
   captions come from `Transcript/words.json` (seconds) with no remapping. Needs `OPENAI_API_KEY`
   + an `ELEVENLABS_API_KEY` that has the `forced_alignment` permission, and the precise_cut venv.
   Fallback when the APIs are unavailable: `build_jumpcuts.py` + **`clean_cut.py`** (`--threshold
   -30 --pad 0.2`). **Never cut with `select`/`setpts`** (stray frames + click per cut).
   `batch_reels.py` still uses the fallback path; it is not wired to precise_cut yet.
4. Lexicon pass → `normalize_numbers.py` → `captions_plan.py` on the cut words (`--max-words 4` per
   standing caption rule; `--emphasis "a|b"` flags big-center lines).
5. `ffmpeg` composite: bar layout (video 1080×608 at y=690) + headline + captions
   (`gen_fullframe_captions_ass.py` bakes the safe-zone: SemiBold fs60 / emphasis fs70 /
   MarginL/R=140 / WrapStyle=0).
6. Prep the CTA face clip: ElevenLabs STT + CTA caption gen; **tonemap HDR→SDR**
   (`tonemap=hable:desat=0`, npl=100) — iPhone clips are HLG/HDR; never deliver HDR (blows out
   skin). No saturation boost.
7. `ffmpeg concat` demo + CTA → `videos/<slug>/<slug>.mp4`. Update `config.md` with the params used.

## Locked brand spec (do not deviate unless asked)
1080×1920 / 9:16 / 30fps, H.264 yuv420p, AAC stereo 44.1k · pure black `#000000` bg, white
`#FFFFFF` text, no accent colors · Montserrat (captions SemiBold, hero/emphasis ExtraBold) ·
jump-cut dead air · no music by default · **Meta safe zone for BOTH headline and captions**:
headline ≤ ~fs62 in a 900px centered box (clear top ~220px, ~90px each side); captions ~4
words/line, centered, MarginL/R=140, clear of the right action rail.

## Non-negotiable gotchas (standing rules)
- **`drawtext` + `%` renders NOTHING** under default expansion → always `:expansion=none` on
  headline drawtext.
- **Never `select`/`setpts` to cut — use `clean_cut.py`** (frame-accurate, click-free).
- **Trailing sibilants:** precise_cut protects them by design (+120 ms after each aligned word end and
  an audible final-fricative guard); verify with `qa_reel.sh <reel> <source>` on the PRE-master
  render (mastering raises HF and skews the comparison). On the fallback path:
- **Trailing-sibilant rule: jump-cut with `--threshold -30 --pad 0.2`** — at −25dB/0.12 the
  low-energy tail of words ending in "s" reads as silence and gets clipped at every cut.
  **Noisy screen-rec caveat:** if the source room-tone floor is high (~−28dB), −30 barely cuts
  (keeps everything) AND sibilants share the −25…−30dB band with the pauses — you can't split them
  by threshold. Then use a bigger pad on −25 (e.g. `--threshold -25 --pad 0.20`, which keeps ~0.2s
  of each word-tail) or true word-safe clamping. Verify: the new cut's HF (>6kHz) content should
  match the RAW source's, not the tight −25/0.12 render's.
- **Speed-up must re-assert 30fps**: `setpts=PTS/1.2` → follow with `fps=30`/`-r 30`, pair with
  `atempo=1.2`.
- **Coherence check before delivery**: watch the WHOLE cut; never cut off the payoff (the last
  item of a list, the concluding thought). Pick the OUT point at the end of the idea.
- **Brand terms:** STT often mishears your product/brand name; fix it before rendering.
- **Caption lexicon (your own, growing):** `caption_lexicon.json` — word fixes
  (e.g. a misheard product name → its correct spelling, …) + adjacent-word merges ("many chat"→"ManyChat"). Apply it
  to every reel's caption words after STT/auto-subs, punctuation-aware. Add new mis-hearings to
  the file (and push) whenever one is spotted.
- **Numerals, never number words (standing rule):** run `scripts/normalize_numbers.py`
  **right after the lexicon pass**, on the same `[{word,start,end}]` list —
  `from normalize_numbers import normalize; words = normalize(words)`. It merges the tokens of a
  spelled-out number into one numeral token over the same time span: "twenty-three percent"→**23%**,
  "sixteen percent"→**16%**, "twenty leads"→**20 leads**, "two years"→**2 years**, "twenty-four
  seven"→**24/7**, "one hundred K"→**100k**, "five hundred dollars"→**$500**. Leaves "a dozen", ordinals and a bare pronoun "one" alone. Applies to
  every burned text layer, not just captions. **Re-check line grouping after the pass** — digits are
  much shorter than the words they replace.
- **Word-safe cuts:** after silence-detect, clamp every keep-segment end so it never lands inside
  a word — extend past the word's estimated acoustic end (word timings are available; est ≈
  0.07s/char, 0.25–1.0s) before cutting. Silence thresholds alone WILL clip word tails.
- **Speech loudness: −6…−12 dB throughout the final reel** — last audio step is always a
  mastering pass: `loudnorm=I=-14:TP=-6:LRA=9` on the voice, music bed shifted by the SAME gain
  (keep the approved ratio), then `alimiter=limit=0.501:level=false` (−6 dB ceiling) after the
  mix. Raw YouTube/screen-rec voice is ~−26 LUFS — never ship unmastered. Match CTA loudness to
  the demo before the join.
- ffmpeg 7.1: step-5 composite may need `,null[out]` on the fontsdir label chain.

## Ending fix — reel that ends on the demo (no CTA to mask it)
**Runnable:** `scripts/ending_fix.sh <demo-comp.mp4> <split_sec> <speed> <out.mp4> [music.mp3] [music_start_sec]`
(tested; does all of the below — split, normal-speed final sentence, adaptive boost, push-in tail,
optional music bed). Only `split_sec` needs judgment; the rest is automatic.

When an appended CTA is removed, the reel now ends on the demo and the last words get exposed. If
the final word is soft/rushed (sped-up) or the tail is a frozen frame, it reads as "cut off." Fix
per reel (work from the **pre-speed composite** `demo-comp` — voice-only, captions/headline burned):
1. Find the **last clean acoustic pause** before the final sentence with `silencedetect` — NOT from
   the word JSON (it's start-only; inter-word gaps read as 0). Split there.
2. Keep the body sped (approved speed); play the **final sentence at NORMAL speed** so the payoff
   lands. **Splice with `trim`/`atrim` inside the filtergraph — NEVER `-t`** (an output-side `-t`
   while speeding leaves the whole clip → the tail plays TWICE). Seam must sit in the detected pause.
3. **Final-word volume: default is NO boost.** A naturally-soft trailing word ("…at once") should
   land at its own level — that's how it was said. Boosting it backfires three ways: it makes the
   word **louder-than-usual**, it **amplifies the noise floor**, and any gain change *within* the
   word (a hard gate OR a ramp) **swells/clicks** and reads as a glitch. First make the word
   *survivable* — **fix clipped sibilants** (re-cut −25/pad 0.20) so it isn't truncated, keep it at
   normal speed, add the push-in — then leave the level alone. Only if it's genuinely inaudible, opt
   in to a small **uniform** lift across the whole final sentence (`ending_fix.sh` env `MAXBOOST=3`;
   Part B is bounded by silence so a constant gain has no click) — never a within-word ramp.
4. End on a **gentle push-in (zoompan) on the last frame of the speaker** — not a `tpad` freeze
   (reads as a cut) and not the raw source's next shot (it may cut to B-roll right after the word).
5. Verify on the waveform: final word present + audible, spoken ONCE (no duplicate), completes
   before the clip ends; seam in a pause.

## Swap a burned headline without re-compositing
The headline sits on the black top band, so cover the old text with `drawbox=...:color=black:t=fill`
over that band and redraw with `drawtext` — use **`textfile=`** (not inline `text=`) to avoid
quoting errors. One re-encode pass; the video band + captions are untouched.

## Pre-delivery QA (run every reel)
**Runnable:** `scripts/qa_reel.sh <reel.mp4> [source_or_democut.mp4]` — checks
1080×1920/30/yuv420p, **exactly one audio stream** (2 streams = a player stacks them / "two audios"),
aac 44.1k stereo, final word audible (≥ −14 dB), a clean tail beat, loudness, and — with the source
as arg 2 — **sibilant HF preservation** (reel's >6.5 kHz energy within 3 dB of the source). Then still
do the manual watch: payoff intact, final word spoken ONCE (no duplicate), no frozen tail, safe-zone.

## Per-video config carries the editorial choices (not this skill)
Headline text + size (e.g. fs47 for a long headline), emphasis phrases, IN/OUT windows, speed, and the **music bed**
live in each reel's `config.md` — read it as the template. Use only music licensed for
commercial use (a copyrighted track can get the reel muted or flagged), and always keep a
**clean (no-music)** cut alongside. Pass the mp3 (+ start offset) to `ending_fix.sh` to lay a bed,
or omit it for the clean cut.
