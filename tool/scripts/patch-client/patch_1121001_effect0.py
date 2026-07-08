#!/usr/bin/env python3
"""Make BeiDou.exe play Sword Illusion's effect and effect0 for 1121001.

Sword Illusion's copied resources are flat `effect` and `effect0` animations.
1121001 is routed to the normal flat visual branch, and this patch replaces
that branch's single `effect` playback for 1121001 with a small custom block
that plays both resources while preserving the original timing parameters.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "clien" / "BeiDou.exe"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-1121001-effect0"

IMAGE_BASE = 0x00400000
TEST_SKILL = 1121001

DEFAULT_HOOK_VA = 0x00935896
DEFAULT_HOOK_ORIGINAL = bytes.fromhex("8b 45 10 83 c0 0a")
DEFAULT_HOOK_RETURN_VA = 0x0093589C

OLD_EXIT_HOOK_VA = 0x00934720
OLD_EXIT_HOOK_ORIGINAL = bytes.fromhex("e9 23 13 00 00")

CAVE_VA = 0x00AEFC80
CAVE_OFFSET = CAVE_VA - IMAGE_BASE
CAVE_SIZE = 0x380


def u32(value: int) -> bytes:
    return struct.pack("<I", value)


def rel32(src_va: int, dst_va: int, instr_len: int = 5) -> bytes:
    return struct.pack("<i", dst_va - (src_va + instr_len))


def jmp(src_va: int, dst_va: int) -> bytes:
    return b"\xE9" + rel32(src_va, dst_va)


def je(src_va: int, dst_va: int) -> bytes:
    return b"\x0F\x84" + rel32(src_va, dst_va, 6)


def call(src_va: int, dst_va: int) -> bytes:
    return b"\xE8" + rel32(src_va, dst_va)


def cmp_esi(value: int) -> bytes:
    return b"\x81\xFE" + u32(value)


def build_old_exit_cave() -> bytes:
    out = bytearray()
    fixups: list[tuple[int, str, int]] = []
    labels: dict[str, int] = {}

    def here() -> int:
        return CAVE_VA + len(out)

    def mark(name: str) -> None:
        labels[name] = here()

    def add(data: bytes) -> None:
        out.extend(data)

    def add_je(label: str) -> None:
        fixups.append((len(out), label, 6))
        add(b"\x0F\x84\x00\x00\x00\x00")

    def add_jmp(label: str) -> None:
        fixups.append((len(out), label, 5))
        add(b"\xE9\x00\x00\x00\x00")

    # If this default-effect exit is not for 1121001, keep the original exit.
    add(cmp_esi(TEST_SKILL))
    add_je("play_effect0")
    add(jmp(here(), 0x00935A48))

    mark("play_effect0")
    # If the skill data did not load effect0, degrade to the original exit.
    add(b"\x83\xBB\x44\x11\x00\x00\x00")  # cmp dword ptr [ebx+0x1144], 0
    add_je("done")

    # Mirror the default effect playback block at 0x9346C6..0x93471B, but
    # request the extra effect0 animation resource at skill object +0x1144.
    add(b"\x8B\x45\x10")  # mov eax, [ebp+0x10]
    add(b"\x83\xC0\x0A")  # add eax, 0x0a
    add(b"\x69\xC0\xE8\x03\x00\x00")  # imul eax, eax, 0x3e8
    add(b"\x6A\x03")  # push 3
    add(b"\x68\xFF\xFF\xFF\x7F")  # push 0x7fffffff
    add(b"\x6A\x10")  # push 0x10
    add(b"\x59")  # pop ecx
    add(b"\x99")  # cdq
    add(b"\xF7\xF9")  # idiv ecx
    add(b"\x50")  # push eax
    add(b"\x51")  # push ecx
    add(b"\x8D\x83\x44\x11\x00\x00")  # lea eax, [ebx+0x1144]
    add(b"\x8B\xCC")  # mov ecx, esp
    add(b"\x89\x65\x10")  # mov [ebp+0x10], esp
    add(b"\x50")  # push eax
    add(call(here(), 0x004145AB))
    add(b"\x51")  # push ecx
    add(b"\x8B\xC4")  # mov eax, esp
    add(b"\x89\x65\x18")  # mov [ebp+0x18], esp
    add(b"\x50")  # push eax
    add(b"\x8B\xCB")  # mov ecx, ebx
    add(b"\xC6\x45\xFC\x2E")  # mov byte ptr [ebp-4], 0x2e
    add(call(here(), 0x004AD42B))
    add(b"\xFF\x75\x14")  # push [ebp+0x14]
    add(b"\x8D\x4D\xE8")  # lea ecx, [ebp-0x18]
    add(b"\xC6\x45\xFC\x01")  # mov byte ptr [ebp-4], 1
    add(call(here(), 0x0040B31F))
    add(b"\x50")  # push eax
    add(call(here(), 0x00432CBC))
    add(b"\x8B\xC8")  # mov ecx, eax
    add(call(here(), 0x0043D72A))

    mark("done")
    add(jmp(here(), 0x00935A48))

    for offset, label, instr_len in fixups:
        src_va = CAVE_VA + offset
        dst_va = labels[label]
        out[offset + 2 if instr_len == 6 else offset + 1 : offset + instr_len] = rel32(src_va, dst_va, instr_len)

    out.extend(b"\x00" * (0x100 - len(out)))
    return bytes(out)


def build_cave() -> bytes:
    out = bytearray()
    fixups: list[tuple[int, str, int]] = []
    labels: dict[str, int] = {}

    def here() -> int:
        return CAVE_VA + len(out)

    def mark(name: str) -> None:
        labels[name] = here()

    def add(data: bytes) -> None:
        out.extend(data)

    def add_je(label: str) -> None:
        fixups.append((len(out), label, 6))
        add(b"\x0F\x84\x00\x00\x00\x00")

    def add_jmp(label: str) -> None:
        fixups.append((len(out), label, 5))
        add(b"\xE9\x00\x00\x00\x00")

    def add_default_hook_original() -> None:
        add(b"\x8B\x45\x10")  # mov eax, [ebp+0x10]
        add(b"\x83\xC0\x0A")  # add eax, 0x0a

    def add_play_resource(resource_offset: int, skip_label: str | None = None) -> None:
        if skip_label is not None:
            add(b"\x83\xBB" + u32(resource_offset) + b"\x00")  # cmp dword ptr [ebx+offset], 0
            add_je(skip_label)

        add(b"\x8B\x45\x10")  # mov eax, [ebp+0x10]
        add(b"\x83\xC0\x0A")  # add eax, 0x0a
        add(b"\x69\xC0\xE8\x03\x00\x00")  # imul eax, eax, 0x3e8
        add(b"\x6A\x03")  # push 3
        add(b"\xFF\x75\x18")  # push [ebp+0x18]
        add(b"\x99")  # cdq
        add(b"\x6A\x10")  # push 0x10
        add(b"\x59")  # pop ecx
        add(b"\xF7\xF9")  # idiv ecx
        add(b"\x50")  # push eax
        add(b"\x51")  # push ecx
        add(b"\x8D\x83" + u32(resource_offset))  # lea eax, [ebx+offset]
        add(b"\x8B\xCC")  # mov ecx, esp
        add(b"\x89\x65\x10")  # mov [ebp+0x10], esp
        add(b"\x50")  # push eax
        add(call(here(), 0x004145AB))
        add(b"\x51")  # push ecx
        add(b"\x8B\xC4")  # mov eax, esp
        add(b"\x89\x65\x18")  # mov [ebp+0x18], esp
        add(b"\x50")  # push eax
        add(b"\x8B\xCB")  # mov ecx, ebx
        add(b"\xC6\x45\xFC\x60")  # mov byte ptr [ebp-4], 0x60
        add(call(here(), 0x004AD42B))
        add(b"\xFF\x75\x14")  # push [ebp+0x14]
        add(b"\x8D\x4D\xE8")  # lea ecx, [ebp-0x18]
        add(b"\xC6\x45\xFC\x01")  # mov byte ptr [ebp-4], 1
        add(call(here(), 0x0040B31F))
        add(b"\x50")  # push eax
        add(call(here(), 0x00432CBC))
        add(b"\x8B\xC8")  # mov ecx, eax
        add(call(here(), 0x0043D72A))

    def add_restore_saved_params() -> None:
        add(b"\x8B\x44\x24\x04")  # mov eax, [esp+4]
        add(b"\x89\x45\x10")  # mov [ebp+0x10], eax
        add(b"\x8B\x04\x24")  # mov eax, [esp]
        add(b"\x89\x45\x18")  # mov [ebp+0x18], eax

    add(cmp_esi(TEST_SKILL))
    add_je("play_both")
    add_default_hook_original()
    add(jmp(here(), DEFAULT_HOOK_RETURN_VA))

    mark("play_both")
    add(b"\xFF\x75\x10")  # push [ebp+0x10]
    add(b"\xFF\x75\x18")  # push [ebp+0x18]
    add_play_resource(0x1150)
    add_restore_saved_params()
    add_play_resource(0x1144, "skip_effect0")
    mark("skip_effect0")
    add_restore_saved_params()
    add(b"\x83\xC4\x08")  # discard saved [ebp+0x18] and [ebp+0x10]
    add(jmp(here(), 0x009358EE))

    for offset, label, instr_len in fixups:
        src_va = CAVE_VA + offset
        dst_va = labels[label]
        out[offset + 2 if instr_len == 6 else offset + 1 : offset + instr_len] = rel32(src_va, dst_va, instr_len)

    if len(out) > CAVE_SIZE:
        raise RuntimeError(f"code cave too small: need {len(out)} bytes, have {CAVE_SIZE}")
    out.extend(b"\x00" * (CAVE_SIZE - len(out)))
    return bytes(out)


def patch_bytes(data: bytearray, dry_run: bool) -> bool:
    cave = build_cave()
    old_cave = build_old_exit_cave() + b"\x00" * (CAVE_SIZE - 0x100)
    hook_offset = DEFAULT_HOOK_VA - IMAGE_BASE
    hook_patch = jmp(DEFAULT_HOOK_VA, CAVE_VA) + b"\x90"
    old_exit_hook_offset = OLD_EXIT_HOOK_VA - IMAGE_BASE
    old_exit_hook_patch = jmp(OLD_EXIT_HOOK_VA, CAVE_VA)

    current_hook = bytes(data[hook_offset : hook_offset + len(DEFAULT_HOOK_ORIGINAL)])
    current_old_exit_hook = bytes(data[old_exit_hook_offset : old_exit_hook_offset + len(OLD_EXIT_HOOK_ORIGINAL)])
    current_cave = bytes(data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE])

    if (
        current_hook == hook_patch
        and current_old_exit_hook == OLD_EXIT_HOOK_ORIGINAL
        and current_cave == cave
    ):
        print("BeiDou.exe already plays flat effect and effect0 for 1121001.")
        return False

    if current_hook not in {DEFAULT_HOOK_ORIGINAL, hook_patch}:
        raise RuntimeError(
            f"unexpected hook bytes at 0x{hook_offset:x}: "
            f"{current_hook.hex()} expected {DEFAULT_HOOK_ORIGINAL.hex()} or {hook_patch.hex()}"
        )
    if current_old_exit_hook not in {OLD_EXIT_HOOK_ORIGINAL, old_exit_hook_patch}:
        raise RuntimeError(
            f"unexpected old exit hook bytes at 0x{old_exit_hook_offset:x}: "
            f"{current_old_exit_hook.hex()} expected {OLD_EXIT_HOOK_ORIGINAL.hex()} "
            f"or {old_exit_hook_patch.hex()}"
        )
    if current_cave not in {cave, old_cave} and any(current_cave):
        raise RuntimeError(f"code cave is not empty at 0x{CAVE_OFFSET:x}")

    print(f"1121001 flat visual hook: VA 0x{DEFAULT_HOOK_VA:x} -> cave VA 0x{CAVE_VA:x}")
    print("resource slots: effect +0x1150, effect0 +0x1144")
    if dry_run:
        print("[dry-run] no changes written")
        return False

    if not BACKUP.exists():
        shutil.copy2(EXE, BACKUP)
        print(f"backup: {BACKUP}")

    data[old_exit_hook_offset : old_exit_hook_offset + len(OLD_EXIT_HOOK_ORIGINAL)] = OLD_EXIT_HOOK_ORIGINAL
    data[hook_offset : hook_offset + len(hook_patch)] = hook_patch
    data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE] = cave
    EXE.write_bytes(data)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = bytearray(EXE.read_bytes())
    changed = patch_bytes(data, args.dry_run)
    if changed:
        print("patched BeiDou.exe: 1121001 now plays flat effect and effect0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
