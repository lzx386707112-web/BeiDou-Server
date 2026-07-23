#!/usr/bin/env python3
"""Build a test client that treats legacy WZ offsets as unsigned DWORDs.

The legacy resource stream already tracks a 64-bit position, but its random
read path calls SetFilePointer with a NULL high-part pointer. Windows therefore
sign-extends offsets whose low DWORD is >= 0x80000000. This patch redirects only
that call site through a tiny wrapper that supplies a zero high DWORD, allowing
absolute offsets in the 2-4 GiB range without changing other file operations.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "clien/BeiDou.exe"
DEFAULT_OUTPUT = ROOT / "clien/BeiDou_2G_TEST.exe"

EXPECTED_SHA256 = "1198fa57ca5a7c489bae43ec13c69681d9cabe0f96762f3dc0357facf2e7d4df"
PATCH_SITE_VA = 0x00495B2D
EXPECTED_CALL = bytes.fromhex("FF 15 68 03 BF 00")
SET_FILE_POINTER_SLOT = 0x00BF0368
SECTION_NAME = b".bd2g\0\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def put_u16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", data, offset, value)


def put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def pe_checksum(data: bytes | bytearray, checksum_offset: int) -> int:
    checksum = 0
    for offset in range(0, len(data), 2):
        if checksum_offset <= offset < checksum_offset + 4:
            word = 0
        elif offset + 1 < len(data):
            word = data[offset] | (data[offset + 1] << 8)
        else:
            word = data[offset]
        checksum = (checksum & 0xFFFF) + (checksum >> 16) + word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    checksum = (checksum & 0xFFFF) + (checksum >> 16)
    return (checksum + len(data)) & 0xFFFFFFFF


def wrapper_bytes() -> bytes:
    # DWORD WINAPI wrapper(HANDLE file, DWORD low, DWORD *ignored, DWORD origin)
    # {
    #     DWORD high = 0;
    #     return SetFilePointer(file, low, &high, origin);
    # }
    return bytes.fromhex(
        "55"                    # push ebp
        "8B EC"                 # mov ebp, esp
        "6A 00"                 # push 0 (local high DWORD)
        "8D 45 FC"              # lea eax, [ebp-4]
        "FF 75 14"              # push [ebp+0x14] (origin)
        "50"                    # push eax (high pointer)
        "FF 75 0C"              # push [ebp+0x0c] (low DWORD)
        "FF 75 08"              # push [ebp+0x08] (file handle)
        f"FF 15 {SET_FILE_POINTER_SLOT.to_bytes(4, 'little').hex()}"
        "C9"                    # leave
        "C2 10 00"              # ret 0x10
    )


def parse_sections(data: bytes | bytearray, section_table: int, count: int) -> list[dict[str, int | bytes]]:
    sections = []
    for index in range(count):
        offset = section_table + index * 40
        sections.append(
            {
                "header": offset,
                "name": bytes(data[offset : offset + 8]),
                "virtual_size": u32(data, offset + 8),
                "virtual_address": u32(data, offset + 12),
                "raw_size": u32(data, offset + 16),
                "raw_pointer": u32(data, offset + 20),
            }
        )
    return sections


def rva_to_offset(rva: int, sections: list[dict[str, int | bytes]]) -> int:
    for section in sections:
        start = int(section["virtual_address"])
        span = max(int(section["virtual_size"]), int(section["raw_size"]))
        if start <= rva < start + span:
            return int(section["raw_pointer"]) + rva - start
    raise ValueError(f"RVA not mapped: 0x{rva:08X}")


def patch(source: Path, output: Path) -> None:
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            f"unexpected source SHA-256: {digest}; expected {EXPECTED_SHA256}"
        )
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")

    data = bytearray(original)
    pe_offset = u32(data, 0x3C)
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise RuntimeError("not a PE image")

    coff = pe_offset + 4
    section_count = u16(data, coff + 2)
    optional_size = u16(data, coff + 16)
    optional = coff + 20
    if u16(data, optional) != 0x10B:
        raise RuntimeError("expected a PE32 optional header")

    image_base = u32(data, optional + 28)
    section_alignment = u32(data, optional + 32)
    file_alignment = u32(data, optional + 36)
    size_of_headers = u32(data, optional + 60)
    checksum_offset = optional + 64
    section_table = optional + optional_size
    new_section_header = section_table + section_count * 40
    if new_section_header + 40 > size_of_headers:
        raise RuntimeError("no room for an additional PE section header")

    sections = parse_sections(data, section_table, section_count)
    if any(section["name"].rstrip(b"\0") == SECTION_NAME.rstrip(b"\0") for section in sections):
        raise RuntimeError("patch section already exists")

    raw_end = max(
        int(section["raw_pointer"]) + int(section["raw_size"])
        for section in sections
    )
    if raw_end != len(data):
        raise RuntimeError("unexpected PE overlay; refusing to move or overwrite it")

    virtual_end = max(
        int(section["virtual_address"])
        + align(int(section["virtual_size"]), section_alignment)
        for section in sections
    )
    section_rva = align(virtual_end, section_alignment)
    section_raw = align(raw_end, file_alignment)
    section_raw_size = file_alignment
    wrapper = wrapper_bytes()
    if len(wrapper) > section_raw_size:
        raise RuntimeError("wrapper does not fit in patch section")

    patch_rva = PATCH_SITE_VA - image_base
    patch_offset = rva_to_offset(patch_rva, sections)
    actual_call = bytes(data[patch_offset : patch_offset + len(EXPECTED_CALL)])
    if actual_call != EXPECTED_CALL:
        raise RuntimeError(
            f"unexpected call bytes at 0x{PATCH_SITE_VA:08X}: {actual_call.hex(' ')}"
        )

    wrapper_va = image_base + section_rva
    relative = wrapper_va - (PATCH_SITE_VA + 5)
    replacement = b"\xE8" + struct.pack("<i", relative) + b"\x90"
    data[patch_offset : patch_offset + len(replacement)] = replacement

    if len(data) < section_raw:
        data.extend(b"\0" * (section_raw - len(data)))
    data.extend(wrapper)
    data.extend(b"\0" * (section_raw_size - len(wrapper)))

    section_header = struct.pack(
        "<8sIIIIIIHHI",
        SECTION_NAME,
        len(wrapper),
        section_rva,
        section_raw_size,
        section_raw,
        0,
        0,
        0,
        0,
        SECTION_CHARACTERISTICS,
    )
    data[new_section_header : new_section_header + 40] = section_header
    put_u16(data, coff + 2, section_count + 1)
    put_u32(data, optional + 4, u32(data, optional + 4) + section_raw_size)
    put_u32(data, optional + 56, align(section_rva + len(wrapper), section_alignment))
    put_u32(data, checksum_offset, 0)
    put_u32(data, checksum_offset, pe_checksum(data, checksum_offset))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    print(f"source_sha256={digest}")
    print(f"output_sha256={hashlib.sha256(data).hexdigest()}")
    print(f"patch_site=0x{PATCH_SITE_VA:08X} wrapper_va=0x{wrapper_va:08X}")
    print(f"section={SECTION_NAME.rstrip(bytes([0])).decode()} size={section_raw_size}")
    print(f"output={output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    patch(args.input.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
