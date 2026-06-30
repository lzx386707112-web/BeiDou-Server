#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ORANGE_WZ_DIR="$ROOT/tool/orange-wz"
DEFAULT_ORZ_HOME="/Users/lizixian/Documents/mxd/OrzRepacker-v1.157.48"
ORZ_HOME="${ORZ_REPACKER_HOME:-$DEFAULT_ORZ_HOME}"
LIB_DIR="$ORZ_HOME/lib"
CLASSES_DIR="$ORANGE_WZ_DIR/target/classes"
SOURCES_FILE="$ORANGE_WZ_DIR/target/sources.txt"
COMPILE_STAMP="$ORANGE_WZ_DIR/target/.pack-img-compile.stamp"
DEFAULT_PACK_IMG_WZ_JAVA_OPTS="-Xms512m -Xmx8g -XX:+UseG1GC"

usage() {
  cat <<'USAGE'
用法:
  rtk tool/scripts/pack_img_wz.sh
  rtk tool/scripts/pack_img_wz.sh --input clien/Data/Character --output "$HOME/Downloads/Character.wz" --version 83
  rtk tool/scripts/pack_img_wz.sh -i clien/Data/Character -o "$HOME/Downloads/Character.wz"

不带参数会进入交互式操作。

环境变量:
  JAVA_HOME_21       自动检测失败时，手动指定 JDK 21 路径
  ORZ_REPACKER_HOME  OrzRepacker 目录，默认:
                     /Users/lizixian/Documents/mxd/OrzRepacker-v1.157.48
  PACK_IMG_WZ_JAVA_OPTS
                     打包进程 JVM 参数，默认:
                     -Xms512m -Xmx8g -XX:+UseG1GC
                     Character 仍内存不足时可设为: -Xms512m -Xmx12g -XX:+UseG1GC
USAGE
}

java_major() {
  local java_bin="$1"
  local version
  version="$("$java_bin" -version 2>&1 | awk -F '"' '/version/ {print $2; exit}')"
  if [[ "$version" == 1.* ]]; then
    printf '%s\n' "${version#1.}" | cut -d. -f1
  else
    printf '%s\n' "$version" | cut -d. -f1
  fi
}

candidate_java_homes() {
  if [[ -n "${JAVA_HOME_21:-}" ]]; then
    printf '%s\n' "$JAVA_HOME_21"
  fi
  if [[ -n "${JAVA_HOME:-}" ]]; then
    printf '%s\n' "$JAVA_HOME"
  fi
  if command -v /usr/libexec/java_home >/dev/null 2>&1; then
    /usr/libexec/java_home -v 21 2>/dev/null || true
  fi
  if command -v brew >/dev/null 2>&1; then
    local brew_jdk
    brew_jdk="$(brew --prefix openjdk@21 2>/dev/null || true)"
    if [[ -n "$brew_jdk" ]]; then
      printf '%s\n' \
        "$brew_jdk/libexec/openjdk.jdk/Contents/Home" \
        "$brew_jdk"
    fi
  fi
  printf '%s\n' \
    /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
    /opt/homebrew/opt/openjdk@21 \
    /usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
    /usr/local/opt/openjdk@21
  find /opt/homebrew/Cellar/openjdk@21 /usr/local/Cellar/openjdk@21 \
    -path '*/libexec/openjdk.jdk/Contents/Home' \
    -type d 2>/dev/null || true
}

find_jdk21() {
  local home java_bin major
  while IFS= read -r home; do
    [[ -n "$home" ]] || continue
    java_bin="$home/bin/java"
    [[ -x "$java_bin" ]] || continue
    major="$(java_major "$java_bin")"
    if [[ "$major" -ge 21 ]]; then
      printf '%s\n' "$home"
      return 0
    fi
  done < <(candidate_java_homes | awk '!seen[$0]++')

  if command -v java >/dev/null 2>&1; then
    java_bin="$(command -v java)"
    major="$(java_major "$java_bin")"
    if [[ "$major" -ge 21 ]]; then
      dirname "$(dirname "$java_bin")"
      return 0
    fi
  fi
  return 1
}

