#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PY=python3
if ! command -v "$PY" &>/dev/null; then
  PY=python
  if ! command -v "$PY" &>/dev/null; then
    echo "No Python found (tried python3 and python)"
    exit 1
  fi
fi

if [ ! -d venv ]; then
  echo "Creating virtualenv…"
  "$PY" -m venv venv
fi
echo "Activating virtualenv…"
# shellcheck disable=SC1091
source venv/bin/activate

if [ -f requirements.txt ]; then
  echo "Installing dependencies…"
  pip install --upgrade pip
  pip install -r requirements.txt
fi

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
CONFIG_FILE="$CONFIG_DIR/elapi.yml"
mkdir -p "$CONFIG_DIR"

if ! grep -q '^[[:space:]]*api_token[[:space:]]*:' "$CONFIG_FILE"; then
  echo "No API token found in known locations."
  echo "Launching elapi init…"

  # ───────────────────────────────────────────────────────────────
  # Blue BG / White FG banner (ANSI escape codes)
  echo '************************************************************'
  echo '*                  UNI-HEIDELBERG USERS                    *'
  echo '*                                                          *'
  echo '*  Use this API address:                                   *'
  echo '*  https://elabftw.uni-heidelberg.de/api/v2                *'
  echo '************************************************************'
  # ───────────────────────────────────────────────────────────────

  # ensure elapi CLI is installed
  if ! command -v elapi &>/dev/null; then
    echo "elapi CLI not installed (pip install elapi) – aborting."
    exit 1
  fi

  elapi init
fi


# 5) now extract the token
API_TOKEN="$(grep -i '^[[:space:]]*api_token[[:space:]]*:' "$CONFIG_FILE" \
             | cut -d: -f2- | xargs)"

if [ -z "$API_TOKEN" ]; then
  echo "Still no api_token in $CONFIG_FILE after init—aborting."
  exit 1
fi

export ELAPI_API_TOKEN="$API_TOKEN"

echo "Running GUI…"
python -m gui.gui
