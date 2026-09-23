#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
source_file="$root_dir/tool/client-debug/ijl15-config/config_loader.S"
patcher="$root_dir/tool/client-debug/ijl15-config/patch_ijl15.py"
output_file="$root_dir/clien/ijl15.dll"
build_dir="$(mktemp -d /tmp/beidou-ijl15-config-build.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

i686-w64-mingw32-gcc -m32 -c "$source_file" -o "$build_dir/config_loader.o"
i686-w64-mingw32-objcopy -O binary -j .text \
  "$build_dir/config_loader.o" "$build_dir/config_loader.bin"
python3 "$patcher" \
  --input "$output_file" \
  --payload "$build_dir/config_loader.bin" \
  --output "$output_file"

file "$output_file" | grep -q "PE32 executable (DLL).*Intel 80386"
file "$output_file"

