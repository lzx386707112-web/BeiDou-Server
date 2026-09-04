#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
i686-w64-mingw32-g++ -std=c++17 -Os -s -shared -nostdlib \
  -fno-builtin -fno-exceptions -fno-rtti -fno-threadsafe-statics \
  -Wl,--entry,_DllMain@12 -Wl,--subsystem,windows -Wl,--no-insert-timestamp \
  -Wl,--kill-at \
  -Wall -Wextra -Werror \
  "$root_dir/tool/client-debug/set-item-compat/BeiDouSetItemCompat.cpp" \
  -lkernel32 -luser32 -loleaut32 -lgcc \
  -o "$root_dir/clien/BeiDouSetItemCompat.dll"

file "$root_dir/clien/BeiDouSetItemCompat.dll"
