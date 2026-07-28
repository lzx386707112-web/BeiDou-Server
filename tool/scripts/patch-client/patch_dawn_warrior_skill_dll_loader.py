#!/usr/bin/env python3
"""Patch BeiDou.exe startup to load DawnWarriorSkillCompat.dll.

Only the loader lives in the EXE. All skill compatibility hooks live in the
new DLL; ijl15.dll is not modified.
"""

from __future__ import annotations

import argparse
import shutil
import struct
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "clien" / "BeiDou.exe"
DLL = ROOT / "clien" / "DawnWarriorSkillCompat.dll"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-dawn-warrior-skill-dll-loader"

IMAGE_BASE = 0x00400000
ENTRY_VA = 0x00A63FF3
ENTRY_OFFSET = ENTRY_VA - IMAGE_BASE
ENTRY_ORIGINAL = bytes.fromhex("55 8B EC 6A FF")
ENTRY_RETURN_VA = ENTRY_VA + len(ENTRY_ORIGINAL)

CAVE_VA = 0x00AEFA20
CAVE_OFFSET = CAVE_VA - IMAGE_BASE
CAVE_SIZE = 0x80
DLL_NAME_OFFSET = 0x48
DLL_NAME = b"DawnWarriorSkillCompat.dll\x00"
LOAD_LIBRARY_A_IAT = 0x00AF00C0


def rel32(source: int, target: int, size: int = 5) -> bytes:
    return struct.pack("<i", target - (source + size))


def jump(source: int, target: int) -> bytes:
    return b"\xE9" + rel32(source, target)


def build_cave() -> bytes:
    name_va = CAVE_VA + DLL_NAME_OFFSET
    code = bytearray()
    code += b"\x9C\x60"  # pushfd; pushad
    code += b"\x68" + struct.pack("<I", name_va)
    code += b"\xFF\x15" + struct.pack("<I", LOAD_LIBRARY_A_IAT)
    code += b"\x61\x9D"  # popad; popfd
    code += ENTRY_ORIGINAL
    code += jump(CAVE_VA + len(code), ENTRY_RETURN_VA)
    if len(code) > DLL_NAME_OFFSET:
        raise RuntimeError("loader code overlaps DLL name")
    code += b"\x00" * (DLL_NAME_OFFSET - len(code))
    code += DLL_NAME
    if len(code) > CAVE_SIZE:
        raise RuntimeError("loader cave is too small")
    return bytes(code) + b"\x00" * (CAVE_SIZE - len(code))


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        temp = Path(tmp.name)
    temp.replace(path)


def patch(dry_run: bool) -> None:
    if not DLL.exists():
        raise RuntimeError(f"build the DLL first: {DLL}")
    data = bytearray(EXE.read_bytes())
    loader = build_cave()
    entry_patch = jump(ENTRY_VA, CAVE_VA)
    current_entry = bytes(data[ENTRY_OFFSET:ENTRY_OFFSET + len(ENTRY_ORIGINAL)])
    current_cave = bytes(data[CAVE_OFFSET:CAVE_OFFSET + CAVE_SIZE])
    if current_entry == entry_patch and current_cave == loader:
        print("BeiDou.exe already loads DawnWarriorSkillCompat.dll")
        return
    if current_entry != ENTRY_ORIGINAL:
        raise RuntimeError(f"unexpected entrypoint bytes: {current_entry.hex(' ')}")
    if any(current_cave):
        raise RuntimeError("loader code cave is occupied; refusing to overwrite it")
    if dry_run:
        print(f"would patch BeiDou.exe entrypoint {ENTRY_VA:#x} to load {DLL.name}")
        return
    if not BACKUP.exists():
        shutil.copy2(EXE, BACKUP)
        print(f"backup: {BACKUP}")
    data[ENTRY_OFFSET:ENTRY_OFFSET + len(entry_patch)] = entry_patch
    data[CAVE_OFFSET:CAVE_OFFSET + CAVE_SIZE] = loader
    atomic_write(EXE, bytes(data))
    print(f"patched BeiDou.exe startup loader: {DLL.name}")


def restore(dry_run: bool) -> None:
    if not BACKUP.exists():
        raise RuntimeError(f"missing backup: {BACKUP}")
    if dry_run:
        print(f"would restore {EXE} from {BACKUP}")
        return
    shutil.copy2(BACKUP, EXE)
    print(f"restored: {EXE}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.restore:
        restore(args.dry_run)
    else:
        patch(args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
