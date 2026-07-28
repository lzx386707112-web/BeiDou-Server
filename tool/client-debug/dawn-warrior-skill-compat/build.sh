#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
source_file="$root_dir/tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp"
output_file="$root_dir/clien/DawnWarriorSkillCompat.dll"

i686-w64-mingw32-g++ \
  -std=c++17 -Os -s -shared -nostdlib -fno-exceptions -fno-rtti \
  -fno-threadsafe-statics -Wl,--entry,_DllMain@12 -Wl,--subsystem,windows \
  -Wall -Wextra -Werror \
  "$source_file" -lkernel32 -lgcc -o "$output_file"

file "$output_file"
