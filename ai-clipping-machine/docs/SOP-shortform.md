# SOP — Transcribe a video → short-form clips (simple)

How we turn a long video into branded 9:16 reels, end to end. Written as a back-and-forth: **what
you prompt**, **what you send**, and **what I produce** at each step. The detailed tooling lives in
the `edit-reel` skill (`.claude/skills/edit-reel/SKILL.md`) + `docs/WORKFLOW.md`. This is the map that ties them together.

**Golden rule:** you drive with plain prompts; I do the pipeline via the skills and hand back files
for your review. Nothing goes live until you approve.

---

## Step 1 — You ask me to transcribe a video

**You prompt (examples):**
- "Transcribe this video: `<YouTube URL>`"
- "Transcribe the '6 Mistakes' video and pull reel ideas."

**What you send me:**
- The **YouTube URL** (or the file path if it's not on YouTube).
- *(Optional)* a steer: the angle you want, which topics matter, target length, ad vs organic.

**What I produce:**
- A cleaned, timestamped **transcript** with word-level timings, saved in `videos/<slug>/`.

---

## Step 2 — I propose the clips; you confirm

**What I produce (no prompt needed — I do it right after transcribing):**
- A **reel-idea breakdown** at `videos/<slug>/ideas.md` — a numbered list of
  candidate clips. Each idea has:
  - **Hook / headline** (the on-screen line)
  - **IN → OUT** window (timestamps in the source)
  - **The payoff** (why it lands / the concluding thought)
  - **Emphasis phrases** (the big-center caption moments)
  - **Angle** (organic value post vs CTA/ad)

**You prompt (examples):**
- "Do ideas 2, 5, and 7."
- "Build #3, but make the hook about a different angle instead."
- "Skip the tutorial ones, just the punchy hooks."

*(This is the confirmation gate — I don't cut anything until you pick.)*

---

## Step 3 — I produce the clips (the `edit-reel` skill)

**You prompt:** usually nothing more — your Step 2 confirmation is the go. Or "make them," "build the 3."

**What I do per confirmed idea (via the `edit-reel` skill + `scripts/`):**
1. Download source at 1080p, cut the demo window.
2. **Precise cut** (`scripts/precise_cut/`): transcribe, time every word, drop bad takes from
   `retakes.json` (keep the last take), cut the dead air on word boundaries. Fallback without the APIs:
   `build_jumpcuts.py` then `clean_cut.py` at −30/0.2.
3. **Captions** (`captions_plan.py` + `gen_demo_captions_ass.py`) — ~4 words/line, brand lexicon
   applied, your emphasis phrases big-center.
4. **Composite** the bar layout: video band + **headline** + burned captions (safe-zone, Montserrat).
5. **Ending / CTA**: append the recorded CTA, or if none, run `ending_fix.sh` so the last words land.
6. *(Optional)* **music bed**; then **QA** with `qa_reel.sh` (format, single audio stream, final
   word audible, sibilants, tail).
7. Record the exact params in `videos/<slug>/config.md`.

**What I hand back:**
- Each clip as a **cmd-click `file://` link** for you to watch locally, grouped and labeled.

---

## Step 4 — You give feedback; I iterate

**You prompt (examples — be specific, I'll target it):**
- **Captions:** "caption says 'Acme Seller', should be 'Acme Setter'" · "the 'AT ONCE' line is one frame early"
- **Language / tone:** "make the hook punchier" · "drop the jargon in line 2"
- **Visuals:** "headline is too big / crowding the edge" · "the bar layout looks off on the white slide"
- **Headline:** "change clip 8's headline to 'How to qualify leads without friction'"
- **Audio:** "the final word sounds clipped / too loud / has music I don't want"

**What I do:**
- Apply the fix precisely (headline swap without re-composite, caption re-time, ending fix, music
  on/off, sibilant-safe re-cut, etc.), **re-deliver the same file link**, and note what changed.
- Repeat until you say it's good. *(When you confirm it's good, I'll ask if we should save/update a
  skill from the feedback — yes/no.)*

---

## Quick reference — one line each

| Step | You send / prompt | I produce |
|---|---|---|
| 1 Transcribe | YouTube URL (+ steer) | transcript + word timings |
| 2 Ideas | "do #2, #5, #7" | numbered reel-idea breakdown → you pick |
| 3 Produce | (your pick = go) | finished reels as `file://` links + `config.md` |
| 4 Feedback | specific notes (captions/lang/visual/headline/audio) | targeted fixes, re-delivered |

**What makes a clip "done":** on-brand (1080×1920/30, black bg, Montserrat, safe-zone), payoff
intact, captions correct (lexicon + emphasis), final word lands, `qa_reel.sh` clean, and you've
approved it.
