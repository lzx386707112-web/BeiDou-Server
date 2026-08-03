#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
source_file="$root_dir/tool/client-debug/wz_file_logger/WzFileLogger.cpp"
output_file="$root_dir/clien/WzFileLogger.dll"

i686-w64-mingw32-g++ \
  -std=c++11 -Os -s -shared -nostdlib -fno-exceptions -fno-rtti \
  -fno-threadsafe-statics -Wl,--entry,_DllMain@12 -Wl,--subsystem,windows \
  -Wall -Wextra -Werror -Wno-cast-function-type -Wno-unused-function -Wno-unused-parameter \
  "$source_file" -lkernel32 -luser32 -lgcc -o "$output_file"

file "$output_file"
