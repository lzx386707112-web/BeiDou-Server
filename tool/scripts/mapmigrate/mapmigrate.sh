#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
APP="$ROOT/tool/scripts/mapmigrate/web_app.py"

usage() {
  cat <<'USAGE'
用法:
  rtk tool/scripts/mapmigrate/mapmigrate.sh [--host 127.0.0.1] [--port 8770]

启动「地图 / Boss 迁移兼容性工作台」网页工具。
默认地址:
  http://127.0.0.1:8770
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

cd "$ROOT"

# 解析可用的 python：优先 venv（含 flask/wzpy/numpy/PIL/Crypto），其次系统 python3
resolve_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "$PYTHON_BIN"; return
  fi
  local venv_py
  venv_py="$HOME/.workbuddy/binaries/python/envs/wz-python/bin/python3"
  if [[ -x "$venv_py" ]] && "$venv_py" -c "import flask, Crypto" >/dev/null 2>&1; then
    echo "$venv_py"; return
  fi
  # 用户真实环境常用 rtk python3（自带 flask），这里也尝试
  if command -v rtk >/dev/null 2>&1; then
    local rtk_py
    rtk_py="$(rtk python3 -c 'import sys,os;print(os.path.realpath(sys.executable))' 2>/dev/null)"
    if [[ -n "$rtk_py" && -x "$rtk_py" ]] && "$rtk_py" -c "import flask" >/dev/null 2>&1; then
      echo "$rtk_py"; return
    fi
  fi
  echo "python3"
}

PY="$(resolve_python)"
echo "使用 Python: $PY"
exec "$PY" "$APP" "$@"
