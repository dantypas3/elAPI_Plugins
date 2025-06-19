#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

PY=python3
if ! command -v $PY &>/dev/null; then
  PY=python
fi

if [ ! -d "venv" ]; then
  echo "Creating virtualenv…"
  $PY -m venv venv
  source venv/bin/activate
  echo "Installing dependencies…"
  if [ -f requirements.txt ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
  fi
else
  echo "Activating virtualenv…"
  source venv/bin/activate
fi

python -m plugins.resources.export_gui
