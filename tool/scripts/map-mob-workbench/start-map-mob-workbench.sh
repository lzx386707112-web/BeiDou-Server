#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8775}"
URL="http://${HOST}:${PORT}"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "端口 ${PORT} 已被占用，可能服务已经启动。"
  echo "访问: ${URL}"
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  exit 0
fi

echo "启动地图与怪物资源工作台..."
echo "访问: ${URL}"
cd "$ROOT"
exec tool/scripts/map-mob-workbench/map-mob-workbench.sh --host "$HOST" --port "$PORT" "$@"
