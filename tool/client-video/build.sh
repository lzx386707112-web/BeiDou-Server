#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../.." && pwd)"
source_dir="$root_dir/tool/client-video"
build_dir="$source_dir/build"
vpx_dir="$source_dir/.deps/libvpx-win32"

bash "$source_dir/build-libvpx-win32.sh"
mkdir -p "$build_dir"

i686-w64-mingw32-g++ \
  -std=c++17 -O2 -shared -static -static-libgcc -static-libstdc++ \
  -Wall -Wextra -Werror \
  -I"$vpx_dir/include" \
  "$source_dir/BeiDouVideo.cpp" \
  "$source_dir/McvFormat.cpp" \
  -L"$vpx_dir/lib" -lvpx -ld3d8 -lwinmm \
  -Wl,--kill-at \
  -o "$root_dir/clien/BeiDouVideo.dll"

i686-w64-mingw32-g++ \
  -std=c++17 -O2 -mwindows -static -static-libgcc -static-libstdc++ \
  -Wall -Wextra -Werror \
  "$source_dir/VideoHarness.cpp" \
  -ld3d8 \
  -o "$root_dir/clien/BeiDouVideoHarness.exe"

i686-w64-mingw32-g++ \
  -std=c++17 -Os -s -shared -nostdlib \
  -fno-exceptions -fno-rtti -fno-threadsafe-statics \
  -Wall -Wextra -Werror \
  "$source_dir/D3D8Proxy.cpp" \
  -lkernel32 -lgcc \
  -Wl,--entry,_DllMain@12 -Wl,--subsystem,windows -Wl,--kill-at \
  -o "$build_dir/d3d8-desktop-test.dll"

c++ -std=c++17 -O2 -Wall -Wextra -Werror \
  "$source_dir/McvFormat.cpp" \
  "$source_dir/McvProbe.cpp" \
  -o "$build_dir/mcv_probe"

file "$root_dir/clien/BeiDouVideo.dll"
file "$root_dir/clien/BeiDouVideoHarness.exe"
file "$build_dir/d3d8-desktop-test.dll"
