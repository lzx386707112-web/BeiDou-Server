#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVER_DIR="$ROOT/gms-server"
UI_DIR="$ROOT/gms-ui"
STATIC_DIR="$SERVER_DIR/src/main/resources/static"
DEFAULT_OUTPUT="$SERVER_DIR/BeiDou.jar"

usage() {
  cat <<'USAGE'
用法:
  rtk tool/scripts/package_server_jar.sh
  rtk tool/scripts/package_server_jar.sh --output "$HOME/Downloads/BeiDou.jar"
  rtk tool/scripts/package_server_jar.sh --with-tests

构建 gms-ui 后，将后台管理页面和 gms-server 一起打包成 BeiDou.jar。

选项:
  -o, --output   输出 jar 路径，默认: gms-server/BeiDou.jar
  --skip-ui      不构建/内置 gms-ui，仅打包服务端
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
build_ui=1

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
    --skip-ui)
      build_ui=0
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

if [[ "$build_ui" -eq 1 ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "找不到 npm，无法构建 gms-ui。请先安装 Node.js/npm，或使用 --skip-ui 仅打包服务端。" >&2
    exit 2
  fi
  if [[ ! -f "$UI_DIR/package.json" ]]; then
    echo "找不到前端 package.json: $UI_DIR/package.json" >&2
    exit 2
  fi

  echo "开始构建后台管理前端..."
  (
    cd "$UI_DIR"
    if [[ ! -d node_modules ]]; then
      echo "未找到 gms-ui/node_modules，先执行 npm install..."
      npm install --no-package-lock --legacy-peer-deps
    fi
    npm run build
  )

  if [[ ! -f "$UI_DIR/dist/index.html" ]]; then
    echo "前端构建完成但找不到产物: $UI_DIR/dist/index.html" >&2
    exit 1
  fi

  rm -rf "$STATIC_DIR"
  mkdir -p "$STATIC_DIR"
  cp -R "$UI_DIR/dist/." "$STATIC_DIR/"
  echo "已内置后台管理页面: $STATIC_DIR"
else
  echo "跳过 gms-ui 构建，仅打包服务端。"
fi

args=(-pl gms-server -am clean package)
if [[ "$skip_tests" -eq 1 ]]; then
  args+=(-Dmaven.test.skip=true)
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

resource_overlay=""
cleanup_resource_overlay() {
  if [[ -n "$resource_overlay" && -d "$resource_overlay" ]]; then
    rm -rf "$resource_overlay"
  fi
}
trap cleanup_resource_overlay EXIT

resource_overlay="$(mktemp -d)"
mkdir -p "$resource_overlay/BOOT-INF/classes"
"$jdk_home/bin/jar" tf "$built_jar" \
  | sed -n 's#^BOOT-INF/classes/##p' \
  > "$resource_overlay/existing-classpath-entries.txt"
(
  cd "$SERVER_DIR/target/classes"
  while IFS= read -r resource; do
    entry="${resource#./}"
    if [[ "$entry" == *.class ]] && grep -Fxq "$entry" "$resource_overlay/existing-classpath-entries.txt"; then
      continue
    fi
    mkdir -p "$resource_overlay/BOOT-INF/classes/$(dirname "$entry")"
    cp "$resource" "$resource_overlay/BOOT-INF/classes/$entry"
  done < <(find . -type f ! -name '.DS_Store')
)
if [[ -d "$SERVER_DIR/scripts-zh-CN" ]]; then
  mkdir -p "$resource_overlay/BOOT-INF/classes/scripts-zh-CN"
  cp -R "$SERVER_DIR/scripts-zh-CN/." "$resource_overlay/BOOT-INF/classes/scripts-zh-CN/"
fi
(
  cd "$resource_overlay"
  "$jdk_home/bin/jar" uf "$built_jar" BOOT-INF/classes
)

if ! "$jdk_home/bin/jar" tf "$built_jar" | grep -q '^BOOT-INF/classes/application.yml$'; then
  echo "打包后的 jar 缺少 BOOT-INF/classes/application.yml" >&2
  exit 1
fi

cp "$built_jar" "$output"
echo "已输出: $output"
