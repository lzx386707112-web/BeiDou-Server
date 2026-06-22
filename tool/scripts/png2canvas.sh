#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY_SCRIPT="$ROOT/tool/scripts/png2canvas/replace_img_canvas.py"

usage() {
  cat <<'USAGE'
用法:
  rtk tool/scripts/png2canvas.sh

交互式 PNG 写入客户端 .img 工具。
默认目标是 clien/Data/Skill/<Skill img ID>.img，例如:
  clien/Data/Skill/122.img -> skill/1221009/effect/0/0, 1, 2...
USAGE
}

ask() {
  local prompt="$1"
  local default="${2:-}"
  local value
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default]: " value
    printf '%s\n' "${value:-$default}"
  else
    read -r -p "$prompt: " value
    printf '%s\n' "$value"
  fi
}

ask_required() {
  local prompt="$1"
  local default="${2:-}"
  local value
  while true; do
    value="$(ask "$prompt" "$default")"
    if [[ -n "$value" ]]; then
      printf '%s\n' "$value"
      return 0
    fi
    echo "必填。"
  done
}

ask_yes_no() {
  local prompt="$1"
  local default="${2:-n}"
  local value
  while true; do
    value="$(ask "$prompt (y/n)" "$default")"
    case "$value" in
      y|Y|yes|YES|是) return 0 ;;
      n|N|no|NO|否) return 1 ;;
      *) echo "请输入 y 或 n。" ;;
    esac
  done
}

choose() {
  local prompt="$1"
  shift
  local -a options=("$@")
  local i choice
  echo "$prompt" >&2
  for i in "${!options[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "${options[$i]}" >&2
  done
  while true; do
    read -r -p "请选择 [1]: " choice
    choice="${choice:-1}"
    if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#options[@]} )); then
      printf '%s\n' "${options[$((choice - 1))]}"
      return 0
    fi
    echo "选择无效。" >&2
  done
}

quote_cmd() {
  local -a out=()
  local arg
  for arg in "$@"; do
    out+=("$(printf '%q' "$arg")")
  done
  printf '%s\n' "${out[*]}"
}

validate_file() {
  local path="$1"
  [[ -f "$path" ]]
}

validate_dir() {
  local path="$1"
  [[ -d "$path" ]]
}

ask_existing_file() {
  local prompt="$1"
  local default="${2:-}"
  local path
  while true; do
    path="$(ask_required "$prompt" "$default")"
    if validate_file "$path"; then
      printf '%s\n' "$path"
      return 0
    fi
    echo "找不到文件: $path"
  done
}

ask_existing_dir() {
  local prompt="$1"
  local default="${2:-}"
  local path
  while true; do
    path="$(ask_required "$prompt" "$default")"
    if validate_dir "$path"; then
      printf '%s\n' "$path"
      return 0
    fi
    echo "找不到目录: $path"
  done
}

ask_skill_img() {
  local skill_img
  local img_path
  while true; do
    skill_img="$(ask_required "Skill img ID" "122")"
    img_path="clien/Data/Skill/${skill_img}.img"
    if validate_file "$img_path"; then
      printf '%s\n' "$img_path"
      return 0
    fi
    echo "找不到客户端 IMG: $img_path"
  done
}

join_canvas_path() {
  local base="${1%/}"
  local child="${2#/}"
  if [[ -z "$child" ]]; then
    printf '%s\n' "$base"
  else
    printf '%s/%s\n' "$base" "$child"
  fi
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  usage >&2
  echo >&2
  echo "该工具只保留交互式操作。请直接运行: rtk tool/scripts/png2canvas.sh" >&2
  exit 2
fi

if [[ ! -t 0 ]]; then
  usage >&2
  echo >&2
  echo "该工具需要交互式终端。" >&2
  exit 2
fi

cd "$ROOT"

echo "PNG -> 客户端 IMG Canvas 交互工具"
echo

args=()

target_mode="$(choose "请选择目标客户端 IMG:" "Skill.wz 技能 .img" "自定义 .img 路径")"
if [[ "$target_mode" == "Skill.wz 技能 .img" ]]; then
  img_path="$(ask_skill_img)"
  args+=(--img "$img_path")
  skill_id="$(ask_required "技能节点 ID" "1221009")"
  node_name="$(ask_required "图片节点名" "effect")"
  default_parent="skill/${skill_id}/${node_name}"
else
  img_path="$(ask_existing_file "客户端 .img 路径" "clien/Data/Skill/122.img")"
  args+=(--img "$img_path")
  default_parent="$(ask_required ".img 内部目标父路径，不是磁盘路径" "skill/1221009/effect")"
fi

source_mode="$(choose "请选择 PNG 来源:" "PNG 帧目录" "单张 PNG")"

if [[ "$source_mode" == "单张 PNG" ]]; then
  png="$(ask_existing_file "PNG 文件")"
  group="$(ask "图片分组，1221009/effect 通常是 0；留空表示 effect 下直接是 canvas" "0")"
  default_canvas_parent="$(join_canvas_path "$default_parent" "$group")"
  canvas_name="$(ask_required "canvas 名称" "0")"
  canvas="$(join_canvas_path "$default_canvas_parent" "$canvas_name")"
  canvas="$(ask_required "目标 canvas 内部路径" "$canvas")"
  args+=(--png "$png" --canvas "$canvas")
else
  png_dir="$(ask_existing_dir "PNG 帧目录")"
  group="$(ask "图片分组，1221009/effect 通常是 0；留空表示 effect 下直接是 canvas" "0")"
  default_canvas_dir="$(join_canvas_path "$default_parent" "$group")"
  canvas_dir="$(ask_required "目标 canvas 父路径（.img 内部路径，不是磁盘路径）" "$default_canvas_dir")"
  name_mode_choice="$(choose "帧画布命名方式:" "按序号" "使用文件名")"
  case "$name_mode_choice" in
    "按序号") name_mode="index" ;;
    *) name_mode="stem" ;;
  esac
  args+=(--png-dir "$png_dir" --canvas-dir "$canvas_dir" --name-mode "$name_mode")
fi

origin_choice="$(choose "请选择原点:" "保持不变" "居中" "左下角" "底部居中" "自定义 x,y")"
case "$origin_choice" in
  "保持不变") origin="keep" ;;
  "居中") origin="center" ;;
  "左下角") origin="bottom-left" ;;
  "底部居中") origin="bottom-center" ;;
  *) origin="$(ask_required "原点 x,y" "0,0")" ;;
esac
args+=(--origin "$origin")

delay="$(ask "delay 整数，留空则保持原值/跳过" "")"
if [[ -n "$delay" ]]; then
  args+=(--set-int "delay=$delay")
fi

z="$(ask "z 整数，留空则保持原值/跳过" "")"
if [[ -n "$z" ]]; then
  args+=(--set-int "z=$z")
fi

while ask_yes_no "是否添加其他 int 子节点" "n"; do
  int_pair="$(ask_required "int，格式 name=value")"
  args+=(--set-int "$int_pair")
done

if ask_yes_no "写入前是否备份客户端 .img" "y"; then
  args+=(--backup)
fi

if ask_yes_no "是否仅预览不写入" "y"; then
  args+=(--dry-run)
fi

echo
echo "即将执行命令:"
quote_cmd python3 "$PY_SCRIPT" "${args[@]}"
echo

if ask_yes_no "现在执行" "y"; then
  exec python3 "$PY_SCRIPT" "${args[@]}"
fi

echo "已取消。"
