#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8790}"
URL="http://${HOST}:${PORT}"
VENV_BIN="$ROOT/tool/resource-workbench/envs/wz-python/bin/python"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "端口 ${PORT} 已被占用，结束旧进程后重新启动以加载最新代码。"
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t | xargs kill
  sleep 1
  if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "无法释放端口 ${PORT}，请手动结束后再试。"
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
    exit 1
  fi
fi

echo "启动 BeiDou 资源工作台..."
echo "访问: ${URL}"
cd "$ROOT"
if [ -x "$VENV_BIN" ]; then
  exec "$VENV_BIN" tool/resource-workbench/app.py --host "$HOST" --port "$PORT" "$@"
else
  echo "未找到项目 venv ($VENV_BIN)，回退到系统 python3..."
  exec python3 tool/resource-workbench/app.py --host "$HOST" --port "$PORT" "$@"
fi
