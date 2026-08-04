#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
source_file="$root_dir/tool/client-debug/fps-limit/BeiDouFpsLimit.cpp"
output_file="$root_dir/clien/BeiDou30FpsLimit.dll"

i686-w64-mingw32-g++ \
  -std=c++17 -Os -s -shared -nostdlib -fno-exceptions -fno-rtti \
  -fno-threadsafe-statics -Wl,--entry,_DllMain@12 -Wl,--subsystem,windows \
  -Wall -Wextra -Werror \
  "$source_file" -ld3d8 -lwinmm -lkernel32 -luser32 -lgcc -o "$output_file"

file "$output_file"
