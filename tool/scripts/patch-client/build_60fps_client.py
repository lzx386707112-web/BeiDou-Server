#!/usr/bin/env python3
"""Create a 60 FPS BeiDou client copy without modifying BeiDou.exe."""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_EXE = ROOT / "clien" / "BeiDou.exe"
OUTPUT_EXE = ROOT / "clien" / "BeiDou-60FPS.exe"
COMPAT_DLL = ROOT / "clien" / "DawnWarriorSkillCompat.dll"
FPS_DLL = ROOT / "clien" / "BeiDouFpsLimit.dll"

IMAGE_BASE = 0x00400000
ENTRY_VA = 0x00A63FF3
ENTRY_OFFSET = ENTRY_VA - IMAGE_BASE
ENTRY_ORIGINAL = bytes.fromhex("55 8B EC 6A FF")
ENTRY_RETURN_VA = ENTRY_VA + len(ENTRY_ORIGINAL)

CAVE_VA = 0x00AEFA20
CAVE_OFFSET = CAVE_VA - IMAGE_BASE
CAVE_SIZE = 0x80
COMPAT_NAME_OFFSET = 0x30
FPS_NAME_OFFSET = 0x50
ORIGINAL_COMPAT_NAME_OFFSET = 0x48
COMPAT_NAME = b"DawnWarriorSkillCompat.dll\x00"
FPS_NAME = b"BeiDouFpsLimit.dll\x00"
LOAD_LIBRARY_A_IAT = 0x00AF00C0


def rel32(source: int, target: int, size: int = 5) -> bytes:
    return struct.pack("<i", target - (source + size))


def jump(source: int, target: int) -> bytes:
    return b"\xE9" + rel32(source, target)


def add_load_library(code: bytearray, name_va: int) -> None:
    code += b"\x68" + struct.pack("<I", name_va)
    code += b"\xFF\x15" + struct.pack("<I", LOAD_LIBRARY_A_IAT)


def build_original_cave() -> bytes:
    code = bytearray(b"\x9C\x60")
    add_load_library(code, CAVE_VA + ORIGINAL_COMPAT_NAME_OFFSET)
    code += b"\x61\x9D" + ENTRY_ORIGINAL
    code += jump(CAVE_VA + len(code), ENTRY_RETURN_VA)
    code += b"\x00" * (ORIGINAL_COMPAT_NAME_OFFSET - len(code))
    code += COMPAT_NAME
    return bytes(code) + b"\x00" * (CAVE_SIZE - len(code))


def build_60fps_cave() -> bytes:
    code = bytearray(b"\x9C\x60")
    add_load_library(code, CAVE_VA + COMPAT_NAME_OFFSET)
    add_load_library(code, CAVE_VA + FPS_NAME_OFFSET)
    code += b"\x61\x9D" + ENTRY_ORIGINAL
    code += jump(CAVE_VA + len(code), ENTRY_RETURN_VA)
    if len(code) > COMPAT_NAME_OFFSET:
        raise RuntimeError("loader code overlaps compatibility DLL name")
    code += b"\x00" * (COMPAT_NAME_OFFSET - len(code))
    code += COMPAT_NAME
    if len(code) > FPS_NAME_OFFSET:
        raise RuntimeError("compatibility DLL name overlaps FPS DLL name")
    code += b"\x00" * (FPS_NAME_OFFSET - len(code))
    code += FPS_NAME
    if len(code) > CAVE_SIZE:
        raise RuntimeError("60 FPS loader exceeds the existing code cave")
    return bytes(code) + b"\x00" * (CAVE_SIZE - len(code))


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    ) as temporary:
        temporary.write(data)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def main() -> int:
    for dependency in (SOURCE_EXE, COMPAT_DLL, FPS_DLL):
        if not dependency.is_file():
            raise RuntimeError(f"missing required client file: {dependency}")

    source = SOURCE_EXE.read_bytes()
    entry_patch = jump(ENTRY_VA, CAVE_VA)
    if source[ENTRY_OFFSET : ENTRY_OFFSET + len(entry_patch)] != entry_patch:
        raise RuntimeError("BeiDou.exe does not contain the expected compatibility loader entry")
    if source[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE] != build_original_cave():
        raise RuntimeError("BeiDou.exe compatibility loader differs from the audited layout")

    output = bytearray(source)
    output[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE] = build_60fps_cave()
    atomic_write(OUTPUT_EXE, output)

    generated = OUTPUT_EXE.read_bytes()
    if len(generated) != len(source):
        raise RuntimeError("generated executable size changed")
    if generated[:CAVE_OFFSET] != source[:CAVE_OFFSET] or generated[CAVE_OFFSET + CAVE_SIZE :] != source[CAVE_OFFSET + CAVE_SIZE :]:
        raise RuntimeError("generated executable changed bytes outside the loader cave")
    if SOURCE_EXE.read_bytes() != source:
        raise RuntimeError("source BeiDou.exe changed while generating the copy")

    print(f"generated: {OUTPUT_EXE}")
    print("original BeiDou.exe unchanged; copied client loads BeiDouFpsLimit.dll at 60 FPS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
