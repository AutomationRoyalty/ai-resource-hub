# Short-Form Reel Workflow

Repeatable pipeline for turning a long video (+ a recorded CTA) into a branded 9:16
Instagram Reel. Every video follows the **same** steps, scripts, and brand spec below.

## Brand spec (locked)
- **Canvas:** 1080×1920 (9:16), 30 fps, H.264, yuv420p, AAC stereo 44.1 kHz.
- **Colors:** background pure **black** `#000000`, text **white** `#FFFFFF`. No blue, no accents.
- **Font:** Montserrat (in `fonts/`). Captions = SemiBold, hero/emphasis = ExtraBold.
- **Two layouts:**
  - **Horizontal source (demo)** → "bar layout": video scaled to `1080×608` in the middle band
    at `y=690`, black above/below; 2-line headline on top; captions in the lower band.
  - **Vertical source (CTA / talking head)** → full-frame; captions lower-third with black outline.
- **Pacing:** jump-cut the dead air (silence-detect) so the demo is fast.
- **Safe zone (Reels):** keep text clear of top ~220px, bottom ~420px, right ~130px.
- **CTA ending:** a real face-to-camera clip saying "Comment 'BUILD' …", captions burned,
  `COMMENT` + `'BUILD'` enlarged.

## Folder structure
```
AI Clipping Machine/
├── scripts/            all the editing scripts (precise_cut/ = the word-accurate cutter)
├── fonts/              Montserrat (bundled)
├── docs/               this file + the working loop
└── videos/<slug>/      one folder per video
    ├── <slug>.mp4      FINAL reel
    ├── config.md       this video's exact settings
    ├── source/         the downloaded video, the CTA recording
    ├── captions/       word timings and caption files
    └── working/        in-between files
```

## Prerequisites (one-time)
- **yt-dlp must be current** (`brew upgrade yt-dlp`). An outdated yt-dlp fails YouTube's
  "n-challenge" and silently falls back to **360p**. Current version gets full 1080p.
- ffmpeg with `libass` (subtitles) + `libzimg`/`zscale` + `tonemap` (HDR handling).
- Montserrat fonts in `fonts/` (bundled).

---

## Steps for a NEW video

Set up:
```bash
SH="<this folder>"; SLUG="my-new-slug"   # SH = the kit root (holds scripts/ and fonts/)
V="$SH/videos/$SLUG"; mkdir -p "$V/source" "$V/captions" "$V/working"
FONTS="$SH/fonts"
```

### 1 — Get the source in full quality
```bash
yt-dlp -f "137+140/bestvideo[height<=1080]+bestaudio/best" --merge-output-format mp4 \
  -o "$V/source/youtube-1080p.mp4" "<YOUTUBE_URL>"
```

### 2 — Cut the demo clip (choose a clean in/out that lands the moment + payoff)
```bash
ffmpeg -y -ss <IN> -to <OUT> -i "$V/source/youtube-1080p.mp4" \
  -c:v libx264 -crf 16 -preset veryfast -c:a aac -b:a 192k "$V/working/demo-cut.mp4"
```

