#!/usr/bin/env python3
"""Let Hero 112 custom 4th-job skills use the same skill-window path as 232."""

from __future__ import annotations

import argparse
import shutil
import struct
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXE = ROOT / "clien" / "BeiDou.exe"
BACKUP = ROOT / "clien" / "BeiDou.exe.bak-112-skill-window-display"

IMAGE_BASE = 0x00400000

SKILL_JOB_HOOK_VA = 0x004F0751
SKILL_JOB_HOOK_OFFSET = SKILL_JOB_HOOK_VA - IMAGE_BASE
SKILL_JOB_ORIGINAL = bytes.fromhex("3d e8 00 00 00 75 1c")
SKILL_JOB_OLD_CAVE_VA = 0x00AEF9E0
SKILL_JOB_NEW_CAVE_VA = 0x00AEFA80
SKILL_JOB_NEW_CAVE_OFFSET = SKILL_JOB_NEW_CAVE_VA - IMAGE_BASE
SKILL_JOB_NEW_CAVE_SIZE = 0x80
SKILL_JOB_BRANCH_VA = 0x004F0758
SKILL_JOB_RETURN_VA = 0x004F0774

BISHOP_ADD_HOOK_VA = 0x00A0A3D6
BISHOP_ADD_HOOK_OFFSET = BISHOP_ADD_HOOK_VA - IMAGE_BASE
BISHOP_ADD_ORIGINAL = bytes.fromhex("3d e8 00 00 00 0f 85 ba 00 00 00")
BISHOP_ADD_CAVE_VA = 0x00AEF980
BISHOP_ADD_CAVE_OFFSET = BISHOP_ADD_CAVE_VA - IMAGE_BASE
BISHOP_ADD_CAVE_SIZE = 0x30
BISHOP_ADD_CONTINUE_VA = 0x00A0A3E1
BISHOP_ADD_REJECT_VA = 0x00A0A49B


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def rel32(src_va: int, dst_va: int, instr_len: int = 5) -> bytes:
    return struct.pack("<i", dst_va - (src_va + instr_len))


def jmp(src_va: int, dst_va: int) -> bytes:
    return b"\xE9" + rel32(src_va, dst_va)


def je(src_va: int, dst_va: int) -> bytes:
    return b"\x0F\x84" + rel32(src_va, dst_va, 6)


def jne(src_va: int, dst_va: int) -> bytes:
    return b"\x0F\x85" + rel32(src_va, dst_va, 6)


def cmp_eax(value: int) -> bytes:
    return b"\x3D" + struct.pack("<I", value)


def current_jump_to(va: int, dst_va: int, original_len: int) -> bytes:
    patch = jmp(va, dst_va)
    return patch + b"\x90" * (original_len - len(patch))


def build_skill_job_cave() -> bytes:
    chunks: list[bytes] = []
    va = SKILL_JOB_NEW_CAVE_VA
    chunks.append(bytes.fromhex("8b4de8"))  # mov ecx, [ebp-18h], skill-window object
    va += 3

    # eax is skillId / 10000. 112 and 232 belong on tab 5 (4th job);
    # 233 was the old fifth-tab experiment and stays on tab 6.
    for job_id, tab in ((112, 5), (232, 5), (233, 6)):
        next_job_va = va + 5 + 6 + 4 + 6 + 5
        chunks.append(cmp_eax(job_id))
        va += 5
        chunks.append(jne(va, next_job_va))
        va += 6
        chunks.append(bytes.fromhex("837918") + bytes([tab]))  # cmp dword ptr [ecx+18h], tab
        va += 4
        chunks.append(je(va, SKILL_JOB_BRANCH_VA))
        va += 6
        chunks.append(jmp(va, SKILL_JOB_RETURN_VA))
        va += 5

    cave = b"".join(chunks)
    if len(cave) > SKILL_JOB_NEW_CAVE_SIZE:
        raise RuntimeError(f"skill-job cave too large: {len(cave)} > {SKILL_JOB_NEW_CAVE_SIZE}")
    return cave + b"\x00" * (SKILL_JOB_NEW_CAVE_SIZE - len(cave))


