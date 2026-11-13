#!/bin/bash
# One-time setup for the AI Clipping Machine (Mac only). Safe to run again any time.
cd "$(dirname "$0")" || exit 1

step() { printf "\n==> %s\n" "$1"; }
stop() { printf "\n[!] %s\n\n" "$1"; exit 1; }

[ "$(uname)" = "Darwin" ] || stop "This workflow only runs on a Mac."

# 1. Homebrew (the Mac's app installer for developer tools)
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)"; done
if ! command -v brew >/dev/null; then
  stop "Homebrew is not installed yet. It needs your Mac password, so you install it yourself:
    1. Open the Terminal app (Cmd+Space, type Terminal, press Return).
    2. Paste this line and press Return, then follow what it says:
       /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"
    3. When it finishes, come back and run setup again."
fi

# 2. Video tools
step "Installing the video tools (ffmpeg, yt-dlp, Python). The first time can take a few minutes."
for p in ffmpeg yt-dlp; do   # install only what's missing; never replace a tool that already works
  command -v "$p" >/dev/null || brew install "$p" || stop "Could not install $p. Run setup again; if it keeps failing, run: brew doctor"
done
[ -x "$(brew --prefix)/bin/python3" ] || brew install python || stop "Could not install Python. Run setup again; if it keeps failing, run: brew doctor"
brew upgrade yt-dlp >/dev/null 2>&1 || true   # an old yt-dlp silently downloads low quality
for f in subtitles zscale tonemap; do
  ffmpeg -hide_banner -filters 2>/dev/null | grep -q " $f " || stop "ffmpeg is missing a feature ($f). Run: brew reinstall ffmpeg"
done

# 3. Python libraries
step "Installing the Python libraries."
[ -x .venv/bin/python ] || "$(brew --prefix)/bin/python3" -m venv .venv || stop "Could not create the Python environment."
.venv/bin/pip install -q --disable-pip-version-check -r scripts/precise_cut/requirements.txt || stop "Could not install the Python libraries. Check your internet connection and run setup again."

# 4. API keys
step "Checking your API keys."
[ -f .env ] || cp .env.example .env
chmod 600 .env
missing=""
for k in OPENAI_API_KEY ELEVENLABS_API_KEY; do
  v="$(grep "^$k=" .env | cut -d= -f2-)"
  case "$v" in ""|*xxxx*) missing="$missing $k" ;; esac
done
if [ -n "$missing" ]; then
  open -e .env
  stop "Your API keys are missing:$missing
    The keys file just opened in TextEdit. Paste each key right after its = sign,
    save (Cmd+S), close the file, then run setup again.
    How to get the keys: see README.md, step 2."
fi
.venv/bin/python -I scripts/check_keys.py || stop "Fix the key problem above, then run setup again."

mkdir -p videos
printf "\nSetup complete. You're ready to make reels.\n\n"
