#!/bin/bash
# ============================================================================
# Slideshow Studio — double-click launcher for Mac
#
# HOW TO USE:
#   1. Double-click this file ("Start Slideshow Studio.command").
#      (First time: if Mac says it's from an unidentified developer, right-click
#       the file -> Open -> Open. You only do that once.)
#   2. The first run asks for your fal.ai key and Claude key in pop-up boxes.
#   3. It installs what it needs, then opens your browser at the app.
#
# To stop the app later: close the Terminal window that opened, or press
# Control + C in it.
# ============================================================================

# Move into the folder this file lives in, no matter where you put it.
cd "$(dirname "$0")" || exit 1

echo "=============================================="
echo "   🎬  Starting Slideshow Studio"
echo "=============================================="
echo

# --- Make sure Python 3 is available ---------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display dialog "Slideshow Studio needs Python 3.\n\nA Mac window will now offer to install developer tools. Click Install, wait a few minutes, then double-click this launcher again." buttons {"OK"} default button "OK" with title "Slideshow Studio"'
  xcode-select --install
  exit 1
fi

# --- First-run setup: collect API keys via friendly pop-ups ----------------
if [ ! -f ".env" ]; then
  FAL=$(osascript -e 'text returned of (display dialog "Paste your fal.ai API key:" default answer "" with title "Slideshow Studio — Setup (1 of 2)")') || exit 1
  CLAUDE=$(osascript -e 'text returned of (display dialog "Paste your Claude (Anthropic) API key:" default answer "" with title "Slideshow Studio — Setup (2 of 2)")') || exit 1

  cat > .env <<EOF
FAL_KEY=${FAL}
ANTHROPIC_API_KEY=${CLAUDE}
IMAGE_MODEL=seedream
SCENE_MODEL=claude-sonnet-4-6
ASPECT_RATIO=9:16
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_REDIRECT_URI=http://localhost:8000/tiktok/callback
HOST=127.0.0.1
PORT=8000
EOF
  echo "→ Saved your keys to a local file (.env). You won't be asked again."
  echo
fi

# --- Install dependencies (quietly) into a local environment ---------------
if [ ! -d ".venv" ]; then
  echo "→ First-time setup: installing components (this can take a few minutes)…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python3 -m pip install -q --upgrade pip >/dev/null 2>&1
python3 -m pip install -q -r requirements.txt

# --- Open the browser shortly after the server starts ----------------------
( sleep 3; open "http://127.0.0.1:8000" ) &

echo
echo "→ Opening your browser at http://127.0.0.1:8000"
echo "→ Keep this window open while you use the app. Press Control+C to stop."
echo
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