def build_bishop_add_cave() -> bytes:
    chunks: list[bytes] = []
    va = BISHOP_ADD_CAVE_VA
    # This function creates the skill-window item for late 4th-job skills.
    # It used to allow only 232/233; add 112 and keep the existing jobs.
    for job_id in (112, 232, 233):
        chunks.append(cmp_eax(job_id))
        va += 5
        chunks.append(je(va, BISHOP_ADD_CONTINUE_VA))
        va += 6
    chunks.append(jmp(va, BISHOP_ADD_REJECT_VA))
    cave = b"".join(chunks)
    if len(cave) > BISHOP_ADD_CAVE_SIZE:
        raise RuntimeError(f"bishop-add cave too large: {len(cave)} > {BISHOP_ADD_CAVE_SIZE}")
    return cave + b"\x00" * (BISHOP_ADD_CAVE_SIZE - len(cave))


def patch_exe(dry_run: bool) -> None:
    data = bytearray(EXE.read_bytes())

    skill_job_hook = current_jump_to(SKILL_JOB_HOOK_VA, SKILL_JOB_NEW_CAVE_VA, len(SKILL_JOB_ORIGINAL))
    old_skill_job_hook = current_jump_to(SKILL_JOB_HOOK_VA, SKILL_JOB_OLD_CAVE_VA, len(SKILL_JOB_ORIGINAL))
    bishop_add_hook = current_jump_to(BISHOP_ADD_HOOK_VA, BISHOP_ADD_CAVE_VA, len(BISHOP_ADD_ORIGINAL))

    skill_job_cave = build_skill_job_cave()
    bishop_add_cave = build_bishop_add_cave()

    current_skill_job_hook = bytes(data[SKILL_JOB_HOOK_OFFSET:SKILL_JOB_HOOK_OFFSET + len(SKILL_JOB_ORIGINAL)])
    if current_skill_job_hook not in (SKILL_JOB_ORIGINAL, old_skill_job_hook, skill_job_hook):
        raise RuntimeError(f"unexpected skill-job hook bytes: {current_skill_job_hook.hex()}")

    current_skill_job_cave = bytes(
        data[SKILL_JOB_NEW_CAVE_OFFSET:SKILL_JOB_NEW_CAVE_OFFSET + SKILL_JOB_NEW_CAVE_SIZE]
    )
    if current_skill_job_cave != skill_job_cave and any(current_skill_job_cave):
        raise RuntimeError(f"new skill-job cave is not empty at VA 0x{SKILL_JOB_NEW_CAVE_VA:x}")

    current_bishop_add_hook = bytes(data[BISHOP_ADD_HOOK_OFFSET:BISHOP_ADD_HOOK_OFFSET + len(BISHOP_ADD_ORIGINAL)])
    if current_bishop_add_hook not in (BISHOP_ADD_ORIGINAL, bishop_add_hook):
        raise RuntimeError(f"unexpected bishop-add hook bytes: {current_bishop_add_hook.hex()}")

    current_bishop_add_cave = bytes(data[BISHOP_ADD_CAVE_OFFSET:BISHOP_ADD_CAVE_OFFSET + BISHOP_ADD_CAVE_SIZE])
    accepted_bishop_caves = {
        build_bishop_add_cave(),
        # Previous 232/233-only cave from patch_bishop_dragon_manual_attacks.py.
        bytes.fromhex(
            "3de80000000f8456aaf1ff"
            "3de90000000f844baaf1ff"
            "e900abf1ff"
        )
        + b"\x00" * (BISHOP_ADD_CAVE_SIZE - 27),
    }
    if current_bishop_add_cave not in accepted_bishop_caves:
        raise RuntimeError(f"unexpected bishop-add cave bytes: {current_bishop_add_cave.hex()}")

    if dry_run:
        print("Would patch BeiDou.exe skill window display: allow job 112 on tab 5 like job 232.")
        return

    if not BACKUP.exists():
        shutil.copy2(EXE, BACKUP)
        print(f"backup: {BACKUP}")

    data[SKILL_JOB_HOOK_OFFSET:SKILL_JOB_HOOK_OFFSET + len(skill_job_hook)] = skill_job_hook
    data[SKILL_JOB_NEW_CAVE_OFFSET:SKILL_JOB_NEW_CAVE_OFFSET + len(skill_job_cave)] = skill_job_cave
    data[BISHOP_ADD_HOOK_OFFSET:BISHOP_ADD_HOOK_OFFSET + len(bishop_add_hook)] = bishop_add_hook
    data[BISHOP_ADD_CAVE_OFFSET:BISHOP_ADD_CAVE_OFFSET + len(bishop_add_cave)] = bishop_add_cave
    atomic_write_bytes(EXE, bytes(data))
    print("patched BeiDou.exe: job 112 custom skills can use the 4th-job skill-window path.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    patch_exe(args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
