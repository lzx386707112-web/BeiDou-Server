#!/usr/bin/env python3
"""Project Damien boss skill tables onto the legacy GMS three-field contract."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
import patch_damien_scene_attacks as scene_patch  # noqa: E402
from wzpy import WzImage, WzIntProperty, WzSubProperty  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_outside(before: bytes, after: bytes, allowed: set[tuple[str, ...]]) -> None:
    before_records, before_orders = arc.raw_record_state(before)
    after_records, after_orders = arc.raw_record_state(after)
    for path, raw in before_records.items():
        affected = any(path[: len(root)] == root or root[: len(path)] == path for root in allowed)
        if not affected and after_records.get(path) != raw:
            raise RuntimeError(f"protected record changed: {path}")
    for parent, names in before_orders.items():
        if any(parent[: len(root)] == root for root in allowed):
            continue
        if after_orders.get(parent) != names:
            raise RuntimeError(f"protected sibling order changed: {parent}")


def build_skill_table(entries: tuple[dict, ...]) -> WzSubProperty:
    skill = WzSubProperty("skill")
    for index, entry in enumerate(entries):
        record = WzSubProperty(str(index), skill)
        for name in ("skill", "action", "level"):
            record.add(WzIntProperty(name, int(entry[name]), record))
        skill.add(record)
    return skill


def read_skill_table(image: WzImage) -> list[dict[str, int]]:
    skill_node = image.root.get("info/skill")
    if not isinstance(skill_node, WzSubProperty):
        raise RuntimeError("missing info/skill")
    current = []
    for child in skill_node.children():
        if not child.name.isdigit():
            continue
        record = {entry.name: int(entry.value) for entry in child.children()}
        current.append(record)
    return current


def assert_legacy_skill_table(mob_id: int, image: WzImage) -> None:
    expected = list(demian.skills_for_mob(mob_id))
    actual = read_skill_table(image)
    if actual != expected:
        raise RuntimeError(f"{mob_id} skill table mismatch: {actual} != {expected}")
    for entry in actual:
        if set(entry) != set(demian.LEGACY_SKILL_FIELDS):
            raise RuntimeError(f"{mob_id} kept modern skill fields: {entry}")
        if entry["skill"] in demian.FORBIDDEN_SKILLS or entry["skill"] == 170:
            raise RuntimeError(f"{mob_id} references unsafe MobSkill {entry['skill']}")


def patch_client_mob(mob_id: int) -> None:
    client = demian.client_mob_path(mob_id)
    original = client.read_bytes()
    entries = demian.skills_for_mob(mob_id)
    image = WzImage.from_bytes(original, key=arc.GMS_KEY, name=client.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"{client.name} parse failed before skill projection")
    if read_skill_table(image) == list(entries):
        checked = image
    else:
        skill = build_skill_table(entries)
        updated = replace_img_record(original, ("info", "skill"), skill, region="GMS").data
        verify_outside(original, updated, {("info", "skill")})
        checked = WzImage.from_bytes(updated, key=arc.GMS_KEY, name=client.name)
        checked.parse()
        if checked.truncated or checked.parse_warnings:
            raise RuntimeError(f"{client.name} parse failed after skill projection")
        arc.atomic_write_bytes(client, updated)
    assert_legacy_skill_table(mob_id, checked)


def patch_server_mob(mob_id: int) -> None:
    server = demian.server_mob_path("wz", mob_id)
    text = server.read_text(encoding="utf-8")
    skill = build_skill_table(demian.skills_for_mob(mob_id))
    start, end = scene_patch.xml_imgdir_span(text, "skill")
    line_start = text.rfind("\n", 0, start) + 1
    fragment = arc.property_to_xml(skill, indent=2)
    updated = text[:line_start] + fragment + text[end:] if text[line_start:end] != fragment else text
    root = ET.fromstring(updated)
    skill_root = root.find('./imgdir[@name="info"]/imgdir[@name="skill"]')
    if skill_root is None:
        raise RuntimeError(f"{server.name} missing info/skill after projection")
    for entry in skill_root.findall("imgdir"):
        names = {child.get("name") for child in entry}
        if names != set(demian.LEGACY_SKILL_FIELDS):
            raise RuntimeError(f"{server.name} kept modern skill fields: {names}")
    if updated != text:
        arc.atomic_write_text(server, updated)


def sync_dependency_mob(boss_id: int, dependency_id: int) -> None:
    boss_client = demian.client_mob_path(boss_id)
    dependency_client = demian.client_mob_path(dependency_id)
    boss_bytes = boss_client.read_bytes()
    if dependency_client.read_bytes() != boss_bytes:
        arc.atomic_write_bytes(dependency_client, boss_bytes)

    boss_xml = demian.server_mob_path("wz", boss_id).read_text(encoding="utf-8")
    dependency_xml = boss_xml.replace(f'name="{boss_id}.img"', f'name="{dependency_id}.img"', 1)
    ET.fromstring(dependency_xml)
    dependency_server = demian.server_mob_path("wz", dependency_id)
    if dependency_server.read_text(encoding="utf-8") != dependency_xml:
        arc.atomic_write_text(dependency_server, dependency_xml)


def patch_all() -> None:
    for mob_id in demian.BOSS_IDS:
        patch_client_mob(mob_id)
        patch_server_mob(mob_id)
    for boss_id, dependency_id in demian.DEPENDENCY_MOB_BY_BOSS.items():
        sync_dependency_mob(boss_id, dependency_id)
        dependency_image = WzImage.from_bytes(
            demian.client_mob_path(dependency_id).read_bytes(),
            key=arc.GMS_KEY,
            name=f"{dependency_id}.img",
        )
        dependency_image.parse()
        assert_legacy_skill_table(dependency_id, dependency_image)


def output_paths() -> tuple[Path, ...]:
    paths = []
    for mob_id in (*demian.BOSS_IDS, *demian.DEPENDENCY_MOBS):
        paths.extend((demian.client_mob_path(mob_id), demian.server_mob_path("wz", mob_id)))
    return tuple(paths)


def main() -> int:
    patch_all()
    first = {str(path.relative_to(ROOT)): sha256_file(path) for path in output_paths()}
    patch_all()
    second = {str(path.relative_to(ROOT)): sha256_file(path) for path in output_paths()}
    if first != second:
        raise RuntimeError(f"Damien legacy skill patch is not idempotent: {first} vs {second}")
    print("damien legacy skill table patch ok")
    for path, digest in first.items():
        print(f"{path} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
