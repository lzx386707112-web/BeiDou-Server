#!/usr/bin/env python3
"""Rebuild client quest additions without signed-root aliases or full encoding."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import add_npc_3003104_daily_items as daily_items  # noqa: E402
import add_npc_3003104_reverse_city_quests as daily_quests  # noqa: E402
import add_reverse_city_story_quests as story  # noqa: E402
import migrate_arcane_river_expansion as arc  # noqa: E402
from wzpy import WzImage, WzSubProperty  # noqa: E402
from wzpy.incremental_img import replace_img_record  # noqa: E402


WORKBENCH_SIGNED_QUEST_IDS = (
    -31434, -31433, -31432, -31431, -31425, -31424, -31423,
    -31420, -31419, -31418, -31417,
    -31336, -31335, -31334, -31333, -31332, -31331, -31330,
    -31329, -31328, -31327, -31326, -31325, -31324, -31323,
    -31322, -31321, -31320, -31319, -31318,
    -27835, -27834, -27833, -27832, -27831, -27830, -27829,
    -27828, -27827, -27826, -27825, -27824, -27823, -27822,
    -27821, -27820, -27819, -27818, -27817, -27816, -27815,
    -27814, -27813, -27812, -27811, -27810,
    -26519, -26518, -26517, -26516, -26515, -26514, -26513,
    -26512, -26511, -26510, -26509, -26508, -26507, -26506,
    -26505, -26504, -26503,
    -26472, -26471, -26470, -26469, -26468, -26467, -26466,
)
WORKBENCH_CLIENT_QUEST_IDS = tuple(
    quest_id + 65536 for quest_id in WORKBENCH_SIGNED_QUEST_IDS
)


def git_baseline(path: Path, ref: str = "HEAD") -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"{ref}:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def server_quest_nodes(name: str) -> list[WzSubProperty]:
    root = ET.parse(story.SERVER_QUESTS[name]).getroot()
    nodes: list[WzSubProperty] = []
    for signed_id in WORKBENCH_SIGNED_QUEST_IDS:
        element = root.find(f"./imgdir[@name='{signed_id}']")
        if element is None:
            raise RuntimeError(f"server {name} record is missing: {signed_id}")
        node = daily_quests.xml_property(element)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"invalid server {name} record: {signed_id}")
        node.name = str(signed_id + 65536)
        nodes.append(node)
    return nodes


def replace_nodes(data: bytes, nodes: list[WzSubProperty]) -> bytes:
    records, _ = arc.raw_record_state(data)
    for node in nodes:
        if (node.name,) not in records:
            raise RuntimeError(f"client quest alias is missing: {node.name}")
        data = replace_img_record(
            data, (node.name,), node, region="GMS"
        ).data
    return data


def insert_nodes(
    data: bytes,
    parent_path: tuple[str, ...],
    nodes: list[WzSubProperty],
    before_name: str,
) -> bytes:
    for node in nodes:
        data = arc.insert_property_record_before(
            data, parent_path, node, before_name
        )
    return data


def verify_rebuild(
    path: Path,
    baseline: bytes,
    current: bytes,
    rebuilt: bytes,
    approved: set[tuple[str, ...]],
    replacements: set[tuple[str, ...]],
) -> None:
    additions = approved - replacements
    before_records, before_order = arc.raw_record_state(baseline)

    def verify_candidate(label: str, candidate: bytes):
        candidate_records, candidate_order = arc.raw_record_state(candidate)
        removed = set(before_records) - set(candidate_records)
        if any(
            not any(record[:len(root)] == root for root in replacements)
            for record in removed
        ):
            raise RuntimeError(
                f"{label} IMG removed protected records in {path}: {sorted(removed)}"
            )
        added = set(candidate_records) - set(before_records)
        if any(
            not any(record[:len(root)] == root for root in additions | replacements)
            for record in added
        ):
            raise RuntimeError(
                f"{label} IMG added unapproved records in {path}: {sorted(added)}"
            )
        for parent, names in before_order.items():
            if any(parent[:len(root)] == root for root in replacements):
                continue
            added_children = {
                root[len(parent)]
                for root in additions
                if len(root) == len(parent) + 1 and root[:len(parent)] == parent
            }
            protected_order = tuple(
                name for name in candidate_order[parent] if name not in added_children
            )
            if protected_order != names:
                raise RuntimeError(
                    f"{label} IMG reordered protected siblings at {parent}"
                )
        for record_path, raw in before_records.items():
            affected = any(
                record_path[:len(root)] == root or root[:len(record_path)] == record_path
                for root in additions | replacements
            )
            if not affected and candidate_records.get(record_path) != raw:
                raise RuntimeError(
                    f"{label} IMG changed protected record: {record_path}"
                )
        return candidate_records, candidate_order

    verify_candidate("current", current)
    after_records, after_order = verify_candidate("rebuilt", rebuilt)

    expected_additions = {root for root in additions if root not in before_records}
    actual_additions = {
        root for root in additions if root in after_records and root not in before_records
    }
    if actual_additions != expected_additions:
        raise RuntimeError(
            f"incomplete rebuilt records in {path}: "
            f"expected={sorted(expected_additions)} actual={sorted(actual_additions)}"
        )
    if any(name.startswith("-") for name in after_order[()]):
        raise RuntimeError(f"signed client quest root remains in {path}")
    image = WzImage.from_bytes(rebuilt, key=arc.GMS_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"rebuilt IMG failed validation: {path} "
            f"truncated={image.truncated} warnings={image.parse_warnings}"
        )


def main() -> int:
    rebuilt: dict[Path, bytes] = {}
    approved_by_path: dict[Path, set[tuple[str, ...]]] = {}

    story_quests, _ = story.build_quest_nodes()
    for name in story.QUEST_NAMES:
        path = story.CLIENT_QUESTS[name]
        baseline = git_baseline(path, "HEAD^")
        data = replace_nodes(baseline, server_quest_nodes(name))
        data = insert_nodes(
            data,
            (),
            story.client_quest_nodes(story_quests[name]),
            "37701",
        )
        data = insert_nodes(
            data,
            (),
            [
                node
                for node in daily_quests.client_quest_nodes(
                    daily_quests.server_quest_nodes(name)
                )
                if int(node.name) <= 34150
            ],
            "34200",
        )
        data = insert_nodes(
            data,
            (),
            [
                node
                for node in daily_quests.client_quest_nodes(
                    daily_quests.server_quest_nodes(name)
                )
                if int(node.name) >= 39055
            ],
            "39064",
        )
        rebuilt[path] = data
        approved_by_path[path] = {
            (str(quest_id),)
            for quest_id in (
                WORKBENCH_CLIENT_QUEST_IDS
                + story.TMS_QUEST_IDS
                + daily_quests.TMS_QUEST_IDS
            )
        }

    daily_item_nodes, daily_string_nodes = daily_items.build_nodes()
    story_item_nodes, story_string_nodes = story.build_item_nodes()
    for path, parent_path, daily_nodes, story_nodes, prefix in (
        (
            daily_items.CLIENT_ITEM,
            (),
            daily_item_nodes,
            story_item_nodes,
            "0",
        ),
        (
            daily_items.CLIENT_STRING,
            ("Etc",),
            daily_string_nodes,
            story_string_nodes,
            "",
        ),
    ):
        baseline = git_baseline(path)
        low_nodes = [node for node in daily_nodes if int(node.name) < 4036000]
        high_nodes = [node for node in daily_nodes if int(node.name) >= 4036000]
        data = insert_nodes(
            baseline, parent_path, low_nodes, f"{prefix}4034937"
        )
        data = insert_nodes(
            data, parent_path, story_nodes, f"{prefix}4036710"
        )
        data = insert_nodes(
            data, parent_path, high_nodes, f"{prefix}4036710"
        )
        rebuilt[path] = data
        approved_by_path[path] = {
            (*parent_path, node.name)
            for node in daily_nodes + story_nodes
        }

    for path, data in rebuilt.items():
        baseline_ref = "HEAD^" if path in story.CLIENT_QUESTS.values() else "HEAD"
        baseline = git_baseline(path, baseline_ref)
        verify_rebuild(
            path,
            baseline,
            path.read_bytes(),
            data,
            approved_by_path[path],
            (
                {(str(quest_id),) for quest_id in WORKBENCH_CLIENT_QUEST_IDS}
                if path in story.CLIENT_QUESTS.values()
                else set()
            ),
        )

    changed = []
    for path, data in rebuilt.items():
        if path.read_bytes() == data:
            continue
        arc.atomic_write_bytes(path, data)
        changed.append(path)

    print(f"Client quest and item records rebuilt: changed={len(changed)}")
    for path in changed:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{path.relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
