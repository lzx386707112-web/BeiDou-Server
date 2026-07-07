#!/usr/bin/env python3
"""Stop BeiDou.exe from treating Hero 1121001 as Monster Magnet.

1121001 is being repurposed as a normal attack skill. The client has several
hard-coded Monster Magnet checks for the warrior trio:
1121001 / 1221001 / 1321001. Patch only the Hero immediate value to an unused
nearby sentinel so Paladin and Dark Knight Monster Magnet remain unchanged.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "clien" / "BeiDou.exe"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-1121001-not-magnet"

ORIGINAL_ID = 1121001
SENTINEL_ID = 1121099

OFFSETS = [
    0x0FB0AA,
    0x100990,
    0x268DB8,
    0x2722F5,
    0x5339DE,
    0x537B43,
    0x553606,
    0x559292,
    0x55C011,
    0x55C45D,
    0x55F97F,
    0x56A9AF,
    0x56AAEE,
    0x56B07C,
]


def le32(value: int) -> bytes:
    return struct.pack("<I", value)


def patch(dry_run: bool) -> int:
    data = bytearray(EXE.read_bytes())
    original = le32(ORIGINAL_ID)
    sentinel = le32(SENTINEL_ID)

    patched = 0
    for offset in OFFSETS:
        current = bytes(data[offset : offset + 4])
        if current == sentinel:
            patched += 1
            continue
        if current != original:
            raise RuntimeError(
                f"unexpected bytes at 0x{offset:x}: {current.hex()} "
                f"(expected {original.hex()} or {sentinel.hex()})"
            )
        if not dry_run:
            data[offset : offset + 4] = sentinel
        patched += 1

    if dry_run:
        print(f"would patch {patched} Hero Monster Magnet checks in {EXE}")
        return 0

    if not BACKUP.exists():
        shutil.copy2(EXE, BACKUP)
        print(f"backup: {BACKUP}")

    EXE.write_bytes(data)
    print(f"patched {patched} Hero Monster Magnet checks in {EXE}")
    return 0


def restore(dry_run: bool) -> int:
    if not BACKUP.exists():
        raise RuntimeError(f"backup does not exist: {BACKUP}")
    if dry_run:
        print(f"would restore {EXE} from {BACKUP}")
        return 0
    shutil.copy2(BACKUP, EXE)
    print(f"restored {EXE} from {BACKUP}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    if args.restore:
        return restore(args.dry_run)
    return patch(args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
