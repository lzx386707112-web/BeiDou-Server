#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ORANGE_WZ_DIR="$ROOT/tool/orange-wz"
DEFAULT_ORZ_HOME="/Users/lizixian/Documents/mxd/OrzRepacker-v1.157.48"
ORZ_HOME="${ORZ_REPACKER_HOME:-$DEFAULT_ORZ_HOME}"
LIB_DIR="$ORZ_HOME/lib"
CLASSES_DIR="$ORANGE_WZ_DIR/target/classes"
SOURCES_FILE="$ORANGE_WZ_DIR/target/sources.txt"

usage() {
  cat <<'USAGE'
用法:
  rtk tool/scripts/package/pack_xml_wz.sh
  rtk tool/scripts/package/pack_xml_wz.sh --input gms-server/wz/Skill.wz --output /tmp/Skill.wz --version 83
  rtk tool/scripts/package/pack_xml_wz.sh -i gms-server/wz/Skill.wz -o /tmp/Skill.wz

不带参数不会自动执行；如确实要打包 .img.xml，请显式传入 --input 和 --output。

环境变量:
  JAVA_HOME_21       自动检测失败时，手动指定 JDK 21 路径
  ORZ_REPACKER_HOME  OrzRepacker 目录，默认:
                     /Users/lizixian/Documents/mxd/OrzRepacker-v1.157.48
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
    /usr/local/opt/openjdk@21 \
    /opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home \
    /opt/homebrew/opt/openjdk \
    /usr/local/opt/openjdk/libexec/openjdk.jdk/Contents/Home \
    /usr/local/opt/openjdk \
    /opt/homebrew/opt/java/libexec/openjdk.jdk/Contents/Home \
    /opt/homebrew/opt/java \
    /usr/local/opt/java/libexec/openjdk.jdk/Contents/Home \
    /usr/local/opt/java
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

  "$javac" --release 21 \
    -encoding UTF-8 \
    -processorpath "$lombok_jar" \
    -processor 'lombok.launch.AnnotationProcessorHider$AnnotationProcessor' \
    -cp "$LIB_DIR/*" \
    -d "$CLASSES_DIR" \
    @"$SOURCES_FILE"
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

if [[ $# -eq 0 ]]; then
  cat >&2 <<'EOF'
服务端 .img.xml 通常不需要打包成 WZ。
如果你要把客户端 clien/Data/Character 这种 .img 目录打包成 Character.wz，请使用:
  rtk tool/scripts/package/pack_img_wz.sh

如确实要打包 .img.xml，请显式传入 --input 和 --output。
EOF
  exit 2
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
  JAVA_HOME_21=/path/to/jdk21 rtk tool/scripts/package/pack_xml_wz.sh ...
EOF
  exit 2
fi

compile_orange_wz "$jdk_home"

exec "$jdk_home/bin/java" \
  -cp "$CLASSES_DIR:$LIB_DIR/*" \
  orange.wz.cli.PackXmlToWz "$@"
