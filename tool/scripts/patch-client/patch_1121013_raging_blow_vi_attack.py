#!/usr/bin/env python3
"""Let BeiDou.exe treat Hero 1121013 as a Brandish-compatible attack.

The previous 1121012 Death Fault patch filled the old 0xAEFB00 cave almost
completely.  This script relocates the Brandish-compatible Hero attack cave to
fresh space, preserves the 1121001 effect/2 tail, and adds 1121013 to the same
client-side release/action/visual branches as Brandish.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCH_CLIENT = ROOT / "tool" / "scripts" / "patch-client"
sys.path.insert(0, str(PATCH_CLIENT))

import patch_1121001_as_brandish as legacy  # noqa: E402
import patch_1121012_death_fault_attack as death_fault  # noqa: E402


EXE = ROOT / "clien" / "BeiDou.exe"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-1121013-raging-blow-vi-attack"

IMAGE_BASE = legacy.IMAGE_BASE
DEATH_FAULT = death_fault.DEATH_FAULT
RAGING_BLOW_VI = 1121013
BRANDISH = legacy.BRANDISH

CAVE_VA = 0x00AEFE30
CAVE_OFFSET = CAVE_VA - IMAGE_BASE
CAVE_SIZE = 0x1C0


def build_cave() -> tuple[bytes, dict[str, int]]:
    out = bytearray()
    starts: dict[str, int] = {}

    def add(name: str, data: bytes) -> None:
        starts[name] = CAVE_VA + len(out)
        out.extend(data)

    # 0x933ABF: Brandish visual branch.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    for skill_id, target_va in (
        (legacy.TEST_SKILL, legacy.TEST_VISUAL_TARGET),
        (DEATH_FAULT, legacy.BRANDISH_VISUAL_TARGET),
        (RAGING_BLOW_VI, legacy.BRANDISH_VISUAL_TARGET),
        (BRANDISH, legacy.BRANDISH_VISUAL_TARGET),
    ):
        block += legacy.cmp_esi(skill_id)
        va += 6
        block += legacy.je(va, target_va)
        va += 6
    block += legacy.jmp(va, legacy.HOOKS[0].return_va)
    add(legacy.HOOKS[0].name, bytes(block))

    # 0x950DE5: Brandish action type.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    for skill_id in (legacy.TEST_SKILL, DEATH_FAULT, RAGING_BLOW_VI, BRANDISH):
        block += legacy.cmp_eax(skill_id)
        va += 5
        block += legacy.je(va, 0x00950F74)
        va += 6
    block += legacy.jmp(va, legacy.HOOKS[1].return_va)
    add(legacy.HOOKS[1].name, bytes(block))

    # 0x95255A: Brandish visual offset.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    for skill_id in (legacy.TEST_SKILL, DEATH_FAULT, RAGING_BLOW_VI, BRANDISH):
        block += legacy.cmp_eax(skill_id)
        va += 5
        block += legacy.je(va, 0x0095262C)
        va += 6
    block += legacy.jmp(va, legacy.HOOKS[2].return_va)
    add(legacy.HOOKS[2].name, bytes(block))

    # 0x967A10: Brandish state switch.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    for skill_id in (legacy.TEST_SKILL, DEATH_FAULT, RAGING_BLOW_VI):
        block += legacy.cmp_esi(skill_id)
        va += 6
        block += legacy.je(va, 0x009690AE)
        va += 6
    block += b"\xB8" + legacy.u32(BRANDISH)
    va += 5
    block += b"\x3B\xF0"
    va += 2
    block += legacy.jg(va, 0x00967A74)
    va += 6
    block += legacy.je(va, 0x009690AE)
    va += 6
    block += legacy.jmp(va, legacy.HOOKS[3].return_va)
    add(legacy.HOOKS[3].name, bytes(block))

    # 0x78E9D6: Brandish hit randomization.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    for skill_id in (legacy.TEST_SKILL, DEATH_FAULT, RAGING_BLOW_VI, BRANDISH):
        block += legacy.cmp_ebx(skill_id)
        va += 6
        block += legacy.je(va, 0x0078E9E6)
        va += 6
    block += legacy.cmp_ebx(0x00A98A5C)
    va += 6
    block += legacy.jne(va, 0x0078E9F3)
    va += 6
    block += legacy.jmp(va, 0x0078E9E6)
    add(legacy.HOOKS[4].name, bytes(block))

    # 0x934720: preserve the existing 1121001-only effect/2 visual tail.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += b"\x8B\x45\x08"
    va += 3
    block += b"\x81\x38" + legacy.u32(legacy.TEST_SKILL)
    va += 6
    play_va_placeholder = va
    block += legacy.je(va, 0)
    va += 6
    block += legacy.jmp(va, 0x00935A48)
    va += 5
    play_va = va
    start = play_va_placeholder - (CAVE_VA + len(out))
    block[start + 2 : start + 6] = legacy.rel32(play_va_placeholder, play_va, 6)

    block += b"\x8D\x4D\xE8"
    va += 3
    block += legacy.call(va, 0x00402D9A)
    va += 5
    block += b"\x8B\x4D\x08"
    va += 3
    block += b"\x6A" + bytes([legacy.SWORD_ILLUSION_ATTACK_EFFECT_INDEX])
    va += 2
    block += b"\x8D\x45\xE8"
    va += 3
    block += b"\x50"
    va += 1
    block += legacy.call(va, 0x00932D40)
    va += 5

    block += b"\x8B\x45\xE8"
    va += 3
    block += b"\x85\xC0"
    va += 2
    done_jump_offsets: list[tuple[int, int]] = []
    done_jump_offsets.append((len(block), va))
    block += b"\x0F\x84\x00\x00\x00\x00"
    va += 6
    block += b"\x8B\x00"
    va += 2
    block += b"\x85\xC0"
    va += 2
    done_jump_offsets.append((len(block), va))
    block += b"\x0F\x84\x00\x00\x00\x00"
    va += 6
    block += b"\x8B\x40\xFC"
    va += 3
    block += b"\xD1\xE8"
    va += 2
    block += b"\x85\xC0"
    va += 2
    done_jump_offsets.append((len(block), va))
    block += b"\x0F\x84\x00\x00\x00\x00"
    va += 6

    block += b"\x6A\x03"
    va += 2
    block += b"\x68\xFF\xFF\xFF\x7F"
    va += 5
    block += b"\x68\xE8\x03\x00\x00"
    va += 5
    block += b"\x6A\x10"
    va += 2
    block += b"\x59"
    va += 1
    block += b"\x51"
    va += 1
    block += b"\x8D\x83\x50\x11\x00\x00"
    va += 6
    block += b"\x8B\xCC"
    va += 2
    block += b"\x89\x65\x10"
    va += 3
    block += b"\x50"
    va += 1
    block += legacy.call(va, 0x004145AB)
    va += 5
    block += b"\x51"
    va += 1
    block += b"\x8B\xC4"
    va += 2
    block += b"\x89\x65\x18"
    va += 3
    block += b"\x50"
    va += 1
    block += b"\x8B\xCB"
    va += 2
    block += b"\xC6\x45\xFC\x2E"
    va += 4
    block += legacy.call(va, 0x004AD42B)
    va += 5
    block += b"\x8B\x45\x14"
    va += 3
    block += b"\x83\xF0\x01"
    va += 3
    block += b"\x50"
    va += 1
    block += b"\x8D\x4D\xE8"
    va += 3
    block += b"\xC6\x45\xFC\x01"
    va += 4
    block += legacy.call(va, 0x0040B31F)
    va += 5
    block += b"\x50"
    va += 1
    block += legacy.call(va, 0x00432CBC)
    va += 5
    block += b"\x8B\xC8"
    va += 2
    block += legacy.call(va, 0x0043D72A)
    va += 5

    done_va = va
    for offset, src_va in done_jump_offsets:
        block[offset + 2 : offset + 6] = legacy.rel32(src_va, done_va, 6)
    block += legacy.jmp(va, 0x00935A48)
    add(legacy.HOOKS[5].name, bytes(block))

    if len(out) > CAVE_SIZE:
        raise RuntimeError(f"relocated cave too small: need {len(out)} bytes, have {CAVE_SIZE}")
    out.extend(b"\x00" * (CAVE_SIZE - len(out)))
    return bytes(out), starts


def accepted_hook_patches(hook: legacy.Hook) -> set[bytes]:
    patches = death_fault.accepted_hook_patches(hook)
    _, starts = build_cave()
    patches.add(legacy.hook_patch(hook, starts[hook.name]))
    return patches


def patch_exe(dry_run: bool) -> None:
    data = bytearray(EXE.read_bytes())
    cave, starts = build_cave()

    current_cave = bytes(data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE])
    if current_cave != cave and any(current_cave):
        raise RuntimeError(f"new code cave is not empty at VA 0x{CAVE_VA:x}")

    already = current_cave == cave
    for hook in legacy.HOOKS:
        patch = legacy.hook_patch(hook, starts[hook.name])
        current = bytes(data[hook.offset : hook.offset + len(hook.original)])
        if current == patch:
            continue
        already = False
        if current not in accepted_hook_patches(hook):
            raise RuntimeError(
                f"{hook.name} unexpected bytes at 0x{hook.offset:x}: "
                f"{current.hex()} expected original, 1121001/1121012 patch, or {patch.hex()}"
            )

    if already:
        print("BeiDou.exe already recognizes 1121013 as a Raging Blow VI attack.")
        return

    print(f"Will patch BeiDou.exe 1121013 attack logic at relocated cave VA 0x{CAVE_VA:x}, bytes {len(cave)}")
    for hook in legacy.HOOKS:
        print(f"{hook.name}: VA 0x{hook.va:x} -> cave VA 0x{starts[hook.name]:x}")
    if dry_run:
        print("[dry-run] no files written")
        return

    if not BACKUP.exists():
        shutil.copy2(EXE, BACKUP)
        print(f"backup: {BACKUP}")

    for hook in legacy.HOOKS:
        patch = legacy.hook_patch(hook, starts[hook.name])
        data[hook.offset : hook.offset + len(patch)] = patch
    data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE] = cave
    EXE.write_bytes(data)
    print("patched BeiDou.exe: 1121013 now follows Raging Blow VI attack logic")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    patch_exe(args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
