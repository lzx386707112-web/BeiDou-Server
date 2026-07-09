#!/usr/bin/env python3
"""Let BeiDou.exe play migrated skill screen nodes from effect/90..93.

The old client does not have a native `screen` resource slot in the loaded
skill visual object.  The companion WZ patch mirrors:

    screen  -> effect/90
    screen0 -> effect/91
    screen1 -> effect/92
    screen2 -> effect/93

This EXE hook runs after the normal flat skill effect has been queued.  It
tries those four effect indices with the client's existing effect selector and
playback path. Missing indices are skipped, so this is safe for skills without
screen resources.
"""

from __future__ import annotations

import argparse
import shutil
import struct
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "clien" / "BeiDou.exe"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-skill-screen-effect-slots"

IMAGE_BASE = 0x00400000

HOOK_VA = 0x009358EE
HOOK_ORIGINAL = bytes.fromhex("8b 45 c8 3b c7")
HOOK_RETURN_VA = HOOK_VA + len(HOOK_ORIGINAL)

CAVE_VA = 0x00AEFD80
CAVE_OFFSET = CAVE_VA - IMAGE_BASE
CAVE_SIZE = 0x280

FIRST_SCREEN_EFFECT_INDEX = 90
PAST_LAST_SCREEN_EFFECT_INDEX = 94
OLD_FIRST_SCREEN_EFFECT_INDEX = 10
OLD_PAST_LAST_SCREEN_EFFECT_INDEX = 14


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def u32(value: int) -> bytes:
    return struct.pack("<I", value)


def rel32(src_va: int, dst_va: int, instr_len: int = 5) -> bytes:
    return struct.pack("<i", dst_va - (src_va + instr_len))


def jmp(src_va: int, dst_va: int) -> bytes:
    return b"\xE9" + rel32(src_va, dst_va)


def je_placeholder() -> bytes:
    return b"\x0F\x84\x00\x00\x00\x00"


def jne_placeholder() -> bytes:
    return b"\x0F\x85\x00\x00\x00\x00"


def call(src_va: int, dst_va: int) -> bytes:
    return b"\xE8" + rel32(src_va, dst_va)


def hook_patch() -> bytes:
    return jmp(HOOK_VA, CAVE_VA)


