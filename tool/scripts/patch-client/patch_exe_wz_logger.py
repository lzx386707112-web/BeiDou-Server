#!/usr/bin/env python3
"""Patch BeiDou.exe to load WzFileLogger.dll at process startup.

The patch is intentionally tiny and reversible:
- backup clien/BeiDou.exe before modifying it
- replace the first 5 entrypoint bytes with a jump to an unused zero cave
- in the cave, LoadLibraryA("WzFileLogger.dll"), replay the overwritten bytes,
  then jump back to the original entrypoint flow
"""

from __future__ import annotations

import argparse
import shutil
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXE_PATH = ROOT / "clien" / "BeiDou.exe"
BACKUP_PATH = ROOT / "clien" / "BeiDou.exe.bak-wz-logger"

IMAGE_BASE = 0x00400000
ENTRY_VA = 0x00A63FF3
ENTRY_OFFSET = 0x00663FF3
ENTRY_ORIGINAL = bytes.fromhex("55 8B EC 6A FF")
ENTRY_RETURN_VA = ENTRY_VA + len(ENTRY_ORIGINAL)

CAVE_VA = 0x00AEFA20
CAVE_OFFSET = 0x006EFA20
CAVE_SIZE = 0x80
DLL_NAME_OFFSET = 0x50
DLL_NAME = b"WzFileLogger.dll\x00"
COMPAT_LOADER_NAME = b"DawnWarriorSkillCompat.dll\x00"

LOAD_LIBRARY_A_IAT = 0x00AF00C0


def rel32(src_va: int, dst_va: int, instr_len: int = 5) -> bytes:
    return struct.pack("<i", dst_va - (src_va + instr_len))


def jmp_rel32(src_va: int, dst_va: int) -> bytes:
    return b"\xE9" + rel32(src_va, dst_va)


def build_cave() -> bytes:
    dll_name_va = CAVE_VA + DLL_NAME_OFFSET
    code = bytearray()
    code += b"\x9C"  # pushfd
    code += b"\x60"  # pushad
    code += b"\x68" + struct.pack("<I", dll_name_va)
    code += b"\xFF\x15" + struct.pack("<I", LOAD_LIBRARY_A_IAT)
    code += b"\x61"  # popad
    code += b"\x9D"  # popfd
    code += ENTRY_ORIGINAL
    code += jmp_rel32(CAVE_VA + len(code), ENTRY_RETURN_VA)

    if len(code) > DLL_NAME_OFFSET:
        raise RuntimeError("cave shellcode overlaps DLL name")
    code += b"\x00" * (DLL_NAME_OFFSET - len(code))
    code += DLL_NAME
    if len(code) > CAVE_SIZE:
        raise RuntimeError("cave shellcode is larger than reserved cave")
    code += b"\x00" * (CAVE_SIZE - len(code))
    return bytes(code)


def ensure_range(data: bytes, offset: int, size: int, label: str) -> None:
    if offset < 0 or offset + size > len(data):
        raise RuntimeError(f"{label} is outside file range")


def patch(dry_run: bool) -> int:
    data = bytearray(EXE_PATH.read_bytes())
    entry_jump = jmp_rel32(ENTRY_VA, CAVE_VA)
    cave = build_cave()

    ensure_range(data, ENTRY_OFFSET, len(ENTRY_ORIGINAL), "entrypoint")
    ensure_range(data, CAVE_OFFSET, CAVE_SIZE, "code cave")

    current_entry = bytes(data[ENTRY_OFFSET : ENTRY_OFFSET + len(ENTRY_ORIGINAL)])
    current_cave = bytes(data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE])

    already_patched = current_entry == entry_jump and current_cave == cave
    if already_patched:
        print("BeiDou.exe already has the WzFileLogger startup patch.")
        return 0

    if current_entry == entry_jump and COMPAT_LOADER_NAME in current_cave:
        print(
            "BeiDou.exe loads DawnWarriorSkillCompat.dll; that runtime loads "
            "WzFileLogger.dll without a second EXE patch."
        )
        return 0

    if current_entry != ENTRY_ORIGINAL:
        raise RuntimeError(
            "entrypoint bytes do not match the expected original bytes: "
            f"{current_entry.hex(' ')}"
        )
    if any(current_cave):
        raise RuntimeError("selected code cave is not empty; refusing to overwrite it")

    if dry_run:
        print(f"Would create backup: {BACKUP_PATH}")
        print(f"Would patch entrypoint {ENTRY_VA:#010x} -> {CAVE_VA:#010x}")
        print(f"Would write {len(cave)} bytes of loader code at {CAVE_VA:#010x}")
        return 0

    if not BACKUP_PATH.exists():
        shutil.copy2(EXE_PATH, BACKUP_PATH)
        print(f"Backup created: {BACKUP_PATH}")
    else:
        print(f"Backup already exists: {BACKUP_PATH}")

    data[ENTRY_OFFSET : ENTRY_OFFSET + len(entry_jump)] = entry_jump
    data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE] = cave
    EXE_PATH.write_bytes(data)

    print("Patched BeiDou.exe to load WzFileLogger.dll at startup.")
    print(f"Restore command: cp {BACKUP_PATH} {EXE_PATH}")
    return 0


def restore(dry_run: bool) -> int:
    if not BACKUP_PATH.exists():
        raise RuntimeError(f"backup does not exist: {BACKUP_PATH}")
    if dry_run:
        print(f"Would restore {EXE_PATH} from {BACKUP_PATH}")
        return 0
    shutil.copy2(BACKUP_PATH, EXE_PATH)
    print(f"Restored {EXE_PATH} from {BACKUP_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="validate only")
    parser.add_argument("--restore", action="store_true", help="restore backup")
    args = parser.parse_args()

    if not EXE_PATH.exists():
        raise RuntimeError(f"missing executable: {EXE_PATH}")

    if args.restore:
        return restore(args.dry_run)
    return patch(args.dry_run)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
