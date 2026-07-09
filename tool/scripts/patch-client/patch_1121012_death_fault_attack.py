#!/usr/bin/env python3
"""Let BeiDou.exe treat Hero 1121012 as a Brandish-compatible attack.

1121012's WZ data is independent from 1121001.  The overlap here is only in
the old client executable: Brandish-compatible melee attacks are gated by the
same hard-coded branch sites, and this patch preserves any existing cave at
those sites while adding 1121012.
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


EXE = ROOT / "clien" / "BeiDou.exe"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-1121012-death-fault-attack"

IMAGE_BASE = legacy.IMAGE_BASE
DEATH_FAULT = 1121012
BRANDISH = legacy.BRANDISH

CAVE_VA = legacy.CAVE_VA
CAVE_OFFSET = legacy.CAVE_OFFSET
CAVE_SIZE = legacy.CAVE_SIZE

def build_cave(death_fault_visual_target: int = legacy.BRANDISH_VISUAL_TARGET) -> tuple[bytes, dict[str, int]]:
    out = bytearray()
    starts: dict[str, int] = {}

    def here() -> int:
        return CAVE_VA + len(out)

    def add(name: str, data: bytes) -> None:
        starts[name] = here()
        out.extend(data)

    # 0x933ABF: Brandish visual branch.
    # 1121012 must use the normal Brandish visual path so its effect is
    # anchored to the character.  The older DEFAULT_VISUAL_TARGET route was
    # only for the abandoned effect/90 screen mirror experiment.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += legacy.cmp_esi(legacy.TEST_SKILL)
    va += 6
    block += legacy.je(va, legacy.TEST_VISUAL_TARGET)
    va += 6
    block += legacy.cmp_esi(DEATH_FAULT)
    va += 6
    block += legacy.je(va, death_fault_visual_target)
    va += 6
    block += legacy.cmp_esi(BRANDISH)
    va += 6
    block += legacy.je(va, legacy.BRANDISH_VISUAL_TARGET)
    va += 6
    block += legacy.jmp(va, legacy.HOOKS[0].return_va)
    add(legacy.HOOKS[0].name, bytes(block))

    # 0x950DE5: Brandish action type.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += legacy.cmp_eax(legacy.TEST_SKILL)
    va += 5
    block += legacy.je(va, 0x00950F74)
    va += 6
    block += legacy.cmp_eax(DEATH_FAULT)
    va += 5
    block += legacy.je(va, 0x00950F74)
    va += 6
    block += legacy.cmp_eax(BRANDISH)
    va += 5
    block += legacy.je(va, 0x00950F74)
    va += 6
    block += legacy.jmp(va, legacy.HOOKS[1].return_va)
    add(legacy.HOOKS[1].name, bytes(block))

    # 0x95255A: Brandish visual offset.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += legacy.cmp_eax(legacy.TEST_SKILL)
    va += 5
    block += legacy.je(va, 0x0095262C)
    va += 6
    block += legacy.cmp_eax(DEATH_FAULT)
    va += 5
    block += legacy.je(va, 0x0095262C)
    va += 6
    block += legacy.cmp_eax(BRANDISH)
    va += 5
    block += legacy.je(va, 0x0095262C)
    va += 6
    block += legacy.jmp(va, legacy.HOOKS[2].return_va)
    add(legacy.HOOKS[2].name, bytes(block))

    # 0x967A10: Brandish state switch.
    block = bytearray()
    va = CAVE_VA + len(out) + len(block)
    block += legacy.cmp_esi(legacy.TEST_SKILL)
    va += 6
    block += legacy.je(va, 0x009690AE)
    va += 6
    block += legacy.cmp_esi(DEATH_FAULT)
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
    block += legacy.cmp_ebx(legacy.TEST_SKILL)
    va += 6
    block += legacy.je(va, 0x0078E9E6)
    va += 6
    block += legacy.cmp_ebx(DEATH_FAULT)
    va += 6
    block += legacy.je(va, 0x0078E9E6)
    va += 6
    block += legacy.cmp_ebx(BRANDISH)
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
        raise RuntimeError(f"code cave too small: need {len(out)} bytes, have {CAVE_SIZE}")
    out.extend(b"\x00" * (CAVE_SIZE - len(out)))
    return bytes(out), starts


def accepted_legacy_caves() -> set[bytes]:
    caves = set()
    for death_fault_visual_target in (legacy.DEFAULT_VISUAL_TARGET, legacy.BRANDISH_VISUAL_TARGET):
        cave, _ = build_cave(death_fault_visual_target=death_fault_visual_target)
        caves.add(cave)
    for use_legacy_short_jg in (False, True):
        for test_visual_target in (legacy.TEST_VISUAL_TARGET, legacy.DEFAULT_VISUAL_TARGET):
            for include_effect0_exit in (False, True):
                cave, _ = legacy.build_cave(
                    use_legacy_short_jg=use_legacy_short_jg,
                    test_visual_target=test_visual_target,
                    include_effect0_exit=include_effect0_exit,
                )
                caves.add(cave)
    return caves


def accepted_hook_patches(hook: legacy.Hook) -> set[bytes]:
    patches = {hook.original}
    for death_fault_visual_target in (legacy.DEFAULT_VISUAL_TARGET, legacy.BRANDISH_VISUAL_TARGET):
        _, starts = build_cave(death_fault_visual_target=death_fault_visual_target)
        if hook.name in starts:
            patches.add(legacy.hook_patch(hook, starts[hook.name]))
    for use_legacy_short_jg in (False, True):
        for test_visual_target in (legacy.TEST_VISUAL_TARGET, legacy.DEFAULT_VISUAL_TARGET):
            for include_effect0_exit in (False, True):
                _, starts = legacy.build_cave(
                    use_legacy_short_jg=use_legacy_short_jg,
                    test_visual_target=test_visual_target,
                    include_effect0_exit=include_effect0_exit,
                )
                if hook.name in starts:
                    patches.add(legacy.hook_patch(hook, starts[hook.name]))
    return patches


def patch_exe(dry_run: bool) -> None:
    data = bytearray(EXE.read_bytes())
    cave, starts = build_cave()
    current_cave = bytes(data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE])
    if current_cave != cave and current_cave not in accepted_legacy_caves() and any(current_cave):
        raise RuntimeError(f"unexpected code cave bytes at VA 0x{CAVE_VA:x}")

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
                f"{current.hex()} expected original, legacy, or {patch.hex()}"
            )

    if already:
        print("BeiDou.exe already recognizes 1121012 as a Death Fault attack.")
        return

    print(f"Will patch BeiDou.exe 1121012 attack logic at cave VA 0x{CAVE_VA:x}, bytes {len(cave)}")
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
    print("patched BeiDou.exe: 1121012 now follows Death Fault attack logic")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    patch_exe(args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
