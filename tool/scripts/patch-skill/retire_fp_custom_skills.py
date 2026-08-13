#!/usr/bin/env python3
"""Remove the retired Fire/Poison custom skills without renumbering peers."""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
WZPY = ROOT / "tool" / "wz-python"
sys.path[:0] = [str(PATCH_SKILL), str(WZPY)]

import patch_blaze_wizard_v_vi as engine  # noqa: E402
import retire_il_archmage_v_vi as inplace  # noqa: E402
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.writer import encode_compressed_int, re_encrypt_string  # noqa: E402


RETIRED_SKILL_IDS = (
    2121009,
    2121010,
    2121011,
    2121013,
    2121014,
    2121015,
    2121016,
    2121023,
    2121024,
    2121025,
    2121026,
    2121027,
    2121029,
    2121030,
    2121031,
    2121037,
)
PROTECTED_SKILL_ID = 2121005
CLIENT_SKILL = ROOT / "clien/Data/Skill/212.img"
CLIENT_STRING = ROOT / "clien/Data/String/Skill.img"
SERVER_SKILL = ROOT / "gms-server/wz/Skill.wz/212.img.xml"
SERVER_STRING = ROOT / "gms-server/wz/String.wz/Skill.img.xml"


def locate_skill_records(path: Path):
    image, reader = inplace.standalone_reader(path)
    inplace.enter_root_property_list(reader)
    root_count = reader.read_compressed_int()
    for root_index in range(root_count):
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root property tag: {name}/{tag}")
        block_size_offset = reader.position
        block_size = reader.read_u32()
        block_end = reader.position + block_size
        if name != "skill":
            reader.seek(block_end)
            continue
        if root_index != root_count - 1 or block_end > path.stat().st_size:
            raise RuntimeError("212.img skill node is not the final readable root property")
        if reader.read_string_block(0) != "Property":
            raise RuntimeError("212.img skill node is not a Property")
        reader.skip(2)
        count_offset = reader.position
        count = reader.read_compressed_int()
        count_end = reader.position
        records = {}
        for _ in range(count):
            start = reader.position
            child_name = reader.read_string_block(0)
            child_tag = reader.read_byte()
            if child_tag != 9:
                raise RuntimeError(f"unexpected skill child tag: {child_name}/{child_tag}")
            child_size = reader.read_u32()
            reader.seek(reader.position + child_size)
            records[int(child_name)] = (start, reader.position)
        return records, block_size_offset, block_end, count_offset, count_end, count
    raise RuntimeError("212.img has no skill node")


def record_bytes(path: Path) -> dict[int, bytes]:
    records, *_ = locate_skill_records(path)
    data = path.read_bytes()
    return {skill_id: data[start:end] for skill_id, (start, end) in records.items()}


def patch_client() -> None:
    before = record_bytes(CLIENT_SKILL)
    present = tuple(skill_id for skill_id in RETIRED_SKILL_IDS if skill_id in before)
    if not present:
        return
    records, block_size_offset, _, count_offset, count_end, count = locate_skill_records(
        CLIENT_SKILL
    )
    updated = bytearray(CLIENT_SKILL.read_bytes())
    for skill_id in sorted(present, key=lambda value: records[value][0], reverse=True):
        start, end = records[skill_id]
        del updated[start:end]
    updated[count_offset:count_end] = encode_compressed_int(count - len(present))
    block_payload_start = block_size_offset + 4
    updated[block_size_offset:block_payload_start] = (
        len(updated) - block_payload_start
    ).to_bytes(4, "little")
    temporary = CLIENT_SKILL.with_name(CLIENT_SKILL.name + ".retire-fp.tmp")
    temporary.write_bytes(updated)
    os.replace(temporary, CLIENT_SKILL)

    after = record_bytes(CLIENT_SKILL)
    for skill_id in RETIRED_SKILL_IDS:
        if skill_id in after:
            raise RuntimeError(f"client skill was not retired: {skill_id}")
    retained_before = {key: value for key, value in before.items() if key not in RETIRED_SKILL_IDS}
    if after != retained_before:
        raise RuntimeError("a retained client skill record changed during retirement")


def patch_client_strings() -> None:
    reader, locations = inplace.top_level_name_locations(CLIENT_STRING)
    patches = []
    for skill_id in RETIRED_SKILL_IDS:
        live_name = str(skill_id)
        retired_name = "x" + live_name[1:]
        if live_name not in locations:
            continue
        if retired_name in locations:
            raise RuntimeError(f"retired client string name already exists: {retired_name}")
        offset, length, encoding, indirected = locations[live_name]
        if indirected:
            raise RuntimeError(f"refusing to patch shared client string name: {live_name}")
        encoded = re_encrypt_string(reader, retired_name, encoding)
        if len(encoded) != length:
            raise RuntimeError(f"client string rename changed byte length: {live_name}")
        patches.append((offset, encoded))
    inplace.patch_many(CLIENT_STRING, patches)


def patch_server(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    spans = []
    for skill_id in RETIRED_SKILL_IDS:
        try:
            start, end = engine.find_imgdir_block(original, str(skill_id))
        except RuntimeError:
            continue
        line_start = original.rfind("\n", 0, start) + 1
        if not original[line_start:start].strip():
            start = line_start
        if end < len(original) and original[end] == "\n":
            end += 1
        spans.append((start, end))
    if not spans:
        return
    updated = original
    for start, end in sorted(spans, reverse=True):
        updated = updated[:start] + updated[end:]
    engine.base.atomic_write_text(path, updated)


def validate() -> None:
    client = WzImage.from_bytes(
        CLIENT_SKILL.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_SKILL.name
    ).parse()
    client_strings = WzImage.from_bytes(
        CLIENT_STRING.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_STRING.name
    ).parse()
    server = ET.parse(SERVER_SKILL).getroot()
    server_skills = server.find("./imgdir[@name='skill']")
    server_strings = ET.parse(SERVER_STRING).getroot()
    for skill_id in RETIRED_SKILL_IDS:
        if client.get(f"skill/{skill_id}") is not None:
            raise RuntimeError(f"client skill still exists: {skill_id}")
        if server_skills.find(f"./imgdir[@name='{skill_id}']") is not None:
            raise RuntimeError(f"server skill still exists: {skill_id}")
        if client_strings.get(str(skill_id)) is not None:
            raise RuntimeError(f"client skill string still exists: {skill_id}")
        if server_strings.find(f"./imgdir[@name='{skill_id}']") is not None:
            raise RuntimeError(f"server skill string still exists: {skill_id}")
    if client.get(f"skill/{PROTECTED_SKILL_ID}") is None:
        raise RuntimeError(f"protected client skill is missing: {PROTECTED_SKILL_ID}")
    if server_skills.find(f"./imgdir[@name='{PROTECTED_SKILL_ID}']") is None:
        raise RuntimeError(f"protected server skill is missing: {PROTECTED_SKILL_ID}")


def main() -> None:
    patch_client()
    patch_client_strings()
    patch_server(SERVER_SKILL)
    patch_server(SERVER_STRING)
    validate()
    retired = ", ".join(str(skill_id) for skill_id in RETIRED_SKILL_IDS)
    print(f"retired Fire/Poison skill nodes: {retired}")
    print(f"protected original skill: {PROTECTED_SKILL_ID}")


if __name__ == "__main__":
    main()
