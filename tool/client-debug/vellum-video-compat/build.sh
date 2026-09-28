#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
source_file="$root_dir/tool/client-debug/vellum-video-compat/VellumVideoCompat.cpp"
output_file="$root_dir/clien/BeiDouVellumVideoCompat.dll"
build_dir="$(mktemp -d /tmp/beidou-vellum-video-build.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

# -fno-tree-loop-distribute-patterns: the DLL is linked with -nostdlib, so the optimiser must not
# rewrite our hand written length loops into `strlen` calls (undefined reference otherwise).
i686-w64-mingw32-g++ \
  -std=c++17 -Os -s -shared -nostdlib -fno-exceptions -fno-rtti \
  -fno-threadsafe-statics -fno-tree-loop-distribute-patterns \
  -Wl,--entry,_DllMain@12 -Wl,--subsystem,windows \
  -Wl,--no-insert-timestamp -Wl,--image-base,0x69140000 \
  -Wall -Wextra -Werror \
  "$source_file" -lkernel32 -luser32 -lgcc \
  -o "$build_dir/BeiDouVellumVideoCompat.dll"

file "$build_dir/BeiDouVellumVideoCompat.dll" | grep -q "PE32 executable (DLL).*Intel 80386"

# Keep the outgoing delivery before overwriting it. v4 (11264) was lost exactly this way, and a
# retired version cannot be rebuilt byte for byte once its source has moved on. One file per size.
backup_dir="$root_dir/tool/client-debug/vellum-video-compat/backup"
if [[ -f "$output_file" ]]; then
  outgoing_size=$(stat -f %z "$output_file")
  if [[ ! -f "$backup_dir/BeiDouVellumVideoCompat.dll.size$outgoing_size" ]]; then
    cp "$output_file" "$backup_dir/BeiDouVellumVideoCompat.dll.size$outgoing_size"
    echo "kept the outgoing delivery as BeiDouVellumVideoCompat.dll.size$outgoing_size"
  fi
fi

mv "$build_dir/BeiDouVellumVideoCompat.dll" "$output_file"
file "$output_file"
