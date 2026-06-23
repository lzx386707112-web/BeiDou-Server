#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8765}"
URL="http://${HOST}:${PORT}"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "端口 ${PORT} 已被占用，可能服务已经启动。"
  echo "访问: ${URL}"
  echo
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  exit 0
fi

echo "启动 PNG2Canvas 工具..."
echo "访问: ${URL}"
echo
cd "$ROOT"
exec tool/scripts/png2canvas.sh --host "$HOST" --port "$PORT" "$@"
