#!/usr/bin/env bash
# Portable launcher — works from any clone location on macOS / Linux / Git Bash.
set -euo pipefail

# Resolve the directory this script lives in (follow symlinks).
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv if present (cross-platform: Unix .venv/bin, Windows .venv/Scripts).
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/Scripts/activate
fi

exec uvicorn backend.main:app --host "${ROOT_HOST:-127.0.0.1}" --port "${ROOT_PORT:-9000}"
