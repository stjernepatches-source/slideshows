#!/usr/bin/env bash
# One command to start the Slideshow Studio.
#   ./run.sh
# Creates a local virtualenv, installs deps, then launches the web app.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if [ ! -d ".venv" ]; then
  echo "→ Creating virtualenv (.venv)…"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Installing dependencies…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  echo "→ No .env found — copying .env.example to .env. Fill in your keys!"
  cp .env.example .env
fi

# Load HOST/PORT from .env if present (without exporting secrets to logs).
HOST="$(grep -E '^HOST=' .env | cut -d= -f2- || true)"; HOST="${HOST:-127.0.0.1}"
PORT="$(grep -E '^PORT=' .env | cut -d= -f2- || true)"; PORT="${PORT:-8000}"

echo "→ Open http://${HOST}:${PORT} in your browser"
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
