#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    echo "Activating existing virtualenv…"
    # shellcheck disable=SC1091
    source "venv/bin/activate"
else
    echo "Creating virtualenv…"
    python3 -m venv venv
    # shellcheck disable=SC1091
    source "venv/bin/activate"

    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies from requirements.txt…"
        pip install --upgrade pip
        pip install -r requirements.txt
    fi
fi

python -m gui.gui