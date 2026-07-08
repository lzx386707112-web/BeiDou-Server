#!/usr/bin/env python3
"""Make BeiDou.exe route Hero 1121001 through Brandish client logic.

1121001 has been repurposed from Monster Magnet to a Brandish-like attack.
The WZ data can match 1121008 exactly, but BeiDou.exe still has hard-coded
branches that only recognize 1121008. This patch adds 1121001 to those
branches without replacing or breaking 1121008, then plays Sword Illusion's
attack-stage visual after the startup effect.

Sword Illusion's copied first-stage effect is reshaped into Brandish-style
effect/0 and effect/1 variants, while effect0 is mirrored to effect/2 for
old-client compatibility. The old client does not load an `effect0` name
directly, so the visual tail explicitly selects effect/2 and plays it on the
normal character effect layer.
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
SWORD_ILLUSION_ATTACK_EFFECT_INDEX = 2
DEFAULT_VISUAL_TARGET = 0x0093587C
BRANDISH_VISUAL_TARGET = 0x0093465F
TEST_VISUAL_TARGET = BRANDISH_VISUAL_TARGET

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
    Hook(
        "Brandish visual exit effect0",
        0x00934720,
        bytes.fromhex("e9 23 13 00 00"),
    ),
]


def u32(value: int) -> bytes:
    return struct.pack("<I", value)


def rel32(src_va: int, dst_va: int, instr_len: int = 5) -> bytes:
    return struct.pack("<i", dst_va - (src_va + instr_len))


def jmp(src_va: int, dst_va: int) -> bytes:
    return b"\xE9" + rel32(src_va, dst_va)


def call(src_va: int, dst_va: int) -> bytes:
    return b"\xE8" + rel32(src_va, dst_va)


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


def build_cave(
    use_legacy_short_jg: bool = False,
    test_visual_target: int = TEST_VISUAL_TARGET,
    include_effect0_exit: bool = True,
) -> tuple[bytes, dict[str, int]]:
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
    block += je(va, test_visual_target)
    va += 6
    block += cmp_esi(BRANDISH)
    va += 6
    block += je(va, BRANDISH_VISUAL_TARGET)
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

    # 0x934720: Brandish visual branch exit. Let normal Brandish exit
    # unchanged, but for 1121001 play effect/2 after the startup effect.
    # effect/2 is a compatibility mirror of the original effect0 node.
    if include_effect0_exit:
        block = bytearray()
        va = CAVE_VA + len(out) + len(block)
        block += b"\x8B\x45\x08"  # mov eax, [ebp+0x8]
        va += 3
        block += b"\x81\x38" + u32(TEST_SKILL)  # cmp dword ptr [eax], 1121001
        va += 6
        play_va_placeholder = va
        block += je(va, 0)
        va += 6
        block += jmp(va, 0x00935A48)
        va += 5
        play_va = va
        block[play_va_placeholder - (CAVE_VA + len(out)) + 2 : play_va_placeholder - (CAVE_VA + len(out)) + 6] = rel32(
            play_va_placeholder,
            play_va,
            6,
        )

        block += b"\x8D\x4D\xE8"  # lea ecx, [ebp-0x18]
        va += 3
        block += call(va, 0x00402D9A)  # release current effect resource
        va += 5
        block += b"\x8B\x4D\x08"  # mov ecx, [ebp+0x8]
        va += 3
        block += b"\x6A" + bytes([SWORD_ILLUSION_ATTACK_EFFECT_INDEX])  # push 2
        va += 2
        block += b"\x8D\x45\xE8"  # lea eax, [ebp-0x18]
        va += 3
        block += b"\x50"  # push eax
        va += 1
        block += call(va, 0x00932D40)  # select effect/2
        va += 5

        # If effect/2 is absent, leave cleanly.
        block += b"\x8B\x45\xE8"  # mov eax, [ebp-0x18]
        va += 3
        block += b"\x85\xC0"  # test eax, eax
        va += 2
        done_jump_offsets: list[tuple[int, int]] = []
        done_jump_offsets.append((len(block), va))
        block += b"\x0F\x84\x00\x00\x00\x00"
        va += 6
        block += b"\x8B\x00"  # mov eax, [eax]
        va += 2
        block += b"\x85\xC0"  # test eax, eax
        va += 2
        done_jump_offsets.append((len(block), va))
        block += b"\x0F\x84\x00\x00\x00\x00"
        va += 6
        block += b"\x8B\x40\xFC"  # mov eax, [eax-4]
        va += 3
        block += b"\xD1\xE8"  # shr eax, 1
        va += 2
        block += b"\x85\xC0"  # test eax, eax
        va += 2
        done_jump_offsets.append((len(block), va))
        block += b"\x0F\x84\x00\x00\x00\x00"
        va += 6

        # Play the selected resource on the normal character effect layer.
        block += b"\x6A\x03"  # push 3
        va += 2
        block += b"\x68\xFF\xFF\xFF\x7F"  # push 0x7fffffff
        va += 5
        block += b"\x68\xE8\x03\x00\x00"  # push 1000
        va += 5
        block += b"\x6A\x10"  # push 0x10
        va += 2
        block += b"\x59"  # pop ecx
        va += 1
        block += b"\x51"  # push ecx
        va += 1
        block += b"\x8D\x83\x50\x11\x00\x00"  # lea eax, [ebx+0x1150]
        va += 6
        block += b"\x8B\xCC"  # mov ecx, esp
        va += 2
        block += b"\x89\x65\x10"  # mov [ebp+0x10], esp
        va += 3
        block += b"\x50"  # push eax
        va += 1
        block += call(va, 0x004145AB)
        va += 5
        block += b"\x51"  # push ecx
        va += 1
        block += b"\x8B\xC4"  # mov eax, esp
        va += 2
        block += b"\x89\x65\x18"  # mov [ebp+0x18], esp
        va += 3
        block += b"\x50"  # push eax
        va += 1
        block += b"\x8B\xCB"  # mov ecx, ebx
        va += 2
        block += b"\xC6\x45\xFC\x2E"  # mov byte ptr [ebp-4], 0x2e
        va += 4
        block += call(va, 0x004AD42B)
        va += 5
        block += b"\x8B\x45\x14"  # mov eax, [ebp+0x14]
        va += 3
        block += b"\x83\xF0\x01"  # xor eax, 1; effect0 source faces opposite
        va += 3
        block += b"\x50"  # push eax
        va += 1
        block += b"\x8D\x4D\xE8"  # lea ecx, [ebp-0x18]
        va += 3
        block += b"\xC6\x45\xFC\x01"  # mov byte ptr [ebp-4], 1
        va += 4
        block += call(va, 0x0040B31F)
        va += 5
        block += b"\x50"  # push eax
        va += 1
        block += call(va, 0x00432CBC)
        va += 5
        block += b"\x8B\xC8"  # mov ecx, eax
        va += 2
        block += call(va, 0x0043D72A)
        va += 5

        done_va = va
        for offset, src_va in done_jump_offsets:
            block[offset + 2 : offset + 6] = rel32(src_va, done_va, 6)
        block += jmp(va, 0x00935A48)
        add(HOOKS[5].name, bytes(block))

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
    no_effect0_cave, no_effect0_starts = build_cave(include_effect0_exit=False)
    old_visual_cave, old_visual_starts = build_cave(test_visual_target=DEFAULT_VISUAL_TARGET)
    old_visual_no_effect0_cave, old_visual_no_effect0_starts = build_cave(
        test_visual_target=DEFAULT_VISUAL_TARGET,
        include_effect0_exit=False,
    )
    legacy_cave, legacy_starts = build_cave(use_legacy_short_jg=True)
    legacy_no_effect0_cave, legacy_no_effect0_starts = build_cave(
        use_legacy_short_jg=True,
        include_effect0_exit=False,
    )
    legacy_old_visual_cave, legacy_old_visual_starts = build_cave(
        use_legacy_short_jg=True,
        test_visual_target=DEFAULT_VISUAL_TARGET,
    )
    legacy_old_visual_no_effect0_cave, legacy_old_visual_no_effect0_starts = build_cave(
        use_legacy_short_jg=True,
        test_visual_target=DEFAULT_VISUAL_TARGET,
        include_effect0_exit=False,
    )

    current_cave = bytes(data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE])
    already_cave = current_cave == cave
    effect0_upgrade_cave = current_cave[:0xA0] == cave[:0xA0]
    accepted_caves = {
        cave,
        no_effect0_cave,
        old_visual_cave,
        old_visual_no_effect0_cave,
        legacy_cave,
        legacy_no_effect0_cave,
        legacy_old_visual_cave,
        legacy_old_visual_no_effect0_cave,
    }
    if not already_cave and current_cave not in accepted_caves and not effect0_upgrade_cave and any(current_cave):
        raise RuntimeError(f"code cave is not empty at 0x{CAVE_OFFSET:x}")

    already_patched = already_cave
    for hook in HOOKS:
        patch = hook_patch(hook, starts[hook.name])
        no_effect0_patch = (
            hook_patch(hook, no_effect0_starts[hook.name])
            if hook.name in no_effect0_starts
            else hook.original
        )
        old_visual_patch = hook_patch(hook, old_visual_starts[hook.name])
        old_visual_no_effect0_patch = (
            hook_patch(hook, old_visual_no_effect0_starts[hook.name])
            if hook.name in old_visual_no_effect0_starts
            else hook.original
        )
        legacy_patch = hook_patch(hook, legacy_starts[hook.name])
        legacy_no_effect0_patch = (
            hook_patch(hook, legacy_no_effect0_starts[hook.name])
            if hook.name in legacy_no_effect0_starts
            else hook.original
        )
        legacy_old_visual_patch = hook_patch(hook, legacy_old_visual_starts[hook.name])
        legacy_old_visual_no_effect0_patch = (
            hook_patch(hook, legacy_old_visual_no_effect0_starts[hook.name])
            if hook.name in legacy_old_visual_no_effect0_starts
            else hook.original
        )
        current = bytes(data[hook.offset : hook.offset + len(hook.original)])
        if current == patch:
            continue
        if current in {
            no_effect0_patch,
            old_visual_patch,
            old_visual_no_effect0_patch,
            legacy_patch,
            legacy_no_effect0_patch,
            legacy_old_visual_patch,
            legacy_old_visual_no_effect0_patch,
        }:
            already_patched = False
            continue
        already_patched = False
        if current != hook.original:
            raise RuntimeError(
                f"{hook.name} unexpected bytes at 0x{hook.offset:x}: "
                f"{current.hex()} expected {hook.original.hex()} or {patch.hex()}"
            )

    if already_patched:
        print("BeiDou.exe already routes 1121001 through Brandish attack logic and effect/2 attack visual.")
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
    print("patched BeiDou.exe: 1121001 now follows Brandish attack logic and effect/2 attack visual")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
