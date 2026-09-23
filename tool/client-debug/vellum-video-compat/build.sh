#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
source_file="$root_dir/tool/client-debug/vellum-video-compat/VellumVideoCompat.cpp"
output_file="$root_dir/clien/BeiDouVellumVideoCompat.dll"
build_dir="$(mktemp -d /tmp/beidou-vellum-video-build.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

i686-w64-mingw32-g++ \
  -std=c++17 -Os -s -shared -nostdlib -fno-exceptions -fno-rtti \
  -fno-threadsafe-statics -Wl,--entry,_DllMain@12 -Wl,--subsystem,windows \
  -Wl,--no-insert-timestamp -Wl,--image-base,0x69140000 \
  -Wall -Wextra -Werror \
  "$source_file" -lkernel32 -luser32 -lgcc \
  -o "$build_dir/BeiDouVellumVideoCompat.dll"

file "$build_dir/BeiDouVellumVideoCompat.dll" | grep -q "PE32 executable (DLL).*Intel 80386"
mv "$build_dir/BeiDouVellumVideoCompat.dll" "$output_file"
file "$output_file"
