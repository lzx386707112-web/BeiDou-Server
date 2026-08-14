#!/usr/bin/env python3
"""Retire removed Night Lord skills without re-encoding either client IMG."""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool/scripts/patch-skill"
WZPY = ROOT / "tool/wz-python"
sys.path[:0] = [str(PATCH_SKILL), str(WZPY)]

import patch_blaze_wizard_v_vi as engine  # noqa: E402
import retire_il_archmage_v_vi as inplace  # noqa: E402
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.writer import encode_compressed_int, re_encrypt_string  # noqa: E402


RETIRED_SKILL_IDS = (4121010, 4121012, 4121013, 4121014, 4121015, 4121021)
PROTECTED_SKILL_IDS = (4121016, 4121017)
CLIENT_SKILL = ROOT / "clien/Data/Skill/412.img"
CLIENT_STRING = ROOT / "clien/Data/String/Skill.img"
SERVER_SKILL = ROOT / "gms-server/wz/Skill.wz/412.img.xml"
SERVER_STRING = ROOT / "gms-server/wz/String.wz/Skill.img.xml"
EQUIPMENT_REFS = (
    ("Weapon/01472141.img", "info/level/case/1/4/Skill", 4121013),
    ("Weapon/01472142.img", "info/level/case/1/6/Skill", 4121013),
    ("Shoes/01072547.img", "info/level/case/1/4/Skill/0", 4121014),
    ("Shoes/01072552.img", "info/level/case/1/6/Skill/0", 4121014),
)


def locate_skill_records(path: Path):
    _, reader = inplace.standalone_reader(path)
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
            raise RuntimeError("412.img skill node is not the final readable root property")
        if reader.read_string_block(0) != "Property":
            raise RuntimeError("412.img skill node is not a Property")
        reader.skip(2)
        count_offset = reader.position
        count = reader.read_compressed_int()
        count_end = reader.position
        records = {}
        order = []
        for _ in range(count):
            start = reader.position
            child_name = reader.read_string_block(0)
            child_tag = reader.read_byte()
            if child_tag != 9:
                raise RuntimeError(f"unexpected skill child tag: {child_name}/{child_tag}")
            child_size = reader.read_u32()
            reader.seek(reader.position + child_size)
            skill_id = int(child_name)
            records[skill_id] = (start, reader.position)
            order.append(skill_id)
        return records, order, block_size_offset, count_offset, count_end, count
    raise RuntimeError("412.img has no skill node")


def record_bytes(path: Path) -> tuple[list[int], dict[int, bytes]]:
    records, order, *_ = locate_skill_records(path)
    data = path.read_bytes()
    return order, {skill_id: data[start:end] for skill_id, (start, end) in records.items()}


def patch_client_skill(dry_run: bool) -> None:
    before_order, before = record_bytes(CLIENT_SKILL)
    present = tuple(skill_id for skill_id in RETIRED_SKILL_IDS if skill_id in before)
    if not present:
        return
    records, _, size_offset, count_offset, count_end, count = locate_skill_records(
        CLIENT_SKILL
    )
    updated = bytearray(CLIENT_SKILL.read_bytes())
    for skill_id in sorted(present, key=lambda value: records[value][0], reverse=True):
        start, end = records[skill_id]
        del updated[start:end]
    new_count = encode_compressed_int(count - len(present))
    if len(new_count) != count_end - count_offset:
        raise RuntimeError("412.img skill count encoding size changed")
    updated[count_offset:count_end] = new_count
    payload_start = size_offset + 4
    updated[size_offset:payload_start] = (
        len(updated) - payload_start
    ).to_bytes(4, "little")
    if dry_run:
        return
    temporary = CLIENT_SKILL.with_name(CLIENT_SKILL.name + ".retire-night-lord.tmp")
    temporary.write_bytes(updated)
    os.replace(temporary, CLIENT_SKILL)
    after_order, after = record_bytes(CLIENT_SKILL)
    expected_order = [value for value in before_order if value not in RETIRED_SKILL_IDS]
    expected = {key: value for key, value in before.items() if key not in RETIRED_SKILL_IDS}
    if after_order != expected_order or after != expected:
        raise RuntimeError("a retained client skill record changed during retirement")


def patch_client_strings(dry_run: bool) -> None:
    reader, locations = inplace.top_level_name_locations(CLIENT_STRING)
    patches = []
    for skill_id in RETIRED_SKILL_IDS:
        live_name = str(skill_id)
        if live_name not in locations:
            continue
        retired_name = next(
            (
                prefix + live_name[1:]
                for prefix in ("x", "y", "z", "r")
                if prefix + live_name[1:] not in locations
            ),
            None,
        )
        if retired_name is None:
            raise RuntimeError(f"no unused retired client string name: {live_name}")
        offset, length, encoding, indirected = locations[live_name]
        if indirected:
            raise RuntimeError(f"refusing to patch shared client string name: {live_name}")
        encoded = re_encrypt_string(reader, retired_name, encoding)
        if len(encoded) != length:
            raise RuntimeError(f"client string rename changed byte length: {live_name}")
        patches.append((offset, encoded))
    if patches and not dry_run:
        inplace.patch_many(CLIENT_STRING, patches)


