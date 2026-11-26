#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
exec "${EDITOR_PYTHON:-python3}" editor.py "$@"