def build_cave(
    first_screen_effect_index: int = FIRST_SCREEN_EFFECT_INDEX,
    past_last_screen_effect_index: int = PAST_LAST_SCREEN_EFFECT_INDEX,
) -> bytes:
    out = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str, int]] = []

    def here() -> int:
        return CAVE_VA + len(out)

    def mark(name: str) -> None:
        labels[name] = here()

    def add(data: bytes) -> None:
        out.extend(data)

    def add_je(label: str) -> None:
        fixups.append((len(out), label, 6))
        add(je_placeholder())

    def add_jne(label: str) -> None:
        fixups.append((len(out), label, 6))
        add(jne_placeholder())

    def add_jmp(label: str) -> None:
        fixups.append((len(out), label, 5))
        add(b"\xE9\x00\x00\x00\x00")

    add(b"\x60")  # pushad; preserve the caller's registers.
    add(b"\xFF\x75\x10")  # save original [ebp+0x10]
    add(b"\xFF\x75\x18")  # save original [ebp+0x18]
    add(b"\xBE" + u32(first_screen_effect_index))  # mov esi, first index

    mark("loop")
    add(b"\x8D\x4D\xE8")  # lea ecx, [ebp-0x18]
    add(call(here(), 0x00402D9A))  # release previous selected effect resource
    add(b"\x8B\x4D\x08")  # mov ecx, [ebp+0x8]
    add(b"\x56")  # push esi
    add(b"\x8D\x45\xE8")  # lea eax, [ebp-0x18]
    add(b"\x50")  # push eax
    add(call(here(), 0x00932D40))  # select effect/<esi>

    add(b"\x8B\x45\xE8")  # mov eax, [ebp-0x18]
    add(b"\x85\xC0")  # test eax, eax
    add_je("next")
    add(b"\x8B\x00")  # mov eax, [eax]
    add(b"\x85\xC0")  # test eax, eax
    add_je("next")
    add(b"\x8B\x40\xFC")  # mov eax, [eax-4]
    add(b"\xD1\xE8")  # shr eax, 1
    add(b"\x85\xC0")  # test eax, eax
    add_je("next")

    # Mirror the stable skill effect playback block, using the selected
    # effect resource and the normal character effect layer.
    add(b"\x6A\x03")  # push 3
    add(b"\x68\xFF\xFF\xFF\x7F")  # push 0x7fffffff
    add(b"\x68\xE8\x03\x00\x00")  # push 1000
    add(b"\x6A\x10")  # push 0x10
    add(b"\x59")  # pop ecx
    add(b"\x51")  # push ecx
    add(b"\x8D\x83\x50\x11\x00\x00")  # lea eax, [ebx+0x1150]
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

    mark("next")
    add(b"\x46")  # inc esi
    add(b"\x83\xFE" + bytes([past_last_screen_effect_index]))  # cmp esi, past-last
    add_jne("loop")

    add(b"\x58")  # restore original [ebp+0x18]
    add(b"\x89\x45\x18")
    add(b"\x58")  # restore original [ebp+0x10]
    add(b"\x89\x45\x10")
    add(b"\x61")  # popad

    # Original bytes overwritten at 0x9358EE, then resume at the original JE.
    add(b"\x8B\x45\xC8")  # mov eax, [ebp-0x38]
    add(b"\x3B\xC7")  # cmp eax, edi
    add(jmp(here(), HOOK_RETURN_VA))

    for offset, label, instr_len in fixups:
        src_va = CAVE_VA + offset
        dst_va = labels[label]
        start = offset + (2 if instr_len == 6 else 1)
        out[start : offset + instr_len] = rel32(src_va, dst_va, instr_len)

    if len(out) > CAVE_SIZE:
        raise RuntimeError(f"code cave too small: need {len(out)} bytes, have {CAVE_SIZE}")
    out.extend(b"\x00" * (CAVE_SIZE - len(out)))
    return bytes(out)


def patch_exe(dry_run: bool) -> None:
    data = bytearray(EXE.read_bytes())
    cave = build_cave()
    old_cave = build_cave(OLD_FIRST_SCREEN_EFFECT_INDEX, OLD_PAST_LAST_SCREEN_EFFECT_INDEX)
    patch = hook_patch()

    current_hook = bytes(data[HOOK_VA - IMAGE_BASE : HOOK_VA - IMAGE_BASE + len(HOOK_ORIGINAL)])
    if current_hook not in {HOOK_ORIGINAL, patch}:
        raise RuntimeError(
            f"unexpected hook bytes at 0x{HOOK_VA:x}: {current_hook.hex()} "
            f"expected {HOOK_ORIGINAL.hex()} or {patch.hex()}"
        )

    current_cave = bytes(data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE])
    if current_cave not in {cave, old_cave} and any(current_cave):
        raise RuntimeError(f"code cave is not empty at VA 0x{CAVE_VA:x}")

    if current_hook == patch and current_cave == cave:
        print("BeiDou.exe already plays migrated skill screen effect slots.")
        return

    print(
        "Will patch BeiDou.exe skill screen compatibility: "
        "screen/screen0/screen1/screen2 -> effect/90..93 playback."
    )
    print(f"hook VA 0x{HOOK_VA:x} -> cave VA 0x{CAVE_VA:x}, cave bytes {len(cave)}")
    if dry_run:
        print("[dry-run] no files written")
        return

    if not BACKUP.exists():
        shutil.copy2(EXE, BACKUP)
        print(f"backup: {BACKUP}")

    data[HOOK_VA - IMAGE_BASE : HOOK_VA - IMAGE_BASE + len(patch)] = patch
    data[CAVE_OFFSET : CAVE_OFFSET + CAVE_SIZE] = cave
    atomic_write_bytes(EXE, bytes(data))
    print("patched BeiDou.exe: migrated skill screen effect slots now play after normal skill effects")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    patch_exe(args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