def patch_server(path: Path, dry_run: bool) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
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
    for start, end in sorted(spans, reverse=True):
        updated = updated[:start] + updated[end:]
    if updated != original and not dry_run:
        engine.base.atomic_write_text(path, updated)


def locate_nested_record(path: Path, property_path: str):
    _, reader = inplace.standalone_reader(path)
    inplace.enter_root_property_list(reader)
    parts = property_path.split("/")

    def skip_value(tag: int) -> None:
        if tag == 0:
            return
        if tag in (2, 11):
            reader.skip(2)
        elif tag in (3, 19):
            reader.read_compressed_int()
        elif tag == 4:
            if reader.read_byte() == 0x80:
                reader.skip(4)
        elif tag == 5:
            reader.skip(8)
        elif tag == 8:
            reader.read_string_block(0)
        elif tag == 20:
            reader.read_compressed_long()
        else:
            raise RuntimeError(f"unsupported property tag in {path}: {tag}")

    def descend(index: int, ancestor_sizes: tuple[int, ...]):
        count_offset = reader.position
        count = reader.read_compressed_int()
        count_end = reader.position
        for _ in range(count):
            record_start = reader.position
            name = reader.read_string_block(0)
            tag = reader.read_byte()
            if tag != 9:
                skip_value(tag)
                continue
            size_offset = reader.position
            block_size = reader.read_u32()
            block_end = reader.position + block_size
            if name != parts[index]:
                reader.seek(block_end)
                continue
            if index == len(parts) - 1:
                return (
                    record_start, block_end, count_offset, count_end, count,
                    ancestor_sizes,
                )
            if reader.read_string_block(0) != "Property":
                raise RuntimeError(f"non-Property path component in {path}: {name}")
            reader.skip(2)
            return descend(index + 1, (*ancestor_sizes, size_offset))
        raise RuntimeError(f"missing client equipment property: {property_path}")

    return descend(0, ())


def patch_client_equipment(dry_run: bool) -> None:
    client_root = ROOT / "clien/Data/Character"
    for relative_path, property_path, skill_id in EQUIPMENT_REFS:
        path = client_root / relative_path
        original = path.read_bytes()
        image = WzImage.from_bytes(original, key=WzKey.for_region("GMS"), name=path.name)
        root = image.parse()
        id_path = property_path + ("/id" if property_path.endswith("/0") else "/0/id")
        value = root.get(id_path)
        if value is None:
            continue
        if int(value.value) != skill_id:
            raise RuntimeError(f"unexpected equipment skill reference: {relative_path}/{id_path}")
        (start, end, count_offset, count_end, count,
         ancestor_sizes) = locate_nested_record(path, property_path)
        updated = bytearray(original)
        new_count = encode_compressed_int(count - 1)
        if len(new_count) != count_end - count_offset:
            raise RuntimeError(f"equipment child count encoding changed: {relative_path}")
        updated[count_offset:count_end] = new_count
        removed_length = end - start
        for size_offset in ancestor_sizes:
            old_size = int.from_bytes(updated[size_offset:size_offset + 4], "little")
            updated[size_offset:size_offset + 4] = (old_size - removed_length).to_bytes(
                4, "little"
            )
        del updated[start:end]
        if dry_run:
            continue
        temporary = path.with_name(path.name + ".retire-night-lord.tmp")
        temporary.write_bytes(updated)
        os.replace(temporary, path)
        verified = WzImage.from_file(str(path), key=WzKey.for_region("GMS"), name=path.name)
        verified_root = verified.parse()
        if verified.truncated or verified.parse_warnings:
            raise RuntimeError(f"malformed patched equipment IMG: {relative_path}")
        if verified_root.get(id_path) is not None:
            raise RuntimeError(f"equipment skill reference remains: {relative_path}/{id_path}")