compile_orange_wz() {
  local jdk_home="$1"
  local javac="$jdk_home/bin/javac"
  local lombok_jar

  if [[ ! -d "$LIB_DIR" ]]; then
    echo "找不到 OrzRepacker lib 目录: $LIB_DIR" >&2
    echo "请设置 ORZ_REPACKER_HOME=/path/to/OrzRepacker-v1.157.48" >&2
    exit 2
  fi
  lombok_jar="$(find "$LIB_DIR" -maxdepth 1 -name 'lombok-*.jar' | sort | tail -n 1)"
  if [[ -z "$lombok_jar" ]]; then
    echo "在该目录下找不到 Lombok jar: $LIB_DIR" >&2
    exit 2
  fi

  mkdir -p "$CLASSES_DIR" "$(dirname "$SOURCES_FILE")"
  find "$ORANGE_WZ_DIR/src/main/java" -name '*.java' \
    ! -name 'Xml2Img2.java' \
    | sort > "$SOURCES_FILE"

  if [[ -f "$COMPILE_STAMP" && -f "$CLASSES_DIR/orange/wz/cli/PackImgDirToWz.class" ]]; then
    if ! find "$ORANGE_WZ_DIR/src/main/java" "$LIB_DIR" -newer "$COMPILE_STAMP" -print -quit | grep -q .; then
      echo "Java 已编译，跳过编译步骤。"
      return 0
    fi
  fi

  echo "开始编译 orange-wz 打包工具..."

  "$javac" --release 21 \
    -encoding UTF-8 \
    -processorpath "$lombok_jar" \
    -processor 'lombok.launch.AnnotationProcessorHider$AnnotationProcessor' \
    -cp "$LIB_DIR/*" \
    -d "$CLASSES_DIR" \
    @"$SOURCES_FILE"

  touch "$COMPILE_STAMP"
}

output_arg() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --output|-o)
        shift
        [[ $# -gt 0 ]] && printf '%s\n' "$1"
        return 0
        ;;
    esac
    shift
  done
  return 0
}

check_output_parent() {
  local output="$1"
  local parent suggestion
  [[ -n "$output" ]] || return 0

  parent="$(dirname "$output")"
  if [[ "$parent" == "/private/tmp" || "$parent" == "/tmp" ]]; then
    suggestion="${HOME:-.}/Downloads/$(basename "$output")"
    echo "当前运行环境不能可靠写入 ${parent}，请改用下载目录，例如: ${suggestion}" >&2
    exit 13
  fi
  if [[ -d "$parent" && ! -w "$parent" ]]; then
    echo "输出目录不可写: ${parent}" >&2
    exit 13
  fi
}

interactive_ask() {
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

interactive_ask_required() {
  local prompt="$1"
  local default="${2:-}"
  local value
  while true; do
    value="$(interactive_ask "$prompt" "$default")"
    if [[ -n "$value" ]]; then
      printf '%s\n' "$value"
      return 0
    fi
    echo "必填。"
  done
}

interactive_ask_yes_no() {
  local prompt="$1"
  local default="${2:-n}"
  local value
  while true; do
    value="$(interactive_ask "$prompt (y/n)" "$default")"
    case "$value" in
      y|Y|yes|YES|是) return 0 ;;
      n|N|no|NO|否) return 1 ;;
      *) echo "请输入 y 或 n。" ;;
    esac
  done
}

