#!/usr/bin/env python3
"""Restore BeiDou.exe's native flat effect playback for 1121001.

The experimental effect0 hook at 0x935896 can crash with a client data error
because it re-enters the animation builder with hand-made stack temporaries.
This restores the native `effect` branch while keeping the separate Brandish
attack/action routing patch intact.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "clien" / "BeiDou.exe"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-before-restore-1121001-default-effect"

IMAGE_BASE = 0x00400000

DEFAULT_HOOK_VA = 0x00935896
DEFAULT_ORIGINAL = bytes.fromhex("8b 45 10 83 c0 0a")
DEFAULT_HOOK_PATCH = bytes.fromhex("e9 e5 a3 1b 00 90")

OLD_EXIT_HOOK_VA = 0x00934720
OLD_EXIT_ORIGINAL = bytes.fromhex("e9 23 13 00 00")
OLD_EXIT_HOOK_PATCH = bytes.fromhex("e9 5b b5 1b 00")


def patch_bytes(data: bytearray, dry_run: bool) -> bool:
    default_offset = DEFAULT_HOOK_VA - IMAGE_BASE
    old_exit_offset = OLD_EXIT_HOOK_VA - IMAGE_BASE

    current_default = bytes(data[default_offset : default_offset + len(DEFAULT_ORIGINAL)])
    current_old_exit = bytes(data[old_exit_offset : old_exit_offset + len(OLD_EXIT_ORIGINAL)])

    if current_default == DEFAULT_ORIGINAL and current_old_exit == OLD_EXIT_ORIGINAL:
        print("BeiDou.exe already uses native flat effect playback.")
        return False

    if current_default not in {DEFAULT_ORIGINAL, DEFAULT_HOOK_PATCH}:
        raise RuntimeError(
            f"unexpected bytes at default hook 0x{default_offset:x}: "
            f"{current_default.hex()}"
        )
    if current_old_exit not in {OLD_EXIT_ORIGINAL, OLD_EXIT_HOOK_PATCH}:
        raise RuntimeError(
            f"unexpected bytes at old exit hook 0x{old_exit_offset:x}: "
            f"{current_old_exit.hex()}"
        )

    print("restoring native flat effect playback:")
    print(f"  VA 0x{DEFAULT_HOOK_VA:x}: {current_default.hex()} -> {DEFAULT_ORIGINAL.hex()}")
    print(f"  VA 0x{OLD_EXIT_HOOK_VA:x}: {current_old_exit.hex()} -> {OLD_EXIT_ORIGINAL.hex()}")
    if dry_run:
        print("[dry-run] no changes written")
        return False

    if not BACKUP.exists():
        shutil.copy2(EXE, BACKUP)
        print(f"backup: {BACKUP}")

    data[default_offset : default_offset + len(DEFAULT_ORIGINAL)] = DEFAULT_ORIGINAL
    data[old_exit_offset : old_exit_offset + len(OLD_EXIT_ORIGINAL)] = OLD_EXIT_ORIGINAL
    EXE.write_bytes(data)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = bytearray(EXE.read_bytes())
    changed = patch_bytes(data, args.dry_run)
    if changed:
        print("patched BeiDou.exe: disabled experimental effect0 hook for 1121001")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
