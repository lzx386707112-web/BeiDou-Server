#!/usr/bin/env python3
"""Let BeiDou.exe treat Hero 1121013 as a Brandish-compatible attack.

The previous 1121012 Death Fault patch filled the old 0xAEFB00 cave almost
completely.  This script relocates the Brandish-compatible Hero attack cave to
fresh space, preserves the 1121001 effect/2 tail, adds 1121013 to the same
client-side release/action branches as Brandish, and routes 1121013's visual
branch through the default effect path.  Extra top-level visuals are mirrored
to effect/90..91 and played independently by the existing screen-effect tail.
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
import patch_skill_screen_effect_slots as screen_effects  # noqa: E402


EXE = ROOT / "clien" / "BeiDou.exe"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-1121013-raging-blow-vi-attack"

IMAGE_BASE = legacy.IMAGE_BASE
DEATH_FAULT = death_fault.DEATH_FAULT
RAGING_BLOW_VI = 1121013
BRANDISH = legacy.BRANDISH

CAVE_VA = 0x00AEFE30
CAVE_OFFSET = CAVE_VA - IMAGE_BASE
CAVE_SIZE = 0x1C0

HELPER_CAVE_VA = legacy.CAVE_VA
HELPER_CAVE_OFFSET = legacy.CAVE_OFFSET
HELPER_CAVE_SIZE = legacy.CAVE_SIZE

SCREEN_TAIL_HOOK_VA = screen_effects.CAVE_VA + 0x9C
SCREEN_TAIL_HOOK_OFFSET = SCREEN_TAIL_HOOK_VA - IMAGE_BASE
SCREEN_TAIL_HOOK_ORIGINAL = bytes.fromhex(
    "58 89 45 18 58 89 45 10 61 8b 45 c8 3b c7 e9 c4 5a e4 ff"
)



def build_visual_exit_block(base_va: int) -> bytes:
    block = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str, int, int]] = []

    def here() -> int:
        return base_va + len(block)

    def mark(name: str) -> None:
        labels[name] = here()

    def add(data: bytes) -> None:
        block.extend(data)

    def add_je(label: str) -> None:
        fixups.append((len(block), label, 6, 2))
        add(b"\x0F\x84\x00\x00\x00\x00")

    def add_jmp(label: str) -> None:
        fixups.append((len(block), label, 5, 1))
        add(b"\xE9\x00\x00\x00\x00")

    selector_helper_va = HELPER_CAVE_VA
    # 0x934720: Brandish visual branch exit. Normal Brandish-compatible visual
    # handling has already queued effect/0. 1121001 keeps its legacy effect/2
    # tail here. 1121013 uses the default flat visual path and the existing
    # effect/90..91 screen-tail compatibility slots for independent extras.
    add(b"\x8B\x45\x08")  # mov eax, [ebp+0x8]
    add(b"\x81\x38" + legacy.u32(legacy.TEST_SKILL))  # cmp dword ptr [eax], 1121001
    add_je("play_1121001")
    add_jmp("done")

    mark("play_1121001")
    add(b"\x6A" + bytes([legacy.SWORD_ILLUSION_ATTACK_EFFECT_INDEX]))
    add(legacy.call(here(), selector_helper_va))
    add_jmp("done")

    mark("done")
    add(legacy.jmp(here(), 0x00935A48))

    for offset, label, instr_len, rel_offset in fixups:
        src_va = base_va + offset
        dst_va = labels[label]
        block[offset + rel_offset : offset + instr_len] = legacy.rel32(src_va, dst_va, instr_len)

    return bytes(block)


def build_effect_selector_helper() -> bytes:
    block = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str, int, int]] = []

    def here() -> int:
        return HELPER_CAVE_VA + len(block)

    def mark(name: str) -> None:
        labels[name] = here()

    def add(data: bytes) -> None:
        block.extend(data)

    def add_je(label: str) -> None:
        fixups.append((len(block), label, 6, 2))
        add(b"\x0F\x84\x00\x00\x00\x00")

    add(b"\x56")  # push esi
    add(b"\xFF\x75\x10")  # save original [ebp+0x10]
    add(b"\xFF\x75\x18")  # save original [ebp+0x18]
    add(b"\x83\xEC\x04")  # local selected-resource ref
    add(b"\xC7\x04\x24\x00\x00\x00\x00")
    add(b"\x8B\xF4")  # mov esi, esp

    add(b"\x8B\x4D\x08")
    add(b"\xFF\x74\x24\x14")  # push selected effect index argument
    add(b"\x56")  # push selected-resource ref
    add(legacy.call(here(), 0x00932D40))

    add(b"\x8B\x06")
    add(b"\x85\xC0")
    add_je("helper_cleanup")
    add(b"\x8B\x00")
    add(b"\x85\xC0")
    add_je("helper_cleanup")
    add(b"\x8B\x40\xFC")
    add(b"\xD1\xE8")
    add(b"\x85\xC0")
    add_je("helper_cleanup")

    add(b"\x6A\x03")
    add(b"\x68\xFF\xFF\xFF\x7F")
    add(b"\x68\xE8\x03\x00\x00")
    add(b"\x6A\x10")
    add(b"\x59")
    add(b"\x51")
    add(b"\x8D\x83\x50\x11\x00\x00")
    add(b"\x8B\xCC")
    add(b"\x89\x65\x10")
    add(b"\x50")
    add(legacy.call(here(), 0x004145AB))
    add(b"\x51")
    add(b"\x8B\xC4")
    add(b"\x89\x65\x18")
    add(b"\x50")
    add(b"\x8B\xCB")
    add(b"\xC6\x45\xFC\x2E")
    add(legacy.call(here(), 0x004AD42B))
    add(b"\x8B\x45\x14")
    add(b"\x83\xF0\x01")
    add(b"\x50")
    add(b"\x8B\xCE")
    add(b"\xC6\x45\xFC\x01")
    add(legacy.call(here(), 0x0040B31F))
    add(b"\x50")
    add(legacy.call(here(), 0x00432CBC))
    add(b"\x8B\xC8")
    add(legacy.call(here(), 0x0043D72A))

    mark("helper_cleanup")
    add(b"\x8B\xCE")
    add(legacy.call(here(), 0x00402D9A))
    add(b"\x83\xC4\x04")
    add(b"\x58")
    add(b"\x89\x45\x18")
    add(b"\x58")
    add(b"\x89\x45\x10")
    add(b"\x5E")
    add(b"\xC2\x04\x00")  # ret 4

    for offset, label, instr_len, rel_offset in fixups:
        src_va = HELPER_CAVE_VA + offset
        dst_va = labels[label]
        block[offset + rel_offset : offset + instr_len] = legacy.rel32(src_va, dst_va, instr_len)

    if len(block) > HELPER_CAVE_SIZE:
        raise RuntimeError(f"selector helper too large: need {len(block)} bytes, have {HELPER_CAVE_SIZE}")
    return bytes(block)


def build_effect_helpers() -> bytes:
    selector = build_effect_selector_helper()
    block = bytearray(selector)
    if len(block) > HELPER_CAVE_SIZE:
        raise RuntimeError(f"helper cave too small: need {len(block)} bytes, have {HELPER_CAVE_SIZE}")
    block.extend(b"\x00" * (HELPER_CAVE_SIZE - len(block)))
    return bytes(block)


def screen_tail_hook_patch(tail_va: int) -> bytes:
    patch = legacy.jmp(SCREEN_TAIL_HOOK_VA, tail_va)
    patch += b"\x90" * (len(SCREEN_TAIL_HOOK_ORIGINAL) - len(patch))
    return patch


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
        (RAGING_BLOW_VI, legacy.DEFAULT_VISUAL_TARGET),
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

    add(legacy.HOOKS[5].name, build_visual_exit_block(CAVE_VA + len(out)))

    if len(out) > CAVE_SIZE:
        raise RuntimeError(f"relocated cave too small: need {len(out)} bytes, have {CAVE_SIZE}")
    out.extend(b"\x00" * (CAVE_SIZE - len(out)))
    return bytes(out), starts


def accepted_hook_patches(hook: legacy.Hook) -> set[bytes]:
    patches = death_fault.accepted_hook_patches(hook)
    _, starts = build_cave()
    patches.add(legacy.hook_patch(hook, starts[hook.name]))
    return patches


def hooks_are_owned_by_raging_blow_patch(data: bytes, starts: dict[str, int]) -> bool:
    return all(
        bytes(data[hook.offset : hook.offset + len(hook.original)])
        == legacy.hook_patch(hook, starts[hook.name])
        for hook in legacy.HOOKS
    )


def patch_exe(dry_run: bool) -> None:
    data = bytearray(EXE.read_bytes())
    cave, starts = build_cave()
    helper_cave = build_effect_helpers()
    old_tail_patch = screen_tail_hook_patch(0x00AEFF69)
    tail_patch = SCREEN_TAIL_HOOK_ORIGINAL

    current_cave = bytes(data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE])
    current_helper_cave = bytes(data[HELPER_CAVE_OFFSET : HELPER_CAVE_OFFSET + HELPER_CAVE_SIZE])
    current_tail_hook = bytes(data[SCREEN_TAIL_HOOK_OFFSET : SCREEN_TAIL_HOOK_OFFSET + len(tail_patch)])
    if current_cave != cave and any(current_cave) and not hooks_are_owned_by_raging_blow_patch(data, starts):
        raise RuntimeError(f"new code cave is not empty at VA 0x{CAVE_VA:x}")
    if (
        current_helper_cave != helper_cave
        and any(current_helper_cave)
        and not hooks_are_owned_by_raging_blow_patch(data, starts)
    ):
        raise RuntimeError(f"helper code cave is not safely reusable at VA 0x{HELPER_CAVE_VA:x}")
    if current_tail_hook not in {SCREEN_TAIL_HOOK_ORIGINAL, old_tail_patch}:
        raise RuntimeError(
            f"screen tail hook has unexpected bytes at VA 0x{SCREEN_TAIL_HOOK_VA:x}: "
            f"{current_tail_hook.hex()}"
        )

    already = current_cave == cave and current_helper_cave == helper_cave and current_tail_hook == tail_patch
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
        print("BeiDou.exe already recognizes 1121013 and routes it through the default visual branch.")
        return

    print(
        f"Will patch BeiDou.exe 1121013 attack logic at relocated cave VA 0x{CAVE_VA:x}, "
        f"bytes {len(cave)}, helper VA 0x{HELPER_CAVE_VA:x}, helper bytes {len(helper_cave)}"
    )
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
    data[HELPER_CAVE_OFFSET : HELPER_CAVE_OFFSET + HELPER_CAVE_SIZE] = helper_cave
    data[SCREEN_TAIL_HOOK_OFFSET : SCREEN_TAIL_HOOK_OFFSET + len(tail_patch)] = tail_patch
    EXE.write_bytes(data)
    print("patched BeiDou.exe: 1121013 now follows Raging Blow VI attack logic and uses the default visual branch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    patch_exe(args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