### 3+4: Precise cut (default), transcribe, align, cut
Word-aware cut with ms word timings, via `scripts/precise_cut/` (read its `README.md`
for every step). Short version, with `PC="$SH/scripts/precise_cut"`, `PY=.venv/bin/python` (the venv from README step 2),
`P="$V/working/precise"`:
```bash
$PY -I "$PC/prep.py" "$V/working/demo-cut.mp4" "$P"
$PY -I "$PC/transcribe_phrases.py" "$P/work" "Brand Name, Product Name"   # Whisper API + ElevenLabs alignment
$PY -I "$PC/show_words.py" "$P/work"          # read it, then write $P/retakes.json (keep the LAST take)
$PY -I "$PC/build_words.py" "$P"
$PY -I "$PC/cut_plan_lf.py" "$P/work"         # pauses >= 200 ms -> 15 ms each side
$PY -I "$PC/check_leftovers.py" "$P"
$PY -I "$PC/render_cut.py" "$P/work" "$V/working/demo-cut.mp4" "$V/working/demo-fast-1080.mp4"
$PY -I "$PC/align_words.py" "$P/work" "$P/Transcript" "demo-fast-1080.mp4" "$SLUG"
$PY -I "$PC/qa_output.py" "$P"                # must report no repeats
python3 -c "import json; d=json.load(open('$P/Transcript/words.json'))
json.dump([{'word':w['w'],'start':w['s'],'end':w['e']} for w in d['words']], open('$V/working/words_fast.json','w'))"
```
Run the caption lexicon + `normalize_numbers.py` over `words_fast.json`, then:
```bash
python3 "$SH/scripts/captions_plan.py" "$V/working/words_fast.json" \
  "$V/captions/demo-captions.json" --max-words 4 --emphasis "phrase one|phrase two"
python3 "$SH/scripts/gen_demo_captions_ass.py" "$V/captions/demo-captions.json" "$V/captions/demo-captions.ass"
```
Then go to step 5. Steps 3 and 4 below are the **fallback** (no API access).

### 3 — Captions for the demo (fallback)
Get word-level timings, then phrase them. Word timings can come from YouTube auto-subs
(`yt-dlp --write-auto-subs --sub-format vtt`, parse the inline `<ts>` word tags, offset to
clip-relative) **or** from ElevenLabs STT (see step 6). Save as `captions/demo-words.json`
`[{"word","start","end"}]`. Then:
```bash
python3 "$SH/scripts/captions_plan.py" "$V/captions/demo-words.json" \
  "$V/captions/demo-captions.json" --emphasis "phrase one|phrase two"
```

### 4 — Jump-cut the dead air (fallback; also remaps the caption timings)
```bash
python3 "$SH/scripts/build_jumpcuts.py" "$V/working/demo-cut.mp4" "$V/working" \
  --words "$V/captions/demo-words.json"      # → keep_segments.json, words_fast.json
# CUT WITH clean_cut, NOT select — trim/concat + 12ms audio declick fades.
# (select+setpts renumbers video frames & audio samples separately → stray boundary
#  frames + a click at every cut. clean_cut is frame-accurate & click-free.)
python3 "$SH/scripts/clean_cut.py" "$V/working/demo-cut.mp4" \
  "$V/working/demo-fast-1080.mp4" "$V/working/keep_segments.json"
# re-plan captions on the tightened timeline:
python3 "$SH/scripts/captions_plan.py" "$V/working/words_fast.json" \
  "$V/captions/demo-captions.json" --emphasis "phrase one|phrase two"
python3 "$SH/scripts/gen_demo_captions_ass.py" "$V/captions/demo-captions.json" "$V/captions/demo-captions.ass"
```

### 5 — Composite the demo (bar layout + headline + captions)
```bash
L1="Headline line one"; L2="line two"
ffmpeg -y -i "$V/working/demo-fast-1080.mp4" -f lavfi -i color=c=black:s=1080x1920 \
 -filter_complex "[0:v]scale=1080:608:flags=lanczos,setsar=1[vid];[1:v][vid]overlay=0:690[c];\
[c]drawtext=fontfile=$FONTS/Montserrat-ExtraBold.ttf:text='$L1':fontcolor=white:fontsize=66:x=(w-text_w)/2:y=472[h1];\
[h1]drawtext=fontfile=$FONTS/Montserrat-ExtraBold.ttf:text='$L2':fontcolor=white:fontsize=66:x=(w-text_w)/2:y=558[h2];\
[h2]subtitles='$V/captions/demo-captions.ass':fontsdir=$FONTS[out]" \
 -map "[out]" -map "0:a" -shortest -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p \
 -c:a aac -b:a 192k -movflags +faststart "$V/working/demo-composited-1080.mp4"
```

