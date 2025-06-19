	#!/usr/bin/env bash
set -euo pipefail

# 1) Go to script’s directory (project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR"

# 2) Create & activate venv if missing
if [ -d "venv" ]; then
    echo "Activating existing virtualenv…"
    # shellcheck disable=SC1091
    source "venv/bin/activate"
else
    echo "Creating virtualenv…"
    python3 -m venv venv
    # shellcheck disable=SC1091
    source "venv/bin/activate"

    # 2a) Install dependencies if you have a requirements.txt
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies from requirements.txt…"
        pip install --upgrade pip
        pip install -r requirements.txt
    fi
fi

# 3) Finally, launch the Flask app (and auto-open browser)
python -m plugins.resources.export_gui
