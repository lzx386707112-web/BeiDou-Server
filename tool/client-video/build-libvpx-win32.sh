#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
deps_dir="$script_dir/.deps"
source_dir="$deps_dir/libvpx-src"
install_dir="$deps_dir/libvpx-win32"
version="1.15.2"
nasm_version="2.16.03"
nasm_source="$deps_dir/nasm-$nasm_version"
nasm_install="$deps_dir/nasm-host"

if [[ -f "$install_dir/lib/libvpx.a" ]]; then
  exit 0
fi

mkdir -p "$deps_dir"
if ! command -v nasm >/dev/null 2>&1 && ! command -v yasm >/dev/null 2>&1; then
  if [[ ! -x "$nasm_install/bin/nasm" ]]; then
    archive="$deps_dir/nasm-$nasm_version.tar.xz"
    if [[ ! -f "$archive" ]]; then
      curl --fail --location \
        "https://www.nasm.us/pub/nasm/releasebuilds/$nasm_version/nasm-$nasm_version.tar.xz" \
        --output "$archive"
    fi
    if [[ ! -d "$nasm_source" ]]; then
      tar -xf "$archive" -C "$deps_dir"
    fi
    pushd "$nasm_source" >/dev/null
    ./configure --prefix="$nasm_install"
    make -j"$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)"
    make install
    popd >/dev/null
  fi
  export PATH="$nasm_install/bin:$PATH"
fi
if [[ ! -d "$source_dir/.git" ]]; then
  git clone --depth 1 --branch "v$version" https://chromium.googlesource.com/webm/libvpx "$source_dir"
fi

configure_flags=(
  --target=x86-win32-gcc
  --prefix="$install_dir"
  --disable-docs
  --disable-examples
  --disable-tools
  --disable-unit-tests
  --disable-webm-io
  --enable-vp8
  --enable-vp9
  --enable-static
  --disable-shared
)
pushd "$source_dir" >/dev/null
make clean >/dev/null 2>&1 || true
CROSS=i686-w64-mingw32- ./configure "${configure_flags[@]}"
make -j"$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)"
make install
popd >/dev/null
