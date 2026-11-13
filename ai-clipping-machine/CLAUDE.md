# AI Clipping Machine: instructions for Claude

This folder turns long YouTube videos into short vertical reels. The person using it is probably not
technical: talk in plain language, one step at a time, and never dump logs on them.

## First-time setup ("set me up", "install this", or any request before setup has passed)
1. Run `bash setup.sh` from this folder. It is safe to re-run; it skips what is already done.
2. Relay its messages in plain words. The common stops:
   - **Homebrew missing.** It needs their Mac password, which you can't type for them. Tell them to
     follow the three steps setup.sh printed (Terminal, paste the line, run setup again).
   - **Keys missing.** setup.sh opens `.env` in TextEdit. Walk them through README.md step 2 to get
     each key, paste it after the `=`, save, close, and say "done". Then re-run setup.sh.
   - **A key fails.** `scripts/check_keys.py` prints the exact fix. Repeat it simply.
3. **Never ask them to paste an API key into the chat.** If they do anyway, write it into `.env`
   yourself and don't repeat it back.
4. Setup is done when it prints `Setup complete.`

## Making reels
- Follow the `edit-reel` skill (`.claude/skills/edit-reel/SKILL.md`). Detail: `docs/WORKFLOW.md`.
  The working loop with the user (transcribe, propose clips, they pick, you build, they review):
  `docs/SOP-shortform.md`.
- One folder per video: `videos/<slug>/`. Scripts are in `scripts/`, fonts in `fonts/`.
- Run the precise cutter with `.venv/bin/python -I scripts/precise_cut/<step>.py` (steps in
  `scripts/precise_cut/README.md`). Other `.py` scripts run with `python3`.
- Keys live in `.env`; the scripts read it themselves.
- Show every finished reel as a clickable `file://` link and ask for feedback before moving on.
- **Review page:** after building or re-rendering reels, run `python3 scripts/build_review.py videos/<slug>`
  then start `python3 scripts/review_server.py videos/<slug>` in the background and hand over
  `http://127.0.0.1:8765/videos/<slug>/review.html` (a `file://` link plays no video when the kit sits
  in Desktop/Documents: macOS gives the browser the HTML file but not the mp4s). They watch each reel there, mark
  Approve / Needs changes / Reject and OK to upload, leave timestamped notes, then paste the
  "Copy feedback" text back into chat. Act on that text, re-render, and re-run the script: re-rendered
  reels show as "Updated" with their previous note.
- The look (colors, font, caption size) is a default house style. If they want a different look,
  update the skill file.
