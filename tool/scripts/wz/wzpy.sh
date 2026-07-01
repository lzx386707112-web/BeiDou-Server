#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
WZPY_DIR="$ROOT/tool/wz-python"

usage() {
  cat <<'USAGE'
Usage:
  tool/scripts/wz/wzpy.sh convert clien/Data/Skill/100.img --region GMS -o /tmp/100.json
  tool/scripts/wz/wzpy.sh convert clien/Data/Skill/100.img --auto-region
  tool/scripts/wz/wzpy.sh ui
  tool/scripts/wz/wzpy.sh ui clien/Data/Skill/Skill.wz
  tool/scripts/wz/wzpy.sh ui clien/Data/Skill --region EMS
  tool/scripts/wz/wzpy.sh python -c 'import wzpy; print(wzpy.WzImage)'

Commands:
  convert   Run wz-python convert_img.py
  ui        Run wz-python Web UI for .wz archives or hierarchical .wz pack dirs
  python    Run python3 with tool/wz-python on PYTHONPATH
USAGE
}

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 2
fi

cmd="$1"
shift

export PYTHONPATH="$WZPY_DIR${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"

has_region_arg() {
  for arg in "$@"; do
    case "$arg" in
      --region|--region=*)
        return 0
        ;;
    esac
  done
  return 1
}

first_path_arg() {
  for arg in "$@"; do
    case "$arg" in
      -*)
        ;;
      *)
        printf '%s\n' "$arg"
        return 0
        ;;
    esac
  done
  return 1
}

looks_like_loose_img_dir() {
  local path="$1"
  local base
  [[ -d "$path" ]] || return 1
  base="$(basename "$path")"
  [[ ! -f "$path/$base.wz" ]] || return 1
  compgen -G "$path/*.img" > /dev/null
}

case "$cmd" in
  convert)
    exec python3 "$WZPY_DIR/convert_img.py" "$@"
    ;;
  ui)
    ui_path="$(first_path_arg "$@" || true)"
    if [[ -n "$ui_path" ]]; then
      if [[ "$ui_path" == *.img ]]; then
        cat >&2 <<EOF
The wz-python Web UI cannot open loose standalone .img files.
Use convert instead:
  tool/scripts/wz/wzpy.sh convert "$ui_path" --region GMS -o /tmp/$(basename "$ui_path").json
EOF
        exit 2
      fi
      if looks_like_loose_img_dir "$ui_path"; then
        cat >&2 <<EOF
The wz-python Web UI cannot open a directory of loose .img files:
  $ui_path

This repo's client data is extracted as standalone .img files. Use convert on a single .img:
  tool/scripts/wz/wzpy.sh convert "$ui_path/100.img" --region GMS -o /tmp/100.img.json

Or start the UI without a path and load a real .wz archive / hierarchical pack:
  tool/scripts/wz/wzpy.sh ui
EOF
        exit 2
      fi
    fi
    if has_region_arg "$@"; then
      exec python3 "$WZPY_DIR/run.py" "$@"
    else
      exec python3 "$WZPY_DIR/run.py" "$@" --region GMS
    fi
    ;;
  python)
    exec python3 "$@"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
