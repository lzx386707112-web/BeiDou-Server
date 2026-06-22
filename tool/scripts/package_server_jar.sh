#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVER_DIR="$ROOT/gms-server"
DEFAULT_OUTPUT="$SERVER_DIR/BeiDou.jar"

usage() {
  cat <<'USAGE'
用法:
  rtk tool/scripts/package_server_jar.sh
  rtk tool/scripts/package_server_jar.sh --output "$HOME/Downloads/BeiDou.jar"
  rtk tool/scripts/package_server_jar.sh --with-tests

将 gms-server 打包成 BeiDou.jar。

选项:
  -o, --output   输出 jar 路径，默认: gms-server/BeiDou.jar
  --with-tests   打包时运行测试，默认跳过测试
  -h, --help     显示帮助

环境变量:
  JAVA_HOME_21  自动检测失败时，手动指定 JDK 21 路径
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

output="$DEFAULT_OUTPUT"
skip_tests=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--output)
      shift
      if [[ $# -eq 0 || "$1" == -* ]]; then
        echo "--output 需要一个值" >&2
        exit 2
      fi
      output="$1"
      ;;
    --with-tests)
      skip_tests=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if ! command -v mvn >/dev/null 2>&1; then
  echo "找不到 mvn，请先安装 Maven 或把 mvn 加入 PATH。" >&2
  exit 2
fi

if [[ ! -f "$SERVER_DIR/pom.xml" ]]; then
  echo "找不到服务端 pom.xml: $SERVER_DIR/pom.xml" >&2
  exit 2
fi

jdk_home="$(find_jdk21 || true)"
if [[ -z "$jdk_home" ]]; then
  cat >&2 <<'EOF'
未能自动找到 JDK 21。
请重新执行:
  JAVA_HOME_21=/path/to/jdk21 rtk tool/scripts/package_server_jar.sh
EOF
  exit 2
fi

mkdir -p "$(dirname "$output")"

args=(-pl gms-server -am clean package)
if [[ "$skip_tests" -eq 1 ]]; then
  args+=(-DskipTests)
fi

echo "开始打包服务端..."
(
  cd "$ROOT"
  JAVA_HOME="$jdk_home" PATH="$jdk_home/bin:$PATH" mvn "${args[@]}"
)

built_jar="$SERVER_DIR/target/BeiDou.jar"
if [[ ! -f "$built_jar" ]]; then
  echo "打包完成但找不到产物: $built_jar" >&2
  exit 1
fi

cp "$built_jar" "$output"
echo "已输出: $output"
