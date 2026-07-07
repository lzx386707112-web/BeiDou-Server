#!/usr/bin/env python3
"""Make BeiDou.exe route Hero 1121001 through Brandish client logic.

1121001 has been repurposed from Monster Magnet to a Brandish-like attack.
The WZ data can match 1121008 exactly, but BeiDou.exe still has hard-coded
branches that only recognize 1121008. This patch adds 1121001 to those
branches without replacing or breaking 1121008.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "clien" / "BeiDou.exe"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-1121001-as-brandish"

IMAGE_BASE = 0x00400000
TEST_SKILL = 1121001
BRANDISH = 1121008

CAVE_VA = 0x00AEFB00
CAVE_OFFSET = CAVE_VA - IMAGE_BASE
CAVE_SIZE = 0x180


@dataclass(frozen=True)
class Hook:
    name: str
    va: int
    original: bytes

    @property
    def offset(self) -> int:
        return self.va - IMAGE_BASE

    @property
    def return_va(self) -> int:
        return self.va + len(self.original)


HOOKS = [
    Hook(
        "Brandish skill branch",
        0x00933ABF,
        bytes.fromhex("81 fe f0 1a 11 00 0f 84 94 0b 00 00"),
    ),
    Hook(
        "Brandish action type",
        0x00950DE5,
        bytes.fromhex("3d f0 1a 11 00 0f 84 84 01 00 00"),
    ),
    Hook(
        "Brandish visual offset",
        0x0095255A,
        bytes.fromhex("3d f0 1a 11 00 0f 84 c7 00 00 00"),
    ),
    Hook(
        "Brandish state switch",
        0x00967A10,
        bytes.fromhex("b8 f0 1a 11 00 3b f0 7f 5b 0f 84 8f 16 00 00"),
    ),
    Hook(
        "Brandish hit randomization",
        0x0078E9D6,
        bytes.fromhex("81 fb f0 1a 11 00 74 08 81 fb 5c 8a a9 00 75 0d"),
    ),
]


def u32(value: int) -> bytes:
    return struct.pack("<I", value)


def rel32(src_va: int, dst_va: int, instr_len: int = 5) -> bytes:
    return struct.pack("<i", dst_va - (src_va + instr_len))


def jmp(src_va: int, dst_va: int) -> bytes:
    return b"\xE9" + rel32(src_va, dst_va)


def je(src_va: int, dst_va: int) -> bytes:
    return b"\x0F\x84" + rel32(src_va, dst_va, 6)


def jne(src_va: int, dst_va: int) -> bytes:
    return b"\x0F\x85" + rel32(src_va, dst_va, 6)


def jg(src_va: int, dst_va: int) -> bytes:
    return b"\x0F\x8F" + rel32(src_va, dst_va, 6)


def cmp_eax(value: int) -> bytes:
    return b"\x3D" + u32(value)


def cmp_ebx(value: int) -> bytes:
    return b"\x81\xFB" + u32(value)


def cmp_esi(value: int) -> bytes:
    return b"\x81\xFE" + u32(value)


def hook_patch(hook: Hook, cave_va: int) -> bytes:
    patch = jmp(hook.va, cave_va)
    patch += b"\x90" * (len(hook.original) - len(patch))
    return patch


def build_cave(use_legacy_short_jg: bool = False) -> tuple[bytes, dict[str, int]]:
    out = bytearray()
    starts: dict[str, int] = {}

    def here() -> int:
        return CAVE_VA + len(out)

    def add(name: str, data: bytes) -> None:
        starts[name] = here()
        out.extend(data)

    # 0x933ABF: cmp esi, 1121008; je 0x93465F
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += cmp_esi(TEST_SKILL)
    va += 6
    block += je(va, 0x0093465F)
    va += 6
    block += cmp_esi(BRANDISH)
    va += 6
    block += je(va, 0x0093465F)
    va += 6
    block += jmp(va, HOOKS[0].return_va)
    add(HOOKS[0].name, bytes(block))

    # 0x950DE5: cmp eax, 1121008; je 0x950F74
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += cmp_eax(TEST_SKILL)
    va += 5
    block += je(va, 0x00950F74)
    va += 6
    block += cmp_eax(BRANDISH)
    va += 5
    block += je(va, 0x00950F74)
    va += 6
    block += jmp(va, HOOKS[1].return_va)
    add(HOOKS[1].name, bytes(block))

    # 0x95255A: cmp eax, 1121008; je 0x95262C
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += cmp_eax(TEST_SKILL)
    va += 5
    block += je(va, 0x0095262C)
    va += 6
    block += cmp_eax(BRANDISH)
    va += 5
    block += je(va, 0x0095262C)
    va += 6
    block += jmp(va, HOOKS[2].return_va)
    add(HOOKS[2].name, bytes(block))

    # 0x967A10: mov eax, 1121008; cmp esi, eax; jg; je; ...
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += cmp_esi(TEST_SKILL)
    va += 6
    block += je(va, 0x009690AE)
    va += 6
    block += b"\xB8" + u32(BRANDISH)  # mov eax, 1121008
    va += 5
    block += b"\x3B\xF0"  # cmp esi, eax
    va += 2
    if use_legacy_short_jg:
        block += bytes([0x7F, (0x00967A74 - (va + 2)) & 0xFF])
        va += 2
    else:
        block += jg(va, 0x00967A74)
        va += 6
    block += je(va, 0x009690AE)
    va += 6
    block += jmp(va, HOOKS[3].return_va)
    add(HOOKS[3].name, bytes(block))

    # 0x78E9D6: cmp ebx, 1121008; je 0x78E9E6; cmp ebx, other; jne 0x78E9F3
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += cmp_ebx(TEST_SKILL)
    va += 6
    block += je(va, 0x0078E9E6)
    va += 6
    block += cmp_ebx(BRANDISH)
    va += 6
    block += je(va, 0x0078E9E6)
    va += 6
    block += cmp_ebx(0x00A98A5C)
    va += 6
    block += jne(va, 0x0078E9F3)
    va += 6
    block += jmp(va, 0x0078E9E6)
    add(HOOKS[4].name, bytes(block))

    if len(out) > CAVE_SIZE:
        raise RuntimeError(f"cave too small: need {len(out)} bytes, have {CAVE_SIZE}")
    out.extend(b"\x00" * (CAVE_SIZE - len(out)))
    return bytes(out), starts


def hex_at(data: bytes, offset: int, size: int) -> str:
    return data[offset : offset + size].hex()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = bytearray(EXE.read_bytes())
    cave, starts = build_cave()
    legacy_cave, legacy_starts = build_cave(use_legacy_short_jg=True)

    current_cave = bytes(data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE])
    already_cave = current_cave == cave
    legacy_cave_present = current_cave == legacy_cave
    if not already_cave and not legacy_cave_present and any(current_cave):
        raise RuntimeError(f"code cave is not empty at 0x{CAVE_OFFSET:x}")

    already_patched = already_cave
    for hook in HOOKS:
        patch = hook_patch(hook, starts[hook.name])
        legacy_patch = hook_patch(hook, legacy_starts[hook.name])
        current = bytes(data[hook.offset : hook.offset + len(hook.original)])
        if current == patch:
            continue
        if current == legacy_patch:
            already_patched = False
            continue
        already_patched = False
        if current != hook.original:
            raise RuntimeError(
                f"{hook.name} unexpected bytes at 0x{hook.offset:x}: "
                f"{current.hex()} expected {hook.original.hex()} or {patch.hex()}"
            )

    if already_patched:
        print("BeiDou.exe already routes 1121001 through Brandish logic.")
        return 0

    print(f"Using code cave VA 0x{CAVE_VA:x}, offset 0x{CAVE_OFFSET:x}, bytes {len(cave)}")
    for hook in HOOKS:
        print(f"{hook.name}: VA 0x{hook.va:x} -> cave VA 0x{starts[hook.name]:x}")

    if args.dry_run:
        print("[dry-run] no files written")
        return 0

    if not BACKUP.exists():
        shutil.copy2(EXE, BACKUP)
        print(f"backup: {BACKUP}")

    for hook in HOOKS:
        patch = hook_patch(hook, starts[hook.name])
        data[hook.offset : hook.offset + len(patch)] = patch
    data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE] = cave
    EXE.write_bytes(data)
    print("patched BeiDou.exe: 1121001 now follows Brandish client branches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
