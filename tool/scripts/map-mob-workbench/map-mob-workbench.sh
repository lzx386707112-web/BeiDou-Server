#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
APP="$ROOT/tool/scripts/map-mob-workbench/app.py"

cd "$ROOT"
exec python3 "$APP" "$@"