interactive_choose() {
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

interactive_quote_cmd() {
  local -a out=()
  local arg
  for arg in "$@"; do
    out+=("$(printf '%q' "$arg")")
  done
  printf '%s\n' "${out[*]}"
}

interactive_default_output_dir() {
  local dir="${HOME:-}/Downloads"
  printf '%s\n' "${dir:-Downloads}"
}

interactive_collect_base_imgs() {
  local img
  base_imgs=()
  while IFS= read -r img; do
    base_imgs+=("$img")
  done < <(find "$data_dir" -mindepth 1 -maxdepth 1 -type f -name '*.img' | sort)
}

interactive_prepare_base_input() {
  base_tmp_dir="$(mktemp -d "$ROOT/tool/orange-wz/target/base-img.XXXXXX")"
  local img
  local input
  for input in "${inputs[@]}"; do
    mkdir -p "$base_tmp_dir/$(basename "$input")"
  done
  for img in "${base_imgs[@]}"; do
    ln -s "$ROOT/$img" "$base_tmp_dir/$(basename "$img")"
  done
}

run_interactive() {
  if [[ ! -t 0 ]]; then
    usage >&2
    echo >&2
    echo "该工具需要交互式终端。脚本中请显式传入 --input 和 --output。" >&2
    return 2
  fi

  cd "$ROOT"

  echo "客户端 IMG 目录 -> WZ 打包交互工具"
  echo

  data_dir="clien/Data"
  target="$(interactive_choose "请选择要打包的客户端 Data 目录:" "Character" "Skill" "Item" "UI" "全部目录" "自定义目录")"
  case "$target" in
    "全部目录")
      if [[ ! -d "$data_dir" ]]; then
        echo "找不到目录: $data_dir" >&2
        return 2
      fi

      mkdir -p "$ROOT/tool/orange-wz/target"

      inputs=()
      while IFS= read -r input; do
        inputs+=("$input")
      done < <(find "$data_dir" -mindepth 1 -maxdepth 1 -type d | sort)
      interactive_collect_base_imgs

      if [[ ${#inputs[@]} -eq 0 && ${#base_imgs[@]} -eq 0 ]]; then
        echo "找不到可打包内容: $data_dir" >&2
        return 2
      fi

      output_dir="$(interactive_ask_required "输出目录" "$(interactive_default_output_dir)")"
      output_dir="${output_dir%/}"
      version="$(interactive_ask_required "WZ 版本" "83")"

      echo
      echo "即将执行命令:"
      if [[ ${#base_imgs[@]} -gt 0 || ${#inputs[@]} -gt 0 ]]; then
        echo "# Data 根目录 ${#base_imgs[@]} 个 .img + ${#inputs[@]} 个一级目录索引 -> $output_dir/Base.wz"
        printf '#   %s\n' "${base_imgs[@]}"
        interactive_quote_cmd "$ROOT/tool/scripts/pack_img_wz.sh" --input "<base-temp-dir>" --output "$output_dir/Base.wz" --version "$version"
      fi
      for input in "${inputs[@]}"; do
        base="$(basename "$input")"
        interactive_quote_cmd "$ROOT/tool/scripts/pack_img_wz.sh" --input "$input" --output "$output_dir/${base}.wz" --version "$version"
      done
      echo

      if interactive_ask_yes_no "现在执行" "y"; then
        base_tmp_dir=""
        trap '[[ -z "${base_tmp_dir:-}" ]] || rm -rf "$base_tmp_dir"' EXIT

        if [[ ${#base_imgs[@]} -gt 0 || ${#inputs[@]} -gt 0 ]]; then
          interactive_prepare_base_input
          echo
          echo "==> 打包 Data 根目录 .img 和一级目录索引 -> $output_dir/Base.wz"
          "$ROOT/tool/scripts/pack_img_wz.sh" --input "$base_tmp_dir" --output "$output_dir/Base.wz" --version "$version"
        fi

        for input in "${inputs[@]}"; do
          base="$(basename "$input")"
          output="$output_dir/${base}.wz"
          echo
          echo "==> 打包 $input -> $output"
          "$ROOT/tool/scripts/pack_img_wz.sh" --input "$input" --output "$output" --version "$version"
        done
        echo
        echo "全部打包完成。"
        return 0
      fi

      echo "已取消。"
      return 0
      ;;
    "自定义目录")
      input="$(interactive_ask_required "输入客户端 .img 目录" "$data_dir/Character")"
      ;;
    *)
      input="$data_dir/$target"
      ;;
  esac

  while [[ ! -d "$input" ]]; do
    echo "找不到目录: $input"
    input="$(interactive_ask_required "输入客户端 .img 目录")"
  done

  base="$(basename "$input")"
  output="$(interactive_ask_required "输出 .wz 文件" "$(interactive_default_output_dir)/${base}.wz")"
  version="$(interactive_ask_required "WZ 版本" "83")"

  args=(--input "$input" --output "$output" --version "$version")

  echo
  echo "即将执行命令:"
  interactive_quote_cmd "$ROOT/tool/scripts/pack_img_wz.sh" "${args[@]}"
  echo

  if interactive_ask_yes_no "现在执行" "y"; then
    exec "$ROOT/tool/scripts/pack_img_wz.sh" "${args[@]}"
  fi

  echo "已取消。"
}

if [[ $# -eq 0 ]]; then
  run_interactive
  exit $?
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

check_output_parent "$(output_arg "$@")"

jdk_home="$(find_jdk21 || true)"
if [[ -z "$jdk_home" ]]; then
  cat >&2 <<'EOF'
未能自动找到 JDK 21。
请重新执行:
  JAVA_HOME_21=/path/to/jdk21 rtk tool/scripts/pack_img_wz.sh ...
EOF
  exit 2
fi

compile_orange_wz "$jdk_home"

pack_img_wz_java_opts="${PACK_IMG_WZ_JAVA_OPTS:-$DEFAULT_PACK_IMG_WZ_JAVA_OPTS}"
read -r -a java_opts <<< "$pack_img_wz_java_opts"
echo "JVM 参数: ${java_opts[*]}"

exec "$jdk_home/bin/java" \
  "${java_opts[@]}" \
  -cp "$CLASSES_DIR:$LIB_DIR/*" \
  orange.wz.cli.PackImgDirToWz "$@"
