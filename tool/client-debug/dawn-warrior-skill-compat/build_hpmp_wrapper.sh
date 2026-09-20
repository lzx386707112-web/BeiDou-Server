#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/../../.." && pwd)"
source_file="$root_dir/tool/client-debug/dawn-warrior-skill-compat/HpMpExpansionWrapper.cpp"
primary_dll="$root_dir/clien/DawnWarriorSkillCompat.dll"
core_dll="$root_dir/clien/BeiDouSkillCompatCore.dll"
core_sha="3882737456d7c95795b2afe63ad91703cd70ef299c6b83fefe5f6f70764b466f"
build_dir="$(mktemp -d /tmp/beidou-hpmp-build.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

hash_file() {
  shasum -a 256 "$1" | cut -d ' ' -f 1
}

if [[ -f "$core_dll" ]] && [[ "$(hash_file "$core_dll")" == "$core_sha" ]]; then
  :
elif [[ -f "$primary_dll" ]] && [[ "$(hash_file "$primary_dll")" == "$core_sha" ]]; then
  cp "$primary_dll" "$core_dll"
else
  echo "verified compatibility core DLL is missing; refusing to build the HP/MP wrapper" >&2
  exit 1
fi

i686-w64-mingw32-g++ \
  -std=c++17 -Os -s -shared -nostdlib -fno-exceptions -fno-rtti \
  -fno-threadsafe-statics -Wl,--entry,_DllMain@12 -Wl,--subsystem,windows \
  -Wl,--no-insert-timestamp -Wl,--image-base,0x69040000 \
  -Wall -Wextra -Werror \
  "$source_file" -lkernel32 -luser32 -lgcc \
  -o "$build_dir/DawnWarriorSkillCompat.dll"

file "$build_dir/DawnWarriorSkillCompat.dll" | grep -q "PE32 executable (DLL).*Intel 80386"
mv "$build_dir/DawnWarriorSkillCompat.dll" "$primary_dll"
file "$primary_dll"
shasum -a 256 "$core_dll" "$primary_dll"