### 6 — Prep the CTA face clip (record a ~5s "Comment 'BUILD' …" selfie)
Transcribe with ElevenLabs STT (returns word timings):
```bash
ffmpeg -y -i "$V/source/cta-recording.MOV" -vn -ac 1 -ar 16000 "$V/working/cta-audio.wav"
curl -s -X POST "https://api.elevenlabs.io/v1/speech-to-text" \
  -H "xi-api-key: $(grep ^ELEVENLABS_API_KEY= "$SH/.env" | cut -d= -f2-)" -F model_id=scribe_v1 \
  -F file=@"$V/working/cta-audio.wav" -F timestamps_granularity=word -o "$V/working/cta-stt.json"
# build cta-words.json [{word,start,end}] from cta-stt.json (words with type=="word")
python3 "$SH/scripts/captions_plan.py" "$V/captions/cta-words.json" "$V/captions/cta-plan.json" \
  --max-words 3 --emphasis "build|free tutorial"
python3 "$SH/scripts/gen_cta_captions_ass.py"   # reads cta-plan.json → cta.ass (run in captions/ or edit paths)
```
Encode the CTA: **iPhone clips are HDR (Dolby Vision / HLG)** — must tone-map HDR→SDR or
colors wash out. `-vf` (simple graph) auto-rotates portrait; `-filter_complex` does NOT.
Preserve original audio (no loudnorm — only a flat gain to match ~‑24 dB mean).
```bash
ffmpeg -y -i "$V/source/cta-recording.MOV" -vf "\
zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,\
zscale=t=bt709:m=bt709:r=tv,format=yuv420p,scale=1080:1920,setsar=1,fps=30,\
subtitles='$V/captions/cta.ass':fontsdir=$FONTS" \
 -af "volume=4dB,aformat=sample_rates=44100:channel_layouts=stereo" \
 -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k \
 -movflags +faststart "$V/working/cta-processed.mp4"
```

### 7 — Concatenate demo + CTA → final
```bash
ffmpeg -y -i "$V/working/demo-composited-1080.mp4" -i "$V/working/cta-processed.mp4" -filter_complex "\
[0:v]fps=30,scale=1080:1920,setsar=1[dv];[0:a]aformat=sample_rates=44100:channel_layouts=stereo[da];\
[1:v]fps=30,scale=1080:1920,setsar=1[cv];[1:a]aformat=sample_rates=44100:channel_layouts=stereo[ca];\
[dv][da][cv][ca]concat=n=2:v=1:a=1[v][a]" \
 -map "[v]" -map "[a]" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k \
 -movflags +faststart "$V/$SLUG.mp4"
```

## Gotchas / lessons baked in
- **360p bug** = outdated yt-dlp failing the n-challenge → `brew upgrade yt-dlp`.
- **Washed-out CTA color** = HDR (Dolby Vision/HLG) dumped to SDR without tone-mapping. Always tone-map.
- **`-filter_complex` does NOT auto-rotate** iPhone portrait clips; do rotation/HDR work in a
  simple `-vf` pass first (which auto-rotates), then concat.
- **No music is added** — audio is original only (zero royalty risk). Add a royalty-free bed only if asked.
- **Captions and beats:** keep phrases short (≤6 words demo, ≤3 words CTA). Emphasis lines → ExtraBold.
- **Transition glitches (micro-frames / audio clicks):** never cut with `select`+`setpts`/`asetpts`
  — it renumbers video frames and audio samples independently, leaving a stray boundary frame and a
  click at every join. Always cut with **`clean_cut.py`** (trim/concat + 12 ms audio fades). When
  joining two composited clips (demo → outro), add a ~30 ms `afade` out/in at the boundary.
- **Speed-up must re-assert 30 fps:** `setpts=PTS/1.2` speeds video but pushes it to 36 fps (30×1.2),
  which stutters on 30fps players. Always follow with `fps=30` (and `-r 30`). Pair with `atempo=1.2`
  for pitch-preserved audio. Verify: video & audio stream durations match and `avg_frame_rate=30/1`.
