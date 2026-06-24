#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVER_DIR="$ROOT/gms-server"
DEFAULT_JAR="$SERVER_DIR/BeiDou.jar"
DEFAULT_PID_FILE="$SERVER_DIR/BeiDou.pid"
DEFAULT_LOG_FILE="$SERVER_DIR/logs/BeiDou.out.log"

usage() {
  cat <<'USAGE'
用法:
  rtk tool/scripts/start_server.sh
  rtk tool/scripts/start_server.sh --background
  rtk tool/scripts/start_server.sh --config gms-server/application.yml
  rtk tool/scripts/start_server.sh -- --server.port=8687

启动当前服务端。优先运行 BeiDou.jar；如果 jar 不存在，则用 Spring Boot Maven 插件从源码启动。

选项:
  --jar PATH       指定 jar，默认: gms-server/BeiDou.jar
  --config PATH    指定外部 application.yml
  --background     后台启动，并写入 PID 文件
  --pid-file PATH  PID 文件，默认: gms-server/BeiDou.pid
  --log-file PATH  后台日志文件，默认: gms-server/logs/BeiDou.out.log
  -h, --help       显示帮助

写在 -- 后面的参数会原样传给 Spring Boot。

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

jar="$DEFAULT_JAR"
config=""
background=0
pid_file="$DEFAULT_PID_FILE"
log_file="$DEFAULT_LOG_FILE"
has_app_args=0
app_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jar)
      shift
      if [[ $# -eq 0 || "$1" == -* ]]; then
        echo "--jar 需要一个值" >&2
        exit 2
      fi
      jar="$1"
      ;;
    --config)
      shift
      if [[ $# -eq 0 || "$1" == -* ]]; then
        echo "--config 需要一个值" >&2
        exit 2
      fi
      config="$1"
      ;;
    --background)
      background=1
      ;;
    --pid-file)
      shift
      if [[ $# -eq 0 || "$1" == -* ]]; then
        echo "--pid-file 需要一个值" >&2
        exit 2
      fi
      pid_file="$1"
      ;;
    --log-file)
      shift
      if [[ $# -eq 0 || "$1" == -* ]]; then
        echo "--log-file 需要一个值" >&2
        exit 2
      fi
      log_file="$1"
      ;;
    --)
      shift
      app_args=("$@")
      has_app_args=1
      break
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

if [[ "$jar" != /* ]]; then
  jar="$ROOT/$jar"
fi
if [[ -n "$config" && "$config" != /* ]]; then
  config="$ROOT/$config"
fi
if [[ "$pid_file" != /* ]]; then
  pid_file="$ROOT/$pid_file"
fi
if [[ "$log_file" != /* ]]; then
  log_file="$ROOT/$log_file"
fi

jdk_home="$(find_jdk21 || true)"
if [[ -z "$jdk_home" ]]; then
  cat >&2 <<'EOF'
未能自动找到 JDK 21。
请重新执行:
  JAVA_HOME_21=/path/to/jdk21 rtk tool/scripts/start_server.sh
EOF
  exit 2
fi

if [[ -n "$config" ]]; then
  if [[ ! -f "$config" ]]; then
    echo "找不到配置文件: $config" >&2
    exit 2
  fi
fi

run_mode="jar"
if [[ ! -f "$jar" ]]; then
  run_mode="spring_boot"
  echo "找不到 jar: $jar"
  echo "改用 Spring Boot Maven 插件从源码启动。"
  if ! command -v mvn >/dev/null 2>&1; then
    echo "找不到 mvn，无法从源码启动。请先安装 Maven 或执行打包脚本生成 jar。" >&2
    exit 2
  fi
fi

java_args=()
if [[ -n "$config" ]]; then
  java_args+=("-Dspring.config.location=$config")
fi
java_args+=(-jar "$jar")
if [[ "$has_app_args" -eq 1 ]]; then
  java_args+=("${app_args[@]}")
fi

mvn_args=(org.springframework.boot:spring-boot-maven-plugin:run -Dmaven.test.skip=true)
if [[ -n "$config" ]]; then
  mvn_args+=("-Dspring-boot.run.jvmArguments=-Dspring.config.location=$config")
fi
if [[ "$has_app_args" -eq 1 ]]; then
  app_arg_value="$(IFS=,; printf '%s' "${app_args[*]}")"
  mvn_args+=("-Dspring-boot.run.arguments=$app_arg_value")
fi

if [[ "$background" -eq 1 ]]; then
  if [[ -f "$pid_file" ]]; then
    old_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
      echo "服务端似乎已在运行，PID: $old_pid" >&2
      exit 1
    fi
  fi

  mkdir -p "$(dirname "$pid_file")" "$(dirname "$log_file")"
  (
    cd "$SERVER_DIR"
    if [[ "$run_mode" == "jar" ]]; then
      nohup "$jdk_home/bin/java" "${java_args[@]}" > "$log_file" 2>&1 &
    else
      JAVA_HOME="$jdk_home" PATH="$jdk_home/bin:$PATH" nohup mvn "${mvn_args[@]}" > "$log_file" 2>&1 &
    fi
    echo $! > "$pid_file"
  )
  echo "服务端已后台启动，PID: $(cat "$pid_file")"
  echo "日志: $log_file"
  exit 0
fi

echo "工作目录: $SERVER_DIR"
cd "$SERVER_DIR"
if [[ "$run_mode" == "jar" ]]; then
  echo "启动服务端: $jar"
  exec "$jdk_home/bin/java" "${java_args[@]}"
fi

echo "启动服务端: mvn org.springframework.boot:spring-boot-maven-plugin:run"
exec env JAVA_HOME="$jdk_home" PATH="$jdk_home/bin:$PATH" mvn "${mvn_args[@]}"
