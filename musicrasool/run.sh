#!/usr/bin/env bash
# MusicRasool launcher (uses the venv created by install.sh)
set -e
cd "$(dirname "$0")"

if [ -d "venv" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

exec python run.py "$@"
