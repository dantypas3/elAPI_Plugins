#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v uv &>/dev/null 2>&1; then
  echo "Installin uv..."

  if command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found."

      RESPONSE=$(osascript <<'APPLESCRIPT'
      tell application "System Events"
          activate
          display dialog "Homebrew is not installed on this Mac.
It is required to install 'uv' and Python dependencies.

Do you want to install Homebrew now?" buttons {"Cancel", "Install"} default button "Install" with icon caution
  end tell
  if button returned of result is "Install" then
      return "yes"
  else
      return "no"
  end if

APPLESCRIPT
  )
      if [ "$RESPONSE" = "yes" ]; then
        echo "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        echo "Homebrew installed successfully."
        # Update PATH for Homebrew (Apple Silicon or Intel)
        eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || eval "$(/usr/local/bin/brew shellenv)" || true
      else
        echo "User canceled Homebrew installation."
        echo "Terminating program."
        exit 1
      fi
    fi

  brew install uv
fi

echo "uv installed"

VENV_DIR=".venv"


[ -d "$VENV_DIR" ] || uv venv "$VENV_DIR"

source "$VENV_DIR/bin/activate"

if [ ! -d "$VENV_DIR" ]; then
  echo "No virtual environment found (.venv missing)."
  echo "Creating a new environment with uv"
  uv venv "$VENV_DIR"
fi

if [ ! -f pyproject.toml ]; then
  echo "pyproject.toml not found; this script expects uv to manage deps from pyproject."
  exit 1
fi



if [ "${UPDATE_DEPS:-0}" = "1" ] || [ ! -f uv.lock ]; then
  echo "Locking dependencies (generating/updating uv.lock)…"
  uv lock
fi

UV_SYNC_FLAGS=(--frozen)
if [ "${ELAPI_DEV:-0}" = "1" ]; then
  UV_SYNC_FLAGS+=(--extra dev)
fi

echo "Syncing environment with uv (${UV_SYNC_FLAGS[*]})…"
uv sync "${UV_SYNC_FLAGS[@]}"

# Install your local elapi-plugins package
if [ -f pyproject.toml ]; then
  echo "Installing local elapi-plugins package…"
  pip install .
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
exec uv run -m gui.gui
