#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
source_file="$root_dir/tool/client-debug/dependency-check/BeiDouDependencyCheck.cpp"
output_file="$root_dir/clien/BeiDouDependencyCheck.exe"

i686-w64-mingw32-g++ \
  -std=c++17 -Os -s -nostdlib -ffreestanding \
  -fno-exceptions -fno-rtti -fno-threadsafe-statics \
  -Wl,--entry,_EntryPoint -Wl,--subsystem,windows -Wl,--no-insert-timestamp \
  -Wall -Wextra -Werror \
  "$source_file" -lkernel32 -luser32 -lgcc -o "$output_file"

file "$output_file"

unexpected_imports="$({ objdump -p "$output_file" | awk '/DLL Name:/ {print $3}'; } \
  | grep -Eiv '^(KERNEL32|USER32)\.dll$' || true)"
if [[ -n "$unexpected_imports" ]]; then
  echo "Unexpected runtime imports in dependency checker:" >&2
  echo "$unexpected_imports" >&2
  exit 1
fi

echo "Verified: checker imports only KERNEL32.dll and USER32.dll"
