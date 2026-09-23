#!/usr/bin/env python3
"""Incrementally add the config loader section to the existing ijl15.dll."""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
import tempfile
from pathlib import Path

import pefile


SECTION_NAME = b".bdcfg\0\0"
SECTION_CHARACTERISTICS = 0x60000020  # code | execute | read
HOOK_RVA = 0x15925
RETURN_RVA = 0x1592C
ORIGINAL_HOOK = bytes.fromhex("56 83 ec 18 89 65 d0")
SECTION_RVA_MARKER = struct.pack("<I", 0xB16B00B5)
RETURN_REL32_MARKER = struct.pack("<I", 0xBADC0FFE)
EXPECTED_UNPATCHED_SHA256 = "efef032c8ba9aa2e80bbadc9c8989f7d777c8a509f37604ba7eb957d22eacc0e"


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def read_u16(data: bytearray, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data: bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def write_u16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", data, offset, value)


def write_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def patch_payload(payload: bytes, section_rva: int) -> bytes:
    result = bytearray(payload)
    if result.count(SECTION_RVA_MARKER) != 1:
        raise ValueError("payload must contain exactly one section-RVA marker")
    marker_offset = result.index(SECTION_RVA_MARKER)
    struct.pack_into("<I", result, marker_offset, section_rva)

    if result.count(RETURN_REL32_MARKER) != 1:
        raise ValueError("payload must contain exactly one return-jump marker")
    return_marker_offset = result.index(RETURN_REL32_MARKER)
    displacement = RETURN_RVA - (section_rva + return_marker_offset + 4)
    struct.pack_into("<i", result, return_marker_offset, displacement)
    return bytes(result)


def rva_to_offset(data: bytearray, section_table: int, section_count: int, rva: int) -> int:
    for index in range(section_count):
        header = section_table + index * 40
        virtual_size = read_u32(data, header + 8)
        virtual_address = read_u32(data, header + 12)
        raw_size = read_u32(data, header + 16)
        raw_pointer = read_u32(data, header + 20)
        if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
            return raw_pointer + rva - virtual_address
    raise ValueError(f"RVA 0x{rva:x} is not mapped by a section")


def update_checksum(data: bytearray, optional_header: int) -> None:
    checksum_offset = optional_header + 64
    write_u32(data, checksum_offset, 0)
    image = pefile.PE(data=bytes(data), fast_load=True)
    write_u32(data, checksum_offset, image.generate_checksum())


def patch_image(image: bytes, payload: bytes) -> bytes:
    data = bytearray(image)
    pe_offset = read_u32(data, 0x3C)
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError("input is not a PE image")

    coff_header = pe_offset + 4
    section_count = read_u16(data, coff_header + 2)
    optional_size = read_u16(data, coff_header + 16)
    optional_header = coff_header + 20
    if read_u16(data, optional_header) != 0x10B:
        raise ValueError("input must be a PE32 image")

    section_alignment = read_u32(data, optional_header + 32)
    file_alignment = read_u32(data, optional_header + 36)
    section_table = optional_header + optional_size
    section_headers = [section_table + index * 40 for index in range(section_count)]
    config_header = next(
        (header for header in section_headers if data[header : header + 8] == SECTION_NAME),
        None,
    )

    hook_offset = rva_to_offset(data, section_table, section_count, HOOK_RVA)
    if config_header is None:
        digest = hashlib.sha256(data).hexdigest()
        if digest != EXPECTED_UNPATCHED_SHA256:
            raise ValueError(
                "refusing to patch an unknown ijl15.dll: "
                f"expected {EXPECTED_UNPATCHED_SHA256}, got {digest}"
            )
        if bytes(data[hook_offset : hook_offset + len(ORIGINAL_HOOK)]) != ORIGINAL_HOOK:
            raise ValueError("initialization hook bytes do not match the verified DLL")

        last_header = max(
            section_headers,
            key=lambda header: read_u32(data, header + 12),
        )
        section_rva = align(
            read_u32(data, last_header + 12)
            + max(read_u32(data, last_header + 8), read_u32(data, last_header + 16)),
            section_alignment,
        )
        raw_pointer = align(len(data), file_alignment)
        raw_size = align(len(payload), file_alignment)
        new_header = section_table + section_count * 40
        first_raw_pointer = min(read_u32(data, header + 20) for header in section_headers)
        if new_header + 40 > first_raw_pointer:
            raise ValueError("PE headers have no room for another section")

        if len(data) < raw_pointer:
            data.extend(b"\0" * (raw_pointer - len(data)))
        data.extend(b"\0" * raw_size)
        data[new_header : new_header + 8] = SECTION_NAME
        write_u32(data, new_header + 8, len(payload))
        write_u32(data, new_header + 12, section_rva)
        write_u32(data, new_header + 16, raw_size)
        write_u32(data, new_header + 20, raw_pointer)
        write_u32(data, new_header + 36, SECTION_CHARACTERISTICS)
        write_u16(data, coff_header + 2, section_count + 1)
        write_u32(data, optional_header + 4, read_u32(data, optional_header + 4) + raw_size)
        write_u32(
            data,
            optional_header + 56,
            align(section_rva + len(payload), section_alignment),
        )
        section_count += 1
        config_header = new_header
    else:
        section_rva = read_u32(data, config_header + 12)
        raw_pointer = read_u32(data, config_header + 20)
        raw_size = read_u32(data, config_header + 16)
        expected_displacement = section_rva - (HOOK_RVA + 5)
        expected_hook = b"\xE9" + struct.pack("<i", expected_displacement) + b"\x90\x90"
        if bytes(data[hook_offset : hook_offset + 7]) != expected_hook:
            raise ValueError("existing config-loader hook is not recognized")
        if len(payload) > raw_size:
            raise ValueError("new payload no longer fits the existing config section")
        write_u32(data, config_header + 8, len(payload))

    patched_payload = patch_payload(payload, section_rva)
    data[raw_pointer : raw_pointer + raw_size] = b"\0" * raw_size
    data[raw_pointer : raw_pointer + len(patched_payload)] = patched_payload
    hook_displacement = section_rva - (HOOK_RVA + 5)
    data[hook_offset : hook_offset + 7] = (
        b"\xE9" + struct.pack("<i", hook_displacement) + b"\x90\x90"
    )
    update_checksum(data, optional_header)
    return bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = patch_image(args.input.read_bytes(), args.payload.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as temporary:
        temporary.write(result)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, args.output)


if __name__ == "__main__":
    main()
