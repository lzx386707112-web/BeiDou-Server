#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
APP="$ROOT/tool/scripts/png2canvas/web_app.py"

usage() {
  cat <<'USAGE'
用法:
  rtk tool/scripts/png2canvas/png2canvas.sh [--host 127.0.0.1] [--port 8765]

启动 PNG -> 客户端 .img Canvas 网页工具。
默认地址:
  http://127.0.0.1:8765
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

cd "$ROOT"
exec python3 "$APP" "$@"
