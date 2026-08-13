#!/usr/bin/env python3
"""Retire the current Ice/Lightning V/VI migration without IMG re-encoding."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.writer import re_encrypt_string  # noqa: E402


MIGRATED_IDS = tuple(str(skill_id) for skill_id in range(2221009, 2221032))
SERVER_SKILL = ROOT / "gms-server/wz/Skill.wz/222.img.xml"
SERVER_STRING = ROOT / "gms-server/wz/String.wz/Skill.img.xml"
CLIENT_SKILL = ROOT / "clien/Data/Skill/222.img"
CLIENT_STRING = ROOT / "clien/Data/String/Skill.img"
CLIENT_EFFECT = ROOT / "clien/Data/Map/Effect.img"

IMGDIR_TAG = re.compile(br"<imgdir\b[^>]*?/?>|</imgdir>")


def remove_xml_nodes(path: Path) -> int:
    data = path.read_bytes()
    spans: list[tuple[int, int]] = []
    for skill_id in MIGRATED_IDS:
        marker = f'<imgdir name="{skill_id}">'.encode("ascii")
        matches = [match.start() for match in re.finditer(re.escape(marker), data)]
        if not matches:
            continue
        if len(matches) != 1:
            raise RuntimeError(f"expected one {skill_id} node in {path}, found {len(matches)}")
        start = matches[0]
        depth = 0
        end = None
        for tag in IMGDIR_TAG.finditer(data, start):
            token = tag.group()
            if token.startswith(b"</"):
                depth -= 1
                if depth == 0:
                    end = tag.end()
                    break
            elif not token.endswith(b"/>"):
                depth += 1
        if end is None:
            raise RuntimeError(f"unterminated {skill_id} node in {path}")
        while end < len(data) and data[end:end + 1] in (b"\r", b"\n"):
            end += 1
        spans.append((start, end))

    for start, end in sorted(spans, reverse=True):
        data = data[:start] + data[end:]
    if spans:
        replace_bytes(path, data)
    return len(spans)


def standalone_reader(path: Path):
    image = WzImage.from_file(str(path), key=WzKey.for_region("GMS"), name=path.name)
    return image, image.wz_file.reader


def enter_root_property_list(reader) -> None:
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError("unsupported standalone IMG header")
    reader.skip(2)


def read_named_extended_child(reader, base_offset: int, wanted: str) -> tuple[int, int, str, bool, int]:
    count = reader.read_compressed_int()
    for _ in range(count):
        name, payload_offset, payload_length, encoding, indirected = (
            reader.read_string_block_with_location(base_offset)
        )
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"expected extended property for {name}, got tag {tag}")
        block_size = reader.read_u32()
        end = reader.position + block_size
        if name == wanted:
            return payload_offset, payload_length, encoding, indirected, end
        reader.seek(end)
    raise KeyError(wanted)


def enter_subproperty(reader, base_offset: int, wanted: str) -> tuple[int, int, str, bool]:
    payload_offset, payload_length, encoding, indirected, _ = read_named_extended_child(
        reader, base_offset, wanted
    )
    if reader.read_string_block(base_offset) != "Property":
        raise RuntimeError(f"{wanted} is not a Property node")
    reader.skip(2)
    return payload_offset, payload_length, encoding, indirected


def patch_skill_child_count() -> tuple[int, int]:
    _, reader = standalone_reader(CLIENT_SKILL)
    enter_root_property_list(reader)
    enter_subproperty(reader, 0, "skill")
    count_offset = reader.position
    old_count = reader.read_compressed_int()
    if old_count == 9:
        return old_count, old_count
    if old_count not in (10, 11, 17, 21, 24, 32) or reader.position - count_offset != 1:
        raise RuntimeError(f"unexpected client 222 skill count: {old_count}")
    patch_bytes(CLIENT_SKILL, count_offset, bytes([9]))
    return old_count, 9


def top_level_name_locations(path: Path) -> tuple[object, dict[str, tuple[int, int, str, bool]]]:
    _, reader = standalone_reader(path)
    enter_root_property_list(reader)
    count = reader.read_compressed_int()
    locations = {}
    for _ in range(count):
        name, payload_offset, payload_length, encoding, indirected = (
            reader.read_string_block_with_location(0)
        )
        locations[name] = (payload_offset, payload_length, encoding, indirected)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"expected top-level extended property for {name}, got tag {tag}")
        block_size = reader.read_u32()
        reader.seek(reader.position + block_size)
    return reader, locations


def retire_client_strings() -> int:
    reader, locations = top_level_name_locations(CLIENT_STRING)
    patches = []
    for skill_id in MIGRATED_IDS:
        retired_name = "x" + skill_id[1:]
        if skill_id not in locations:
            if retired_name not in locations:
                raise RuntimeError(f"missing both live and retired client string node {skill_id}")
            continue
        if retired_name in locations:
            raise RuntimeError(f"retired client string name already exists: {retired_name}")
        offset, length, encoding, indirected = locations[skill_id]
        if indirected:
            raise RuntimeError(f"refusing to patch shared client string name: {skill_id}")
        encoded = re_encrypt_string(reader, retired_name, encoding)
        if len(encoded) != length:
            raise RuntimeError(f"client string rename changed byte length: {skill_id}")
        patches.append((offset, encoded))
    patch_many(CLIENT_STRING, patches)
    return len(patches)


def retire_effect_marker() -> bool:
    _, reader = standalone_reader(CLIENT_EFFECT)
    enter_root_property_list(reader)
    enter_subproperty(reader, 0, "customSkill")
    child_list_offset = reader.position
    try:
        offset, length, encoding, indirected, _ = read_named_extended_child(
            reader, 0, "ilArchMage"
        )
        replacement = "retiredIL_"
    except KeyError:
        reader.seek(child_list_offset)
        read_named_extended_child(reader, 0, "retiredIL_")
        return False
    if indirected:
        raise RuntimeError("refusing to patch shared ilArchMage marker name")
    encoded = re_encrypt_string(reader, replacement, encoding)
    if len(encoded) != length:
        raise RuntimeError("Map Effect marker rename changed byte length")
    patch_bytes(CLIENT_EFFECT, offset, encoded)
    return True


def patch_bytes(path: Path, offset: int, data: bytes) -> None:
    with path.open("r+b") as stream:
        stream.seek(offset)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def patch_many(path: Path, patches: list[tuple[int, bytes]]) -> None:
    if not patches:
        return
    with path.open("r+b") as stream:
        for offset, data in patches:
            stream.seek(offset)
            stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def replace_bytes(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".retire-il.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def main() -> None:
    skill_nodes = remove_xml_nodes(SERVER_SKILL)
    string_nodes = remove_xml_nodes(SERVER_STRING)
    old_count, new_count = patch_skill_child_count()
    client_strings = retire_client_strings()
    marker_changed = retire_effect_marker()
    print(f"server skill nodes removed: {skill_nodes}")
    print(f"server string nodes removed: {string_nodes}")
    print(f"client skill visible count: {old_count} -> {new_count}")
    print(f"client string nodes retired in place: {client_strings}")
    print(f"Map Effect marker retired in place: {marker_changed}")


if __name__ == "__main__":
    main()
