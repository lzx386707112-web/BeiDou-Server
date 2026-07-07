#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ORANGE_WZ_DIR="$ROOT/tool/orange-wz"
DEFAULT_ORZ_HOME="/Users/lizixian/Documents/mxd/OrzRepacker-v1.157.48"
ORZ_HOME="${ORZ_REPACKER_HOME:-$DEFAULT_ORZ_HOME}"
LIB_DIR="$ORZ_HOME/lib"
CLASSES_DIR="$ORANGE_WZ_DIR/target/classes"
SOURCES_FILE="$ORANGE_WZ_DIR/target/sources.txt"
COMPILE_STAMP="$ORANGE_WZ_DIR/target/.preview-img-compile.stamp"
DEFAULT_PREVIEW_IMG_JAVA_OPTS="-Xms256m -Xmx4g -XX:+UseG1GC"
DEFAULT_PREVIEW_INPUT="${PREVIEW_IMG_INPUT:-/Users/lizixian/Documents/mxd/神说/Data/Character}"
DEFAULT_PREVIEW_REGION="${PREVIEW_IMG_REGION:-cms}"
DEFAULT_PREVIEW_PORT="${PREVIEW_IMG_PORT:-8787}"

usage() {
  cat <<'USAGE'
用法:
  rtk tool/scripts/package/preview_img_wz.sh
  rtk tool/scripts/package/preview_img_wz.sh --interactive
  rtk tool/scripts/package/preview_img_wz.sh --input "/Users/lizixian/Documents/mxd/神说/Data/Character" --region cms --port 8787
  rtk tool/scripts/package/preview_img_wz.sh -i clien/Data/Character -p 8787 --region gms

不带参数会一键启动神说 Character 预览:
  input  = /Users/lizixian/Documents/mxd/神说/Data/Character
  region = cms
  port   = 8787

环境变量:
  JAVA_HOME_21       自动检测失败时，手动指定 JDK 21 路径
  ORZ_REPACKER_HOME  OrzRepacker 目录，默认:
                     /Users/lizixian/Documents/mxd/OrzRepacker-v1.157.48
  PREVIEW_IMG_INPUT  一键启动时的默认输入目录
  PREVIEW_IMG_REGION 一键启动时的默认 region，默认 cms
  PREVIEW_IMG_PORT   一键启动时的默认端口，默认 8787
  PREVIEW_IMG_JAVA_OPTS
                     预览服务 JVM 参数，默认:
                     -Xms256m -Xmx4g -XX:+UseG1GC
USAGE
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

run_interactive() {
  if [[ ! -t 0 ]]; then
    usage >&2
    echo >&2
    echo "该工具需要交互式终端。脚本中请显式传入 --input、--region 和 --port。" >&2
    return 2
  fi

  local target input default_region region port
  target="$(interactive_choose "请选择要预览的 IMG 目录:" \
    "神说 Character" \
    "神说 Skill" \
    "神说 Item" \
    "本项目 Character" \
    "自定义目录")"

  case "$target" in
    "神说 Character") input="/Users/lizixian/Documents/mxd/神说/Data/Character" ;;
    "神说 Skill") input="/Users/lizixian/Documents/mxd/神说/Data/Skill" ;;
    "神说 Item") input="/Users/lizixian/Documents/mxd/神说/Data/Item" ;;
    "本项目 Character") input="$ROOT/clien/Data/Character" ;;
    "自定义目录") input="$(interactive_ask "输入包含 .img 的目录" "$DEFAULT_PREVIEW_INPUT")" ;;
  esac

  default_region="$DEFAULT_PREVIEW_REGION"
  if [[ "$input" == "$ROOT/"* ]]; then
    default_region="gms"
  fi

  region="$(interactive_ask "region: gms/cms/latest/empty" "$default_region")"
  port="$(interactive_ask "端口" "$DEFAULT_PREVIEW_PORT")"
  preview_args=(--input "$input" --region "$region" --port "$port")
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

  if [[ -f "$COMPILE_STAMP" && -f "$CLASSES_DIR/orange/wz/cli/PreviewImgServer.class" ]]; then
    if ! find "$ORANGE_WZ_DIR/src/main/java" "$LIB_DIR" -newer "$COMPILE_STAMP" -print -quit | grep -q .; then
      echo "Java 已编译，跳过编译步骤。"
      return 0
    fi
  fi

  echo "开始编译 orange-wz 预览服务..."

  "$javac" --release 21 \
    -encoding UTF-8 \
    -processorpath "$lombok_jar" \
    -processor 'lombok.launch.AnnotationProcessorHider$AnnotationProcessor' \
    -cp "$LIB_DIR/*" \
    -d "$CLASSES_DIR" \
    @"$SOURCES_FILE"

  touch "$COMPILE_STAMP"
}

preview_args=()
if [[ $# -eq 0 ]]; then
  preview_args=(--input "$DEFAULT_PREVIEW_INPUT" --region "$DEFAULT_PREVIEW_REGION" --port "$DEFAULT_PREVIEW_PORT")
  echo "一键启动 IMG 预览: ${DEFAULT_PREVIEW_INPUT} (region=${DEFAULT_PREVIEW_REGION}, port=${DEFAULT_PREVIEW_PORT})"
elif [[ "${1:-}" == "--interactive" ]]; then
  run_interactive
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
else
  preview_args=("$@")
fi

jdk_home="$(find_jdk21 || true)"
if [[ -z "$jdk_home" ]]; then
  cat >&2 <<'EOF'
未能自动找到 JDK 21。
请重新执行:
  JAVA_HOME_21=/path/to/jdk21 rtk tool/scripts/package/preview_img_wz.sh ...
EOF
  exit 2
fi

compile_orange_wz "$jdk_home"

preview_img_java_opts="${PREVIEW_IMG_JAVA_OPTS:-$DEFAULT_PREVIEW_IMG_JAVA_OPTS}"
read -r -a java_opts <<< "$preview_img_java_opts"
echo "JVM 参数: ${java_opts[*]}"

exec "$jdk_home/bin/java" \
  "${java_opts[@]}" \
  -cp "$CLASSES_DIR:$LIB_DIR/*" \
  orange.wz.cli.PreviewImgServer "${preview_args[@]}"