def patch_server_equipment(dry_run: bool) -> None:
    server_root = ROOT / "gms-server/wz/Character.wz"
    for relative_path, property_path, skill_id in EQUIPMENT_REFS:
        path = server_root / f"{relative_path}.xml"
        original = path.read_text(encoding="utf-8")
        marker = f'<int name="id" value="{skill_id}"'
        if marker not in original:
            continue
        root = ET.fromstring(original)
        parts = property_path.split("/")
        parent = root
        for name in parts[:-1]:
            parent = parent.find(f"./imgdir[@name='{name}']")
            if parent is None:
                raise RuntimeError(f"missing server equipment path: {relative_path}/{property_path}")
        target = parent.find(f"./imgdir[@name='{parts[-1]}']")
        if target is None:
            raise RuntimeError(f"missing server equipment node: {relative_path}/{property_path}")
        identifier = target.find("./int[@name='id']")
        if identifier is None:
            identifier = target.find("./imgdir[@name='0']/int[@name='id']")
        if identifier is None or int(identifier.get("value")) != skill_id:
            raise RuntimeError(f"unexpected server equipment skill: {relative_path}")
        start, end = engine.find_imgdir_block(original, parts[-1])
        # The leaf names repeat elsewhere, so anchor the search after its parent path.
        marker_offset = original.find(marker)
        candidates = []
        search = 0
        while True:
            try:
                candidate_start, candidate_end = engine.find_imgdir_block(
                    original[search:], parts[-1]
                )
            except RuntimeError:
                break
            candidate_start += search
            candidate_end += search
            if candidate_start <= marker_offset < candidate_end:
                candidates.append((candidate_start, candidate_end))
            search = candidate_start + 1
        if len(candidates) != 1:
            raise RuntimeError(f"ambiguous server equipment node: {relative_path}/{property_path}")
        start, end = candidates[0]
        line_start = original.rfind("\n", 0, start) + 1
        if not original[line_start:start].strip():
            start = line_start
        if end < len(original) and original[end] == "\n":
            end += 1
        updated = original[:start] + original[end:]
        ET.fromstring(updated)
        if not dry_run:
            engine.base.atomic_write_text(path, updated)


def validate() -> None:
    skill_image = WzImage.from_bytes(
        CLIENT_SKILL.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_SKILL.name
    )
    client = skill_image.parse()
    string_image = WzImage.from_bytes(
        CLIENT_STRING.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_STRING.name
    )
    client_strings = string_image.parse()
    if skill_image.truncated or skill_image.parse_warnings:
        raise RuntimeError(f"malformed client skill IMG: {skill_image.parse_warnings}")
    if string_image.truncated or string_image.parse_warnings:
        raise RuntimeError(f"malformed client String IMG: {string_image.parse_warnings}")
    server_skills = ET.parse(SERVER_SKILL).getroot().find("./imgdir[@name='skill']")
    server_strings = ET.parse(SERVER_STRING).getroot()
    for skill_id in RETIRED_SKILL_IDS:
        if client.get(f"skill/{skill_id}") is not None:
            raise RuntimeError(f"client skill still exists: {skill_id}")
        if client_strings.get(str(skill_id)) is not None:
            raise RuntimeError(f"client string still exists: {skill_id}")
        if server_skills.find(f"./imgdir[@name='{skill_id}']") is not None:
            raise RuntimeError(f"server skill still exists: {skill_id}")
        if server_strings.find(f"./imgdir[@name='{skill_id}']") is not None:
            raise RuntimeError(f"server string still exists: {skill_id}")
    for skill_id in PROTECTED_SKILL_IDS:
        if client.get(f"skill/{skill_id}") is None:
            raise RuntimeError(f"protected client skill is missing: {skill_id}")
        if server_skills.find(f"./imgdir[@name='{skill_id}']") is None:
            raise RuntimeError(f"protected server skill is missing: {skill_id}")
    for relative_path, _, skill_id in EQUIPMENT_REFS:
        client = WzImage.from_file(
            str(ROOT / "clien/Data/Character" / relative_path),
            key=WzKey.for_region("GMS"), name=Path(relative_path).name,
        ).parse()
        stack = [client]
        while stack:
            node = stack.pop()
            if getattr(node, "value", None) == skill_id:
                raise RuntimeError(f"client equipment still grants {skill_id}: {relative_path}")
            if hasattr(node, "children"):
                stack.extend(node.children())
        server_text = (
            ROOT / "gms-server/wz/Character.wz" / f"{relative_path}.xml"
        ).read_text(encoding="utf-8")
        if f'<int name="id" value="{skill_id}"' in server_text:
            raise RuntimeError(f"server equipment still grants {skill_id}: {relative_path}")


def retire(*, dry_run: bool = False) -> None:
    patch_client_skill(dry_run)
    patch_client_strings(dry_run)
    patch_server(SERVER_SKILL, dry_run)
    patch_server(SERVER_STRING, dry_run)
    patch_client_equipment(dry_run)
    patch_server_equipment(dry_run)
    if not dry_run:
        validate()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    retire(dry_run=args.dry_run)
    mode = "checked" if args.dry_run else "retired"
    print(
        f"{mode} Night Lord retired nodes: "
        + ", ".join(map(str, RETIRED_SKILL_IDS))
    )


if __name__ == "__main__":
    main()
